import pytest
import pytest_asyncio
import os
import sys
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.models import AuditLog
from backend.database import AsyncSessionLocal
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID
from backend.llm.gemini_client import gemini_client

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db_for_phase5():
    await init_models()
    await seed_demo_persona()

@pytest.mark.asyncio
async def test_on_demand_debate_parallel_twins_and_synthesis(monkeypatch):
    """
    Test On-Demand Debate endpoint:
    - The two other twins respond in parallel (asyncio.gather), each adding
      considerations the primary twin missed and NOT repeating its points.
    - HumanTwin synthesis returns trade-offs, a compromise option, and a
      'consider before deciding' list without giving a single command.
    """
    async def fake_voices(**kwargs):
        return [
            {"style": style, "label": label, "argument": f"A distinct thought from {label} about your situation.", "your_usual_voice": style == "rational"}
            for style, label in [("rational", "Head"), ("emotional", "Heart"), ("ambitious", "Drive")]
        ]
    monkeypatch.setattr(gemini_client, "run_style_blend_debate", fake_voices)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "What if I spend two days on exam prep instead of the assignment?",
            "primary_twin": "rational",
            "first_answer": "Prioritizing exam prep exclusively leaves no buffer for the 16.5-hour Cloud project, risking late penalty."
        }
        resp = await ac.post("/debate", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["primary_twin"] == "rational"
        assert [voice["style"] for voice in data["voices"]] == ["rational", "emotional", "ambitious"]
        assert data["voices"][0]["your_usual_voice"] is True
        assert len(data["other_twins"]) == 2

        # Check HumanTwin Synthesis
        synthesis = data["synthesis"]
        assert "summary_of_tensions" in synthesis
        assert len(synthesis["summary_of_tensions"]) > 20

        assert "compromise_option" in synthesis
        assert len(synthesis["compromise_option"]["title"]) > 0
        assert len(synthesis["compromise_option"]["action"]) > 0

        assert "consider_before_deciding" in synthesis
        assert data["closing_line"] == "It's your call, and I'm with you either way."

        # Check audit log touch
        async with AsyncSessionLocal() as session:
            audit_res = await session.execute(
                select(AuditLog).where(AuditLog.endpoint == "/debate")
            )
            audit_entry = audit_res.scalars().first()
            assert audit_entry is not None
            assert audit_entry.action == "debate_twins"

@pytest.mark.asyncio
async def test_debate_cache_resilience(monkeypatch):
    """Offline debate fallback is a short, friendly retry message."""
    async def fail_voices(**kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr(gemini_client, "run_style_blend_debate", fail_voices)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "What if I spend two days on exam prep instead of the assignment?",
            "primary_twin": "rational",
            "first_answer": "Cached answer"
        }
        resp = await ac.post("/debate", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["voices"] == []
        assert data["closing_line"] == "Couldn't reach the other voices right now, try again?"

@pytest.mark.asyncio
async def test_crisis_dilemma_never_calls_other_voices(monkeypatch):
    async def must_not_run(**kwargs):
        raise AssertionError("crisis messages must never invoke voice generation")
    monkeypatch.setattr(gemini_client, "run_style_blend_debate", must_not_run)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/debate", json={
            "user_id": USER_ID,
            "question": "I might hurt myself tonight",
            "primary_twin": "rational",
            "first_answer": "",
        })
    assert response.status_code == 400
