"""Create repeatable synthetic work and freelance demo accounts in PostgreSQL."""
import asyncio
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import AsyncSessionLocal
from backend.models import User, Permission, Timetable, Deadline, StudyLog, Goal
from backend.memory_registry import defaults_for

DEMOS = [
    {"id": "demo-working-professional", "name": "Morgan Patel", "email": "morgan.professional@humantwin.demo", "persona": "working_professional", "schedule": ["Team planning", "Focus block"], "dates": ["Quarterly report", "Client review"], "goal": "Protect two focused work blocks each week"},
    {"id": "demo-freelancer-founder", "name": "Taylor Brooks", "email": "taylor.founder@humantwin.demo", "persona": "freelancer_founder", "schedule": ["Client delivery", "Product work"], "dates": ["Design handoff", "Launch milestone"], "goal": "Ship the next product milestone"},
]

async def seed():
    async with AsyncSessionLocal() as db:
        for demo in DEMOS:
            if await db.get(User, demo["id"]):
                continue
            user = User(id=demo["id"], name=demo["name"], email=demo["email"], persona=demo["persona"], twin_name="Echo", onboarding_completed=True, onboarding_step="completed", demo_mode=True)
            db.add(user)
            await db.flush()
            db.add_all([Permission(user_id=user.id, source=category, enabled=enabled) for category, enabled in defaults_for(user.persona).items()])
            db.add_all([
                Timetable(user_id=user.id, day_of_week="Monday", start_time="09:00", end_time="10:00", activity_name=activity, location="Remote", is_mandatory=True)
                for activity in demo["schedule"]
            ])
            db.add_all([
                Deadline(user_id=user.id, title=title, course_or_project="Work", due_date=datetime.datetime.utcnow() + datetime.timedelta(days=days), estimated_hours=4.0, priority="medium", is_exam=False)
                for days, title in enumerate(demo["dates"], start=5)
            ])
            db.add(StudyLog(user_id=user.id, timestamp=datetime.datetime.utcnow(), subject="Focused work", hours_spent=1.5, focus_rating=8, time_of_day="morning", energy_before=75, energy_after=65))
            db.add(Goal(user_id=user.id, title=demo["goal"]))
        await db.commit()
    print("Persona demo accounts are ready.")

if __name__ == "__main__":
    asyncio.run(seed())
