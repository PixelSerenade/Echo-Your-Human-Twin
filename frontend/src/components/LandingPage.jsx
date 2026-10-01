import React from 'react';
import EchoOrb from './EchoOrb';
import { Sparkles, Brain, Heart, Rocket, ShieldCheck, ArrowRight, Lock, LogIn } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

/**
 * LandingPage — Gen Z styled public front door.
 * Bold headline, glowing orb hero, 3 benefit cards, privacy trust line, and Sign up / Log in buttons.
 */
export default function LandingPage({
  onSignUp,
  onLogIn,
  onLoginDemo,
  twinStyle = 'default'
}) {
  const { twinName } = useTheme();

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 sm:py-16 space-y-16 animate-fadeIn">
      {/* Hero Section */}
      <div className="text-center space-y-6">
        <div className="flex justify-center mb-6">
          <EchoOrb size="hero" style={twinStyle} state="idle" title={twinName} />
        </div>

        <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-brand-purple dark:text-[#A894FF]">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Meet {twinName} &bull; Your Adaptive Digital Twin</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark tracking-tight leading-[1.15]">
          A twin that learns how you think <br className="hidden sm:inline" />
          <span className="text-gradient">& helps you decide.</span>
        </h1>

        <p className="text-base sm:text-lg text-content-mutedLight dark:text-content-mutedDark max-w-xl mx-auto leading-relaxed">
          Stuck between a crunch deadline and burning out? {twinName} mirrors your thinking, balances logic, mood, and ambition, and maps out clean paths forward.
        </p>

        {/* Primary CTAs */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={onSignUp}
            className="w-full sm:w-auto px-8 py-4 rounded-full bg-brand-gradient text-white font-bold text-base shadow-lg shadow-brand-purple/25 hover:shadow-brand-purple/40 hover:scale-[1.02] active:scale-[0.98] transition flex items-center justify-center space-x-2"
          >
            <span>Sign Up</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <button
            onClick={onLogIn}
            className="w-full sm:w-auto px-7 py-4 rounded-full bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark font-bold text-sm hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark hover:scale-[1.01] active:scale-[0.99] transition flex items-center justify-center space-x-2"
          >
            <LogIn className="w-4 h-4" />
            <span>Log In</span>
          </button>
        </div>

        {/* Subtle Demo Option */}
        <div className="pt-1">
          <button
            onClick={onLoginDemo}
            className="text-xs font-medium text-content-mutedLight dark:text-content-mutedDark hover:text-brand-purple dark:hover:text-[#A894FF] underline transition"
          >
            Or explore directly as Alex (Demo Persona)
          </button>
        </div>
      </div>

      {/* 3 Benefit Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Benefit 1: Understands you */}
        <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3 hover:translate-y-[-2px] transition">
          <div className="w-12 h-12 rounded-2xl bg-style-rational/15 text-style-rational flex items-center justify-center">
            <Brain className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              Understands you
            </h3>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
              Learns your focus peaks, energy patterns, and work rhythms so advice fits how you actually work.
            </p>
          </div>
        </div>

        {/* Benefit 2: Shows you options */}
        <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3 hover:translate-y-[-2px] transition">
          <div className="w-12 h-12 rounded-2xl bg-style-emotional/15 text-style-emotional flex items-center justify-center">
            <Heart className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              Shows you options
            </h3>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
              Maps out two clean paths when assignments collide, showing realistic trade-offs with zero guilt.
            </p>
          </div>
        </div>

        {/* Benefit 3: You stay in control */}
        <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-3 hover:translate-y-[-2px] transition">
          <div className="w-12 h-12 rounded-2xl bg-style-ambitiousFrom/15 text-style-ambitiousFrom flex items-center justify-center">
            <Rocket className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              You stay in control
            </h3>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
              Full toggle control over what Echo can see. Switch your twin's thinking style or wipe data anytime.
            </p>
          </div>
        </div>
      </div>

      {/* Clear Privacy Line */}
      <div className="p-5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark flex items-center space-x-3.5 text-xs text-content-mutedLight dark:text-content-mutedDark">
        <Lock className="w-4 h-4 text-brand-purple flex-shrink-0" />
        <p className="leading-relaxed">
          <strong className="text-content-mainLight dark:text-content-mainDark">Privacy First:</strong> Your data is strictly used to compute your twin's decisions. Never sold, never shared, zero tracking.
        </p>
      </div>
    </div>
  );
}
