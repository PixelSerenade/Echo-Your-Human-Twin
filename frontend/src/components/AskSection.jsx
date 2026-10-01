import React, { useState, useEffect } from 'react';
import EchoOrb from './EchoOrb';
import SlideUpDrawer from './SlideUpDrawer';
import SkeletonLoader from './SkeletonLoader';
import {
  Sparkles, AlertTriangle, Scale, Plus, MessageSquare,
  Brain, Heart, Rocket, Info, PhoneCall, ExternalLink, FileText
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import ChatComposer from './ChatComposer';
import { CHAT_CONTEXT_TURN_LIMIT, CHAT_HISTORY_RETENTION_MS, createChatThread, readChatWorkspace, retainChatHistory, titleForChat } from '../utils/chatHistory';
import { learningProgressFromTurns, nextLearningProgress } from '../utils/learningProgress';

const STARTER_CHIPS = [
  {
    icon: '✨',
    label: 'Deadline priorities',
    q: 'How should I prioritize two important deadlines this week?'
  },
  {
    icon: '🎯',
    label: 'Focus for Tonight',
    q: 'What tasks should I focus on tonight?'
  },
  {
    icon: '☕',
    label: 'Guilt-Free Rest Check',
    q: 'Can I just relax and ignore schoolwork for the next two days?'
  }
];
export default function AskSection({
  profile,
  pendingQuestion,
  setPendingQuestion,
  lastAnswer,
  setLastAnswer,
  isLoading,
  setIsLoading,
  api
}) {
  const { twinName } = useTheme();
  const [inputText, setInputText] = useState('');
  const [activeDrawer, setActiveDrawer] = useState(null); // 'why' | 'debate' | null
  const [debateLoading, setDebateLoading] = useState(false);
  const [debateData, setDebateData] = useState(null);
  const [debateError, setDebateError] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const userId = profile?.user_id || 'demo-alex-rivers';
  const conversationStorageKey = `echo-chat-workspace-${userId}`;
  const legacyHistoryKey = `echo-chat-history-${userId}`;
  const [chatWorkspace, setChatWorkspace] = useState(() => typeof window !== 'undefined'
    ? readChatWorkspace(conversationStorageKey, legacyHistoryKey, window.localStorage, window.sessionStorage)
    : { activeThreadId: '', threads: [] });
  const [historyLoadedForKey, setHistoryLoadedForKey] = useState(conversationStorageKey);
  const [voiceFeedback, setVoiceFeedback] = useState(null);
  const [decisionFeedback, setDecisionFeedback] = useState('');
  const [chosenAlternative, setChosenAlternative] = useState('');
  const [showAlternativeInput, setShowAlternativeInput] = useState(false);
  const [savingDecisionFeedback, setSavingDecisionFeedback] = useState(false);
  const [sessionStyleWeights, setSessionStyleWeights] = useState(null);
  const [sessionStyleChange, setSessionStyleChange] = useState(0);
  const [attachment, setAttachment] = useState(null);
  const [extractionStatus, setExtractionStatus] = useState('');
  const [starterPrompts, setStarterPrompts] = useState([]);
  const [learningCategories, setLearningCategories] = useState([]);
  const [memoryCategoryNames, setMemoryCategoryNames] = useState({});
  const [dimensionLabels, setDimensionLabels] = useState({ progress: 'Personal Progress', goals: 'Goal Progress' });

  useEffect(() => {
    if (historyLoadedForKey === conversationStorageKey) return;
    const restored = typeof window !== 'undefined'
      ? readChatWorkspace(conversationStorageKey, legacyHistoryKey, window.localStorage, window.sessionStorage)
      : { activeThreadId: '', threads: [] };
    setChatWorkspace(restored);
    setHistoryLoadedForKey(conversationStorageKey);
  }, [conversationStorageKey, historyLoadedForKey, legacyHistoryKey]);

  useEffect(() => {
    if (historyLoadedForKey !== conversationStorageKey) return;
    try {
      const cutoff = Date.now() - CHAT_HISTORY_RETENTION_MS;
      const threads = chatWorkspace.threads.filter((thread) => (
        thread.id === chatWorkspace.activeThreadId ||
        (thread.turns.length > 0 && thread.updatedAt >= cutoff)
      )).map((thread) => ({
        ...thread,
        turns: retainChatHistory(thread.turns).filter((turn) => new Date(turn.createdAt).getTime() >= cutoff),
      }));
      window.localStorage.setItem(conversationStorageKey, JSON.stringify({ ...chatWorkspace, threads }));
      window.localStorage.removeItem(legacyHistoryKey);
      window.sessionStorage.removeItem(legacyHistoryKey);
    } catch {
      // Chat remains usable if browser storage is unavailable.
    }
  }, [conversationStorageKey, chatWorkspace, historyLoadedForKey, legacyHistoryKey]);

  const activeThread = chatWorkspace.threads.find((thread) => thread.id === chatWorkspace.activeThreadId)
    || chatWorkspace.threads[0];
  const conversationTurns = activeThread?.turns || [];
  const learningProgress = activeThread?.learningProgress || learningProgressFromTurns(conversationTurns);
  const setConversationTurns = (updateTurns, threadUpdates = {}) => setChatWorkspace((workspace) => {
    const thread = workspace.threads.find((item) => item.id === workspace.activeThreadId);
    if (!thread) return workspace;
    const turns = typeof updateTurns === 'function' ? updateTurns(thread.turns) : updateTurns;
    return {
      ...workspace,
      threads: workspace.threads.map((item) => item.id === thread.id
        ? { ...item, ...threadUpdates, title: titleForChat(turns), updatedAt: Date.now(), turns }
        : item),
    };
  });

  const startNewChat = () => {
    const thread = createChatThread();
    setChatWorkspace((workspace) => ({
      activeThreadId: thread.id,
      threads: [thread, ...workspace.threads.filter((item) => item.turns.length > 0)],
    }));
    setLastAnswer(null);
    setInputText('');
    setErrorMsg('');
    setDebateData(null);
  };

  const openChat = (threadId) => {
    setChatWorkspace((workspace) => ({ ...workspace, activeThreadId: threadId }));
    setLastAnswer(null);
    setInputText('');
    setErrorMsg('');
    setDebateData(null);
  };

  const historyTurns = (() => {
    const turns = [...conversationTurns];
    const question = lastAnswer?.question;
    const answer = lastAnswer?.message || lastAnswer?.answer;
    if (question && answer) {
      for (let userIndex = turns.length - 2; userIndex >= 0; userIndex -= 1) {
        if (turns[userIndex]?.role === 'user' && turns[userIndex]?.content === question &&
            turns[userIndex + 1]?.role === 'assistant' && turns[userIndex + 1]?.content === answer) {
          turns.splice(userIndex, 2);
          break;
        }
      }
    }
    return turns;
  })();
  useEffect(() => {
    let live = true;
    Promise.all([api.getMemoryRegistry(profile?.persona || 'other'), api.getTwinKnowledge(profile?.user_id || 'demo-alex-rivers')]).then(([registry, knowledge]) => {
      if (!live) return;
      setStarterPrompts(registry.example_prompts || []);
      setDimensionLabels(registry.simulator_labels || {});
      setMemoryCategoryNames(Object.fromEntries((registry.categories || []).map((category) => [category.id, category.title])));
      const counts = { schedule_commitments: knowledge.timetable?.length || 0, deadlines_key_dates: knowledge.deadlines?.length || 0, focus_work_patterns: knowledge.study_history?.length || 0, routines_preferences: knowledge.preferences?.length || 0, goals: knowledge.goals?.length || 0, decision_history: knowledge.decision_history?.length || 0 };
      setLearningCategories(registry.categories.filter((category) => knowledge.active_permissions?.[category.id] && counts[category.id] > 0).map((category) => category.title));
    }).catch(() => {});
    return () => { live = false; };
  }, [api, profile?.user_id, profile?.persona]);

  useEffect(() => {
    if (profile?.weights) setSessionStyleWeights(profile.weights);
  }, [profile?.user_id, profile?.weights]);

  const visibleBlend = sessionStyleWeights || profile?.weights || { rational: 0.5, emotional: 0.25, ambitious: 0.25 };
  const visiblePrimary = ['emotional', 'rational', 'ambitious'].sort((a, b) => (visibleBlend[b] || 0) - (visibleBlend[a] || 0))[0];
  const primaryTwin = lastAnswer?.primary_style || visiblePrimary || profile?.primary_twin || 'rational';

  const nudgeSessionStyle = (style) => {
    const current = sessionStyleWeights || profile?.weights || { rational: 0.5, emotional: 0.25, ambitious: 0.25 };
    const next = { ...current };
    const amount = Math.min(0.1, Math.max(0, 0.3 - sessionStyleChange), Math.max(0, next[style] - 0.05));
    if (!amount) return;
    setSessionStyleChange((total) => total + amount);
    const others = Object.keys(next).filter((item) => item !== style);
    const total = others.reduce((sum, item) => sum + next[item], 0);
    next[style] += amount;
    others.forEach((item) => { next[item] -= amount * next[item] / total; });
    const sum = Object.values(next).reduce((a, b) => a + b, 0);
    setSessionStyleWeights(Object.fromEntries(Object.entries(next).map(([key, value]) => [key, value / sum])));
  };

  const styleColors = {
    rational: '#7C5CFF',
    emotional: '#FF8FA3',
    ambitious: '#C026D3'
  };

  const handleAsk = async (queryText) => {
    const q = (queryText || inputText).trim() || (attachment ? 'Please look at this attachment.' : '');
    if (!q) return;

    const previousLearningProgress = activeThread?.learningProgress || learningProgressFromTurns(conversationTurns);
    const nextProgress = nextLearningProgress(previousLearningProgress, conversationTurns, q);
    const previousAttachmentTurn = [...conversationTurns].reverse().find((turn) => turn.role === 'user' && turn.attachment_id);
    const contextAttachmentId = attachment?.id || previousAttachmentTurn?.attachment_id || null;

    setIsLoading(true);
    setErrorMsg('');
    setVoiceFeedback(null);
    setDecisionFeedback('');
    setChosenAlternative('');
    setShowAlternativeInput(false);
    setDebateData(null);
    const requestStyleWeights = sessionStyleWeights ? Object.fromEntries(
      ['rational', 'emotional', 'ambitious'].map((style) => {
        const value = Number(sessionStyleWeights[style]);
        return [style, Number.isFinite(value) ? value : 1 / 3];
      })
    ) : null;
    const localNow = new Date();
    const localToday = [localNow.getFullYear(), String(localNow.getMonth() + 1).padStart(2, '0'), String(localNow.getDate()).padStart(2, '0')].join('-');

    try {
      const resp = await api.askTwin({
        user_id: profile?.user_id || 'demo-alex-rivers',
        question: q,
        recent_turns: conversationTurns.slice(-CHAT_CONTEXT_TURN_LIMIT).map((turn) => ({
          role: turn.role,
          content: turn.content,
          ...(turn.attachment_id ? { attachment_id: turn.attachment_id } : {}),
        })),
        attachment_id: attachment?.id || null,
        context_attachment_id: contextAttachmentId,
        session_style_weights: requestStyleWeights,
        local_today: localToday,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || ''
      });
      const answerWithQuestion = { ...resp, question: q, attachment_id: attachment?.id || null, attachment_name: attachment?.name || null };
      setLastAnswer(answerWithQuestion);
      const turnTime = Date.now();
      setConversationTurns((turns) => [
        ...turns,
        {
          role: 'user', content: q, createdAt: turnTime,
          ...(attachment ? { attachment_id: attachment.id, attachment_name: attachment.name } : {}),
        },
        { role: 'assistant', content: resp.message || resp.answer, createdAt: turnTime }
      ], { learningProgress: nextProgress });
      setInputText('');
      if (attachment?.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
      setAttachment(null);

    } catch (err) {
      console.error('Ask Echo failed:', err);
      const detail = typeof err?.message === 'string' ? err.message.trim() : '';
      setErrorMsg(detail ? `I couldn’t send that message: ${detail}` : 'Hmm, I lost my train of thought. Try again?');
    } finally {
      setIsLoading(false);
    }
  };

  const recordDecision = async (followedRecommendation, chosenText) => {
    if (!lastAnswer?.recommended_choice || savingDecisionFeedback) return;
    setSavingDecisionFeedback(true);
    try {
      const items = lastAnswer.decision_support?.items || [];
      const style = lastAnswer.primary_style || primaryTwin || 'rational';
      const result = await api.submitFeedback({
        user_id: profile?.user_id || 'demo-alex-rivers',
        question: lastAnswer.question || '',
        options: items.length
          ? items.map((item) => ({ text: `${item.title} (${item.attention_share_pct}% relative priority)`, aligned_twin: style }))
          : [{ text: lastAnswer.recommended_choice, aligned_twin: style }],
        twin_recommended: style,
        option_chosen: chosenText,
        aligned_twin: style,
        followed_recommendation: followedRecommendation,
        decision_only: true,
      });
      const turnTime = Date.now();
      setConversationTurns((turns) => [
        ...turns,
        { role: 'user', content: `I ${followedRecommendation ? 'followed Echo’s recommendation and chose' : 'chose'} ${chosenText}.`, createdAt: turnTime },
        { role: 'assistant', content: 'Got it. I’ll keep that in mind for this chat.', createdAt: turnTime },
      ]);
      if (resp.plan_items_created?.length) window.dispatchEvent(new Event('echo-reminders-refresh'));
      setDecisionFeedback(result?.decision_id
        ? "Got it. I'll use this choice to guide future recommendations."
        : "Decision History is off, so I won't save this choice. You can turn it on in Privacy.");
    } catch {
      setDecisionFeedback("I couldn't save that choice just now. You can try again later.");
    } finally {
      setSavingDecisionFeedback(false);
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const qAnswered = new URLSearchParams(window.location.search).get('answered');
      if (qAnswered === 'true' && !lastAnswer) {
        handleAsk('How should I prioritize two important deadlines this week?');
      }
    }
  }, []);

  useEffect(() => {
    if (pendingQuestion) {
      handleAsk(pendingQuestion);
      if (setPendingQuestion) setPendingQuestion('');
    }
  }, [pendingQuestion]);

  const handleOpenDebateDrawer = async () => {
    setActiveDrawer('debate');
    setErrorMsg('');
    if (debateData || debateLoading) return;

    setDebateLoading(true);
    setDebateError('');
    try {
      const resp = await api.conductDebate({
        user_id: profile?.user_id || 'demo-alex-rivers',
        question: lastAnswer?.question || 'How should I prioritize two important deadlines this week?',
        primary_twin: lastAnswer?.primary_style || primaryTwin,
        first_answer: lastAnswer?.message || lastAnswer?.answer,
        recent_turns: conversationTurns.slice(-12).map(({ role, content }) => ({ role, content }))
      });
      setDebateData(resp);
      setRevealStep(1);
    } catch (err) {
      console.error('Council request failed:', err);
      setDebateError("Couldn't reach the other voices right now, try again?");
    } finally {
      setDebateLoading(false);
    }
  };

  const sortedThreads = [...chatWorkspace.threads].sort((left, right) => right.updatedAt - left.updatedAt);

  return (
    <div className="md:flex w-full min-h-[calc(100vh-4rem)]">
      <aside aria-label="Chat history" className="hidden md:flex md:w-64 md:shrink-0 md:flex-col border-r border-stroke-light dark:border-stroke-dark bg-surface-light/70 dark:bg-surface-dark/70 p-3">
        <button type="button" onClick={startNewChat} disabled={isLoading} className="min-h-11 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-brand-gradient px-3 text-sm font-semibold text-white shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple disabled:opacity-50">
          <Plus className="h-4 w-4" /> New chat
        </button>
        <h2 className="px-2 pt-5 pb-2 text-xs font-semibold uppercase tracking-wide text-content-mutedLight dark:text-content-mutedDark">Chats</h2>
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Saved chats">
          {sortedThreads.map((thread) => (
            <button
              key={thread.id}
              type="button"
              onClick={() => openChat(thread.id)}
              disabled={isLoading}
              aria-current={thread.id === activeThread?.id ? 'page' : undefined}
              title={thread.title}
              className={`min-h-11 w-full inline-flex items-center gap-2 rounded-xl px-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple ${thread.id === activeThread?.id ? 'bg-brand-purple/10 text-brand-purple dark:text-[#C5B8FF] font-semibold' : 'text-content-mainLight dark:text-content-mainDark hover:bg-brand-purple/5'}`}
            >
              <MessageSquare className="h-4 w-4 shrink-0 opacity-70" />
              <span className="truncate">{thread.title}</span>
            </button>
          ))}
        </nav>
        <p className="px-2 pt-3 text-[11px] leading-relaxed text-content-mutedLight dark:text-content-mutedDark">Chats are saved on this device for 14 days.</p>
      </aside>

      <div className="min-w-0 flex-1">
        <nav aria-label="Chats" className="md:hidden flex items-center gap-2 overflow-x-auto border-b border-stroke-light dark:border-stroke-dark bg-surface-light/70 dark:bg-surface-dark/70 p-2">
          <button type="button" onClick={startNewChat} disabled={isLoading} className="min-h-11 shrink-0 inline-flex items-center gap-1.5 rounded-full bg-brand-gradient px-4 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple disabled:opacity-50">
            <Plus className="h-4 w-4" /> New chat
          </button>
          {sortedThreads.map((thread) => (
            <button key={thread.id} type="button" onClick={() => openChat(thread.id)} disabled={isLoading} aria-current={thread.id === activeThread?.id ? 'page' : undefined} title={thread.title} className={`min-h-11 max-w-48 shrink-0 truncate rounded-full border px-4 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple disabled:opacity-50 ${thread.id === activeThread?.id ? 'border-brand-purple/50 bg-brand-purple/10 text-brand-purple dark:text-[#C5B8FF] font-semibold' : 'border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark'}`}>
              {thread.title}
            </button>
          ))}
        </nav>

      <div className="max-w-3xl mx-auto px-4 py-4 pb-44 md:pb-28 space-y-6">
      {/* EMPTY STATE: When no question asked yet */}
      {!lastAnswer && !isLoading && (
        <div className="py-12 sm:py-20 text-center space-y-6 animate-fadeIn">
          <div className="flex justify-center">
            <EchoOrb size="lg" style={primaryTwin} state="idle" title={twinName} />
          </div>

          <div className="max-w-lg mx-auto p-4 rounded-2xl bg-brand-purple/5 border border-brand-purple/20 text-left">
            <h3 className="text-sm font-bold">Here's what I know so far</h3>
            <p className="mt-1 text-xs text-content-mutedLight dark:text-content-mutedDark">I'm still learning from the information you choose to share.</p>
            <p className="mt-2 text-xs">{learningCategories.length ? `Available to use: ${learningCategories.join(', ')}.` : 'No saved details are available yet. You can share only what feels useful.'}</p>
          </div>

          <div className="space-y-2 max-w-md mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold font-heading text-content-mainLight dark:text-content-mainDark">
              Hey {profile?.name ? profile.name.split(' ')[0] : 'there'}! What's on your mind?
            </h2>
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark leading-relaxed">
              {twinName} is using a <strong className="capitalize" style={{ color: styleColors[primaryTwin] }}>{primaryTwin}</strong> style. Whenever you're facing a tough choice or tight deadline, ask below or try a starter:
            </p>
          </div>

          {/* Starter Chips */}
          <div className="flex flex-col sm:flex-row flex-wrap items-center justify-center gap-2.5 pt-2">
            {starterPrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleAsk(prompt)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-full bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-xs font-semibold text-content-mainLight dark:text-content-mainDark hover:border-brand-purple hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark shadow-sm transition flex items-center space-x-2"
              >
                <span>âœ¨</span>
                <span>{prompt}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {learningProgress?.active && (
        <section aria-label="Learning progress" className="rounded-2xl border border-brand-purple/20 bg-brand-purple/5 px-4 py-3">
          <div className="mb-2 flex items-center justify-between gap-3 text-xs">
            <span className="font-semibold text-content-mainLight dark:text-content-mainDark">Learning together</span>
            <span className="text-content-mutedLight dark:text-content-mutedDark">{Math.min(learningProgress.answered, learningProgress.target)} of {learningProgress.target} questions answered</span>
          </div>
          <div
            role="progressbar"
            aria-label="Practice questions answered"
            aria-valuemin={0}
            aria-valuemax={learningProgress.target}
            aria-valuenow={Math.min(learningProgress.answered, learningProgress.target)}
            className="h-2 overflow-hidden rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark"
          >
            <div className="h-full rounded-full bg-brand-gradient transition-[width] duration-300" style={{ width: `${Math.min(100, learningProgress.answered / learningProgress.target * 100)}%` }} />
          </div>
        </section>
      )}

      {historyTurns.length > 0 && (
        <section aria-label="Previous messages" className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-content-mutedLight dark:text-content-mutedDark">Messages in this chat</h2>
          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">Chat history stays on this device for 14 days. Details saved to permitted memory categories stay until you remove them in Privacy.</p>
          <div role="log" aria-live="off" className="space-y-4">
            {historyTurns.map((turn, index) => turn.role === 'user' ? (
              <div key={`${index}-${turn.role}`} className="flex justify-end">
                <div className="max-w-[85%] sm:max-w-md rounded-3xl rounded-tr-md bg-brand-purple px-4 py-3 text-sm font-medium leading-relaxed text-white">
                  {turn.attachment_name && <span className="mb-2 flex items-center gap-1.5 text-xs text-white/80"><FileText className="h-3.5 w-3.5" />{turn.attachment_name}</span>}
                  <p className="whitespace-pre-line">{turn.content}</p>
                </div>
              </div>
            ) : (
              <div key={`${index}-${turn.role}`} className="flex items-start gap-3">
                <EchoOrb size="sm" style={primaryTwin} state="idle" title={twinName} />
                <p className="max-w-[90%] whitespace-pre-line rounded-2xl rounded-tl-md border border-stroke-light bg-surface-light px-4 py-3 text-sm leading-relaxed text-content-mainLight dark:border-stroke-dark dark:bg-surface-dark dark:text-content-mainDark">{turn.content}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* SKELETON LOADER while waiting for answer */}
      {isLoading && (
        <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4 animate-fadeIn">
          <div className="flex items-center space-x-3">
            <EchoOrb size="sm" style={primaryTwin} state="thinking" title={twinName} />
            <span className="text-xs font-semibold text-brand-purple dark:text-[#A894FF]">
              {twinName} is thinking this through...
            </span>
          </div>
          <SkeletonLoader lines={4} />
        </div>
      )}

      {/* ERROR NOTICE */}
      {errorMsg && (
        <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-xs font-medium flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* CHAT MESSAGES STREAM */}
      {lastAnswer && !isLoading && (
        <div className="space-y-5 animate-fadeIn">
          {/* User Message Bubble */}
          <div className="flex justify-end">
            <div className="max-w-[85%] sm:max-w-md rounded-3xl rounded-tr-md bg-brand-purple p-4 text-sm font-medium leading-relaxed text-white shadow-md">
              {lastAnswer.attachment_name && <span className="mb-2 flex items-center gap-1.5 text-xs text-white/80"><FileText className="h-3.5 w-3.5" />{lastAnswer.attachment_name}</span>}
              <p className="whitespace-pre-line">{lastAnswer.question}</p>
            </div>
          </div>

          {/* Echo Card */}
          <div className="p-6 sm:p-7 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-5">
            {/* Header: Orb + Style Dot Badge */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <EchoOrb size="sm" style={lastAnswer.twin_type || primaryTwin} state="idle" title={twinName} />
                <div>
                  <div className="flex items-center space-x-1.5">
                    <span className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                      {twinName}
                    </span>
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: styleColors[lastAnswer.twin_type || primaryTwin] }}
                    />
                  </div>
                  <span className="text-xs text-content-mutedLight dark:text-content-mutedDark font-medium">
                    {(lastAnswer.twin_type || primaryTwin)} style
                  </span>
                </div>
              </div>
            </div>

            {lastAnswer.provider_status === 'offline' && (
              <p role="status" className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-xs text-content-mutedLight dark:text-content-mutedDark">
                Gemini isn’t reachable right now, so this reply was made locally from the details you shared.
              </p>
            )}

            {/* Echo's conversational reply. Analytics live in the Why drawer. */}
            <div className="text-base text-content-mainLight dark:text-content-mainDark leading-relaxed whitespace-pre-line">
              {lastAnswer.message || lastAnswer.answer}
            </div>
            {lastAnswer.memories_saved?.length > 0 && (
              <p role="status" className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                I’ll remember this under {lastAnswer.memories_saved.map((category) => memoryCategoryNames[category] || category.replaceAll('_', ' ')).join(', ')}. You can review or remove it in My Twin.
              </p>
            )}
        {lastAnswer.recommended_choice && lastAnswer.intent === 'decision_question' && !lastAnswer.is_crisis_response && (
              <section className="border-t border-stroke-light dark:border-stroke-dark pt-4 space-y-3" aria-label="Decision follow-up">
                <p className="text-sm font-semibold text-content-mainLight dark:text-content-mainDark">What did you end up doing?</p>
                {decisionFeedback ? <p className="text-sm text-content-mutedLight dark:text-content-mutedDark" role="status">{decisionFeedback}</p> : (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" disabled={savingDecisionFeedback} onClick={() => {
                      recordDecision(true, lastAnswer.recommended_choice);
                    }} className="min-h-11 rounded-full bg-brand-gradient px-4 text-sm font-semibold text-white disabled:opacity-60">I followed Echo’s recommendation</button>
                    <button type="button" disabled={savingDecisionFeedback} onClick={() => setShowAlternativeInput(true)} className="min-h-11 rounded-full border border-stroke-light dark:border-stroke-dark px-4 text-sm font-medium disabled:opacity-60">I chose something else</button>
                  </div>
                )}
                {!decisionFeedback && showAlternativeInput && (
                  <form className="flex flex-col sm:flex-row gap-2" onSubmit={(event) => { event.preventDefault(); const choice = chosenAlternative.trim(); if (choice) recordDecision(false, choice); }}>
                    <label className="sr-only" htmlFor="actual-choice">What did you choose?</label>
                    <input id="actual-choice" value={chosenAlternative} onChange={(event) => setChosenAlternative(event.target.value)} maxLength={300} placeholder="What did you choose?" className="min-h-11 flex-1 rounded-xl border border-stroke-light dark:border-stroke-dark bg-transparent px-3 text-sm" />
                    <button type="submit" disabled={!chosenAlternative.trim() || savingDecisionFeedback} className="min-h-11 rounded-full border border-brand-purple/40 px-4 text-sm font-semibold text-brand-purple disabled:opacity-50">Save my choice</button>
                  </form>
                )}
              </section>
            )}
            {lastAnswer.lookup_sources?.length > 0 && (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-content-mutedLight dark:text-content-mutedDark" aria-label="Live information sources">
                <span>Sources:</span>
                {lastAnswer.lookup_sources.slice(0, 3).map((source) => (
                  <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="min-h-11 inline-flex items-center underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple rounded">
                    {source.title}
                  </a>
                ))}
              </div>
            )}

            {lastAnswer.show_other_voices && !lastAnswer.is_crisis_response && <button type="button" onClick={handleOpenDebateDrawer} className="min-h-11 inline-flex items-center gap-2 rounded-full border border-brand-purple/30 bg-brand-purple/5 px-4 text-sm font-medium text-brand-purple dark:text-[#C5B8FF] hover:bg-brand-purple/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple"><Scale className="h-4 w-4" />Hear the other voices</button>}

            {lastAnswer.attachment_looks_like_schedule && lastAnswer.extracted_items?.length > 0 && (
              <div className="rounded-lg border border-brand-purple/30 bg-brand-purple/5 p-4 space-y-3">
                <div>
                  <p className="text-sm font-bold text-content-mainLight dark:text-content-mainDark">I found a possible schedule</p>
                  <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">Check these before adding them. Nothing is saved yet.</p>
                </div>
                <div className="space-y-2">
                  {lastAnswer.extracted_items.map((item, index) => (
                    <div key={`${item.title}-${index}`} className="text-xs text-content-mainLight dark:text-content-mainDark">
                      <span className="font-semibold">{item.title}</span>{item.day ? `, ${item.day}` : ''}{item.start_time ? ` ${item.start_time}` : ''}{item.end_time ? ` to ${item.end_time}` : ''}
                    </div>
                  ))}
                </div>
                {extractionStatus ? <p className="text-xs font-medium text-brand-purple" aria-live="polite">{extractionStatus}</p> : (
                  <div className="flex gap-2">
                    <button type="button" onClick={async () => {
                      try {
                        const result = await api.confirmExtractedItems(profile?.user_id || 'demo-alex-rivers', lastAnswer.attachment_id, lastAnswer.extracted_items);
                        setExtractionStatus(result.message);
                      } catch { setExtractionStatus("Hmm, I couldn't save those. Try again?"); }
                    }} className="min-h-11 px-4 rounded-full bg-brand-gradient text-white text-xs font-bold">Add to schedule</button>
                    <button type="button" onClick={() => setExtractionStatus('Okay, nothing was saved.')} className="min-h-11 px-4 rounded-full border border-stroke-light dark:border-stroke-dark text-xs font-semibold">Not now</button>
                  </div>
                )}
              </div>
            )}

            {(lastAnswer.is_crisis_response || lastAnswer.show_safety_resources) && lastAnswer.crisis_resources?.length > 0 && (
              <div className="space-y-3 border-t border-rose-300/60 dark:border-rose-800/70 pt-4" role="region" aria-label="Crisis support resources">
                <div className="flex items-center gap-2 text-sm font-semibold text-rose-700 dark:text-rose-300">
                  <PhoneCall className="h-4 w-4" />
                  <span>Talk to someone now</span>
                </div>
                <div className="space-y-2">
                  {lastAnswer.crisis_resources.map((resource) => {
                    const isExternal = resource.url.startsWith('http');
                    return (
                      <a
                        key={resource.name}
                        href={resource.url}
                        target={isExternal ? '_blank' : undefined}
                        rel={isExternal ? 'noreferrer' : undefined}
                        className="min-h-11 flex items-center justify-between gap-4 rounded-lg border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/20 p-3 transition hover:border-rose-400"
                      >
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold text-content-mainLight dark:text-content-mainDark">{resource.name}</span>
                          <span className="block text-xs text-content-mutedLight dark:text-content-mutedDark">{resource.description}</span>
                        </span>
                        <span className="flex flex-shrink-0 items-center gap-1 text-xs font-semibold text-rose-700 dark:text-rose-300">
                          {resource.contact}
                          {isExternal && <ExternalLink className="h-3.5 w-3.5" />}
                        </span>
                      </a>
                    );
                  })}
                </div>
                <div className="flex flex-wrap gap-2">
                  {lastAnswer.crisis_resources.some((resource) => resource.number) && (
                    <a href={`tel:${(lastAnswer.crisis_resources.find((resource) => resource.type === 'emergency') || lastAnswer.crisis_resources.find((resource) => resource.number))?.number?.replace(/[^\d+]/g, '')}`} className="min-h-11 inline-flex items-center rounded-full bg-rose-700 px-4 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500">Call now</a>
                  )}
                  {lastAnswer.crisis_resources.some((resource) => resource.message_number) && (
                    <a href={`sms:${lastAnswer.crisis_resources.find((resource) => resource.message_number).message_number}`} className="min-h-11 inline-flex items-center rounded-full border border-rose-400 px-4 text-sm font-semibold text-rose-800 dark:text-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500">Message a helpline</a>
                  )}
                  {typeof navigator !== 'undefined' && navigator.share && (
                    <button type="button" onClick={() => navigator.share({ text: 'Could you stay with me or call me? I could use some support right now.' }).catch(() => {})} className="min-h-11 inline-flex items-center rounded-full border border-rose-400 px-4 text-sm font-semibold text-rose-800 dark:text-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500">Reach someone I trust</button>
                  )}
                </div>
              </div>
            )}


          </div>
        </div>
      )}

      <ChatComposer
        api={api}
        userId={profile?.user_id || 'demo-alex-rivers'}
        twinName={twinName}
        value={inputText}
        onChange={setInputText}
        onSend={() => handleAsk()}
        isLoading={isLoading}
        attachment={attachment}
        setAttachment={setAttachment}
      />

      {/* Optional explanation and technical details */}
      <SlideUpDrawer
        isOpen={activeDrawer === 'why'}
        onClose={() => setActiveDrawer(null)}
        title="Why this suggestion?"
        subtitle="A little context behind these options."
      >
        {lastAnswer?.ml_insights ? (
          <div className="space-y-4">
            <p className="text-sm text-content-mainLight dark:text-content-mainDark">{lastAnswer.why_summary || "I kept the priorities you shared in mind and left room to pause between them."}</p>
            <details className="rounded-xl border border-stroke-light dark:border-stroke-dark p-4">
              <summary className="cursor-pointer min-h-11 flex items-center text-sm font-semibold text-brand-purple dark:text-[#A894FF]">Show details</summary>
              <div className="space-y-6 pt-3">
            {lastAnswer.deadline_risk_alert && (
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 text-sm text-amber-800 dark:text-amber-200">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="font-bold uppercase tracking-wider block text-[11px] text-amber-600 dark:text-amber-400">
                    Schedule Conflict
                  </span>
                  <p className="leading-relaxed">{lastAnswer.deadline_risk_alert}</p>
                </div>
              </div>
            )}

            {/* 2 Big Indicator Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-1">
                <span className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
                  On-Time Completion Likelihood
                </span>
                <div className="text-3xl font-extrabold font-heading text-brand-purple dark:text-[#A894FF]">
                  {Math.round(lastAnswer.ml_insights.on_time_probability * 100)}%
                </div>
                <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                  Shared starter model trained on synthetic task data; not trained on your personal history.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-1">
                <span className="text-xs font-semibold text-content-mutedLight dark:text-content-mutedDark uppercase tracking-wider">
                  Predicted Effort Required
                </span>
                <div className="text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
                  {lastAnswer.ml_insights.predicted_hours} hrs
                </div>
                <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                  Includes ~1.5x realistic estimation overhead.
                </p>
              </div>
            </div>

            {/* Optional technical details */}
            {lastAnswer.ml_insights.why_factors?.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Info className="w-4 h-4 text-brand-purple" />
                  <h4 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                    What influenced the estimate
                  </h4>
                </div>
                <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                  These details are estimates, not promises.
                </p>

                <div className="space-y-2.5">
                  {lastAnswer.ml_insights.why_factors.map((feat, idx) => {
                    const pct = Math.round(feat.importance_pct);
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between text-xs font-medium">
                          <span className="text-content-mainLight dark:text-content-mainDark">
                            {feat.feature.replace(/_/g, ' ')}
                          </span>
                          <span className="text-content-mutedLight dark:text-content-mutedDark font-mono">
                            {pct}%
                          </span>
                        </div>
                        {feat.impact && (
                          <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
                            {feat.impact}
                          </p>
                        )}
                        <div className="h-2 rounded-full bg-surface-subtleLight dark:bg-surface-subtleDark overflow-hidden">
                          <div
                            className="h-full rounded-full bg-brand-gradient transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
              </div>
            </details>
          </div>
        ) : (
          <p className="text-sm text-content-mutedLight dark:text-content-mutedDark py-4">
            No predictive metrics generated for this query.
          </p>
        )}
      </SlideUpDrawer>

      {/* DRAWER 2: PERSONAL STYLE BLEND */}
      <SlideUpDrawer
        isOpen={activeDrawer === 'debate'}
        onClose={() => setActiveDrawer(null)}
        title="Hear the other voices"
        subtitle="Three caring ways to think it through. You’re always in charge."
        badge="Heart · Head · Drive"
        maxWidth="max-w-3xl"
      >
        {debateLoading && <div className="py-10 text-center text-sm text-content-mutedLight dark:text-content-mutedDark">Bringing the voices together…</div>}
        {!debateLoading && !debateData && <p className="py-6 text-sm text-content-mutedLight dark:text-content-mutedDark">{debateError || errorMsg || "Couldn't reach the other voices right now, try again?"}</p>}
        {!debateLoading && debateData && debateData.voices?.length === 0 && <p className="py-6 text-sm text-content-mutedLight dark:text-content-mutedDark">{debateData.closing_line}</p>}
        {!debateLoading && debateData?.voices?.length > 0 && <div className="space-y-4">
          {debateData.voices.map((voice) => {
            const labels = { emotional: 'Heart', rational: 'Head', ambitious: 'Drive' };
            const icons = { emotional: Heart, rational: Brain, ambitious: Rocket };
            const Icon = icons[voice.style] || Sparkles;
            return <article key={voice.style} className="rounded-2xl border border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark p-4 space-y-2">
              <div className="flex items-center gap-2" style={{ color: styleColors[voice.style] }}><Icon className="h-4 w-4" /><h3 className="text-sm font-bold">{labels[voice.style]} <span className="font-normal text-content-mutedLight dark:text-content-mutedDark">({voice.style})</span></h3>{voice.your_usual_voice && <span className="ml-auto rounded-full bg-brand-purple/10 px-2 py-1 text-[11px] font-semibold text-brand-purple">Your usual voice</span>}</div>
              <p className="text-sm leading-relaxed text-content-mainLight dark:text-content-mainDark">{voice.argument}</p>
            </article>;
          })}
          <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">{debateData.closing_line || "It's your call, and I'm with you either way."}</p>
          <div className="border-t border-stroke-light dark:border-stroke-dark pt-3 space-y-2">
            <p className="text-sm font-medium">Which one feels most like you?</p>
            <div className="flex flex-wrap gap-2">{[['emotional','Heart'],['rational','Head'],['ambitious','Drive']].map(([style,label]) => <button key={style} type="button" disabled={!!voiceFeedback} onClick={async () => {
              try {
                const saved = await api.submitFeedback({ user_id: profile?.user_id || 'demo-alex-rivers', question: lastAnswer?.question || '', options: debateData.voices.map(v => ({ text: v.argument, style: v.style })), twin_recommended: lastAnswer?.primary_style || primaryTwin, option_chosen: label, aligned_twin: style, followed_recommendation: true, feedback_comment: 'style_signal:strong' });
                if (!saved?.decision_id) nudgeSessionStyle(style);
                setVoiceFeedback(saved?.decision_id ? `Thanks, I’ll remember that voice.` : `Thanks. I’ll keep that in mind in this chat only while Decision History is off.`);
              } catch { setVoiceFeedback('Thanks for telling me.'); }
            }} className="min-h-11 rounded-full border border-brand-purple/30 px-4 text-sm disabled:opacity-60">{label}</button>)}<button type="button" disabled={!!voiceFeedback} onClick={() => setVoiceFeedback('No problem — you don’t need to choose one.')} className="min-h-11 rounded-full border border-stroke-light dark:border-stroke-dark px-4 text-sm">None</button></div>
            {voiceFeedback && <p role="status" className="text-xs text-content-mutedLight dark:text-content-mutedDark">{voiceFeedback}</p>}
          </div>
        </div>}
      </SlideUpDrawer>

      </div>
      </div>
    </div>
  );
}
