import asyncio

import pytest

from backend.services.style_blend import normalize_style_weights, style_order, voice_blend_instruction, move_toward_style
from backend.llm.gemini_client import GeminiClient


def test_normalized_blend_respects_floor_and_lead_secondary_order():
    weights = normalize_style_weights({"emotional": 0.5, "rational": 0.3, "ambitious": 0.2})
    assert abs(sum(weights.values()) - 1.0) < 0.0001
    assert min(weights.values()) >= 0.05
    assert style_order(weights)[:2] == ["emotional", "rational"]
    _, _, instruction = voice_blend_instruction({"emotional": 0.45, "rational": 0.40, "ambitious": 0.15})
    assert "Balance emotional and rational" in instruction
    assert "tender" in instruction
    assert "quietly warm" in instruction


def test_style_blend_instructions_keep_each_personality_distinct():
    emotional, _, emotional_instruction = voice_blend_instruction(
        {"emotional": 0.75, "rational": 0.15, "ambitious": 0.10}
    )
    ambitious, _, ambitious_instruction = voice_blend_instruction(
        {"emotional": 0.10, "rational": 0.15, "ambitious": 0.75}
    )

    assert emotional == "emotional"
    assert "noticeably tender" in emotional_instruction
    assert ambitious == "ambitious"
    assert "lively, confident" in ambitious_instruction


def test_style_learning_is_small_and_keeps_every_voice_present():
    weights = {"emotional": 0.5, "rational": 0.3, "ambitious": 0.2}
    updated = move_toward_style(weights, "ambitious", 0.5)
    assert abs(sum(updated.values()) - 1.0) < 0.0001
    assert min(updated.values()) >= 0.05
    assert updated["ambitious"] - weights["ambitious"] <= 0.1001


@pytest.mark.asyncio
async def test_all_three_style_voices_are_requested_concurrently(monkeypatch):
    client = GeminiClient()
    active = 0
    maximum_active = 0
    calls = []

    async def fake_text(prompt, system_instruction="", temperature=0.8):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        calls.append(prompt)
        await asyncio.sleep(0.02)
        active -= 1
        return "You have a couple of things worth considering. Take a moment to think about what matters most to you."

    monkeypatch.setattr(client, "call_gemini_text", fake_text)
    voices = await client.run_style_blend_debate(
        question="Which commitment should I keep?", styles=["ambitious", "rational", "emotional"],
        usual_style="ambitious", first_answer="Keep the meeting if possible.",
        permitted_context="No permitted personal data available.", recent_turns=[],
    )
    assert len(calls) == 3 and maximum_active == 3
    assert [voice["style"] for voice in voices] == ["ambitious", "rational", "emotional"]
    assert voices[0]["your_usual_voice"] is True
