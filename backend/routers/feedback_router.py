from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import datetime

from backend.database import get_db
from backend.models import (
    User, TwinWeight, TwinWeightLog, DecisionHistory, SimulatorModifier, Permission, PreferenceProfile
)
from backend.schemas import TwinWeightsOut
from backend.services.identity import resolve_twin_name
from backend.memory_registry import defaults_for
from backend.services.style_blend import normalize_style_weights
from backend.services.data_access import get_permitted_user_data

router = APIRouter(tags=["Feedback & Adaptive Personality"])

@router.get("/api/preferences/learned")
async def get_learned_preferences(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    permission = await db.scalar(select(Permission).where(Permission.user_id == user_id, Permission.source == "decision_history"))
    enabled = permission.enabled if permission else defaults_for(user.persona).get("decision_history", False)
    if not enabled:
        return {"enabled": False, "tendencies": {}, "confidence": {}, "source_counts": {}}
    row = await db.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
    if not row:
        return {"enabled": True, "tendencies": {}, "confidence": {}, "source_counts": {}}
    return {"enabled": True, "tendencies": row.tendencies or {}, "confidence": row.confidence or {}, "source_counts": row.source_counts or {}}

@router.delete("/api/preferences/learned")
async def reset_learned_preferences(user_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
    await db.commit()
    return {"status": "reset"}

@router.delete("/api/preferences/learned/{key}")
async def forget_learned_preference(key: str, user_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
    if row:
        for field in ("tendencies", "confidence", "source_counts"):
            values = dict(getattr(row, field) or {})
            values.pop(key, None)
            setattr(row, field, values)
        await db.commit()
    return {"status": "forgotten"}

class FeedbackDecisionRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    question: str
    options: List[Dict[str, Any]]
    twin_recommended: str
    option_chosen: str
    aligned_twin: str = Field(..., description="rational | emotional | ambitious")
    followed_recommendation: bool
    feedback_understood: Optional[bool] = None
    feedback_comment: Optional[Optional[str]] = None
    decision_only: bool = False
    # Optional "Save this as my actual day" adjustment
    actual_day_feedback: Optional[Dict[str, Any]] = None  # { activity: "badminton", perceived_impact: "focus", delta: 1.5 }

class EvolutionAlert(BaseModel):
    evolved: bool
    title: str = "Your twin has evolved"
    old_primary: str
    new_primary: str
    one_line_description: str
    before_weights: Dict[str, float]
    after_weights: Dict[str, float]

class FeedbackResponse(BaseModel):
    status: str
    weights: TwinWeightsOut
    twin_weight_step: float
    consecutive_lead_count: int
    consecutive_lead_twin: Optional[str]
    twin_evolved: bool
    evolution_alert: Optional[EvolutionAlert] = None
    decision_id: Optional[int] = None
    timestamp: datetime.datetime

def calculate_weight_step(
    current_weights: Dict[str, float],
    aligned_twin: str,
    step_size: float = 0.05
) -> Dict[str, float]:
    """
    Applies step size toward aligned_twin, deducts from other two,
    and renormalizes to strictly sum to 1.000.
    """
    w = dict(current_weights)
    aligned_twin = aligned_twin.lower()
    other_twins = [t for t in ["rational", "emotional", "ambitious"] if t != aligned_twin]

    # Add step to aligned twin
    w[aligned_twin] += step_size

    # Deduct equally from other two twins with minimum floor 0.05
    half_step = step_size / 2.0
    for ot in other_twins:
        w[ot] = max(0.05, w[ot] - half_step)

    # Renormalize to exact 1.000
    total = sum(w.values())
    w_norm = {k: round(v / total, 4) for k, v in w.items()}
    # Fix precision remainder on primary/aligned
    diff = round(1.0 - sum(w_norm.values()), 4)
    w_norm[aligned_twin] = round(w_norm[aligned_twin] + diff, 4)

    return w_norm

@router.post("/feedback", response_model=FeedbackResponse)
@router.post("/api/feedback", response_model=FeedbackResponse)
async def process_feedback(req: FeedbackDecisionRequest, db: AsyncSession = Depends(get_db)):
    """
    Adaptive Personality & Decision Logging:
    1. Stores decision in decision_history with feedback_understood.
    2. Updates twin_weights with configurable step (0.05 normal, 0.12 demo mode).
    3. Renormalizes weights and logs to twin_weight_log.
    4. Evaluates primary switch rule: 10+ point lead for 3 decisions in a row.
    5. Returns evolution alert if switch triggered.
    """
    user_id = req.user_id or "demo-alex-rivers"

    # 1. Fetch user and weights
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    twin_name = resolve_twin_name(user)

    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = w_res.scalar_one_or_none()
    if not twin_weight:
        twin_weight = TwinWeight(
            user_id=user_id, rational=0.50, emotional=0.25, ambitious=0.25, primary_twin="rational"
        )
        db.add(twin_weight)
        await db.flush()

    before_weights = {
        "rational": round(twin_weight.rational, 4),
        "emotional": round(twin_weight.emotional, 4),
        "ambitious": round(twin_weight.ambitious, 4)
    }

    permission_bundle = await get_permitted_user_data(
        db, user_id=user_id, requested_sources=["decision_history"]
    )
    history_allowed = bool(permission_bundle.enabled_sources.get("decision_history", False))

    # Explicit voice picks are strong signals; ordinary feedback is gentler.
    is_style_pick = bool(req.feedback_comment and req.feedback_comment.startswith("style_signal:"))
    requested_step = 0.0 if req.decision_only else (0.10 if is_style_pick else (0.08 if user.demo_mode else 0.04))
    now = datetime.datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if history_allowed:
        daily_logs = await db.execute(select(TwinWeightLog.step_size).where(
            TwinWeightLog.user_id == user_id, TwinWeightLog.timestamp >= day_start
        ))
        used_today = sum(max(0.0, float(value or 0.0)) for value in daily_logs.scalars().all())
        step_size = max(0.0, min(requested_step, 0.30 - used_today))
    else:
        step_size = 0.0

    # 2. Record in decision_history
    decision = None
    if history_allowed:
        decision = DecisionHistory(
        user_id=user_id,
        question=req.question,
        options=req.options,
        twin_recommended=req.twin_recommended,
        option_chosen=req.option_chosen,
        aligned_twin=req.aligned_twin.lower(),
        followed_recommendation=req.followed_recommendation,
        feedback_understood=req.feedback_understood,
        feedback_comment=req.feedback_comment,
        timestamp=datetime.datetime.utcnow()
        )
        db.add(decision)
        await db.flush()
        # Keep a separate per-person profile. One override is deliberately weak;
        # confidence builds gradually and remains isolated to this account.
        profile_res = await db.execute(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
        preference = profile_res.scalar_one_or_none()
        if preference is None:
            preference = PreferenceProfile(user_id=user_id, tendencies={}, confidence={}, source_counts={})
            db.add(preference)
        key = f"voice_affinity:{req.aligned_twin.lower()}" if is_style_pick else "follow_recommendation"
        counts = dict(preference.source_counts) if isinstance(preference.source_counts, dict) else {}
        tendencies = dict(preference.tendencies) if isinstance(preference.tendencies, dict) else {}
        confidence = dict(preference.confidence) if isinstance(preference.confidence, dict) else {}
        prior_n = int(counts.get(key, 0))
        observed = 1.0 if req.followed_recommendation else -1.0
        alpha = 0.12 if req.feedback_comment and "usually" in req.feedback_comment.lower() else 0.04
        tendencies[key] = max(-1.0, min(1.0, float(tendencies.get(key, 0.0)) * (1-alpha) + observed * alpha))
        counts[key] = prior_n + 1
        confidence[key] = min(1.0, counts[key] / 3.0)
        preference.tendencies, preference.confidence, preference.source_counts = tendencies, confidence, counts

    # Optional: Save as actual day modifier adjustment
    if req.actual_day_feedback and history_allowed:
        act = req.actual_day_feedback.get("activity", "").lower()
        impact = req.actual_day_feedback.get("perceived_impact", "focus")
        delta = float(req.actual_day_feedback.get("delta", 1.0))
        if act:
            mod = SimulatorModifier(
                user_id=user_id,
                activity_name=act,
                metric_affected=impact,
                delta_value=delta,
                description=f"Actual day reflection adjustment: {act} -> {impact} {delta:+0.1f}",
                created_at=datetime.datetime.utcnow()
            )
            db.add(mod)

    # 3. Step update and renormalize weights
    updated_weights = (
        normalize_style_weights(calculate_weight_step(before_weights, req.aligned_twin, step_size))
        if history_allowed and not req.decision_only else before_weights
    )
    twin_weight.rational = updated_weights["rational"]
    twin_weight.emotional = updated_weights["emotional"]
    twin_weight.ambitious = updated_weights["ambitious"]

    # 4. Evaluate Primary Twin Switch Rule
    # Rule: Change primary twin ONLY when another twin leads the current one by 10+ points (0.10) for 3 decisions in a row.
    curr_primary = twin_weight.primary_twin
    curr_primary_weight = updated_weights[curr_primary]

    # Find highest non-primary twin
    challengers = [(t, updated_weights[t]) for t in ["rational", "emotional", "ambitious"] if t != curr_primary]
    challengers.sort(key=lambda x: x[1], reverse=True)
    top_challenger_twin, top_challenger_weight = challengers[0]

    lead_margin = top_challenger_weight - curr_primary_weight

    twin_evolved = False
    evolution_alert = None

    if history_allowed and not req.decision_only and lead_margin >= 0.10:  # 10+ points lead
        if twin_weight.consecutive_lead_twin == top_challenger_twin:
            twin_weight.consecutive_lead_count += 1
        else:
            twin_weight.consecutive_lead_twin = top_challenger_twin
            twin_weight.consecutive_lead_count = 1

        # Check threshold: 3 in a row!
        if twin_weight.consecutive_lead_count >= 3:
            old_primary = curr_primary
            new_primary = top_challenger_twin
            twin_weight.primary_twin = new_primary
            twin_weight.consecutive_lead_twin = None
            twin_weight.consecutive_lead_count = 0
            twin_evolved = True

            descriptions = {
                "emotional": f"You've been choosing more room for balance and recovery, so {twin_name} will lead with a gentler voice now.",
                "ambitious": f"You've been choosing growth and momentum, so {twin_name} will bring more energy to the opportunities ahead.",
                "rational": f"You've been choosing structure and clarity, so {twin_name} will lead with a calmer, more practical voice."
            }

            evolution_alert = EvolutionAlert(
                evolved=True,
                title="Your twin has evolved",
                old_primary=old_primary,
                new_primary=new_primary,
                one_line_description=descriptions.get(new_primary, f"{twin_name}'s voice has shifted to match the choices you've been making."),
                before_weights=before_weights,
                after_weights=updated_weights
            )
    elif history_allowed and not req.decision_only:
        # Reset streak if lead is less than 10 points
        twin_weight.consecutive_lead_twin = None
        twin_weight.consecutive_lead_count = 0

    if history_allowed:
        twin_weight.updated_at = datetime.datetime.utcnow()

    # 5. Log to twin_weight_log
    log_entry = TwinWeightLog(
        user_id=user_id,
        decision_id=decision.id if decision else None,
        rational=updated_weights["rational"],
        emotional=updated_weights["emotional"],
        ambitious=updated_weights["ambitious"],
        primary_twin=twin_weight.primary_twin,
        delta_twin=req.aligned_twin.lower(),
        step_size=step_size,
        reason=f"Option chosen: '{req.option_chosen[:60]}' aligned with {req.aligned_twin}" + (" (EVOLVED)" if twin_evolved else ""),
        timestamp=datetime.datetime.utcnow()
    )
    if history_allowed and not req.decision_only:
        db.add(log_entry)

    await db.commit()
    if decision is not None:
        await db.refresh(decision)

    return FeedbackResponse(
        status=("Choice saved for future recommendations" if req.decision_only else "Decision recorded and voice weights updated") if history_allowed else "Decision History is off, so I can only use this in the current chat",
        weights=TwinWeightsOut(
            rational=round(twin_weight.rational, 3),
            emotional=round(twin_weight.emotional, 3),
            ambitious=round(twin_weight.ambitious, 3),
            primary_twin=twin_weight.primary_twin
        ),
        twin_weight_step=step_size,
        consecutive_lead_count=twin_weight.consecutive_lead_count,
        consecutive_lead_twin=twin_weight.consecutive_lead_twin,
        twin_evolved=twin_evolved,
        evolution_alert=evolution_alert,
        decision_id=decision.id if decision else None,
        timestamp=datetime.datetime.utcnow()
    )
