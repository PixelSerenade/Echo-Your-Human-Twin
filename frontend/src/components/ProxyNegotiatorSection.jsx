import React, { useState, useEffect } from 'react';
import {
  Calendar, Shield, Clock, AlertTriangle, CheckCircle, XCircle,
  MessageSquare, Plus, Trash2, Copy, Send, Sparkles, UserCheck, RefreshCw
} from 'lucide-react';

export default function ProxyNegotiatorSection({ api, userId = 'demo-user-alex', twinName = 'Echo', primaryTwin = 'rational' }) {
  const [negotiations, setNegotiations] = useState([]);
  const [focusBlocks, setFocusBlocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [statusMsg, setStatusMsg] = useState('');

  // Form State
  const [title, setTitle] = useState('');
  const [requestedBy, setRequestedBy] = useState('');
  const [proposedStartTime, setProposedStartTime] = useState('');
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [priority, setPriority] = useState('medium');
  const [latestEvaluation, setLatestEvaluation] = useState(null);

  // Focus Block Form State
  const [showAddBlock, setShowAddBlock] = useState(false);
  const [blockTitle, setBlockTitle] = useState('');
  const [blockDay, setBlockDay] = useState('Wednesday');
  const [blockStart, setBlockStart] = useState('09:00');
  const [blockEnd, setBlockEnd] = useState('12:00');

  useEffect(() => {
    // Set default tomorrow date at 10 AM
    const tmr = new Date();
    tmr.setDate(tmr.getDate() + 1);
    tmr.setHours(10, 0, 0, 0);
    setProposedStartTime(tmr.toISOString().slice(0, 16));

    fetchData();
  }, [userId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [negs, fbs] = await Promise.all([
        api.listProxyNegotiations(userId).catch(() => []),
        api.listFocusBlocks(userId).catch(() => [])
      ]);
      setNegotiations(Array.isArray(negs) ? negs : []);
      setFocusBlocks(Array.isArray(fbs) ? fbs : []);
    } catch (err) {
      console.error('Failed to fetch proxy data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handlePresetSample = (preset) => {
    if (preset === 'architecture') {
      setTitle('Cloud Architecture Sync Meeting');
      setRequestedBy('Prof. Smith');
      setPriority('high');
      setDurationMinutes(60);
    } else if (preset === 'client') {
      setTitle('Client Milestone Review');
      setRequestedBy('Lead Architect Alex');
      setPriority('medium');
      setDurationMinutes(90);
    }
  };

  const handleEvaluate = async (e) => {
    if (e) e.preventDefault();
    if (!title || !requestedBy || !proposedStartTime) {
      setStatusMsg('Please fill in title, requester, and proposed time.');
      return;
    }

    setEvaluating(true);
    setStatusMsg('');
    try {
      const result = await api.evaluateProxyNegotiation({
        user_id: userId,
        title,
        requested_by: requestedBy,
        duration_minutes: parseInt(durationMinutes, 10),
        proposed_start_time: new Date(proposedStartTime).toISOString(),
        priority
      });
      setLatestEvaluation(result);
      setStatusMsg('Twin Proxy successfully evaluated the incoming proposal!');
      fetchData();
    } catch (err) {
      console.error(err);
      setStatusMsg('Evaluation failed. Please try again.');
    } finally {
      setEvaluating(false);
    }
  };

  const handleAction = async (id, action) => {
    try {
      await api.actionProxyNegotiation(id, action, userId);
      setStatusMsg(`Proposal ${action}ed!`);
      if (latestEvaluation && latestEvaluation.id === id) {
        setLatestEvaluation(prev => prev ? { ...prev, status: action === 'accept' ? 'accepted' : (action === 'counter' ? 'countered' : 'declined') } : null);
      }
      fetchData();
    } catch (err) {
      console.error(err);
      setStatusMsg(`Failed to ${action} proposal.`);
    }
  };

  const handleAddFocusBlock = async (e) => {
    e.preventDefault();
    if (!blockTitle) return;
    try {
      await api.createFocusBlock({
        user_id: userId,
        title: blockTitle,
        day_of_week: blockDay,
        start_time: blockStart,
        end_time: blockEnd,
        is_protected: true
      });
      setBlockTitle('');
      setShowAddBlock(false);
      setStatusMsg('Protected deep work focus block added!');
      fetchData();
    } catch (err) {
      console.error(err);
      setStatusMsg('Failed to add focus block.');
    }
  };

  const handleDeleteFocusBlock = async (id) => {
    try {
      await api.deleteFocusBlock(id, userId);
      setStatusMsg('Focus block removed.');
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {/* HEADER BANNER */}
      <div className="bg-gradient-to-r from-purple-900/40 via-indigo-900/40 to-slate-900/40 p-6 rounded-2xl border border-brand-purple/30 backdrop-blur-md">
        <div className="flex items-center space-x-3 mb-2">
          <div className="p-2.5 bg-brand-purple/20 rounded-xl text-brand-purple">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
              {twinName} Proxy & Negotiator
            </h1>
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">
              Autonomous calendar proxy that evaluates schedule density, protected focus blocks, and ML deadline risk to negotiate optimal times.
            </p>
          </div>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 bg-brand-purple/10 border border-brand-purple/30 rounded-xl text-xs font-semibold text-brand-purple flex items-center justify-between">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg('')} className="hover:opacity-80">✕</button>
        </div>
      )}

      {/* GRID LAYOUT: FORM & EVALUATION RESULT */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* INPUT FORM: SIMULATE INCOMING REQUEST */}
        <div className="bg-surface-light dark:bg-surface-dark p-6 rounded-2xl border border-stroke-light dark:border-stroke-dark shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-brand-purple" />
              <span>Simulate Incoming Request</span>
            </h2>
            <div className="flex space-x-1">
              <button
                type="button"
                onClick={() => handlePresetSample('architecture')}
                className="px-2 py-1 text-[10px] font-semibold bg-surface-subtleLight dark:bg-surface-subtleDark hover:bg-brand-purple/20 text-content-mutedLight dark:text-content-mutedDark rounded-md transition"
              >
                Sample 1
              </button>
              <button
                type="button"
                onClick={() => handlePresetSample('client')}
                className="px-2 py-1 text-[10px] font-semibold bg-surface-subtleLight dark:bg-surface-subtleDark hover:bg-brand-purple/20 text-content-mutedLight dark:text-content-mutedDark rounded-md transition"
              >
                Sample 2
              </button>
            </div>
          </div>

          <form onSubmit={handleEvaluate} className="space-y-3 text-xs">
            <div>
              <label className="block text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark mb-1">
                Meeting / Task Title
              </label>
              <input
                type="text"
                placeholder="e.g. Cloud Architecture Sync"
                value={title}
                onChange={e => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark focus:outline-none focus:ring-2 focus:ring-brand-purple"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark mb-1">
                Requested By (Person / Org)
              </label>
              <input
                type="text"
                placeholder="e.g. Prof. Smith"
                value={requestedBy}
                onChange={e => setRequestedBy(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark focus:outline-none focus:ring-2 focus:ring-brand-purple"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark mb-1">
                  Proposed Start Time
                </label>
                <input
                  type="datetime-local"
                  value={proposedStartTime}
                  onChange={e => setProposedStartTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark focus:outline-none focus:ring-2 focus:ring-brand-purple"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark mb-1">
                  Duration (Minutes)
                </label>
                <select
                  value={durationMinutes}
                  onChange={e => setDurationMinutes(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark focus:outline-none focus:ring-2 focus:ring-brand-purple"
                >
                  <option value={30}>30 mins</option>
                  <option value={60}>60 mins</option>
                  <option value={90}>90 mins</option>
                  <option value={120}>120 mins</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-content-mutedLight dark:text-content-mutedDark mb-1">
                Priority Level
              </label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark focus:outline-none focus:ring-2 focus:ring-brand-purple"
              >
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
                <option value="critical">Critical / Urgent</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={evaluating}
              className="w-full py-2.5 px-4 bg-brand-purple hover:bg-brand-purple/90 text-white rounded-xl font-bold transition flex items-center justify-center space-x-2 shadow-md disabled:opacity-50"
            >
              {evaluating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Evaluating Risk & Focus Blocks...</span>
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  <span>Evaluate with Twin Proxy</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* EVALUATION RESULT DISPLAY */}
        <div className="bg-surface-light dark:bg-surface-dark p-6 rounded-2xl border border-stroke-light dark:border-stroke-dark shadow-sm flex flex-col justify-between space-y-4">
          <div>
            <h2 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark flex items-center space-x-2 mb-3">
              <MessageSquare className="w-4 h-4 text-brand-purple" />
              <span>Proxy Evaluation Result</span>
            </h2>

            {!latestEvaluation ? (
              <div className="text-center py-12 text-content-mutedLight dark:text-content-mutedDark text-xs space-y-2">
                <Calendar className="w-8 h-8 mx-auto opacity-40" />
                <p>Fill out the form on the left and click <strong>Evaluate with Twin Proxy</strong> to test automated schedule negotiation.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* STATUS BADGE */}
                <div className={`p-3 rounded-xl border flex items-center justify-between ${
                  latestEvaluation.conflict_detected
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-500'
                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500'
                }`}>
                  <div className="flex items-center space-x-2 text-xs font-bold">
                    {latestEvaluation.conflict_detected ? (
                      <AlertTriangle className="w-4 h-4" />
                    ) : (
                      <CheckCircle className="w-4 h-4" />
                    )}
                    <span>
                      {latestEvaluation.conflict_detected ? 'Schedule Conflict / High Risk' : 'Auto-Approved (Safe)'}
                    </span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider font-extrabold bg-surface-dark/40">
                    {latestEvaluation.status}
                  </span>
                </div>

                {/* CONFLICT REASON */}
                {latestEvaluation.conflict_reason && (
                  <div className="p-3 bg-surface-subtleLight dark:bg-surface-subtleDark rounded-xl text-xs space-y-1">
                    <span className="font-bold text-amber-500 block">Conflict Analysis:</span>
                    <p className="text-content-mutedLight dark:text-content-mutedDark">{latestEvaluation.conflict_reason}</p>
                  </div>
                )}

                {/* DRAFT RESPONSE MESSAGE */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-bold text-content-mutedLight dark:text-content-mutedDark">
                    <span>Twin Proxy Draft Response:</span>
                    <button
                      onClick={() => copyToClipboard(latestEvaluation.negotiation_message, latestEvaluation.id)}
                      className="flex items-center space-x-1 text-brand-purple hover:underline"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedId === latestEvaluation.id ? 'Copied!' : 'Copy'}</span>
                    </button>
                  </div>
                  <div className="p-3 bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark rounded-xl text-xs text-content-mainLight dark:text-content-mainDark whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
                    {latestEvaluation.negotiation_message}
                  </div>
                </div>

                {/* ACTION BUTTONS */}
                <div className="flex space-x-2 pt-2">
                  <button
                    onClick={() => handleAction(latestEvaluation.id, 'accept')}
                    disabled={latestEvaluation.status === 'accepted'}
                    className="flex-1 py-1.5 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1 disabled:opacity-40"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span>Accept</span>
                  </button>
                  <button
                    onClick={() => handleAction(latestEvaluation.id, 'counter')}
                    disabled={latestEvaluation.status === 'countered'}
                    className="flex-1 py-1.5 px-3 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1 disabled:opacity-40"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send Counter</span>
                  </button>
                  <button
                    onClick={() => handleAction(latestEvaluation.id, 'decline')}
                    disabled={latestEvaluation.status === 'declined'}
                    className="flex-1 py-1.5 px-3 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1 disabled:opacity-40"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Decline</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* PROTECTED FOCUS BLOCKS & HISTORY */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* PROTECTED DEEP WORK FOCUS BLOCKS */}
        <div className="bg-surface-light dark:bg-surface-dark p-6 rounded-2xl border border-stroke-light dark:border-stroke-dark shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark flex items-center space-x-2">
              <Shield className="w-4 h-4 text-brand-purple" />
              <span>Protected Deep Work Focus Blocks</span>
            </h2>
            <button
              onClick={() => setShowAddBlock(!showAddBlock)}
              className="px-2.5 py-1 text-xs font-semibold bg-brand-purple text-white rounded-lg flex items-center space-x-1 hover:bg-brand-purple/90 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Block</span>
            </button>
          </div>

          {showAddBlock && (
            <form onSubmit={handleAddFocusBlock} className="p-3 bg-surface-subtleLight dark:bg-surface-subtleDark rounded-xl border border-stroke-light dark:border-stroke-dark space-y-2 text-xs">
              <input
                type="text"
                placeholder="Block Name (e.g. Thesis Research)"
                value={blockTitle}
                onChange={e => setBlockTitle(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark text-content-mainLight dark:text-content-mainDark"
                required
              />
              <div className="grid grid-cols-3 gap-2">
                <select
                  value={blockDay}
                  onChange={e => setBlockDay(e.target.value)}
                  className="px-2 py-1.5 rounded-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark"
                >
                  {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
                <input
                  type="time"
                  value={blockStart}
                  onChange={e => setBlockStart(e.target.value)}
                  className="px-2 py-1.5 rounded-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark"
                />
                <input
                  type="time"
                  value={blockEnd}
                  onChange={e => setBlockEnd(e.target.value)}
                  className="px-2 py-1.5 rounded-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddBlock(false)}
                  className="px-2.5 py-1 text-xs text-content-mutedLight dark:text-content-mutedDark hover:underline"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 bg-brand-purple text-white rounded-lg font-bold"
                >
                  Save Focus Block
                </button>
              </div>
            </form>
          )}

          {focusBlocks.length === 0 ? (
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark py-4 text-center">
              No focus blocks configured. Add deep work blocks to protect uninterrupted focus hours.
            </p>
          ) : (
            <div className="space-y-2">
              {focusBlocks.map(fb => (
                <div
                  key={fb.id}
                  className="p-3 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-bold text-content-mainLight dark:text-content-mainDark block">{fb.title}</span>
                    <span className="text-[11px] text-content-mutedLight dark:text-content-mutedDark flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{fb.day_of_week}: {fb.start_time} - {fb.end_time}</span>
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteFocusBlock(fb.id)}
                    className="p-1.5 text-rose-500 hover:bg-rose-500/10 rounded-lg transition"
                    title="Delete Focus Block"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* PAST NEGOTIATION AUDIT HISTORY */}
        <div className="bg-surface-light dark:bg-surface-dark p-6 rounded-2xl border border-stroke-light dark:border-stroke-dark shadow-sm space-y-4">
          <h2 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark flex items-center space-x-2">
            <Clock className="w-4 h-4 text-brand-purple" />
            <span>Negotiation History Log</span>
          </h2>

          {negotiations.length === 0 ? (
            <p className="text-xs text-content-mutedLight dark:text-content-mutedDark py-4 text-center">
              No recent proxy negotiations evaluated.
            </p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {negotiations.map(neg => (
                <div
                  key={neg.id}
                  className="p-3 rounded-xl border border-stroke-light dark:border-stroke-dark bg-surface-subtleLight dark:bg-surface-subtleDark text-xs space-y-1"
                >
                  <div className="flex items-center justify-between font-bold text-content-mainLight dark:text-content-mainDark">
                    <span>{neg.title}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-extrabold ${
                      neg.status === 'accepted' ? 'bg-emerald-500/20 text-emerald-500' : (
                        neg.status === 'countered' ? 'bg-amber-500/20 text-amber-500' : 'bg-rose-500/20 text-rose-500'
                      )
                    }`}>
                      {neg.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-content-mutedLight dark:text-content-mutedDark flex items-center justify-between">
                    <span>Requested by: <strong>{neg.requested_by}</strong></span>
                    <span>{new Date(neg.proposed_start_time).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
