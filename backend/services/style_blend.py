"""Helpers for stable, bounded three-style blends."""

STYLES = ("emotional", "rational", "ambitious")

VOICE_GUIDES = {
    "rational": "Rational is steady, clear, and quietly warm. Use precise everyday language, weigh the facts, and give a practical recommendation without sounding clinical.",
    "emotional": "Emotional is noticeably tender, affectionate, and reassuring. Validate the user's feelings, speak gently and patiently, and make the user feel cared for without using pet names, gushy praise, or pretending to have human feelings.",
    "ambitious": "Ambitious is lively, confident, and encouraging. Spot opportunities, turn them into a concrete next move, and celebrate effort without pressure, shame, or hype.",
}


def normalize_style_weights(values, floor: float = 0.05) -> dict[str, float]:
    raw = {style: max(0.0, float((values or {}).get(style, 0.0))) for style in STYLES}
    remainder = max(0.0, 1.0 - floor * len(STYLES))
    excess = {style: max(0.0, raw[style] - floor) for style in STYLES}
    total = sum(excess.values())
    if total == 0:
        excess = {style: 1.0 for style in STYLES}
        total = len(STYLES)
    result = {style: floor + remainder * excess[style] / total for style in STYLES}
    # Round while keeping the sum exactly one.
    result = {style: round(value, 4) for style, value in result.items()}
    result[STYLES[0]] = round(result[STYLES[0]] + (1.0 - sum(result.values())), 4)
    return result


def style_order(weights):
    normalized = normalize_style_weights(weights)
    tie_break = {"rational": 0, "emotional": 1, "ambitious": 2}
    return sorted(STYLES, key=lambda style: (-normalized[style], tie_break[style]))


def voice_blend_instruction(weights) -> tuple[str, str, str]:
    normalized = normalize_style_weights(weights)
    lead, second, _ = style_order(normalized)
    if normalized[lead] - normalized[second] <= 0.10:
        instruction = (
            f"Balance {lead} and {second} styles equally while keeping both voices distinct: "
            f"{VOICE_GUIDES[lead]} {VOICE_GUIDES[second]}"
        )
    else:
        instruction = (
            f"Lead with {lead} style: {VOICE_GUIDES[lead]} Let {second} lightly color the reply: "
            f"{VOICE_GUIDES[second]}"
        )
    return lead, second, instruction


def move_toward_style(weights, style: str, amount: float) -> dict[str, float]:
    current = normalize_style_weights(weights)
    if style not in STYLES:
        return current
    amount = max(0.0, min(float(amount), 0.10))
    amount = min(amount, current[style] - 0.05)
    if amount <= 0:
        return current
    others = [item for item in STYLES if item != style]
    other_total = sum(current[item] for item in others)
    updated = {item: value for item, value in current.items()}
    updated[style] += amount
    for item in others:
        updated[item] -= amount * current[item] / other_total
    return normalize_style_weights(updated)
