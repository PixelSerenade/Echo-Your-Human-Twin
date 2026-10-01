import pytest

from backend.services.message_intent import is_explicit_plan_request


@pytest.mark.parametrize('message', [
    'Please create a preparation plan for me.',
    'Make me an interview plan.',
    'Please save the plan and goal.',
    'Create my study timetable.',
    'Build a weekly training schedule.',
])
def test_explicit_plan_variations(message):
    assert is_explicit_plan_request(message)


@pytest.mark.parametrize('message', [
    'My assignment is due tomorrow.',
    'I have an interview in a week.',
    'My preparation plan looks good.',
])
def test_mentions_do_not_request_schedule(message):
    assert not is_explicit_plan_request(message)
