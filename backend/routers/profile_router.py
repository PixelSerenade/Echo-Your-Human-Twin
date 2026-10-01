from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Optional
import datetime

from backend.database import get_db
from backend.models import User, ProfileTag, TwinWeight, TwinWeightLog, Permission, ConsentEntry
from backend.schemas import (
    ProfileCreateRequest, ProfileResponse, TwinWeightsOut, ProfileTagItem,
    OnboardingStepRequest, OnboardingStepResponse, TwinNameUpdateRequest,
    TwinNameUpdateResponse
)
from backend.routers.auth_router import get_current_user_id
from backend.services.identity import resolve_twin_name
from backend.memory_registry import PERSONAS, CATEGORY_IDS, CATEGORIES, defaults_for, registry_for, LEGACY_TO_CATEGORY, PERMISSION_WORDING_VERSION
from backend.models import Goal
from backend.services.style_blend import normalize_style_weights

router = APIRouter(tags=["Profile & Onboarding"])

@router.get("/api/memory-registry")
async def get_memory_registry(persona: str = None):
    return registry_for(persona)

@router.put("/api/profile/persona")
async def update_persona(payload: dict, db: AsyncSession = Depends(get_db)):
    user_id = payload.get("user_id")
    persona = payload.get("persona")
    if persona not in PERSONAS:
        raise HTTPException(status_code=400, detail="Choose a valid persona.")
    user = await db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.persona = persona
    await db.commit()
    existing = {p.source: p.enabled for p in (await db.execute(select(Permission).where(Permission.user_id == user_id))).scalars().all()}
    return {"user_id": user_id, "persona": persona, "permissions": existing}


@router.post("/profile", response_model=ProfileResponse)
@router.post("/api/profile", response_model=ProfileResponse)
async def create_or_update_profile(
    req: ProfileCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Onboarding endpoint: Accepts tags grouped by twin.
    The group with the most tags becomes the PRIMARY twin.
    Calculates normalized weights (e.g. 50/25/25), stores in DB, and logs to twin_weight_log.
    """
    user_id = req.user_id or "demo-alex-rivers"

    # 1. Fetch or create User
    user = await db.get(User, user_id)
    if not user:
        user = User(
            id=user_id,
            name=req.name or "Alex Rivers",
            email=req.email or f"{user_id}@humantwin.ai",
            demo_mode=req.demo_mode if req.demo_mode is not None else True
        )
        db.add(user)
        await db.flush()

    # 2. Delete existing tags for user if re-onboarding
    await db.execute(delete(ProfileTag).where(ProfileTag.user_id == user_id))

    # 3. Count tags per twin
    counts = {"rational": 0, "emotional": 0, "ambitious": 0}
    tag_objects = []

    for t in req.tags:
        ttype = t.twin_type.lower()
        if ttype not in counts:
            ttype = "rational"
        counts[ttype] += 1
        tag_objects.append(
            ProfileTag(user_id=user_id, twin_type=ttype, tag_name=t.tag_name)
        )

    db.add_all(tag_objects)

    total_tags = len(req.tags)
    if total_tags == 0:
        # Default fallback
        weights_dict = {"rational": 0.50, "emotional": 0.25, "ambitious": 0.25}
        primary_twin = "rational"
    else:
        # Calculate weights based on tag distribution
        # Example: 4 Rational, 2 Emotional, 2 Ambitious -> 0.50 / 0.25 / 0.25
        r_w = round(counts["rational"] / total_tags, 2)
        e_w = round(counts["emotional"] / total_tags, 2)
        a_w = round(1.0 - (r_w + e_w), 2)  # Ensure exact sum to 1.0
        weights_dict = normalize_style_weights({"rational": r_w, "emotional": e_w, "ambitious": a_w})

        # Determine primary twin (highest count; tie-breaker: rational > emotional > ambitious)
        sorted_twins = sorted(
            ["rational", "emotional", "ambitious"],
            key=lambda k: counts[k],
            reverse=True
        )
        primary_twin = sorted_twins[0]

    # 4. Upsert TwinWeight
    weight_res = await db.execute(
        select(TwinWeight).where(TwinWeight.user_id == user_id)
    )
    twin_weight = weight_res.scalar_one_or_none()
    if not twin_weight:
        twin_weight = TwinWeight(
            user_id=user_id,
            rational=weights_dict["rational"],
            emotional=weights_dict["emotional"],
            ambitious=weights_dict["ambitious"],
            primary_twin=primary_twin,
            consecutive_lead_twin=None,
            consecutive_lead_count=0
        )
        db.add(twin_weight)
    else:
        twin_weight.rational = weights_dict["rational"]
        twin_weight.emotional = weights_dict["emotional"]
        twin_weight.ambitious = weights_dict["ambitious"]
        twin_weight.primary_twin = primary_twin
        twin_weight.consecutive_lead_twin = None
        twin_weight.consecutive_lead_count = 0

    # 5. Log to twin_weight_log
    weight_log = TwinWeightLog(
        user_id=user_id,
        rational=weights_dict["rational"],
        emotional=weights_dict["emotional"],
        ambitious=weights_dict["ambitious"],
        primary_twin=primary_twin,
        delta_twin=primary_twin,
        step_size=0.0,
        reason=f"Onboarding tag selection: {counts['rational']} Rational, {counts['emotional']} Emotional, {counts['ambitious']} Ambitious"
    )
    db.add(weight_log)

    await db.commit()
    await db.refresh(user)

    return ProfileResponse(
        user_id=user.id,
        name=user.name,
        user_name=user.name,
        twin_name=resolve_twin_name(user),
        twin_name_customized=bool(user.twin_name_customized),
        primary_twin=primary_twin,
        weights=TwinWeightsOut(
            rational=weights_dict["rational"],
            emotional=weights_dict["emotional"],
            ambitious=weights_dict["ambitious"],
            primary_twin=primary_twin
        ),
        tags=[ProfileTagItem(twin_type=t.twin_type, tag_name=t.tag_name) for t in req.tags],
        demo_mode=user.demo_mode,
        persona=user.persona or "student"
    )

@router.get("/profile/{user_id}", response_model=ProfileResponse)
@router.get("/api/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str = "demo-alex-rivers", db: AsyncSession = Depends(get_db)):
    """Retrieve existing user profile, tags, and weights."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = w_res.scalar_one_or_none()
    if not twin_weight:
        twin_weight = TwinWeight(
            user_id=user_id, rational=0.5, emotional=0.25, ambitious=0.25, primary_twin="rational"
        )

    tag_res = await db.execute(select(ProfileTag).where(ProfileTag.user_id == user_id))
    tags = tag_res.scalars().all()

    return ProfileResponse(
        user_id=user.id,
        name=user.name,
        user_name=user.name,
        twin_name=resolve_twin_name(user),
        twin_name_customized=bool(user.twin_name_customized),
        primary_twin=twin_weight.primary_twin,
        weights=TwinWeightsOut(
            rational=round(twin_weight.rational, 2),
            emotional=round(twin_weight.emotional, 2),
            ambitious=round(twin_weight.ambitious, 2),
            primary_twin=twin_weight.primary_twin
        ),
        tags=[ProfileTagItem(twin_type=t.twin_type, tag_name=t.tag_name) for t in tags],
        demo_mode=user.demo_mode,
        persona=user.persona or "student"
    )

@router.post("/api/onboarding/step", response_model=OnboardingStepResponse)
async def process_onboarding_step(
    req: OnboardingStepRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Step-by-step onboarding processor:
    - 'tags': Validates >= 5 tags, calculates normalized weights (50/30/20), handles tie-breaker, advances to 'reveal'.
    - 'reveal': Saves primary_twin (allows user override), advances to 'name'.
    - 'name': Validates and saves twin_name, advances to 'permissions'.
    - 'permissions': Saves granular permissions, advances to 'finish'.
    - 'finish': Marks onboarding_completed = True and completes onboarding.
    """
    user_id = req.user_id or get_current_user_id(request) or "demo-alex-rivers"
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    step = req.step.lower()

    if step == "persona":
        persona = (req.persona or "other").strip().lower()
        if persona not in PERSONAS:
            raise HTTPException(status_code=400, detail="Choose a valid persona.")
        user.persona = persona
        existing = {p.source: p.enabled for p in (await db.execute(select(Permission).where(Permission.user_id == user_id))).scalars().all()}
        for category, enabled in defaults_for(persona).items():
            if category not in existing:
                legacy = CATEGORIES[category]["legacy"]
                preserved = existing.get(legacy, enabled) if legacy else enabled
                db.add(Permission(user_id=user_id, source=category, enabled=preserved))
        user.onboarding_step = "tags"
        await db.commit()
        return OnboardingStepResponse(success=True, current_step="tags", onboarding_completed=False, persona=persona, message="Your starting setup is ready to customize.")

    if step == "tags":
        if not req.tags or len(req.tags) < 5:
            raise HTTPException(status_code=400, detail="Pick at least five tags so Echo has enough to start with.")

        counts = {"rational": 0, "emotional": 0, "ambitious": 0}
        tag_objects = []
        for t in req.tags:
            ttype = t.twin_type.lower()
            if ttype in counts:
                counts[ttype] += 1
            else:
                counts["rational"] += 1
                ttype = "rational"
            tag_objects.append(ProfileTag(user_id=user_id, twin_type=ttype, tag_name=t.tag_name))

        total = sum(counts.values())
        blend = normalize_style_weights({style: counts[style] / total for style in counts})
        r_w, e_w, a_w = blend["rational"], blend["emotional"], blend["ambitious"]

        # Check for ties among top count
        max_val = max(counts.values())
        top_twins = [k for k, v in counts.items() if v == max_val]

        if len(top_twins) > 1 and not req.tie_breaker_choice:
            return OnboardingStepResponse(
                success=True,
                current_step="tags",
                onboarding_completed=False,
                tie_needed=True,
                tied_twins=top_twins,
                message="A couple of voices fit you equally well. One quick choice will help."
            )

        recommended = req.tie_breaker_choice if (req.tie_breaker_choice and req.tie_breaker_choice in top_twins) else top_twins[0]

        # Delete old tags and save new tags
        await db.execute(delete(ProfileTag).where(ProfileTag.user_id == user_id))
        db.add_all(tag_objects)

        # Update or create weights
        w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
        twin_weight = w_res.scalar_one_or_none()
        if not twin_weight:
            twin_weight = TwinWeight(
                user_id=user_id,
                rational=r_w,
                emotional=e_w,
                ambitious=a_w,
                primary_twin=recommended
            )
            db.add(twin_weight)
        else:
            twin_weight.rational = r_w
            twin_weight.emotional = e_w
            twin_weight.ambitious = a_w
            twin_weight.primary_twin = recommended

        user.onboarding_step = "reveal"
        await db.commit()

        return OnboardingStepResponse(
            success=True,
            current_step="reveal",
            onboarding_completed=False,
            recommended_twin=recommended,
            primary_twin=recommended,
            weights=TwinWeightsOut(
                rational=r_w,
                emotional=e_w,
                ambitious=a_w,
                primary_twin=recommended
            ),
            message=f"Your choices sound closest to the {recommended} voice."
        )

    elif step == "reveal":
        chosen_style = (req.primary_twin or "rational").lower()
        if chosen_style not in ["rational", "emotional", "ambitious"]:
            chosen_style = "rational"

        w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
        twin_weight = w_res.scalar_one_or_none()
        if twin_weight:
            twin_weight.primary_twin = chosen_style

        user.onboarding_step = "name"
        await db.commit()

        return OnboardingStepResponse(
            success=True,
            current_step="name",
            onboarding_completed=False,
            primary_twin=chosen_style,
            message=f"Echo will start with the {chosen_style} voice."
        )

    elif step == "name":
        raw_name = (req.twin_name or "").strip()
        if not raw_name:
            final_name = "Echo"
        else:
            # 1 to 24 characters sanitized
            final_name = raw_name[:24]

        user.twin_name = final_name
        user.twin_name_customized = bool(raw_name)
        user.onboarding_step = "permissions"
        await db.commit()

        return OnboardingStepResponse(
            success=True,
            current_step="permissions",
            onboarding_completed=False,
            twin_name=final_name,
            message=f"{final_name} it is."
        )

    elif step == "permissions":
        perms = req.permissions or {}
        for src, enabled in perms.items():
            src = LEGACY_TO_CATEGORY.get(src, src)
            if src not in CATEGORY_IDS:
                continue
            p_res = await db.execute(
                select(Permission).where(Permission.user_id == user_id, Permission.source == src)
            )
            existing_p = p_res.scalar_one_or_none()
            if existing_p:
                existing_p.enabled = bool(enabled)
            else:
                db.add(Permission(user_id=user_id, source=src, enabled=bool(enabled)))
            db.add(ConsentEntry(user_id=user_id, category=src, value=bool(enabled), wording_version=PERMISSION_WORDING_VERSION, timestamp=datetime.datetime.utcnow()))

        user.onboarding_step = "seed"
        await db.commit()

        return OnboardingStepResponse(
            success=True,
            current_step="seed",
            onboarding_completed=False,
            message="Your privacy choices are set."
        )

    elif step == "seed":
        saved_perms = {p.source: p.enabled for p in (await db.execute(select(Permission).where(Permission.user_id == user_id))).scalars().all()}
        deadline_allowed = saved_perms.get("deadlines_key_dates", saved_perms.get("deadlines", defaults_for(user.persona).get("deadlines_key_dates", False)))
        goals_allowed = saved_perms.get("goals", defaults_for(user.persona).get("goals", False))
        if deadline_allowed:
            from backend.models import Deadline
            for item in (req.seed_deadlines or [])[:3]:
                title = str(item.get("title", "")).strip()[:200]
                due_raw = item.get("due_date")
                if not title or not due_raw:
                    continue
                try:
                    due_date = datetime.datetime.fromisoformat(str(due_raw))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Enter a valid date for each key date.")
                try:
                    estimated_effort = max(0.1, float(item.get("estimated_effort", 1)))
                except (TypeError, ValueError):
                    estimated_effort = 1.0
                db.add(Deadline(user_id=user_id, title=title, course_or_project="Personal", due_date=due_date, estimated_hours=estimated_effort, priority="medium", is_exam=False))
        if goals_allowed and req.goals:
            for title in req.goals[:2]:
                clean = (title or "").strip()[:200]
                if clean:
                    db.add(Goal(user_id=user_id, title=clean))
        user.onboarding_step = "finish"
        await db.commit()
        return OnboardingStepResponse(success=True, current_step="finish", onboarding_completed=False, message="You can add more details whenever you are ready.")

    elif step == "finish":
        user.onboarding_completed = True
        user.onboarding_step = "completed"
        await db.commit()

        w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
        twin_weight = w_res.scalar_one_or_none()
        primary_twin = twin_weight.primary_twin if twin_weight else "rational"

        return OnboardingStepResponse(
            success=True,
            current_step="completed",
            onboarding_completed=True,
            primary_twin=primary_twin,
            twin_name=resolve_twin_name(user),
            message=f"You're all set. {user.twin_name or 'Echo'} is ready when you are."
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown onboarding step: '{step}'")

@router.get("/api/onboarding/state")
async def get_onboarding_state(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = get_current_user_id(request) or "demo-alex-rivers"
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = w_res.scalar_one_or_none()

    return {
        "user_id": user.id,
        "name": user.name,
        "twin_name": resolve_twin_name(user),
        "onboarding_completed": bool(user.onboarding_completed),
        "onboarding_step": user.onboarding_step or "tags",
        "primary_twin": twin_weight.primary_twin if twin_weight else "rational",
        "weights": {
            "rational": twin_weight.rational if twin_weight else 0.34,
            "emotional": twin_weight.emotional if twin_weight else 0.33,
            "ambitious": twin_weight.ambitious if twin_weight else 0.33
        } if twin_weight else None
    }

@router.put("/api/profile/twin-name", response_model=TwinNameUpdateResponse)
async def update_twin_name(
    req: TwinNameUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = req.user_id or get_current_user_id(request) or "demo-alex-rivers"
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    requested_name = (req.twin_name or "").strip()[:24]
    user.twin_name = requested_name or "Echo"
    user.twin_name_customized = bool(requested_name)
    await db.commit()

    return TwinNameUpdateResponse(
        user_id=user.id,
        user_name=user.name,
        twin_name=resolve_twin_name(user),
        twin_name_customized=bool(user.twin_name_customized),
    )
