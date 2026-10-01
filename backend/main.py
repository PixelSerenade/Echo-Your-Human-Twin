import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from backend.config import settings
from backend.database import engine, Base
from backend.routers import (
    profile_router, permissions_router, ask_router, audit_router,
    simulate_router, feedback_router, knowledge_router, debate_router,
    auth_router, attachment_router
)
from backend.routers import push_router
from backend.services.push_notifications import reminder_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables and legacy identity columns exist before ORM queries run.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "twin_name_customized BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        # Equivalent additive migration: legacy users retain their records and
        # receive the student persona unless they choose another one.
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS persona VARCHAR(40) NOT NULL DEFAULT 'student'"
        ))
        await conn.execute(text(
            "ALTER TABLE timetable ADD COLUMN IF NOT EXISTS specific_date TIMESTAMP NULL"
        ))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0"))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS next_step TEXT NULL"))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS milestones JSONB NOT NULL DEFAULT '[]'::jsonb"))
        # Earlier builds created this field as TEXT/JSON and could store the
        # serialized checklist as a string. Normalize it to JSONB so API reads
        # return an array of milestone objects for the Goals UI.
        await conn.execute(text("ALTER TABLE goals ALTER COLUMN milestones DROP DEFAULT"))
        await conn.execute(text("""
            ALTER TABLE goals
            ALTER COLUMN milestones TYPE JSONB
            USING CASE
                WHEN milestones IS NULL OR btrim(milestones::text) = '' THEN '[]'::jsonb
                WHEN jsonb_typeof(milestones::text::jsonb) = 'array' THEN milestones::text::jsonb
                ELSE '[]'::jsonb
            END
        """))
        await conn.execute(text("ALTER TABLE goals ALTER COLUMN milestones SET DEFAULT '[]'::jsonb"))
        await conn.execute(text("""
            UPDATE users
            SET twin_name = 'Echo'
            WHERE trim(COALESCE(twin_name, '')) = ''
               OR (NOT COALESCE(twin_name_customized, FALSE)
                   AND lower(trim(twin_name)) = lower(trim(name)))
        """))
    print("HumanTwin AI backend started with database initialized.")
    stop_push_scheduler = asyncio.Event()
    push_scheduler_task = asyncio.create_task(reminder_scheduler(stop_push_scheduler))
    try:
        yield
    finally:
        stop_push_scheduler.set()
        await push_scheduler_task
    await engine.dispose()
    print("HumanTwin AI backend shut down.")

app = FastAPI(
    title="HumanTwin AI API",
    description="Intelligent Digital Twin Hackathon Prototype",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration supporting cookies
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def reject_declared_oversize_uploads(request: Request, call_next):
    """Framework-level guard; endpoints also count streamed bytes."""
    if request.url.path.rstrip("/") in {"/api/attachments", "/api/transcribe"}:
        declared = request.headers.get("content-length")
        if declared:
            try:
                if int(declared) > settings.MAX_UPLOAD_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Only files up to 5 MB are allowed."},
                    )
            except ValueError:
                pass
    return await call_next(request)

# Include Routers
app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(permissions_router.router)
app.include_router(ask_router.router)
app.include_router(audit_router.router)
app.include_router(simulate_router.router)
app.include_router(feedback_router.router)
app.include_router(knowledge_router.router)
app.include_router(debate_router.router)
app.include_router(attachment_router.router)
app.include_router(push_router.router)

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "app": "HumanTwin AI",
        "demo_mode": settings.DEMO_MODE,
        "database": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
