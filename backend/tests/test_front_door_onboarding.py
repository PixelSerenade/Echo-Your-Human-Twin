import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_auth_and_onboarding_full_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Signup with weak password fails
        resp = await ac.post("/api/auth/signup", json={
            "name": "Jordan Lee",
            "email": "jordan.weak@test.com",
            "password": "short"
        })
        assert resp.status_code == 400
        assert "at least 8 characters" in resp.json()["detail"]

        # 2. Signup successfully
        import uuid
        unique_email = f"jordan.{uuid.uuid4()}@humantwin.ai"
        signup_resp = await ac.post("/api/auth/signup", json={
            "name": "Jordan Lee",
            "email": unique_email,
            "password": "SecurePassword123!"
        })
        assert signup_resp.status_code == 200
        user_data = signup_resp.json()
        user_id = user_data["user_id"]
        assert user_data["name"] == "Jordan Lee"
        assert user_data["onboarding_completed"] is False
        assert user_data["onboarding_step"] == "persona"
        assert "session_user_id" in signup_resp.cookies

        persona_resp = await ac.post("/api/onboarding/step", json={"user_id": user_id, "step": "persona", "persona": "student"}, cookies=signup_resp.cookies)
        assert persona_resp.status_code == 200
        assert persona_resp.json()["current_step"] == "tags"

        # 3. Step 1: Tags (< 5 tags fails)
        fail_tags = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "tags",
                "tags": [
                    {"twin_type": "rational", "tag_name": "plans ahead"},
                    {"twin_type": "rational", "tag_name": "deadline-driven"}
                ]
            },
            cookies=signup_resp.cookies
        )
        assert fail_tags.status_code == 400

        # 4. Step 1: Tags calibration (5 Rational, 3 Emotional, 2 Ambitious)
        tags_payload = [
            {"twin_type": "rational", "tag_name": "plans ahead"},
            {"twin_type": "rational", "tag_name": "deadline-driven"},
            {"twin_type": "rational", "tag_name": "loves lists"},
            {"twin_type": "rational", "tag_name": "organized"},
            {"twin_type": "rational", "tag_name": "likes facts"},
            {"twin_type": "emotional", "tag_name": "needs balance"},
            {"twin_type": "emotional", "tag_name": "values peace of mind"},
            {"twin_type": "emotional", "tag_name": "needs breaks"},
            {"twin_type": "ambitious", "tag_name": "dreams big"},
            {"twin_type": "ambitious", "tag_name": "career-focused"},
        ]
        step1_resp = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "tags",
                "tags": tags_payload
            },
            cookies=signup_resp.cookies
        )
        assert step1_resp.status_code == 200
        step1_data = step1_resp.json()
        assert step1_data["current_step"] == "reveal"
        assert step1_data["recommended_twin"] == "rational"
        assert step1_data["weights"]["rational"] == 0.50
        assert step1_data["weights"]["emotional"] == 0.30
        assert step1_data["weights"]["ambitious"] == 0.20

        # 5. Step 2: Meet Echo & Style Override (User picks Ambitious instead of recommended Rational)
        step2_resp = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "reveal",
                "primary_twin": "ambitious"
            },
            cookies=signup_resp.cookies
        )
        assert step2_resp.status_code == 200
        step2_data = step2_resp.json()
        assert step2_data["current_step"] == "name"
        assert step2_data["primary_twin"] == "ambitious"

        # 6. Step 3: Name your Echo
        step3_resp = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "name",
                "twin_name": "Aether"
            },
            cookies=signup_resp.cookies
        )
        assert step3_resp.status_code == 200
        step3_data = step3_resp.json()
        assert step3_data["current_step"] == "permissions"
        assert step3_data["twin_name"] == "Aether"

        # 7. Step 4: Permissions (mood_tone is False by default)
        step4_resp = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "permissions",
                "permissions": {
                    "schedule_commitments": True,
                    "deadlines_key_dates": True,
                    "focus_work_patterns": True,
                    "routines_preferences": True,
                    "goals": True,
                    "decision_history": True,
                    "mood_tone": False
                }
            },
            cookies=signup_resp.cookies
        )
        assert step4_resp.status_code == 200
        step4_data = step4_resp.json()
        assert step4_data["current_step"] == "seed"

        seed_resp = await ac.post("/api/onboarding/step", json={"user_id": user_id, "step": "seed", "goals": ["Build a consistent routine"]}, cookies=signup_resp.cookies)
        assert seed_resp.status_code == 200
        assert seed_resp.json()["current_step"] == "finish"

        # 8. Finish celebration & finalize
        step5_resp = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "finish"
            },
            cookies=signup_resp.cookies
        )
        assert step5_resp.status_code == 200
        step5_data = step5_resp.json()
        assert step5_data["current_step"] == "completed"
        assert step5_data["onboarding_completed"] is True
        assert step5_data["primary_twin"] == "ambitious"
        assert step5_data["twin_name"] == "Aether"

        # 9. GET /api/auth/me returns updated session
        me_resp = await ac.get("/api/auth/me", cookies=signup_resp.cookies)
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["name"] == "Jordan Lee"
        assert me_data["twin_name"] == "Aether"
        assert me_data["onboarding_completed"] is True
        assert me_data["primary_twin"] == "ambitious"

@pytest.mark.asyncio
async def test_tie_breaker_logic():
    import uuid
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"tie.breaker.{uuid.uuid4()}@humantwin.ai"
        signup_resp = await ac.post("/api/auth/signup", json={
            "name": "Tie Tester",
            "email": email,
            "password": "Password123!"
        })
        assert signup_resp.status_code == 200
        user_id = signup_resp.json()["user_id"]

        # Equal Rational and Emotional tags (3 rational, 3 emotional, 1 ambitious)
        tied_tags = [
            {"twin_type": "rational", "tag_name": "plans ahead"},
            {"twin_type": "rational", "tag_name": "deadline-driven"},
            {"twin_type": "rational", "tag_name": "likes facts"},
            {"twin_type": "emotional", "tag_name": "needs balance"},
            {"twin_type": "emotional", "tag_name": "values peace of mind"},
            {"twin_type": "emotional", "tag_name": "needs breaks"},
            {"twin_type": "ambitious", "tag_name": "dreams big"},
        ]

        # Call without tie breaker choice -> flags tie
        resp_tied = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "tags",
                "tags": tied_tags
            }
        )
        assert resp_tied.status_code == 200
        data_tied = resp_tied.json()
        assert data_tied["tie_needed"] is True
        assert "rational" in data_tied["tied_twins"]
        assert "emotional" in data_tied["tied_twins"]

        # Resolve tie with tie_breaker_choice
        resp_resolved = await ac.post(
            "/api/onboarding/step",
            json={
                "user_id": user_id,
                "step": "tags",
                "tags": tied_tags,
                "tie_breaker_choice": "emotional"
            }
        )
        assert resp_resolved.status_code == 200
        data_resolved = resp_resolved.json()
        assert data_resolved["tie_needed"] is False
        assert data_resolved["recommended_twin"] == "emotional"
        assert data_resolved["current_step"] == "reveal"

@pytest.mark.asyncio
async def test_auth_rate_limiting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Rapid failed logins
        for _ in range(5):
            r = await ac.post("/api/auth/login", json={
                "email": "hacker@test.com",
                "password": "wrongpassword"
            })
            assert r.status_code == 401

        # 6th attempt should be rate limited (429)
        r6 = await ac.post("/api/auth/login", json={
            "email": "hacker@test.com",
            "password": "wrongpassword"
        })
        assert r6.status_code == 429
        assert "Too many failed login attempts" in r6.json()["detail"]
