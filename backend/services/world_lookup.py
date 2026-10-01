"""Privacy-limited live lookup helpers. No user profile or memory enters public queries."""
from __future__ import annotations

import asyncio
import datetime as dt
import re
from zoneinfo import ZoneInfo

import httpx

_CACHE: dict[str, tuple[float, dict]] = {}
_RATE: dict[str, list[float]] = {}


def check_world_rate_limit(user_id: str, now: float | None = None, limit: int = 12) -> bool:
    now = now if now is not None else asyncio.get_event_loop().time()
    recent = [value for value in _RATE.get(user_id, []) if now - value < 60]
    if len(recent) >= limit:
        _RATE[user_id] = recent
        return False
    recent.append(now)
    _RATE[user_id] = recent
    return True


def sanitize_public_query(question: str, user_name: str = "", email: str = "") -> str:
    """Remove personal clauses and identifiers; return only public lookup terms."""
    text = re.sub(r"\b(?:and\s+)?(?:do\s+i\s+have|what(?:'s| is)\s+my|when\s+is\s+my|what\s+time\s+is\s+my)\b[^,?.;]*", " ", question, flags=re.I)
    for private in (user_name, email):
        if private:
            text = re.sub(re.escape(private), " ", text, flags=re.I)
    # Strip remaining first-person and sensitive personal clauses conservatively.
    text = re.sub(r"\b(?:my|mine|i told you|i shared|my schedule|my meeting|my assignment|my goal|my mood)\b[^,?.;]*", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", re.sub(r"[^\w\s,'-]", " ", text)).strip(" ,-")
    return text[:240]


def extract_place(question: str) -> str | None:
    patterns = (r"\b(?:weather|forecast|rain|events?)\s+(?:in|for|near)\s+([A-Z][\w .'-]{1,60})", r"\b(?:in|near)\s+([A-Z][\w .'-]{1,60})")
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.I)
        if match:
            place = re.split(r"\b(?:and|tomorrow|today|next week|this week)\b", match.group(1), maxsplit=1, flags=re.I)[0].strip(" ,?.")
            if place.casefold() not in {"my city", "my area", "here", "there", "my location"}:
                return place
    return None


async def cached_grounded_search(client, query: str, current_context: str, ttl_seconds: int, safety_mode: bool = False) -> dict:
    now = asyncio.get_event_loop().time()
    key = f"search:{safety_mode}:{query.casefold()}"
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    result = await client.call_gemini_grounded(query, current_context, safety_mode=safety_mode)
    _CACHE[key] = (now + ttl_seconds, result)
    return result


async def open_meteo_weather(place: str, tomorrow: bool = False) -> dict:
    """Geocode a user-named city and fetch a short forecast; timeout is capped at 8s."""
    key = f"weather:{place.casefold()}:{dt.date.today().isoformat()}:{tomorrow}"
    now = asyncio.get_event_loop().time()
    if key in _CACHE and _CACHE[key][0] > now:
        return _CACHE[key][1]
    async with asyncio.timeout(8.0), httpx.AsyncClient(timeout=4.0) as client:
        geo = await client.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": place, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            raise LookupError("No matching place")
        location = results[0]
        timezone = location.get("timezone") or "UTC"
        local_today = dt.datetime.now(ZoneInfo(timezone)).date()
        forecast = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": location["latitude"], "longitude": location["longitude"], "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": timezone, "forecast_days": 7,
        })
        forecast.raise_for_status()
        data = forecast.json().get("daily", {})
    target = local_today + dt.timedelta(days=1) if tomorrow else local_today
    day_key = target.isoformat()
    try:
        index = data.get("time", []).index(day_key)
    except ValueError:
        index = 0
    result = {
        "place": ", ".join(x for x in (location.get("name"), location.get("admin1"), location.get("country")) if x),
        "date": data.get("time", [day_key])[index], "min_c": data.get("temperature_2m_min", [None])[index],
        "max_c": data.get("temperature_2m_max", [None])[index], "rain_chance": data.get("precipitation_probability_max", [None])[index],
        "weather_code": data.get("weather_code", [None])[index], "timezone": timezone,
        "source": "Open-Meteo", "url": "https://open-meteo.com/",
    }
    _CACHE[key] = (now + 1800, result)
    return result
