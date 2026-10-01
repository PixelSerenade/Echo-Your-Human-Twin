import pytest
import pytest_asyncio
import os
import sys
from httpx import AsyncClient, ASGITransport

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.main import app
from backend.models import Goal, User, Permission
from backend.database import AsyncSessionLocal
from backend.scripts.generate_data import init_models, seed_demo_persona, USER_ID

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    await init_models()
    await seed_demo_persona()

@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["app"] == "HumanTwin AI"

@pytest.mark.asyncio
async def test_goal_milestone_checkboxes_update_progress_and_can_be_undone():
    async with AsyncSessionLocal() as db:
        goal = Goal(user_id=USER_ID, title="Progress checkbox regression", status="active", milestones=[
            {"title": "First step", "completed": False},
            {"title": "Second step", "completed": False},
        ])
        db.add(goal)
        await db.commit()
        await db.refresh(goal)
        goal_id = goal.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(f"/api/goals/{goal_id}?user_id={USER_ID}", json={"milestones": [
            {"title": "First step", "completed": True},
            {"title": "Second step", "completed": False},
        ]})
        assert response.status_code == 200, response.text
        assert response.json()["progress"] == 50
        assert response.json()["status"] == "active"

        response = await ac.put(f"/api/goals/{goal_id}?user_id={USER_ID}", json={"milestones": [
            {"title": "First step", "completed": True},
            {"title": "Second step", "completed": True},
        ]})
        assert response.status_code == 200
        assert response.json()["progress"] == 100
        assert response.json()["status"] == "completed"

        response = await ac.put(f"/api/goals/{goal_id}?user_id={USER_ID}", json={"milestones": [
            {"title": "First step", "completed": True},
            {"title": "Second step", "completed": False},
        ]})
        assert response.status_code == 200
        assert response.json()["progress"] == 50
        assert response.json()["status"] == "active"

@pytest.mark.asyncio
async def test_goal_delete_is_owner_scoped():
    other_user_id = "goal-delete-other-user"
    async with AsyncSessionLocal() as db:
        db.add(User(id=other_user_id, name="Other User", email="goal-delete-other-user@example.test", demo_mode=True))
        db.add(Permission(user_id=other_user_id, source="goals", enabled=True))
        goal = Goal(user_id=USER_ID, title="Delete goal regression", status="active")
        db.add(goal)
        await db.commit()
        await db.refresh(goal)
        goal_id = goal.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        wrong_owner = await ac.delete(f"/api/goals/{goal_id}?user_id={other_user_id}")
        assert wrong_owner.status_code == 404

        response = await ac.delete(f"/api/goals/{goal_id}?user_id={USER_ID}")
        assert response.status_code == 200
        assert response.json() == {"id": goal_id, "deleted": True}

        missing = await ac.delete(f"/api/goals/{goal_id}?user_id={USER_ID}")
        assert missing.status_code == 404

    async with AsyncSessionLocal() as db:
        await db.delete(await db.get(User, other_user_id))
        await db.commit()

@pytest.mark.asyncio
async def test_api_get_permissions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/permissions?user_id={USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == USER_ID
        assert "timetable" in data["permissions"]
        assert "deadlines" in data["permissions"]
        assert data["permissions"]["deadlines"] is True
        assert data["permissions"]["mood_tone"] is False

@pytest.mark.asyncio
async def test_api_update_permissions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Disable deadlines
        payload = {
            "user_id": USER_ID,
            "permissions": {"deadlines": False}
        }
        put_res = await ac.put("/permissions", json=payload)
        assert put_res.status_code == 200
        data = put_res.json()
        assert data["permissions"]["deadlines"] is False

        # Verify through GET
        get_res = await ac.get(f"/permissions?user_id={USER_ID}")
        assert get_res.json()["permissions"]["deadlines"] is False

        # Restore
        await ac.put("/permissions", json={"user_id": USER_ID, "permissions": {"deadlines": True}})

@pytest.mark.asyncio
async def test_api_profile_onboarding():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test custom tags with Ambitious dominant: 3 Ambitious, 1 Rational, 1 Emotional
        payload = {
            "user_id": "test-ambitious-user",
            "name": "Jordan Vance",
            "email": "jordan@humantwin.ai",
            "demo_mode": True,
            "tags": [
                {"twin_type": "ambitious", "tag_name": "career-focused"},
                {"twin_type": "ambitious", "tag_name": "takes opportunities"},
                {"twin_type": "ambitious", "tag_name": "goal-driven"},
                {"twin_type": "rational", "tag_name": "plans ahead"},
                {"twin_type": "emotional", "tag_name": "values peace of mind"}
            ]
        }
        res = await ac.post("/profile", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["primary_twin"] == "ambitious"
        assert data["weights"]["primary_twin"] == "ambitious"
        # 3/5 = 0.60 Ambitious, 1/5 = 0.20 Rational, 1/5 = 0.20 Emotional
        assert round(data["weights"]["ambitious"], 2) == 0.60
        assert round(data["weights"]["rational"], 2) == 0.20
        assert round(data["weights"]["emotional"], 2) == 0.20
