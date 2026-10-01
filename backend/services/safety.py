"""Deterministic safety routing for crisis, crime, and health-related messages."""
import re

_ACTIVE = [
    r"\b(?:i(?:'m| am| will|'ll|m gonna| am going to| might)|tonight|right now)\b.{0,55}\b(?:kill myself|end my life|hurt myself|harm myself|take my life|suicide|self[- ]?harm)\b",
    r"\b(?:i want to die|i want to end it|i am going to die|i'm going to die|i might kill myself)\b",
    r"\b(?:i want to hurt myself|i will hurt myself|i'm going to hurt myself|i am going to hurt myself|i want to unalive myself|i want to end it all)\b",
    r"\b(?:i (?:cut|hurt|poisoned|overdosed) myself|i have (?:cut|hurt|poisoned|overdosed) myself)\b",
    r"\b(?:i have overdosed|i overdosed|i have taken an overdose)\b",
    r"\b(?:suicide plan|plan to kill myself|plan to end my life|means to kill myself)\b",
    r"(?:ನಾನು\s*ಆತ್ಮಹತ್ಯೆ\s*ಮಾಡಿಕೊಳ್ಳುತ್ತೇನೆ|ನನ್ನನ್ನು\s*ನಾನೇ\s*ಕೊಲ್ಲುತ್ತೇನೆ)",
    r"(?:मैं\s*(?:खुदकुशी|आत्महत्या)\s*करने\s*वाला\s*हूँ|मैं\s*अपनी\s*जान\s*ले\s*लूँगा)",
    r"\b(?:mai|main)\s+(?:apni\s+)?jaan\s+(?:dene|lene)\s+wala\s+hoon\b",
]
_PASSIVE = [
    r"\b(?:i can't do this anymore|i cannot do this anymore|what's the point|what is the point|i wish i (?:wasn't|were not) here|i don't want to be here|i don't want to live|i can't go on|i cannot go on|i feel like giving up)\b",
    r"\b(?:past attempt|i tried to kill myself(?: before)?|self[- ]?harm urges|urges to hurt myself|i am suicidal|i feel suicidal|i feel like hurting myself|i feel like self[- ]?harming|i want to self[- ]?harm)\b",
    r"(?:जीने का मन नहीं|मैं जीना नहीं चाहता|मैं जीना नहीं चाहती|अब और नहीं सह सकता|अब और नहीं सह सकती)",
    r"(?:ಬದುಕಲು\s*ಇಷ್ಟವಿಲ್ಲ|ಇನ್ನು\s*ಸಹಿಸಲಾಗುತ್ತಿಲ್ಲ)",
]
_INFORMATIONAL = re.compile(r"\b(?:warning signs|statistics|research|paper|school project|study|prevention|what are signs|explain|information about)\b", re.I)
_SUICIDE_TOPIC = re.compile(r"\b(?:suicide|suicidal|self[- ]?harm|killing myself)\b|ಆತ್ಮಹತ್ಯೆ|आत्महत्या|खुदकुशी", re.I)
_FRIEND_RISK = re.compile(r"\b(?:my friend|someone i know|my brother|my sister|my child|my partner)\b.{0,70}\b(?:want(?:s|ed)? to die|suicidal|kill themselves|self[- ]?harm|hurt themselves)\b", re.I)
_ESCALATION_CANDIDATE = re.compile(r"\b(?:life|live|gone|disappear|can't go on|cannot go on|give up|hopeless|worthless|can't do this|cannot do this|end it|hurt|harm|die|suicid|self[- ]?harm)\b|आत्महत्या|जीना|ಬದುಕು", re.I)


def needs_crisis_escalation_check(message: str) -> bool:
    return bool(_ESCALATION_CANDIDATE.search(message or ""))


def crisis_tier(message: str) -> tuple[int, bool] | None:
    text = " ".join((message or "").lower().split())
    if any(re.search(pattern, text, re.I) for pattern in _ACTIVE):
        return 1, False
    if _FRIEND_RISK.search(text):
        return 1, True
    if _INFORMATIONAL.search(text) and _SUICIDE_TOPIC.search(text):
        return 3, False
    if any(re.search(pattern, text, re.I) for pattern in _PASSIVE):
        return 2, False
    if _SUICIDE_TOPIC.search(text) and not re.search(r"\b(?:suicide prevention|warning signs|research on suicide)\b", text):
        return 2, False
    return None


_CRIME_VICTIM = re.compile(r"\b(?:i was scammed|someone hacked me|my account was hacked|i was robbed|someone is stalking me|i received a threat|i'm being threatened)\b", re.I)
_CRIME_REQUEST = re.compile(
    r"\b(?:how (?:do i|can i|to) (?:hack|steal|defraud|scam|stalk|blackmail|poison|hurt|kill|attack)|"
    r"how to commit (?:fraud|theft)|how to make (?:meth|cocaine|fentanyl|poison)|build (?:a weapon|an explosive)|"
    r"make (?:a bomb|an explosive|illegal drugs)|hide (?:a crime|evidence|a body)|get away with (?:murder|theft|fraud)|"
    r"revenge on (?:him|her|them)|break into (?:someone's|my neighbor's)|bypass (?:someone's|the) password)\b", re.I
)


def crime_intent(message: str) -> str | None:
    if _CRIME_VICTIM.search(message or ""):
        return "victim_support"
    if _CRIME_REQUEST.search(message or ""):
        return "crime_or_harm"
    return None


def is_health_question(message: str) -> bool:
    return bool(re.search(r"\b(?:symptoms?|diagnos(?:e|is)|diseases?|illness|medicine|medication|dosage|treatment|side effects?|infection|pain|fever|rash|doctor|medical)\b", message or "", re.I))


def has_unsafe_safety_detail(message: str) -> bool:
    return bool(re.search(r"\b(?:method|means|lethality|lethal|dose|dosage|step[- ]by[- ]step|how to (?:kill|die|poison|make)|suicide method|weapon|overdose amount)\b", message or "", re.I))
