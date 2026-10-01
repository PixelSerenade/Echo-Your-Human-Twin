import json
import re

import pytest

from backend.llm.gemini_client import gemini_client


@pytest.mark.parametrize(
    ("message", "question"),
    [
        ("Certainly, let's work through this. We can start with what matters most.", "What should I do?"),
        ("You have a 72% chance of finishing. Let's protect your focus.", "Can I finish?"),
        ("- Finish the draft\n- Review your notes", "What should I do?"),
        ("Does that feel right? Should we try something else?", "What should I do?"),
        ("Your project is high risk. Let's make a calmer plan.", "What should I do?"),
        ("The model gives this a strong probability. Let's follow it.", "What should I do?"),
        ("I feel worried for you. Let's slow this down.", "What should I do?"),
        ("Start with the assignment. Take a pause. Review Maths. Pack your bag. Go to sleep.", "What should I do?"),
        ("Giving your full attention to a single commitment may look simpler, but leaving the other untouched could make the next stretch harder.", "iam sad"),
    ],
)
def test_robotic_pattern_detector_rejects_invalid_chat(message, question):
    assert gemini_client._is_spoken_message_safe(message, question) is False


@pytest.mark.parametrize(
    ("message", "question"),
    [
        (
            "That sounds like a lot to hold at once. Let's choose the task with the least flexibility and make its next step smaller.",
            "I'm overwhelmed. What should I do?",
        ),
        (
            "Your exam is due on October 5, so let's start there and leave room for the project afterward.",
            "Which is more important?",
        ),
        (
            "- Finish the draft\n- Review it tomorrow\n- Send it by Friday",
            "Make me a plan for this week.",
        ),
        (
            "This opportunity sounds exciting, and it deserves a real look. Check what it would ask you to pause before you commit.",
            "I got offered a new role.",
        ),
        (
            "- Open the draft\n- Finish the introduction\n- Take a proper pause",
            "Give me a plan with steps.",
        ),
    ],
)
def test_robotic_pattern_detector_accepts_natural_chat(message, question):
    assert gemini_client._is_spoken_message_safe(message, question) is True


def test_numbers_stay_out_of_message_and_remain_in_why_payload():
    normalized = gemini_client._normalize_spoken_message(
        {
            "message": "You have a 38% probability and need 12 hours, so this is high risk.",
            "deadline_risk_alert": "Maths test is due in 2 days.",
            "options": [],
        },
        primary_twin="rational",
        question="Can I finish my Maths revision in time?",
    )
    why_payload = {
        "on_time_probability": 0.38,
        "predicted_hours": 12.0,
        "why_factors": [{"feature": "days_until_deadline", "importance_pct": 44.2}],
    }

    assert re.search(r"\d|%", normalized["message"]) is None
    assert re.search(r"\d", json.dumps(why_payload)) is not None
    assert why_payload["on_time_probability"] == 0.38
    assert why_payload["predicted_hours"] == 12.0


def test_stale_generic_plan_draft_is_replaced_with_shared_due_items():
    context = (
        "- [Assessment] Exam (Personal) | Date: 2030-10-05 00:00 | Estimated Effort: 2.0h | Priority: high | Status: Pending\n"
        "- [Task or milestone] Project (Personal) | Date: 2030-10-08 00:00 | Estimated Effort: 3.0h | Priority: medium | Status: Pending"
    )
    result = gemini_client._normalize_spoken_message(
        {"message": "Giving your full attention to a single commitment may look simpler, but leaving the other untouched could make the next stretch harder."},
        primary_twin="rational",
        question="Make me a plan for my exam and project.",
        permitted_context=context,
    )

    assert "Exam" in result["message"] and "Oct 5" in result["message"]
    assert "Project" in result["message"]
