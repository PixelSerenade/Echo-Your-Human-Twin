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


@pytest.mark.asyncio
@pytest.mark.parametrize('error', ['Gemini returned 429', 'Connection unavailable'])
async def test_schedule_failure_does_not_repeat_availability_question(monkeypatch, error):
    from backend.llm.gemini_client import GeminiClient
    client = GeminiClient()
    client.api_key = 'test-only'

    async def unavailable(*args, **kwargs):
        raise RuntimeError(error)

    monkeypatch.setattr(client, 'call_gemini_json', unavailable)
    result = await client.build_chat_schedule(
        ['Prepare for my interview. I am free Monday to Thursday, 6:30 pm to 9 pm.'],
        '2026-10-01', '',
    )
    assert result['blocks'] == []
    assert "hasn't been saved" in result['question']
    assert 'What exact hours' not in result['question']
    if '429' in error:
        assert 'request limit' in result['question']
