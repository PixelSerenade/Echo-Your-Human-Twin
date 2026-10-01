from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import datetime

from backend.models import Permission, Timetable, Deadline, StudyLog, Preference, DecisionHistory, AuditLog, Goal, User, MoneyEntry, UserMemory
from backend.memory_registry import CATEGORIES, CATEGORY_IDS, LEGACY_TO_CATEGORY, defaults_for

ALL_SOURCES = CATEGORY_IDS

@dataclass
class PermittedDataBundle:
    user_id: str
    enabled_sources: Dict[str, bool]
    timetable: List[Timetable] = field(default_factory=list)
    deadlines: List[Deadline] = field(default_factory=list)
    study_history: List[StudyLog] = field(default_factory=list)
    preferences: List[Preference] = field(default_factory=list)
    spending_preferences: List[Preference] = field(default_factory=list)
    money_entries: List[MoneyEntry] = field(default_factory=list)
    decision_history: List[DecisionHistory] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)
    memories: List[UserMemory] = field(default_factory=list)
    accessed_sources: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """
        Builds a sanitized, formatted context string for LLM prompts containing
        ONLY data from enabled sources.
        """
        sections = []

        if ("schedule_commitments" in self.accessed_sources or "timetable" in self.accessed_sources) and self.timetable:
            t_lines = ["--- Schedule & Recurring Commitments ---"]
            for t in self.timetable:
                t_lines.append(f"- {t.day_of_week} {t.start_time}-{t.end_time}: {t.activity_name} ({t.location}) [{'Mandatory' if t.is_mandatory else 'Optional'}]")
            sections.append("\n".join(t_lines))

        if ("deadlines_key_dates" in self.accessed_sources or "deadlines" in self.accessed_sources) and self.deadlines:
            d_lines = ["--- Current Deadlines & Key Dates ---"]
            for d in self.deadlines:
                due_str = d.due_date.strftime("%Y-%m-%d %H:%M") if hasattr(d.due_date, 'strftime') else str(d.due_date)
                kind = "Assessment" if d.is_exam else "Task or milestone"
                status = "Completed" if d.completed else "Pending"
                d_lines.append(f"- [{kind}] {d.title} ({d.course_or_project}) | Date: {due_str} | Estimated Effort: {d.estimated_hours}h | Priority: {d.priority} | Status: {status}")
            sections.append("\n".join(d_lines))

        if ("focus_work_patterns" in self.accessed_sources or "study_history" in self.accessed_sources) and self.study_history:
            s_lines = ["--- Recent Focus & Work Patterns ---"]
            for s in self.study_history[-10:]:  # Last 10 records
                s_lines.append(f"- {s.subject} ({s.time_of_day}): {s.hours_spent}h, Rating: {s.focus_rating}/10, Energy: {s.energy_before}->{s.energy_after}")
            sections.append("\n".join(s_lines))

        if ("routines_preferences" in self.accessed_sources or "preferences" in self.accessed_sources) and self.preferences:
            p_lines = ["--- Routines & Preferences ---"]
            for p in self.preferences:
                p_lines.append(f"- {p.key}: {p.value} ({p.category})")
            sections.append("\n".join(p_lines))

        if "spending_money" in self.accessed_sources and self.spending_preferences:
            sections.append("--- Spending & Money Preferences ---\n" + "\n".join(f"- {p.key}: {p.value}" for p in self.spending_preferences))

        if "decision_history" in self.accessed_sources and self.decision_history:
            dh_lines = ["--- Past Decisions & Patterns ---"]
            for dh in self.decision_history[-5:]:  # Last 5 decisions
                dh_lines.append(f"- Q: '{dh.question}' | Chosen: '{dh.option_chosen}' (Aligned: {dh.aligned_twin}, Rec: {dh.twin_recommended})")
            sections.append("\n".join(dh_lines))

        if "goals" in self.accessed_sources and self.goals:
            sections.append("--- Goals ---\n" + "\n".join(f"- {g.title} ({g.status})" for g in self.goals))

        if self.memories:
            sections.append("--- Important details the user chose to share ---\n" + "\n".join(
                f"- [{memory.category}] {memory.fact}" for memory in self.memories
            ))

        if not sections:
            return "No permitted personal data available (all sources are either disabled or empty)."

        return "\n\n".join(sections)


async def get_permitted_user_data(
    db: AsyncSession,
    user_id: str,
    requested_sources: Optional[List[str]] = None,
    log_audit_endpoint: Optional[str] = None,
    audit_action: str = "data_access"
) -> PermittedDataBundle:
    """
    SINGLE DATA-ACCESS GATEWAY ENFORCING PRIVACY.
    Used by every endpoint. Returns only enabled sources.
    Disabled sources are NEVER queried from the database and NEVER sent to Gemini.
    Logs access into audit_log.
    """
    # 1. Fetch current user permissions
    perm_result = await db.execute(
        select(Permission).where(Permission.user_id == user_id)
    )
    user_perms = {p.source: p.enabled for p in perm_result.scalars().all()}

    # Personal data defaults on for legacy users; mood inference is opt-in.
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    defaults = defaults_for(getattr(user, "persona", "student"))
    enabled_map = {}
    for src in ALL_SOURCES:
        legacy = CATEGORIES[src]["legacy"]
        enabled_map[src] = user_perms.get(src, user_perms.get(legacy, defaults[src]) if legacy else defaults[src])
        if legacy:
            enabled_map[legacy] = enabled_map[src]

    # 2. Determine which sources can actually be fetched
    sources_to_query = []
    candidates = requested_sources if requested_sources is not None else ALL_SOURCES
    for requested in candidates:
        src = LEGACY_TO_CATEGORY.get(requested, requested)
        if src in CATEGORIES and enabled_map.get(src) and src not in sources_to_query:
            sources_to_query.append(src)

    bundle = PermittedDataBundle(
        user_id=user_id,
        enabled_sources=enabled_map,
        # Keep legacy names available to existing internal consumers during migration.
        accessed_sources=sources_to_query + [CATEGORIES[src]["legacy"] for src in sources_to_query if CATEGORIES[src]["legacy"]]
    )

    # 3. Strictly query only the enabled and requested sources
    if "schedule_commitments" in sources_to_query:
        res = await db.execute(select(Timetable).where(Timetable.user_id == user_id))
        bundle.timetable = list(res.scalars().all())

    if "deadlines_key_dates" in sources_to_query:
        res = await db.execute(
            select(Deadline)
            .where(Deadline.user_id == user_id)
            .order_by(Deadline.due_date.asc())
        )
        bundle.deadlines = list(res.scalars().all())

    if "focus_work_patterns" in sources_to_query:
        res = await db.execute(
            select(StudyLog)
            .where(StudyLog.user_id == user_id)
            .order_by(StudyLog.timestamp.desc())
        )
        bundle.study_history = list(res.scalars().all())

    if "routines_preferences" in sources_to_query:
        # Financial preferences are isolated behind their own opt-in category.
        res = await db.execute(select(Preference).where(Preference.user_id == user_id, Preference.category != "spending"))
        bundle.preferences = list(res.scalars().all())

    if "spending_money" in sources_to_query:
        # This table is queried for financial preferences only when that opt-in
        # category is enabled and explicitly requested.
        res = await db.execute(select(Preference).where(Preference.user_id == user_id, Preference.category == "spending"))
        bundle.spending_preferences = list(res.scalars().all())
        result = await db.execute(select(MoneyEntry).where(MoneyEntry.user_id == user_id).order_by(MoneyEntry.entry_date.desc()))
        bundle.money_entries = list(result.scalars().all())

    if "decision_history" in sources_to_query:
        res = await db.execute(
            select(DecisionHistory)
            .where(DecisionHistory.user_id == user_id)
            .order_by(DecisionHistory.timestamp.desc())
        )
        bundle.decision_history = list(res.scalars().all())

    if "goals" in sources_to_query:
        res = await db.execute(select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at.desc()))
        bundle.goals = list(res.scalars().all())

    # Memories are scoped to enabled categories and this user only.
    if sources_to_query:
        res = await db.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.category.in_(sources_to_query),
            ).order_by(UserMemory.importance.desc(), UserMemory.updated_at.desc()).limit(40)
        )
        bundle.memories = list(res.scalars().all())

    # 4. Record access in audit log
    if log_audit_endpoint and sources_to_query:
        audit_entry = AuditLog(
            user_id=user_id,
            action=audit_action,
            endpoint=log_audit_endpoint,
            sources_accessed=sources_to_query,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(audit_entry)
        await db.commit()

    return bundle
