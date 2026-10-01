"""Signed sessions and account ownership checks for public deployments."""
import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from backend.config import settings

SESSION_SECONDS = 14 * 24 * 60 * 60
PUBLIC_PATHS = {"/", "/health", "/api/memory-registry", "/api/auth/signup", "/api/auth/login", "/api/auth/logout"}


def issue_session(user_id: str) -> str:
    if not settings.PRODUCTION:
        return user_id
    if len(settings.SESSION_SECRET) < 32:
        raise RuntimeError("Production requires a SESSION_SECRET of at least 32 characters")
    payload = base64.urlsafe_b64encode(f"{user_id}:{int(time.time()) + SESSION_SECONDS}".encode()).decode().rstrip("=")
    signature = hmac.new(settings.SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def read_session(token: str | None) -> str | None:
    if not token:
        return None
    if not settings.PRODUCTION:
        return token
    if len(settings.SESSION_SECRET) < 32:
        return None
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(settings.SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id, expiry = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode().rsplit(":", 1)
        return user_id if user_id and int(expiry) > time.time() else None
    except (ValueError, UnicodeError):
        return None


async def require_production_session(request: Request) -> None:
    if not settings.PRODUCTION or request.url.path.rstrip("/") in PUBLIC_PATHS or request.url.path == "/":
        return
    identity = read_session(request.cookies.get("session_user_id"))
    if not identity:
        raise HTTPException(401, "Please sign in to continue.")

    # Validate every identity carrier; handlers may use path, query, JSON, or
    # header IDs. Do not allow an omitted field to fall back to the demo user.
    ids = request.query_params.getlist("user_id")
    ids += [request.path_params.get("user_id"), request.headers.get("X-User-Id")]
    route = request.scope.get("route")
    dependant = getattr(route, "dependant", None)
    if any(field.name == "user_id" for field in getattr(dependant, "query_params", [])):
        if not request.query_params.get("user_id"):
            raise HTTPException(400, "An account ID is required.")
    body_params = getattr(dependant, "body_params", [])
    # FastAPI also accepts JSON with an omitted Content-Type. Inspect typed
    # body routes regardless of that header, so it cannot bypass ownership.
    if body_params or "json" in request.headers.get("content-type", ""):
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(400, "Send valid JSON.")
        if isinstance(payload, dict):
            ids.append(payload.get("user_id"))
            fields = [getattr(field.field_info.annotation, "model_fields", {}) for field in body_params]
            if any("user_id" in model_fields for model_fields in fields) and not payload.get("user_id"):
                raise HTTPException(400, "An account ID is required.")
    if any(value is not None and value != identity for value in ids):
        raise HTTPException(403, "You can only access your own account.")
