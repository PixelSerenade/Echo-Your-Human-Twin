import datetime as dt
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from backend.models import Permission, PushSubscription, User
from backend.services import push_notifications


@pytest.mark.parametrize(
    ("hours_until_due", "expected"),
    [
        (72, "3-day"),
        (48, "3-day"),
        (24, "1-day"),
        (1, "1-day"),
        (73, None),
        (0, None),
        (-1, None),
    ],
)
def test_reminder_lead_windows(hours_until_due, expected):
    now = dt.datetime(2026, 10, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    due = now + dt.timedelta(hours=hours_until_due)
    assert push_notifications._lead_window(due, now) == expected


def test_date_only_reminder_time_defaults_to_nine_local():
    due = dt.datetime(2026, 10, 4, 0, 0)
    local = push_notifications._as_local(due, ZoneInfo("Asia/Kolkata"))
    if local.hour == local.minute == local.second == 0:
        local = local.replace(hour=9)
    assert local.hour == 9
    assert local.utcoffset() == dt.timedelta(hours=5, minutes=30)


def test_scheduler_parses_commitment_clock_safely():
    assert push_notifications._parse_clock("14:25") == dt.time(14, 25)
    assert push_notifications._parse_clock(None) == dt.time(9, 0)
    assert push_notifications._parse_clock("invalid") == dt.time(9, 0)


@pytest.mark.asyncio
async def test_send_push_serializes_payload_and_uses_configured_vapid(tmp_path, monkeypatch):
    import pywebpush

    private_key = tmp_path / "vapid.pem"
    private_key.write_text("test private key")
    calls = []

    def fake_webpush(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    monkeypatch.setattr(push_notifications.settings, "VAPID_PUBLIC_KEY", "public")
    monkeypatch.setattr(push_notifications.settings, "VAPID_PRIVATE_KEY_PATH", str(private_key))
    subscription = PushSubscription(
        id=9,
        user_id="test-user",
        endpoint="https://push.example/subscription",
        p256dh="p256dh-key",
        auth="auth-key",
        timezone="Asia/Kolkata",
    )
    payload = {"title": "Coming up", "body": "Due soon", "url": "/", "tag": "item:3-day"}

    assert await push_notifications.send_push(subscription, payload)
    assert len(calls) == 1
    assert calls[0]["subscription_info"]["endpoint"] == subscription.endpoint
    assert calls[0]["subscription_info"]["keys"] == {"p256dh": "p256dh-key", "auth": "auth-key"}
    assert calls[0]["vapid_private_key"] == str(private_key)
    assert calls[0]["ttl"] == 4 * 24 * 60 * 60
    assert calls[0]["data"] == '{"title": "Coming up", "body": "Due soon", "url": "/", "tag": "item:3-day"}'


class _Scalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return _Scalars(self.rows)


class _SchedulerSession:
    def __init__(self, permissions, delivered=False):
        self.permissions = permissions
        self.delivered = delivered
        self.added = []
        self.commits = 0
        self.subscription = PushSubscription(
            id=21,
            user_id="push-test-user",
            endpoint="https://push.example/subscription",
            p256dh="p256dh-key",
            auth="auth-key",
            timezone="Asia/Kolkata",
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, model, user_id):
        assert model is User
        return User(id=user_id, persona="other")

    async def execute(self, statement):
        model = statement.column_descriptions[0].get("entity")
        if model is PushSubscription:
            return _Result([self.subscription])
        if model is Permission:
            return _Result(self.permissions)
        return _Result([])

    async def scalar(self, _statement):
        return 1 if self.delivered else None

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_scheduler_sends_permitted_deadline_and_records_delivery(monkeypatch):
    zone = ZoneInfo("Asia/Kolkata")
    due = (dt.datetime.now(zone) + dt.timedelta(days=2)).replace(tzinfo=None)
    bundle = SimpleNamespace(
        accessed_sources=["deadlines_key_dates"],
        deadlines=[SimpleNamespace(id=45, title="Portfolio submission", due_date=due, completed=False)],
        timetable=[],
    )
    session = _SchedulerSession([Permission(user_id="push-test-user", source="deadlines_key_dates", enabled=True)])
    sent = []
    gateway_calls = []

    async def fake_gateway(db, **kwargs):
        gateway_calls.append(kwargs)
        return bundle

    async def fake_send(subscription, payload):
        sent.append((subscription.id, payload))
        return True

    monkeypatch.setattr(push_notifications, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(push_notifications, "get_permitted_user_data", fake_gateway)
    monkeypatch.setattr(push_notifications, "send_push", fake_send)
    await push_notifications._send_due_reminders_for_user("push-test-user")

    assert len(sent) == 1
    assert "Portfolio submission" in sent[0][1]["title"]
    assert "next few days" in sent[0][1]["body"]
    assert gateway_calls[0]["requested_sources"] == ["deadlines_key_dates"]
    assert gateway_calls[0]["log_audit_endpoint"] is None
    assert any(row.__class__.__name__ == "PushReminderDelivery" for row in session.added)
    assert any(row.__class__.__name__ == "AuditLog" for row in session.added)


@pytest.mark.asyncio
async def test_scheduler_does_not_query_disabled_reminder_categories(monkeypatch):
    session = _SchedulerSession([Permission(user_id="push-test-user", source="deadlines_key_dates", enabled=False)])
    gateway_calls = []
    sent = []

    async def fake_gateway(_db, **kwargs):
        gateway_calls.append(kwargs)
        return SimpleNamespace(accessed_sources=[], deadlines=[], timetable=[])

    async def fake_send(*_args):
        sent.append(True)
        return True

    monkeypatch.setattr(push_notifications, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(push_notifications, "get_permitted_user_data", fake_gateway)
    monkeypatch.setattr(push_notifications, "send_push", fake_send)
    await push_notifications._send_due_reminders_for_user("push-test-user")

    assert gateway_calls[0]["requested_sources"] == []
    assert sent == []
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("recurring", [False, True])
async def test_scheduler_reminds_before_confirmed_time_block(monkeypatch, recurring):
    zone = ZoneInfo("Asia/Kolkata")
    start = dt.datetime.now(zone) + dt.timedelta(minutes=10)
    item = SimpleNamespace(
        id=71,
        activity_name="Practice coding",
        specific_date=None if recurring else start.replace(tzinfo=None),
        day_of_week=start.strftime("%A"),
        start_time=start.strftime("%H:%M"),
    )
    bundle = SimpleNamespace(
        accessed_sources=["schedule_commitments"], deadlines=[], timetable=[item],
    )
    session = _SchedulerSession([
        Permission(user_id="push-test-user", source="schedule_commitments", enabled=True),
    ])
    sent = []
    gateway_calls = []

    async def fake_gateway(_db, **kwargs):
        gateway_calls.append(kwargs)
        return bundle

    async def fake_send(_subscription, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr(push_notifications, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(push_notifications, "get_permitted_user_data", fake_gateway)
    monkeypatch.setattr(push_notifications, "send_push", fake_send)

    await push_notifications._send_due_reminders_for_user("push-test-user")

    assert gateway_calls[0]["requested_sources"] == ["schedule_commitments"]
    assert len(sent) == 1
    assert sent[0]["title"] == "Starting soon: Practice coding"
    assert "Practice coding" in sent[0]["body"]
    assert sent[0]["tag"].endswith(":start-soon")
    assert any(row.__class__.__name__ == "PushReminderDelivery" for row in session.added)


@pytest.mark.asyncio
async def test_scheduler_does_not_repeat_delivered_time_block(monkeypatch):
    zone = ZoneInfo("Asia/Kolkata")
    start = dt.datetime.now(zone) + dt.timedelta(minutes=10)
    bundle = SimpleNamespace(
        accessed_sources=["schedule_commitments"], deadlines=[],
        timetable=[SimpleNamespace(
            id=72, activity_name="Review notes", specific_date=start.replace(tzinfo=None),
            day_of_week=start.strftime("%A"), start_time=start.strftime("%H:%M"),
        )],
    )
    session = _SchedulerSession([
        Permission(user_id="push-test-user", source="schedule_commitments", enabled=True),
    ], delivered=True)
    sent = []

    async def fake_gateway(_db, **_kwargs):
        return bundle

    async def fake_send(*_args):
        sent.append(True)
        return True

    monkeypatch.setattr(push_notifications, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(push_notifications, "get_permitted_user_data", fake_gateway)
    monkeypatch.setattr(push_notifications, "send_push", fake_send)

    await push_notifications._send_due_reminders_for_user("push-test-user")

    assert sent == []
