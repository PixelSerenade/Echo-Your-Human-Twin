import React, { useState, useEffect } from 'react';
import EchoOrb from './EchoOrb';
import SlideUpDrawer from './SlideUpDrawer';
import {
  Sparkles, CheckCircle, Circle, Bell, BellOff,
  BarChart2, Trash2, Plus, Sliders, ChevronDown, ChevronUp,
  Info, BatteryCharging, Smile, BookOpen, Clock, ArrowRight,
  MessageSquare
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const ACTIVITY_OPTIONS = ['focused work', 'badminton', 'netflix', 'project work', 'sleep'];

const FOUR_METRICS = [
  { key: 'energy', label: 'Energy', icon: BatteryCharging, color: '#FF9F43' },
  { key: 'happiness', label: 'Happiness', icon: Smile, color: '#FF8FA3' },
  { key: 'study', label: 'Personal Progress', icon: BookOpen, color: '#2EC4B6' },
  { key: 'free_time', label: 'Free Time', icon: Clock, color: '#7C5CFF' }
];

export default function SimulatorSection({
  api,
  profile,
  activePlan,
  onUpdatePlan,
  onAskEcho
}) {
  const { twinName, setActivePage } = useTheme();
  const [dimensionLabels, setDimensionLabels] = useState({ progress: 'Personal Progress', goals: 'Goal Progress' });
  useEffect(() => { api.getMemoryRegistry(profile?.persona || 'other').then((data) => setDimensionLabels(data.simulator_labels || {})).catch(() => {}); }, [api, profile?.persona]);

  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [reflectionFeedback, setReflectionFeedback] = useState(activePlan?.reflection || null);
  const [showAdvancedSimulator, setShowAdvancedSimulator] = useState(false);

  // Manual scenario state for optional advanced builder
  const [pathA, setPathA] = useState([
    { activity: 'focused work', hours: 3.0 },
    { activity: 'badminton', hours: 1.5 },
    { activity: 'sleep', hours: 7.5 }
  ]);

  const [pathB, setPathB] = useState([
    { activity: 'focused work', hours: 8.0 },
    { activity: 'netflix', hours: 1.5 },
    { activity: 'sleep', hours: 3.5 }
  ]);

  const [manualResult, setManualResult] = useState(null);
  const [isRunningManual, setIsRunningManual] = useState(false);
  const [newPatternLearned, setNewPatternLearned] = useState(null);

  // Correction Form state
  const [correctionActivity, setCorrectionActivity] = useState('badminton');
  const [correctionMetric, setCorrectionMetric] = useState('focus');
  const [correctionDelta, setCorrectionDelta] = useState(1.5);
  const [correctionDesc, setCorrectionDesc] = useState('Badminton dramatically improves next-session focus');

  // Toggle step completion in active plan
  const handleToggleStep = (stepIdx) => {
    if (!activePlan) return;
    const updatedSteps = activePlan.steps.map((st, i) =>
      i === stepIdx ? { ...st, completed: !st.completed } : st
    );
    onUpdatePlan({ ...activePlan, steps: updatedSteps });
  };

  // Toggle reminders in active plan
  const handleToggleReminders = () => {
    if (!activePlan) return;
    onUpdatePlan({ ...activePlan, remindersEnabled: !activePlan.remindersEnabled });
  };

  // Submit plan reflection
  const handlePlanReflection = async (rating) => {
    setReflectionFeedback(rating);
    if (activePlan) {
      onUpdatePlan({ ...activePlan, reflection: rating });
    }
    try {
      await api.submitFeedback({
        user_id: profile?.user_id || 'demo-alex-rivers',
        question: `Plan reflection for ${activePlan?.name || 'schedule'}`,
        twin_recommended: profile?.primary_twin || 'rational',
        option_chosen: activePlan?.name || 'Your plan',
        aligned_twin: activePlan?.aligned_twin || 'rational',
        followed_recommendation: true,
        feedback_comment: `Plan felt: ${rating}`
      });
    } catch (err) {
      console.error('Failed to submit plan reflection:', err);
    }
  };

  // Manual simulation runner
  const handleRunManualSimulation = async () => {
    setIsRunningManual(true);
    setNewPatternLearned(null);
    try {
      const resp = await api.simulate({
        user_id: profile?.user_id || 'demo-alex-rivers',
        scenario_name: 'Manual Scenario Exploration',
        path_a: pathA,
        path_b: pathB
      });
      setManualResult(resp);
    } catch (err) {
      console.error('Simulation failed:', err);
    } finally {
      setIsRunningManual(false);
    }
  };

  // Save manual correction
  const handleSaveCorrection = async () => {
    try {
      const res = await api.correctSimulation({
        user_id: profile?.user_id || 'demo-alex-rivers',
        activity: correctionActivity,
        metric: correctionMetric,
        modifier_delta: parseFloat(correctionDelta),
        description: correctionDesc
      });
      setNewPatternLearned(res);
      handleRunManualSimulation();
    } catch (err) {
      console.error('Failed to teach twin:', err);
    }
  };

  const styleColors = {
    rational: '#2EC4B6',
    emotional: '#FF8FA3',
    ambitious: '#8B5CF6'
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 pb-28 space-y-8 animate-fadeIn">
      {/* ============================================================ */}
      {/* 1. ACTIVE PLAN VIEW (When user chose a path in chat) */}
      {/* ============================================================ */}
      {activePlan ? (
        <div className="space-y-6">
          {/* Header */}
          <div className="p-6 sm:p-7 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-brand-purple dark:text-[#A894FF]">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Your plan</span>
              </div>

              <div className="flex items-center space-x-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: styleColors[activePlan.aligned_twin] || '#7C5CFF' }}
                />
                <span
                  className="text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border"
                  style={{
                    color: styleColors[activePlan.aligned_twin] || '#7C5CFF',
                    borderColor: `${styleColors[activePlan.aligned_twin]}40`,
                    backgroundColor: `${styleColors[activePlan.aligned_twin]}15`
                  }}
                >
                  {activePlan.aligned_twin} Path
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <h2 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
                {activePlan.name}
              </h2>
              <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
                {activePlan.what_youll_achieve}
              </p>
            </div>

            {/* Reminder status banner */}
            <div className="pt-3 border-t border-stroke-light dark:border-stroke-dark flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs font-medium text-content-mainLight dark:text-content-mainDark">
                {activePlan.remindersEnabled ? (
                  <Bell className="w-4 h-4 text-brand-purple" />
                ) : (
                  <BellOff className="w-4 h-4 text-content-mutedLight dark:text-content-mutedDark" />
                )}
                <span>
                  {activePlan.remindersEnabled
                    ? `Quick nudge: ${twinName} will remind you before the next block.`
                    : 'Reminders are off for now.'}
                </span>
              </div>

              <button
                type="button"
                onClick={handleToggleReminders}
                className="text-xs font-semibold text-brand-purple hover:underline"
              >
                {activePlan.remindersEnabled ? 'Turn off' : 'Turn on'}
              </button>
            </div>
          </div>

          {/* Actionable Steps Checklist */}
          <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-content-mutedLight dark:text-content-mutedDark">
                What's next
              </span>
              <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                {activePlan.steps.every(s => s.completed)
                  ? 'You did it. Everything here is done.'
                  : `${activePlan.steps.filter(s => s.completed).length} of ${activePlan.steps.length} done. Keep going.`}
              </span>
            </div>

            <div className="space-y-2.5">
              {activePlan.steps.map((step, idx) => (
                <div
                  key={idx}
                  onClick={() => handleToggleStep(idx)}
                  className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                    step.completed
                      ? 'bg-surface-subtleLight/50 dark:bg-surface-subtleDark/50 border-stroke-light dark:border-stroke-dark opacity-60'
                      : 'bg-surface-subtleLight dark:bg-surface-subtleDark border-stroke-light dark:border-stroke-dark hover:border-brand-purple/40 shadow-sm'
                  }`}
                >
                  <div className="flex items-center space-x-3 truncate">
                    <button
                      type="button"
                      aria-label="Toggle step"
                      className="flex-shrink-0 text-brand-purple"
                    >
                      {step.completed ? (
                        <CheckCircle className="w-5 h-5 text-emerald-500 fill-emerald-500/20" />
                      ) : (
                        <Circle className="w-5 h-5 text-content-mutedLight dark:text-content-mutedDark" />
                      )}
                    </button>
                    <div className="space-y-0.5 truncate">
                      <span className="text-[11px] font-mono font-bold text-brand-purple dark:text-[#C5B8FF] block">
                        {step.time}
                      </span>
                      <p
                        className={`text-sm font-medium text-content-mainLight dark:text-content-mainDark truncate ${
                          step.completed ? 'line-through text-content-mutedLight dark:text-content-mutedDark' : ''
                        }`}
                      >
                        {step.task}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reflection Card: Did this path feel right today? */}
          <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-content-mutedLight dark:text-content-mutedDark block">
              Quick check-in
            </span>
            <p className="text-sm font-medium text-content-mainLight dark:text-content-mainDark">
              Did this path feel right for you today?
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {[
                { key: 'balanced', label: 'Felt balanced & focused', color: 'border-emerald-500 text-emerald-600 bg-emerald-500/10' },
                { key: 'too_intense', label: 'Too intense & tiring', color: 'border-amber-500 text-amber-600 bg-amber-500/10' },
                { key: 'need_more_study', label: 'Needed more focus time', color: 'border-purple-500 text-purple-600 bg-purple-500/10' }
              ].map(opt => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => handlePlanReflection(opt.key)}
                  className={`px-4 py-2 rounded-full text-xs font-semibold border transition ${
                    reflectionFeedback === opt.key
                      ? opt.color
                      : 'bg-surface-subtleLight dark:bg-surface-subtleDark border-stroke-light dark:border-stroke-dark text-content-mutedLight dark:text-content-mutedDark hover:border-brand-purple/40'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {reflectionFeedback && (
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium block pt-1">
                Got it. I'll use that next time we shape a plan.
              </span>
            )}
          </div>

          {/* Secondary Actions: Inspect Numbers & Clear Plan */}
          <div className="flex items-center justify-between flex-wrap gap-3 pt-2">
            <button
              type="button"
              onClick={() => setIsDetailsOpen(true)}
              className="px-4 py-2.5 rounded-full bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-brand-purple dark:text-[#A894FF] hover:border-brand-purple/50 shadow-sm transition flex items-center space-x-1.5"
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span>See the numbers behind this plan</span>
            </button>

            <button
              type="button"
              onClick={() => onUpdatePlan(null)}
              className="px-4 py-2.5 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-medium text-rose-500 hover:bg-rose-500/10 transition"
            >
              Let go of this plan
            </button>
          </div>
        </div>
      ) : (
        /* ============================================================ */
        /* 2. NO DEFAULT SIMULATOR UI: Serene, uncluttered empty state   */
        /* ============================================================ */
        <div className="py-12 sm:py-20 text-center space-y-6 animate-fadeIn">
          <div className="flex justify-center">
            <EchoOrb size="lg" style={profile?.primary_twin || 'rational'} state="idle" title={twinName} />
          </div>

          <div className="space-y-2 max-w-md mx-auto">
            <h2 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              Nothing planned yet
            </h2>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
              When you're ready, tell {twinName} what you're trying to balance. You'll get a couple of realistic paths to choose from.
            </p>
          </div>

          {/* Quick Prompt Chips */}
          <div className="flex flex-col sm:flex-row flex-wrap items-center justify-center gap-2.5 pt-2 max-w-xl mx-auto">
            {[
              { icon: '⚡', q: 'How should I organize two important priorities?' },
              { icon: '🎯', q: 'How should I prioritize two important deadlines this week?' },
              { icon: '☕', q: 'What tasks should I focus on tonight?' }
            ].map((chip, idx) => (
              <button
                key={idx}
                onClick={() => onAskEcho ? onAskEcho(chip.q) : setActivePage('chat')}
                className="w-full sm:w-auto px-4 py-2.5 rounded-full bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-content-mainLight dark:text-content-mainDark hover:border-brand-purple hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark shadow-sm transition flex items-center space-x-2"
              >
                <span>{chip.icon}</span>
                <span className="truncate">{chip.q}</span>
              </button>
            ))}
          </div>

          <div className="pt-4">
            <button
              onClick={() => onAskEcho ? onAskEcho('What should I do about my test and assignment?') : setActivePage('chat')}
              className="px-6 py-3 rounded-full bg-brand-gradient text-white text-xs font-bold shadow-md hover:scale-105 active:scale-95 transition inline-flex items-center space-x-2"
            >
              <MessageSquare className="w-4 h-4" />
              <span>Ask {twinName} in Chat</span>
            </button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 3. OPTIONAL ADVANCED SCENARIO BUILDER (Hidden by default)   */}
      {/* ============================================================ */}
      <div className="pt-6 border-t border-stroke-light dark:border-stroke-dark">
        <button
          type="button"
          onClick={() => setShowAdvancedSimulator(!showAdvancedSimulator)}
          className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight flex items-center space-x-1.5 transition mx-auto"
        >
          <Sliders className="w-3.5 h-3.5 text-brand-purple" />
          <span>Advanced: Manual Scenario Builder</span>
          {showAdvancedSimulator ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showAdvancedSimulator && (
          <div className="pt-6 space-y-6 animate-fadeIn">
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark text-center max-w-md mx-auto">
              Custom sandbox to test hypothetical hours and train learned modifiers directly.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* PATH A */}
              <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
                <div className="flex items-center justify-between border-b border-stroke-light dark:border-stroke-dark pb-3">
                  <span className="text-xs font-bold font-mono text-style-rational uppercase">
                    Path A &bull; Custom
                  </span>
                  <button
                    onClick={() => setPathA([...pathA, { activity: 'focused work', hours: 2.0 }])}
                    className="text-xs px-2.5 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark text-brand-purple font-semibold hover:bg-brand-purple/15 transition flex items-center space-x-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {pathA.map((act, i) => (
                    <div key={i} className="flex items-center space-x-2">
                      <select
                        value={act.activity}
                        onChange={(e) => {
                          const next = [...pathA];
                          next[i].activity = e.target.value;
                          setPathA(next);
                        }}
                        className="flex-1 px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-medium text-content-mainLight dark:text-content-mainDark"
                      >
                        {ACTIVITY_OPTIONS.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>

                      <input
                        type="number"
                        step="0.5"
                        min="0.5"
                        max="12"
                        value={act.hours}
                        onChange={(e) => {
                          const next = [...pathA];
                          next[i].hours = parseFloat(e.target.value) || 1;
                          setPathA(next);
                        }}
                        className="w-16 px-2 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-center font-mono text-content-mainLight dark:text-content-mainDark"
                      />

                      {pathA.length > 1 && (
                        <button
                          onClick={() => setPathA(pathA.filter((_, idx) => idx !== i))}
                          className="p-2 text-content-mutedLight dark:text-content-mutedDark hover:text-red-500 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* PATH B */}
              <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
                <div className="flex items-center justify-between border-b border-stroke-light dark:border-stroke-dark pb-3">
                  <span className="text-xs font-bold font-mono text-style-ambitious uppercase">
                    Path B &bull; Custom
                  </span>
                  <button
                    onClick={() => setPathB([...pathB, { activity: 'focused work', hours: 2.0 }])}
                    className="text-xs px-2.5 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark text-brand-purple font-semibold hover:bg-brand-purple/15 transition flex items-center space-x-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {pathB.map((act, i) => (
                    <div key={i} className="flex items-center space-x-2">
                      <select
                        value={act.activity}
                        onChange={(e) => {
                          const next = [...pathB];
                          next[i].activity = e.target.value;
                          setPathB(next);
                        }}
                        className="flex-1 px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-medium text-content-mainLight dark:text-content-mainDark"
                      >
                        {ACTIVITY_OPTIONS.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>

                      <input
                        type="number"
                        step="0.5"
                        min="0.5"
                        max="12"
                        value={act.hours}
                        onChange={(e) => {
                          const next = [...pathB];
                          next[i].hours = parseFloat(e.target.value) || 1;
                          setPathB(next);
                        }}
                        className="w-16 px-2 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-center font-mono text-content-mainLight dark:text-content-mainDark"
                      />

                      {pathB.length > 1 && (
                        <button
                          onClick={() => setPathB(pathB.filter((_, idx) => idx !== i))}
                          className="p-2 text-content-mutedLight dark:text-content-mutedDark hover:text-red-500 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Run Button */}
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={handleRunManualSimulation}
                disabled={isRunningManual}
                className="px-6 py-3 rounded-full bg-brand-gradient text-white text-xs font-bold shadow-md hover:scale-105 active:scale-95 transition disabled:opacity-50"
              >
                {isRunningManual ? 'Running the comparison...' : 'Compare these paths'}
              </button>
            </div>

            {/* Manual Results */}
            {manualResult && (
              <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark space-y-4 animate-pop">
                <div className="flex items-center space-x-2 text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
                  <BarChart2 className="w-4 h-4 text-brand-purple" />
                  <span>Manual Comparison Results</span>
                </div>
                <p className="text-xs text-content-mainLight dark:text-content-mainDark leading-relaxed">
                  {manualResult.gemini_explanation}
                </p>

                {/* Teach Twin Modifier Form */}
                <div className="p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-3">
                  <span className="text-xs font-bold text-content-mainLight dark:text-content-mainDark block">
                    Teach {twinName} a Custom Habit Pattern:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <select
                      value={correctionActivity}
                      onChange={(e) => setCorrectionActivity(e.target.value)}
                      className="px-3 py-2 rounded-xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs"
                    >
                      {ACTIVITY_OPTIONS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <select
                      value={correctionMetric}
                      onChange={(e) => setCorrectionMetric(e.target.value)}
                      className="px-3 py-2 rounded-xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs"
                    >
                      <option value="focus">Focus</option>
                      <option value="energy">Energy</option>
                      <option value="happiness">Happiness</option>
                    </select>
                    <input
                      type="number"
                      step="0.5"
                      value={correctionDelta}
                      onChange={(e) => setCorrectionDelta(e.target.value)}
                      className="px-3 py-2 rounded-xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs"
                    />
                  </div>
                  <input
                    type="text"
                    value={correctionDesc}
                    onChange={(e) => setCorrectionDesc(e.target.value)}
                    placeholder="Describe how this affects you..."
                    className="w-full px-3 py-2 rounded-xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs"
                  />
                  <button
                    type="button"
                    onClick={handleSaveCorrection}
                    className="px-4 py-2 rounded-full bg-brand-purple text-white text-xs font-semibold hover:opacity-95 transition"
                  >
                    Remember this pattern
                  </button>
                  {newPatternLearned && (
                    <span className="text-xs text-emerald-600 block">Got it. I'll remember that for next time.</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ============================================================ */}
      {/* DRAWER: INSPECT SIMULATION NUMBERS (On-demand drawer)         */}
      {/* ============================================================ */}
      <SlideUpDrawer
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        title={activePlan ? `${activePlan.name} Simulation Metrics` : 'Simulation Metrics'}
        subtitle="Simulated outcomes computed by deterministic model & learned modifiers"
        badge="Engine Metrics"
      >
        {activePlan && (
          <div className="space-y-6">
            <div className="p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-content-mutedLight dark:text-content-mutedDark flex items-start space-x-2">
              <Info className="w-4 h-4 text-brand-purple flex-shrink-0 mt-0.5" />
              <p>
                Simulated outcomes based on deterministic engine model and learned modifiers, not absolute predictions.
              </p>
            </div>

            {/* ML Probability */}
            {activePlan.on_time_probability !== undefined && (
              <div className="p-5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-1">
                <span className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider block">
                  ML On-Time Completion Probability
                </span>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-extrabold font-heading text-brand-purple dark:text-[#A894FF]">
                    {activePlan.on_time_probability}%
                  </span>
                  <span className="text-xs text-content-mutedLight dark:text-content-mutedDark font-medium">
                    (prototype indicator from scikit-learn task regression)
                  </span>
                </div>
              </div>
            )}

            {/* 4 State Bars */}
            {activePlan.simulated_metrics && (
              <div className="space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-content-mainLight dark:text-content-mainDark block">
                  Simulated Impact on Wellbeing & Focus:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { label: 'Energy', val: activePlan.simulated_metrics.energy, color: '#FF9F43' },
                    { label: 'Happiness', val: activePlan.simulated_metrics.happiness, color: '#FF8FA3' },
                    { label: dimensionLabels.progress, val: activePlan.simulated_metrics.study, color: '#2EC4B6' },
                    { label: 'Free Time', val: activePlan.simulated_metrics.free_time, color: '#7C5CFF' }
                  ].map((bar, bIdx) => (
                    <div
                      key={bIdx}
                      className="p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-content-mainLight dark:text-content-mainDark">{bar.label}</span>
                        <span className="font-mono" style={{ color: bar.color }}>{bar.val}/100</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-stroke-light dark:bg-stroke-dark overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${bar.val}%`, backgroundColor: bar.color }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Explanatory notes */}
            {activePlan.explanation && (
              <p className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
                {activePlan.explanation}
              </p>
            )}
          </div>
        )}
      </SlideUpDrawer>
    </div>
  );
}
