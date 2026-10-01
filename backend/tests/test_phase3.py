import pytest
import pytest_asyncio
import os
import sys
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.models import User, TwinWeight, SimulatorModifier, Permission
from backend.database import AsyncSessionLocal
from backend.simulator.engine import simulator_engine, clamp
from backend.routers.feedback_router import calculate_weight_step
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db_for_phase3():
    await init_models()
    await seed_demo_persona()

def test_simulator_clamping_and_diminishing_returns():
    """Verify state clamping [0, 100] and diminishing returns on low energy."""
    # Test 1: Excessive sleep cannot exceed 100 energy
    res_high = simulator_engine.simulate_path(
        activities=[{"activity": "sleep", "hours": 20.0}],
        initial_state={"energy": 80.0, "happiness": 50.0, "study": 50.0, "goals": 50.0, "free_time": 50.0}
    )
    assert res_high["final_state"]["energy"] == 100.0

    # Test 2: Low energy (< 30) triggers diminishing study returns
    res_low_energy = simulator_engine.simulate_path(
        activities=[{"activity": "study", "hours": 4.0}],
        initial_state={"energy": 15.0, "happiness": 50.0, "study": 20.0, "goals": 20.0, "free_time": 50.0}
    )
    # Check that diminishing returns was recorded in timeline
    assert res_low_energy["timeline"][1]["diminishing_returns"] is True
    # Gain should be significantly dampened compared to standard 22*4 = 88
    study_gain = res_low_energy["deltas"]["study"]
    assert study_gain < 45.0, f"Expected dampened study gain, got {study_gain}"

@pytest.mark.asyncio
async def test_simulate_endpoint_path_comparison():
    """Test POST /simulate comparing Path A vs Path B side-by-side."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "user_id": USER_ID,
            "scenario_name": "Deep Work vs Balanced Day",
            "path_a": [
                {"activity": "study", "hours": 2.0},
                {"activity": "badminton", "hours": 1.5},
                {"activity": "sleep", "hours": 6.0}
            ],
            "path_b": [
                {"activity": "study", "hours": 7.0},
                {"activity": "netflix", "hours": 1.0},
                {"activity": "sleep", "hours": 2.0}
            ]
        }
        resp = await ac.post("/simulate", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "path_a" in data
        assert "path_b" in data
        assert "net_difference" in data
        assert len(data["gemini_explanation"]) > 20
        # Check that simulated outcomes disclaimer is present
        assert "simulated outcomes" in data["indicator_notice"].lower()

        # Path A has badminton + 6h sleep -> should have higher energy than Path B (7h study + only 2h sleep)
        assert data["path_a"]["final_state"]["energy"] > data["path_b"]["final_state"]["energy"]
        # Path B has 7h study vs Path A 2h study -> should have higher study gain
        assert data["path_b"]["final_state"]["study"] > data["path_a"]["final_state"]["study"]

@pytest.mark.asyncio
async def test_simulate_correct_endpoint():
    """Test user correction creates learned modifier with 'New pattern learned'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "user_id": USER_ID,
            "activity_name": "badminton",
            "metric_affected": "focus",
            "delta_value": 2.0,
            "description": "Playing badminton provides a strong mental reset"
        }
        resp = await ac.post("/simulate/correct", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "New pattern learned"
        assert data["activity_name"] == "badminton"
        assert data["delta_value"] == 2.0

def test_weight_step_math_and_normalization():
    """Verify weight step addition, deduction, and 1.000 normalization."""
    initial = {"rational": 0.50, "emotional": 0.25, "ambitious": 0.25}
    # Step 0.12 towards ambitious
    updated = calculate_weight_step(initial, "ambitious", step_size=0.12)

    assert updated["ambitious"] > 0.25
    assert updated["rational"] < 0.50
    assert updated["emotional"] < 0.25
    assert round(sum(updated.values()), 3) == 1.000

@pytest.mark.asyncio
async def test_adaptive_personality_3_consecutive_switch_rule():
    """
    Test the strict Primary Twin Switch Rule:
    Change the primary twin ONLY when another twin leads the current one by 10+ points
    for 3 decisions in a row.
    """
    # 1. Reset user in demo mode with Rational primary (Rational: 0.38, Ambitious: 0.38, Emotional: 0.24)
    # So on step 0.12, Ambitious immediately leads by 18 points (0.50 vs 0.32 >= 0.10)
    async with AsyncSessionLocal() as session:
        user = await session.get(User, USER_ID)
        user.demo_mode = True
        w_res = await session.execute(select(TwinWeight).where(TwinWeight.user_id == USER_ID))
        w = w_res.scalar_one()
        w.rational = 0.38
        w.ambitious = 0.38
        w.emotional = 0.24
        w.primary_twin = "rational"
        w.consecutive_lead_twin = None
        w.consecutive_lead_count = 0
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        base_decision = {
            "user_id": USER_ID,
            "options": [{"text": "Ambitious path", "aligned_twin": "ambitious"}],
            "twin_recommended": "rational",
            "option_chosen": "Build high-impact project milestone",
            "aligned_twin": "ambitious",
            "followed_recommendation": False,
            "feedback_understood": True
        }

        # DECISION 1: Ambitious chosen -> Leads by 10+ points (streak = 1)
        req1 = dict(base_decision, question="Decision 1: Take hackathon leadership role?")
        resp1 = await ac.post("/feedback", json=req1)
        data1 = resp1.json()
        assert data1["twin_evolved"] is False, "Should NOT evolve after decision 1"
        assert data1["weights"]["primary_twin"] == "rational"
        assert data1["consecutive_lead_count"] == 1
        assert data1["consecutive_lead_twin"] == "ambitious"

        # DECISION 2: Ambitious chosen again -> Leads by 10+ points (streak = 2)
        req2 = dict(base_decision, question="Decision 2: Pitch project to industry panel?")
        resp2 = await ac.post("/feedback", json=req2)
        data2 = resp2.json()
        assert data2["twin_evolved"] is False, "Should NOT evolve after decision 2 (streak is only 2)"
        assert data2["weights"]["primary_twin"] == "rational"
        assert data2["consecutive_lead_count"] == 2
        assert data2["consecutive_lead_twin"] == "ambitious"

        # DECISION 3: Ambitious chosen 3rd time in a row! -> Streak = 3 -> EVOLVES!
        req3 = dict(base_decision, question="Decision 3: Accept extra advanced research fellowship?")
        resp3 = await ac.post("/feedback", json=req3)
        data3 = resp3.json()

        assert data3["twin_evolved"] is True, "Must evolve after 3 consecutive decisions leading by 10+ points!"
        assert data3["weights"]["primary_twin"] == "ambitious", "Primary twin must switch to ambitious!"
        assert data3["evolution_alert"] is not None
        assert data3["evolution_alert"]["title"] == "Your twin has evolved"
        assert data3["evolution_alert"]["old_primary"] == "rational"
        assert data3["evolution_alert"]["new_primary"] == "ambitious"
        assert len(data3["evolution_alert"]["one_line_description"]) > 10
        assert "before_weights" in data3["evolution_alert"]
        assert "after_weights" in data3["evolution_alert"]

@pytest.mark.asyncio
async def test_style_signal_is_not_persisted_when_decision_history_is_off():
    async with AsyncSessionLocal() as session:
        permission = await session.scalar(select(Permission).where(
            Permission.user_id == USER_ID, Permission.source == "decision_history"
        ))
        previous = permission.enabled
        permission.enabled = False
        weight = await session.scalar(select(TwinWeight).where(TwinWeight.user_id == USER_ID))
        before = (weight.rational, weight.emotional, weight.ambitious)
        await session.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/feedback", json={
                "user_id": USER_ID, "question": "A personal choice", "options": [],
                "twin_recommended": "rational", "option_chosen": "Heart",
                "aligned_twin": "emotional", "followed_recommendation": True,
                "feedback_comment": "style_signal:strong",
            })
        assert response.status_code == 200
        assert response.json()["decision_id"] is None
        async with AsyncSessionLocal() as session:
            weight = await session.scalar(select(TwinWeight).where(TwinWeight.user_id == USER_ID))
            assert (weight.rational, weight.emotional, weight.ambitious) == before
    finally:
        async with AsyncSessionLocal() as session:
            permission = await session.scalar(select(Permission).where(
                Permission.user_id == USER_ID, Permission.source == "decision_history"
            ))
            permission.enabled = previous
            await session.commit()
