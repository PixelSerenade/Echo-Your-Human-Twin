import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Check, Plus, MessageCircle, Trash2, X } from 'lucide-react';
import { formatTimeValue, localDateKey } from '../utils/localDateTime';

const EMPTY = "Nothing here yet. Tell me what's coming up, or add it here, and I'll help you keep track.";
const CATEGORY = {
  schedule_commitments: 'Schedule & Commitments',
  deadlines_key_dates: 'Deadlines & Key Dates',
  goals: 'Goals',
  spending_money: 'Spending & Money'
};
const TABS = ['Today', 'This Week', 'Goals', 'Money'];
const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function goalProgress(goal) {
  const value = goal.status?.toLowerCase() === 'completed' ? 100 : Number(goal.progress || 0);
  return Math.max(0, Math.min(100, value));
}

export default function MyPlanSection({ api, profile, userId, onAskEcho }) {
  const [tab, setTab] = useState('Today');
  const [knowledge, setKnowledge] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: '', date: '', time: '', value: '', entry_type: 'expense', type: 'deadline', category: 'deadlines_key_dates' });
  const today = new Date();
  const weights = profile?.weights || {};
  const voiceStyle = Object.entries({ rational: weights.rational || 0, emotional: weights.emotional || 0, ambitious: weights.ambitious || 0 }).sort((a, b) => b[1] - a[1])[0]?.[0] || profile?.primary_twin || 'rational';
  const echoLine = {
    rational: "Here’s what’s on your plate. We can take it one step at a time.",
    emotional: "You don’t have to hold it all at once. Let’s take today gently.",
    ambitious: "You have a few things in motion today. One steady step at a time.",
  }[voiceStyle];
  const todayKey = localDateKey(today);
  const enabled = knowledge?.active_permissions || {};
  const moneyEnabled = Boolean(enabled.spending_money);
  const visibleTabs = moneyEnabled ? TABS : TABS.filter((name) => name !== 'Money');
  const readySources = useMemo(() => ({ schedule_commitments: Boolean(enabled.schedule_commitments ?? enabled.timetable), deadlines_key_dates: Boolean(enabled.deadlines_key_dates ?? enabled.deadlines), goals: Boolean(enabled.goals), spending_money: moneyEnabled }), [knowledge]);

  const load = async () => {
    setBusy(true); setError('');
    try { setKnowledge(await api.getTwinKnowledge(userId)); }
    catch { setKnowledge(null); setError("I couldn't load your plan just now. Please try again."); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    load();
    window.addEventListener('echo-reminders-refresh', load);
    return () => window.removeEventListener('echo-reminders-refresh', load);
  }, [userId]);
  useEffect(() => { if (!visibleTabs.includes(tab)) setTab('Today'); }, [moneyEnabled]);

  const deadlines = knowledge?.deadlines || [];
  const commitments = knowledge?.timetable || [];
  const goals = knowledge?.goals || [];
  const todayItems = [
    ...(readySources.schedule_commitments ? commitments.filter((x) => x.specific_date ? localDateKey(x.specific_date) === todayKey : x.day_of_week === dayNames[today.getDay()]).map((x) => ({ title: x.activity_name, detail: `${formatTimeValue(x.start_time)}–${formatTimeValue(x.end_time)}`, kind: 'Commitment' })) : []),
    ...(readySources.deadlines_key_dates ? deadlines.filter((x) => localDateKey(x.due_date) === todayKey && !x.completed).map((x) => ({ title: x.title, detail: x.course_or_project, kind: 'Due today' })) : [])
  ];
  const hasAgendaPermission = readySources.schedule_commitments || readySources.deadlines_key_dates;
  const weekStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const mondayOffset = (weekStart.getDay() + 6) % 7;
  weekStart.setDate(weekStart.getDate() - mondayOffset);
  const weekDays = Array.from({ length: 7 }, (_, i) => { const d = new Date(weekStart); d.setDate(weekStart.getDate() + i); return d; });
  const weekItems = (date) => [
    ...(readySources.schedule_commitments ? commitments.filter((x) => x.specific_date ? localDateKey(x.specific_date) === localDateKey(date) : x.day_of_week === dayNames[date.getDay()]).map((x) => ({ title: x.activity_name, time: `${formatTimeValue(x.start_time)}–${formatTimeValue(x.end_time)}`, kind: 'Commitment' })) : []),
    ...(readySources.deadlines_key_dates ? deadlines.filter((x) => localDateKey(x.due_date) === localDateKey(date) && !x.completed).map((x) => {
      const due = new Date(x.due_date);
      const allDay = due.getHours() === 0 && due.getMinutes() === 0;
      return { title: x.title, time: allDay ? '' : due.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }), kind: 'Due' };
    }) : [])
  ];
  const scheduledWeekDays = weekDays.map((date) => ({ date, items: weekItems(date) })).filter((day) => day.items.length > 0);
  const moneyEntries = (knowledge?.money_entries || []).filter((item) => {
    const date = new Date(item.entry_date);
    return date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth();
  });
  const monthlySpend = moneyEntries.filter((item) => item.entry_type === 'expense').reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const spendingByCategory = Object.entries(moneyEntries.filter((item) => item.entry_type === 'expense').reduce((all, item) => ({ ...all, [item.category]: (all[item.category] || 0) + Number(item.amount || 0) }), {}));
  const budgets = moneyEntries.filter((item) => item.entry_type === 'budget');

  const addItem = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      await api.createPlanItem({ user_id: userId, category: form.category, title: form.title.trim(), date: form.date || null, time: form.time || null, value: form.value || null, entry_type: form.entry_type, type: form.type });
      window.dispatchEvent(new Event('echo-reminders-refresh'));
      setAdding(false); setForm({ title: '', date: '', time: '', value: '', entry_type: 'expense', type: 'deadline', category: readySources.schedule_commitments ? 'schedule_commitments' : 'deadlines_key_dates' });
      await load();
    } catch (err) { setError(err.message || "I couldn't save that yet. Please try again."); }
    finally { setSaving(false); }
  };

  const toggleMilestone = async (goal, index) => {
    const milestones = (goal.milestones || []).map((item, itemIndex) => itemIndex === index ? { ...item, completed: !item.completed } : item);
    setError('');
    try {
      await api.updateGoal(userId, goal.id, milestones);
      await load();
    } catch (err) { setError(err.message || "I couldn't update that goal just now. Please try again."); }
  };

  const deleteGoal = async (goal) => {
    if (!window.confirm(`Delete “${goal.title}” and its saved progress? This can't be undone.`)) return;
    setError('');
    try {
      await api.deleteGoal(userId, goal.id);
      await load();
    } catch (err) { setError(err.message || "I couldn't delete that goal just now. Please try again."); }
  };

  const toggleTab = (event, index) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const nextIndex = (index + (event.key === 'ArrowRight' ? 1 : -1) + visibleTabs.length) % visibleTabs.length;
    setTab(visibleTabs[nextIndex]); document.getElementById(`plan-tab-${visibleTabs[nextIndex]}`)?.focus();
  };
  const offMessage = (category) => <p className="rounded-2xl border border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark p-4 text-sm text-content-mutedLight dark:text-content-mutedDark">Turn on {CATEGORY[category]} in Privacy to see this here.</p>;
  const empty = <p className="py-8 text-center text-sm text-content-mutedLight dark:text-content-mutedDark">{EMPTY}</p>;

  return <section className="mx-auto w-full max-w-5xl px-4 sm:px-6 py-6 sm:py-10 pb-24 md:pb-10">
    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div><h1 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">My Plan</h1><p className="mt-1 text-sm text-content-mutedLight dark:text-content-mutedDark">A clear view of what you’ve shared.</p></div>
      <div className="flex gap-2"><button onClick={() => { setError(''); setForm({ ...form, category: readySources.schedule_commitments ? 'schedule_commitments' : 'deadlines_key_dates' }); setAdding(true); }} className="min-h-11 px-4 rounded-full bg-brand-gradient text-white text-sm font-semibold inline-flex items-center gap-2"><Plus className="w-4 h-4"/>Add something</button><button onClick={() => onAskEcho('Help me make a plan using the things I have shared.')} className="min-h-11 px-4 rounded-full border border-stroke-light dark:border-stroke-dark text-sm font-semibold text-brand-purple inline-flex items-center gap-2"><MessageCircle className="w-4 h-4"/>Talk to Echo</button></div>
    </div>
    <div role="tablist" aria-label="Plan sections" className="flex gap-2 overflow-x-auto pb-2 mb-5">
      {visibleTabs.map((name, i) => <button id={`plan-tab-${name}`} role="tab" aria-selected={tab === name} aria-controls="plan-panel" key={name} onClick={() => setTab(name)} onKeyDown={(e) => toggleTab(e, i)} className={`min-h-11 min-w-24 px-5 rounded-full text-sm font-semibold whitespace-nowrap ${tab === name ? 'bg-brand-purple text-white' : 'bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mutedLight dark:text-content-mutedDark'}`}>{name}</button>)}
    </div>
    <div id="plan-panel" role="tabpanel" aria-labelledby={`plan-tab-${tab}`} className="rounded-3xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark p-4 sm:p-7 min-h-64">
      {busy ? <p className="py-10 text-center text-sm text-content-mutedLight dark:text-content-mutedDark">Loading your plan…</p> : error && !knowledge ? <div className="py-10 text-center text-sm text-content-mutedLight dark:text-content-mutedDark">{error}<button onClick={load} className="ml-2 underline text-brand-purple">Try again</button></div> : <>
        {error && <p role="alert" className="mb-4 text-sm text-rose-600">{error}</p>}
        {tab === 'Today' && <div><h2 className="text-lg font-bold mb-4 text-content-mainLight dark:text-content-mainDark">Today</h2><div className="space-y-5">{!readySources.schedule_commitments && offMessage('schedule_commitments')}{!readySources.deadlines_key_dates && offMessage('deadlines_key_dates')}{hasAgendaPermission && (todayItems.length ? <><h3 className="text-sm font-semibold text-content-mainLight dark:text-content-mainDark">What matters most</h3><ul className="space-y-3">{todayItems.slice(0, 3).map((item, i) => <li key={`${item.kind}-${i}`} className="flex gap-3 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark p-4"><CalendarDays className="w-5 h-5 text-brand-purple shrink-0"/><div><p className="font-semibold text-content-mainLight dark:text-content-mainDark">{item.title}</p><p className="text-sm text-content-mutedLight dark:text-content-mutedDark">{item.kind}{item.detail ? ` · ${item.detail}` : ''}</p></div></li>)}</ul></> : empty)}<p className="text-sm text-content-mutedLight dark:text-content-mutedDark">{echoLine}</p></div></div>}
        {tab === 'This Week' && <div><h2 className="text-lg font-bold mb-4 text-content-mainLight dark:text-content-mainDark">This Week</h2>{!readySources.schedule_commitments && offMessage('schedule_commitments')}{!readySources.deadlines_key_dates && offMessage('deadlines_key_dates')}{hasAgendaPermission && (scheduledWeekDays.length ? <div className="space-y-3">{scheduledWeekDays.map(({ date, items }) => <div key={localDateKey(date)} className="rounded-2xl border border-stroke-light dark:border-stroke-dark p-4"><h3 className="font-semibold text-content-mainLight dark:text-content-mainDark">{date.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}</h3><ul className="mt-2 space-y-2">{items.map((item, i) => <li key={`${item.kind}-${i}`} className="text-sm text-content-mainLight dark:text-content-mainDark"><span className="text-brand-purple font-medium">{item.kind}</span> · {item.title}{item.time ? ` · ${item.time}` : ''}</li>)}</ul>{items.length > 1 && <button onClick={() => onAskEcho('Help me plan around the commitments and dates I have shared this week.')} className="mt-3 min-h-11 text-sm text-brand-purple underline">These two land on the same day. Want help planning them?</button>}</div>)}</div> : <p className="py-8 text-center text-sm text-content-mutedLight dark:text-content-mutedDark">Nothing is scheduled this week yet. Add something and it’ll show up on its date.</p>)}</div>}
        {tab === 'Goals' && <div><h2 className="text-lg font-bold mb-4 text-content-mainLight dark:text-content-mainDark">Goals</h2>{!readySources.goals ? offMessage('goals') : goals.length ? <div className="grid gap-3 sm:grid-cols-2">{goals.map((goal) => <article key={goal.id} className="rounded-2xl border border-stroke-light dark:border-stroke-dark p-4"><div className="flex items-start justify-between gap-3"><h3 className="font-semibold text-content-mainLight dark:text-content-mainDark">{goal.title}</h3><button type="button" aria-label={`Delete goal ${goal.title}`} title="Delete goal" onClick={() => deleteGoal(goal)} className="flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full text-content-mutedLight hover:bg-surface-subtleLight hover:text-rose-600 dark:text-content-mutedDark dark:hover:bg-surface-subtleDark"><Trash2 className="h-4 w-4"/></button></div>{goal.description && <p className="mt-1 text-sm text-content-mutedLight dark:text-content-mutedDark">{goal.description}</p>}<div className="mt-3 flex items-center justify-between text-sm"><span>Progress</span><span>{goalProgress(goal)}%</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark"><div className="h-full rounded-full bg-brand-gradient" style={{ width: `${goalProgress(goal)}%` }}/></div>{goal.next_step && <p className="mt-3 text-sm text-content-mutedLight dark:text-content-mutedDark">Next step: {goal.next_step}</p>}<h4 className="mt-4 text-sm font-semibold">Milestones</h4>{goal.milestones?.length ? <ul className="mt-2 space-y-2">{goal.milestones.map((milestone, index) => <li key={`${milestone.title}-${index}`}><button type="button" role="checkbox" aria-checked={Boolean(milestone.completed)} onClick={() => toggleMilestone(goal, index)} className="flex min-h-11 w-full items-center gap-2 rounded-lg px-1 text-left text-sm hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark"><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${milestone.completed ? 'border-brand-purple bg-brand-purple text-white' : 'border-content-mutedLight dark:border-content-mutedDark'}`}>{milestone.completed && <Check className="h-4 w-4"/>}</span><span className={milestone.completed ? 'line-through text-content-mutedLight dark:text-content-mutedDark' : ''}>{milestone.title}</span></button></li>)}</ul> : <p className="mt-1 text-sm text-content-mutedLight dark:text-content-mutedDark">Echo will add steps when there’s enough detail to make a useful plan.</p>}{goal.target_date && <p className="mt-3 text-sm text-brand-purple">By {new Date(goal.target_date).toLocaleDateString()}</p>}</article>)}</div> : empty}</div>}
        {tab === 'Money' && moneyEnabled && <div><h2 className="text-lg font-bold mb-4 text-content-mainLight dark:text-content-mainDark">Money</h2>{moneyEntries.length > 0 && <section className="mb-5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark p-4"><p className="text-sm text-content-mutedLight dark:text-content-mutedDark">Spent this month</p><p className="text-2xl font-bold text-content-mainLight dark:text-content-mainDark">{new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(monthlySpend)}</p></section>}{spendingByCategory.length > 0 && <><h3 className="font-semibold mb-2">Categories</h3><ul className="space-y-2">{spendingByCategory.map(([category, amount]) => <li key={category} className="flex justify-between rounded-xl border border-stroke-light dark:border-stroke-dark p-3"><span>{category}</span><span>{new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount)}</span></li>)}</ul></>}{budgets.length > 0 && <><h3 className="font-semibold mt-5 mb-2">Budgets</h3><ul className="space-y-2">{budgets.map((item) => <li key={item.id} className="flex justify-between rounded-xl border border-stroke-light dark:border-stroke-dark p-3"><span>{item.category}</span><span>{new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(item.amount)}</span></li>)}</ul></>}{moneyEntries.length === 0 && empty}</div>}
      </>}
    </div>
    {adding && <div className="fixed inset-0 z-50 bg-black/40 p-4 flex items-center justify-center" onMouseDown={(e) => { if (e.target === e.currentTarget) setAdding(false); }}><form onSubmit={addItem} className="w-full max-w-md rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark p-5 sm:p-7 space-y-4"><div className="flex justify-between"><h2 className="text-xl font-bold">Add something</h2><button type="button" aria-label="Close" className="min-h-11 min-w-11 flex justify-center items-center" onClick={() => setAdding(false)}><X/></button></div><label className="block text-sm">What is it?<input required maxLength="200" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-3"/></label><label className="block text-sm">Type<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value, type: e.target.value === 'schedule_commitments' ? 'commitment' : e.target.value === 'goals' ? 'goal' : e.target.value === 'spending_money' ? 'money' : 'deadline' })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark px-3">{readySources.schedule_commitments && <option value="schedule_commitments">Commitment</option>}{readySources.deadlines_key_dates && <option value="deadlines_key_dates">Deadline or date</option>}{readySources.goals && <option value="goals">Goal</option>}{readySources.spending_money && <option value="spending_money">Spending or budget</option>}</select></label>{form.category !== 'spending_money' && form.category !== 'goals' && <div className="grid grid-cols-2 gap-3"><label className="block text-sm">Date<input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-2"/></label><label className="block text-sm">Time<input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-2"/></label></div>}{form.category === 'goals' && <label className="block text-sm">Target date<input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-2"/></label>}{form.category === 'spending_money' && <label className="block text-sm">Amount<input required type="number" min="0" step="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} placeholder="Amount" className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-3"/></label>}{form.category === 'spending_money' && <label className="block text-sm">Entry type<select value={form.entry_type} onChange={(e) => setForm({ ...form, entry_type: e.target.value })} className="mt-1 w-full min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark px-3"><option value="expense">Spending</option><option value="budget">Budget</option></select></label>}<button disabled={saving} className="min-h-11 w-full rounded-full bg-brand-gradient text-white font-semibold disabled:opacity-60">{saving ? 'Saving…' : 'Save'}</button></form></div>}
  </section>;
}
