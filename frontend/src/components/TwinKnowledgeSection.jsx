import React, { useState, useEffect } from 'react';
import EchoOrb from './EchoOrb';
import {
  Calendar, Clock, BookOpen, Sliders, CheckSquare,
  Trash2, Edit2, Check, X, Sparkles, Brain, Heart, Rocket
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const CATEGORIES = [
  { key: 'memories', label: 'Important details', icon: Brain },
  { key: 'deadlines', label: 'Deadlines', icon: Clock },
  { key: 'timetable', label: 'Schedule', icon: Calendar },
  { key: 'study_log', label: 'Focus & Work Logs', icon: BookOpen },
  { key: 'preferences', label: 'Preferences', icon: Sliders }
];

export default function TwinKnowledgeSection({ api, profile }) {
  const { twinName } = useTheme();
  const [knowledge, setKnowledge] = useState(null);
  const [activeCategory, setActiveCategory] = useState('memories');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [memoryLabels, setMemoryLabels] = useState({});

  // Editing item state
  const [editingId, setEditingId] = useState(null);
  const [editingCategory, setEditingCategory] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [editHours, setEditHours] = useState('');

  const userId = profile?.user_id || 'demo-alex-rivers';
  const weights = profile?.weights || { rational: 0.5, emotional: 0.25, ambitious: 0.25 };
  const primaryTwin = profile?.primary_twin || 'rational';

  const loadKnowledge = async () => {
    setLoading(true);
    try {
      const data = await api.getTwinKnowledge(userId);
      setKnowledge(data);
    } catch (err) {
      console.error('Failed to load twin knowledge:', err);
      setStatusMsg("Hmm, I couldn't pull that up. Try again?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKnowledge();
    api.getMemoryRegistry(profile?.persona || 'other').then((data) => setMemoryLabels(Object.fromEntries((data.categories || []).map((item) => [item.id, item.title])))).catch(() => {});
  }, [userId]);

  const handleDelete = async (source, id, category = '') => {
    if (!window.confirm(`Delete this item from ${source}?`)) return;
    try {
      await api.deleteKnowledgeItem(source, id, userId, category);
      setStatusMsg("That's removed now.");
      loadKnowledge();
      setTimeout(() => setStatusMsg(''), 3000);
    } catch (err) {
      console.error('Delete failed:', err);
      setStatusMsg("Hmm, I couldn't remove that. Try again?");
    }
  };

  const startEdit = (item) => {
    setEditingId(item.id);
    setEditingCategory(item.category || '');
    setEditTitle(item.fact || item.title || item.activity_name || item.value || '');
    setEditHours(item.estimated_hours?.toString() || '');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
    setEditHours('');
  };

  const saveEdit = async (source, id) => {
    try {
      const payload = {
        title_or_activity: editTitle,
        value: activeCategory === 'memories' ? editTitle : undefined,
        estimated_hours: editHours ? parseFloat(editHours) : null
      };
      await api.editKnowledgeItem(source, id, payload, userId, editingCategory);
      setStatusMsg("Got it. That change is saved.");
      cancelEdit();
      loadKnowledge();
      setTimeout(() => setStatusMsg(''), 3000);
    } catch (err) {
      console.error('Update failed:', err);
      setStatusMsg("Hmm, I couldn't save that change. Try again?");
    }
  };

  const rPct = Math.round((weights.rational || 0.5) * 100);
  const ePct = Math.round((weights.emotional || 0.25) * 100);
  const aPct = Math.round((weights.ambitious || 0.25) * 100);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 pb-24 space-y-8 animate-fadeIn">
      {/* Header & Persona Card */}
      <div className="p-6 sm:p-8 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center space-x-4 text-center sm:text-left">
          <EchoOrb size="lg" style={primaryTwin} state="idle" title={twinName} />
          <div className="space-y-1">
            <span className="text-xs uppercase font-mono font-bold px-2.5 py-0.5 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark text-brand-purple dark:text-[#A894FF] border border-stroke-light dark:border-stroke-dark">
              Current voice: {primaryTwin}
            </span>
            <h2 className="text-2xl font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              {twinName}
            </h2>
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
              {twinName} keeps this view in step with the choices you've been making.
            </p>
          </div>
        </div>

        {/* Weights Summary Bars */}
        <div className="w-full sm:w-60 space-y-2.5 p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark">
          <span className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark block uppercase tracking-wider">
            Thinking Styles
          </span>

          <div className="space-y-1.5 text-xs font-medium">
            <div className="flex justify-between">
              <span className="text-style-rational font-bold">Rational</span>
              <span className="font-mono">{rPct}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-light dark:bg-surface-dark overflow-hidden">
              <div className="h-full bg-style-rational transition-all duration-500" style={{ width: `${rPct}%` }} />
            </div>

            <div className="flex justify-between">
              <span className="text-style-emotional font-bold">Emotional</span>
              <span className="font-mono">{ePct}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-light dark:bg-surface-dark overflow-hidden">
              <div className="h-full bg-style-emotional transition-all duration-500" style={{ width: `${ePct}%` }} />
            </div>

            <div className="flex justify-between">
              <span className="text-style-ambitiousFrom font-bold">Ambitious</span>
              <span className="font-mono">{aPct}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-light dark:bg-surface-dark overflow-hidden">
              <div className="h-full bg-style-ambitiousFrom transition-all duration-500" style={{ width: `${aPct}%` }} />
            </div>
          </div>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 rounded-2xl bg-brand-purple/10 border border-brand-purple/30 text-xs font-medium text-brand-purple dark:text-[#A894FF] flex items-center space-x-2 animate-fadeIn">
          <Sparkles className="w-4 h-4 flex-shrink-0" />
          <span>{statusMsg}</span>
        </div>
      )}

      <section className="p-5 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark space-y-3">
        <h3 className="text-lg font-bold font-heading">What I've learned about you</h3>
        {!knowledge ? <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">Loading permitted patterns…</p> : <div className="space-y-2 text-sm">
          {knowledge.active_permissions?.focus_work_patterns && knowledge.study_history?.length > 0 && (() => { const counts = knowledge.study_history.reduce((acc, item) => { const key = item.time_of_day || 'varied times'; acc[key] = (acc[key] || 0) + (item.focus_rating || 0); return acc; }, {}); const peak = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0]; return <p>Focus ratings are strongest during <strong>{peak}</strong>. <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">Source: {memoryLabels.focus_work_patterns || 'Focus & Work Patterns'}</span></p>; })()}
          {knowledge.active_permissions?.deadlines_key_dates && knowledge.deadlines?.some((item) => item.actual_hours && item.estimated_hours) && (() => { const rows = knowledge.deadlines.filter((item) => item.actual_hours && item.estimated_hours); const ratio = rows.reduce((sum, item) => sum + item.actual_hours / item.estimated_hours, 0) / rows.length; return <p>{ratio > 1.15 ? 'Completed tasks have tended to take longer than estimated.' : ratio < 0.85 ? 'Completed tasks have tended to take less time than estimated.' : 'Time estimates have been close to actual effort so far.'} <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">Source: {memoryLabels.deadlines_key_dates || 'Deadlines & Key Dates'}</span></p>; })()}
          {knowledge.active_permissions?.goals && knowledge.goals?.length > 0 && <p>You have {knowledge.goals.filter((goal) => goal.status === 'active').length} active goal{knowledge.goals.filter((goal) => goal.status === 'active').length === 1 ? '' : 's'}. <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">Source: {memoryLabels.goals || 'Goals'}</span></p>}
          {(!knowledge.active_permissions?.focus_work_patterns || !knowledge.study_history?.length) && (!knowledge.active_permissions?.deadlines_key_dates || !knowledge.deadlines?.some((item) => item.actual_hours && item.estimated_hours)) && (!knowledge.active_permissions?.goals || !knowledge.goals?.length) && <p className="text-content-mutedLight dark:text-content-mutedDark">Echo is still learning. Share a few details when you're ready to see patterns here.</p>}
        </div>}
      </section>

      {/* Memory Inspector ("What Echo Knows") */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold font-heading text-content-mainLight dark:text-content-mainDark">
            What {twinName} remembers
          </h3>
          <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">
            It's yours to review, change, or remove anytime.
          </span>
        </div>

        {/* Segmented Category Tabs */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-1">
          {CATEGORIES.map(c => {
            const isActive = activeCategory === c.key;
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => setActiveCategory(c.key)}
                className={`px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap transition flex items-center space-x-1.5 ${
                  isActive
                    ? 'bg-brand-purple text-white shadow-sm'
                    : 'bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark'
                }`}
              >
                <c.icon className="w-3.5 h-3.5" />
                <span>{c.label}</span>
              </button>
            );
          })}
        </div>

        {/* Items List */}
        <div className="space-y-3">
          {loading ? (
            <div className="p-8 text-center text-xs text-content-mutedLight dark:text-content-mutedDark">
              Pulling everything together...
            </div>
          ) : !knowledge?.[activeCategory] || knowledge[activeCategory].length === 0 ? (
            <div className="p-8 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-center text-xs text-content-mutedLight dark:text-content-mutedDark">
              No entries stored in {activeCategory}.
            </div>
          ) : (
            knowledge[activeCategory].map(item => {
              const isEditing = editingId === item.id;
              const titleText = item.fact || item.title || item.activity_name || item.preference_key || item.task_name || 'Entry';
              const secondaryText = item.category ? `${memoryLabels[item.category] || item.category} · importance ${item.importance}/5` : item.course_code || item.notes || item.value || (item.estimated_hours ? `${item.estimated_hours}h estimated` : '');

              return (
                <div
                  key={item.id}
                  className="p-4 rounded-2xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-sm flex items-center justify-between gap-3 hover:border-brand-purple/40 transition"
                >
                  {isEditing ? (
                    <div className="flex-1 flex items-center space-x-2">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="flex-1 px-3 py-1.5 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-content-mainLight dark:text-content-mainDark font-medium"
                      />
                      {item.estimated_hours !== undefined && (
                        <input
                          type="number"
                          step="0.5"
                          value={editHours}
                          onChange={(e) => setEditHours(e.target.value)}
                          placeholder="Hrs"
                          className="w-16 px-2 py-1.5 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-center font-mono text-content-mainLight dark:text-content-mainDark"
                        />
                      )}
                      <button
                        onClick={() => saveEdit(activeCategory, item.id)}
                        className="p-2 rounded-full bg-emerald-500 text-white hover:bg-emerald-600 transition"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="p-2 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark transition"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="space-y-0.5 flex-1 min-w-0">
                        <h4 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark truncate">
                          {titleText}
                        </h4>
                        {secondaryText && (
                          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark truncate">
                            {secondaryText}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center space-x-1 flex-shrink-0">
                        <button
                          onClick={() => startEdit(item)}
                          className="p-2 rounded-full text-content-mutedLight dark:text-content-mutedDark hover:text-brand-purple hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark transition"
                          title="Edit"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(activeCategory, item.id, item.category)}
                          className="p-2 rounded-full text-content-mutedLight dark:text-content-mutedDark hover:text-rose-500 hover:bg-rose-500/10 transition"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
