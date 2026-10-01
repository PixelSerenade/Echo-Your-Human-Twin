import React, { useState } from 'react';
import EchoOrb from './EchoOrb';
import Confetti from './Confetti';
import { Brain, Heart, Rocket, Sparkles, Check, ArrowRight, ArrowLeft } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const ONBOARDING_STEPS = [
  {
    twin: 'rational',
    title: 'How do you handle deadlines & tasks?',
    subtitle: 'Pick the habits that sound most like you.',
    icon: Brain,
    color: '#2EC4B6',
    tags: [
      { name: 'plans ahead', desc: 'Schedules blocks before crunch time' },
      { name: 'deadline-driven', desc: 'Thrives when the clock is ticking' },
      { name: 'risk-averse', desc: 'Avoids last-minute chaos' },
      { name: 'optimizes schedule', desc: 'Maps out tasks strategically' }
    ]
  },
  {
    twin: 'emotional',
    title: 'What protects your energy & peace of mind?',
    subtitle: 'Your twin needs to know what keeps you whole.',
    icon: Heart,
    color: '#FF8FA3',
    tags: [
      { name: 'avoids burnout', desc: 'Prioritizes sleep and recovery' },
      { name: 'values peace of mind', desc: 'Needs low anxiety to do good work' },
      { name: 'mood-driven', desc: 'Rides natural inspiration waves' },
      { name: 'protects rest', desc: 'Hard boundaries around free time' }
    ]
  },
  {
    twin: 'ambitious',
    title: 'What fuels your drive & future goals?',
    subtitle: 'Where do you want to see yourself grow?',
    icon: Rocket,
    color: '#8B5CF6',
    tags: [
      { name: 'career-focused', desc: 'Eye on the long-term destination' },
      { name: 'takes opportunities', desc: 'Leaps into high-upside challenges' },
      { name: 'goal-driven', desc: 'Tracks milestones relentlessly' },
      { name: 'skill-builder', desc: 'Prioritizes mastering hard things' }
    ]
  }
];

export default function OnboardingModal({
  isOpen,
  onClose,
  currentTags = [],
  onSaveProfile,
  onSaveTwinName
}) {
  const { twinName, setTwinName } = useTheme();
  const [currentStep, setCurrentStep] = useState(0); // 0, 1, 2 = Questions; 3 = Reveal
  const [selectedTagNames, setSelectedTagNames] = useState(() => {
    return new Set(currentTags.map(t => t.tag_name));
  });
  const [customTwinName, setCustomTwinName] = useState(twinName || 'Echo');
  const [showConfetti, setShowConfetti] = useState(false);

  if (!isOpen) return null;

  const toggleTag = (tagName) => {
    setSelectedTagNames(prev => {
      const next = new Set(prev);
      if (next.has(tagName)) {
        next.delete(tagName);
      } else {
        next.add(tagName);
      }
      return next;
    });
  };

  // Compute live breakdown
  const rationalCount = ONBOARDING_STEPS[0].tags.filter(t => selectedTagNames.has(t.name)).length;
  const emotionalCount = ONBOARDING_STEPS[1].tags.filter(t => selectedTagNames.has(t.name)).length;
  const ambitiousCount = ONBOARDING_STEPS[2].tags.filter(t => selectedTagNames.has(t.name)).length;
  const total = rationalCount + emotionalCount + ambitiousCount || 1;

  let leadingTwin = 'rational';
  if (emotionalCount > rationalCount && emotionalCount >= ambitiousCount) leadingTwin = 'emotional';
  if (ambitiousCount > rationalCount && ambitiousCount > emotionalCount) leadingTwin = 'ambitious';

  const rPct = Math.round((rationalCount / total) * 100);
  const ePct = Math.round((emotionalCount / total) * 100);
  const aPct = 100 - rPct - ePct;

  const handleNext = () => {
    if (currentStep < 2) {
      setCurrentStep(prev => prev + 1);
    } else {
      // Advance to Reveal Step
      setCurrentStep(3);
      setShowConfetti(true);
    }
  };

  const handleFinish = async () => {
    // Compile tags array for backend
    const tagsToSave = [];
    ONBOARDING_STEPS.forEach(step => {
      step.tags.forEach(t => {
        if (selectedTagNames.has(t.name)) {
          tagsToSave.push({ twin_type: step.twin, tag_name: t.name });
        }
      });
    });

    if (customTwinName.trim()) {
      const savedName = onSaveTwinName
        ? await onSaveTwinName(customTwinName.trim())
        : customTwinName.trim();
      setTwinName(savedName);
    }

    if (onSaveProfile) {
      await onSaveProfile(tagsToSave);
    }
    onClose();
  };

  const activeStepData = ONBOARDING_STEPS[currentStep];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <Confetti trigger={showConfetti} onComplete={() => setShowConfetti(false)} />

      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-[#120F1C]/70 dark:bg-[#0A0714]/85 backdrop-blur-md cursor-pointer animate-fadeIn"
      />

      {/* Modal Dialog Card */}
      <div className="relative z-10 w-full max-w-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 animate-pop">

        {/* Step Indicator Dots */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {[0, 1, 2, 3].map((stepIdx) => (
              <div
                key={stepIdx}
                className={`h-2 rounded-full transition-all duration-300 ${
                  currentStep === stepIdx
                    ? 'w-7 bg-brand-gradient'
                    : stepIdx < currentStep
                    ? 'w-2 bg-brand-purple'
                    : 'w-2 bg-stroke-light dark:bg-stroke-dark'
                }`}
              />
            ))}
          </div>

          <span className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark">
            {currentStep < 3 ? `Step ${currentStep + 1} of 3` : 'Calibration Ready'}
          </span>
        </div>

        {/* STEP 0, 1, 2: The 3 Questions */}
        {currentStep < 3 && activeStepData && (
          <div className="space-y-6">
            <div className="space-y-1.5">
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: `${activeStepData.color}20`, color: activeStepData.color }}>
                <activeStepData.icon className="w-3.5 h-3.5" />
                <span className="uppercase tracking-wider">{activeStepData.twin} Style</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                {activeStepData.title}
              </h2>
              <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">
                {activeStepData.subtitle}
              </p>
            </div>

            {/* Big Tappable Tag Chips */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {activeStepData.tags.map((tag) => {
                const isSelected = selectedTagNames.has(tag.name);
                return (
                  <button
                    key={tag.name}
                    type="button"
                    onClick={() => toggleTag(tag.name)}
                    className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'border-brand-purple bg-brand-purple/10 shadow-sm scale-[1.01]'
                        : 'border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark hover:border-brand-purple/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-bold text-content-mainLight dark:text-content-mainDark">
                        {tag.name}
                      </span>
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center border transition ${
                        isSelected
                          ? 'bg-brand-purple border-brand-purple text-white'
                          : 'border-stroke-light dark:border-stroke-dark'
                      }`}>
                        {isSelected && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                    <span className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-snug">
                      {tag.desc}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Navigation buttons */}
            <div className="pt-2 flex items-center justify-between">
              {currentStep > 0 ? (
                <button
                  type="button"
                  onClick={() => setCurrentStep(prev => prev - 1)}
                  className="px-4 py-2.5 rounded-full text-sm font-semibold text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark flex items-center space-x-1.5 transition"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back</span>
                </button>
              ) : <div />}

              <button
                type="button"
                onClick={handleNext}
                className="px-6 py-3 rounded-full bg-brand-gradient text-white text-sm font-bold shadow-md shadow-brand-purple/20 hover:scale-[1.02] active:scale-[0.98] transition flex items-center space-x-2"
              >
                <span>{currentStep === 2 ? 'Meet Echo' : 'Keep going'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Animated "Meet your Twin" Reveal & Rename */}
        {currentStep === 3 && (
          <div className="text-center space-y-6 animate-pop">
            <div className="flex justify-center">
              <EchoOrb size="lg" style={leadingTwin} state="evolving" title={customTwinName || 'Echo'} />
            </div>

            <div className="space-y-2">
              <span className="text-xs uppercase font-mono font-bold px-3 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark text-brand-purple dark:text-[#A894FF] border border-stroke-light dark:border-stroke-dark">
                Starting voice: {leadingTwin}
              </span>
              <h2 className="text-2xl font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                Here's how Echo will start
              </h2>
              <p className="text-sm text-content-mutedLight dark:text-content-mutedDark max-w-sm mx-auto">
                Calibrated with {rPct}% Rational, {ePct}% Emotional, and {aPct}% Ambitious priorities.
              </p>
            </div>

            {/* Customizable Twin Name */}
            <div className="p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-left space-y-2">
              <label className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark block">
                Pick a name that feels natural, or keep Echo:
              </label>
              <input
                type="text"
                value={customTwinName}
                onChange={(e) => setCustomTwinName(e.target.value)}
                placeholder="Echo"
                className="w-full px-4 py-2.5 rounded-xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark font-medium text-sm focus:outline-none focus:ring-2 focus:ring-brand-purple"
              />
            </div>

            {/* Single primary button */}
            <button
              type="button"
              onClick={handleFinish}
              className="w-full py-4 rounded-full bg-brand-gradient text-white font-bold text-base shadow-lg shadow-brand-purple/25 hover:scale-[1.02] active:scale-[0.98] transition flex items-center justify-center space-x-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>Start talking with {customTwinName || 'Echo'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
