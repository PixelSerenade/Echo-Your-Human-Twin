"""Transparent, lightweight ranking for choices backed by permitted deadlines."""
from __future__ import annotations

import datetime
import math
import re
from typing import Any, Iterable


def _priority_weight(value: str | None) -> float:
    return {"urgent": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}.get((value or "").lower(), 1.5)


def rank_deadlines_for_decision(
    deadlines: Iterable[Any], question: str, now: datetime.datetime | None = None
) -> dict[str, Any] | None:
    """Rank two relevant pending deadlines; percentages are attention shares, never odds."""
    now = now or datetime.datetime.utcnow()
    pending = [item for item in deadlines if not item.completed and item.due_date]
    if len(pending) < 2:
        return None

    q = question.lower()
    asks_assessment = bool(re.search(r"\b(exam|exams|test|tests|assessment)\b", q))
    asks_project = bool(re.search(r"\b(assignment|project|competition|event|deadline|work)\b", q))

    def days_until(item: Any) -> float:
        due = item.due_date
        reference = now.replace(tzinfo=due.tzinfo) if due.tzinfo else now.replace(tzinfo=None)
        return (due - reference).total_seconds() / 86400.0

    def score(item: Any) -> float:
        days = max(0.0, days_until(item))
        effort = max(0.0, float(item.estimated_hours or 0.0))
        # Earlier dates and explicit importance dominate; effort adds a modest
        # nudge to start substantial work sooner. The result is a relative share.
        return _priority_weight(item.priority) * 2.0 + 12.0 / (days + 1.0) + min(math.sqrt(effort), 3.0)

    # If the user named two kinds of work, compare those kinds first.
    relevant = pending
    if asks_assessment and asks_project:
        assessments = [item for item in pending if item.is_exam]
        other_work = [item for item in pending if not item.is_exam]
        if assessments and other_work:
            relevant = [min(assessments, key=days_until), min(other_work, key=days_until)]

    chosen = sorted(relevant, key=lambda item: (days_until(item), -score(item)))[:2]
    if len(chosen) < 2:
        return None
    raw = [score(item) for item in chosen]
    total = sum(raw)
    shares = [round(value * 100 / total) for value in raw]
    if sum(shares) != 100:
        shares[0] += 100 - sum(shares)

    def serialize(item: Any, share: int) -> dict[str, Any]:
        due = item.due_date
        return {
            "title": item.title,
            "due_date": due.strftime("%b %d").replace(" 0", " "),
            "priority": item.priority or "not specified",
            "estimated_hours": float(item.estimated_hours or 0.0),
            "attention_share_pct": share,
            "is_assessment": bool(item.is_exam),
        }

    items = [serialize(item, share) for item, share in zip(chosen, shares)]
    lead = max(range(2), key=lambda index: raw[index])
    return {
        "items": items,
        "recommended_index": lead,
        "recommended_title": items[lead]["title"],
        "score_method": "relative attention share from due date, saved priority, and estimated effort; not a success probability",
    }
