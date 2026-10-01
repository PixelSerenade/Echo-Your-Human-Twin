import React, { useState, useEffect } from 'react';
import {
  Brain, Heart, Rocket, Sparkles, Check, ChevronRight,
  Shield, Calendar, AlertTriangle, BookOpen, Sliders, Volume2,
  CheckCircle2, ArrowRight
} from 'lucide-react';
import EchoOrb from './EchoOrb';
import Confetti from './Confetti';
import { useTheme } from '../context/ThemeContext';
import { api } from '../api';
import { resolveTwinName } from '../utils/identity';

const RATIONAL_TAGS = [
  'Plans ahead', 'Deadline-driven', 'Loves lists', 'Thinks before acting',
  'Likes facts', 'Hates last-minute chaos', 'Organized', 'Careful with risks'
];

const EMOTIONAL_TAGS = [
  'Mood-driven', 'Needs balance', 'Values peace of mind', 'Gets stressed easily',
  'Cares about people', 'Listens to my gut', 'Burns out fast', 'Needs breaks'
];

const AMBITIOUS_TAGS = [
  'Dreams big', 'Goal-obsessed', 'Career-focused', 'Takes chances',
  'Always learning', 'Competitive', 'Builds side projects', 'Says yes to opportunities'
];

const STYLE_DETAILS = {
  rational: {
    label: 'Rational',
    tagline: 'Calm, clear, and practical when things get busy.',
    example: "Two priorities need attention. Let's make a manageable plan and start with the most important one.",
    color: '#2EC4B6',
    borderClass: 'border-style-rational/50 bg-style-rational/5',
    activeClass: 'ring-2 ring-style-rational bg-style-rational/10 border-style-rational',
    icon: Brain
  },
  emotional: {
    label: 'Emotional',
    tagline: 'Warm and gentle, with room for your energy and wellbeing.',
    example: "You're carrying a lot right now. Let's choose a manageable place to start and leave room to breathe.",
    color: '#FF8FA3',
    borderClass: 'border-style-emotional/50 bg-style-emotional/5',
    activeClass: 'ring-2 ring-style-emotional bg-style-emotional/10 border-style-emotional',
    icon: Heart
  },
  ambitious: {
    label: 'Ambitious',
    tagline: 'Upbeat and encouraging, with an eye on meaningful growth.',
    example: "This project could become something you're proud to show. Let's lock in a strong milestone without burning through all your energy.",
    color: '#8B5CF6',
    borderClass: 'border-style-ambitiousFrom/50 bg-style-ambitiousFrom/5',
    activeClass: 'ring-2 ring-style-ambitiousFrom bg-style-ambitiousFrom/10 border-style-ambitiousFrom',
    icon: Rocket
  }
};

export default function OnboardingWizard({ initialStep = 'tags', currentUser, onComplete }) {
  const { reduceMotion, setTwinName: setGlobalTwinName, setTwinStyle: setGlobalTwinStyle } = useTheme();

  // Step state: 'tags' -> 'reveal' -> 'name' -> 'permissions' -> 'finish'
  const [step, setStep] = useState(initialStep);
  const [selectedPersona, setSelectedPersona] = useState(currentUser?.persona || 'other');
  const [memoryRegistry, setMemoryRegistry] = useState({ personas: [], categories: [], defaults: {} });
  const [goalDraft, setGoalDraft] = useState('');
  const [goalDraftTwo, setGoalDraftTwo] = useState('');
  const [seedDeadlines, setSeedDeadlines] = useState([{ title: '', due_date: '', estimated_effort: 1 }, { title: '', due_date: '', estimated_effort: 1 }, { title: '', due_date: '', estimated_effort: 1 }]);
  const [scheduleAttachment, setScheduleAttachment] = useState(null);
  const [scheduleExtractedItems, setScheduleExtractedItems] = useState([]);
  const [scheduleStatus, setScheduleStatus] = useState('');
  const [scheduleBusy, setScheduleBusy] = useState(false);
  useEffect(() => { api.getMemoryRegistry(selectedPersona).then(setMemoryRegistry).catch(() => {}); }, [selectedPersona]);
  const [selectedTags, setSelectedTags] = useState([]); // array of { twin_type, tag_name }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Recommendations & Selections
  const [recommendedStyle, setRecommendedStyle] = useState('rational');
  const [chosenStyle, setChosenStyle] = useState('rational');
  const [twinNameInput, setTwinNameInput] = useState(() => resolveTwinName(
    currentUser?.twin_name,
    currentUser?.name,
    currentUser?.twin_name_customized
  ));

  // Tie-breaker state
  const [showTieBreaker, setShowTieBreaker] = useState(false);
  const [tiedTwins, setTiedTwins] = useState([]);

  // Permissions state (mood_tone strictly False by default)
  const [permissions, setPermissions] = useState({});
  useEffect(() => { if (memoryRegistry.defaults) setPermissions({ ...memoryRegistry.defaults, mood_tone: false }); }, [memoryRegistry]);

  // Calculate dominant tag style live
  const rationalCount = selectedTags.filter((t) => t.twin_type === 'rational').length;
  const emotionalCount = selectedTags.filter((t) => t.twin_type === 'emotional').length;
  const ambitiousCount = selectedTags.filter((t) => t.twin_type === 'ambitious').length;

  let liveLeadingStyle = 'default';
  if (selectedTags.length > 0) {
    if (rationalCount >= emotionalCount && rationalCount >= ambitiousCount) liveLeadingStyle = 'rational';
    else if (emotionalCount >= rationalCount && emotionalCount >= ambitiousCount) liveLeadingStyle = 'emotional';
    else liveLeadingStyle = 'ambitious';
  }

  const toggleTag = (twinType, tagName) => {
    setSelectedTags((prev) => {
      const exists = prev.some((t) => t.tag_name === tagName);
      if (exists) {
        return prev.filter((t) => t.tag_name !== tagName);
      } else {
        return [...prev, { twin_type: twinType, tag_name: tagName }];
      }
    });
  };

  const isTagSelected = (tagName) => selectedTags.some((t) => t.tag_name === tagName);

  // STEP 1: Submit Tags
  const handleTagsSubmit = async (tieBreakerChoice = null) => {
    if (selectedTags.length < 5) {
      setError('Pick at least five tags so Echo has enough to start with.');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await api.saveOnboardingStep({
        user_id: currentUser?.user_id,
        step: 'tags',
        tags: selectedTags,
        tie_breaker_choice: tieBreakerChoice
      });

      if (res.tie_needed) {
        setTiedTwins(res.tied_twins || ['rational', 'emotional']);
        setShowTieBreaker(true);
        setLoading(false);
        return;
      }

      setShowTieBreaker(false);
      const rec = res.recommended_twin || 'rational';
      setRecommendedStyle(rec);
      setChosenStyle(rec);
      if (typeof setGlobalTwinStyle === 'function') setGlobalTwinStyle(rec);
      setStep('reveal');
    } catch (err) {
      console.error('Tag setup failed:', err);
      setError("Hmm, I couldn't save those yet. Try again?");
    } finally {
      setLoading(false);
    }
  };

  // STEP 2: Confirm Style
  const handleRevealSubmit = async () => {
    setError(null);
    setLoading(true);

    try {
      await api.saveOnboardingStep({
        user_id: currentUser?.user_id,
        step: 'reveal',
        primary_twin: chosenStyle
      });
      if (typeof setGlobalTwinStyle === 'function') setGlobalTwinStyle(chosenStyle);
      setStep('name');
    } catch (err) {
      console.error('Style setup failed:', err);
      setError("Hmm, that choice didn't stick. Try again?");
    } finally {
      setLoading(false);
    }
  };

  // STEP 3: Confirm Name
  const handleNameSubmit = async (skipped = false) => {
    setError(null);
    setLoading(true);
    const finalName = skipped ? 'Echo' : (twinNameInput.trim().slice(0, 24) || 'Echo');

    try {
      await api.saveOnboardingStep({
        user_id: currentUser?.user_id,
        step: 'name',
        twin_name: finalName
      });
      if (typeof setGlobalTwinName === 'function') setGlobalTwinName(finalName);
      setStep('permissions');
    } catch (err) {
      console.error('Name setup failed:', err);
      setError("Hmm, I couldn't save that name. Try again?");
    } finally {
      setLoading(false);
    }
  };

  // STEP 4: Confirm Permissions
  const handlePermissionsSubmit = async () => {
    setError(null);
    setLoading(true);

    try {
      await api.saveOnboardingStep({
        user_id: currentUser?.user_id,
        step: 'permissions',
        permissions
      });
      setStep('seed');
    } catch (err) {
      console.error('Permission setup failed:', err);
      setError("Hmm, I couldn't save those privacy choices. Try again?");
    } finally {
      setLoading(false);
    }
  };

  const handlePersonaSubmit = async () => {
    setLoading(true); setError(null);
    try { await api.saveOnboardingStep({ user_id: currentUser?.user_id, step: 'persona', persona: selectedPersona }); setStep('tags'); }
    catch { setError('Hmm, that choice did not save. Try again?'); }
    finally { setLoading(false); }
  };

  const handleSeedSubmit = async (skip = false) => {
    setLoading(true); setError(null);
    try { await api.saveOnboardingStep({ user_id: currentUser?.user_id, step: 'seed', goals: skip ? [] : [goalDraft, goalDraftTwo].map((item) => item.trim()).filter(Boolean), seed_deadlines: skip ? [] : seedDeadlines.filter((item) => item.title.trim() && item.due_date) }); setStep('finish'); }
    catch { setError('That did not save yet. You can skip this step or try again.'); }
    finally { setLoading(false); }
  };

  const handleScheduleUpload = async (file) => {
    if (!file) return;
    if (!permissions.schedule_commitments) { setScheduleStatus('Turn on Schedule & Commitments in the permissions step before uploading a schedule.'); return; }
    setScheduleBusy(true); setScheduleStatus('Uploading and reviewing your schedule…'); setError(null);
    try {
      const uploaded = await api.uploadAttachment(currentUser?.user_id, file);
      setScheduleAttachment(uploaded);
      const result = await api.askTwin({ user_id: currentUser?.user_id, question: 'Please extract recurring schedule commitments from this file for me to review.', attachment_id: uploaded.id });
      if (result.attachment_looks_like_schedule && result.extracted_items?.length) {
        setScheduleExtractedItems(result.extracted_items);
        setScheduleStatus('Review the proposed schedule items before saving.');
      } else setScheduleStatus('I could not find schedule items to review in that file. You can try another file or skip this.');
    } catch (err) { setScheduleStatus(err.message || 'The schedule could not be processed. You can skip this step.'); }
    finally { setScheduleBusy(false); }
  };

  const handleConfirmSchedule = async () => {
    if (!scheduleAttachment || !scheduleExtractedItems.length) return;
    setScheduleBusy(true);
    try {
      await api.confirmExtractedItems(currentUser?.user_id, scheduleAttachment.id, scheduleExtractedItems);
      setScheduleStatus('Your reviewed schedule items are saved.'); setScheduleExtractedItems([]);
    } catch (err) { setScheduleStatus(err.message || 'Those schedule items could not be saved.'); }
    finally { setScheduleBusy(false); }
  };

  // STEP 5: Finalize
  const handleFinish = async () => {
    setError(null);
    setLoading(true);

    try {
      await api.saveOnboardingStep({
        user_id: currentUser?.user_id,
        step: 'finish'
      });
      onComplete({
        name: currentUser?.name || 'Friend',
        twin_name: twinNameInput.trim() || 'Echo',
        primary_twin: chosenStyle
      });
    } catch (err) {
      console.error('Onboarding completion failed:', err);
      setError("Almost there. Something got interrupted, so try once more?");
    } finally {
      setLoading(false);
    }
  };

  // Step indicator steps list
  const stepsList = ['persona', 'tags', 'reveal', 'name', 'permissions', 'seed', 'finish'];
  const currentStepIdx = stepsList.indexOf(step);

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12 animate-fadeIn space-y-8">
      {/* Confetti on finish */}
      {step === 'finish' && !reduceMotion && <Confetti count={40} />}

      {/* Progress Dots Header */}
      <div className="flex flex-col items-center space-y-3">
        <div className="flex items-center space-x-2">
          {stepsList.map((s, idx) => (
            <div
              key={s}
              className={`h-2 rounded-full transition-all duration-300 ${
                idx === currentStepIdx
                  ? 'w-8 bg-brand-purple'
                  : idx < currentStepIdx
                  ? 'w-2 bg-emerald-500'
                  : 'w-2 bg-stroke-light dark:bg-stroke-dark'
              }`}
            />
          ))}
        </div>
        <span className="text-xs font-bold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
          Step {currentStepIdx + 1} of {stepsList.length} &bull; {step.toUpperCase()}
        </span>
      </div>

      {/* Inline Error */}
      {error && (
        <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/25 text-xs text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* =================================================================== */}
      {step === 'persona' && <div className="space-y-6 text-center">
        <h2 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">What best describes your days?</h2>
        <div className="grid sm:grid-cols-2 gap-3">{memoryRegistry.personas.map((persona) => <button key={persona.id} type="button" aria-pressed={selectedPersona === persona.id} onClick={() => setSelectedPersona(persona.id)} className={`p-4 rounded-2xl border text-left ${selectedPersona === persona.id ? 'border-brand-purple bg-brand-purple/10 ring-2 ring-brand-purple/40' : 'border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark'}`}><strong>{persona.label}</strong><span className="block mt-1 text-xs text-content-mutedLight dark:text-content-mutedDark">{persona.description}</span></button>)}</div>
        <button type="button" disabled={loading} onClick={handlePersonaSubmit} className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold">Continue <ChevronRight className="inline w-4 h-4" /></button>
      </div>}

      {/* STEP 1: PICK YOUR TAGS */}
      {/* STEP 1: PICK YOUR TAGS */}
      {/* =================================================================== */}
      {step === 'tags' && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="flex justify-center mb-2">
              <EchoOrb size="chat" style={liveLeadingStyle} state="idle" title="Echo" />
            </div>
            <h2 className="text-xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              What sounds most like you?
            </h2>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-md mx-auto">
              Pick the habits and instincts that feel familiar. Echo will use them to find a starting voice that fits.
            </p>

            {/* Live Counter, Fast-Fill, & Mood Indicator */}
            <div className="pt-2 flex flex-wrap items-center justify-center gap-2">
              <span className={`px-3.5 py-1 rounded-full text-xs font-bold border transition ${
                selectedTags.length >= 5
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
                  : 'bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mutedLight dark:text-content-mutedDark border-stroke-light dark:border-stroke-dark'
              }`}>
                {selectedTags.length} / 5 selected {selectedTags.length >= 5 ? '✨ (Ready)' : ''}
              </span>

              {selectedTags.length < 5 && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTags([
                      { twin_type: 'rational', tag_name: 'Plans ahead' },
                      { twin_type: 'rational', tag_name: 'Deadline-driven' },
                      { twin_type: 'rational', tag_name: 'Loves lists' },
                      { twin_type: 'emotional', tag_name: 'Needs balance' },
                      { twin_type: 'emotional', tag_name: 'Values peace of mind' },
                      { twin_type: 'ambitious', tag_name: 'Dreams big' }
                    ]);
                  }}
                  className="px-3 py-1 rounded-full text-xs font-semibold bg-brand-purple/15 text-brand-purple dark:text-[#A894FF] border border-brand-purple/30 hover:bg-brand-purple/25 transition flex items-center space-x-1"
                >
                  <span>Pick a balanced mix</span>
                </button>
              )}

              {selectedTags.length > 0 && (
                <span className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                  Echo's starting to sound <strong className="capitalize text-content-mainLight dark:text-content-mainDark">{liveLeadingStyle}</strong>
                </span>
              )}
            </div>
          </div>

          {/* Group 1: Rational */}
          <div className="p-5 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3">
            <div className="flex items-center space-x-2 text-style-rational font-bold text-xs uppercase tracking-wider">
              <Brain className="w-4 h-4" />
              <span>Rational &bull; Structure & Deadlines</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {RATIONAL_TAGS.map((tag) => {
                const active = isTagSelected(tag);
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag('rational', tag)}
                    className={`min-h-[44px] px-4 py-2 rounded-full text-xs font-semibold border transition active:scale-95 flex items-center space-x-1.5 ${
                      active
                        ? 'bg-style-rational text-surface-dark border-style-rational shadow-sm'
                        : 'bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mainLight dark:text-content-mainDark border-stroke-light dark:border-stroke-dark hover:border-style-rational/50'
                    }`}
                  >
                    {active && <Check className="w-3.5 h-3.5" />}
                    <span>{tag}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Group 2: Emotional */}
          <div className="p-5 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3">
            <div className="flex items-center space-x-2 text-style-emotional font-bold text-xs uppercase tracking-wider">
              <Heart className="w-4 h-4" />
              <span>Emotional &bull; Wellbeing & Balance</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {EMOTIONAL_TAGS.map((tag) => {
                const active = isTagSelected(tag);
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag('emotional', tag)}
                    className={`min-h-[44px] px-4 py-2 rounded-full text-xs font-semibold border transition active:scale-95 flex items-center space-x-1.5 ${
                      active
                        ? 'bg-style-emotional text-surface-dark border-style-emotional shadow-sm'
                        : 'bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mainLight dark:text-content-mainDark border-stroke-light dark:border-stroke-dark hover:border-style-emotional/50'
                    }`}
                  >
                    {active && <Check className="w-3.5 h-3.5" />}
                    <span>{tag}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Group 3: Ambitious */}
          <div className="p-5 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3">
            <div className="flex items-center space-x-2 text-style-ambitiousFrom font-bold text-xs uppercase tracking-wider">
              <Rocket className="w-4 h-4" />
              <span>Ambitious &bull; Big Goals & Momentum</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {AMBITIOUS_TAGS.map((tag) => {
                const active = isTagSelected(tag);
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag('ambitious', tag)}
                    className={`min-h-[44px] px-4 py-2 rounded-full text-xs font-semibold border transition active:scale-95 flex items-center space-x-1.5 ${
                      active
                        ? 'bg-style-ambitiousFrom text-white border-style-ambitiousFrom shadow-sm'
                        : 'bg-surface-subtleLight dark:bg-surface-subtleDark text-content-mainLight dark:text-content-mainDark border-stroke-light dark:border-stroke-dark hover:border-style-ambitiousFrom/50'
                    }`}
                  >
                    {active && <Check className="w-3.5 h-3.5" />}
                    <span>{tag}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-2">
            <button
              type="button"
              disabled={selectedTags.length < 5 || loading}
              onClick={() => handleTagsSubmit()}
              className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold text-sm shadow-md shadow-brand-purple/20 hover:shadow-brand-purple/35 hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 transition flex items-center justify-center space-x-2"
            >
              <span>{loading ? 'Getting Echo ready...' : 'Continue to Meet Your Echo'}</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Tie-Breaker Modal */}
          {showTieBreaker && (
            <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="max-w-md w-full p-6 sm:p-7 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-xl space-y-5 animate-scaleUp">
                <div className="space-y-1 text-center">
                  <div className="w-10 h-10 mx-auto rounded-full bg-brand-purple/15 text-brand-purple flex items-center justify-center mb-2">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <h3 className="text-lg font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                    One quick choice
                  </h3>
                  <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                    A few styles fit you equally well. When things suddenly get busy, what do you reach for first?
                  </p>
                </div>

                <div className="space-y-2.5">
                  <button
                    onClick={() => handleTagsSubmit('rational')}
                    className="w-full p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark hover:border-style-rational text-left text-xs font-semibold text-content-mainLight dark:text-content-mainDark transition"
                  >
                    📅 Break it down into an hourly schedule and follow the checklist.
                  </button>
                  <button
                    onClick={() => handleTagsSubmit('emotional')}
                    className="w-full p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark hover:border-style-emotional text-left text-xs font-semibold text-content-mainLight dark:text-content-mainDark transition"
                  >
                    🧘 Take a deep breath, protect my sleep, and avoid burning out.
                  </button>
                  <button
                    onClick={() => handleTagsSubmit('ambitious')}
                    className="w-full p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark hover:border-style-ambitiousFrom text-left text-xs font-semibold text-content-mainLight dark:text-content-mainDark transition"
                  >
                    🚀 Power through a late-night sprint to finish ahead and excel.
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* STEP 2: MEET YOUR ECHO (ANIMATED REVEAL & STYLE CARDS) */}
      {/* =================================================================== */}
      {step === 'reveal' && (
        <div className="space-y-6">
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <EchoOrb size="hero" style={chosenStyle} state="idle" title="Echo" />
            </div>

            <div className="space-y-2">
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-brand-purple/15 text-brand-purple dark:text-[#A894FF] inline-flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Meet Echo</span>
              </span>

              <h2 className="text-xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
                Echo will start with a <span className="capitalize" style={{ color: STYLE_DETAILS[chosenStyle].color }}>{chosenStyle}</span> voice
              </h2>

              <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-md mx-auto">
                Your choices point toward a <strong>{recommendedStyle}</strong> approach. Keep it, try another voice, or let Echo adapt as you make decisions.
              </p>
            </div>
          </div>

          {/* 3 Selectable Style Cards */}
          <div className="space-y-3">
            {['rational', 'emotional', 'ambitious'].map((stKey) => {
              const info = STYLE_DETAILS[stKey];
              const isSelected = chosenStyle === stKey;
              const isRec = recommendedStyle === stKey;
              const IconComp = info.icon;

              return (
                <div
                  key={stKey}
                  onClick={() => setChosenStyle(stKey)}
                  className={`cursor-pointer p-5 rounded-3xl border transition-all duration-200 ${
                    isSelected ? info.activeClass : 'bg-surface-light dark:bg-surface-dark border-stroke-light dark:border-stroke-dark hover:border-brand-purple/40'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div
                        className="w-10 h-10 rounded-2xl flex items-center justify-center"
                        style={{ backgroundColor: `${info.color}20`, color: info.color }}
                      >
                        <IconComp className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h4 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                            {info.label}
                          </h4>
                          {isRec && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                              Feels closest to you
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                          {info.tagline}
                        </p>
                      </div>
                    </div>

                    <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                      isSelected
                        ? 'border-brand-purple bg-brand-purple text-white'
                        : 'border-stroke-light dark:border-stroke-dark'
                    }`}>
                      {isSelected && <Check className="w-3.5 h-3.5" />}
                    </div>
                  </div>

                  {/* Concrete example of how Echo replies */}
                  <div className="mt-3.5 pt-3 border-t border-stroke-light/60 dark:border-stroke-dark/60 text-xs text-content-mutedLight dark:text-content-mutedDark">
                    <span className="font-semibold text-content-mainLight dark:text-content-mainDark">How Echo might sound: </span>
                    <span className="italic">"{info.example}"</span>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-center text-content-mutedLight dark:text-content-mutedDark">
            Nothing's locked in. Echo can adapt with you, and you can change the voice anytime.
          </p>

          <button
            type="button"
            disabled={loading}
            onClick={handleRevealSubmit}
            className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold text-sm shadow-md shadow-brand-purple/20 hover:shadow-brand-purple/35 hover:scale-[1.01] active:scale-[0.99] transition flex items-center justify-center space-x-2"
          >
            <span>This voice feels right</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* =================================================================== */}
      {/* STEP 3: NAME YOUR ECHO */}
      {/* =================================================================== */}
      {step === 'name' && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="flex justify-center mb-2">
              <EchoOrb size="chat" style={chosenStyle} state="idle" title={twinNameInput || 'Echo'} />
            </div>
            <h2 className="text-xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              What would you like to call Echo?
            </h2>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-md mx-auto">
              Choose a name that feels natural, or keep Echo.
            </p>
          </div>

          <div className="p-7 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-5">
            <div className="space-y-2">
              <label className="block text-xs font-bold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
                Twin Name (1–24 characters)
              </label>
              <input
                type="text"
                maxLength={24}
                value={twinNameInput}
                onChange={(e) => setTwinNameInput(e.target.value)}
                placeholder="Echo"
                className="w-full px-4 py-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-base font-bold text-content-mainLight dark:text-content-mainDark placeholder-content-mutedLight/50 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 transition"
              />
              <div className="text-right text-[11px] text-content-mutedLight dark:text-content-mutedDark">
                {twinNameInput.trim().length} / 24
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => handleNameSubmit(false)}
                className="w-full sm:flex-1 py-3.5 rounded-full bg-brand-gradient text-white font-bold text-sm shadow-md shadow-brand-purple/20 hover:scale-[1.01] active:scale-[0.99] transition flex items-center justify-center space-x-2"
              >
                <span>Save Name</span>
                <ChevronRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                disabled={loading}
                onClick={() => handleNameSubmit(true)}
                className="w-full sm:w-auto px-6 py-3.5 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark font-semibold text-xs transition"
              >
                Skip, keep Echo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* STEP 4: PERMISSIONS GATEWAY */}
      {/* =================================================================== */}
      {step === 'permissions' && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="flex justify-center mb-2">
              <div className="w-12 h-12 rounded-2xl bg-brand-purple/15 text-brand-purple flex items-center justify-center">
                <Shield className="w-6 h-6" />
              </div>
            </div>
            <h2 className="text-xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              What can Echo remember? You're in control here.
            </h2>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-md mx-auto">
              Mood & Tone stays off unless you choose to turn it on. Echo only uses what you choose to share.
            </p>
          </div>

          <div className="space-y-3">
            {memoryRegistry.categories.map((perm) => {
              const isEnabled = permissions[perm.id] ?? perm.default_enabled;

              return (
                <div
                  key={perm.id}
                  className="p-4 sm:p-5 rounded-2xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark flex items-center justify-between space-x-4"
                >
                  <div className="flex items-center space-x-3.5">
                    <div className="w-9 h-9 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark flex items-center justify-center text-content-mutedLight dark:text-content-mutedDark">
                      <Shield className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-content-mainLight dark:text-content-mainDark">
                        {perm.title}
                      </h4>
                      <p className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-snug">
                        {perm.description}
                      </p>
                      <p className="mt-1 text-[11px] text-content-mutedLight dark:text-content-mutedDark">{perm.hint}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setPermissions((p) => ({ ...p, [perm.id]: !p[perm.id] }))}
                    role="switch"
                    aria-checked={isEnabled}
                    className={`min-h-11 min-w-[76px] px-2 rounded-full transition-colors relative flex-shrink-0 inline-flex items-center justify-center ${
                      isEnabled ? 'bg-brand-purple' : 'bg-stroke-light dark:bg-stroke-dark'
                    }`}
                    aria-label={`Toggle ${perm.title}`}
                  >
                    <span className="text-xs font-bold text-white">{isEnabled ? 'On' : 'Off'}</span>
                  </button>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-center text-content-mutedLight dark:text-content-mutedDark">
            Shared data is processed by Google Gemini to generate replies. <a className="underline text-brand-purple dark:text-[#A894FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple rounded" href="/privacy-notice.html">Read the privacy notice</a>.
          </p>

          <div className="p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs text-content-mutedLight dark:text-content-mutedDark text-center">
            You can change any of this later in <strong>Privacy</strong>.
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={handlePermissionsSubmit}
            className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold text-sm shadow-md shadow-brand-purple/20 hover:scale-[1.01] active:scale-[0.99] transition flex items-center justify-center space-x-2"
          >
            <span>Save my choices</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* =================================================================== */}
      {/* STEP 5: FINISH CELEBRATION */}
      {/* =================================================================== */}
      {step === 'seed' && <div className="space-y-5">
        <div className="text-center"><h2 className="text-2xl font-extrabold font-heading">Seed your twin</h2><p className="text-sm text-content-mutedLight dark:text-content-mutedDark">A little context helps {twinNameInput || 'Echo'} get started. You can skip this and add information later.</p></div>
        <div className="p-4 rounded-2xl border border-stroke-light dark:border-stroke-dark space-y-3"><label className="block text-sm font-semibold">Upload a schedule (optional)<input type="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,application/pdf,text/plain" disabled={scheduleBusy || !permissions.schedule_commitments} onChange={(event) => handleScheduleUpload(event.target.files?.[0])} className="mt-2 block w-full text-xs" /></label>{!permissions.schedule_commitments && <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">Enable Schedule & Commitments in your permissions to use this option.</p>}{scheduleStatus && <p role="status" className="text-xs text-content-mutedLight dark:text-content-mutedDark">{scheduleStatus}</p>}{scheduleExtractedItems.length > 0 && <div className="space-y-2"><p className="text-xs font-bold">Proposed items — check these before saving</p>{scheduleExtractedItems.map((item, index) => <p key={`${item.title}-${index}`} className="text-xs rounded-lg bg-surface-subtleLight dark:bg-surface-subtleDark p-2">{item.day} {item.start_time}–{item.end_time}: {item.title}</p>)}<button type="button" disabled={scheduleBusy} onClick={handleConfirmSchedule} className="px-4 py-2 rounded-full bg-brand-gradient text-white text-xs font-bold">Save reviewed items</button></div>}</div>
        <div className="space-y-2"><span className="text-sm font-semibold">Upcoming deadlines or key dates (optional)</span>{seedDeadlines.map((item, index) => <div key={index} className="grid sm:grid-cols-[1fr_170px] gap-2"><input aria-label={`Key date ${index + 1} title`} value={item.title} onChange={(e) => setSeedDeadlines((items) => items.map((row, rowIndex) => rowIndex === index ? { ...row, title: e.target.value } : row))} maxLength={200} placeholder="What is coming up?" className="min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark px-3" /><input aria-label={`Key date ${index + 1} date`} type="date" value={item.due_date} onChange={(e) => setSeedDeadlines((items) => items.map((row, rowIndex) => rowIndex === index ? { ...row, due_date: e.target.value } : row))} className="min-h-11 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark px-3" /></div>)}</div>
        <div className="grid sm:grid-cols-2 gap-2"><label className="block text-sm font-semibold">A goal you are working toward (optional)<input value={goalDraft} onChange={(e) => setGoalDraft(e.target.value)} maxLength={200} className="mt-2 w-full rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark p-3" placeholder="A goal that matters to you" /></label><label className="block text-sm font-semibold">Another goal (optional)<input value={goalDraftTwo} onChange={(e) => setGoalDraftTwo(e.target.value)} maxLength={200} className="mt-2 w-full rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark p-3" placeholder="Another thing you are working toward" /></label></div>
        <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">You can paste a schedule into chat later; uploaded schedules are reviewed before anything is saved.</p>
        <div className="flex gap-3"><button type="button" disabled={loading} onClick={() => handleSeedSubmit(true)} className="flex-1 py-3 rounded-full border border-stroke-light dark:border-stroke-dark">Skip for now</button><button type="button" disabled={loading} onClick={() => handleSeedSubmit(false)} className="flex-1 py-3 rounded-full bg-brand-gradient text-white font-bold">Save and continue</button></div>
      </div>}

      {step === 'finish' && (
        <div className="space-y-6 text-center animate-scaleUp">
          <div className="flex justify-center mb-2">
            <EchoOrb size="hero" style={chosenStyle} state="idle" title={twinNameInput || 'Echo'} />
          </div>

          <div className="space-y-2">
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-xs font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>You're all set!</span>
            </div>

            <h2 className="text-3xl sm:text-4xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              {twinNameInput || 'Echo'} is ready when you are.
            </h2>

            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-md mx-auto">
              Start with whatever's on your mind. You can ask a question, think through a choice, or shape a plan for the week.
            </p>
          </div>

          <div className="pt-4 max-w-sm mx-auto">
            <button
              type="button"
              disabled={loading}
              onClick={handleFinish}
              className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold text-base shadow-lg shadow-brand-purple/25 hover:shadow-brand-purple/40 hover:scale-[1.02] active:scale-[0.98] transition flex items-center justify-center space-x-2"
            >
              <span>Start talking with {twinNameInput || 'Echo'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
