import React, { useState } from 'react';
import { Eye, EyeOff, Lock, Mail, User, Sparkles, AlertCircle, ArrowRight } from 'lucide-react';
import EchoOrb from './EchoOrb';
import { api } from '../api';

export default function AuthCard({ onAuthSuccess, onDemoLogin, onBackToHome, initialMode = 'signup' }) {
  const [mode, setMode] = useState(initialMode); // 'signup' | 'login'
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Compute password strength (0 to 4)
  const computeStrength = (pwd) => {
    if (!pwd) return 0;
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score += 1;
    if (/\d/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;
    return score;
  };

  const strength = computeStrength(password);
  const strengthLabels = ['Too weak', 'Weak', 'Moderate', 'Good', 'Strong'];
  const strengthColors = ['bg-stroke-light dark:bg-stroke-dark', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500'];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (mode === 'signup') {
      if (!name.trim()) {
        setError('Please enter your name.');
        return;
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters long.');
        return;
      }
      if (!(/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password))) {
        setError('Add at least one number or symbol to your password.');
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === 'signup') {
        const session = await api.signup({
          name: name.trim(),
          email: email.trim().toLowerCase(),
          password
        });
        onAuthSuccess(session);
      } else {
        const session = await api.login({
          email: email.trim().toLowerCase(),
          password
        });
        onAuthSuccess(session);
      }
    } catch (err) {
      console.error('Authentication failed:', err);
      const detail = String(err?.message || '').trim();
      if (/already exists/i.test(detail)) {
        setError('An account with this email already exists. Choose Sign In to use that account.');
      } else if (/password must contain/i.test(detail)) {
        setError('Add at least one number or symbol to your password.');
      } else if (/password must be at least/i.test(detail)) {
        setError('Password must be at least 8 characters long.');
      } else if (/valid email/i.test(detail)) {
        setError('Enter a valid email address, like name@example.com.');
      } else if (detail) {
        setError(detail);
      } else {
        setError("Hmm, that didn't work. Check your details and try again?");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto w-full px-4 py-8 animate-fadeIn">
      {/* Echo glowing badge */}
      <div className="flex flex-col items-center mb-6 text-center">
        <EchoOrb size="chat" style="default" state={loading ? 'thinking' : 'idle'} />
        <span className="mt-3 text-xs font-semibold px-3 py-1 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-brand-purple dark:text-[#A894FF] inline-flex items-center space-x-1.5">
          <Sparkles className="w-3.5 h-3.5" />
          <span>HumanTwin AI &bull; {mode === 'signup' ? 'Create Account' : 'Welcome Back'}</span>
        </span>
      </div>

      {/* Main Single Card */}
      <div className="p-7 sm:p-8 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light dark:shadow-soft-dark space-y-6">
        {/* Tab Toggle */}
        <div className="grid grid-cols-2 p-1 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark">
          <button
            type="button"
            onClick={() => { setMode('signup'); setError(null); }}
            className={`py-2 text-xs sm:text-sm font-bold rounded-xl transition ${
              mode === 'signup'
                ? 'bg-surface-light dark:bg-surface-dark text-content-mainLight dark:text-content-mainDark shadow-sm'
                : 'text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark'
            }`}
          >
            Create account
          </button>
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null); }}
            className={`py-2 text-xs sm:text-sm font-bold rounded-xl transition ${
              mode === 'login'
                ? 'bg-surface-light dark:bg-surface-dark text-content-mainLight dark:text-content-mainDark shadow-sm'
                : 'text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark'
            }`}
          >
            Log in
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3.5 rounded-2xl bg-red-500/10 border border-red-500/25 flex items-start space-x-2.5 text-xs text-red-600 dark:text-red-400 animate-fadeIn">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'signup' && (
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-content-mutedLight dark:text-content-mutedDark" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Jordan Lee"
                  className="w-full pl-10 pr-4 py-3 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-sm text-content-mainLight dark:text-content-mainDark placeholder-content-mutedLight/50 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 transition"
                />
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-content-mutedLight dark:text-content-mutedDark" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full pl-10 pr-4 py-3 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-sm text-content-mainLight dark:text-content-mainDark placeholder-content-mutedLight/50 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 transition"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-content-mutedLight dark:text-content-mutedDark" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'signup' ? 'At least 8 characters' : 'Enter your password'}
                className="w-full pl-10 pr-11 py-3 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-sm text-content-mainLight dark:text-content-mainDark placeholder-content-mutedLight/50 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {/* Real-time 4-bar Password Strength Meter for Sign Up */}
            {mode === 'signup' && password.length > 0 && (
              <div className="pt-2 space-y-1.5 animate-fadeIn">
                <div className="grid grid-cols-4 gap-1.5 h-1.5">
                  {[1, 2, 3, 4].map((step) => (
                    <div
                      key={step}
                      className={`h-full rounded-full transition-colors duration-300 ${
                        strength >= step ? strengthColors[strength] : 'bg-stroke-light dark:bg-stroke-dark'
                      }`}
                    />
                  ))}
                </div>
                <div className="flex justify-between items-center text-[11px] text-content-mutedLight dark:text-content-mutedDark">
                  <span>Strength: <strong className="text-content-mainLight dark:text-content-mainDark">{strengthLabels[strength]}</strong></span>
                  <span>{strength < 4 ? 'Use 8+ chars, upper, number & symbol' : '✨ Strong'}</span>
                </div>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3.5 px-6 rounded-2xl bg-brand-gradient text-white font-bold text-sm shadow-md shadow-brand-purple/20 hover:shadow-brand-purple/35 hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 transition flex items-center justify-center space-x-2"
          >
            {loading ? (
              <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <span>{mode === 'signup' ? 'Get Started & Pick Tags' : 'Log In to Twin'}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="pt-2 border-t border-stroke-light dark:border-stroke-dark flex flex-col items-center space-y-3 text-xs text-content-mutedLight dark:text-content-mutedDark">
          <button
            type="button"
            onClick={onDemoLogin}
            className="hover:underline font-semibold text-brand-purple dark:text-[#A894FF]"
          >
            Or explore directly as Alex (Demo Persona)
          </button>
          {onBackToHome && (
            <button
              type="button"
              onClick={onBackToHome}
              className="hover:text-content-mainLight dark:hover:text-content-mainDark"
            >
              &larr; Back to overview
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
