import React, { useState } from 'react';
import { useTheme } from '../context/ThemeContext';
import { Brain, Heart, TrendingUp, Sparkles, ChevronRight, CheckCircle, HelpCircle, ArrowLeft, RefreshCw, Scale } from 'lucide-react';

export default function DebateStudio({
  debateData,
  isLoading,
  onBack,
  onRefreshDebate
}) {
  const { twinName } = useTheme();
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initialStep = urlParams ? Math.min(3, Math.max(1, parseInt(urlParams.get('step') || '1', 10))) : 1;
  const [revealStep, setRevealStep] = useState(initialStep);

  if (isLoading) {
    return (
      <div className="bg-[#0f172a]/90 border border-slate-800 rounded-3xl p-12 text-center space-y-4 shadow-2xl">
        <div className="w-12 h-12 mx-auto rounded-2xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30 animate-pulse">
          <Scale className="w-6 h-6 animate-spin" style={{ animationDuration: '4s' }} />
        </div>
        <h3 className="text-base font-bold text-slate-100">
          Pulling the other perspectives together...
        </h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Give me a moment to look at this from a few angles.
        </p>
      </div>
    );
  }

  if (!debateData) {
    return (
      <div className="bg-[#0f172a]/90 border border-slate-800 rounded-2xl p-8 text-center space-y-3">
        <p className="text-xs text-slate-400">There's nothing to compare yet. Ask {twinName} about a decision first.</p>
        <button
          onClick={onBack}
          className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
        >
          Return to Ask Twin
        </button>
      </div>
    );
  }

  const { primary_twin, other_twins = [], synthesis } = debateData;
  const twin1 = other_twins[0];
  const twin2 = other_twins[1];

  const twinTheme = {
    rational: {
      border: 'border-cyan-700/60 bg-cyan-950/20',
      badge: 'bg-cyan-950 text-cyan-400 border-cyan-700/60',
      icon: Brain,
      titleColor: 'text-cyan-400'
    },
    emotional: {
      border: 'border-pink-700/60 bg-pink-950/20',
      badge: 'bg-pink-950 text-pink-400 border-pink-700/60',
      icon: Heart,
      titleColor: 'text-pink-400'
    },
    ambitious: {
      border: 'border-amber-700/60 bg-amber-950/20',
      badge: 'bg-amber-950 text-amber-400 border-amber-700/60',
      icon: TrendingUp,
      titleColor: 'text-amber-400'
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-[#0f172a]/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex items-center justify-between flex-wrap gap-3">
        <div>
          <button
            onClick={onBack}
            className="text-xs font-mono text-slate-400 hover:text-slate-200 flex items-center space-x-1.5 mb-1.5 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Primary Answer</span>
          </button>
          <div className="flex items-center space-x-2.5">
            <Scale className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-slate-100">
              A few honest ways to look at this
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Q: <span className="text-slate-200 italic">"{debateData.question}"</span>
          </p>
        </div>

        {/* Step reveal controller */}
        <div className="flex items-center space-x-2">
          {revealStep < 3 && (
            <button
              onClick={() => setRevealStep(prev => prev + 1)}
              className="px-4 py-2 rounded-xl text-xs font-bold text-slate-950 bg-gradient-to-r from-cyan-400 via-indigo-400 to-pink-400 hover:opacity-95 shadow-md shadow-indigo-500/20 transition flex items-center space-x-1.5"
            >
              <span>Hear another voice</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
          {revealStep === 3 && (
            <span className="text-[11px] font-mono px-3 py-1.5 rounded-xl bg-emerald-950/80 text-emerald-300 border border-emerald-700/60">
              You've heard every side
            </span>
          )}
        </div>
      </div>

      {/* CARD 1: First Other Twin (Always revealed) */}
      {twin1 && (
        <div className={`p-6 rounded-2xl border ${twinTheme[twin1.twin]?.border || 'border-slate-800'} shadow-xl space-y-4 animate-fadeIn`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-1 text-xs font-mono font-bold uppercase rounded-lg border ${twinTheme[twin1.twin]?.badge}`}>
                {twin1.twin} voice
              </span>
              <span className="text-xs text-slate-400">Another honest take</span>
            </div>
          </div>

          <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-line bg-slate-900/60 p-4 rounded-xl border border-slate-800/60">
            {twin1.argument}
          </p>
        </div>
      )}

      {/* CARD 2: Second Other Twin (Revealed when revealStep >= 2) */}
      {revealStep >= 2 && twin2 && (
        <div className={`p-6 rounded-2xl border ${twinTheme[twin2.twin]?.border || 'border-slate-800'} shadow-xl space-y-4 animate-fadeIn`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-1 text-xs font-mono font-bold uppercase rounded-lg border ${twinTheme[twin2.twin]?.badge}`}>
                {twin2.twin} voice
              </span>
              <span className="text-xs text-slate-400">Another honest take</span>
            </div>
          </div>

          <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-line bg-slate-900/60 p-4 rounded-xl border border-slate-800/60">
            {twin2.argument}
          </p>
        </div>
      )}

      {/* CARD 3: HumanTwin Synthesis (Revealed when revealStep >= 3) */}
      {revealStep >= 3 && synthesis && (
        <div className="bg-[#0f172a]/95 border-2 border-indigo-500/50 rounded-2xl p-6 shadow-2xl space-y-5 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2.5">
              <Sparkles className="w-5 h-5 text-indigo-400 animate-pulse" />
              <h3 className="text-base font-bold text-slate-100">
                Where this leaves you
              </h3>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-indigo-950 text-indigo-300 border border-indigo-700/60">
              Your call, with the trade-offs made clear
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/80 p-3.5 rounded-xl border border-slate-800">
            {synthesis.summary_of_tensions}
          </p>

          {/* Trade-Offs Dimensions */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">
              What you're balancing
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {synthesis.trade_offs?.map((to, i) => (
                <div key={i} className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                  <span className="text-xs font-bold text-cyan-300 font-mono block">
                    {to.dimension}
                  </span>
                  <p className="text-xs text-slate-300 leading-snug">{to.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Compromise Option */}
          {synthesis.compromise_option && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-cyan-950/40 via-indigo-950/40 to-pink-950/40 border border-indigo-500/50 space-y-1.5 shadow-md">
              <div className="flex items-center space-x-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-300 font-mono">
                  A middle path: {synthesis.compromise_option.title}
                </span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed">
                {synthesis.compromise_option.action}
              </p>
            </div>
          )}

          {/* Consider Before Deciding Checklist */}
          {synthesis.consider_before_deciding?.length > 0 && (
            <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
              <div className="flex items-center space-x-2">
                <HelpCircle className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-bold font-mono uppercase tracking-wider text-amber-300">
                  A few things to ask yourself
                </span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
                {synthesis.consider_before_deciding.map((item, i) => (
                  <li key={i} className="leading-snug">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
