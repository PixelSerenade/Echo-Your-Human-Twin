import datetime
import json
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base


def normalize_json_list(value):
    """Return a list for native JSON values and legacy JSON-encoded strings."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return value if isinstance(value, list) else []


def normalize_goal_milestones(value):
    """Return a checklist array for both native JSONB and legacy encoded rows."""
    return [item for item in normalize_json_list(value) if isinstance(item, dict) and str(item.get("title", "")).strip()]

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, default="Alex Rivers")
    email = Column(String(120), unique=True, nullable=False, default="alex.rivers@humantwin.ai")
    demo_mode = Column(Boolean, default=True)
    password_hash = Column(String(255), nullable=True)
    twin_name = Column(String(50), default="Echo")
    twin_name_customized = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String(50), default="tags")  # 'tags', 'reveal', 'name', 'permissions', 'completed'
    persona = Column(String(40), nullable=False, default="student", server_default="student")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    tags = relationship("ProfileTag", back_populates="user", cascade="all, delete-orphan")
    weights = relationship("TwinWeight", back_populates="user", uselist=False, cascade="all, delete-orphan")
    weight_logs = relationship("TwinWeightLog", back_populates="user", cascade="all, delete-orphan")
    timetable_entries = relationship("Timetable", back_populates="user", cascade="all, delete-orphan")
    deadlines = relationship("Deadline", back_populates="user", cascade="all, delete-orphan")
    study_logs = relationship("StudyLog", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("Preference", back_populates="user", cascade="all, delete-orphan")
    decisions = relationship("DecisionHistory", back_populates="user", cascade="all, delete-orphan")
    preference_profile = relationship("PreferenceProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    modifiers = relationship("SimulatorModifier", back_populates="user", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="user", cascade="all, delete-orphan")
    goals_list = relationship("Goal", back_populates="user", cascade="all, delete-orphan")


class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
    target_date = Column(DateTime, nullable=True)
    progress = Column(Integer, nullable=False, default=0)
    next_step = Column(Text, nullable=True)
    milestones = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    user = relationship("User", back_populates="goals_list")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(80), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="attachments")


class ProfileTag(Base):
    __tablename__ = "profile_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    twin_type = Column(String(20), nullable=False)  # 'rational', 'emotional', 'ambitious'
    tag_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="tags")


class TwinWeight(Base):
    __tablename__ = "twin_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    rational = Column(Float, nullable=False, default=0.33)
    emotional = Column(Float, nullable=False, default=0.33)
    ambitious = Column(Float, nullable=False, default=0.34)
    primary_twin = Column(String(20), nullable=False, default="rational")  # 'rational', 'emotional', 'ambitious'
    consecutive_lead_twin = Column(String(20), nullable=True)
    consecutive_lead_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="weights")


class TwinWeightLog(Base):
    __tablename__ = "twin_weight_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    decision_id = Column(Integer, ForeignKey("decision_history.id", ondelete="SET NULL"), nullable=True)
    rational = Column(Float, nullable=False)
    emotional = Column(Float, nullable=False)
    ambitious = Column(Float, nullable=False)
    primary_twin = Column(String(20), nullable=False)
    delta_twin = Column(String(20), nullable=True)
    step_size = Column(Float, default=0.05)
    reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="weight_logs")


class Timetable(Base):
    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(20), nullable=False)  # 'Monday' - 'Sunday'
    specific_date = Column(DateTime, nullable=True)
    start_time = Column(String(10), nullable=False)   # 'HH:MM'
    end_time = Column(String(10), nullable=False)     # 'HH:MM'
    activity_name = Column(String(150), nullable=False)
    location = Column(String(100), default="Campus / Remote")
    is_mandatory = Column(Boolean, default=True)

    user = relationship("User", back_populates="timetable_entries")


class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    course_or_project = Column(String(150), nullable=False)
    due_date = Column(DateTime, nullable=False)
    estimated_hours = Column(Float, nullable=False)
    actual_hours = Column(Float, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default="high")  # 'high', 'medium', 'low'
    is_exam = Column(Boolean, default=False)

    user = relationship("User", back_populates="deadlines")


class StudyLog(Base):
    __tablename__ = "study_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    subject = Column(String(150), nullable=False)
    hours_spent = Column(Float, nullable=False)
    focus_rating = Column(Integer, nullable=False)  # 1 to 10
    time_of_day = Column(String(20), nullable=False)  # 'morning', 'afternoon', 'evening', 'night'
    energy_before = Column(Float, default=70.0)
    energy_after = Column(Float, default=50.0)

    user = relationship("User", back_populates="study_logs")


class Preference(Base):
    __tablename__ = "preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(String(255), nullable=False)
    category = Column(String(50), default="general")  # 'work', 'rest', 'habit'

    user = relationship("User", back_populates="preferences")


class MoneyEntry(Base):
    __tablename__ = "money_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    entry_type = Column(String(20), nullable=False, default="expense")
    entry_date = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


class DecisionHistory(Base):
    __tablename__ = "decision_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list of {text, aligned_twin, description}
    twin_recommended = Column(String(20), nullable=False)
    option_chosen = Column(Text, nullable=False)
    aligned_twin = Column(String(20), nullable=False)
    followed_recommendation = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    feedback_understood = Column(Boolean, nullable=True)
    feedback_comment = Column(Text, nullable=True)

    user = relationship("User", back_populates="decisions")


class PreferenceProfile(Base):
    __tablename__ = "preference_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    tendencies = Column(JSON, nullable=False, default=dict)
    confidence = Column(JSON, nullable=False, default=dict)
    source_counts = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    user = relationship("User", back_populates="preference_profile")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=False)  # Includes data sources plus opt-in 'mood_tone'
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="permissions")


class ConsentEntry(Base):
    __tablename__ = "consent_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    value = Column(Boolean, nullable=False)
    wording_version = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


class UserMemory(Base):
    """Concise user-scoped facts extracted from chat under an enabled category."""
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    fact = Column(Text, nullable=False)
    importance = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)  # 'ask', 'simulate', 'debate', 'read_knowledge'
    endpoint = Column(String(100), nullable=False)
    sources_accessed = Column(JSON, nullable=False)  # e.g. ["deadlines", "timetable"]
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")


class SimulatorModifier(Base):
    __tablename__ = "simulator_modifiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_name = Column(String(100), nullable=False)
    metric_affected = Column(String(50), nullable=False)  # 'energy', 'happiness', 'study', 'goals', 'free_time', 'focus'
    delta_value = Column(Float, nullable=False)
    description = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="modifiers")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(String(255), nullable=False)
    timezone = Column(String(80), nullable=False, default="UTC")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


class PushReminderDelivery(Base):
    __tablename__ = "push_reminder_deliveries"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_push_reminder_user_event"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key = Column(String(255), nullable=False)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")
