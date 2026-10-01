import pytest
import pytest_asyncio
import os
import sys
import datetime
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine, Base, AsyncSessionLocal
from backend.models import User, ProfileTag, TwinWeight, Permission, AuditLog, Deadline
from backend.services.data_access import get_permitted_user_data, ALL_SOURCES
from backend.scripts.generate_data import init_models, seed_demo_persona, generate_500_ml_tasks, USER_ID

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_db():
    await init_models()
    generate_500_ml_tasks(num_rows=550)
    await seed_demo_persona()
    yield
    # Cleanup if needed
    async with engine.begin() as conn:
        pass

@pytest.mark.asyncio
async def test_demo_persona_seeded():
    async with AsyncSessionLocal() as session:
        user = await session.get(User, USER_ID)
        assert user is not None
        assert user.name == "Alex Rivers"
        assert user.demo_mode is True

        # Check weights
        w_res = await session.execute(select(TwinWeight).where(TwinWeight.user_id == USER_ID))
        weights = w_res.scalar_one()
        assert weights.primary_twin == "rational"
        assert weights.rational == 0.50
        assert weights.emotional == 0.25
        assert weights.ambitious == 0.25

        # Check planted conflict
        d_res = await session.execute(select(Deadline).where(Deadline.user_id == USER_ID))
        deadlines = d_res.scalars().all()
        assert len(deadlines) >= 4
        exam_found = any(d.is_exam and "Midterm" in d.title for d in deadlines)
        assignment_found = any(not d.is_exam and "Cloud" in d.title for d in deadlines)
        assert exam_found, "Planted Midterm exam deadline must exist"
        assert assignment_found, "Planted Cloud project deadline must exist"

@pytest.mark.asyncio
async def test_permission_enforcement_gateway_enabled_all():
    async with AsyncSessionLocal() as session:
        bundle = await get_permitted_user_data(
            session, USER_ID, log_audit_endpoint="/test-endpoint-all"
        )
        assert "timetable" in bundle.accessed_sources
        assert "deadlines" in bundle.accessed_sources
        assert "study_history" in bundle.accessed_sources
        assert len(bundle.timetable) > 0
        assert len(bundle.deadlines) > 0
        assert len(bundle.study_history) > 0

        context = bundle.to_context_string()
        assert "Midterm Exam" in context
        assert "Distributed Systems Lecture" in context

        # Check audit log
        audit_res = await session.execute(
            select(AuditLog).where(AuditLog.endpoint == "/test-endpoint-all")
        )
        log = audit_res.scalar_one_or_none()
        assert log is not None
        assert "deadlines" in log.sources_accessed

@pytest.mark.asyncio
async def test_permission_enforcement_gateway_disabled_source():
    async with AsyncSessionLocal() as session:
        # Disable 'deadlines'
        p_res = await session.execute(
            select(Permission).where(Permission.user_id == USER_ID, Permission.source == "deadlines")
        )
        perm = p_res.scalar_one()
        perm.enabled = False
        await session.commit()

        # Call data gateway
        bundle = await get_permitted_user_data(
            session, USER_ID, log_audit_endpoint="/test-endpoint-no-deadlines"
        )
        assert "deadlines" not in bundle.accessed_sources
        assert len(bundle.deadlines) == 0

        context = bundle.to_context_string()
        assert "Midterm Exam" not in context
        assert "Cloud Infrastructure" not in context
        # Other enabled sources should still be present
        assert "timetable" in bundle.accessed_sources
        assert "Distributed Systems Lecture" in context

        # Re-enable deadlines for other tests
        perm.enabled = True
        await session.commit()
