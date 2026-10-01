import React, { useState } from 'react';
import { Sun, Moon, Laptop, Eye, RotateCcw, Zap, Sparkles, Check } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function SettingsSection({ api, profile, onResetPersona, onUpdateDemoMode, onSaveTwinName, onPersonaChange }) {
  const {
    theme,
    setTheme,
    reduceMotion,
    setReduceMotion,
    twinName,
    setTwinName
  } = useTheme();

  const [inputName, setInputName] = useState(twinName);
  const [nameSaved, setNameSaved] = useState(false);
  const [demoMode, setDemoMode] = useState(profile?.demo_mode ?? true);
  const [personas, setPersonas] = useState([]);
  const [personaSaved, setPersonaSaved] = useState(false);
  const [learned, setLearned] = useState({ enabled: true, tendencies: {}, confidence: {}, source_counts: {} });
  const loadLearned = () => api?.getLearnedPreferences(profile?.user_id || 'demo-alex-rivers').then(setLearned).catch(() => {});
  React.useEffect(() => { loadLearned(); }, [api, profile?.user_id]);
  React.useEffect(() => { api?.getMemoryRegistry(profile?.persona || 'other').then((data) => setPersonas(data.personas || [])).catch(() => {}); }, [api, profile?.persona]);

  const handleSaveName = async (e) => {
    e.preventDefault();
    const requestedName = inputName.trim() || 'Echo';
    try {
      const savedName = onSaveTwinName
        ? await onSaveTwinName(requestedName)
        : requestedName;
      setTwinName(savedName);
      setInputName(savedName);
      setNameSaved(true);
      setTimeout(() => setNameSaved(false), 2500);
    } catch (error) {
      console.error('Twin name update failed:', error);
    }
  };

  const handleToggleDemoMode = () => {
    const next = !demoMode;
    setDemoMode(next);
    if (onUpdateDemoMode) onUpdateDemoMode(next);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 pb-24 space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="space-y-1.5 text-center sm:text-left">
        <h2 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
          Settings & Preferences
        </h2>
        <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">
          Customize your experience, appearance, accessibility, and twin behavior.
        </p>
      </div>

      {/* THEME SELECTOR CARD */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-3">
        <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">What best describes your days?</h3>
        <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">Changing this updates the examples shown with each memory category. Your saved permission choices stay the same.</p>
        <div className="grid sm:grid-cols-2 gap-2">{personas.map((persona) => <button key={persona.id} type="button" aria-pressed={(profile?.persona || 'other') === persona.id} onClick={async () => { await onPersonaChange?.(persona.id); setPersonaSaved(true); setTimeout(() => setPersonaSaved(false), 2500); }} className={`min-h-11 p-3 rounded-xl border text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple ${(profile?.persona || 'other') === persona.id ? 'border-brand-purple bg-brand-purple/10' : 'border-stroke-light dark:border-stroke-dark'}`}><strong>{persona.label}</strong><span className="block text-xs text-content-mutedLight dark:text-content-mutedDark">{persona.description}</span></button>)}</div>
      {personaSaved && <p role="status" className="text-xs text-brand-purple">Your setup is updated.</p>}
      </div>

      <section className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-3" aria-labelledby="learned-title">
        <h3 id="learned-title" className="text-base font-bold font-heading">What I’ve learned about you</h3>
        {!learned.enabled ? <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">Decision memory is off, so I can only adapt within this chat.</p> : Object.keys(learned.tendencies || {}).length === 0 ? <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">I’m still learning from your choices. You can change or clear anything I learn here.</p> : Object.entries(learned.tendencies).map(([key, value]) => {
          const voice = key.split(':')[1];
          const voiceLabels = { emotional: 'Heart', rational: 'Head', ambitious: 'Drive' };
          const learnedText = voice ? `${voiceLabels[voice] || voice} feels like a voice you connect with` : `You ${value >= 0 ? 'often go with my recommendation' : 'often choose your own direction'}`;
          return <div key={key} className="flex items-center justify-between gap-3 border-t border-stroke-light dark:border-stroke-dark pt-3"><p className="text-sm">{learnedText} <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">({learned.confidence?.[key] >= 0.66 ? 'high' : learned.confidence?.[key] >= 0.33 ? 'growing' : 'early'} confidence · {learned.source_counts?.[key] || 0} choices)</span></p><button className="text-xs text-brand-purple underline" onClick={async () => { await api.forgetLearnedPreference(key, profile?.user_id); loadLearned(); }}>That’s not right / forget</button></div>;
        })}
        {learned.enabled && Object.keys(learned.tendencies || {}).length > 0 && <button className="min-h-11 px-3 rounded-xl border border-stroke-light dark:border-stroke-dark text-sm" onClick={async () => { await api.resetLearnedPreferences(profile?.user_id); loadLearned(); }}>Reset what I’ve learned</button>}
      </section>

      {/* THEME SELECTOR CARD */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
        <div>
          <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
            Color Theme
          </h3>
          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
            Choose between full light mode, velvet dark mode, or follow your OS setting.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {[
            { id: 'light', label: 'Light', icon: Sun, desc: 'Soft Lavender' },
            { id: 'dark', label: 'Dark', icon: Moon, desc: 'Velvet Midnight' },
            { id: 'system', label: 'System', icon: Laptop, desc: 'Automatic' }
          ].map(opt => {
            const isSelected = theme === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setTheme(opt.id)}
                className={`p-4 rounded-2xl border text-center transition flex flex-col items-center space-y-2 ${
                  isSelected
                    ? 'border-brand-purple bg-brand-purple/10 shadow-sm'
                    : 'border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark hover:border-brand-purple/40'
                }`}
              >
                <opt.icon className={`w-5 h-5 ${isSelected ? 'text-brand-purple' : 'text-content-mutedLight dark:text-content-mutedDark'}`} />
                <div>
                  <span className="text-xs font-bold text-content-mainLight dark:text-content-mainDark block">
                    {opt.label}
                  </span>
                  <span className="text-[10px] text-content-mutedLight dark:text-content-mutedDark">
                    {opt.desc}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ACCESSIBILITY & MOTION */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
        <div className="flex items-center justify-between">
          <div className="pr-4">
            <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              Reduce Motion
            </h3>
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-snug">
              Disable animations, confetti bursts, and pulsing orb effects for sensory comfort.
            </p>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={reduceMotion}
            onClick={() => setReduceMotion(!reduceMotion)}
            className={`w-12 h-7 rounded-full p-1 transition-colors duration-200 focus:outline-none flex-shrink-0 ${
              reduceMotion ? 'bg-brand-purple' : 'bg-stroke-light dark:bg-stroke-dark'
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${
                reduceMotion ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* TWIN IDENTITY RENAME */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
        <div>
          <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
            Twin Nickname
          </h3>
          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
            Choose what your twin is called throughout the app.
          </p>
        </div>

        <form onSubmit={handleSaveName} className="flex items-center space-x-2">
          <input
            type="text"
            value={inputName}
            onChange={(e) => setInputName(e.target.value)}
            placeholder="Echo"
            className="flex-1 px-4 py-2.5 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-sm text-content-mainLight dark:text-content-mainDark font-medium focus:outline-none focus:ring-2 focus:ring-brand-purple"
          />
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl bg-brand-purple text-white text-xs font-bold hover:bg-brand-purple/90 transition flex items-center space-x-1"
          >
            {nameSaved ? <Check className="w-4 h-4" /> : <span>Save</span>}
          </button>
        </form>
      </div>

      {/* DEMO MODE MULTIPLIER */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
        <div className="flex items-center justify-between">
          <div className="pr-4">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-brand-purple" />
              <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                Hackathon Demo Mode (+0.12 step)
              </h3>
            </div>
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-snug">
              Increases the weight step size from 0.05 to 0.12 so the twin evolves within 3 decisions for live presentations.
            </p>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={demoMode}
            onClick={handleToggleDemoMode}
            className={`w-12 h-7 rounded-full p-1 transition-colors duration-200 focus:outline-none flex-shrink-0 ${
              demoMode ? 'bg-brand-purple' : 'bg-stroke-light dark:bg-stroke-dark'
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${
                demoMode ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* PERSONA RESET */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4">
        <div>
          <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
            Reset Demo Persona
          </h3>
          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
            Restore Alex Rivers to the initial baseline weights (50 Rational, 25 Emotional, 25 Ambitious).
          </p>
        </div>

        <button
          onClick={onResetPersona}
          className="px-5 py-2.5 rounded-full border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark hover:text-rose-500 hover:border-rose-500/40 transition flex items-center space-x-1.5"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Persona Baseline</span>
        </button>
      </div>
    </div>
  );
}
