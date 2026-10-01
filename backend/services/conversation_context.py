"""Small, deterministic helpers for carrying an active chat clarification forward."""
import re
from typing import Optional


_PLACEMENT_QUESTION = re.compile(
    r"\bplacement\b.*\b(?:job\s+)?role\b|\b(?:job\s+)?role\b.*\bplacement\b",
    re.IGNORECASE,
)
_TARGET_DATE = re.compile(
    r"\b(?:today|tomorrow|next\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"in\s+\d+\s+(?:days?|weeks?|months?)|"
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|20\d{2})\b|"
    r"\b\d{1,2}(?:st|nd|rd|th)?(?:[/-]\d{1,2}(?:[/-]\d{2,4})?)?\b",
    re.IGNORECASE,
)

_SPELLING_WORDS = ("necessary", "resilient", "accommodate", "conscientious", "rhythm")


def spelling_quiz_start_reply(question: str, recent_turns: list[dict]) -> Optional[str]:
    """Resume an explicitly requested spelling lesson or a confirmed next round."""
    text = " ".join((question or "").casefold().split())
    topic = bool(re.search(r"\b(?:spelling\s*bee|spell\s*b)\b", text))
    wants_to_start = bool(re.search(r"\b(?:ready|start|begin|practice|practise|learn|continue|resume)\b", text))
    latest_assistant = next((
        str(turn.get("content", "")) for turn in reversed(recent_turns or [])
        if str(turn.get("role", "")).lower() == "assistant"
    ), "")
    confirms_next = bool(
        re.fullmatch(r"\s*(?:yes|yeah|yep|sure|okay|ok|please|let's go|go ahead)[.! ]*\s*", text)
        and re.search(r"\b(?:ready for|try|start) the next word\b", latest_assistant, re.I)
    )
    if not ((topic and wants_to_start) or confirms_next):
        return None

    assistant_history = " ".join(
        str(turn.get("content", "")) for turn in recent_turns or []
        if str(turn.get("role", "")).lower() == "assistant"
    )
    used = {word.casefold() for word in re.findall(r"\b(?:first|next) word\s*[:\-]\s*([a-z][a-z'-]*)", assistant_history, re.I)}
    word = next((candidate for candidate in _SPELLING_WORDS if candidate not in used), _SPELLING_WORDS[0])
    return f"Let's pick up your spelling practice. Next word: {word}. How do you spell it?"


def spelling_quiz_followup_reply(question: str, recent_turns: list[dict], style: str = "rational") -> Optional[str]:
    """Answer a spelling submission when the current chat is in a word quiz."""
    turns = recent_turns or []
    latest_assistant = next(
        (turn for turn in reversed(turns) if str(turn.get("role", "")).lower() == "assistant"),
        None,
    )
    if not latest_assistant:
        return None

    latest_text = str(latest_assistant.get("content", ""))
    if not re.search(r"\bhow do you spell\b", latest_text, re.I):
        return None

    target_match = re.search(r"\b(?:first|next)\s+word\s*[:\-]\s*([a-z][a-z'-]*)", latest_text, re.I)
    if not target_match:
        target_match = re.search(r"\bhow do you spell\s+([a-z][a-z'-]*)", latest_text, re.I)
        if target_match and target_match.group(1).casefold() in {"it", "that", "this", "word"}:
            return None
    if not target_match:
        return None

    target = target_match.group(1).casefold()
    submitted = " ".join((question or "").strip().split()).casefold()
    submitted = re.sub(r"^(?:it's|it is|the word is|the spelling is|spelled as)\s+", "", submitted)
    if len(submitted) > 64 or not re.fullmatch(r"[a-z\s'-]+[.!?]?", submitted):
        return None
    submitted_letters = re.sub(r"[^a-z]", "", submitted)
    spelling = "-".join(target.upper())

    if submitted_letters == target:
        return {
            "emotional": f"Yes, that's it! “{target}” is spelled {spelling}. You got it—want to try the next word?",
            "rational": f"Correct — “{target}” is spelled {spelling}. Ready for the next word?",
            "ambitious": f"You nailed it: “{target}” is {spelling}. Ready to take on the next word?",
        }.get((style or "rational").casefold(), f"Correct — “{target}” is spelled {spelling}. Ready for the next word?")

    return {
        "emotional": f"Close, and it’s okay to try again. “{target}” is spelled {spelling}. Want another go?",
        "rational": f"Close — “{target}” is spelled {spelling}. Want to try it once more?",
        "ambitious": f"Almost. “{target}” is spelled {spelling}. Give it one more try?",
    }.get((style or "rational").casefold(), f"Close — “{target}” is spelled {spelling}. Want to try it once more?")


def placement_role_followup_reply(question: str, recent_turns: list[dict]) -> Optional[str]:
    """Respond to a short answer to Echo's placement-role clarification.

    Recent chat is in-session context and is intentionally independent of saved-memory
    permissions. Nothing is written to the user's long-term memory by this helper.
    """
    latest_assistant = next(
        (turn for turn in reversed(recent_turns or []) if str(turn.get("role", "")).lower() == "assistant"),
        None,
    )
    assistant_text = str((latest_assistant or {}).get("content", ""))
    if not _PLACEMENT_QUESTION.search(assistant_text):
        return None

    detail = " ".join((question or "").split()).strip(" .!\t\r\n")
    if not detail or "?" in detail or len(detail) > 120 or len(detail.split()) > 14:
        return None

    if _TARGET_DATE.search(detail):
        return (
            f'Got it — I’ll keep “{detail}” in mind as your placement target for this conversation. '
            "What would help most right now: finding openings, improving your CV, or interview practice?"
        )

    return (
        f"Got it — {detail}. I’ll keep that role in mind as we talk about placement. "
        "Do you have a target date or application deadline?"
    )
