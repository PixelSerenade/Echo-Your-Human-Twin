import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.services.message_intent import classify_by_keywords, world_fact_subtype
from backend.services.world_lookup import check_world_rate_limit, extract_place, sanitize_public_query
from backend.main import app
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID


@pytest_asyncio.fixture(scope="module", autouse=True)
async def seed_world_test_user():
    await init_models()
    await seed_demo_persona()


@pytest.mark.parametrize(("question", "subtype"), [
    ("Will it rain tomorrow in Mangaluru?", "weather"),
    ("Is there a government holiday next week in Karnataka?", "holidays_calendar"),
    ("What's the latest news today?", "news_current_events"),
    ("Who won the match last night?", "other_live"),
])
def test_live_world_questions_get_live_subtype(question, subtype):
    assert world_fact_subtype(question) == subtype
    assert classify_by_keywords(question) == "world_fact_lookup"


def test_mixed_personal_and_public_question_is_split():
    question = "Will it rain tomorrow in Mangaluru, and do I have my meeting?"
    assert classify_by_keywords(question) == "mixed_fact_lookup"


def test_public_query_sanitizer_removes_personal_clause_and_identity():
    result = sanitize_public_query("Will it rain tomorrow in Mangaluru, and do I have my client meeting, Alex?", "Alex", "alex@example.com")
    assert "Mangaluru" in result and "rain" in result
    assert "meeting" not in result and "Alex" not in result and "example.com" not in result


def test_explicit_place_extraction():
    assert extract_place("Will it rain tomorrow in Mangaluru?") == "Mangaluru"


def test_holidays_without_region_are_classified_for_region_question():
    assert world_fact_subtype("Is there a government holiday next week?") == "holidays_calendar"


def test_world_lookup_has_per_user_rate_limit():
    user = "test-world-limit"
    assert all(check_world_rate_limit(user, now=100 + i) for i in range(12))
    assert not check_world_rate_limit(user, now=111)


@pytest.mark.asyncio
async def test_weather_without_city_asks_instead_of_guessing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/ask", json={"user_id": USER_ID, "question": "What's the weather tomorrow?"})
    assert response.status_code == 200
    data = response.json()
    assert data["fact_lookup_status"] == "missing_place"
    assert data["message"] == "Which city should I check?"
    assert data["lookup_sources"] == []


@pytest.mark.asyncio
async def test_holiday_without_region_asks_for_scope_instead_of_searching():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/ask", json={"user_id": USER_ID, "question": "Is there a government holiday next week?"})
    assert response.status_code == 200
    data = response.json()
    assert data["fact_lookup_status"] == "missing_region"
    assert "Which state" in data["message"]
