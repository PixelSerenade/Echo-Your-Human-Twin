import os
import sys
import datetime
import random
import asyncio
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine, Base, AsyncSessionLocal
from sqlalchemy import text
from backend.models import (
    User, ProfileTag, TwinWeight, TwinWeightLog, Timetable, Deadline,
    StudyLog, Preference, DecisionHistory, Permission, SimulatorModifier
)

USER_ID = "demo-alex-rivers"

# Seed for reproducibility
random.seed(42)
np.random.seed(42)

async def init_models():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Keep the test/demo initializer aligned with the application's additive migration.
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS persona VARCHAR(40) NOT NULL DEFAULT 'student'"))
        await conn.execute(text("ALTER TABLE timetable ADD COLUMN IF NOT EXISTS specific_date TIMESTAMP NULL"))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0"))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS next_step TEXT NULL"))
        await conn.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS milestones JSONB NOT NULL DEFAULT '[]'::jsonb"))
    print("Database tables created successfully.")

def generate_500_ml_tasks(num_rows=600):
    """
    Generate synthetic, persona-neutral task and key-date records for scikit-learn.
    Planted patterns with noise:
    - Assignments take ~1.5x estimated hours, exams take ~1.25x.
    - Higher focus lowers the overrun multiplier.
    - Shorter deadline runway + high concurrent deadlines severely drops on-time probability.
    """
    rows = []
    task_categories = ["project delivery", "client work", "personal milestone", "administrative task", "assessment", "care commitment"]

    for i in range(num_rows):
        is_key_date = 1 if random.random() < 0.25 else 0
        task_category = random.choice(task_categories)
        estimated_hours = round(random.uniform(4.0, 32.0), 1)
        days_until_key_date = round(random.uniform(1.0, 20.0), 1)
        priority_numeric = random.choice([1, 2, 3])  # 1=low, 2=medium, 3=high
        focus_rating_avg = round(random.uniform(4.0, 9.8), 2)
        workload_density = random.randint(1, 5)
        late_day_work_ratio = round(random.uniform(0.1, 0.9), 2)

        # Pattern: Assignments take ~1.5x with noise, Exams ~1.25x
        base_multiplier = 1.25 if is_key_date else 1.52
        # Night focus slightly reduces overruns
        focus_efficiency = 1.15 - (0.03 * focus_rating_avg)
        noise = np.random.normal(0, 1.2)
        actual_effort = max(2.0, round(estimated_hours * base_multiplier * focus_efficiency + noise, 1))

        # On-time probability calculation based on realistic runway
        available_capacity = days_until_key_date * 4.2
        headroom = available_capacity - actual_effort
        congestion_penalty = (workload_density - 1) * 2.5
        late_work_bonus = (late_day_work_ratio - 0.5) * 2.0

        score = headroom - congestion_penalty + late_work_bonus + np.random.normal(0, 2.5)
        prob = 1.0 / (1.0 + np.exp(-score / 3.0))
        completed_on_time = 1 if prob >= 0.5 else 0

        rows.append({
            "task_id": i + 1,
            "task_category": task_category,
            "is_assessment_key_date": is_key_date,
            "estimated_effort": estimated_hours,
            "days_until_key_date": days_until_key_date,
            "priority_numeric": priority_numeric,
            "focus_rating_avg": focus_rating_avg,
            "workload_density": workload_density,
            "late_day_work_ratio": late_day_work_ratio,
            "actual_effort": actual_effort,
            "completed_on_time": completed_on_time
        })

    df = pd.DataFrame(rows)
    os.makedirs("backend/data", exist_ok=True)
    csv_path = "backend/data/task_history_500.csv"
    df.to_csv(csv_path, index=False)
    print(f"Generated {len(df)} ML task history rows saved to {csv_path}")
    return df

async def seed_demo_persona():
    """Seed persona Alex Rivers with 4-6 weeks of history and planted conflicts."""
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        existing_user = await session.get(User, USER_ID)
        if existing_user:
            print("Demo user already exists. Cleaning up existing records...")
            await session.delete(existing_user)
            await session.commit()

        # 1. User
        user = User(
            id=USER_ID,
            name="Alex Rivers",
            email="alex.rivers@humantwin.ai",
            password_hash=None,
            twin_name="Echo",
            onboarding_completed=True,
            onboarding_step="completed",
            demo_mode=True,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=40)
        )
        session.add(user)

        # 2. Profile Tags (Rational dominant: 4 Rational, 2 Emotional, 2 Ambitious)
        tags = [
            # Rational (4 tags)
            ProfileTag(user_id=USER_ID, twin_type="rational", tag_name="plans ahead"),
            ProfileTag(user_id=USER_ID, twin_type="rational", tag_name="deadline-driven"),
            ProfileTag(user_id=USER_ID, twin_type="rational", tag_name="risk-averse"),
            ProfileTag(user_id=USER_ID, twin_type="rational", tag_name="optimizes schedule"),
            # Emotional (2 tags)
            ProfileTag(user_id=USER_ID, twin_type="emotional", tag_name="avoids burnout"),
            ProfileTag(user_id=USER_ID, twin_type="emotional", tag_name="values peace of mind"),
            # Ambitious (2 tags)
            ProfileTag(user_id=USER_ID, twin_type="ambitious", tag_name="career-focused"),
            ProfileTag(user_id=USER_ID, twin_type="ambitious", tag_name="takes opportunities")
        ]
        session.add_all(tags)

        # 3. Initial Twin Weights (50% Rational, 25% Emotional, 25% Ambitious)
        weights = TwinWeight(
            user_id=USER_ID,
            rational=0.50,
            emotional=0.25,
            ambitious=0.25,
            primary_twin="rational",
            consecutive_lead_twin=None,
            consecutive_lead_count=0
        )
        session.add(weights)

        # Initial weight log
        weight_log = TwinWeightLog(
            user_id=USER_ID,
            rational=0.50,
            emotional=0.25,
            ambitious=0.25,
            primary_twin="rational",
            delta_twin="rational",
            step_size=0.0,
            reason="Onboarding tag profile distribution (4 Rational, 2 Emotional, 2 Ambitious)"
        )
        session.add(weight_log)

        # 4. Default Permissions (mood and tone inference is opt-in)
        permissions = [
            Permission(user_id=USER_ID, source="timetable", enabled=True),
            Permission(user_id=USER_ID, source="deadlines", enabled=True),
            Permission(user_id=USER_ID, source="study_history", enabled=True),
            Permission(user_id=USER_ID, source="preferences", enabled=True),
            Permission(user_id=USER_ID, source="decision_history", enabled=True),
            Permission(user_id=USER_ID, source="mood_tone", enabled=False),
        ]
        session.add_all(permissions)

        # 5. Timetable (Weekly recurring classes + badminton)
        timetable_entries = [
            Timetable(user_id=USER_ID, day_of_week="Monday", start_time="09:00", end_time="11:00", activity_name="Distributed Systems Lecture", location="Hall A", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Monday", start_time="14:00", end_time="16:00", activity_name="Database Systems Lab", location="Lab 302", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Tuesday", start_time="10:00", end_time="12:00", activity_name="Cloud Computing Seminar", location="Online", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Tuesday", start_time="17:00", end_time="18:30", activity_name="Badminton Session", location="Sports Center", is_mandatory=False),
            Timetable(user_id=USER_ID, day_of_week="Wednesday", start_time="09:00", end_time="11:00", activity_name="Algorithms Tutorial", location="Room 105", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Wednesday", start_time="13:00", end_time="15:00", activity_name="Software Engineering Studio", location="Engineering Hall", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Thursday", start_time="11:00", end_time="13:00", activity_name="Machine Learning Lecture", location="Hall B", is_mandatory=True),
            Timetable(user_id=USER_ID, day_of_week="Thursday", start_time="18:00", end_time="19:30", activity_name="Badminton Session", location="Sports Center", is_mandatory=False),
            Timetable(user_id=USER_ID, day_of_week="Friday", start_time="10:00", end_time="12:00", activity_name="Senior Capstone Meeting", location="Lab 401", is_mandatory=True),
        ]
        session.add_all(timetable_entries)

        # 6. Deadlines with PLANTED CONFLICT
        # Exam overlaps with assignment deadline so spending 2 days on exam causes major assignment collision!
        now = datetime.datetime.utcnow()
        deadlines = [
            # PLANTED CONFLICT: Both due within 48h window
            Deadline(
                user_id=USER_ID,
                title="Distributed Systems Midterm Exam",
                course_or_project="CS410 Distributed Systems",
                due_date=now + datetime.timedelta(days=2, hours=4),  # In 2 days morning
                estimated_hours=14.0,
                completed=False,
                priority="high",
                is_exam=True
            ),
            Deadline(
                user_id=USER_ID,
                title="Cloud Infrastructure Deployment Project",
                course_or_project="CS420 Cloud Computing",
                due_date=now + datetime.timedelta(days=2, hours=14),  # In 2 days night
                estimated_hours=12.0,
                completed=False,
                priority="high",
                is_exam=False
            ),
            Deadline(
                user_id=USER_ID,
                title="Database Indexing Milestone 2",
                course_or_project="CS330 Database Systems",
                due_date=now + datetime.timedelta(days=7),
                estimated_hours=9.0,
                completed=False,
                priority="medium",
                is_exam=False
            ),
            Deadline(
                user_id=USER_ID,
                title="Algorithm Complexity Analysis Assignment",
                course_or_project="CS310 Algorithms",
                due_date=now - datetime.timedelta(days=5),
                estimated_hours=8.0,
                actual_hours=12.5,  # ~1.56x overrun pattern
                completed=True,
                priority="medium",
                is_exam=False
            ),
            Deadline(
                user_id=USER_ID,
                title="Software Requirements Specification Document",
                course_or_project="CS350 Software Engineering",
                due_date=now - datetime.timedelta(days=12),
                estimated_hours=6.0,
                actual_hours=9.2,   # ~1.53x overrun pattern
                completed=True,
                priority="low",
                is_exam=False
            )
        ]
        session.add_all(deadlines)

        # 7. Study Logs (5 weeks of logs = 35 days, 2 sessions/day)
        study_logs = []
        for d in range(35, 0, -1):
            log_date = now - datetime.timedelta(days=d)
            # Session 1: Afternoon session
            study_logs.append(StudyLog(
                user_id=USER_ID,
                timestamp=log_date.replace(hour=14, minute=30),
                subject=random.choice(["Distributed Systems", "Cloud Computing", "Database Systems"]),
                hours_spent=round(random.uniform(1.5, 3.0), 1),
                focus_rating=random.randint(5, 7),  # Lower focus in afternoon
                time_of_day="afternoon",
                energy_before=round(random.uniform(65, 80), 1),
                energy_after=round(random.uniform(45, 60), 1)
            ))
            # Session 2: Night session (Planted Pattern: higher focus!)
            study_logs.append(StudyLog(
                user_id=USER_ID,
                timestamp=log_date.replace(hour=21, minute=0),
                subject=random.choice(["Distributed Systems", "Algorithms", "Machine Learning"]),
                hours_spent=round(random.uniform(2.0, 4.0), 1),
                focus_rating=random.randint(8, 10),  # Planted pattern: Night sessions have higher focus!
                time_of_day="night",
                energy_before=round(random.uniform(60, 75), 1),
                energy_after=round(random.uniform(35, 50), 1)
            ))
        session.add_all(study_logs)

        # 8. Preferences
        preferences = [
            Preference(user_id=USER_ID, key="Peak Focus Time", value="Late evening & night (20:00 - 01:00)", category="habit"),
            Preference(user_id=USER_ID, key="Physical Activity", value="Badminton on Tuesdays & Thursdays", category="rest"),
            Preference(user_id=USER_ID, key="Target Sleep", value="7.5 hours minimum to prevent mental fatigue", category="rest"),
            Preference(user_id=USER_ID, key="Long-term Career Objective", value="Lead Cloud & Distributed Systems Architect", category="work"),
            Preference(user_id=USER_ID, key="Exam Preparation Style", value="Active recall & practice problems in 2-hour blocks", category="work")
        ]
        session.add_all(preferences)

        # 9. Short Decision History (Leaning toward Rational)
        decisions = [
            DecisionHistory(
                user_id=USER_ID,
                question="Should I attend Friday night campus party or complete the Database checkpoint?",
                options=[
                    {"text": "Stay home and finish the checkpoint to stay on track", "aligned_twin": "rational"},
                    {"text": "Go to the party and de-stress with friends", "aligned_twin": "emotional"},
                    {"text": "Quick 1-hour party visit then work on project", "aligned_twin": "ambitious"}
                ],
                twin_recommended="rational",
                option_chosen="Stay home and finish the checkpoint to stay on track",
                aligned_twin="rational",
                followed_recommendation=True,
                timestamp=now - datetime.timedelta(days=14),
                feedback_understood=True,
                feedback_comment="Spot on, staying behind saved me from weekend rush."
            ),
            DecisionHistory(
                user_id=USER_ID,
                question="Exam prep schedule: Cram in 2 massive days or space over 5 days?",
                options=[
                    {"text": "Space review into 2-hour daily slots starting immediately", "aligned_twin": "rational"},
                    {"text": "Rest now and study when feeling inspired", "aligned_twin": "emotional"},
                    {"text": "Study 8 hours daily and build extra sample projects", "aligned_twin": "ambitious"}
                ],
                twin_recommended="rational",
                option_chosen="Space review into 2-hour daily slots starting immediately",
                aligned_twin="rational",
                followed_recommendation=True,
                timestamp=now - datetime.timedelta(days=8),
                feedback_understood=True,
                feedback_comment="Good pacing kept my stress manageable."
            ),
            DecisionHistory(
                user_id=USER_ID,
                question="Should I accept an invitation to join an extra 3-day hackathon this weekend?",
                options=[
                    {"text": "Decline to protect upcoming assignment milestones", "aligned_twin": "rational"},
                    {"text": "Decline to get full rest and recharge", "aligned_twin": "emotional"},
                    {"text": "Accept to network and build a portfolio project", "aligned_twin": "ambitious"}
                ],
                twin_recommended="rational",
                option_chosen="Decline to protect upcoming assignment milestones",
                aligned_twin="rational",
                followed_recommendation=True,
                timestamp=now - datetime.timedelta(days=3),
                feedback_understood=True,
                feedback_comment="Agreed with Rational twin advice."
            )
        ]
        session.add_all(decisions)

        # 10. Simulator Modifiers (Initial learned pattern)
        modifiers = [
            SimulatorModifier(
                user_id=USER_ID,
                activity_name="badminton",
                metric_affected="focus",
                delta_value=1.5,
                description="User verified: badminton improves next-session focus by +1.5 points"
            )
        ]
        session.add_all(modifiers)

        await session.commit()
        print(f"Successfully seeded demo persona '{user.name}' ({USER_ID}) with full dataset.")

async def main():
    print("--- Starting HumanTwin AI Data Generation ---")
    await init_models()
    generate_500_ml_tasks(num_rows=600)
    await seed_demo_persona()
    print("--- Data Generation Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
