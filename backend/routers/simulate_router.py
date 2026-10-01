from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import datetime

from backend.database import get_db
from backend.models import User, TwinWeight, SimulatorModifier, AuditLog
from backend.simulator.engine import simulator_engine, DEFAULT_INITIAL_STATE
from backend.llm.gemini_client import gemini_client
from backend.services.data_access import get_permitted_user_data
from backend.services.identity import resolve_twin_name
from backend.memory_registry import registry_for

router = APIRouter(tags=["Life Simulator"])

class ActivityItem(BaseModel):
    activity: str = Field(..., description="study | badminton | netflix | project work | sleep")
    hours: float = Field(..., ge=0.1, le=24.0)

class StateBars(BaseModel):
    energy: float
    happiness: float
    study: float
    goals: float
    free_time: float

class SimulateRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    scenario_name: Optional[str] = "Study vs Recreation"
    path_a: List[ActivityItem]
    path_b: Optional[List[ActivityItem]] = None
    initial_state: Optional[StateBars] = None

class SimulationPathResult(BaseModel):
    initial_state: StateBars
    final_state: StateBars
    deltas: Dict[str, float]
    timeline: List[Dict[str, Any]]

class SimulateResponse(BaseModel):
    user_id: str
    scenario_name: str
    path_a: SimulationPathResult
    path_b: Optional[SimulationPathResult] = None
    net_difference: Optional[Dict[str, float]] = None
    gemini_explanation: str
    indicator_notice: str = "Simulated outcomes based on deterministic model and learned modifiers, not absolute predictions."
    timestamp: datetime.datetime
    dimension_labels: Dict[str, str] = {}

class SimulationCorrectionRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    activity_name: str
    metric_affected: str = Field(..., description="energy | happiness | study | goals | free_time | focus")
    delta_value: float
    description: str

class SimulationCorrectionResponse(BaseModel):
    status: str = "New pattern learned"
    activity_name: str
    metric_affected: str
    delta_value: float
    description: str
    id: int

@router.post("/simulate", response_model=SimulateResponse)
@router.post("/api/simulate", response_model=SimulateResponse)
async def simulate_scenario(req: SimulateRequest, db: AsyncSession = Depends(get_db)):
    """
    Life Simulator endpoint:
    - Simulates Path A and optionally Path B with clamped bars (0-100).
    - Incorporates user personality weights, diminishing returns on low energy, and learned modifiers.
    - Generates concise Gemini explanation using ONLY computed numbers.
    - Logs data touch into audit_log.
    """
    user_id = req.user_id or "demo-alex-rivers"
    user = await db.get(User, user_id)
    user_name = (user.name or "the user").strip() if user else "the user"
    twin_name = resolve_twin_name(user) if user else "Echo"

    # Fetch user weights
    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = w_res.scalar_one_or_none()
    weights = {
        "rational": twin_weight.rational if twin_weight else 0.50,
        "emotional": twin_weight.emotional if twin_weight else 0.25,
        "ambitious": twin_weight.ambitious if twin_weight else 0.25
    }

    # Fetch modifiers
    mod_res = await db.execute(
        select(SimulatorModifier).where(SimulatorModifier.user_id == user_id)
    )
    modifiers = [
        {
            "activity_name": m.activity_name,
            "metric_affected": m.metric_affected,
            "delta_value": m.delta_value,
            "description": m.description
        }
        for m in mod_res.scalars().all()
    ]

    init_state = req.initial_state.model_dump() if req.initial_state else DEFAULT_INITIAL_STATE

    path_a_activities = [act.model_dump() for act in req.path_a]
    path_b_activities = [act.model_dump() for act in req.path_b] if req.path_b else None

    if path_b_activities:
        comparison = simulator_engine.compare_paths(
            path_a=path_a_activities,
            path_b=path_b_activities,
            initial_state=init_state,
            weights=weights,
            modifiers=modifiers
        )
        explanation = await gemini_client.explain_simulation(
            comparison,
            req.scenario_name or "",
            user_name=user_name,
            twin_name=twin_name,
        )

        path_a_res = SimulationPathResult(
            initial_state=StateBars(**comparison["path_a"]["initial_state"]),
            final_state=StateBars(**comparison["path_a"]["final_state"]),
            deltas=comparison["path_a"]["deltas"],
            timeline=comparison["path_a"]["timeline"]
        )
        path_b_res = SimulationPathResult(
            initial_state=StateBars(**comparison["path_b"]["initial_state"]),
            final_state=StateBars(**comparison["path_b"]["final_state"]),
            deltas=comparison["path_b"]["deltas"],
            timeline=comparison["path_b"]["timeline"]
        )
        net_diff = comparison["net_difference_a_minus_b"]
    else:
        single_res = simulator_engine.simulate_path(
            activities=path_a_activities,
            initial_state=init_state,
            weights=weights,
            modifiers=modifiers
        )
        path_a_res = SimulationPathResult(
            initial_state=StateBars(**single_res["initial_state"]),
            final_state=StateBars(**single_res["final_state"]),
            deltas=single_res["deltas"],
            timeline=single_res["timeline"]
        )
        path_b_res = None
        net_diff = None
        explanation = f"Simulated outcome yields final energy of {path_a_res.final_state.energy} and study gain of {path_a_res.deltas.get('study', 0):+0.1f}."

    # Record in audit log
    audit_entry = AuditLog(
        user_id=user_id,
        action="simulate",
        endpoint="/simulate",
        # Keep this list aligned with the records queried above. Preferences
        # are not read by the simulator; it does read profile, twin weights,
        # and the user's saved simulator corrections.
        sources_accessed=["profile", "twin_weights", "simulator_modifiers"],
        timestamp=datetime.datetime.utcnow()
    )
    db.add(audit_entry)
    await db.commit()

    return SimulateResponse(
        user_id=user_id,
        scenario_name=req.scenario_name or "Custom Scenario",
        path_a=path_a_res,
        path_b=path_b_res,
        net_difference=net_diff,
        gemini_explanation=explanation,
        dimension_labels=registry_for(getattr(user, "persona", "student"))["simulator_labels"],
        timestamp=datetime.datetime.utcnow()
    )

@router.post("/simulate/correct", response_model=SimulationCorrectionResponse)
@router.post("/api/simulate/correct", response_model=SimulationCorrectionResponse)
async def correct_simulation(req: SimulationCorrectionRequest, db: AsyncSession = Depends(get_db)):
    """
    User corrects simulation behavior (e.g. 'badminton helps my focus').
    Saved as a learned simulator modifier and displayed as 'New pattern learned'.
    """
    user_id = req.user_id or "demo-alex-rivers"

    mod = SimulatorModifier(
        user_id=user_id,
        activity_name=req.activity_name.lower().strip(),
        metric_affected=req.metric_affected.lower().strip(),
        delta_value=float(req.delta_value),
        description=req.description.strip(),
        created_at=datetime.datetime.utcnow()
    )
    db.add(mod)
    await db.commit()
    await db.refresh(mod)

    return SimulationCorrectionResponse(
        status="New pattern learned",
        activity_name=mod.activity_name,
        metric_affected=mod.metric_affected,
        delta_value=mod.delta_value,
        description=mod.description,
        id=mod.id
    )
