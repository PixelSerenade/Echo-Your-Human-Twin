from __future__ import annotations

import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models import User, TwinWeight, FocusBlock, CalendarNegotiation, AuditLog, Timetable, Deadline
from backend.services.data_access import get_permitted_user_data
from backend.ml.predictor import predictor


async def evaluate_calendar_proposal(
    user_id: str,
    title: str,
    requested_by: str,
    duration_minutes: int,
    proposed_start_time: datetime.datetime,
    priority: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Evaluates an incoming meeting/task proposal against user's permitted data:
    timetable, focus blocks, and ML deadline risk. Returns conflict evaluation,
    suggested counter-proposal, and persona-aligned negotiation text.
    """
    # 1. Fetch user & permitted data bundle through central gateway (db is 1st param)
    bundle = await get_permitted_user_data(db, user_id, log_audit_endpoint="/api/proxy/negotiate", audit_action="proxy_negotiation")

    # Fetch user profile & twin weights
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()

    weight_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = weight_res.scalar_one_or_none()

    primary_twin = twin_weight.primary_twin if twin_weight else "rational"
    twin_name = user.twin_name if (user and user.twin_name) else "Echo"
    user_display_name = user.name if (user and user.name) else "User"

    # 2. Fetch protected focus blocks for the user
    stmt = select(FocusBlock).where(FocusBlock.user_id == user_id, FocusBlock.is_protected == True)
    res = await db.execute(stmt)
    focus_blocks = res.scalars().all()

    proposed_end_time = proposed_start_time + datetime.timedelta(minutes=duration_minutes)
    day_name = proposed_start_time.strftime("%A")

    conflicts: List[str] = []
    conflict_detected = False

    # Check Timetable entries
    for item in bundle.timetable:
        if item.day_of_week.lower() == day_name.lower():
            try:
                item_start = datetime.datetime.strptime(item.start_time, "%H:%M").time()
                item_end = datetime.datetime.strptime(item.end_time, "%H:%M").time()
                p_start = proposed_start_time.time()
                p_end = proposed_end_time.time()

                if max(p_start, item_start) < min(p_end, item_end):
                    conflict_detected = True
                    conflicts.append(f"Direct conflict with existing scheduled activity: '{item.activity_name}' ({item.start_time} - {item.end_time}).")
            except ValueError:
                pass

    # Check Focus Blocks
    for fb in focus_blocks:
        if fb.day_of_week.lower() == day_name.lower():
            try:
                fb_start = datetime.datetime.strptime(fb.start_time, "%H:%M").time()
                fb_end = datetime.datetime.strptime(fb.end_time, "%H:%M").time()
                p_start = proposed_start_time.time()
                p_end = proposed_end_time.time()

                if max(p_start, fb_start) < min(p_end, fb_end):
                    conflict_detected = True
                    conflicts.append(f"Collides with protected deep work block: '{fb.title}' ({fb.start_time} - {fb.end_time}).")
            except ValueError:
                pass

    # Check ML Deadline Risk within 72 hours
    now = datetime.datetime.utcnow()
    window_end = now + datetime.timedelta(days=3)

    high_risk_deadlines: List[Dict[str, Any]] = []

    for dl in bundle.deadlines:
        if not dl.completed and dl.due_date <= window_end:
            hrs_left = max((dl.due_date - now).total_seconds() / 3600.0, 0.1)
            pred = predictor.predict(
                estimated_hours=dl.estimated_hours,
                days_until_deadline=hrs_left / 24.0,
                priority_numeric=3 if dl.priority == "high" else (2 if dl.priority == "medium" else 1)
            )
            on_time_prob = pred["on_time_probability"]

            if on_time_prob < 0.60 or dl.priority == "high":
                high_risk_deadlines.append({
                    "title": dl.title,
                    "due_date": dl.due_date.strftime("%A at %I:%M %p"),
                    "on_time_probability": round(on_time_prob * 100, 1),
                    "estimated_hours": dl.estimated_hours
                })

    if high_risk_deadlines and priority not in ["critical"]:
        conflict_detected = True
        deadline_titles = ", ".join([d["title"] for d in high_risk_deadlines])
        conflicts.append(f"High deadline risk detected! Pending upcoming deliverables: {deadline_titles} (on-time probability drops as low as {high_risk_deadlines[0]['on_time_probability']}%).")

    # 3. Calculate suggested counter-proposal time if conflict exists
    suggested_counter: Optional[datetime.datetime] = None
    if conflict_detected:
        candidate_date = proposed_start_time + datetime.timedelta(days=1)
        suggested_counter = candidate_date.replace(hour=14, minute=0, second=0, microsecond=0)
    else:
        suggested_counter = proposed_start_time

    # 4. Craft persona-aligned twin proxy message
    if not conflict_detected:
        msg = (
            f"Hello {requested_by},\n\n"
            f"I evaluated your proposal for '{title}' on {proposed_start_time.strftime('%A, %B %d at %I:%M %p')}. "
            f"My schedule and workload permit this meeting. I have confirmed and added this block to my calendar.\n\n"
            f"Best regards,\n{user_display_name} (via {twin_name} Twin Proxy)"
        )
        conflict_reason = None
    else:
        reasons_text = " ".join(conflicts)
        counter_str = suggested_counter.strftime("%A, %B %d at %I:%M %p") if suggested_counter else "a later slot"

        if primary_twin == "rational":
            msg = (
                f"Hello {requested_by},\n\n"
                f"Thank you for reaching out regarding '{title}'. "
                f"My Rational Twin evaluated my current workload density and identified schedule conflicts: {reasons_text}\n\n"
                f"To protect high-priority deliverables and maintain efficiency, my twin proxy proposes rescheduling to {counter_str}. "
                f"Please let me know if this proposed window works for you.\n\n"
                f"Best regards,\n{user_display_name} (via {twin_name} Twin Proxy)"
            )
        elif primary_twin == "emotional":
            msg = (
                f"Hi {requested_by},\n\n"
                f"Thanks for sending over the request for '{title}'. "
                f"I'm currently balancing tight commitments ({reasons_text}) and need to protect my focus and well-being to avoid burnout.\n\n"
                f"Would it be possible for us to meet on {counter_str} instead? That will give me the breathing room to be fully present.\n\n"
                f"Warmly,\n{user_display_name} (via {twin_name} Twin Proxy)"
            )
        else: # ambitious
            msg = (
                f"Hello {requested_by},\n\n"
                f"Thank you for the invitation to '{title}'. "
                f"I am focused on delivering critical milestones right now: {reasons_text}\n\n"
                f"To ensure I can give this meeting my full strategic focus without compromising ongoing key objectives, I propose meeting on {counter_str}.\n\n"
                f"Best,\n{user_display_name} (via {twin_name} Twin Proxy)"
            )
        conflict_reason = reasons_text

    # 5. Persist negotiation record
    neg = CalendarNegotiation(
        user_id=user_id,
        title=title,
        requested_by=requested_by,
        duration_minutes=duration_minutes,
        proposed_start_time=proposed_start_time,
        priority=priority,
        status="countered" if conflict_detected else "accepted",
        conflict_detected=conflict_detected,
        conflict_reason=conflict_reason,
        suggested_counter_time=suggested_counter,
        negotiation_message=msg,
        created_at=datetime.datetime.utcnow()
    )
    db.add(neg)
    await db.commit()
    await db.refresh(neg)

    return {
        "id": neg.id,
        "title": neg.title,
        "requested_by": neg.requested_by,
        "duration_minutes": neg.duration_minutes,
        "proposed_start_time": neg.proposed_start_time.isoformat(),
        "priority": neg.priority,
        "status": neg.status,
        "conflict_detected": neg.conflict_detected,
        "conflict_reason": neg.conflict_reason,
        "suggested_counter_time": neg.suggested_counter_time.isoformat() if neg.suggested_counter_time else None,
        "negotiation_message": neg.negotiation_message,
        "high_risk_deadlines": high_risk_deadlines,
        "primary_twin": primary_twin,
        "twin_name": twin_name,
        "created_at": neg.created_at.isoformat()
    }
