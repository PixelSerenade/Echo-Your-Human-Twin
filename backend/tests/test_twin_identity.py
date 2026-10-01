import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.database import AsyncSessionLocal
from backend.llm.gemini_client import GeminiClient
from backend.main import app
from backend.models import User
from backend.scripts.generate_data import init_models
from backend.services.identity import resolve_twin_name


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_identity_schema():
    await init_models()


def test_unrenamed_user_name_collision_falls_back_to_echo():
    user = User(
        id="identity-unit-user",
        name="Rakshu",
        email="identity-unit@example.com",
        twin_name="rakshu",
        twin_name_customized=False,
    )
    assert resolve_twin_name(user) == "Echo"
    assert user.twin_name == "Echo"


def test_deliberate_custom_name_is_preserved_even_if_it_matches_user():
    user = User(
        id="identity-custom-user",
        name="Rakshu",
        email="identity-custom@example.com",
        twin_name="Rakshu",
        twin_name_customized=True,
    )
    assert resolve_twin_name(user) == "Rakshu"


@pytest.mark.asyncio
async def test_account_identity_and_persisted_twin_rename_are_separate():
    email = f"rakshu.{uuid.uuid4()}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        signup = await client.post("/api/auth/signup", json={
            "name": "Rakshu",
            "email": email,
            "password": "Password123!",
        })
        assert signup.status_code == 200
        session = signup.json()
        user_id = session["user_id"]
        assert session["name"] == "Rakshu"
        assert session["twin_name"] == "Echo"
        assert session["twin_name_customized"] is False

        renamed = await client.put("/api/profile/twin-name", json={
            "user_id": user_id,
            "twin_name": "Nova",
        })
        assert renamed.status_code == 200
        assert renamed.json()["user_name"] == "Rakshu"
        assert renamed.json()["twin_name"] == "Nova"

        profile = await client.get(f"/profile/{user_id}")
        assert profile.status_code == 200
        assert profile.json()["user_name"] == "Rakshu"
        assert profile.json()["twin_name"] == "Nova"

    async with AsyncSessionLocal() as session_db:
        user = await session_db.get(User, user_id)
        user.twin_name = user.name
        user.twin_name_customized = False
        await session_db.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        repaired = await client.get("/api/auth/me", headers={"X-User-Id": user_id})
        assert repaired.status_code == 200
        assert repaired.json()["name"] == "Rakshu"
        assert repaired.json()["twin_name"] == "Echo"


@pytest.mark.asyncio
async def test_gemini_prompts_keep_user_and_twin_names_in_their_roles(monkeypatch):
    client = GeminiClient()
    client.cache = {}
    captured = {"json": "", "text": ""}

    async def fake_json(prompt, system_instruction="", temperature=0.2):
        captured["json"] = prompt
        return {"deadline_risk_alert": "", "options": []}

    async def fake_text(prompt, system_instruction="", temperature=0.8):
        captured["text"] = prompt
        return "Your next step can stay small and practical. Let's choose the task with the least room to move."

    monkeypatch.setattr(client, "call_gemini_json", fake_json)
    monkeypatch.setattr(client, "call_gemini_text", fake_text)
    monkeypatch.setattr(client, "_save_cache", lambda: None)

    result = await client.ask_primary_twin(
        primary_twin="emotional",
        question="What should I focus on?",
        permitted_context="No permitted personal data available.",
        ml_insights={"why_factors": []},
        deadline_risk_summary="",
        user_name="Rakshu",
        twin_name="Echo",
        message_type="decision_question",
    )

    assert 'user_name: "Rakshu"' in captured["text"]
    assert 'twin_name: "Echo"' in captured["text"]
    assert result["badge"] == "Emotional style"
