from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import datetime

# Profile & Onboarding
class ProfileTagItem(BaseModel):
    twin_type: str = Field(..., description="rational | emotional | ambitious")
    tag_name: str

class ProfileCreateRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    name: Optional[str] = "Alex Rivers"
    email: Optional[str] = "alex.rivers@humantwin.ai"
    demo_mode: Optional[bool] = True
    tags: List[ProfileTagItem]

class TwinWeightsOut(BaseModel):
    rational: float
    emotional: float
    ambitious: float
    primary_twin: str

class ProfileResponse(BaseModel):
    user_id: str
    name: str
    user_name: str
    twin_name: str
    twin_name_customized: bool = False
    primary_twin: str
    weights: TwinWeightsOut
    tags: List[ProfileTagItem]
    demo_mode: bool
    persona: str = "student"

# Permissions
class PermissionItem(BaseModel):
    source: str
    enabled: bool
    updated_at: Optional[datetime.datetime] = None

class PermissionsResponse(BaseModel):
    user_id: str
    permissions: Dict[str, bool]

class PermissionUpdateRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    permissions: Dict[str, bool]

# Audit Log
class AuditLogItem(BaseModel):
    id: int
    action: str
    endpoint: str
    sources_accessed: List[str]
    timestamp: datetime.datetime

# Permitted Data Bundle (internal and for twin-knowledge)
class TimetableItem(BaseModel):
    id: int
    day_of_week: str
    specific_date: Optional[datetime.datetime] = None
    start_time: str
    end_time: str
    activity_name: str
    location: str
    is_mandatory: bool

class DeadlineItem(BaseModel):
    id: int
    title: str
    course_or_project: str
    due_date: datetime.datetime
    estimated_hours: float
    actual_hours: Optional[float] = None
    completed: bool
    priority: str
    is_exam: bool

class StudyLogItem(BaseModel):
    id: int
    timestamp: datetime.datetime
    subject: str
    hours_spent: float
    focus_rating: int
    time_of_day: str
    energy_before: float
    energy_after: float

class PreferenceItem(BaseModel):
    id: int
    key: str
    value: str
    category: str

class DecisionHistoryItem(BaseModel):
    id: int
    question: str
    options: List[Any]
    twin_recommended: str
    option_chosen: str
    aligned_twin: str
    followed_recommendation: bool
    timestamp: datetime.datetime
    feedback_understood: Optional[bool] = None

class GoalItem(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    target_date: Optional[datetime.datetime] = None
    progress: int = 0
    next_step: Optional[str] = None
    milestones: List[Dict[str, Any]] = Field(default_factory=list)

class TwinKnowledgeResponse(BaseModel):
    user_id: str
    active_permissions: Dict[str, bool]
    timetable: Optional[List[TimetableItem]] = None
    deadlines: Optional[List[DeadlineItem]] = None
    study_history: Optional[List[StudyLogItem]] = None
    preferences: Optional[List[PreferenceItem]] = None
    spending_preferences: Optional[List[PreferenceItem]] = None
    money_entries: Optional[List[Dict[str, Any]]] = None
    decision_history: Optional[List[DecisionHistoryItem]] = None
    goals: Optional[List[GoalItem]] = None
    memories: List[Dict[str, Any]] = Field(default_factory=list)
    memory_categories: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

# Authentication & Onboarding
class SignUpRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=120)
    password: str = Field(...)

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    password: str = Field(...)

class UserSessionResponse(BaseModel):
    user_id: str
    name: str
    email: str
    twin_name: str
    twin_name_customized: bool = False
    onboarding_completed: bool
    onboarding_step: str
    primary_twin: Optional[str] = "rational"
    weights: Optional[TwinWeightsOut] = None
    persona: str = "student"

class OnboardingStepRequest(BaseModel):
    user_id: Optional[str] = None
    step: str = Field(..., description="persona | tags | reveal | name | permissions | seed | finish")
    persona: Optional[str] = None
    goals: Optional[List[str]] = None
    seed_deadlines: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[ProfileTagItem]] = None
    tie_breaker_choice: Optional[str] = None
    primary_twin: Optional[str] = None
    twin_name: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None

class OnboardingStepResponse(BaseModel):
    success: bool
    current_step: str
    onboarding_completed: bool
    recommended_twin: Optional[str] = None
    primary_twin: Optional[str] = None
    weights: Optional[TwinWeightsOut] = None
    tie_needed: Optional[bool] = False
    tied_twins: Optional[List[str]] = None
    twin_name: Optional[str] = None
    message: Optional[str] = None
    persona: Optional[str] = None

class TwinNameUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    twin_name: Optional[str] = None

class TwinNameUpdateResponse(BaseModel):
    user_id: str
    user_name: str
    twin_name: str
    twin_name_customized: bool
