from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import datetime
import re
import json
import os
import asyncio

from backend.database import get_db
from backend.models import User, TwinWeight, Timetable, Deadline, StudyLog, SimulatorModifier, Attachment, PreferenceProfile, Permission, AuditLog, UserMemory, Goal, normalize_goal_milestones
from backend.config import settings
from pathlib import Path
from backend.services.data_access import get_permitted_user_data
from backend.memory_registry import PERSONAS, CATEGORY_IDS, CATEGORIES, defaults_for
from backend.services.message_intent import personal_fact_category, world_fact_subtype, is_explicit_plan_request
from backend.services.conversation_context import placement_role_followup_reply, spelling_quiz_followup_reply, spelling_quiz_start_reply
from backend.services.world_lookup import cached_grounded_search, check_world_rate_limit, extract_place, open_meteo_weather, sanitize_public_query
from backend.services.safety import crisis_tier, crime_intent, has_unsafe_safety_detail, is_health_question, needs_crisis_escalation_check
from backend.ml.predictor import predictor
from backend.llm.gemini_client import gemini_client
from backend.services.identity import resolve_twin_name
from backend.services.style_blend import normalize_style_weights, style_order
from backend.services.decision_support import rank_deadlines_for_decision

from backend.simulator.engine import simulator_engine, DEFAULT_INITIAL_STATE

router = APIRouter(tags=["Ask Twin"])

def _personal_fact_matches(question: str, category: str, bundle) -> list[tuple[int, str]]:
    """Find category-scoped candidates and format answers only from stored fields."""
    terms = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in {
        "what", "when", "where", "why", "how", "do", "does", "did", "you", "know", "my", "me", "i", "is", "the", "a", "an", "about", "tell", "said", "say", "have", "i", "your"
    }}
    for word, related in {
        "assignment": {"task", "project", "work"}, "deadline": {"task", "project", "due"},
        "meeting": {"call", "appointment"}, "appointment": {"meeting"}, "routine": {"habit"},
    }.items():
        if word in terms:
            terms.update(related)
    records = []
    if category == "deadlines_key_dates":
        for x in bundle.deadlines:
            when = x.due_date.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ").lstrip("0") if hasattr(x.due_date, "strftime") else str(x.due_date)
            records.append((f"{x.title} {x.course_or_project}", f"{x.title} is due {when}."))
    elif category == "schedule_commitments":
        for x in bundle.timetable:
            records.append((f"{x.activity_name} {x.day_of_week}", f"{x.activity_name} is on {x.day_of_week} from {x.start_time} to {x.end_time}."))
    elif category == "goals":
        for x in bundle.goals:
            target = f", with a target of {x.target_date.strftime('%B %d, %Y').replace(' 0', ' ')}" if x.target_date else ""
            records.append((f"{x.title} {x.description or ''}", f"Your goal is {x.title} ({x.status}){target}."))
    elif category == "routines_preferences":
        for x in bundle.preferences:
            records.append((f"{x.key} {x.value} {x.category}", f"You shared that {x.key}: {x.value}."))
    elif category == "spending_money":
        for x in bundle.spending_preferences:
            records.append((f"{x.key} {x.value}", f"You shared that {x.key}: {x.value}."))
    elif category == "focus_work_patterns":
        for x in bundle.study_history:
            records.append((f"{x.subject} {x.time_of_day}", f"You logged {x.subject} in the {x.time_of_day}, for {x.hours_spent:g} hours."))
    elif category == "decision_history":
        for x in bundle.decision_history:
            records.append((f"{x.question} {x.option_chosen}", f"You chose {x.option_chosen} when deciding {x.question}."))
    for memory in bundle.memories:
        if memory.category == category:
            records.append((memory.fact, f"You told me: {memory.fact}"))
    scored = []
    for haystack, answer in records:
        words = set(re.findall(r"[a-z0-9]+", haystack.lower()))
        score = len(terms & words)
        if score:
            scored.append((score, answer))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def _recent_personal_fact_matches(question: str, category: str, recent_turns: list[dict]) -> list[tuple[int, str]]:
    """Reuse explicit facts from this chat before asking the user to repeat them."""
    question_terms = {
        word for word in re.findall(r"[a-z0-9]+", question.lower())
        if word not in {"what", "when", "where", "why", "how", "do", "does", "did", "you", "know", "my", "me", "i", "is", "the", "a", "an", "about", "tell", "said", "say", "have", "your", "on", "for"}
    }
    month_names = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    day_names = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    candidates = []
    for turn in reversed(recent_turns or []):
        if str(turn.get("role", "")).lower() != "user":
            continue
        content = " ".join(str(turn.get("content", "")).split())[:1200]
        words = set(re.findall(r"[a-z0-9]+", content.lower()))
        overlap = question_terms & words
        if not overlap:
            continue
        if category == "deadlines_key_dates":
            if not re.search(rf"\b(?:today|tomorrow|{day_names}|{month_names}\s+\d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}(?:st|nd|rd|th)?(?:\s+(?:of\s+)?(?:{month_names}))?|\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?)\b", content, re.I):
                continue
            has_month = bool(re.search(rf"\b(?:{month_names})\b|\d{{1,2}}[/-]\d{{1,2}}", content, re.I))
            day_match = re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\b", content)
            if day_match and not has_month:
                answer = f"You mentioned the date is the {day_match.group(0)}, but I don’t have the month yet. Which month is it?"
            else:
                answer = f"Earlier in this chat, you said: “{content}”"
        elif category == "schedule_commitments":
            if not re.search(rf"\b(?:{day_names}|\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)|\d{{1,2}}:\d{{2}})\b", content, re.I):
                continue
            answer = f"Earlier in this chat, you mentioned: “{content}”"
        elif category == "routines_preferences":
            if not re.search(r"\b(?:i prefer|i like|i usually|i avoid|i tend to|i work best)\b", content, re.I):
                continue
            answer = f"You told me: “{content}”"
        else:
            continue
        candidates.append((100 + len(overlap), answer))
        if len(candidates) >= 5:
            break
    return candidates


def _missing_task_dates_reply(style: str, question: str, has_real_deadlines: bool) -> Optional[str]:
    """Ask for dates instead of letting a model invent a priority for named tasks."""
    if has_real_deadlines or not re.search(r"\b(?:which|what|how|should|prioriti[sz]e|important|first)\b", question, re.I):
        return None
    task_types = {
        label for pattern, label in (
            (r"\b(?:tests?|exams?|assessments?)\b", "test or exam"),
            (r"\bassignments?\b", "assignment"),
            (r"\bprojects?\b", "project"),
            (r"\bcompetitions?\b", "competition"),
            (r"\binterviews?\b", "interview"),
        ) if re.search(pattern, question, re.I)
    }
    if len(task_types) < 2:
        return None
    return {
        "emotional": "Oh, I can see both matter, and choosing can feel tricky. When are they each due? I'll help you sort out what deserves attention first.",
        "rational": "I need their due dates to compare them accurately. When is each one due?",
        "ambitious": "We can keep both moving. Which is due first, and when is the other one due?",
    }.get(style, "I need their due dates to compare them accurately. When is each one due?")


def _weather_description(code: Optional[int]) -> str:
    descriptions = {0: "clear skies", 1: "mostly clear skies", 2: "partly cloudy skies", 3: "cloudy skies", 45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "steady drizzle", 61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "heavy rain showers", 95: "thunderstorms", 96: "thunderstorms", 99: "thunderstorms"}
    return descriptions.get(code, "a forecast I can’t describe clearly")

class PathStepItem(BaseModel):
    time: str
    task: str

class SimulatedMetrics(BaseModel):
    energy: float
    happiness: float
    study: float
    free_time: float
    disclaimer: str = "Simulated outcomes from life simulator engine"

class PathCardItem(BaseModel):
    id: str
    name: str
    aligned_twin: str
    steps: List[PathStepItem]
    what_youll_achieve: str
    what_it_risks: str
    why_it_could_work: str = ""
    simulated_metrics: SimulatedMetrics
    on_time_probability: float
    explanation: Optional[str] = None

class AskRequest(BaseModel):
    user_id: Optional[str] = "demo-alex-rivers"
    question: str = Field(..., description="The user's question or what-if scenario")
    estimated_hours: Optional[float] = None
    days_until_deadline: Optional[float] = None
    is_exam: Optional[bool] = None
    concurrent_deadlines: Optional[int] = None
    recent_turns: List[Dict[str, Any]] = Field(default_factory=list)
    attachment_id: Optional[str] = None
    context_attachment_id: Optional[str] = None
    # Accept old clients that may include non-weight metadata like primary_twin;
    # the style normalizer reads only the three numeric style keys.
    session_style_weights: Optional[Dict[str, Any]] = None
    local_today: Optional[str] = None
    timezone: Optional[str] = None

class ExtractedItem(BaseModel):
    title: str
    day: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class OptionItem(BaseModel):
    id: str
    text: str
    aligned_twin: str
    description: str

class WhyFactorItem(BaseModel):
    feature: str
    importance_pct: float
    impact: str

class MLInsights(BaseModel):
    on_time_probability: float
    label: str = "prototype indicator"
    predicted_hours: float
    estimated_hours: float
    why_factors: List[WhyFactorItem]
    metrics_report: Optional[Dict[str, Any]] = None
    model_source: str = "synthetic_seed_model"

class CrisisResourceItem(BaseModel):
    name: str
    contact: str
    description: str
    url: str
    type: str = "crisis"
    number: str = ""
    message_number: Optional[str] = None
    hours: str = ""
    languages: str = ""
    last_verified: str = ""


HELPLINES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "helplines.json")

def helplines_for_locale(accept_language: str = "") -> tuple[str, list[CrisisResourceItem]]:
    """Choose resources from the browser locale; no profile or location lookup occurs."""
    try:
        with open(HELPLINES_PATH, "r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError):
        config = {}
    country_code = "OTHER"
    for token in (accept_language or "").split(","):
        locale = token.split(";", 1)[0].strip().replace("_", "-")
        pieces = locale.split("-")
        if len(pieces) > 1 and pieces[1].upper() in {"IN", "US", "GB", "IE"}:
            country_code = pieces[1].upper()
            break
    entry = config.get(country_code, config.get("OTHER", {}))
    resources = []
    for item in entry.get("resources", []):
        number = item.get("number", "")
        resources.append(CrisisResourceItem(
            name=item["name"], contact=number or "Find local support",
            description=f"{item.get('hours', '')}. {item.get('languages', '')}".strip(" ."),
            url=item.get("url") or (f"tel:{number.replace(' ', '')}" if number else "https://findahelpline.com/"),
            type=item.get("type", "crisis"), number=number,
            message_number=item.get("message_number"), hours=item.get("hours", ""),
            languages=item.get("languages", ""), last_verified=entry.get("last_verified", ""),
        ))
    directory_url = config.get("OTHER", {}).get("resources", [{}])[0].get("url", "https://findahelpline.com/")
    if country_code != "OTHER":
        resources.append(CrisisResourceItem(name="Find help in my country", contact="Search local support", description="International directory of local support services.", url=directory_url, type="crisis", last_verified=entry.get("last_verified", "")))
    return entry.get("country", "Other / location not known"), resources


def safety_response(user_id: str, message: str, intent: str, resources: Optional[List[CrisisResourceItem]] = None, severity: Optional[int] = None, crime: bool = False, sources: Optional[List[Dict[str, str]]] = None) -> AskResponse:
    return AskResponse(
        user_id=user_id, badge="Safety support", primary_twin="rational", message=message, answer=message,
        deadline_risk_alert="", ml_insights=MLInsights(on_time_probability=0, predicted_hours=0, estimated_hours=0, why_factors=[], label="not applicable", model_source="not_applicable"),
        options=[], sources_used=["safety_lookup"] if sources else [], prototype_disclaimer="", intent=intent,
        has_paths=False, paths=[], is_crisis_response=bool(severity), crisis_severity=severity,
        crime_response=crime, show_safety_resources=bool(resources), crisis_resources=resources or [], lookup_sources=sources or [],
        timestamp=datetime.datetime.utcnow(),
    )

class AskResponse(BaseModel):
    user_id: str
    badge: str
    primary_twin: str
    message: str
    provider_status: str = "local"
    why_summary: Optional[str] = None
    # Compatibility alias for clients that have not migrated to `message` yet.
    answer: str
    deadline_risk_alert: str
    ml_insights: MLInsights
    options: List[OptionItem]
    sources_used: List[str]
    prototype_disclaimer: str = "Percentages and probabilities are prototype indicators, not scientific measurements."
    intent: str = "question_or_advice"
    style_weights: Dict[str, float] = Field(default_factory=lambda: {"rational": 0.5, "emotional": 0.25, "ambitious": 0.25})
    primary_style: str = "rational"
    secondary_style: str = "emotional"
    show_other_voices: bool = False
    decision_support: Optional[Dict[str, Any]] = None
    recommended_choice: Optional[str] = None
    has_paths: bool = False
    offer_simulation: Optional[str] = None
    paths: List[PathCardItem] = []
    is_crisis_response: bool = False
    crisis_severity: Optional[int] = None
    crime_response: bool = False
    show_safety_resources: bool = False
    fact_lookup_status: Optional[str] = None
    lookup_category: Optional[str] = None
    lookup_sources: List[Dict[str, str]] = Field(default_factory=list)
    crisis_resources: List[CrisisResourceItem] = []
    attachment_looks_like_schedule: bool = False
    extracted_items: List[ExtractedItem] = []
    memories_saved: List[str] = []
    plan_items_created: List[Dict[str, Any]] = []
    goals_updated: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime.datetime

CRISIS_PATTERNS = (
    r"\b(?:kill|hurt|harm)\s+(?:myself|me)\b",
    r"\b(?:end|take)\s+my\s+(?:life|own life)\b",
    r"\b(?:suicide|suicidal|self[- ]?harm)\b",
    r"\b(?:want|wish|plan|going|gonna|about)\s+to\s+die\b",
    r"\b(?:don't|do not|can't|cannot)\s+(?:want to live|go on)\b",
    r"\b(?:better off dead|no reason to live)\b",
)

def is_crisis_like_message(message: str) -> bool:
    result = crisis_tier(message)
    return bool(result and result[0] in (1, 2))


_AVAILABILITY_RANGE = re.compile(
    r"\b(?:free|available|focus|study|work)\b[^\n]{0,140}?"
    r"\b(?:from|between|at)?\s*(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
    r"\s*(?:to|until|till|and|[-–])\s*"
    r"(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
    re.I,
)

_TIME_RANGE_ONLY = re.compile(
    r"\b(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\s*"
    r"(?:to|until|till|[-–])\s*(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)\b",
    re.I,
)


def _minutes_for_time_token(token: str, default_meridiem: str = "") -> Optional[int]:
    clean = re.sub(r"\s+", "", token.lower()).replace(".", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", clean)
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2) or 0), match.group(3) or default_meridiem
    if minute > 59 or hour > 23:
        return None
    if meridiem:
        if hour < 1 or hour > 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    elif hour < 1 or hour > 23 or hour <= 12:
        return None  # 4–8 is ambiguous; ask instead of guessing AM/PM.
    return hour * 60 + minute


def _explicit_availability_window(text: str) -> Optional[tuple[int, int]]:
    match = _AVAILABILITY_RANGE.search(text or "")
    if not match:
        match = _TIME_RANGE_ONLY.search(text or "")
    if not match:
        return None
    first, second = match.group(1), match.group(2)
    meridiem_match = re.search(r"(am|pm)", second.replace(".", ""), re.I) or re.search(r"(am|pm)", first.replace(".", ""), re.I)
    default_meridiem = meridiem_match.group(1).lower() if meridiem_match else ""
    start = _minutes_for_time_token(first, default_meridiem)
    end = _minutes_for_time_token(second, default_meridiem)
    if start is None or end is None or end <= start:
        return None
    return start, end


def _ambiguous_availability_period(text: str) -> Optional[tuple[str, str]]:
    """Return an unmarked 12-hour range so Echo can ask AM/PM only."""
    match = _AVAILABILITY_RANGE.search(text or "") or _TIME_RANGE_ONLY.search(text or "")
    if not match:
        return None
    first, second = match.group(1).strip(), match.group(2).strip()
    if re.search(r"\b(?:am|pm)\b", first + " " + second, re.I):
        return None
    hours = [int(re.match(r"\d{1,2}", token).group()) for token in (first, second)]
    if any(hour > 12 for hour in hours):
        return None
    return first, second


def _one_sided_availability(text: str, start_hint: Optional[int] = None) -> tuple[Optional[int], Optional[int]]:
    """Read a stated start/end bound without pretending it is a full free-time window."""
    text = text or ""
    start_match = re.search(
        r"\b(?:reach|get|arrive|come)\s+(?:back\s+)?home\s+(?:after|at|around)\s+(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
        r"|\bhome\s+(?:after|at|around)\s+(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)"
        r"|\bfree\s+(?:after|from)\s+(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)",
        text, re.I,
    )
    end_match = re.search(
        r"\b(?:until|till|stop(?:ping)?\s+at|finish(?:ing)?\s+at)\s+(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)",
        text, re.I,
    )
    start = None
    if start_match:
        token = next((group for group in start_match.groups() if group), "")
        # A return-home time in the context of daytime classes is an evening
        # boundary. Keep other unmarked clock times ambiguous and ask first.
        meridiem = "pm" if re.search(r"\bhome\b", text, re.I) and not re.search(r"\b(?:am|pm)\b", token, re.I) else ""
        start = _minutes_for_time_token(token, meridiem)
    end = None
    if end_match:
        token = end_match.group(1)
        meridiem = "pm" if (start_hint or start or 0) >= 12 * 60 and not re.search(r"\b(?:am|pm)\b", token, re.I) else ""
        end = _minutes_for_time_token(token, meridiem)
        if end is not None and start_hint is not None and end <= start_hint and end < 12 * 60:
            end += 12 * 60
    return start, end


def _explicit_availability_days(text: str) -> Optional[set[int]]:
    lower = (text or "").lower()
    if re.search(r"\b(?:every day|daily|all week|any day|next 7 days)\b", lower):
        return set(range(7))
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if re.search(r"\bweekdays\b", lower):
        return {0, 1, 2, 3, 4}
    if re.search(r"\bweekends\b", lower):
        return {5, 6}
    found = {index for index, name in enumerate(names) if re.search(rf"\b{name}s?\b", lower)}
    range_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:to|through|until|-)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower)
    if range_match:
        start, end = names.index(range_match.group(1)), names.index(range_match.group(2))
        found = set(range(start, end + 1)) if start <= end else set(range(start, 7)) | set(range(0, end + 1))
    return found or None


def _mentions_upcoming_commitment(text: str) -> bool:
    task = bool(re.search(r"\b(?:exams?|tests?|assignments?|submissions?|submit|homework|tasks?|deadlines?|due|projects?|competitions?|appointments?|presentations?|quizzes|reports?)\b", text or "", re.I))
    future = bool(re.search(
        r"\b(?:in\s+\d+\s+days?|(?:after|in)\s+(?:a|one|1)\s+week|next\s+(?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|day\s+after\s+tomorrow|by\s+(?:\w+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\b)|on\s+(?:\w+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\b)|due\s+(?:on\s+)?\w+\s+\d{1,2}(?:st|nd|rd|th)?)\b",
        text or "", re.I,
    ))
    return task and future


def _has_explicit_date_cue(text: str) -> bool:
    return bool(re.search(
        r"\b(?:today|tomorrow|day after tomorrow|next\s+(?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|in\s+\d+\s+days?|(?:after|in)\s+(?:a|one|1)\s+week|(?:on|by)\s+(?:\w+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\b)|due\s+(?:on\s+)?\w+\s+\d{1,2}(?:st|nd|rd|th)?|\w+\s+\d{1,2}(?:st|nd|rd|th)?)\b",
        text or "", re.I,
    ))

@router.post("/ask", response_model=AskResponse)
@router.post("/api/ask", response_model=AskResponse)
async def ask_twin(req: AskRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Fast Answers from One Twin:
    - Every answer comes from the primary twin only, using ONE Gemini call.
    - Uses permitted data via single data-access function get_permitted_user_data().
    - Integrates scikit-learn ML predictions and feature importances.
    - Mentions real deadline risks from data even when primary twin is not Rational.
    - Logs accessed sources to audit_log.
    """
    user_id = req.user_id or "demo-alex-rivers"

    # Crisis and crime safety are deterministic and run before any database, memory,
    # intent-model, search, planning, or Gemini work. The browser locale is only a
    # country hint; device location and profile data are never read here.
    recent_active = any(
        turn.get("role") == "user" and crisis_tier(str(turn.get("content", ""))) == (1, False)
        for turn in req.recent_turns
    )
    risk = (1, False) if recent_active else crisis_tier(req.question)
    if risk is None and needs_crisis_escalation_check(req.question):
        try:
            async with asyncio.timeout(4.0):
                if await gemini_client.classify_crisis_escalation(req.question):
                    risk = (2, False)
        except Exception:
            pass
    country, resources = helplines_for_locale(request.headers.get("accept-language", ""))
    if risk and risk[0] in (1, 2):
        tier, for_someone_else = risk
        if tier == 1 and for_someone_else:
            message = "I'm glad you told me. Stay with them if you can do so safely, listen without judgment, and don't keep this to yourself. If they may be in immediate danger, contact emergency services or someone nearby now."
        elif tier == 1:
            message = "I'm really glad you told me. This sounds incredibly painful, and you deserve support from a real person right now. Please reach out to one of these helplines. If you might act on these feelings, call your local emergency number or go to the nearest hospital, or ask someone near you to stay with you. I'm here with you too."
        else:
            message = "I'm sorry things feel this heavy. You don't have to carry it alone; please consider telling someone you trust. If it ever feels like too much, these people are here to talk. Would you like to tell me more, or see someone you can contact?"
        return safety_response(user_id, message, "crisis", resources, severity=tier)
    if risk and risk[0] == 3:
        safe_topic = "suicide prevention warning signs and how to support someone safely"
        try:
            local_now = datetime.datetime.now().astimezone()
            grounded = await cached_grounded_search(gemini_client, safe_topic, f"{local_now.isoformat()} ({local_now.tzname() or 'local time'})", 3600)
            sources = grounded["sources"]
            message = grounded["text"]
        except Exception:
            sources = []
            message = "Warning signs can include talking about hopelessness, withdrawing, or a sudden change in behavior. A mental health professional or local support service can help put concerns in context."
        if has_unsafe_safety_detail(message):
            message = "Warning signs can include talking about hopelessness, withdrawing, or a sudden change in behavior. A mental health professional or local support service can help put concerns in context."
        message += " This is a heavy topic. If any of it is close to home, I’m here and can point you to people who can help."
        return safety_response(user_id, message, "crisis_information", resources, severity=3, sources=sources)
    crime = crime_intent(req.question)
    if crime:
        if crime == "victim_support":
            message = "I'm sorry this is happening. Save any evidence, avoid engaging with the person, and contact a trusted person or the relevant local support service. If you're in immediate danger, call emergency services."
        else:
            message = "I can't help with hurting someone or committing or hiding a crime. It could harm people and bring serious legal consequences. If you're angry or stuck, I can help you find a safe, legal next step."
        crime_resources = [r for r in resources if r.type in {"cyber", "emergency", "women", "child"}]
        return safety_response(user_id, message, "crime_or_harm", crime_resources, crime=True)
    if is_health_question(req.question):
        emergency_symptom = re.search(r"\b(?:chest pain|can't breathe|cannot breathe|trouble breathing|overdose|unconscious|severe bleeding|stroke symptoms)\b", req.question, re.I)
        asks_general = re.search(r"\b(?:what is|what are|explain|warning signs|symptoms of|information about)\b", req.question, re.I)
        personal_health = re.search(r"\b(?:i have|i'm having|my\b|i feel|should i take|what should i take|my medication|do i have|could i have|can i have)\b", req.question, re.I)
        if emergency_symptom:
            message = "That could need urgent medical attention. Please contact your local emergency service or go to an emergency department now. I can’t assess this safely over chat."
            return safety_response(user_id, message, "health_question", [resource for resource in resources if resource.type == "emergency"])
        if asks_general and not personal_health:
            safe_query = sanitize_public_query(req.question)
            try:
                now = datetime.datetime.now().astimezone()
                grounded = await cached_grounded_search(gemini_client, safe_query, f"{now.isoformat()} ({now.tzname() or 'local time'})", 3600, safety_mode=True)
                grounded_text = grounded["text"]
                if has_unsafe_safety_detail(grounded_text):
                    raise ValueError("The grounded answer contained unsafe medical details")
                message = grounded_text + " I'm not a doctor, so use this as general information and check with a clinician for personal advice."
                return safety_response(user_id, message, "health_question", sources=grounded["sources"])
            except Exception:
                pass
        message = "I can share general health information, but I can't diagnose you or recommend a treatment. A clinician can assess your symptoms; if they're severe or quickly getting worse, please seek urgent care."
        return safety_response(user_id, message, "health_question")

    # Read identity and primary voice first; casual chat never loads personal context.
    user = await db.get(User, user_id)
    user_name = (user.name or "the user").strip() if user else "the user"
    twin_name = resolve_twin_name(user) if user else "Echo"

    # 2. Get user's primary twin and weights
    w_res = await db.execute(select(TwinWeight).where(TwinWeight.user_id == user_id))
    twin_weight = w_res.scalar_one_or_none()
    primary_twin = twin_weight.primary_twin if twin_weight else "rational"
    style_weights = normalize_style_weights({
        "rational": twin_weight.rational if twin_weight else 0.50,
        "emotional": twin_weight.emotional if twin_weight else 0.25,
        "ambitious": twin_weight.ambitious if twin_weight else 0.25,
    })
    current_style_order = style_order(style_weights)
    primary_style, secondary_style = current_style_order[0], current_style_order[1]

    history_permission = await db.scalar(select(Permission).where(
        Permission.user_id == user_id, Permission.source == "decision_history"
    ))
    history_enabled = history_permission.enabled if history_permission else defaults_for(user.persona if user else "other").get("decision_history", False)
    if not history_enabled and req.session_style_weights:
        style_weights = normalize_style_weights(req.session_style_weights)
        current_style_order = style_order(style_weights)
        primary_style, secondary_style = current_style_order[0], current_style_order[1]

    # Classify first so casual chat is not treated as a planning request. Greetings
    # stay local, while feelings and small talk still reach Gemini for a natural,
    # context-aware conversation (with a specific local reply only if it is offline).
    affirmative_reply = bool(re.fullmatch(r"\s*(?:yes|yeah|yep|sure|okay|ok|please|do that|go ahead|absolutely)(?:[,\s]+please)?[.! ]*\s*", req.question, re.I))
    assistant_offered_reminder = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"would you like me to (?:add|set|save) (?:a )?(?:reminder|reminder for)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    assistant_offered_exam_plan = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"would you like me to (?:help (?:you )?(?:prepare|make)|make|create) (?:a )?(?:study )?(?:plan|timetable)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    prior_upcoming_message = next((
        str(turn.get("content", ""))[:1200]
        for turn in reversed(req.recent_turns)
        if str(turn.get("role", "")).lower() == "user" and _mentions_upcoming_commitment(str(turn.get("content", "")))
    ), "")
    reminder_confirmation = affirmative_reply and assistant_offered_reminder and bool(prior_upcoming_message)
    plan_confirmation = affirmative_reply and assistant_offered_exam_plan and bool(prior_upcoming_message)
    latest_assistant_message = next((
        str(turn.get("content", "")) for turn in reversed(req.recent_turns)
        if str(turn.get("role", "")).lower() == "assistant"
    ), "")
    retry_failed_plan = bool(
        re.search(r"\b(?:try again|retry|yes|go ahead)\b", req.question, re.I)
        and "I've got your availability, but" in latest_assistant_message
    )
    plan_request = is_explicit_plan_request(req.question) or plan_confirmation or retry_failed_plan
    assistant_asked_for_availability = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"(?:what (?:exact )?hours are you free|exact hours are you free|what times are you free|when do you focus best|which days should i use|which days should i plan around|what time would you like to finish|what time can you start|would you like me to (?:help you prepare with a timetable|make a preparation timetable)|are those times .*am or pm|did you mean .*\b(?:am|pm)\b)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    assistant_asked_goal = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"(?:what (?:are you hoping|event|outcome|goal are you aiming)|what date are you aiming)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    assistant_offered_goal_tracking = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"(?:would you like me to (?:help you )?(?:track|work toward)|want me to (?:track|help you work toward)) (?:this goal|that goal|it)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    goal_tracking_confirmation = affirmative_reply and assistant_offered_goal_tracking
    explicit_goal_statement = bool(re.search(r"\b(?:my goal is|i want to|i'd like to|i would like to|i am aiming to|i'm aiming to|i hope to)\b", req.question, re.I))
    deadline_source_text = req.question if _mentions_upcoming_commitment(req.question) else (prior_upcoming_message if (reminder_confirmation or plan_confirmation) else req.question)
    upcoming_commitment = _mentions_upcoming_commitment(deadline_source_text)
    reminder_request = bool(re.search(r"\b(?:remind me|reminder|don't let me forget|do not let me forget)\b", req.question, re.I)) or reminder_confirmation
    schedule_setup_request = plan_request or assistant_asked_for_availability
    detected_intent = await gemini_client.classify_message_type(req.question)
    if schedule_setup_request:
        detected_intent = "decision_question"
    elif upcoming_commitment or reminder_request:
        # A saved due date or reminder is a concrete write request. A model
        # classification such as personal_fact_lookup must not divert it into a
        # read-only lookup response before the reminder can be persisted.
        detected_intent = "question_or_advice"
    placement_followup = placement_role_followup_reply(req.question, req.recent_turns)
    if placement_followup:
        detected_intent = "question_or_advice"
    spelling_followup = spelling_quiz_followup_reply(req.question, req.recent_turns, primary_style)
    if not spelling_followup:
        spelling_followup = spelling_quiz_start_reply(req.question, req.recent_turns)
    if spelling_followup:
        return AskResponse(
            user_id=user_id,
            badge=f"{primary_style.capitalize()} style",
            primary_twin=primary_twin,
            message=spelling_followup,
            answer=spelling_followup,
            deadline_risk_alert="",
            ml_insights=MLInsights(
                on_time_probability=0, predicted_hours=0, estimated_hours=0,
                why_factors=[], label="not applicable", model_source="not_applicable",
            ),
            options=[], sources_used=[], intent="learning_followup",
            style_weights=style_weights, primary_style=primary_style,
            secondary_style=secondary_style, show_other_voices=False,
            has_paths=False, timestamp=datetime.datetime.utcnow(),
        )
    if detected_intent == "greeting_or_intro":
        from backend.services.message_intent import introduced_name
        message = gemini_client._fallback_spoken_message(
            primary_style, req.question, False, req.recent_turns, twin_name,
        )
        introduced = introduced_name(req.question)
        if detected_intent == "greeting_or_intro" and introduced:
            already_introduced = any(
                turn.get("role") == "assistant" and f"i'm {twin_name.lower()}" in str(turn.get("content", "")).lower()
                for turn in req.recent_turns
            )
            message = f"Hey {introduced}! So nice to meet you. " if not already_introduced else f"Hey {introduced}! "
            if not already_introduced:
                message += f"I'm {twin_name}, your twin here. "
            message += "What's on your mind today?"
        return AskResponse(
            user_id=user_id, badge=f"{primary_twin.capitalize()} style", primary_twin=primary_twin,
            message=message, answer=message, deadline_risk_alert="",
            ml_insights=MLInsights(on_time_probability=0, predicted_hours=0, estimated_hours=0, why_factors=[]),
            options=[], sources_used=[], intent=detected_intent, has_paths=False,
            offer_simulation=None, paths=[], timestamp=datetime.datetime.utcnow(),
            style_weights=style_weights, primary_style=primary_style, secondary_style=secondary_style,
            show_other_voices=False,
        )

    if detected_intent in {"world_fact_lookup", "mixed_fact_lookup"}:
        subtype = world_fact_subtype(req.question) or "other_live"
        tool_used = "none"
        if not check_world_rate_limit(user_id):
            world_status, world_reply, source_list = "rate_limited", "I’ve checked quite a few things just now. Give me a minute, then I can try again.", []
        elif subtype == "holidays_calendar" and not extract_place(req.question):
            world_status, world_reply, source_list = "missing_region", "Which state should I check, and do you mean government, bank, school, or company holidays?", []
        elif not (place := extract_place(req.question)) and subtype in {"weather", "local_info"}:
            city_bundle = await get_permitted_user_data(db, user_id=user_id, requested_sources=["routines_preferences"], log_audit_endpoint="/ask", audit_action="world_fact_lookup")
            saved_city = next((p.value for p in city_bundle.preferences if p.key.casefold() in {"city", "location", "home city"}), None) if city_bundle.enabled_sources.get("routines_preferences") else None
            if saved_city:
                place = saved_city
            else:
                world_status, world_reply, source_list = "missing_place", "Which city should I check?", []
        if "world_status" not in locals():
            try:
                if subtype == "weather":
                    try:
                        weather = await open_meteo_weather(place, tomorrow=bool(re.search(r"\btomorrow\b", req.question, re.I)))
                        date = datetime.date.fromisoformat(weather["date"]).strftime("%A, %B %d").replace(" 0", " ")
                        description = _weather_description(weather.get("weather_code"))
                        values = [f"{date} in {weather['place']}: {description}"]
                        if weather.get("min_c") is not None and weather.get("max_c") is not None:
                            values.append(f"{weather['min_c']}–{weather['max_c']}°C")
                        if weather.get("rain_chance") is not None:
                            values.append(f"{weather['rain_chance']}% chance of rain")
                        world_reply = ", ".join(values) + ". Forecast from Open-Meteo."
                        source_list = [{"title": "Open-Meteo", "url": "https://open-meteo.com/"}]
                        tool_used = "open_meteo"
                    except Exception:
                        public_query = sanitize_public_query(req.question, user_name, getattr(user, "email", "") if user else "")
                        local_now = datetime.datetime.now().astimezone()
                        grounded = await cached_grounded_search(gemini_client, public_query, f"{local_now.isoformat()} ({local_now.tzname() or 'local time'})", 1800)
                        source_list = grounded["sources"]
                        world_reply = grounded["text"]
                        tool_used = "google_search"
                else:
                    public_query = sanitize_public_query(req.question, user_name, getattr(user, "email", "") if user else "")
                    if not public_query:
                        raise LookupError("No safe public query")
                    if subtype == "holidays_calendar":
                        public_query = "official " + public_query
                    local_now = datetime.datetime.now().astimezone()
                    cache_ttl = 86400 if subtype == "holidays_calendar" else 1800
                    grounded = await cached_grounded_search(gemini_client, public_query, f"{local_now.isoformat()} ({local_now.tzname() or 'local time'})", cache_ttl)
                    source_list = grounded["sources"]
                    world_reply = grounded["text"]
                    tool_used = "google_search"
                world_status = "found"
            except Exception:
                world_status, world_reply, source_list = "unavailable", "I couldn’t check that right now. Want me to try again in a moment?", []
        db.add(AuditLog(user_id=user_id, action="world_fact_lookup", endpoint="/ask", sources_accessed=[f"intent:{subtype}", f"tool:{tool_used}", f"result:{world_status}"], timestamp=datetime.datetime.utcnow()))
        personal_reply = ""
        if detected_intent == "mixed_fact_lookup":
            category = personal_fact_category(req.question)
            personal_bundle = await get_permitted_user_data(db, user_id=user_id, requested_sources=[category] if category else [], log_audit_endpoint=None)
            if category and not personal_bundle.enabled_sources.get(category, False):
                personal_reply = f"I can’t see that personal detail because {CATEGORIES[category]['title']} is switched off."
                fact_status = "permission_off"
            else:
                matches = (
                    _recent_personal_fact_matches(req.question, category, req.recent_turns)
                    + _personal_fact_matches(req.question, category, personal_bundle)
                ) if category else []
                if matches:
                    personal_reply, fact_status = matches[0][1], "found"
                else:
                    personal_reply, fact_status = "I don’t know that personal detail yet. Want to tell me?", "not_found"
            db.add(AuditLog(user_id=user_id, action="personal_fact_lookup", endpoint="/ask", sources_accessed=[f"category:{category or 'unknown'}", "purpose:personal_fact_lookup", f"result:{fact_status}"], timestamp=datetime.datetime.utcnow()))
        await db.commit()
        reply = world_reply + (" " + personal_reply if personal_reply else "")
        return AskResponse(
            user_id=user_id, badge=f"{primary_twin.capitalize()} style", primary_twin=primary_twin,
            message=reply, answer=reply, deadline_risk_alert="",
            ml_insights=MLInsights(on_time_probability=0, predicted_hours=0, estimated_hours=0, why_factors=[]),
            options=[], sources_used=["world_lookup"] if world_status == "found" else [], intent=detected_intent,
            has_paths=False, paths=[], lookup_sources=source_list,
            fact_lookup_status=world_status, timestamp=datetime.datetime.utcnow(), style_weights=style_weights,
            primary_style=primary_style, secondary_style=secondary_style,
        )

    if detected_intent == "personal_fact_lookup":
        category = personal_fact_category(req.question)
        # The gateway checks permission first and only queries the requested category.
        bundle = await get_permitted_user_data(db, user_id=user_id, requested_sources=[category] if category else [], log_audit_endpoint=None)
        if not category:
            status, reply = "ambiguous", "I’m not sure which part you mean yet. What would you like me to check?"
        elif not bundle.enabled_sources.get(category, False):
            status = "permission_off"
            label = CATEGORIES[category]["title"]
            reply = f"I can’t see that right now because {label} is switched off. You can turn it on in Privacy, or tell me here and I can help just this once."
        else:
            matches = (
                _recent_personal_fact_matches(req.question, category, req.recent_turns)
                + _personal_fact_matches(req.question, category, bundle)
            )
            if not matches:
                status = "not_found"
                reply = "Hmm, I don’t know that about you yet. Want to tell me, so I can keep it in mind?"
            elif len(matches) > 1 and matches[0][0] - matches[1][0] < 2:
                status = "ambiguous"
                reply = f"I found a couple of possibilities. Which {CATEGORIES[category]['title'].lower()} did you mean?"
            else:
                status, reply = "found", matches[0][1]
                if category == "goals" and re.search(r"\b(?:when|due|date|by)\b", req.question, re.I) and not any(g.target_date for g in bundle.goals):
                    status = "partial"
                    reply = f"{matches[0][1]} I don’t have a target date for it yet. Do you know when you’d like it done?"
        # Record purpose and outcome only; never include the question or matched content.
        db.add(AuditLog(user_id=user_id, action="personal_fact_lookup", endpoint="/ask", sources_accessed=[f"category:{category or 'unknown'}", "purpose:personal_fact_lookup", f"result:{status}"], timestamp=datetime.datetime.utcnow()))
        await db.commit()
        # Give Gemini an explicit status and evidence boundary. The UI reply is composed
        # from the same evidence/status templates so a model cannot add personal details.
        try:
            await gemini_client.call_gemini_text(
                f"Personal fact lookup status: {status}. Category: {category or 'unknown'}. Evidence: {reply if status == 'found' else 'none'}. User message: {req.question}. Return a warm reply using only that evidence; never invent personal facts, dates, times, or names.",
                system_instruction="Only state personal facts present in the explicit evidence. Never guess. If evidence is none, say you do not know yet; if permission is off, do not imply data exists.",
                temperature=0.2,
            )
        except Exception:
            pass
        return AskResponse(
            user_id=user_id, badge=f"{primary_twin.capitalize()} style", primary_twin=primary_twin,
            message=reply, answer=reply, deadline_risk_alert="",
            ml_insights=MLInsights(on_time_probability=0, predicted_hours=0, estimated_hours=0, why_factors=[]),
            options=[], sources_used=[category] if category and category in bundle.accessed_sources else [], intent="personal_fact_lookup",
            has_paths=False, offer_simulation=None, paths=[], fact_lookup_status=status, lookup_category=category,
            timestamp=datetime.datetime.utcnow(), style_weights=style_weights, primary_style=primary_style, secondary_style=secondary_style,
        )

    # Only questions that need permitted context pass through the data gateway.
    bundle = await get_permitted_user_data(
        db, user_id=user_id, log_audit_endpoint="/ask", audit_action="ask_twin"
    )
    inline_attachment = None
    context_attachment_id = req.attachment_id or req.context_attachment_id or next((
        str(turn.get("attachment_id"))
        for turn in reversed(req.recent_turns)
        if str(turn.get("role", "")).lower() == "user" and turn.get("attachment_id")
    ), None)
    if context_attachment_id:
        attachment = await db.get(Attachment, context_attachment_id)
        if not attachment or attachment.user_id != user_id:
            raise HTTPException(status_code=404, detail="I couldn't find that file.")
        attachment_path = Path(settings.UPLOAD_DIR) / user_id / attachment.stored_name
        if not attachment_path.is_file():
            raise HTTPException(status_code=404, detail="I couldn't find that file.")
        inline_attachment = {
            "mime_type": attachment.mime_type,
            "data": attachment_path.read_bytes(),
            "name": attachment.original_name,
        }

    # 3. Detect real deadline risks from permitted deadlines
    deadline_risk_summary = ""
    active_deadlines = [item for item in bundle.deadlines if not item.completed]
    nearest_deadline = min(active_deadlines, key=lambda item: item.due_date) if active_deadlines else None
    target_est_hours = req.estimated_hours if req.estimated_hours is not None else (nearest_deadline.estimated_hours if nearest_deadline else 12.0)
    if req.days_until_deadline is not None:
        target_days = req.days_until_deadline
    elif nearest_deadline:
        target_days = max(0.1, (nearest_deadline.due_date - datetime.datetime.utcnow()).total_seconds() / 86400.0)
    else:
        target_days = 2.0
    target_is_exam = req.is_exam if req.is_exam is not None else bool(nearest_deadline and nearest_deadline.is_exam)
    target_priority_numeric = {"low": 1, "medium": 2, "high": 3, "urgent": 4}.get((nearest_deadline.priority or "").lower(), 3) if nearest_deadline else 3
    target_concurrent = req.concurrent_deadlines if req.concurrent_deadlines is not None else max(1, len(active_deadlines))

    if "deadlines" in bundle.accessed_sources and bundle.deadlines:
        urgent_deadlines = []
        exam_found = False
        assignment_found = False
        now = datetime.datetime.utcnow()

        for d in bundle.deadlines:
            if not d.completed:
                days_left = max(0.1, (d.due_date - now).total_seconds() / 86400.0)
                if days_left <= 3.5:
                    urgent_deadlines.append(f"{d.title} (due in {days_left:.1f} days, estimated effort {d.estimated_hours}h)")
                    if d.is_exam:
                        exam_found = True
                    else:
                        assignment_found = True

        if urgent_deadlines:
            target_concurrent = max(target_concurrent, len(urgent_deadlines))
            conflict_note = "Several key dates are close together. " if len(urgent_deadlines) > 1 else ""
            deadline_risk_summary = f"{conflict_note}Upcoming key dates within 3 days: " + "; ".join(urgent_deadlines)
    # Disabled categories are omitted from context and from the spoken reply.

    # Calculate average recent focus from study history if permitted
    avg_focus = 8.0
    if "study_history" in bundle.accessed_sources and bundle.study_history:
        recent_ratings = [s.focus_rating for s in bundle.study_history[:10]]
        if recent_ratings:
            avg_focus = sum(recent_ratings) / len(recent_ratings)

    # 4. Generate ML Predictions (scikit-learn)
    ml_res = predictor.predict(
        estimated_hours=target_est_hours,
        days_until_deadline=target_days,
        is_exam=target_is_exam,
        priority_numeric=target_priority_numeric,
        avg_recent_focus=avg_focus,
        concurrent_deadlines=target_concurrent,
        night_study_ratio=0.5
    )

    # Convert why factors
    why_factors_out = []
    for wf in ml_res.get("why_factors", []):
        why_factors_out.append(WhyFactorItem(
            feature=wf.get("feature", ""),
            importance_pct=float(wf.get("importance_pct", 0.0)),
            impact=wf.get("impact", "")
        ))

    # 6. Check data availability for decision requests
    has_real_deadlines = bool("deadlines" in bundle.accessed_sources and bundle.deadlines and any(not d.completed for d in bundle.deadlines))
    has_real_timetable = bool("timetable" in bundle.accessed_sources and bundle.timetable)
    asks_about_saved_work = bool(re.search(
        r"\b(deadline|due|exam|test|assignment|project|task|commitment|plan|prioriti[sz]e|important|work|competition|focus)\b",
        req.question, re.I,
    ))
    decision_support = (
        rank_deadlines_for_decision(active_deadlines, req.question)
        if detected_intent == "decision_question" and has_real_deadlines and asks_about_saved_work and not schedule_setup_request else None
    )

    # 7. Call Gemini for natural twin dialogue
    permitted_context = bundle.to_context_string()
    learned_profile = None
    if "decision_history" in bundle.accessed_sources:
        learned = await db.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
        if learned:
            learned_profile = {
                "tendencies": learned.tendencies or {},
                "confidence": learned.confidence or {},
                "source_counts": learned.source_counts or {},
            }
    gemini_out = await gemini_client.ask_primary_twin(
        primary_twin=primary_twin,
        question=req.question,
        permitted_context=permitted_context,
        ml_insights=ml_res,
        deadline_risk_summary=deadline_risk_summary or "No deadline or due date has been shared in the information available for this reply.",
        user_name=user_name,
        twin_name=twin_name,
        mood_tone_enabled=bundle.enabled_sources.get("mood_tone", False),
        recent_turns=req.recent_turns,
        inline_attachment=inline_attachment,
        extract_attachment=bool(req.attachment_id),
        user_persona=PERSONAS.get(getattr(user, "persona", "student"), PERSONAS["other"])["label"],
        permitted_categories=[category for category in CATEGORY_IDS if category in bundle.accessed_sources],
        message_type=detected_intent,
        preference_profile=learned_profile,
        style_weights=style_weights,
        decision_support=decision_support,
        plan_request=schedule_setup_request,
    )

    # Turn an in-chat planning conversation into real, reminder-visible calendar
    # blocks once the user has supplied an exact free-time window.
    plan_items_created = []
    goals_updated = []
    goal_saved_during_schedule = False
    deadline_reminder_created = False
    deadline_offer_needed = False
    deadline_offer_title = None
    deadline_offer_date = None
    deadline_offer_is_exam = False
    spoken_message = gemini_out.get("message") or gemini_out.get("answer", "")
    if placement_followup:
        # A short clarification such as “Software engineer” must stay attached to
        # the placement question even if the model classifies it as small talk or
        # its draft falls back to a generic response.
        spoken_message = placement_followup
    missing_dates_reply = _missing_task_dates_reply(primary_style, req.question, has_real_deadlines)
    if detected_intent == "decision_question" and asks_about_saved_work and missing_dates_reply:
        spoken_message = missing_dates_reply
    date_followup_needed = False
    saved_deadline_title = None
    saved_deadline_date = None
    local_today = None
    try:
        local_today = datetime.date.fromisoformat(req.local_today) if req.local_today else datetime.datetime.now().date()
    except ValueError:
        local_today = datetime.datetime.now().date()

    if upcoming_commitment or reminder_request:
        if not bundle.enabled_sources.get("deadlines_key_dates", False):
            if reminder_request:
                spoken_message = "I can save a due-date reminder, but Deadlines & Key Dates is switched off. Turn it on in Privacy and tell me the date again."
                date_followup_needed = True
        elif reminder_request and not _has_explicit_date_cue(deadline_source_text):
            if reminder_request:
                spoken_message = "What date should I remind you about? If you want a time-specific reminder, include the time too."
                date_followup_needed = True
        else:
            try:
                async with asyncio.timeout(8.0):
                    deadline_candidate = await gemini_client.extract_chat_deadline(deadline_source_text, local_today.isoformat())
                if deadline_candidate.get("needs_follow_up"):
                    spoken_message = str(deadline_candidate.get("question") or "What exact date should I use for that reminder?")
                    date_followup_needed = True
                elif deadline_candidate.get("create"):
                    quote = " ".join(str(deadline_candidate.get("date_quote", "")).split()).casefold()
                    user_text = " ".join(deadline_source_text.split()).casefold()
                    try:
                        due_date = datetime.date.fromisoformat(str(deadline_candidate["due_date"]))
                    except (KeyError, ValueError, TypeError):
                        due_date = None
                    title = " ".join(str(deadline_candidate.get("title", "")).split())[:200]
                    if not quote or quote not in user_text or not title or not due_date or not (local_today <= due_date <= local_today + datetime.timedelta(days=365)):
                        spoken_message = "I want to get that reminder right. What exact date should I use?"
                        date_followup_needed = True
                    else:
                        saved_deadline_title = title
                        saved_deadline_date = due_date
                        deadline_offer_title = title
                        deadline_offer_date = due_date
                        deadline_offer_is_exam = bool(deadline_candidate.get("is_exam", False))
                        priority = str(deadline_candidate.get("priority", "medium")).lower()
                        if priority not in {"low", "medium", "high", "urgent"}:
                            priority = "medium"
                        duplicate = next((item for item in bundle.deadlines if item.title.casefold() == title.casefold() and item.due_date.date() == due_date), None)
                        if duplicate:
                            deadline_reminder_created = True
                            saved_deadline_title = duplicate.title
                            saved_deadline_date = duplicate.due_date.date()
                        elif reminder_request or schedule_setup_request:
                            deadline_item = Deadline(
                                user_id=user_id, title=title, course_or_project="Personal",
                                due_date=datetime.datetime.combine(due_date, datetime.time(9, 0)),
                                estimated_hours=0, completed=False, priority=priority,
                                is_exam=bool(deadline_candidate.get("is_exam", False)),
                            )
                            db.add(deadline_item)
                            db.add(AuditLog(
                                user_id=user_id, action="create_chat_reminder", endpoint="/ask",
                                sources_accessed=["deadlines_key_dates"], timestamp=datetime.datetime.utcnow(),
                            ))
                            await db.commit()
                            deadline_reminder_created = True
                            plan_items_created.append({"id": deadline_item.id, "title": title, "date": due_date.isoformat(), "kind": "deadline"})
                        else:
                            deadline_offer_needed = True
            except (TimeoutError, KeyError, TypeError, ValueError) as exc:
                print(f"Could not save chat reminder: {exc}")
                if reminder_request:
                    spoken_message = "I couldn't save that reminder yet. What exact date should I use?"
                    date_followup_needed = True
    user_messages = [
        str(turn.get("content", ""))[:1200]
        for turn in req.recent_turns
        if str(turn.get("role", "")).lower() == "user" and turn.get("content")
    ][-7:] + [req.question[:1200]]
    period_confirmation = re.fullmatch(r"\s*(?:yes[, ]*)?(am|pm)[.! ]*\s*", req.question, re.I)
    assistant_asked_for_period = any(
        str(turn.get("role", "")).lower() == "assistant"
        and re.search(r"(?:are those times .*am or pm|did you mean .*\b(?:am|pm)\b)", str(turn.get("content", "")), re.I)
        for turn in req.recent_turns
    )
    clarified_period = period_confirmation.group(1).lower() if period_confirmation and assistant_asked_for_period else None
    availability_sources = [
        (message, _explicit_availability_window(f"{message.rstrip(' .!?')} {clarified_period}" if clarified_period and _ambiguous_availability_period(message) else message))
        for message in user_messages
    ]
    availability_sources = [(message, interval) for message, interval in availability_sources if interval]
    partial_starts = []
    partial_ends = []
    for message in user_messages:
        if _explicit_availability_window(message):
            continue
        start_bound, _ = _one_sided_availability(message)
        if start_bound is not None:
            partial_starts.append((message, start_bound))
    latest_start_bound = partial_starts[-1][1] if partial_starts else None
    for message in user_messages:
        if _explicit_availability_window(message):
            continue
        _, end_bound = _one_sided_availability(message, latest_start_bound)
        if end_bound is not None:
            partial_ends.append((message, end_bound))
    if not availability_sources and partial_starts and partial_ends:
        start_message, start_bound = partial_starts[-1]
        end_message, end_bound = partial_ends[-1]
        if end_bound > start_bound:
            merged_window = (start_bound, end_bound)
            availability_sources = [(start_message, merged_window)]
            if end_message != start_message:
                availability_sources.append((end_message, merged_window))
    availability_day_messages = [
        message for message in user_messages
        if re.search(r"\b(?:free|available|weekdays|weekends|daily|every day|all week|any day|next 7 days)\b", message, re.I)
        and _explicit_availability_days(message)
    ]
    allowed_plan_days = _explicit_availability_days(availability_day_messages[-1]) if availability_day_messages else None

    if schedule_setup_request and not date_followup_needed:
        if not bundle.enabled_sources.get("schedule_commitments", False):
            spoken_message = "I can turn this into timetable reminders, but Schedule & Commitments is switched off. You can turn it on in Privacy, then ask me to make the plan here in chat."
        elif allowed_plan_days and not availability_sources and any(_ambiguous_availability_period(message) for message in user_messages):
            spoken_message = "I have the days. Are those times AM or PM?"
        elif not availability_sources:
            noted = " I’ve also added the date to Reminders." if deadline_reminder_created else ""
            if partial_starts:
                bound = partial_starts[-1][1] % 1440
                label = datetime.time(bound // 60, bound % 60).strftime('%I:%M %p').lstrip('0')
                spoken_message = f"Got it — you’re usually home after {label}.{noted} What time would you like to finish, and which days should I plan around?"
            elif partial_ends:
                bound = partial_ends[-1][1] % 1440
                label = datetime.time(bound // 60, bound % 60).strftime('%I:%M %p').lstrip('0')
                spoken_message = f"Got it — you can work until {label}.{noted} What time can you start, and which days should I plan around?"
            else:
                spoken_message = f"I can map this out with you.{noted} What hours are you free over the next few days, which days should I use, and when do you usually focus best? For example, ‘Monday to Friday, 5–8 pm; I focus best around 6.’"
        elif not allowed_plan_days:
            spoken_message = "I have your free-time window. Which days does it apply to—weekdays, weekends, every day, or specific days?"
        else:
            try:
                local_today = datetime.date.fromisoformat(req.local_today) if req.local_today else datetime.datetime.now().date()
                async with asyncio.timeout(18.0):
                    schedule = await gemini_client.build_chat_schedule(
                        user_messages=user_messages,
                        local_today=local_today.isoformat(),
                        permitted_context=permitted_context,
                    )
                if schedule.get("needs_follow_up"):
                    spoken_message = str(schedule.get("question") or "What exact hours are you free, and which days should I use?")
                else:
                    validated = []
                    for block in schedule.get("blocks", [])[:8]:
                        if not isinstance(block, dict):
                            continue
                        quoted = " ".join(str(block.get("availability_quote", "")).split()).casefold()
                        source = next((
                            (message, interval) for message, interval in availability_sources
                            if quoted and quoted in " ".join(message.split()).casefold()
                        ), None)
                        if not source:
                            continue
                        try:
                            block_date = datetime.date.fromisoformat(str(block["date"]))
                            start_time = datetime.datetime.strptime(str(block["start_time"]), "%H:%M").time()
                            end_time = datetime.datetime.strptime(str(block["end_time"]), "%H:%M").time()
                        except (KeyError, TypeError, ValueError):
                            continue
                        start_minute = start_time.hour * 60 + start_time.minute
                        end_minute = end_time.hour * 60 + end_time.minute
                        available_start, available_end = source[1]
                        duration = end_minute - start_minute
                        if not (local_today <= block_date <= local_today + datetime.timedelta(days=14)):
                            continue
                        if allowed_plan_days and block_date.weekday() not in allowed_plan_days:
                            continue
                        if duration < 25 or duration > 120 or start_minute < available_start or end_minute > available_end:
                            continue
                        title = " ".join(str(block.get("title", "")).split())[:150]
                        if not title:
                            continue
                        block_words = set(re.findall(r"[a-z0-9]+", title.casefold()))
                        past_its_deadline = any(
                            not item.completed
                            and item.due_date.date() < block_date
                            and bool(block_words & set(re.findall(r"[a-z0-9]+", f"{item.title} {item.course_or_project}".casefold())))
                            for item in bundle.deadlines
                        )
                        if past_its_deadline:
                            continue
                        conflicts = False
                        for existing in bundle.timetable:
                            same_date = (
                                existing.specific_date.date() == block_date
                                if existing.specific_date else existing.day_of_week == block_date.strftime("%A")
                            )
                            if not same_date:
                                continue
                            try:
                                old_start = datetime.datetime.strptime(existing.start_time, "%H:%M").time()
                                old_end = datetime.datetime.strptime(existing.end_time, "%H:%M").time()
                            except ValueError:
                                continue
                            if start_time < old_end and end_time > old_start:
                                conflicts = True
                                break
                        if any(
                            item["date"] == block_date
                            and start_time < item["end_time"] and end_time > item["start_time"]
                            for item in validated
                        ):
                            conflicts = True
                        if not conflicts:
                            validated.append({"date": block_date, "start_time": start_time, "end_time": end_time, "title": title})

                    if not validated:
                        spoken_message = "I couldn't safely fit a timetable to those details yet. What exact days and hours should I use—for example, ‘Monday to Friday, 5–8 pm’?"
                    else:
                        validated.sort(key=lambda item: (item["date"], item["start_time"]))
                        schedule_goal_context = " ".join(user_messages).casefold()
                        placement_goal_context = bool(re.search(
                            r"\b(?:placement|placed|career goal|my goal is to get a job|my goal is to get a placement)\b",
                            schedule_goal_context,
                        ))
                        matching_existing_goal = next((
                            goal for goal in bundle.goals
                            if goal.status.casefold() != "completed"
                            and any(token in schedule_goal_context for token in re.findall(r"[a-z0-9]+", goal.title.casefold()) if len(token) > 3)
                        ), None)
                        schedule_goal = None
                        if bundle.enabled_sources.get("goals", False) and (placement_goal_context or matching_existing_goal):
                            try:
                                async with asyncio.timeout(12.0):
                                    goal_data = await gemini_client.build_goal_details(user_messages, local_today.isoformat())
                            except Exception as exc:
                                print(f"Could not build goal checklist from schedule plan: {exc}")
                                goal_data = {}
                            goal_title = " ".join(str(goal_data.get("title", "")).split())[:200] or (matching_existing_goal.title if matching_existing_goal else "Get a placement")
                            raw_goal_steps = goal_data.get("milestones", [])
                            goal_steps = [
                                {"title": " ".join(str(step.get("title", "")).split())[:120], "completed": False}
                                for step in raw_goal_steps[:5]
                                if isinstance(step, dict) and str(step.get("title", "")).strip()
                            ] if isinstance(raw_goal_steps, list) else []
                            if not goal_steps and placement_goal_context:
                                goal_steps = [
                                    {"title": "Choose the role you want to target", "completed": False},
                                    {"title": "Check the skills and requirements for that role", "completed": False},
                                    {"title": "Update your CV for the role", "completed": False},
                                    {"title": "Apply to a suitable opening", "completed": False},
                                    {"title": "Practise a few interview answers", "completed": False},
                                ]
                            if goal_steps:
                                schedule_goal = matching_existing_goal or next((goal for goal in bundle.goals if goal.title.casefold() == goal_title.casefold()), None)
                                goal_description = str(goal_data.get("description") or f"A practical step-by-step plan for {goal_title}.")[:2000]
                                if schedule_goal:
                                    completed_by_title = {str(step.get("title", "")).casefold(): bool(step.get("completed")) for step in normalize_goal_milestones(schedule_goal.milestones)}
                                    schedule_goal.title = goal_title
                                    schedule_goal.description = goal_description
                                    schedule_goal.milestones = [{**step, "completed": completed_by_title.get(step["title"].casefold(), False)} for step in goal_steps]
                                    schedule_goal.progress = round(100 * sum(step["completed"] for step in schedule_goal.milestones) / len(schedule_goal.milestones))
                                    schedule_goal.next_step = str(goal_data.get("next_step") or schedule_goal.next_step or goal_steps[0]["title"])[:500]
                                else:
                                    schedule_goal = Goal(
                                        user_id=user_id, title=goal_title, description=goal_description,
                                        status="active", progress=0,
                                        next_step=str(goal_data.get("next_step") or goal_steps[0]["title"])[:500],
                                        milestones=goal_steps,
                                    )
                                    db.add(schedule_goal)
                                db.add(AuditLog(user_id=user_id, action="save_chat_goal", endpoint="/ask", sources_accessed=["goals"], timestamp=datetime.datetime.utcnow()))
                        rows = [Timetable(
                            user_id=user_id,
                            day_of_week=item["date"].strftime("%A"),
                            specific_date=datetime.datetime.combine(item["date"], datetime.time.min),
                            start_time=item["start_time"].strftime("%H:%M"),
                            end_time=item["end_time"].strftime("%H:%M"),
                            activity_name=item["title"], location="", is_mandatory=True,
                        ) for item in validated]
                        db.add_all(rows)
                        db.add(AuditLog(
                            user_id=user_id, action="create_chat_plan", endpoint="/ask",
                            sources_accessed=["schedule_commitments"], timestamp=datetime.datetime.utcnow(),
                        ))
                        await db.commit()
                        if schedule_goal:
                            goals_updated.append({"id": schedule_goal.id, "title": schedule_goal.title, "progress": schedule_goal.progress, "milestones": schedule_goal.milestones or []})
                            goal_saved_during_schedule = True
                        plan_items_created = [{
                            "id": row.id, "title": row.activity_name,
                            "date": item["date"].isoformat(),
                            "start_time": row.start_time, "end_time": row.end_time,
                        } for row, item in zip(rows, validated)]
                        lines = ["Your plan is ready. I’ve added these time blocks to My Plan → This Week."]
                        if schedule_goal:
                            lines.append(f"I’ve also added {schedule_goal.title} to My Plan → Goals with checkable steps, so you can track your progress there.")
                        for item in (item for item in plan_items_created if item.get("start_time")):
                            day_label = datetime.date.fromisoformat(item["date"]).strftime("%a, %b %d").replace(" 0", " ")
                            start_label = datetime.datetime.strptime(item["start_time"], "%H:%M").strftime("%I:%M %p").lstrip("0")
                            end_label = datetime.datetime.strptime(item["end_time"], "%H:%M").strftime("%I:%M %p").lstrip("0")
                            lines.append(f"• {day_label}, {start_label}–{end_label} — {item['title']}")
                        lines.append("You can check them in My Plan. Turn on reminders in the bell if you’d like notifications.")
                        spoken_message = "\n".join(lines)
            except (TimeoutError, ValueError, TypeError) as exc:
                print(f"Could not build a chat plan safely: {exc}")
                spoken_message = "I've got your availability, but I couldn't finish creating the plan just now. Nothing new has been saved. Please try again in a moment."

    if reminder_request and deadline_reminder_created and not schedule_setup_request and not date_followup_needed:
        due_item = plan_items_created[0] if plan_items_created else None
        if due_item:
            spoken_message = f"Got it — I’ve added {due_item['title']} to your Reminders for {due_item['date']}. Browser notifications need to be enabled in the bell while Echo is open."
        else:
            spoken_message = "That reminder is already saved. You’ll find it in the Reminders bell."

    if deadline_offer_needed and not reminder_request and not schedule_setup_request and not date_followup_needed:
        day_label = deadline_offer_date.strftime('%B %d').replace(' 0', ' ') if deadline_offer_date else "that date"
        if deadline_offer_is_exam:
            spoken_message = f"Got it — your exam is on {day_label}. Would you like me to make a study timetable for it?"
        else:
            spoken_message = f"Got it — your {deadline_offer_title or 'assignment'} is due on {day_label}. Would you like me to add a reminder?"
    elif upcoming_commitment and deadline_reminder_created and not reminder_request and not schedule_setup_request and not date_followup_needed:
        if deadline_offer_is_exam and saved_deadline_date:
            day_label = saved_deadline_date.strftime('%B %d').replace(' 0', ' ')
            spoken_message = f"I’ve already got your exam on {day_label} in Reminders. Would you like me to make a study timetable for it?"
        else:
            spoken_message = "I’ve already got that assignment in Reminders."

    # Capture explicit goals in chat and keep their small action plan in My Plan → Goals.
    if not schedule_setup_request and not goal_saved_during_schedule and explicit_goal_statement and not goal_tracking_confirmation and not bundle.enabled_sources.get("goals", False):
        spoken_message = "I can save and track that goal in My Plan. Turn on Goals in Privacy, then tell me again and I’ll add it."
    elif not schedule_setup_request and not goal_saved_during_schedule and explicit_goal_statement and not goal_tracking_confirmation:
        # A stated aspiration is not permission to save it as a tracked goal.
        # Ask once; on confirmation the recent conversation supplies the goal.
        spoken_message = "That sounds meaningful. Would you like me to track this goal and help you work toward it with a few practical steps?"
    elif not schedule_setup_request and not goal_saved_during_schedule and (goal_tracking_confirmation or assistant_asked_goal):
        if not bundle.enabled_sources.get("goals", False):
            if explicit_goal_statement:
                spoken_message = "I can save and track that goal in My Plan. Turn on Goals in Privacy, then tell me again and I’ll add it."
        else:
            user_goal_messages = [
                str(turn.get("content", ""))[:1000]
                for turn in req.recent_turns
                if str(turn.get("role", "")).lower() == "user" and turn.get("content")
            ][-7:] + [req.question[:1000]]
            try:
                vague_win = bool(re.search(r"\b(?:i want to|my goal is to?|i'd like to)\s+(?:win|succeed|be successful|do well)\b", req.question, re.I))
                if vague_win:
                    goal_data = {"needs_follow_up": True, "follow_up_question": "What are you hoping to win—what event or outcome is it, and when does it happen?", "title": "Win", "description": req.question[:500], "milestones": []}
                else:
                    async with asyncio.timeout(12.0):
                        goal_data = await gemini_client.build_goal_details(user_goal_messages, local_today.isoformat())
                title = " ".join(str(goal_data.get("title", "")).split())[:200]
                follow_up = " ".join(str(goal_data.get("follow_up_question", "")).split())[:400]
                milestones = goal_data.get("milestones", [])
                if not isinstance(milestones, list):
                    milestones = []
                clean_milestones = [
                    {"title": " ".join(str(item.get("title", "")).split())[:120], "completed": False}
                    for item in milestones[:5] if isinstance(item, dict) and str(item.get("title", "")).strip()
                ]
                goal_date = None
                if goal_data.get("target_date"):
                    try:
                        parsed_date = datetime.date.fromisoformat(str(goal_data["target_date"]))
                        if local_today <= parsed_date <= local_today + datetime.timedelta(days=3650):
                            goal_date = datetime.datetime.combine(parsed_date, datetime.time.min)
                    except ValueError:
                        goal_date = None
                if title:
                    matching_goal = next((g for g in bundle.goals if g.title.casefold() == title.casefold()), None)
                    if not matching_goal and assistant_asked_goal:
                        matching_goal = next((g for g in bundle.goals if g.next_step and "tell echo what you’re hoping to win" in g.next_step.casefold()), None)
                    vague_goal = bool(goal_data.get("needs_follow_up"))
                    if matching_goal:
                        goal = matching_goal
                        if assistant_asked_goal and title:
                            goal.title = title
                        # Follow-up details refine the existing goal without resetting progress.
                        if goal_data.get("description"):
                            goal.description = str(goal_data["description"])[:2000]
                        if clean_milestones:
                            old_done = {str(x.get("title", "")).casefold(): bool(x.get("completed")) for x in normalize_goal_milestones(goal.milestones)}
                            goal.milestones = [{**m, "completed": old_done.get(m["title"].casefold(), False)} for m in clean_milestones]
                        if goal_date:
                            goal.target_date = goal_date
                        goal.next_step = str(goal_data.get("next_step") or goal.next_step or "")[:500] or None
                    else:
                        goal = Goal(
                            user_id=user_id, title=title,
                            description=str(goal_data.get("description") or req.question)[:2000],
                            status="active", target_date=goal_date, progress=0,
                            next_step=(str(goal_data.get("next_step") or "")[:500] or ("Tell Echo what you’re hoping to win, and when the event is." if vague_goal else None)),
                            milestones=[] if vague_goal else clean_milestones,
                        )
                        db.add(goal)
                    db.add(AuditLog(user_id=user_id, action="save_chat_goal", endpoint="/ask", sources_accessed=["goals"], timestamp=datetime.datetime.utcnow()))
                    await db.commit()
                    goals_updated.append({"id": goal.id, "title": goal.title, "progress": goal.progress, "milestones": goal.milestones or []})
                    if vague_goal:
                        spoken_message = follow_up or "What are you hoping to win—what event is it, and when does it happen?"
                    else:
                        summary = "I’ve added a small plan for that goal to My Plan → Goals."
                        if clean_milestones:
                            summary += " First steps: " + "; ".join(m["title"] for m in clean_milestones[:3]) + "."
                        if schedule_setup_request:
                            # The explicit preparation request is already being handled
                            # by the timetable flow above.
                            pass
                        elif not goal_date:
                            spoken_message = summary + " What date are you aiming for?"
                        else:
                            target_label = goal_date.strftime('%B %d, %Y').replace(' 0', ' ')
                            spoken_message = summary + f" I’ll track your progress there, with a target of {target_label}. Would you like me to make a preparation timetable too?"
            except Exception as exc:
                await db.rollback()
                print(f"Could not save chat goal: {exc}")
                if explicit_goal_statement:
                    spoken_message = "I understand that matters to you. What outcome are you hoping for, and when would you like to reach it?"

    # Learn only high-confidence, durable details from this user's explicit message.
    # The extractor cannot write anything unless its matching privacy category is on.
    saved_categories = []
    avoid_memory = bool(re.search(r"\b(?:don't|do not|never|stop)\s+(?:remember|save|store|keep this)\b|\bforget (?:this|that|what i said)\b", req.question, re.I))
    try:
        memory_categories = [category for category in CATEGORY_IDS if bundle.enabled_sources.get(category, False)]
        if not avoid_memory:
            async with asyncio.timeout(5.0):
                memory_candidates = await gemini_client.extract_important_memories(req.question, memory_categories)
        else:
            memory_candidates = []
        for candidate in memory_candidates:
            category = candidate["category"]
            if not bundle.enabled_sources.get(category, False):
                continue
            existing_rows = await db.execute(select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.category == category,
            ))
            existing = existing_rows.scalars().all()
            duplicate = next((row for row in existing if row.fact.casefold() == candidate["fact"].casefold()), None)
            if duplicate:
                duplicate.importance = max(duplicate.importance, candidate["importance"])
                duplicate.confidence = max(duplicate.confidence, candidate["confidence"])
                duplicate.updated_at = datetime.datetime.utcnow()
            else:
                db.add(UserMemory(user_id=user_id, **candidate))
            if category not in saved_categories:
                saved_categories.append(category)
        if saved_categories:
            db.add(AuditLog(
                user_id=user_id, action="save_chat_memory", endpoint="/ask",
                sources_accessed=saved_categories, timestamp=datetime.datetime.utcnow(),
            ))
            await db.commit()
            # Include the just-saved facts in the response context only on later turns.
    except Exception as exc:
        await db.rollback()
        saved_categories = []
        print(f"Could not save chat memories: {exc}")

    # Recommendations stay in the spoken reply; chat never renders path cards.
    options_out = []

    # Keep emotionally supportive replies conversational even when the provider
    # returns a statement with no invitation to continue. Do not append a second
    # question when Gemini already asked one.
    if detected_intent == "feeling_or_vent" and "?" not in spoken_message:
        if re.search(r"\b(?:spent|spend|bought|purchase|regret|money|clothes)\b", req.question, re.I):
            follow_up = "Would it help to check whether you can return it or make a plan from here?"
        elif re.search(r"\b(?:sad|lonely|miss|hurt|upset|cry)\b", req.question, re.I):
            follow_up = "Want to tell me what’s been weighing on you?"
        else:
            follow_up = "Want to tell me what’s making today feel so heavy?"
        spoken_message = f"{spoken_message.rstrip()} {follow_up}"

    # Paths are generated only after the message router has identified a planning request.
    paths_out: List[PathCardItem] = []
    has_paths = False
    offer_simulation = None

    if detected_intent == "decision_question" and not spoken_message:
        spoken_message = "I’m still getting to know what you’re deciding between. What are the options?"
    recommendation_match = re.search(
        r"^(?:my call is|my recommendation is|i recommend|i'd choose|i would choose)\s*:?[ ]*(.+?)(?:[.!?]\s|$)",
        spoken_message.strip(), re.I,
    ) if detected_intent == "decision_question" and not schedule_setup_request and not assistant_asked_for_availability else None
    recommended_choice = (
        decision_support["recommended_title"] if decision_support
        else recommendation_match.group(1).strip(" .,:;") if recommendation_match else None
    )
    why_summary = "I kept the priorities you shared in mind and left room to pause between them."
    if has_real_deadlines and has_real_timetable:
        why_summary = "I used the key dates and commitments you shared, and left room for both priorities."
    elif has_real_deadlines:
        why_summary = "I used the key dates you shared to keep both priorities moving."
    elif has_real_timetable:
        why_summary = "I left space around the commitments you shared."
    if decision_support:
        chosen = decision_support["items"][decision_support["recommended_index"]]
        why_summary = f"I’d put {chosen['title']} first based on its due date, saved priority, and estimated effort. The percentages in my reply are relative priority shares, not odds of success."

    return AskResponse(
        user_id=user_id,
        badge=gemini_out.get("badge", f"{primary_twin.capitalize()} style"),
        primary_twin=primary_twin,
        message=spoken_message,
        provider_status=gemini_out.get("provider_status", "offline"),
        why_summary=why_summary,
        answer=spoken_message,
        deadline_risk_alert=gemini_out.get("deadline_risk_alert", deadline_risk_summary),
        ml_insights=MLInsights(
            on_time_probability=ml_res["on_time_probability"],
            label="prototype indicator",
            predicted_hours=ml_res["predicted_hours"],
            estimated_hours=ml_res["estimated_hours"],
            why_factors=why_factors_out,
            metrics_report=ml_res.get("metrics_report"),
            model_source=ml_res.get("model_source", "synthetic_seed_model"),
        ),
        options=options_out,
        sources_used=bundle.accessed_sources,
        intent=detected_intent,
        style_weights=style_weights,
        primary_style=primary_style,
        secondary_style=secondary_style,
        # Offer the other styles only after Echo has actually named a choice.
        # Clarification questions (especially plan availability questions) are
        # not recommendations and should not get decision feedback controls.
        show_other_voices=bool(recommended_choice and detected_intent == "decision_question" and not schedule_setup_request and not assistant_asked_for_availability),
        decision_support=decision_support,
        recommended_choice=recommended_choice,
        has_paths=has_paths,
        offer_simulation=offer_simulation,
        paths=paths_out,
        attachment_looks_like_schedule=bool(gemini_out.get("attachment_looks_like_schedule", False)),
        extracted_items=gemini_out.get("extracted_items", []),
        memories_saved=saved_categories,
        plan_items_created=plan_items_created,
        goals_updated=goals_updated,
        timestamp=datetime.datetime.utcnow()
    )
