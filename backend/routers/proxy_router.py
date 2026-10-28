from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

from backend.database import get_db
from backend.models import FocusBlock, CalendarNegotiation, Timetable, AuditLog
from backend.services.session_auth import require_production_session
from backend.services.calendar_proxy import evaluate_calendar_proposal

router = APIRouter(prefix="/api/proxy", tags=["Twin Proxy"])


class ProposalRequest(BaseModel):
    user_id: Optional[str] = "demo-user-alex"
    title: str = Field(..., example="Project Architecture Sync")
    requested_by: str = Field(..., example="Prof. Miller")
    duration_minutes: int = Field(default=60, ge=15, le=480)
    proposed_start_time: str = Field(..., example="2026-10-02T10:00:00")
    priority: str = Field(default="medium", example="medium")


class ActionRequest(BaseModel):
    user_id: Optional[str] = "demo-user-alex"
    action: str = Field(..., example="accept")  # 'accept', 'counter', 'decline'


class FocusBlockCreate(BaseModel):
    user_id: Optional[str] = "demo-user-alex"
    title: str = Field(..., example="Morning Deep Work")
    day_of_week: str = Field(..., example="Wednesday")
    start_time: str = Field(..., example="09:00")
    end_time: str = Field(..., example="12:00")
    is_protected: bool = True


@router.post("/negotiate")
async def negotiate_proposal(payload: ProposalRequest, db: AsyncSession = Depends(get_db)):
    """
    Evaluates an incoming calendar or task request with the Twin Proxy.
    Detects focus block collisions, schedule overlaps, and ML deadline risks.
    Drafts persona-aware counter-proposals.
    """
    user_id = payload.user_id or "demo-user-alex"
    try:
        dt = datetime.datetime.fromisoformat(payload.proposed_start_time.replace("Z", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISO date format for proposed_start_time")

    result = await evaluate_calendar_proposal(
        user_id=user_id,
        title=payload.title,
        requested_by=payload.requested_by,
        duration_minutes=payload.duration_minutes,
        proposed_start_time=dt,
        priority=payload.priority,
        db=db
    )
    return result


@router.get("/negotiations")
async def list_negotiations(user_id: str = "demo-user-alex", db: AsyncSession = Depends(get_db)):
    """List all past and pending negotiations evaluated by the Twin Proxy."""
    stmt = select(CalendarNegotiation).where(CalendarNegotiation.user_id == user_id).order_by(CalendarNegotiation.created_at.desc())
    res = await db.execute(stmt)
    rows = res.scalars().all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "requested_by": r.requested_by,
            "duration_minutes": r.duration_minutes,
            "proposed_start_time": r.proposed_start_time.isoformat() if r.proposed_start_time else None,
            "priority": r.priority,
            "status": r.status,
            "conflict_detected": r.conflict_detected,
            "conflict_reason": r.conflict_reason,
            "suggested_counter_time": r.suggested_counter_time.isoformat() if r.suggested_counter_time else None,
            "negotiation_message": r.negotiation_message,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rows
    ]


@router.post("/negotiations/{negotiation_id}/action")
async def action_negotiation(negotiation_id: int, payload: ActionRequest, db: AsyncSession = Depends(get_db)):
    """Accept, counter, or decline a proxy negotiation."""
    user_id = payload.user_id or "demo-user-alex"
    stmt = select(CalendarNegotiation).where(CalendarNegotiation.id == negotiation_id, CalendarNegotiation.user_id == user_id)
    res = await db.execute(stmt)
    neg = res.scalar_one_or_none()

    if not neg:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    action = payload.action.lower()
    if action not in ["accept", "counter", "decline"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept', 'counter', or 'decline'")

    neg.status = "accepted" if action == "accept" else ("countered" if action == "counter" else "declined")

    # If accepted, auto-create a Timetable entry for the user
    if action == "accept":
        day_name = neg.proposed_start_time.strftime("%A")
        start_time_str = neg.proposed_start_time.strftime("%H:%M")
        end_dt = neg.proposed_start_time + datetime.timedelta(minutes=neg.duration_minutes)
        end_time_str = end_dt.strftime("%H:%M")

        tt = Timetable(
            user_id=user_id,
            day_of_week=day_name,
            specific_date=neg.proposed_start_time,
            start_time=start_time_str,
            end_time=end_time_str,
            activity_name=f"{neg.title} ({neg.requested_by})",
            location="Remote / Scheduled",
            is_mandatory=True
        )
        db.add(tt)

    await db.commit()
    await db.refresh(neg)

    return {
        "id": neg.id,
        "status": neg.status,
        "message": f"Negotiation {action}ed successfully"
    }


@router.get("/focus-blocks")
async def list_focus_blocks(user_id: str = "demo-user-alex", db: AsyncSession = Depends(get_db)):
    """Get all protected deep work focus blocks for the user."""
    stmt = select(FocusBlock).where(FocusBlock.user_id == user_id).order_by(FocusBlock.created_at.desc())
    res = await db.execute(stmt)
    blocks = res.scalars().all()

    return [
        {
            "id": b.id,
            "title": b.title,
            "day_of_week": b.day_of_week,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "is_protected": b.is_protected,
            "created_at": b.created_at.isoformat() if b.created_at else None
        }
        for b in blocks
    ]


@router.post("/focus-blocks")
async def create_focus_block(payload: FocusBlockCreate, db: AsyncSession = Depends(get_db)):
    """Create a new protected deep work focus block."""
    user_id = payload.user_id or "demo-user-alex"
    fb = FocusBlock(
        user_id=user_id,
        title=payload.title,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_protected=payload.is_protected,
        created_at=datetime.datetime.utcnow()
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    return {
        "id": fb.id,
        "title": fb.title,
        "day_of_week": fb.day_of_week,
        "start_time": fb.start_time,
        "end_time": fb.end_time,
        "is_protected": fb.is_protected
    }


@router.delete("/focus-blocks/{block_id}")
async def delete_focus_block(block_id: int, user_id: str = "demo-user-alex", db: AsyncSession = Depends(get_db)):
    """Delete a protected focus block."""
    stmt = delete(FocusBlock).where(FocusBlock.id == block_id, FocusBlock.user_id == user_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "deleted", "id": block_id}
