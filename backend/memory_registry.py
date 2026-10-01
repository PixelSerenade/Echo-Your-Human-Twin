"""Persona-aware memory categories and copy, kept in one backend registry."""

PERSONAS = {
    "student": {"label": "Student", "description": "Classes, coursework, and life around study.", "simulator": {"progress": "Study Progress", "goals": "Goal Progress"}},
    "working_professional": {"label": "Working professional", "description": "Work, meetings, and life beyond work.", "simulator": {"progress": "Work Progress", "goals": "Goal Progress"}},
    "freelancer_founder": {"label": "Freelancer or founder", "description": "Projects, clients, and building something of your own.", "simulator": {"progress": "Project Progress", "goals": "Business Progress"}},
    "caregiver_parent": {"label": "Caregiver or parent", "description": "Care routines, family commitments, and your own goals.", "simulator": {"progress": "Personal Progress", "goals": "Goal Progress"}},
    "other": {"label": "Something else", "description": "A flexible setup for the shape of your days.", "simulator": {"progress": "Personal Progress", "goals": "Goal Progress"}},
}

_ALL = list(PERSONAS)
CATEGORIES = {
    "schedule_commitments": {"title": "Schedule & Commitments", "description": "Recurring activities, shifts, meetings, appointments, and other commitments.", "hint": {"student": "Examples: classes, appointments, personal plans", "working_professional": "Examples: meetings, shifts, appointments", "freelancer_founder": "Examples: client calls, project time, appointments", "caregiver_parent": "Examples: care routines, appointments, family plans", "other": "Examples: tasks, meetings, appointments"}, "source": "timetable", "legacy": "timetable", "default_on": ["student", "working_professional", "freelancer_founder", "caregiver_parent"]},
    "deadlines_key_dates": {"title": "Deadlines & Key Dates", "description": "Due dates, milestones, appointments, and other important dates.", "hint": {"student": "Examples: project due dates, appointments, milestones", "working_professional": "Examples: deliverables, appointments, key dates", "freelancer_founder": "Examples: client deadlines, launch dates, milestones", "caregiver_parent": "Examples: appointments, renewals, family dates", "other": "Examples: due dates, appointments, milestones"}, "source": "deadlines", "legacy": "deadlines", "default_on": ["student", "working_professional", "freelancer_founder", "caregiver_parent"]},
    "focus_work_patterns": {"title": "Focus & Work Patterns", "description": "Patterns in focus, energy, and how different activities go.", "hint": {"student": "Examples: focused work sessions, energy patterns", "working_professional": "Examples: deep work, energy patterns", "freelancer_founder": "Examples: creative time, project focus", "caregiver_parent": "Examples: personal focus time, energy patterns", "other": "Examples: work sessions, focus, energy patterns"}, "source": "study_history", "legacy": "study_history", "default_on": ["student", "working_professional", "freelancer_founder"]},
    "routines_preferences": {"title": "Routines & Preferences", "description": "Rest, routines, planning preferences, and working style.", "hint": {p: "Examples: routines, planning preferences, working style" for p in _ALL}, "source": "preferences", "legacy": "preferences", "default_on": ["student", "working_professional", "freelancer_founder", "caregiver_parent"]},
    "goals": {"title": "Goals", "description": "What you are working toward and the progress you choose to share.", "hint": {p: "Examples: personal goals, milestones, progress" for p in _ALL}, "source": "goals", "legacy": None, "default_on": ["student", "working_professional", "freelancer_founder", "caregiver_parent"]},
    "decision_history": {"title": "Decision History", "description": "Past choices and feedback used to adapt recommendations.", "hint": {p: "Examples: choices, feedback, what worked for you" for p in _ALL}, "source": "decision_history", "legacy": "decision_history", "default_on": ["student", "working_professional", "freelancer_founder", "caregiver_parent"]},
    "mood_tone": {"title": "Mood & Tone", "description": "Optional wording cues used to tailor the tone of replies.", "hint": {p: "Examples: tone and communication preferences" for p in _ALL}, "source": None, "legacy": "mood_tone", "default_on": [], "always_opt_in": True},
    "spending_money": {"title": "Spending & Money", "description": "Optional financial details you choose to share for relevant replies.", "hint": {p: "Examples: spending preferences, budget goals" for p in _ALL}, "source": None, "legacy": None, "default_on": [], "always_opt_in": True},
}

LEGACY_TO_CATEGORY = {v["legacy"]: k for k, v in CATEGORIES.items() if v.get("legacy")}
LEGACY_TO_CATEGORY.update({"timetable": "schedule_commitments", "deadlines": "deadlines_key_dates", "study_history": "focus_work_patterns", "preferences": "routines_preferences"})
CATEGORY_IDS = list(CATEGORIES)
PERMISSION_WORDING_VERSION = "permissions-v1"


def _persona_or_other(persona):
    return persona if persona in PERSONAS else "other"


def defaults_for(persona: str) -> dict[str, bool]:
    persona = _persona_or_other(persona)
    return {key: persona in value["default_on"] for key, value in CATEGORIES.items()}


def registry_for(persona: str = None) -> dict:
    persona = _persona_or_other(persona)
    return {
        "personas": [{"id": key, **value} for key, value in PERSONAS.items()],
        "persona": persona,
        "categories": [{"id": key, "title": item["title"], "display_name": item["title"], "description": item["description"], "hint": item["hint"][persona], "default_enabled": persona in item["default_on"], "always_opt_in": item.get("always_opt_in", False)} for key, item in CATEGORIES.items()],
        "defaults": defaults_for(persona),
        "simulator_labels": {"progress": PERSONAS[persona]["simulator"]["progress"], "goals": PERSONAS[persona]["simulator"]["goals"], "energy": "Energy", "happiness": "Happiness", "free_time": "Free Time"},
        "example_prompts": {
            "student": ["Help me plan my week around classes", "What should I focus on before my next deadline?"],
            "working_professional": ["Help me plan around my meetings", "How can I protect time for focused work?"],
            "freelancer_founder": ["Help me balance client work and my own project", "What milestone should I tackle next?"],
            "caregiver_parent": ["Help me make room for rest in a busy week", "How can I plan around family commitments?"],
            "other": ["Help me plan my time", "What would make this week feel more manageable?"],
        }[persona],
    }
