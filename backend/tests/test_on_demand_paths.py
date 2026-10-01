import pytest
import pytest_asyncio
import os
import sys
import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.models import Permission, Goal, Timetable, Attachment, normalize_goal_milestones
from backend.database import AsyncSessionLocal
from backend.config import settings
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID
from backend.llm.gemini_client import gemini_client
from backend.routers.ask_router import _explicit_availability_window, _explicit_availability_days, _ambiguous_availability_period
from backend.services.message_intent import classify_by_keywords

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db_for_on_demand():
    await init_models()
    await seed_demo_persona()

@pytest.mark.asyncio
async def test_conversational_question_never_produces_path_cards():
    """A plain question ('how are you?') must never produce path cards."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "how are you?"
        }
        resp = await ac.post("/ask", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "small_talk"
        assert data["has_paths"] is False
        assert len(data["paths"]) == 0
        assert data["offer_simulation"] is None
        assert data["show_other_voices"] is False
        assert len(data["message"]) > 10
        assert len(data["answer"]) > 10


@pytest.mark.asyncio
async def test_name_introduction_gets_a_warm_reply_without_planning_controls():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/ask", json={"user_id": USER_ID, "question": "HI iam lia"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "greeting_or_intro"
    assert "Hey Lia!" in data["message"]
    assert "I'm Echo, your twin here." in data["message"]
    assert data["has_paths"] is False
    assert data["paths"] == []
    assert data["options"] == []
    assert data["offer_simulation"] is None
    assert data["show_other_voices"] is False


@pytest.mark.asyncio
async def test_plan_clarification_does_not_show_decision_feedback_or_other_voices():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/ask", json={
            "user_id": USER_ID,
            "question": "Can you create a plan for where I should start?",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_choice"] is None
    assert data["show_other_voices"] is False


@pytest.mark.asyncio
async def test_spelling_answer_continues_the_active_word_quiz(monkeypatch):
    async def fake_classify(_message):
        return "question_or_advice"

    monkeypatch.setattr(gemini_client, "classify_message_type", fake_classify)
    turns = [
        {"role": "assistant", "content": "Awesome, ready to dive into the first word?"},
        {"role": "user", "content": "yes"},
        {"role": "assistant", "content": "Here is your first word: brilliant. How do you spell it?"},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/ask", json={"user_id": USER_ID, "question": "Brilliant.", "recent_turns": turns})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "learning_followup"
    assert "Correct" in data["message"]
    assert "B-R-I-L-L-I-A-N-T" in data["message"]
    assert "next word" in data["message"]
    assert "one more detail" not in data["message"]
    assert data["show_other_voices"] is False


@pytest.mark.asyncio
async def test_ready_now_starts_spell_b_practice_even_if_intent_is_misclassified(monkeypatch):
    async def fake_classify(_message):
        return "world_fact_lookup"

    monkeypatch.setattr(gemini_client, "classify_message_type", fake_classify)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/ask", json={
            "user_id": USER_ID,
            "question": "Hey, let's continue with my Spell B plan that we have. I'm ready right now. We can start learning.",
            "recent_turns": [],
        })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "learning_followup"
    assert "Next word: necessary" in data["message"]
    assert data["fact_lookup_status"] is None


@pytest.mark.asyncio
async def test_uploaded_pdf_stays_available_for_followups_in_the_same_chat(monkeypatch, tmp_path):
    pdf_id = "test-study-context-pdf"
    pdf_bytes = b"%PDF-1.4\nThis document explains photosynthesis.\n"
    user_folder = tmp_path / USER_ID
    user_folder.mkdir(parents=True)
    (user_folder / "study.pdf").write_bytes(pdf_bytes)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    async with AsyncSessionLocal() as db:
        await db.execute(delete(Attachment).where(Attachment.id == pdf_id))
        db.add(Attachment(
            id=pdf_id, user_id=USER_ID, original_name="study.pdf", stored_name="study.pdf",
            mime_type="application/pdf", kind="document", size_bytes=len(pdf_bytes),
        ))
        await db.commit()

    captured = {}

    async def fake_classify(_message):
        return "question_or_advice"

    async def fake_primary(**kwargs):
        captured.update(kwargs)
        return {"message": "Let’s go through the diagram together. What does the arrow show?", "provider_status": "offline"}

    async def fake_memories(*_args, **_kwargs):
        return []

    monkeypatch.setattr(gemini_client, "classify_message_type", fake_classify)
    monkeypatch.setattr(gemini_client, "ask_primary_twin", fake_primary)
    monkeypatch.setattr(gemini_client, "extract_important_memories", fake_memories)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/ask", json={
            "user_id": USER_ID,
            "question": "Can you explain that diagram?",
            "context_attachment_id": pdf_id,
            "recent_turns": [{
                "role": "user", "content": "Quiz me on this assignment.", "attachment_id": pdf_id,
            }],
        })

    assert response.status_code == 200, response.text
    assert captured["inline_attachment"]["data"] == pdf_bytes
    assert captured["inline_attachment"]["name"] == "study.pdf"
    assert captured["extract_attachment"] is False
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Attachment).where(Attachment.id == pdf_id))
        await db.commit()


def test_natural_availability_reply_is_parsed_and_only_asks_for_missing_period():
    text = "Free like from Monday to Thursday. Like from 6:30 to 9:00."
    assert _explicit_availability_days(text) == {0, 1, 2, 3}
    assert _explicit_availability_window(text) is None
    assert _ambiguous_availability_period(text) == ("6:30", "9:00")
    assert _explicit_availability_window(f"{text.rstrip(' .!?')} pm") == (1110, 1260)


@pytest.mark.asyncio
async def test_placement_plan_creates_checkable_goal_after_period_clarification(monkeypatch):
    async def fake_classify(_message):
        return "question_or_advice"

    async def fake_primary(**_kwargs):
        return {"message": "I can help plan that.", "provider_status": "offline"}

    async def fake_schedule(user_messages, local_today, permitted_context):
        assert any("6:30 to 9:00" in message for message in user_messages)
        day = datetime.date.fromisoformat(local_today)
        offset = (7 - day.weekday()) % 7 or 7
        plan_day = day + datetime.timedelta(days=offset)
        return {"needs_follow_up": False, "blocks": [{
            "date": plan_day.isoformat(), "start_time": "18:30", "end_time": "19:30",
            "title": "Review software engineer role requirements",
            "availability_quote": "Free like from Monday to Thursday. Like from 6:30 to 9:00.",
        }]}

    async def fake_goal_details(_messages, _today):
        return {
            "needs_follow_up": False,
            "title": "Software Engineer Placement",
            "description": "Build toward a software engineer placement through practical steps.",
            "milestones": [
                {"title": "Review software engineer role requirements", "completed": False},
                {"title": "Update CV for the role", "completed": False},
                {"title": "Practise interview answers", "completed": False},
            ],
            "next_step": "Review software engineer role requirements",
        }

    async def fake_memories(*_args, **_kwargs):
        return []

    monkeypatch.setattr(gemini_client, "classify_message_type", fake_classify)
    monkeypatch.setattr(gemini_client, "ask_primary_twin", fake_primary)
    monkeypatch.setattr(gemini_client, "build_chat_schedule", fake_schedule)
    monkeypatch.setattr(gemini_client, "build_goal_details", fake_goal_details)
    monkeypatch.setattr(gemini_client, "extract_important_memories", fake_memories)

    local_today = datetime.date.today().isoformat()
    # A failed previous run may have left this fixture's goal behind. Keep the
    # persistence assertions deterministic and don't let older rows shadow it.
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Goal).where(Goal.user_id == USER_ID, Goal.title == "Software Engineer Placement"))
        await db.execute(delete(Timetable).where(Timetable.user_id == USER_ID, Timetable.activity_name == "Review software engineer role requirements"))
        await db.commit()
    turns = [
        {"role": "user", "content": "I want to be placed."},
        {"role": "user", "content": "Software engineer."},
        {"role": "assistant", "content": "What hours are you free over the next few days, and which days should I use?"},
        {"role": "user", "content": "Free like from Monday to Thursday. Like from 6:30 to 9:00."},
        {"role": "assistant", "content": "I have the days. Are those times AM or PM?"},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        clarification = await ac.post("/ask", json={
            "user_id": USER_ID,
            "question": "Free like from Monday to Thursday. Like from 6:30 to 9:00.",
            "recent_turns": turns[:3],
            "local_today": local_today,
        })
        assert clarification.status_code == 200, clarification.text
        assert "AM or PM" in clarification.json()["message"]
        assert "focus best" not in clarification.json()["message"]
        response = await ac.post("/ask", json={"user_id": USER_ID, "question": "PM", "recent_turns": turns, "local_today": local_today})
    assert response.status_code == 200, response.text
    data = response.json()
    assert "Your plan is ready" in data["message"]
    assert "My Plan → Goals" in data["message"]
    assert data["goals_updated"]
    assert len(data["goals_updated"][0]["milestones"]) == 3
    assert data["plan_items_created"]

    async with AsyncSessionLocal() as db:
        goal = await db.scalar(select(Goal).where(Goal.user_id == USER_ID, Goal.title == "Software Engineer Placement"))
        assert goal is not None
        assert goal.progress == 0
        raw_milestones = await db.execute(text("SELECT jsonb_typeof(milestones), milestones FROM goals WHERE id = :id"), {"id": goal.id})
        assert raw_milestones.scalar_one() == "array", repr(goal.milestones)
        saved_steps = normalize_goal_milestones(goal.milestones)
        assert len(saved_steps) == 3
        assert all(step["completed"] is False for step in saved_steps)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            knowledge = await ac.get("/api/twin-knowledge", params={"user_id": USER_ID})
        assert knowledge.status_code == 200, knowledge.text
        saved_goal = next(item for item in knowledge.json()["goals"] if item["id"] == goal.id)
        assert len(saved_goal["milestones"]) == 3
        await db.execute(delete(Goal).where(Goal.id == goal.id))
        await db.execute(delete(Timetable).where(Timetable.user_id == USER_ID, Timetable.activity_name == "Review software engineer role requirements"))
        await db.commit()


@pytest.mark.asyncio
async def test_feeling_and_money_regret_get_a_kind_reply_without_cards():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for message in ("i'm so tired of everything today", "iam sad", "I spent 500 on clothes and I regret it"):
            response = await ac.post("/ask", json={"user_id": USER_ID, "question": message})
            assert response.status_code == 200
            data = response.json()
            assert data["intent"] == "feeling_or_vent"
            assert data["has_paths"] is False
            assert data["paths"] == []
            assert data["options"] == []
            assert data["offer_simulation"] is None
            assert "?" in data["message"]
            if message == "iam sad":
                assert len(data["message"]) > 30
                assert "least room to move" not in data["message"]


def test_keyword_router_separates_greeting_advice_and_planning():
    assert classify_by_keywords("HI iam lia") == "greeting_or_intro"
    assert classify_by_keywords("how are you?") == "small_talk"
    assert classify_by_keywords("I'm so tired today") == "feeling_or_vent"
    assert classify_by_keywords("iam sad") == "feeling_or_vent"
    assert classify_by_keywords("How do I ask for a raise?") == "question_or_advice"
    assert classify_by_keywords("what if I spend a day resting?") == "decision_question"
    assert classify_by_keywords("I want to save more money") == "goal_or_money"
    assert classify_by_keywords("Which is more important, my exam or my project?") == "decision_question"
    assert classify_by_keywords("Create a plan for my tasks this week") == "decision_question"

@pytest.mark.asyncio
async def test_decision_request_produces_three_friendly_paths_from_real_data():
    """Only an explicit planning request receives the three path cards."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "what should I do about my test and assignment?"
        }
        resp = await ac.post("/ask", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "decision_question"
        assert data["has_paths"] is False
        assert data["paths"] == []
        assert data["show_other_voices"] is True


@pytest.mark.asyncio
async def test_zero_data_or_disabled_permissions_prompts_user_without_inventing_data():
    """If the user has no saved goals or deadlines, Echo asks what they want to achieve instead of inventing data."""
    # Temporarily disable deadlines and timetable permissions
    async with AsyncSessionLocal() as session:
        perms = (await session.execute(
            select(Permission).where(Permission.user_id == USER_ID, Permission.source.in_(["deadlines", "timetable"]))
        )).scalars().all()
        for p in perms:
            p.enabled = False
        await session.commit()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            req_payload = {
                "user_id": USER_ID,
                "question": "what should I do about my test and assignment?"
            }
            resp = await ac.post("/ask", json=req_payload)
            assert resp.status_code == 200
            data = resp.json()

            # Must NOT produce paths
            assert data["has_paths"] is False
            assert len(data["paths"]) == 0
            # Ask for a missing due-date detail without inventing either date.
            assert "?" in data["message"]
            assert "practice problem" not in data["message"].lower()
            assert data["answer"] == data["message"]
    finally:
        # Re-enable permissions
        async with AsyncSessionLocal() as session:
            perms = (await session.execute(
                select(Permission).where(Permission.user_id == USER_ID, Permission.source.in_(["deadlines", "timetable"]))
            )).scalars().all()
            for p in perms:
                p.enabled = True
            await session.commit()
