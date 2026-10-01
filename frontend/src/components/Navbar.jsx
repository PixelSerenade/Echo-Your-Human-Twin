import React from 'react';
import EchoOrb from './EchoOrb';
import {
  MessageSquare, Sliders, ShieldCheck, Database,
  Settings, Sun, Moon, Sparkles, Zap, Brain, Heart, Rocket, LogOut
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import NotificationBell from './NotificationBell';

export default function Navbar({
  profile,
  activeTab,
  setActiveTab,
  onOpenOnboarding,
  currentUser,
  onLogout,
  api,
  onOpenPrivacy
}) {
  const { theme, effectiveTheme, setTheme, twinName } = useTheme();

  const primaryTwin = profile?.primary_twin || 'rational';
  const weights = profile?.weights || { rational: 0.5, emotional: 0.25, ambitious: 0.25 };

  const styleColors = {
    rational: '#2EC4B6',
    emotional: '#FF8FA3',
    ambitious: '#8B5CF6'
  };

  const navItems = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'plan', label: 'My Plan', icon: Sliders },
    { id: 'privacy', label: 'Privacy', icon: ShieldCheck },
    { id: 'twin', label: 'My Twin', icon: Database },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  const toggleTheme = () => {
    if (theme === 'light') setTheme('dark');
    else if (theme === 'dark') setTheme('light');
    else setTheme(effectiveTheme === 'dark' ? 'light' : 'dark');
  };

  const rPct = Math.round((weights.rational || 0.5) * 100);
  const ePct = Math.round((weights.emotional || 0.25) * 100);
  const aPct = Math.round((weights.ambitious || 0.25) * 100);

  return (
    <>
      {/* DESKTOP & MOBILE TOP BAR */}
      <header className="sticky top-0 z-40 bg-surface-light/80 dark:bg-surface-dark/80 backdrop-blur-md border-b border-stroke-light dark:border-stroke-dark transition-colors duration-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">
            {/* Left: Echo Orb & Name */}
            <div
              onClick={() => setActiveTab('chat')}
              className="flex items-center space-x-3 cursor-pointer group"
            >
              <EchoOrb size="sm" style={primaryTwin} state="idle" title={twinName} />
              <div>
                <div className="flex items-center space-x-1.5">
                  <span className="font-extrabold font-heading text-base text-content-mainLight dark:text-content-mainDark tracking-tight group-hover:text-brand-purple transition">
                    {twinName}
                  </span>
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: styleColors[primaryTwin] }}
                  />
                </div>
                <span className="text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark block capitalize">
                  {primaryTwin} style
                </span>
              </div>
            </div>

            {/* Middle: Desktop Nav Pill Bar */}
            <nav className="hidden md:flex items-center space-x-1 bg-surface-subtleLight dark:bg-surface-subtleDark p-1 rounded-full border border-stroke-light dark:border-stroke-dark">
              {navItems.map(item => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition flex items-center space-x-1.5 ${
                      isActive
                        ? 'bg-brand-purple text-white shadow-sm'
                        : 'text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark'
                    }`}
                  >
                    <item.icon className="w-3.5 h-3.5" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>

            {/* Right: Theme Toggle & Tags Configuration */}
            <div className="flex items-center space-x-2">
              <NotificationBell key={profile?.user_id || currentUser?.user_id} api={api} userId={profile?.user_id || currentUser?.user_id} activeTab={activeTab} onOpenPrivacy={onOpenPrivacy} />
              {/* Quick Theme Switch */}
              <button
                type="button"
                onClick={toggleTheme}
                aria-label="Toggle theme"
                className="w-9 h-9 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark flex items-center justify-center text-content-mutedLight dark:text-content-mutedDark hover:text-content-mainLight dark:hover:text-content-mainDark transition"
              >
                {effectiveTheme === 'dark' ? (
                  <Sun className="w-4 h-4 text-amber-400" />
                ) : (
                  <Moon className="w-4 h-4 text-brand-purple" />
                )}
              </button>

              {/* Configure Tags */}
              <button
                type="button"
                onClick={onOpenOnboarding}
                className="px-3.5 py-2 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-content-mainLight dark:text-content-mainDark hover:border-brand-purple/40 transition flex items-center space-x-1.5"
              >
                <Sparkles className="w-3.5 h-3.5 text-brand-purple" />
                <span className="hidden sm:inline">Configure Tags</span>
              </button>

              {/* Log out button if authenticated */}
              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  title="Log out"
                  className="w-9 h-9 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark flex items-center justify-center text-content-mutedLight dark:text-content-mutedDark hover:text-red-500 hover:border-red-500/30 transition"
                  aria-label="Log out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* MOBILE BOTTOM NAVIGATION BAR */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface-light/90 dark:bg-surface-dark/90 backdrop-blur-md border-t border-stroke-light dark:border-stroke-dark flex items-center justify-around py-2 px-1">
        {navItems.map(item => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex flex-col items-center py-1 px-3 rounded-2xl transition ${
                isActive
                  ? 'text-brand-purple font-bold'
                  : 'text-content-mutedLight dark:text-content-mutedDark font-medium'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-[10px] mt-0.5">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
