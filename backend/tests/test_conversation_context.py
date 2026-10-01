from backend.services.conversation_context import placement_role_followup_reply, spelling_quiz_followup_reply, spelling_quiz_start_reply
from backend.services.message_intent import classify_by_keywords, world_fact_subtype


def test_placement_role_answer_is_carried_forward_and_only_missing_date_is_asked():
    turns = [
        {"role": "user", "content": "I want to be placed"},
        {
            "role": "assistant",
            "content": "What specific placement or job role are you targeting, and when is your application deadline or target date?",
        },
    ]

    reply = placement_role_followup_reply("Software engineer", turns)

    assert reply is not None
    assert "Software engineer" in reply
    assert "target date or application deadline" in reply
    assert "what role" not in reply.lower()
    assert "enough to go on" not in reply.lower()


def test_placement_followup_does_not_repeat_date_when_user_provides_one():
    turns = [{
        "role": "assistant",
        "content": "What specific placement or job role are you targeting, and when is your application deadline or target date?",
    }]

    reply = placement_role_followup_reply("Software engineer by December", turns)

    assert reply is not None
    assert "Software engineer by December" in reply
    assert "target date or application deadline" not in reply


def test_placement_followup_only_uses_the_active_clarification():
    assert placement_role_followup_reply(
        "Software engineer", [{"role": "assistant", "content": "How has your day been?"}]
    ) is None
    assert placement_role_followup_reply(
        "Can you explain the role requirements?",
        [{"role": "assistant", "content": "What specific placement or job role are you targeting?"}],
    ) is None


def test_spelling_quiz_answer_uses_the_word_echo_just_asked_about():
    turns = [
        {"role": "assistant", "content": "Here is your first word: brilliant. How do you spell it?"},
    ]

    correct = spelling_quiz_followup_reply("Brilliant.", turns, "rational")
    assert correct is not None
    assert "Correct" in correct
    assert "B-R-I-L-L-I-A-N-T" in correct
    assert "next word" in correct
    assert "one more detail" not in correct

    retry = spelling_quiz_followup_reply("Briliant", turns, "emotional")
    assert retry is not None
    assert "try again" in retry
    assert "B-R-I-L-L-I-A-N-T" in retry

    assert spelling_quiz_followup_reply("Brilliant", [{"role": "assistant", "content": "How was your day?"}]) is None


def test_ready_now_resumes_spelling_practice_without_world_lookup():
    question = "Hey, let's continue with my Spell B plan that we have. I'm ready right now. We can start learning."
    assert world_fact_subtype(question) is None
    assert classify_by_keywords(question) != "world_fact_lookup"
    reply = spelling_quiz_start_reply(question, [])
    assert reply is not None
    assert "Next word: necessary" in reply
    assert "How do you spell it?" in reply


def test_spelling_quiz_moves_to_the_next_word_and_checks_latest_word():
    turns = [
        {"role": "assistant", "content": "First word: brilliant. How do you spell it?"},
        {"role": "user", "content": "Brilliant"},
        {"role": "assistant", "content": "Correct. Ready for the next word?"},
    ]
    next_reply = spelling_quiz_start_reply("yes", turns)
    assert next_reply is not None
    assert "Next word: necessary" in next_reply
    turns.extend([{"role": "user", "content": "yes"}, {"role": "assistant", "content": next_reply}])
    answer = spelling_quiz_followup_reply("Necessary", turns)
    assert answer is not None
    assert "N-E-C-E-S-S-A-R-Y" in answer
    assert "B-R-I-L-L-I-A-N-T" not in answer
