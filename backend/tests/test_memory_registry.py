import pytest
import uuid
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from backend.memory_registry import CATEGORY_IDS, CATEGORIES, PERSONAS, defaults_for, registry_for
from backend.models import Permission, User, Timetable, Deadline, StudyLog, Preference, DecisionHistory, Goal, ConsentEntry, MoneyEntry
from backend.services.data_access import get_permitted_user_data
from backend.main import app
from backend.database import AsyncSessionLocal
from backend.scripts.generate_data import init_models


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_persona_registry_has_complete_defaults_and_role_labels(persona):
    defaults = defaults_for(persona)
    assert set(defaults) == set(CATEGORY_IDS)
    assert defaults["mood_tone"] is False
    assert registry_for(persona)["simulator_labels"]["progress"]
    assert len(registry_for(persona)["categories"]) == len(CATEGORY_IDS)
    assert defaults["spending_money"] is False


def test_permission_labels_are_universal_and_hints_are_personalized():
    registries = [registry_for(persona) for persona in PERSONAS]
    labels = [{item["id"]: item["title"] for item in registry["categories"]} for registry in registries]
    assert all(label_set == labels[0] for label_set in labels)
    assert labels[0]["schedule_commitments"] == "Schedule & Commitments"
    assert labels[0]["deadlines_key_dates"] == "Deadlines & Key Dates"
    assert labels[0]["focus_work_patterns"] == "Focus & Work Patterns"
    assert labels[0]["spending_money"] == "Spending & Money"
    category_hints = [{item["id"]: item["hint"] for item in registry["categories"]} for registry in registries]
    assert len({hints["schedule_commitments"] for hints in category_hints}) > 1
    assert len({hints["deadlines_key_dates"] for hints in category_hints}) > 1
    assert len({hints["focus_work_patterns"] for hints in category_hints}) > 1
    other_copy = " ".join(str(value) for item in registry_for("other")["categories"] for value in item.values()).lower()
    for word in ("classes", "exams", "study", "timetable", "student", "semester", "course"):
        assert word not in other_copy


@pytest.mark.parametrize("persona,expected", [("student", "Study Progress"), ("working_professional", "Work Progress"), ("freelancer_founder", "Project Progress"), ("caregiver_parent", "Personal Progress"), ("other", "Personal Progress")])
def test_simulator_dimension_label_per_persona(persona, expected):
    assert registry_for(persona)["simulator_labels"]["progress"] == expected


class _Scalars:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class _Result:
    def __init__(self, values): self.values = values
    def scalars(self): return _Scalars(self.values)
    def scalar_one_or_none(self): return self.values[0] if self.values else None


class _GatewaySession:
    def __init__(self, disabled):
        self.disabled = disabled
        self.queried = []
        self.statements = []
        self.audit = None
    async def execute(self, statement):
        model = statement.column_descriptions[0]["entity"]
        self.queried.append(model)
        self.statements.append(statement)
        if model is Permission:
            rows = [Permission(user_id="u", source=category, enabled=category != self.disabled) for category in CATEGORY_IDS]
            return _Result(rows)
        if model is User:
            return _Result([User(id="u", persona="other")])
        return _Result([])
    def add(self, record): self.audit = record
    async def commit(self): return None


@pytest.mark.parametrize("category", CATEGORY_IDS)
@pytest.mark.asyncio
async def test_gateway_never_queries_disabled_category(category):
    session = _GatewaySession(category)
    await get_permitted_user_data(session, "u", log_audit_endpoint="/test")
    category_model = {
        "schedule_commitments": Timetable,
        "deadlines_key_dates": Deadline,
        "focus_work_patterns": StudyLog,
        "goals": Goal,
        "decision_history": DecisionHistory,
        "spending_money": MoneyEntry,
    }.get(category)
    if category_model is not None:
        assert category_model not in session.queried
    assert category not in session.audit.sources_accessed


@pytest.mark.asyncio
async def test_routine_preference_reads_exclude_financial_rows():
    session = _GatewaySession("spending_money")
    await get_permitted_user_data(session, "u", requested_sources=["routines_preferences"])
    preference_queries = [str(query).lower() for query, model in zip(session.statements, session.queried) if model is Preference]
    assert preference_queries
    assert all("preferences.category !=" in query for query in preference_queries)


@pytest.mark.asyncio
async def test_audit_records_canonical_memory_category_ids():
    session = _GatewaySession("mood_tone")
    await get_permitted_user_data(session, "u", log_audit_endpoint="/test")
    assert session.audit is not None
    assert set(session.audit.sources_accessed) <= set(CATEGORY_IDS)
    assert all(source not in {"timetable", "deadlines", "study_history", "preferences"} for source in session.audit.sources_accessed)


@pytest.mark.asyncio
async def test_persona_change_preserves_goals_and_existing_permissions():
    await init_models()
    user_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(User(id=user_id, name="Persona Test", email=f"{user_id}@example.test", persona="student"))
        db.add(Permission(user_id=user_id, source="focus_work_patterns", enabled=False))
        db.add(Goal(user_id=user_id, title="Keep this goal"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/profile/persona", json={"user_id": user_id, "persona": "freelancer_founder"})
    assert response.status_code == 200
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        goals = (await db.execute(select(Goal).where(Goal.user_id == user_id))).scalars().all()
        permissions = (await db.execute(select(Permission).where(Permission.user_id == user_id))).scalars().all()
        assert user.persona == "freelancer_founder"
        assert [goal.title for goal in goals] == ["Keep this goal"]
        assert next(permission for permission in permissions if permission.source == "focus_work_patterns").enabled is False
        assert [permission.source for permission in permissions] == ["focus_work_patterns"]
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_permission_updates_record_consent_entries():
    await init_models()
    user_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/permissions", json={"user_id": user_id, "permissions": {"mood_tone": False, "spending_money": False}})
    assert response.status_code == 200
    async with AsyncSessionLocal() as db:
        entries = (await db.execute(select(ConsentEntry).where(ConsentEntry.user_id == user_id).order_by(ConsentEntry.id))).scalars().all()
        assert [(entry.category, entry.value, entry.wording_version) for entry in entries] == [("mood_tone", False, "permissions-v1"), ("spending_money", False, "permissions-v1")]
        assert all(entry.timestamp is not None for entry in entries)
        user = await db.get(User, user_id)
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_plan_item_requires_permission_and_saves_a_specific_date():
    await init_models()
    user_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.put("/api/permissions", json={"user_id": user_id, "permissions": {"schedule_commitments": True}})
        response = await client.post("/api/plan-items", json={
            "user_id": user_id, "category": "schedule_commitments", "title": "Appointment",
            "date": "2030-04-05", "time": "14:30", "type": "commitment"
        })
        assert response.status_code == 200
        await client.put("/api/permissions", json={"user_id": user_id, "permissions": {"schedule_commitments": False}})
        denied = await client.post("/api/plan-items", json={
            "user_id": user_id, "category": "schedule_commitments", "title": "Private appointment",
            "date": "2030-04-06", "time": "10:00", "type": "commitment"
        })
        assert denied.status_code == 403
    async with AsyncSessionLocal() as db:
        entries = (await db.execute(select(Timetable).where(Timetable.user_id == user_id))).scalars().all()
        assert len(entries) == 1
        assert entries[0].activity_name == "Appointment"
        assert entries[0].specific_date.date().isoformat() == "2030-04-05"
        assert entries[0].start_time == "14:30"
        assert await db.get(User, user_id)
        user = await db.get(User, user_id)
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_money_tab_data_is_written_and_read_only_with_opt_in():
    await init_models()
    user_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.put("/api/permissions", json={"user_id": user_id, "permissions": {"spending_money": True}})
        created = await client.post("/api/plan-items", json={
            "user_id": user_id, "category": "spending_money", "title": "Groceries",
            "value": "42.50", "entry_type": "expense"
        })
        assert created.status_code == 200
        permitted = await client.get(f"/api/twin-knowledge?user_id={user_id}")
        assert permitted.json()["money_entries"][0]["amount"] == 42.5
        await client.put("/api/permissions", json={"user_id": user_id, "permissions": {"spending_money": False}})
        disabled = await client.get(f"/api/twin-knowledge?user_id={user_id}")
        assert disabled.json()["money_entries"] is None
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_additive_migration_keeps_legacy_student_records_and_permissions():
    await init_models()
    user_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        user = User(id=user_id, name="Legacy Test", email=f"{user_id}@example.test")
        db.add(user)
        await db.flush()
        db.add(Permission(user_id=user_id, source="timetable", enabled=False))
        db.add(Timetable(user_id=user_id, day_of_week="Tuesday", start_time="09:00", end_time="10:00", activity_name="Legacy commitment", location="Remote", is_mandatory=True))
        await db.commit()

    await init_models()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        legacy_permission = (await db.execute(select(Permission).where(Permission.user_id == user_id, Permission.source == "timetable"))).scalar_one()
        legacy_entry = (await db.execute(select(Timetable).where(Timetable.user_id == user_id))).scalar_one()
        assert user.persona == "student"
        assert legacy_permission.enabled is False
        assert legacy_entry.activity_name == "Legacy commitment"
        await db.delete(user)
        await db.commit()
