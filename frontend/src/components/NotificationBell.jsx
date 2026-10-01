import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, BellRing } from 'lucide-react';
import { localDateKey, parseLocalDateTime } from '../utils/localDateTime';

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const REMINDER_WINDOW_MS = 24 * 60 * 60 * 1000;
const THREE_DAYS_MS = 3 * REMINDER_WINDOW_MS;
const VISIBLE_WINDOW_MS = 7 * REMINDER_WINDOW_MS;
const START_SOON_MS = 15 * 60 * 1000;

function eventDate(value, time) {
  const date = parseLocalDateTime(value, 9);
  if (!date) return null;
  if (time) {
    const [hour, minute] = String(time).split(':').map(Number);
    if (Number.isFinite(hour) && Number.isFinite(minute)) date.setHours(hour, minute, 0, 0);
  } else if (date.getHours() === 0 && date.getMinutes() === 0) {
    date.setHours(9, 0, 0, 0);
  }
  return date;
}

function buildReminderEvents(knowledge) {
  const events = [];
  const now = new Date();
  const permissions = knowledge?.active_permissions || {};
  if (permissions.deadlines_key_dates ?? permissions.deadlines) {
    for (const item of knowledge?.deadlines || []) {
      if (item.completed) continue;
      const date = eventDate(item.due_date);
      if (date) events.push({ id: `deadline:${item.id}`, title: item.title, type: 'Due', date });
    }
  }
  if (permissions.schedule_commitments ?? permissions.timetable) {
    for (const item of knowledge?.timetable || []) {
      let date;
      if (item.specific_date) {
        date = eventDate(item.specific_date, item.start_time);
      } else {
        const weekday = DAY_NAMES.indexOf(item.day_of_week);
        if (weekday < 0) continue;
        date = new Date(now);
        let offset = (weekday - date.getDay() + 7) % 7;
        date.setDate(date.getDate() + offset);
        const [hour, minute] = String(item.start_time || '09:00').split(':').map(Number);
        date.setHours(hour || 0, minute || 0, 0, 0);
        if (date <= now) date.setDate(date.getDate() + 7);
      }
      if (date) events.push({ id: `commitment:${item.id}:${localDateKey(date)}`, title: item.activity_name, type: 'Commitment', date });
    }
  }
  return events
    .filter((event) => event.date.getTime() >= now.getTime() - REMINDER_WINDOW_MS && event.date.getTime() <= now.getTime() + VISIBLE_WINDOW_MS)
    .sort((a, b) => a.date - b.date);
}

function readNotified(userId) {
  try { return JSON.parse(localStorage.getItem(`echo-notified-reminders:${userId}`) || '[]'); }
  catch { return []; }
}

function applicationServerKeyBytes(encodedKey) {
  const padding = '='.repeat((4 - encodedKey.length % 4) % 4);
  const base64 = (encodedKey + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from(raw, (character) => character.charCodeAt(0));
}

export default function NotificationBell({ api, userId, activeTab, onOpenPrivacy }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState([]);
  const [knowledge, setKnowledge] = useState(null);
  const [permission, setPermission] = useState(() => typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
  const pushSupported = Boolean(userId && typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && typeof Notification !== 'undefined');
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushError, setPushError] = useState('');
  const [testPushStatus, setTestPushStatus] = useState('');
  const [loadFailed, setLoadFailed] = useState(false);
  const [now, setNow] = useState(() => new Date().getTime());

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const result = await api.getReminders(userId);
      setKnowledge(result);
      setEvents(buildReminderEvents(result));
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    }
  }, [api, userId]);

  useEffect(() => {
    window.addEventListener('echo-reminders-refresh', refresh);
    return () => window.removeEventListener('echo-reminders-refresh', refresh);
  }, [refresh]);
  useEffect(() => { if (activeTab) refresh(); }, [activeTab, refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date().getTime()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let live = true;
    if (!pushSupported) return () => { live = false; };
    navigator.serviceWorker.register('/sw.js').then(async () => {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (!subscription || !live) return;
      await api.savePushSubscription(userId, subscription.toJSON(), Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
      if (live) setPushEnabled(true);
    }).catch(() => {
      if (live) setPushError('Background reminders could not connect. Try again from this bell.');
    });
    return () => { live = false; };
  }, [api, pushSupported, userId]);

  const notifyDueSoon = useCallback(() => {
    if (pushEnabled || typeof Notification === 'undefined' || Notification.permission !== 'granted' || !userId) return;
    const now = Date.now();
    const notified = new Set(readNotified(userId));
    const newKeys = [];
    for (const event of events) {
      const delay = event.date.getTime() - now;
      if (delay <= 0) continue;
      // A separate key for each heads-up lets the same item notify once at
      // three days and once again on the day before it is due.
      const reminderWindow = event.type === 'Commitment' && delay <= START_SOON_MS
        ? 'start-soon'
        : delay <= REMINDER_WINDOW_MS ? '1-day' : delay <= THREE_DAYS_MS ? '3-day' : null;
      const notificationKey = reminderWindow ? `${event.id}:${reminderWindow}` : null;
      if (!notificationKey || notified.has(notificationKey)) continue;
      try {
        const when = event.date.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
        const headsUp = reminderWindow === 'start-soon'
          ? 'Your time for this starts soon.'
          : reminderWindow === '3-day' ? 'Coming up in the next few days.' : 'Coming up tomorrow or sooner.';
        const title = reminderWindow === 'start-soon' ? `Starting soon: ${event.title}` : `${event.type}: ${event.title}`;
        new Notification(title, { body: `${headsUp} ${when}.`, tag: notificationKey });
        newKeys.push(notificationKey);
      } catch { /* Browser notifications may be unavailable in an embedded tab. */ }
    }
    if (newKeys.length) {
      try { localStorage.setItem(`echo-notified-reminders:${userId}`, JSON.stringify([...notified, ...newKeys].slice(-100))); }
      catch { /* Notifications still work even when browser storage is unavailable. */ }
    }
  }, [events, userId, pushEnabled]);

  useEffect(() => {
    notifyDueSoon();
    const timer = window.setInterval(notifyDueSoon, 60_000);
    return () => window.clearInterval(timer);
  }, [notifyDueSoon]);

  const permissionLabel = useMemo(() => {
    if (permission === 'granted' && pushEnabled) return 'Background reminders are on. Echo will remind you before saved time blocks start, even when this page is closed.';
    if (permission === 'granted') return pushSupported
      ? 'Turn on background reminders to hear about upcoming dates and saved time blocks, even when this page is closed.'
      : 'This browser does not support background push. Reminders work only while Echo is open.';
    if (permission === 'denied') return 'Browser notifications are blocked. Change this site’s notification permission in your browser settings.';
    if (permission === 'unsupported') return 'This browser does not support desktop notifications. Upcoming reminders still appear here.';
    return 'Turn on background reminders for upcoming dates and saved time blocks, even when this page is closed.';
  }, [permission, pushEnabled, pushSupported]);

  const enableNotifications = async () => {
    if (typeof Notification === 'undefined') { setPermission('unsupported'); return; }
    try {
      const value = await Notification.requestPermission();
      setPermission(value);
      if (value !== 'granted') return;
      if (!pushSupported) return;
      await navigator.serviceWorker.register('/sw.js');
      const registration = await navigator.serviceWorker.ready;
      const { public_key: publicKey } = await api.getPushPublicKey();
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKeyBytes(publicKey)
        });
      }
      await api.savePushSubscription(userId, subscription.toJSON(), Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
      setPushEnabled(true);
      setPushError('');
    } catch (error) {
      setPushError(error?.message || 'Background reminders could not be enabled. Please try again.');
    }
  };

  const disableNotifications = async () => {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await api.removePushSubscription(userId, subscription.endpoint);
        await subscription.unsubscribe();
      }
      setPushEnabled(false);
      setPushError('');
    } catch {
      setPushError('I couldn’t turn reminders off just now. Please try again.');
    }
  };

  const sendTestNotification = async () => {
    setTestPushStatus('Sending a test…');
    try {
      await api.sendPushTest(userId);
      setTestPushStatus('Test sent. Check your device notifications.');
    } catch (error) {
      setTestPushStatus(error?.message || 'The test notification could not be sent.');
    }
  };

  const soonCount = events.filter((event) => event.date.getTime() >= now && event.date.getTime() <= now + REMINDER_WINDOW_MS).length;
  const permissions = knowledge?.active_permissions || {};
  const hasReminderPermission = Boolean(permissions.deadlines_key_dates ?? permissions.deadlines) || Boolean(permissions.schedule_commitments ?? permissions.timetable);

  return <div className="relative">
    <button type="button" onClick={() => { const next = !open; setOpen(next); if (next) refresh(); }} aria-label={soonCount ? `Notifications, ${soonCount} coming up soon` : 'Notifications'} aria-expanded={open} className="relative min-h-11 min-w-11 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark flex items-center justify-center text-content-mutedLight dark:text-content-mutedDark hover:text-brand-purple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple">
      {permission === 'granted' ? <BellRing className="h-4 w-4"/> : <Bell className="h-4 w-4"/>}
      {soonCount > 0 && <span aria-hidden="true" className="absolute -right-1 -top-1 min-w-5 h-5 rounded-full bg-brand-purple px-1 text-[10px] font-bold leading-5 text-white">{soonCount > 9 ? '9+' : soonCount}</span>}
    </button>
    {open && <section className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark p-4 shadow-xl" aria-label="Upcoming notifications">
      <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-bold text-content-mainLight dark:text-content-mainDark">Reminders</h2><button type="button" onClick={() => setOpen(false)} className="min-h-11 px-3 text-sm text-brand-purple">Close</button></div>
      <p className="mt-1 text-xs text-content-mutedLight dark:text-content-mutedDark">{permissionLabel}</p>
      {(permission === 'default' || (permission === 'granted' && !pushEnabled && pushSupported)) && <button type="button" onClick={enableNotifications} className="mt-3 min-h-11 w-full rounded-full bg-brand-gradient px-4 text-sm font-semibold text-white">Enable background reminders</button>}
      {pushEnabled && <button type="button" onClick={disableNotifications} className="mt-3 min-h-11 w-full rounded-full border border-stroke-light dark:border-stroke-dark px-4 text-sm font-semibold">Turn off background reminders</button>}
      {pushEnabled && <button type="button" onClick={sendTestNotification} className="mt-2 min-h-11 w-full rounded-full border border-brand-purple/30 px-4 text-sm font-semibold text-brand-purple">Send a test notification</button>}
      {pushError && <p role="status" className="mt-2 text-xs text-rose-600 dark:text-rose-300">{pushError}</p>}
      {testPushStatus && <p role="status" className="mt-2 text-xs text-content-mutedLight dark:text-content-mutedDark">{testPushStatus}</p>}
      {loadFailed ? <p className="mt-4 text-sm text-content-mutedLight dark:text-content-mutedDark">I couldn’t load your saved dates. Try opening this again.</p>
        : events.length ? <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto">{events.slice(0, 8).map((event) => <li key={event.id} className="rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark p-3"><p className="text-sm font-semibold text-content-mainLight dark:text-content-mainDark">{event.title}</p><p className="mt-1 text-xs text-content-mutedLight dark:text-content-mutedDark">{event.type} · {event.date.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</p></li>)}</ul>
          : !hasReminderPermission ? <div className="mt-4 space-y-2"><p className="text-sm text-content-mutedLight dark:text-content-mutedDark">Turn on Schedule & Commitments or Deadlines & Key Dates in Privacy to see reminders.</p><button type="button" onClick={onOpenPrivacy} className="min-h-11 text-sm font-semibold text-brand-purple underline">Open Privacy</button></div>
            : <p className="mt-4 text-sm text-content-mutedLight dark:text-content-mutedDark">No saved dates in the next week.</p>}
    </section>}
  </div>;
}
