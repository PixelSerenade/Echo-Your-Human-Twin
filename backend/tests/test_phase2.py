import pytest
import pytest_asyncio
import os
import re
import sys
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.models import Permission, TwinWeight, AuditLog
from backend.database import AsyncSessionLocal
from backend.services.data_access import get_permitted_user_data
from backend.ml.predictor import predictor
from backend.llm.gemini_client import gemini_client
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db_for_phase2():
    await init_models()
    await seed_demo_persona()


def assert_spoken_message_is_clean(message: str):
    assert len(message) > 20
    assert "%" not in message
    assert message.count("?") <= 1
    assert re.search(r"(?m)^\s*(?:[-*#]|\d+[.)])\s+", message) is None
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", message.strip()) if part]
    assert 2 <= len(sentences) <= 4
    lowered = message.lower()
    assert not lowered.startswith((
        "certainly", "sure!", "sure,", "great question", "as an ai",
        "based on your data", "here are your options",
    ))
    assert "i feel" not in lowered
    assert "i've been there" not in lowered
    for phrase in (
        "probability", "likelihood", "odds", "prototype indicator", "high risk", "medium risk",
        "low risk", "critical risk", "weights", "machine learning", "ml model",
    ):
        assert phrase not in lowered

@pytest.mark.asyncio
async def test_ml_predictor_honest_metrics():
    """Verify ML models are trained and report honest metrics and feature importances."""
    res = predictor.predict(
        estimated_hours=12.0,
        days_until_deadline=2.0,
        concurrent_deadlines=2
    )
    assert 0.0 <= res["on_time_probability"] <= 1.0
    assert res["label"] == "prototype indicator"
    assert res["predicted_hours"] > 0
    assert len(res["why_factors"]) >= 2
    for factor in res["why_factors"]:
        assert "feature" in factor
        assert factor["importance_pct"] >= 0.0
        assert len(factor["impact"]) > 0

    assert "metrics_report" in res
    assert res["metrics_report"]["test_accuracy"] >= 0.80
    assert res["metrics_report"]["mae_hours"] <= 2.5

@pytest.mark.asyncio
async def test_ask_endpoint_with_all_permissions():
    """Test fast answer from primary twin, deadline risk alert, and scikit-learn predictions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "What if I spend two days on exam prep instead of the assignment?"
        }
        resp = await ac.post("/ask", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        # Offline fallback answers intentionally disclose their provenance in
        # the badge, so accept both live and cached demo variants.
        assert data["badge"].startswith("Rational style")
        assert data["primary_twin"] == "rational"
        assert data["message"] != "Hmm, I had a little trouble there. Can you say that again?"
        assert data["answer"] == data["message"]
        assert len(data["answer"]) > 50
        assert data["options"] == []
        assert data["paths"] == []

        # Check deadline risk
        assert "deadline_risk_alert" in data
        assert len(data["deadline_risk_alert"]) > 0

        # Check ML numbers
        assert "ml_insights" in data
        assert data["ml_insights"]["label"] == "prototype indicator"
        assert len(data["ml_insights"]["why_factors"]) >= 2

        # Check sources used
        assert "deadlines" in data["sources_used"]
        assert "timetable" in data["sources_used"]


@pytest.mark.asyncio
async def test_crisis_message_bypasses_model_and_keeps_support_resources(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("The conversational model must not run for crisis messages")

    monkeypatch.setattr(gemini_client, "ask_primary_twin", fail_if_called)
    monkeypatch.setattr(gemini_client, "classify_crisis_escalation", fail_if_called)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/ask", json={
            "user_id": USER_ID,
            "question": "I want to hurt myself and I don't know what to do."
        }, headers={"accept-language": "en-IN,en;q=0.9"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_crisis_response"] is True
    assert data["intent"] == "crisis"
    assert data["options"] == []
    assert data["paths"] == []
    assert data["has_paths"] is False
    assert data["message"].count("?") == 0
    assert "real person" in data["message"].lower()
    contacts = {resource["contact"] for resource in data["crisis_resources"]}
    assert "14416" in contacts
    assert "112" in contacts


def test_spoken_message_guard_replaces_metric_heavy_model_copy():
    result = gemini_client._normalize_spoken_message(
        {
            "message": "You have a 23% probability of success and a HIGH RISK label.",
            "deadline_risk_alert": "Structured details stay available here.",
            "options": [],
        },
        primary_twin="emotional",
        question="Should I focus on my exam or project?",
    )

    assert_spoken_message_is_clean(result["message"])
    assert result["answer"] == result["message"]
    assert result["deadline_risk_alert"] == "Structured details stay available here."


def test_spoken_message_guard_replaces_stock_or_overlong_copy():
    result = gemini_client._normalize_spoken_message(
        {
            "message": (
                "Certainly! Great question. Here are your options. First, do this. "
                "Second, do that. Does that work? Any other questions?"
            ),
            "options": [],
        },
        primary_twin="rational",
        question="What should I focus on tonight?",
    )

    assert_spoken_message_is_clean(result["message"])


def test_explicit_feelings_are_acknowledged_without_reading_mood_memory():
    question = "I'm overwhelmed and anxious about my assignment."
    without_permission = gemini_client._fallback_spoken_message(
        "emotional", question, mood_tone_enabled=False
    )
    with_permission = gemini_client._fallback_spoken_message(
        "emotional", question, mood_tone_enabled=True
    )

    assert without_permission.startswith("Oh, that sounds like a lot to hold.")
    assert without_permission == with_permission
    assert_spoken_message_is_clean(without_permission)
    assert_spoken_message_is_clean(with_permission)


def test_fallback_voice_styles_have_distinct_personalities():
    question = "I'm sad today."
    emotional = gemini_client._fallback_spoken_message("emotional", question)
    rational = gemini_client._fallback_spoken_message("rational", question)
    ambitious = gemini_client._fallback_spoken_message("ambitious", question)

    assert len({emotional, rational, ambitious}) == 3
    assert "You don't have to make it sound okay" in emotional
    assert "Which would you prefer?" in rational
    assert "one small thing to make the next hour easier" in ambitious


def test_fallback_keeps_conversation_continuity():
    message = gemini_client._fallback_spoken_message(
        "rational",
        "Can we carry on from there?",
        recent_turns=[{"role": "user", "content": "I finished the setup yesterday."}],
    )

    assert message.startswith("We can pick this back up whenever you're ready.")
    assert_spoken_message_is_clean(message)


def test_offline_plan_fallback_uses_only_shared_due_items():
    context = (
        "- [Assessment] Exam (Personal) | Date: 2030-10-05 00:00 | Estimated Effort: 2.0h | Priority: high | Status: Pending\n"
        "- [Task or milestone] Project (Personal) | Date: 2030-10-08 00:00 | Estimated Effort: 3.0h | Priority: medium | Status: Pending"
    )
    message = gemini_client._fallback_spoken_message(
        "rational", "Can you make a plan for my exam and project?", permitted_context=context
    )

    assert "Exam" in message and "Oct 5" in message and "Project" in message
    assert "tuple" not in message.lower()
    assert_spoken_message_is_clean(message)

    no_context = gemini_client._fallback_spoken_message(
        "rational", "Which deadline is more important?", permitted_context=""
    )
    assert "What are the tasks" in no_context


@pytest.mark.asyncio
async def test_spoken_pipeline_uses_one_natural_call_and_retries_bad_voice(monkeypatch):
    calls = {"json": [], "text": []}

    async def fake_json(prompt, system_instruction="", temperature=0.2):
        calls["json"].append({"prompt": prompt, "temperature": temperature})
        return {
            "deadline_risk_alert": "Cloud project deadline is approaching.",
            "options": [
                {"id": "opt-1", "text": "Protect the deadline", "aligned_twin": "rational", "description": "Keeps work moving."},
                {"id": "opt-2", "text": "Make room to reset", "aligned_twin": "emotional", "description": "Keeps the pace sustainable."},
                {"id": "opt-3", "text": "Push the key milestone", "aligned_twin": "ambitious", "description": "Builds momentum."},
            ],
        }

    text_drafts = iter([
        "Certainly! Here are your options. Do this? Or that?",
        "We can pick this back up without starting over. Your Cloud project still matters, so let's return to the next clear task.",
    ])

    async def fake_text(prompt, system_instruction="", temperature=0.8):
        calls["text"].append({"prompt": prompt, "temperature": temperature})
        return next(text_drafts)

    monkeypatch.setattr(gemini_client, "call_gemini_json", fake_json)
    monkeypatch.setattr(gemini_client, "call_gemini_text", fake_text)
    monkeypatch.setattr(gemini_client, "_save_cache", lambda: None)

    result = await gemini_client.ask_primary_twin(
        primary_twin="rational",
        question="Can we keep going with the project?",
        message_type="decision_question",
        permitted_context="Cloud Infrastructure project is an active saved task.",
        ml_insights={"why_factors": []},
        deadline_risk_summary="Cloud project deadline is approaching.",
        recent_turns=[
            {"role": "user", "content": "I finished the setup yesterday."},
            {"role": "assistant", "content": "Nice, let's keep that momentum."},
        ],
    )

    assert calls["json"] == []
    assert [call["temperature"] for call in calls["text"]] == [0.8, 0.8]
    assert len(calls["text"]) == 2
    assert "I finished the setup yesterday." in calls["text"][0]["prompt"]
    assert "CORRECTION:" in calls["text"][1]["prompt"]
    assert_spoken_message_is_clean(result["message"])


@pytest.mark.asyncio
async def test_planning_reply_does_not_depend_on_unused_decision_json(monkeypatch):
    json_calls = []
    async def failing_json(*args, **kwargs):
        json_calls.append(True)
        raise RuntimeError("structured output unavailable")

    async def natural_text(prompt, system_instruction="", temperature=0.8):
        assert "short, ordered set of concrete next steps" in prompt
        return "Start with the exam due October 5. Then give the project a short block before Friday."

    monkeypatch.setattr(gemini_client, "call_gemini_json", failing_json)
    monkeypatch.setattr(gemini_client, "call_gemini_text", natural_text)
    monkeypatch.setattr(gemini_client, "_save_cache", lambda: None)

    result = await gemini_client.ask_primary_twin(
        primary_twin="rational",
        question="Make me a plan for my exam and project.",
        message_type="decision_question",
        permitted_context="Exam due October 5. Project due Friday.",
        ml_insights={"why_factors": []},
        deadline_risk_summary="",
    )

    assert result["message"].startswith("Start with the exam due October 5")
    assert result["options"] == []
    assert json_calls == []

@pytest.mark.asyncio
async def test_privacy_enforcement_disabled_source_never_sent_to_gemini():
    """
    Automated test proving a disabled source NEVER appears in the context sent to Gemini
    and is never fetched from the database.
    """
    # 1. Disable deadlines and study_history
    async with AsyncSessionLocal() as session:
        p_res = await session.execute(
            select(Permission).where(Permission.user_id == USER_ID)
        )
        for perm in p_res.scalars().all():
            if perm.source in ("deadlines", "study_history"):
                perm.enabled = False
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "What tasks should I focus on tonight?"
        }
        resp = await ac.post("/ask", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        # Verify sources used
        assert "deadlines" not in data["sources_used"]
        assert "study_history" not in data["sources_used"]

        # Verify audit log recorded this access without the disabled sources
        audit_res = await ac.get(f"/audit-log?user_id={USER_ID}&limit=5")
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        latest_ask = next(e for e in audit_data["entries"] if e["endpoint"] == "/ask")
        assert "deadlines" not in latest_ask["sources_accessed"]
        assert "study_history" not in latest_ask["sources_accessed"]

    # Restore permissions
    async with AsyncSessionLocal() as session:
        p_res = await session.execute(
            select(Permission).where(Permission.user_id == USER_ID)
        )
        for perm in p_res.scalars().all():
            perm.enabled = True
        await session.commit()

@pytest.mark.asyncio
async def test_ask_non_rational_twin_still_flags_deadline_risk():
    """
    Requirement: Even when the primary twin is not the Rational one,
    the answer must still mention any real deadline risk found in the data.
    """
    # Temporarily set primary twin to emotional
    async with AsyncSessionLocal() as session:
        w_res = await session.execute(
            select(TwinWeight).where(TwinWeight.user_id == USER_ID)
        )
        weight = w_res.scalar_one()
        weight.primary_twin = "emotional"
        weight.emotional = 0.50
        weight.rational = 0.25
        weight.ambitious = 0.25
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req_payload = {
            "user_id": USER_ID,
            "question": "Can I just relax and ignore schoolwork for the next two days?"
        }
        resp = await ac.post("/ask", json=req_payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["badge"] == "Emotional style"
        assert data["primary_twin"] == "emotional"

        # Must still mention real deadline risk found in data!
        assert len(data["deadline_risk_alert"]) > 0
        assert ("Midterm" in data["deadline_risk_alert"] or "Cloud" in data["deadline_risk_alert"] or "conflict" in data["deadline_risk_alert"].lower() or "deadline" in data["deadline_risk_alert"].lower())

    # Restore rational primary twin
    async with AsyncSessionLocal() as session:
        w_res = await session.execute(
            select(TwinWeight).where(TwinWeight.user_id == USER_ID)
        )
        weight = w_res.scalar_one()
        weight.primary_twin = "rational"
        weight.rational = 0.50
        weight.emotional = 0.25
        weight.ambitious = 0.25
        await session.commit()
