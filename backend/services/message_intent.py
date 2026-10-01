"""Lightweight, deterministic intent classification for chat routing."""
import re

MESSAGE_TYPES = {
    "greeting_or_intro", "small_talk", "feeling_or_vent",
    "question_or_advice", "decision_question", "goal_or_money", "personal_fact_lookup", "world_fact_lookup", "mixed_fact_lookup", "crisis",
}

_PERSONAL_LOOKUP = re.compile(r"\b(?:i told you|i shared|do you know|do i have my|what do you know about my|did i say|what did i (?:say|choose|decide|pick)|when is|when's|what time is|where is|what are my|what's my|what is my|have i shared|have i told you|what did i choose|what did i decide)\b", re.I)

# Explicit preparation requests start the availability → timetable flow. Merely
# mentioning a due date is handled as a reminder, not a schedule request.
_EXPLICIT_PLAN_REQUEST = re.compile(
    r"\b(?:make|create|build|draft|prepare|put together)\s+(?:me\s+)?(?:a\s+)?plan\b"
    r"|\b(?:help me|can you|could you|please)\s+(?:to\s+)?plan\b"
    r"|\bplan out\b"
    r"|\bplan me\b"
    r"|\b(?:help me|can you|could you|please|i want to|i'd like to|i need to)\s+(?:prepare|study|practice|get ready)\b"
    r"|\bprepare me for\b",
    re.I,
)


def is_explicit_plan_request(message: str) -> bool:
    """Return true only when the user asks Echo to create or arrange a plan."""
    return bool(_EXPLICIT_PLAN_REQUEST.search(message or ""))

def world_fact_subtype(message: str) -> str | None:
    text = (message or "").lower()
    if re.search(r"\b(?:weather|rain|raining|temperature|forecast)\b", text):
        return "weather"
    if re.search(r"\b(?:holiday|holidays|public holiday|gazetted)\b", text):
        return "holidays_calendar"
    if re.search(r"\b(?:news|latest|breaking|current events|today's headlines)\b", text):
        return "news_current_events"
    if re.search(r"\b(?:open now|opening hours|business hours|is .+ open|events near|what's on)\b", text):
        return "local_info"
    if re.search(r"\b(?:score|who won|match result|standings|game last night)\b", text):
        return "other_live"
    if re.search(r"\b(?:today's date|what date is it|what day is it|current time|what time is it|today today)\b", text):
        return "date_time"
    if re.search(r"\b(?:latest|price of|exchange rate|stock price|president|prime minister|who is the ceo|law in force)\b", text):
        return "general_fact"
    if re.search(r"\b(?:what(?:'s| is) happening|what(?:'s| is) going on)\s+right now\b|\b(?:current|currently)\s+(?:price|weather|news|president|prime minister|ceo|law|exchange rate)\b", text):
        return "general_fact"
    return None

def personal_fact_category(message: str) -> str | None:
    text = (message or "").lower()
    if not _PERSONAL_LOOKUP.search(text):
        return None
    if re.search(r"\b(?:assignment|deadline|due|exam|test|milestone|renewal|key date)\b", text):
        return "deadlines_key_dates"
    if re.search(r"\b(?:meeting|appointment|schedule|calendar|shift|class|call|timetable|commitment)\b", text):
        return "schedule_commitments"
    if re.search(r"\b(?:goals?|targets?|aims?|progress)\b", text):
        return "goals"
    if re.search(r"\b(?:decision|choice|chose|decided?|option)\b", text):
        return "decision_history"
    if re.search(r"\b(?:spend|spent|spending|money|budget|purchase|bought|saving|save)\b", text):
        return "spending_money"
    if re.search(r"\b(?:routine|habit|preference|prefer|like|rest|work style)\b", text):
        return "routines_preferences"
    if re.search(r"\b(?:focus|work pattern|energy|concentrat)\b", text):
        return "focus_work_patterns"
    # Personal possession phrasing with a lookup question but no clear topic.
    return "routines_preferences" if re.search(r"\b(?:what|when|where|do you know|did i)\b", text) else None

_INTRO = re.compile(r"\b(?:i\s*am|i'm|im|iam)\s+([a-z][a-z'-]{0,29})\b", re.IGNORECASE)
_FEELING = re.compile(
    r"\b(?:i(?:'m| am| feel| am feeling)|im|iam|feeling)\s+(?:so\s+|really\s+|pretty\s+)?"
    r"(?:stressed|sad|tired|exhausted|anxious|worried|overwhelmed|excited|happy|proud|relieved|angry|lonely|burned out|burnt out|regretful)\b",
    re.IGNORECASE,
)
_NOT_NAMES = {"so", "very", "really", "pretty", "a", "an", "the", "fine", "okay", "ok", "good", "great", "ready", "here", "doing", "feeling", "happy", "proud", "relieved", "tired", "stressed", "sad", "anxious", "worried", "overwhelmed", "excited", "angry", "lonely", "exhausted", "burned", "burnt", "mad"}


def classify_by_keywords(message: str) -> str | None:
    text = " ".join((message or "").strip().split())
    lower = text.lower()
    if not text:
        return "question_or_advice"

    if personal_fact_category(text):
        if world_fact_subtype(text):
            return "mixed_fact_lookup"
        return "personal_fact_lookup"
    if world_fact_subtype(text):
        return "world_fact_lookup"

    # Clear decisions route to analysis; the rest stay in conversational chat.
    planning_terms = (
        "what if", "help me decide", "how should i prioritize", "how should i prioritise",
        "prioritise", "prioritize", "plan my", "plan for", "make a plan", "create a plan",
        "help me plan", "map it out", "show me the paths", "choose between", "compare these",
        "which path", "balance both", "workload", "schedule my", "organize my", "organise my",
        "what should i do first", "what do i work on first", "which is more important",
        "what is more important", "what's most important", "what is most important",
        "should i focus", "what should i do about my", "test and assignment", "exam and assignment",
    )
    if any(term in lower for term in planning_terms):
        return "decision_question"
    if re.search(r"\b(?:versus|vs\.?|torn between|choose between|choice between|either .+ or|trade[- ]off)\b", lower):
        return "decision_question"
    if re.search(r"\b(?:deadline|test|exam|assignment|commitment|task)\b", lower) and any(
        cue in lower for cue in ("what should", "how should", "which", "help me", "what do i do", "more important", "most important", "importance", "do first")
    ):
        return "decision_question"
    mentions_competing_work = bool(re.search(
        r"\b(?:exam|test|assessment|assignment|project|competition|deadline|task|commitment)s?\b", lower
    ))
    asks_what_matters = bool(re.search(
        r"\b(?:important|priority|priorities|prioritise|prioritize|matters most|focus on first|do first)\b", lower
    ))
    if mentions_competing_work and asks_what_matters and (
        "?" in text or re.search(r"^(?:is|are|which|what|how|should|can|could)\b", lower)
    ):
        return "decision_question"
    intro = _INTRO.search(text)
    introduces_name = bool(intro and intro.group(1).lower() not in _NOT_NAMES)
    greeting = re.match(r"^(?:hi|hello|hey|heya|yo|good morning|good afternoon|good evening)\b", lower)
    if introduces_name and (greeting or len(text.split()) <= 6):
        return "greeting_or_intro"
    if greeting and len(text.split()) <= 5:
        return "greeting_or_intro"
    if lower in {"who are you", "who are you?", "what is your name", "what is your name?", "tell me about yourself"}:
        return "greeting_or_intro"
    if _FEELING.search(text) or any(term in lower for term in ("tired of everything", "rough day", "i regret", "feeling down")):
        return "feeling_or_vent"
    if any(term in lower for term in (
        "how are you", "how's it going", "what's up", "thank you", "thanks",
        "tell me a joke", "make me laugh", "just chatting", "good to see you",
    )):
        return "small_talk"
    if re.search(r"\b(?:spend|spent|spending|save|saving|budget|money|bought|purchase|goal|goals)\b", lower):
        return "goal_or_money"

    if re.search(r"\b(?:what if|deadline|prioriti[sz]e|workload|schedule|plan|compare paths|more important|most important)\b", lower):
        if any(word in lower for word in ("what", "how", "should", "can", "help", "which", "could")):
            return "decision_question"
    if "?" in text or re.match(r"^(?:what|how|why|when|where|who|can|could|would|should|do|does|is|are)\b", lower):
        return "question_or_advice"
    return None


def introduced_name(message: str) -> str | None:
    match = _INTRO.search(message or "")
    if not match or match.group(1).lower() in _NOT_NAMES:
        return None
    raw_name = match.group(1)
    return raw_name[:1].upper() + raw_name[1:].lower()
