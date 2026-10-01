import React, { useState, useEffect } from 'react';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import Navbar from './components/Navbar';
import LandingPage from './components/LandingPage';
import AuthCard from './components/AuthCard';
import OnboardingWizard from './components/OnboardingWizard';
import AskSection from './components/AskSection';
import SimulatorSection from './components/SimulatorSection';
import MyPlanSection from './components/MyPlanSection';
import PrivacySection from './components/PrivacySection';
import TwinKnowledgeSection from './components/TwinKnowledgeSection';
import SettingsSection from './components/SettingsSection';
import OnboardingModal from './components/OnboardingModal';
import EvolutionModal from './components/EvolutionModal';
import { api, BASE_URL } from './api';
import { resolveTwinName } from './utils/identity';

function AppContent() {
  const { activePage, setActivePage, twinName, setTwinName, setTwinStyle } = useTheme();
  const [currentUser, setCurrentUser] = useState(null);
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState('signup');
  const [profile, setProfile] = useState(null);
  const [lastAnswer, setLastAnswer] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [evolutionAlert, setEvolutionAlert] = useState(null);
  const [statusNotification, setStatusNotification] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');

  // Active Plan persisted in localStorage
  const [activePlan, setActivePlan] = useState(() => {
    try {
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        if (params.get('demo_plan') === 'true') {
          return {
            id: 'path-balanced',
            name: 'Balanced',
            aligned_twin: 'rational',
            steps: [
              { time: '18:00 - 20:00', task: 'Focused time for a priority you choose', completed: true },
              { time: '20:00 - 21:30', task: 'Take a break and recharge', completed: false },
              { time: '21:30 - 00:30', task: 'Make a little progress on another priority', completed: false },
              { time: '00:30 - 08:00', task: 'Rest and recharge', completed: false }
            ],
            what_youll_achieve: "You'll make room for both priorities and leave time to recharge.",
            what_it_risks: 'An unexpected delay could make the schedule feel tight.',
            simulated_metrics: { energy: 75.0, happiness: 78.0, study: 70.0, free_time: 55.0 },
            on_time_probability: 21.2,
            remindersEnabled: true,
            reflection: 'balanced',
            createdAt: new Date().toISOString()
          };
        }
      }
      const saved = localStorage.getItem('humantwin_active_plan');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const handleUpdateActivePlan = (updated) => {
    setActivePlan(updated);
    if (updated) {
      localStorage.setItem('humantwin_active_plan', JSON.stringify(updated));
    } else {
      localStorage.removeItem('humantwin_active_plan');
    }
  };

  const handleChoosePath = async (path, questionText) => {
    const newPlan = {
      id: path.id || `plan-${Date.now()}`,
      name: path.name,
      aligned_twin: path.aligned_twin,
      steps: (path.steps || []).map((s, idx) => ({ ...s, id: idx, completed: false })),
      what_youll_achieve: path.what_youll_achieve,
      what_it_risks: path.what_it_risks,
      simulated_metrics: path.simulated_metrics,
      on_time_probability: path.on_time_probability,
      explanation: path.explanation,
      remindersEnabled: true,
      reflection: null,
      createdAt: new Date().toISOString()
    };
    handleUpdateActivePlan(newPlan);

    // Record decision in backend history for adaptive twin logic
    try {
      await handleOptionSelected({
        question: questionText || lastAnswer?.question || 'What should I do about my test and assignment?',
        options: (lastAnswer?.paths || []).map(p => ({ id: p.id, text: p.name, aligned_twin: p.aligned_twin })),
        twin_recommended: lastAnswer?.primary_twin || 'rational',
        option_chosen: path.name,
        aligned_twin: path.aligned_twin,
        followed_recommendation: path.aligned_twin === (lastAnswer?.primary_twin || 'rational'),
        feedback_understood: true
      });
    } catch (err) {
      console.error('Error recording path decision:', err);
    }

    setStatusNotification(`${twinName} saved ${path.name} and will remind you when it's time to start.`);
    setTimeout(() => setStatusNotification(''), 4000);
  };

  const handleAskFromPlan = (q) => {
    setPendingQuestion(q);
    setActivePage('chat');
  };

  const handleLoginDemo = async () => {
    if (!BASE_URL) return;
    try {
      const p = await api.getProfile('demo-alex-rivers');
      const safeTwinName = resolveTwinName(p.twin_name, p.user_name || p.name, p.twin_name_customized);
      setProfile(p);
      setCurrentUser({
        user_id: 'demo-alex-rivers',
        name: 'Alex Rivers',
        email: 'alex.rivers@humantwin.ai',
        twin_name: safeTwinName,
        twin_name_customized: p.twin_name_customized,
        onboarding_completed: true,
        onboarding_step: 'completed',
        primary_twin: p.primary_twin,
        weights: p.weights
      });
      setTwinName(safeTwinName);
      setTwinStyle(p.primary_twin || 'rational');
      setShowAuth(false);
      setActivePage('chat');
    } catch (err) {
      console.error('Failed to load demo user:', err);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (e) {}
    setCurrentUser(null);
    setTwinName('Echo');
    setProfile(null);
    setShowAuth(false);
    setActivePage('landing');
    setStatusNotification("You're logged out. See you next time.");
    setTimeout(() => setStatusNotification(''), 3000);
  };

  const handleAuthSuccess = async (session) => {
    setCurrentUser(session);
    setTwinName(resolveTwinName(session.twin_name, session.name, session.twin_name_customized));
    if (session.primary_twin) setTwinStyle(session.primary_twin);

    try {
      const p = await api.getProfile(session.user_id);
      setProfile(p);
    } catch (e) {
      setProfile({
        user_id: session.user_id,
        name: session.name,
        primary_twin: session.primary_twin || 'rational',
        weights: session.weights || { rational: 0.34, emotional: 0.33, ambitious: 0.33 },
        tags: []
      });
    }

    setShowAuth(false);
    if (session.onboarding_completed) {
      setActivePage('chat');
    }
  };

  const handleOnboardingComplete = async (finalData) => {
    const completedTwinName = resolveTwinName(finalData.twin_name, currentUser?.name, true);
    setCurrentUser((prev) => ({
      ...prev,
      onboarding_completed: true,
      onboarding_step: 'completed',
      twin_name: completedTwinName,
      twin_name_customized: completedTwinName !== 'Echo',
      primary_twin: finalData.primary_twin
    }));
    setTwinName(completedTwinName);
    setTwinStyle(finalData.primary_twin || 'rational');

    try {
      const p = await api.getProfile(currentUser?.user_id || 'demo-alex-rivers');
      setProfile(p);
    } catch (e) {}

    setActivePage('chat');
    setStatusNotification(`${completedTwinName} is ready when you are.`);
    setTimeout(() => setStatusNotification(''), 4000);
  };

  // Check existing session on mount
  useEffect(() => {
    async function initSession() {
      // Check URL parameters for direct test hooks
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        if (params.get('auth') === 'true') {
          setCurrentUser(null);
          setAuthMode(params.get('mode') || 'signup');
          setShowAuth(true);
          return;
        }
        if (params.get('onboarding') === 'true') {
          const stepParam = params.get('step') || 'tags';
          setCurrentUser({
            user_id: 'test-preview-user',
            name: 'Jordan Lee',
            email: 'jordan@test.com',
            twin_name: 'Echo',
            onboarding_completed: false,
            onboarding_step: stepParam
          });
          return;
        }
        if (params.get('landing') === 'true') {
          setCurrentUser(null);
          setShowAuth(false);
          setActivePage('landing');
          return;
        }
        if (params.get('demo') === 'true' || params.get('answered') === 'true' || params.get('demo_plan') === 'true' || params.get('drawer') === 'details') {
          handleLoginDemo();
          return;
        }
      }

      try {
        const me = await api.getMe();
        if (me && me.user_id) {
          setCurrentUser(me);
          setTwinName(resolveTwinName(me.twin_name, me.name, me.twin_name_customized));
          if (me.primary_twin) setTwinStyle(me.primary_twin);
          const p = await api.getProfile(me.user_id);
          setProfile(p);
          if (me.onboarding_completed) {
            setActivePage('chat');
          }
          return;
        }
      } catch (e) {
        // Not authenticated
      }

      setActivePage('landing');
    }
    initSession();
  }, []);

  const handleOptionSelected = async (decisionData) => {
    try {
      const res = await api.submitFeedback({
        user_id: profile?.user_id || currentUser?.user_id || 'demo-alex-rivers',
        ...decisionData
      });

      if (res.weights) {
        setProfile(prev => ({
          ...prev,
          primary_twin: res.weights.primary_twin,
          weights: res.weights
        }));
      }

      if (res.twin_evolved && res.evolution_alert) {
        setEvolutionAlert(res.evolution_alert);
      } else {
        setStatusNotification(`${twinName} will remember that choice for next time.`);
        setTimeout(() => setStatusNotification(''), 4000);
      }
    } catch (err) {
      console.error('Feedback submission failed:', err);
    }
  };

  const handleSaveProfile = async (tags) => {
    try {
      const res = await api.saveProfile({
        user_id: profile?.user_id || currentUser?.user_id || 'demo-alex-rivers',
        name: profile?.name || currentUser?.name || 'Alex Rivers',
        email: profile?.email || currentUser?.email || 'alex.rivers@humantwin.ai',
        demo_mode: profile?.demo_mode ?? true,
        tags
      });
      setProfile(res);
      setStatusNotification(`All set. ${twinName} will lean ${res.primary_twin} from here.`);
      setTimeout(() => setStatusNotification(''), 4000);
      setActivePage('chat');
    } catch (err) {
      console.error('Failed to save profile tags:', err);
    }
  };

  const handleResetPersona = async () => {
    if (!window.confirm("Reset demo persona to clean baseline (50 Rational, 25 Emotional, 25 Ambitious)?")) return;
    try {
      const defaultTags = [
        { twin_type: 'rational', tag_name: 'plans ahead' },
        { twin_type: 'rational', tag_name: 'deadline-driven' },
        { twin_type: 'rational', tag_name: 'risk-averse' },
        { twin_type: 'rational', tag_name: 'optimizes schedule' },
        { twin_type: 'emotional', tag_name: 'avoids burnout' },
        { twin_type: 'emotional', tag_name: 'values peace of mind' },
        { twin_type: 'ambitious', tag_name: 'career-focused' },
        { twin_type: 'ambitious', tag_name: 'takes opportunities' }
      ];
      await handleSaveProfile(defaultTags);
      setLastAnswer(null);
      setStatusNotification("All clear. The demo profile is back to its starting point.");
      setTimeout(() => setStatusNotification(''), 3000);
    } catch (err) {
      console.error('Reset failed:', err);
    }
  };

  const handleUpdateDemoMode = async (isDemo) => {
    if (profile) {
      setProfile(prev => ({ ...prev, demo_mode: isDemo }));
    }
  };

  const handleSaveTwinName = async (requestedName) => {
    const response = await api.updateTwinName(
      currentUser?.user_id || profile?.user_id || 'demo-alex-rivers',
      requestedName
    );
    const safeTwinName = resolveTwinName(
      response.twin_name,
      response.user_name,
      response.twin_name_customized
    );
    setTwinName(safeTwinName);
    setCurrentUser((previous) => previous ? {
      ...previous,
      twin_name: safeTwinName,
      twin_name_customized: response.twin_name_customized
    } : previous);
    setProfile((previous) => previous ? {
      ...previous,
      twin_name: safeTwinName,
      twin_name_customized: response.twin_name_customized
    } : previous);
    setStatusNotification(`${safeTwinName} is saved as your twin's name.`);
    setTimeout(() => setStatusNotification(''), 3000);
    return safeTwinName;
  };

  const handlePersonaChange = async (persona) => {
    const userId = profile?.user_id || currentUser?.user_id;
    await api.updatePersona(userId, persona);
    setProfile((previous) => previous ? { ...previous, persona } : previous);
    setCurrentUser((previous) => previous ? { ...previous, persona } : previous);
  };

  // Determine which primary view to render:
  // 1. If logged in and onboarding not completed -> show OnboardingWizard!
  // 2. If showAuth -> show AuthCard
  // 3. Otherwise show activePage
  const isOnboardingActive = currentUser && !currentUser.onboarding_completed;

  return (
    <div className="min-h-screen bg-app text-content flex flex-col font-sans">
      {/* Global Navbar (shown when inside dashboard) */}
      {!isOnboardingActive && !showAuth && activePage !== 'landing' && (
        <Navbar
          profile={profile}
          activeTab={activePage}
          setActiveTab={setActivePage}
          onOpenOnboarding={() => setIsOnboardingOpen(true)}
          currentUser={currentUser}
          onLogout={handleLogout}
          api={api}
          onOpenPrivacy={() => setActivePage('privacy')}
        />
      )}

      {/* Real-time Status Notification Toast */}
      {statusNotification && (
        <div className="bg-brand-purple/15 dark:bg-brand-purple/25 border-b border-brand-purple/30 px-4 py-2 text-center text-xs font-semibold text-brand-purple dark:text-[#C5B8FF] animate-fadeIn">
          {statusNotification}
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 w-full mx-auto">
        {/* Onboarding Wizard for new or resuming users */}
        {isOnboardingActive ? (
          <OnboardingWizard
            initialStep={currentUser.onboarding_step || 'tags'}
            currentUser={currentUser}
            onComplete={handleOnboardingComplete}
          />
        ) : showAuth ? (
          <AuthCard
            initialMode={authMode}
            onAuthSuccess={handleAuthSuccess}
            onDemoLogin={BASE_URL ? handleLoginDemo : undefined}
            onBackToHome={() => setShowAuth(false)}
          />
        ) : (
          <>
            {activePage === 'landing' && (
              <LandingPage
                onSignUp={() => { setAuthMode('signup'); setShowAuth(true); }}
                onLogIn={() => { setAuthMode('login'); setShowAuth(true); }}
                onLoginDemo={BASE_URL ? handleLoginDemo : undefined}
                twinStyle={profile?.primary_twin || 'rational'}
              />
            )}

            {activePage === 'chat' && (
              <AskSection
                key={profile?.user_id || 'demo-alex-rivers'}
                profile={profile}
                onOptionSelected={handleOptionSelected}
                onChoosePath={handleChoosePath}
                activePlan={activePlan}
                pendingQuestion={pendingQuestion}
                setPendingQuestion={setPendingQuestion}
                onComparePaths={() => setActivePage('plan')}
                lastAnswer={lastAnswer}
                setLastAnswer={setLastAnswer}
                isLoading={isLoading}
                setIsLoading={setIsLoading}
                api={api}
              />
            )}

            {activePage === 'plan' && (
              new URLSearchParams(window.location.search).get('dev') === '1' ? <SimulatorSection
                api={api}
                profile={profile}
                activePlan={activePlan}
                onUpdatePlan={handleUpdateActivePlan}
                onAskEcho={handleAskFromPlan}
              /> : <MyPlanSection key={profile?.user_id || currentUser?.user_id || 'demo-alex-rivers'} api={api} profile={profile} userId={profile?.user_id || currentUser?.user_id || 'demo-alex-rivers'} onAskEcho={handleAskFromPlan} />
            )}

            {activePage === 'privacy' && (
              <PrivacySection key={profile?.user_id || currentUser?.user_id || 'demo-alex-rivers'} api={api} profile={profile} onPersonaChange={handlePersonaChange} />
            )}

            {activePage === 'twin' && (
              <TwinKnowledgeSection key={profile?.user_id || currentUser?.user_id || 'demo-alex-rivers'} api={api} profile={profile} />
            )}

            {activePage === 'settings' && (
              <SettingsSection
                key={profile?.user_id || currentUser?.user_id || 'demo-alex-rivers'}
                api={api}
                profile={profile}
                onResetPersona={handleResetPersona}
                onUpdateDemoMode={handleUpdateDemoMode}
                onSaveTwinName={handleSaveTwinName}
                onPersonaChange={handlePersonaChange}
              />
            )}
          </>
        )}
      </main>

      {/* Onboarding Questionnaire Modal (accessible from Settings/Navbar) */}
      <OnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
        currentTags={profile?.tags || []}
        onSaveProfile={handleSaveProfile}
        onSaveTwinName={handleSaveTwinName}
      />

      {/* Personality Evolution Celebration Modal */}
      <EvolutionModal
        alertData={evolutionAlert}
        onClose={() => setEvolutionAlert(null)}
      />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
