import pytest
import pytest_asyncio
import datetime
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import AsyncSessionLocal
from backend.models import User, FocusBlock, CalendarNegotiation, Timetable
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID
from backend.services.calendar_proxy import evaluate_calendar_proposal


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    await init_models()
    await seed_demo_persona()


@pytest.mark.asyncio
async def test_proxy_focus_block_conflict_detection():
    async with AsyncSessionLocal() as db_session:
        # Create a protected deep work focus block on Wednesday from 09:00 to 12:00
        fb = FocusBlock(
            user_id=USER_ID,
            title="Deep Work Thesis",
            day_of_week="Wednesday",
            start_time="09:00",
            end_time="12:00",
            is_protected=True,
            created_at=datetime.datetime.utcnow()
        )
        db_session.add(fb)
        await db_session.commit()

        # Evaluate an incoming proposal landing on Wednesday at 10:00 AM (overlaps with focus block)
        proposed_time = datetime.datetime(2026, 10, 7, 10, 0, 0)  # A Wednesday
        result = await evaluate_calendar_proposal(
            user_id=USER_ID,
            title="Sync Meeting",
            requested_by="Prof. Miller",
            duration_minutes=60,
            proposed_start_time=proposed_time,
            priority="medium",
            db=db_session
        )

        assert result["conflict_detected"] is True
        assert "Deep Work Thesis" in result["conflict_reason"]
        assert result["status"] == "countered"
        assert result["suggested_counter_time"] is not None
        assert "Twin Proxy" in result["negotiation_message"]


@pytest.mark.asyncio
async def test_proxy_negotiation_accept_action():
    proposed_time = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    async with AsyncSessionLocal() as db_session:
        neg = CalendarNegotiation(
            user_id=USER_ID,
            title="Client Strategy Review",
            requested_by="Alice",
            duration_minutes=45,
            proposed_start_time=proposed_time,
            priority="high",
            status="pending",
            conflict_detected=False,
            negotiation_message="Meeting confirmed.",
            created_at=datetime.datetime.utcnow()
        )
        db_session.add(neg)
        await db_session.commit()
        await db_session.refresh(neg)
        neg_id = neg.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/proxy/negotiations/{neg_id}/action",
            json={"user_id": USER_ID, "action": "accept"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

    async with AsyncSessionLocal() as db_session:
        stmt = select(Timetable).where(Timetable.user_id == USER_ID, Timetable.activity_name.contains("Client Strategy Review"))
        res = await db_session.execute(stmt)
        entry = res.scalar_one_or_none()
        assert entry is not None


@pytest.mark.asyncio
async def test_focus_block_crud_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create focus block
        resp = await ac.post(
            "/api/proxy/focus-blocks",
            json={
                "user_id": USER_ID,
                "title": "Morning Coding Block",
                "day_of_week": "Friday",
                "start_time": "08:00",
                "end_time": "11:00",
                "is_protected": True
            }
        )
        assert resp.status_code == 200
        block_id = resp.json()["id"]

        # 2. List focus blocks
        resp = await ac.get(f"/api/proxy/focus-blocks?user_id={USER_ID}")
        assert resp.status_code == 200
        blocks = resp.json()
        assert any(b["id"] == block_id for b in blocks)

        # 3. Delete focus block
        resp = await ac.delete(f"/api/proxy/focus-blocks/{block_id}?user_id={USER_ID}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
