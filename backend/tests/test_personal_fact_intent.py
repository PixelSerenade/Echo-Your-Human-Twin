import pytest

from backend.services.message_intent import classify_by_keywords, personal_fact_category


@pytest.mark.parametrize(("question", "category"), [
    ("Do you know when my maths assignment is due?", "deadlines_key_dates"),
    ("What time is my client meeting?", "schedule_commitments"),
    ("What are my goals?", "goals"),
    ("What did I decide about the move?", "decision_history"),
    ("What's my budget?", "spending_money"),
    ("Do you know my usual routine?", "routines_preferences"),
    ("What do you know about my focus pattern?", "focus_work_patterns"),
])
def test_personal_fact_questions_map_to_memory_categories(question, category):
    assert personal_fact_category(question) == category
    assert classify_by_keywords(question) == "personal_fact_lookup"


def test_ordinary_planning_question_is_not_a_personal_fact_lookup():
    question = "What should I do about my test and assignment?"
    assert personal_fact_category(question) is None
    assert classify_by_keywords(question) == "decision_question"


def test_non_lookup_personal_statement_is_not_a_personal_fact_lookup():
    assert personal_fact_category("My meeting went well today") is None
