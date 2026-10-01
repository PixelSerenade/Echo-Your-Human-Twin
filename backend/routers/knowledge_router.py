from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Dict, Any, Optional
from pydantic import BaseModel
import datetime
import math

from backend.database import get_db
from backend.models import (
    Timetable, Deadline, StudyLog, Preference, DecisionHistory, Permission, Goal, MoneyEntry, UserMemory, AuditLog,
    normalize_goal_milestones, normalize_json_list,
)
from backend.services.data_access import get_permitted_user_data, ALL_SOURCES
from backend.memory_registry import CATEGORIES
from backend.schemas import (
    TwinKnowledgeResponse, TimetableItem, DeadlineItem, StudyLogItem,
    PreferenceItem, DecisionHistoryItem, GoalItem
)

router = APIRouter(tags=["Twin Knowledge CRUD"])

class KnowledgeEditRequest(BaseModel):
    title_or_activity: Optional[str] = None
    course_or_subject: Optional[str] = None
    estimated_hours: Optional[float] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    value: Optional[str] = None

class PlanItemCreateRequest(BaseModel):
    user_id: str
    category: str
    title: str
    date: Optional[datetime.date] = None
    time: Optional[str] = None
    type: Optional[str] = None
    value: Optional[str] = None
    entry_type: Optional[str] = "expense"

class GoalProgressRequest(BaseModel):
    milestones: list[Dict[str, Any]]

@router.post("/api/plan-items")
async def create_plan_item(req: PlanItemCreateRequest, db: AsyncSession = Depends(get_db)):
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Please add a title.")
    category = req.category
    valid = {"schedule_commitments", "deadlines_key_dates", "goals", "spending_money"}
    if category not in valid:
        raise HTTPException(status_code=400, detail="That item type is not supported.")
    bundle = await get_permitted_user_data(
        db, req.user_id, requested_sources=[category],
        log_audit_endpoint="/api/plan-items", audit_action="create_plan_item"
    )
    if category not in bundle.accessed_sources:
        raise HTTPException(status_code=403, detail="Turn on this category in Privacy before adding an item.")
    if category == "schedule_commitments":
        if not req.date:
            raise HTTPException(status_code=422, detail="Choose a date for this commitment.")
        from datetime import datetime as dt, time as dtime, timedelta
        try:
            parsed_start = dtime.fromisoformat(req.time or "09:00")
            if parsed_start.tzinfo is not None:
                raise ValueError
            start = parsed_start.strftime("%H:%M")
            end = (dt.combine(req.date, parsed_start) + timedelta(hours=1)).strftime("%H:%M")
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Choose a valid time.")
        item = Timetable(user_id=req.user_id, day_of_week=req.date.strftime("%A"), specific_date=dt.combine(req.date, dt.min.time()), start_time=start, end_time=end, activity_name=title, location="", is_mandatory=True)
        db.add(item)
        await db.commit()
        return {"id": item.id, "category": category}
    if category == "deadlines_key_dates":
        if not req.date:
            raise HTTPException(status_code=422, detail="Choose a date for this item.")
        from datetime import datetime as dt, time as dtime
        if req.time:
            try:
                parsed_time = dtime.fromisoformat(req.time)
                if parsed_time.tzinfo is not None:
                    raise ValueError
                due = dt.combine(req.date, parsed_time)
            except ValueError:
                raise HTTPException(status_code=422, detail="Choose a valid time.")
        else:
            due = dt.combine(req.date, dtime.min)
        item = Deadline(user_id=req.user_id, title=title, course_or_project="Personal", due_date=due, estimated_hours=0, completed=False, priority="medium", is_exam=False)
        db.add(item)
        await db.commit()
        return {"id": item.id, "category": category}
    if category == "goals":
        target_date = datetime.datetime.combine(req.date, datetime.time.min) if req.date else None
        item = Goal(user_id=req.user_id, title=title, status="active", target_date=target_date)
        db.add(item)
        await db.commit()
        return {"id": item.id, "category": category}
    try:
        amount = float(req.value or "0")
    except ValueError:
        raise HTTPException(status_code=422, detail="Enter an amount using numbers.")
    if amount < 0 or not math.isfinite(amount):
        raise HTTPException(status_code=422, detail="Enter a valid amount.")
    if req.entry_type not in {"expense", "budget"}:
        raise HTTPException(status_code=422, detail="Choose an expense or budget.")
    item = MoneyEntry(user_id=req.user_id, category=title, amount=amount, entry_type=req.entry_type)
    db.add(item)
    await db.commit()
    return {"id": item.id, "category": category}


@router.put("/api/goals/{goal_id}")
async def update_goal_progress(goal_id: int, req: GoalProgressRequest, user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    bundle = await get_permitted_user_data(
        db, user_id, requested_sources=["goals"],
        log_audit_endpoint="/api/goals", audit_action="update_goal_progress",
    )
    if "goals" not in bundle.accessed_sources:
        raise HTTPException(status_code=403, detail="Turn on Goals in Privacy before updating progress.")
    goal = await db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    milestones = []
    for item in req.milestones[:10]:
        title = " ".join(str(item.get("title", "")).split())[:120]
        if title:
            milestones.append({"title": title, "completed": bool(item.get("completed", False))})
    goal.milestones = milestones
    goal.progress = round(100 * sum(item["completed"] for item in milestones) / len(milestones)) if milestones else 0
    goal.status = "completed" if milestones and goal.progress == 100 else "active"
    db.add(AuditLog(user_id=user_id, action="update_goal_milestones", endpoint="/api/goals", sources_accessed=["goals"], timestamp=datetime.datetime.utcnow()))
    await db.commit()
    return {"id": goal.id, "progress": goal.progress, "status": goal.status, "milestones": goal.milestones}


@router.delete("/api/goals/{goal_id}")
async def delete_goal(goal_id: int, user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    bundle = await get_permitted_user_data(
        db, user_id, requested_sources=["goals"],
        log_audit_endpoint="/api/goals", audit_action="delete_goal",
    )
    if "goals" not in bundle.accessed_sources:
        raise HTTPException(status_code=403, detail="Turn on Goals in Privacy before deleting a goal.")
    goal = await db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    await db.delete(goal)
    db.add(AuditLog(user_id=user_id, action="delete_goal", endpoint="/api/goals", sources_accessed=["goals"], timestamp=datetime.datetime.utcnow()))
    await db.commit()
    return {"id": goal_id, "deleted": True}


@router.get("/api/reminders")
async def get_reminders(user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Read only the opted-in schedule and deadline categories for the reminder bell."""
    bundle = await get_permitted_user_data(
        db,
        user_id=user_id,
        requested_sources=["schedule_commitments", "deadlines_key_dates"],
        log_audit_endpoint="/api/reminders",
        audit_action="read_reminders",
    )
    return {
        "active_permissions": {
            "schedule_commitments": bool(bundle.enabled_sources.get("schedule_commitments", False)),
            "deadlines_key_dates": bool(bundle.enabled_sources.get("deadlines_key_dates", False)),
        },
        "timetable": [
            {"id": item.id, "day_of_week": item.day_of_week, "specific_date": item.specific_date,
             "start_time": item.start_time, "activity_name": item.activity_name}
            for item in bundle.timetable
        ] if "schedule_commitments" in bundle.accessed_sources else None,
        "deadlines": [
            {"id": item.id, "title": item.title, "due_date": item.due_date, "completed": item.completed}
            for item in bundle.deadlines
        ] if "deadlines_key_dates" in bundle.accessed_sources else None,
    }

@router.get("/twin-knowledge", response_model=TwinKnowledgeResponse)
@router.get("/api/twin-knowledge", response_model=TwinKnowledgeResponse)
async def get_twin_knowledge(
    user_id: str = Query("demo-alex-rivers", description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns viewable data for all permitted sources.
    Sources disabled in privacy settings return empty / omitted.
    """
    bundle = await get_permitted_user_data(
        db, user_id=user_id, log_audit_endpoint="/twin-knowledge", audit_action="read_knowledge"
    )

    timetable_items = [
        TimetableItem(
            id=t.id, day_of_week=t.day_of_week, specific_date=t.specific_date, start_time=t.start_time, end_time=t.end_time,
            activity_name=t.activity_name, location=t.location, is_mandatory=t.is_mandatory
        ) for t in bundle.timetable
    ] if "timetable" in bundle.accessed_sources else None

    deadline_items = [
        DeadlineItem(
            id=d.id, title=d.title, course_or_project=d.course_or_project,
            due_date=d.due_date, estimated_hours=d.estimated_hours, actual_hours=d.actual_hours,
            completed=d.completed, priority=d.priority, is_exam=d.is_exam
        ) for d in bundle.deadlines
    ] if "deadlines" in bundle.accessed_sources else None

    study_items = [
        StudyLogItem(
            id=s.id, timestamp=s.timestamp, subject=s.subject, hours_spent=s.hours_spent,
            focus_rating=s.focus_rating, time_of_day=s.time_of_day,
            energy_before=s.energy_before, energy_after=s.energy_after
        ) for s in bundle.study_history
    ] if "study_history" in bundle.accessed_sources else None

    pref_items = [
        PreferenceItem(id=p.id, key=p.key, value=p.value, category=p.category)
        for p in bundle.preferences
    ] if "preferences" in bundle.accessed_sources else None
    spending_items = [
        PreferenceItem(id=p.id, key=p.key, value=p.value, category=p.category)
        for p in bundle.spending_preferences
    ] if "spending_money" in bundle.accessed_sources else None

    decision_items = [
        DecisionHistoryItem(
            id=dh.id, question=dh.question, options=normalize_json_list(dh.options), twin_recommended=dh.twin_recommended,
            option_chosen=dh.option_chosen, aligned_twin=dh.aligned_twin,
            followed_recommendation=dh.followed_recommendation, timestamp=dh.timestamp,
            feedback_understood=dh.feedback_understood
        ) for dh in bundle.decision_history
    ] if "decision_history" in bundle.accessed_sources else None

    goal_items = [GoalItem(id=g.id, title=g.title, description=g.description, status=g.status, target_date=g.target_date, progress=g.progress, next_step=g.next_step, milestones=normalize_goal_milestones(g.milestones)) for g in bundle.goals] if "goals" in bundle.accessed_sources else None

    generic_memory = {}
    if "schedule_commitments" in bundle.accessed_sources:
        generic_memory["schedule_commitments"] = [{"id": t.id, "title": t.activity_name, "start": t.start_time, "end": t.end_time, "recurrence": t.day_of_week, "type": "required" if t.is_mandatory else "optional", "location": t.location} for t in bundle.timetable]
    if "deadlines_key_dates" in bundle.accessed_sources:
        generic_memory["deadlines_key_dates"] = [{"id": d.id, "title": d.title, "category": "assessment" if d.is_exam else "task", "deadline": d.due_date, "estimated_effort": d.estimated_hours, "actual_effort": d.actual_hours, "priority": d.priority, "status": "completed" if d.completed else "open"} for d in bundle.deadlines]
    if "focus_work_patterns" in bundle.accessed_sources:
        generic_memory["focus_work_patterns"] = [{"id": s.id, "activity": s.subject, "duration": s.hours_spent, "time_of_day": s.time_of_day, "outcome": {"energy_before": s.energy_before, "energy_after": s.energy_after}, "rating": s.focus_rating, "timestamp": s.timestamp} for s in bundle.study_history]
    if "routines_preferences" in bundle.accessed_sources:
        generic_memory["routines_preferences"] = [{"id": p.id, "key": p.key, "value": p.value, "category": p.category} for p in bundle.preferences]
    if "goals" in bundle.accessed_sources:
        generic_memory["goals"] = [{"id": g.id, "title": g.title, "description": g.description, "status": g.status, "target_date": g.target_date, "progress": g.progress, "next_step": g.next_step, "milestones": normalize_goal_milestones(g.milestones)} for g in bundle.goals]
    if "decision_history" in bundle.accessed_sources:
        generic_memory["decision_history"] = [{"id": d.id, "question": d.question, "chosen_option": d.option_chosen, "recommended_option": d.twin_recommended, "feedback_understood": d.feedback_understood} for d in bundle.decision_history]

    return TwinKnowledgeResponse(
        user_id=user_id,
        active_permissions=bundle.enabled_sources,
        timetable=timetable_items,
        deadlines=deadline_items,
        study_history=study_items,
        preferences=pref_items,
        spending_preferences=spending_items,
        money_entries=[{"id": item.id, "category": item.category, "amount": item.amount, "entry_type": item.entry_type, "entry_date": item.entry_date} for item in bundle.money_entries] if "spending_money" in bundle.accessed_sources else None,
        decision_history=decision_items,
        goals=goal_items,
        memories=[{"id": memory.id, "category": memory.category, "fact": memory.fact,
                   "importance": memory.importance, "confidence": memory.confidence,
                   "updated_at": memory.updated_at} for memory in bundle.memories],
        memory_categories=generic_memory
    )

@router.put("/twin-knowledge/{source}/{item_id}")
@router.put("/api/twin-knowledge/{source}/{item_id}")
async def edit_twin_knowledge_item(
    source: str,
    item_id: int,
    req: KnowledgeEditRequest,
    user_id: str = Query("demo-alex-rivers"),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Edit a stored knowledge item."""
    source = source.lower()
    if source == "memories":
        if category not in CATEGORIES:
            raise HTTPException(status_code=400, detail="Choose a memory category.")
        permitted = await get_permitted_user_data(
            db, user_id=user_id, requested_sources=[category],
            log_audit_endpoint="/twin-knowledge/memories", audit_action="edit_chat_memory",
        )
        if category not in permitted.accessed_sources:
            raise HTTPException(status_code=403, detail="Turn on this category in Privacy to manage this memory.")
        item = await db.get(UserMemory, item_id)
        if not item or item.user_id != user_id or item.category != category:
            raise HTTPException(status_code=404, detail="Memory not found")
        if not req.value or not req.value.strip():
            raise HTTPException(status_code=422, detail="Memory text cannot be empty.")
        item.fact = req.value.strip()[:700]
        item.updated_at = datetime.datetime.utcnow()
        await db.commit()
        return {"status": "success", "message": "Memory updated"}
    if source == "deadlines":
        item = await db.get(Deadline, item_id)
        if not item or item.user_id != user_id:
            raise HTTPException(status_code=404, detail="Deadline not found")
        if req.title_or_activity:
            item.title = req.title_or_activity
        if req.course_or_subject:
            item.course_or_project = req.course_or_subject
        if req.estimated_hours is not None:
            item.estimated_hours = req.estimated_hours
        if req.completed is not None:
            item.completed = req.completed
        if req.priority:
            item.priority = req.priority
    elif source == "timetable":
        item = await db.get(Timetable, item_id)
        if not item or item.user_id != user_id:
            raise HTTPException(status_code=404, detail="Timetable entry not found")
        if req.title_or_activity:
            item.activity_name = req.title_or_activity
    elif source == "preferences":
        item = await db.get(Preference, item_id)
        if not item or item.user_id != user_id:
            raise HTTPException(status_code=404, detail="Preference not found")
        if req.value:
            item.value = req.value
    else:
        raise HTTPException(status_code=400, detail=f"Editing source '{source}' not supported")

    await db.commit()
    return {"status": "success", "message": f"Updated {source} item {item_id}"}

@router.delete("/twin-knowledge/{source}/{item_id}")
@router.delete("/api/twin-knowledge/{source}/{item_id}")
async def delete_twin_knowledge_item(
    source: str,
    item_id: int,
    user_id: str = Query("demo-alex-rivers"),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete a stored knowledge item."""
    source = source.lower()
    if source == "memories":
        if category not in CATEGORIES:
            raise HTTPException(status_code=400, detail="Choose a memory category.")
        permitted = await get_permitted_user_data(
            db, user_id=user_id, requested_sources=[category],
            log_audit_endpoint="/twin-knowledge/memories", audit_action="delete_chat_memory",
        )
        if category not in permitted.accessed_sources:
            raise HTTPException(status_code=403, detail="Turn on this category in Privacy to manage this memory.")
        item = await db.get(UserMemory, item_id)
        if not item or item.user_id != user_id or item.category != category:
            raise HTTPException(status_code=404, detail=f"Item not found in {source}")
        await db.delete(item)
        await db.commit()
        return {"status": "success", "message": "Memory deleted"}
    model_map = {
        "deadlines": Deadline,
        "timetable": Timetable,
        "study_history": StudyLog,
        "preferences": Preference,
        "decision_history": DecisionHistory
    }
    model = model_map.get(source)
    if not model:
        raise HTTPException(status_code=400, detail=f"Source '{source}' not recognized")

    item = await db.get(model, item_id)
    if not item or item.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Item not found in {source}")

    await db.delete(item)
    await db.commit()
    return {"status": "success", "message": f"Deleted {source} item {item_id}"}
