import React from 'react';
import EchoOrb from './EchoOrb';
import Confetti from './Confetti';
import { Sparkles, ArrowRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useTheme } from '../context/ThemeContext';

export default function EvolutionModal({ alertData, onClose }) {
  const { twinName, effectiveTheme } = useTheme();

  if (!alertData || !alertData.evolved) return null;

  const { old_primary, new_primary, one_line_description, before_weights, after_weights } = alertData;

  const chartData = [
    {
      twin: 'Rational',
      'Before Evolution': Math.round((before_weights?.rational || 0.33) * 100),
      'After Evolution': Math.round((after_weights?.rational || 0.33) * 100),
    },
    {
      twin: 'Emotional',
      'Before Evolution': Math.round((before_weights?.emotional || 0.33) * 100),
      'After Evolution': Math.round((after_weights?.emotional || 0.33) * 100),
    },
    {
      twin: 'Ambitious',
      'Before Evolution': Math.round((before_weights?.ambitious || 0.33) * 100),
      'After Evolution': Math.round((after_weights?.ambitious || 0.33) * 100),
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <Confetti trigger={true} />

      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-[#120F1C]/70 dark:bg-[#0A0714]/85 backdrop-blur-md cursor-pointer animate-fadeIn"
      />

      <div className="relative z-10 w-full max-w-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 text-center animate-pop">
        {/* Glowing Echo Orb */}
        <div className="flex justify-center">
          <EchoOrb size="lg" style={new_primary} state="evolving" title={twinName} />
        </div>

        <div className="space-y-1.5">
          <span className="px-3 py-1 text-xs font-mono font-bold tracking-wider uppercase rounded-full bg-brand-purple/15 text-brand-purple dark:text-[#A894FF] border border-brand-purple/30">
            {twinName} noticed a pattern
          </span>

          <h2 className="text-2xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
            {twinName}'s voice is shifting
          </h2>

          <div className="flex items-center justify-center space-x-2 pt-2 text-xs font-bold uppercase">
            <span className="px-3 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mutedLight dark:text-content-mutedDark">
              {old_primary} Twin
            </span>
            <ArrowRight className="w-4 h-4 text-brand-purple" />
            <span className="px-3 py-1 rounded-full bg-brand-gradient text-white shadow-sm">
              {new_primary} voice
            </span>
          </div>
        </div>

        <p className="text-xs text-content-mainLight dark:text-content-mainDark leading-relaxed bg-surface-subtleLight dark:bg-surface-subtleDark p-4 rounded-2xl border border-stroke-light dark:border-stroke-dark">
          "{one_line_description}"
        </p>

        {/* Before / After Weights Chart */}
        <div className="p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-left space-y-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-content-mutedLight dark:text-content-mutedDark block">
            What changed behind the scenes
          </span>

          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="twin" stroke="#A9A1C4" fontSize={11} />
                <YAxis stroke="#A9A1C4" fontSize={11} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: effectiveTheme === 'dark' ? '#1D1830' : '#FFFFFF',
                    borderColor: effectiveTheme === 'dark' ? '#2E2747' : '#ECE6FA',
                    borderRadius: '12px',
                    fontSize: '11px',
                    color: effectiveTheme === 'dark' ? '#F4F0FF' : '#1B1530'
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                <Bar dataKey="Before Evolution" fill="#A9A1C4" radius={[4, 4, 0, 0]} />
                <Bar dataKey="After Evolution" fill="#7C5CFF" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-full py-3.5 rounded-full font-bold text-sm text-white bg-brand-gradient shadow-md shadow-brand-purple/20 hover:scale-[1.02] active:scale-[0.98] transition"
        >
          Got it
        </button>
      </div>
    </div>
  );
}
