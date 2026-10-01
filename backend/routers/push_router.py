"""Authenticated browser push subscription endpoints."""

from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import PushSubscription, User
from backend.routers.auth_router import get_current_user_id
from backend.services.push_notifications import push_is_configured, send_push

router = APIRouter(prefix="/api/push", tags=["push notifications"])


class PushSubscriptionRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    timezone: str = Field(default="UTC", max_length=80)
    subscription: dict


class PushUnsubscribeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    endpoint: str = Field(min_length=1, max_length=4096)


class PushTestRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)


def _check_identity(request: Request, user_id: str) -> None:
    authenticated_id = get_current_user_id(request)
    if authenticated_id and authenticated_id != user_id:
        raise HTTPException(status_code=403, detail="This reminder subscription belongs to another account.")
    if not authenticated_id:
        raise HTTPException(status_code=401, detail="Please sign in before enabling reminders.")


@router.get("/public-key")
async def get_vapid_public_key():
    if not push_is_configured():
        raise HTTPException(status_code=503, detail="Background reminders are not configured on this server yet.")
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe_push(req: PushSubscriptionRequest, request: Request, db: AsyncSession = Depends(get_db)):
    _check_identity(request, req.user_id)
    if not push_is_configured():
        raise HTTPException(status_code=503, detail="Background reminders are not configured on this server yet.")
    subscription = req.subscription
    endpoint = str(subscription.get("endpoint", ""))
    parsed = urlparse(endpoint)
    keys = subscription.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if parsed.scheme != "https" or not parsed.netloc or not p256dh or not auth:
        raise HTTPException(status_code=422, detail="That browser push subscription is incomplete.")
    try:
        ZoneInfo(req.timezone)
        timezone = req.timezone
    except (ZoneInfoNotFoundError, ValueError):
        timezone = "UTC"
    if not await db.get(User, req.user_id):
        raise HTTPException(status_code=404, detail="Account not found.")

    existing = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if existing:
        existing.user_id = req.user_id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.timezone = timezone
    else:
        db.add(PushSubscription(
            user_id=req.user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            timezone=timezone,
        ))
    await db.commit()
    return {"enabled": True}


@router.delete("/subscribe")
async def unsubscribe_push(req: PushUnsubscribeRequest, request: Request, db: AsyncSession = Depends(get_db)):
    _check_identity(request, req.user_id)
    await db.execute(delete(PushSubscription).where(
        PushSubscription.user_id == req.user_id,
        PushSubscription.endpoint == req.endpoint,
    ))
    await db.commit()
    return {"enabled": False}


@router.post("/test")
async def send_test_push(req: PushTestRequest, request: Request, db: AsyncSession = Depends(get_db)):
    _check_identity(request, req.user_id)
    subscriptions = list((await db.execute(select(PushSubscription).where(
        PushSubscription.user_id == req.user_id,
    ))).scalars().all())
    if not subscriptions:
        raise HTTPException(status_code=409, detail="Enable background reminders on this device first.")
    payload = {
        "title": "Echo reminder test",
        "body": "Background notifications are connected on this device.",
        "url": "/",
        "tag": "echo-push-test",
    }
    delivered = False
    for subscription in subscriptions:
        delivered = await send_push(subscription, payload) or delivered
    if not delivered:
        raise HTTPException(status_code=502, detail="The browser push service could not deliver a test notification.")
    return {"sent": True}
