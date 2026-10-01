"""VAPID web-push sender and permission-aware deadline scheduler."""

import asyncio
import datetime as dt
import json
import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.memory_registry import defaults_for
from backend.models import (
    AuditLog,
    Deadline,
    Permission,
    PushReminderDelivery,
    PushSubscription,
    Timetable,
    User,
)
from backend.services.data_access import get_permitted_user_data

logger = logging.getLogger(__name__)
DAY = dt.timedelta(days=1)
THREE_DAYS = dt.timedelta(days=3)
START_SOON = dt.timedelta(minutes=15)


def push_is_configured() -> bool:
    return bool(
        settings.VAPID_PUBLIC_KEY
        and settings.VAPID_PRIVATE_KEY_PATH
        and os.path.isfile(settings.VAPID_PRIVATE_KEY_PATH)
    )


async def send_push(subscription: PushSubscription, payload: dict) -> bool:
    """Send a web-push payload without blocking the async server loop."""
    if not push_is_configured():
        return False
    try:
        from pywebpush import WebPushException, webpush

        def _send():
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY_PATH,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=60 * 60 * 24 * 4,
            )

        await asyncio.to_thread(_send)
        return True
    except Exception as exc:
        try:
            from pywebpush import WebPushException
            if isinstance(exc, WebPushException) and exc.response is not None:
                if exc.response.status_code in (404, 410):
                    async with AsyncSessionLocal() as db:
                        await db.execute(delete(PushSubscription).where(PushSubscription.id == subscription.id))
                        await db.commit()
                    return False
        except Exception:
            pass
        logger.warning("Web-push delivery failed for subscription %s: %s", subscription.id, exc)
        return False


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _as_local(value: dt.datetime, zone: ZoneInfo) -> dt.datetime:
    # Echo stores commitment/deadline times as local wall-clock values.
    return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)


def _parse_clock(value: str | None) -> dt.time:
    try:
        return dt.time.fromisoformat(value or "09:00")
    except ValueError:
        return dt.time(9, 0)


def _lead_window(due: dt.datetime, now: dt.datetime) -> str | None:
    remaining = due - now
    if remaining <= dt.timedelta(0):
        return None
    if remaining <= DAY:
        return "1-day"
    if remaining <= THREE_DAYS:
        return "3-day"
    return None


async def _send_due_reminders_for_user(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return
        subscriptions = list((await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )).scalars().all())
        if not subscriptions:
            return

        zone = _zone(subscriptions[0].timezone)
        now = dt.datetime.now(zone)
        permissions = {
            item.source: item.enabled
            for item in (await db.execute(select(Permission).where(Permission.user_id == user_id))).scalars().all()
        }
        defaults = defaults_for(user.persona or "student")
        deadline_enabled = permissions.get(
            "deadlines_key_dates", permissions.get("deadlines", defaults["deadlines_key_dates"])
        )
        schedule_enabled = permissions.get(
            "schedule_commitments", permissions.get("timetable", defaults["schedule_commitments"])
        )

        # Use the shared privacy gateway; category-off data is never queried.
        bundle = await get_permitted_user_data(
            db,
            user_id=user_id,
            requested_sources=[
                *( ["deadlines_key_dates"] if deadline_enabled else [] ),
                *( ["schedule_commitments"] if schedule_enabled else [] ),
            ],
            # Scheduler reads are audited with the event they result in below;
            # do not create a new audit row on every 60-second poll.
            log_audit_endpoint=None,
        )

        occurrences: list[tuple[str, str, dt.datetime, str]] = []
        if "deadlines_key_dates" in bundle.accessed_sources:
            for deadline in bundle.deadlines:
                if deadline.completed:
                    continue
                due = _as_local(deadline.due_date, zone)
                if due.hour == 0 and due.minute == 0 and due.second == 0:
                    due = due.replace(hour=9)
                if dt.timedelta(0) < due - now <= THREE_DAYS:
                    occurrences.append((f"deadline:{deadline.id}", deadline.title, due, "Deadlines & Key Dates"))

        if "schedule_commitments" in bundle.accessed_sources:
            for item in bundle.timetable:
                if item.specific_date:
                    days = [item.specific_date.date()]
                else:
                    days = [(now + dt.timedelta(days=offset)).date() for offset in range(4)]
                for day in days:
                    if day < now.date() or day > (now + THREE_DAYS).date():
                        continue
                    if not item.specific_date and day.strftime("%A") != item.day_of_week:
                        continue
                    clock = _parse_clock(item.start_time)
                    due = dt.datetime.combine(day, clock, tzinfo=zone)
                    if dt.timedelta(0) < due - now <= THREE_DAYS:
                        occurrences.append((f"commitment:{item.id}", item.activity_name, due, "Schedule & Commitments"))

        for item_key, title, due, category in occurrences:
            remaining = due - now
            # A saved time block is an appointment with the user. Remind them
            # shortly before it starts, once per occurrence (including weekly
            # recurring blocks), even if they already got an earlier heads-up.
            lead = (
                "start-soon"
                if category == "Schedule & Commitments" and dt.timedelta(0) < remaining <= START_SOON
                else _lead_window(due, now)
            )
            if not lead:
                continue
            event_key = f"{item_key}:{due.astimezone(dt.timezone.utc).isoformat()}:{lead}"
            existing = await db.scalar(select(PushReminderDelivery.id).where(
                PushReminderDelivery.user_id == user_id,
                PushReminderDelivery.event_key == event_key,
            ))
            if existing:
                continue

            when = due.strftime("%a, %b %d at %I:%M %p").replace(" 0", " ").lstrip("0")
            if lead == "start-soon":
                notification_title = f"Starting soon: {title}"
                body = f"Your time for {title} starts at {due.strftime('%I:%M %p').lstrip('0')}. Ready to begin?"
            elif lead == "3-day":
                notification_title = f"Coming up: {title}"
                body = f"{title} is coming up in the next few days ({when}). A little preparation now can help."
            else:
                notification_title = f"Tomorrow or soon: {title}"
                body = f"{title} is coming up ({when})."
            payload = {"title": notification_title, "body": body, "url": "/", "tag": event_key}

            sent = False
            for subscription in subscriptions:
                sent = await send_push(subscription, payload) or sent
            if sent:
                db.add(PushReminderDelivery(user_id=user_id, event_key=event_key))
                db.add(AuditLog(
                    user_id=user_id,
                    action="deliver_push_reminder",
                    endpoint="/push-reminders/scheduler",
                    sources_accessed=[category],
                    timestamp=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                ))
                await db.commit()


async def reminder_scheduler(stop_event: asyncio.Event, interval_seconds: int = 60) -> None:
    """Check opted-in reminders regularly; push services wake closed browsers."""
    while not stop_event.is_set():
        if push_is_configured():
            try:
                async with AsyncSessionLocal() as db:
                    user_ids = (await db.execute(select(PushSubscription.user_id).distinct())).scalars().all()
                for user_id in user_ids:
                    try:
                        await _send_due_reminders_for_user(user_id)
                    except Exception:
                        logger.exception("Push reminder scheduler failed for user %s", user_id)
            except Exception:
                logger.exception("Push reminder scheduler cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
