import time
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from backend.config import settings
from backend.main import app
from backend.services.session_auth import issue_session, read_session


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "PRODUCTION", True)
    monkeypatch.setattr(settings, "SESSION_SECRET", "test-only-signing-secret-that-is-long-enough")


def test_signed_sessions_reject_tampering_and_expiration(production, monkeypatch):
    issued_at = time.time()
    token = issue_session("account-one")
    assert read_session(token) == "account-one"
    assert read_session("account-one") is None
    assert read_session(token + "tampered") is None
    monkeypatch.setattr(time, "time", lambda: issued_at + 15 * 86400)
    assert read_session(token) is None


@pytest.mark.asyncio
async def test_public_deployment_requires_session_and_owns_account_ids(production):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/profile/other", headers={"X-User-Id": "other"})).status_code == 401
        client.cookies.set("session_user_id", issue_session("account-one"))
        assert (await client.get("/profile/other")).status_code == 403
        assert (await client.get("/permissions?user_id=other")).status_code == 403
        assert (await client.get("/permissions")).status_code == 400
        assert (await client.post("/ask", json={"user_id": "other", "question": "hello"})).status_code == 403
        assert (await client.post("/ask", json={"question": "hello"})).status_code == 400
        assert (await client.post("/ask", content='{"user_id":"other","question":"hello"}')).status_code == 403


@pytest.mark.asyncio
async def test_production_signup_cookie_and_authenticated_onboarding(production):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.post("/api/auth/signup", json={
            "name": "Deployment test", "email": f"deploy-{uuid.uuid4()}@example.com", "password": "DeployTest!4829",
        })
        assert response.status_code == 200, response.text
        cookie = response.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie
        user_id = response.json()["user_id"]
        try:
            assert (await client.get("/api/auth/me")).json()["user_id"] == user_id
            assert (await client.get(f"/profile/{user_id}")).status_code == 200
            assert (await client.put("/permissions", json={"user_id": user_id, "permissions": {"goals": True}})).status_code == 200
            assert (await client.get(f"/permissions?user_id={user_id}")).status_code == 200
            assert (await client.get(f"/api/preferences/learned?user_id={user_id}")).status_code == 200
        finally:
            assert (await client.delete("/api/auth/account")).status_code == 200


def test_container_secrets_survive_restart(tmp_path, monkeypatch):
    from backend.deploy import configure_runtime
    for key in ("SESSION_SECRET", "VAPID_PRIVATE_KEY_PATH", "VAPID_PUBLIC_KEY", "UPLOAD_DIR"):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    configure_runtime()
    import os
    first = {key: os.environ[key] for key in ("SESSION_SECRET", "VAPID_PRIVATE_KEY_PATH", "VAPID_PUBLIC_KEY")}
    for key in first:
        monkeypatch.delenv(key)
    configure_runtime()
    assert first == {key: os.environ[key] for key in first}
