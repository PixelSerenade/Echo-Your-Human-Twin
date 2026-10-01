"""Generate a side-by-side review of Echo's three live voice styles."""

import asyncio
import re
from pathlib import Path

from backend.llm.gemini_client import GeminiClient


SAMPLES = [
    ("Neutral", "What should I work on after class?"),
    ("Neutral", "Can you help me choose between reading and starting my assignment?"),
    ("Stressed", "I'm overwhelmed by everything I need to finish this week."),
    ("Stressed", "I'm panicking about my Maths test and can't focus."),
    ("Excited", "I got invited to join a student research project!"),
    ("Excited", "I finally finished the hardest part of my assignment!"),
    ("Vague", "I don't know what to do next."),
    ("Vague", "Something feels off with my plan."),
    ("What-if", "What if I skip revision tonight and catch up tomorrow?"),
    ("What-if", "What if I accept the internship and keep all my current commitments?"),
    ("Goal", "I want to feel ready for my Maths test on Friday."),
    ("Goal", "I want to submit work I'm genuinely proud of."),
    ("Progress", "I finished the assignment outline, but the introduction is still rough."),
    ("Progress", "I studied for a while and I'm starting to understand the difficult chapter."),
    ("Progress", "I followed yesterday's plan and got the project setup working."),
]

STYLES = ("rational", "emotional", "ambitious")
CONTEXT = """Saved goals and tasks the user has allowed Echo to use:
- Prepare confidently for the Maths test on Friday.
- Finish the research assignment due Thursday.
- Explore an internship without dropping current commitments.
"""
RECENT_TURNS = [
    {"role": "user", "content": "I'm trying to balance my Maths test and research assignment."},
    {"role": "assistant", "content": "We can keep both moving without making tonight impossible."},
]


def clean_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>").strip()


async def generate_review(output_path: Path) -> None:
    client = GeminiClient()
    client.cache = {}
    client._save_cache = lambda: None

    async def fixed_structured_data(*args, **kwargs):
        return {
            "deadline_risk_alert": "The Maths test and research assignment are close together.",
            "options": [
                {"id": "opt-1", "text": "Protect the nearest deadline", "aligned_twin": "rational", "description": "Keeps the plan workable."},
                {"id": "opt-2", "text": "Make room to recover", "aligned_twin": "emotional", "description": "Protects energy."},
                {"id": "opt-3", "text": "Push a meaningful milestone", "aligned_twin": "ambitious", "description": "Builds momentum."},
            ],
        }

    client.call_gemini_json = fixed_structured_data
    semaphore = asyncio.Semaphore(3)

    async def run_one(category: str, prompt: str, style: str):
        async with semaphore:
            result = await client.ask_primary_twin(
                primary_twin=style,
                question=prompt,
                permitted_context=CONTEXT,
                ml_insights={
                    "on_time_probability": 0.61,
                    "estimated_hours": 8.0,
                    "predicted_hours": 10.5,
                    "why_factors": [{"feature": "deadline proximity", "importance_pct": 42.0}],
                },
                deadline_risk_summary="The Maths test and research assignment are close together.",
                user_name="Alex",
                twin_name="Echo",
                mood_tone_enabled=True,
                recent_turns=RECENT_TURNS,
            )
            message = result["message"]
            fallback_message = client._fallback_spoken_message(
                style, prompt, mood_tone_enabled=True, recent_turns=RECENT_TURNS
            )
            return {
                "category": category,
                "prompt": prompt,
                "style": style,
                "message": message,
                "safe": client._is_spoken_message_safe(message, prompt),
                "has_number": bool(re.search(r"\d|%", message)),
                "source": "Safe fallback" if message == fallback_message else "Live model",
            }

    jobs = [run_one(category, prompt, style) for category, prompt in SAMPLES for style in STYLES]
    rows = await asyncio.gather(*jobs)
    indexed = {(row["prompt"], row["style"]): row for row in rows}

    lines = [
        "# Echo Voice Review",
        "",
        "Generated through the live spoken-reply pipeline with mood and tone permission enabled.",
        "Structured extraction was stubbed so this review exercises voice generation and its corrective post-check without making unrelated JSON calls.",
        "",
        "| # | Situation | User message | Rational | Emotional | Ambitious | Checks |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, (category, prompt) in enumerate(SAMPLES, start=1):
        style_rows = [indexed[(prompt, style)] for style in STYLES]
        check_state = "PASS" if all(row["safe"] and not row["has_number"] for row in style_rows) else "REVIEW"
        live_count = sum(row["source"] == "Live model" for row in style_rows)
        checks = f"{check_state}; {live_count}/3 live"
        lines.append(
            f"| {index} | {category} | {clean_cell(prompt)} | "
            f"{clean_cell(style_rows[0]['message'])} | {clean_cell(style_rows[1]['message'])} | "
            f"{clean_cell(style_rows[2]['message'])} | {checks} |"
        )

    passed = sum(row["safe"] and not row["has_number"] for row in rows)
    live = sum(row["source"] == "Live model" for row in rows)
    lines.extend([
        "",
        "## Automated Summary",
        "",
        f"- Replies generated: {len(rows)}",
        f"- Passed the robotic-pattern detector: {passed}/{len(rows)}",
        f"- Replies containing digits or percentages: {sum(row['has_number'] for row in rows)}",
        f"- Live model replies: {live}/{len(rows)}",
        f"- Safe fallback replies after API timeout or unavailability: {len(rows) - live}/{len(rows)}",
        "- Exact numbers remain available to the app as structured fields for the Why sheet.",
        "",
    ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[2] / "voice-review.md"
    asyncio.run(generate_review(destination))
    print(destination)
