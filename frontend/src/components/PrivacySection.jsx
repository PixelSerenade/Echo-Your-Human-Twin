import React, { useState, useEffect } from 'react';
import SlideUpDrawer from './SlideUpDrawer';
import { ShieldCheck, FileText, CheckCircle, Trash2, ExternalLink } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function PrivacySection({ api, profile, onPersonaChange }) {
  const { twinName } = useTheme();
  const [permissions, setPermissions] = useState({
    schedule_commitments: true,
    deadlines_key_dates: true,
    focus_work_patterns: true,
    routines_preferences: true,
    goals: true,
    decision_history: true,
    mood_tone: false,
    spending_money: false
  });
  const [auditLogs, setAuditLogs] = useState([]);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [registry, setRegistry] = useState({ categories: [], personas: [] });

  const userId = profile?.user_id || 'demo-alex-rivers';

  const loadData = async (persona = profile?.persona || 'other') => {
    try {
      const registryRes = await api.getMemoryRegistry(persona);
      setRegistry(registryRes);
      const permRes = await api.getPermissions(userId);
      if (permRes?.permissions) {
        setPermissions(permRes.permissions);
      }
      const auditRes = await api.getAuditLog(userId, 30);
      if (auditRes?.entries) {
        setAuditLogs(auditRes.entries);
      }
      const attachmentRes = await api.listAttachments(userId);
      setAttachments(attachmentRes?.attachments || []);
    } catch (err) {
      console.error('Error loading permissions:', err);
      setSaveStatus("Hmm, I couldn't load your privacy choices. Try again?");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggle = async (sourceKey) => {
    const previous = permissions;
    const updated = {
      ...permissions,
      [sourceKey]: !permissions[sourceKey]
    };
    setPermissions(updated);
    try {
      const registryPatch = Object.fromEntries(registry.categories.map((category) => [category.id, updated[category.id]]));
      await api.updatePermissions(userId, registryPatch);
      setSaveStatus(`${registry.categories.find((item) => item.id === sourceKey)?.title || sourceKey} is ${updated[sourceKey] ? 'on' : 'off'}.`);
      setTimeout(() => setSaveStatus(''), 3000);
      loadData();
    } catch (err) {
      setPermissions(previous);
      console.error('Failed to update permission:', err);
      setSaveStatus("Hmm, that change didn't save. Try again?");
    }
  };

  const handleDeleteAttachment = async (attachmentId) => {
    try {
      await api.deleteAttachment(userId, attachmentId);
      setAttachments((items) => items.filter((item) => item.id !== attachmentId));
      setSaveStatus('That file has been deleted.');
      setTimeout(() => setSaveStatus(''), 3000);
    } catch {
      setSaveStatus("Hmm, I couldn't delete that file. Try again?");
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 pb-24 space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="space-y-1.5 text-center sm:text-left">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Single Gateway Active &bull; Zero Data Leaks</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold font-heading text-content-mainLight dark:text-content-mainDark">
          Privacy & Data Sovereignty
        </h2>
        <p className="text-sm text-content-mutedLight dark:text-content-mutedDark">
          You control what {twinName} can use from information you choose to share. Disabled categories are not read or sent to Gemini.
        </p>
        <label className="mt-3 block text-xs font-semibold">What best describes your days?
          <select value={profile?.persona || 'other'} onChange={async (event) => { if (onPersonaChange) await onPersonaChange(event.target.value); else await api.updatePersona(userId, event.target.value); await loadData(event.target.value); }} className="ml-2 rounded-lg border border-stroke-light dark:border-stroke-dark bg-surface-light dark:bg-surface-dark p-2 min-h-11">
            {registry.personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.label}</option>)}
          </select>
        </label>
      </div>

      {saveStatus && (
        <div className="p-3 rounded-2xl bg-brand-purple/10 border border-brand-purple/30 text-xs font-medium text-brand-purple dark:text-[#A894FF] flex items-center space-x-2 animate-fadeIn">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{saveStatus}</span>
        </div>
      )}

      {/* Grouped Permission Toggles (Spacious Cards) */}
      <div className="p-6 rounded-3xl bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-5">
        <span className="text-xs font-bold uppercase tracking-wider text-content-mutedLight dark:text-content-mutedDark">
          Permitted Data Sources
        </span>

        <div className="space-y-4">
          {registry.categories.map((details) => {
            const key = details.id;
            const isEnabled = permissions[key] ?? details.default_enabled;

            return (
              <div
                key={key}
                className="flex items-center justify-between p-4 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark hover:border-brand-purple/40 transition"
              >
                <div className="flex items-center space-x-3.5 pr-4">
                  <span className="text-2xl flex-shrink-0">{key === 'schedule_commitments' ? '📅' : key === 'deadlines_key_dates' ? '⏰' : key === 'focus_work_patterns' ? '✨' : key === 'mood_tone' ? '💬' : key === 'goals' ? '🎯' : '⚙️'}</span>
                  <div>
                    <h4 className="text-sm font-bold font-heading text-content-mainLight dark:text-content-mainDark">
                      {details.title}
                    </h4>
                    <p className="text-xs text-content-mutedLight dark:text-content-mutedDark leading-snug">
                      {details.description}
                    </p>
                    <p className="mt-1 text-[11px] text-content-mutedLight dark:text-content-mutedDark">{details.hint}</p>
                  </div>
                </div>

                {/* iOS-Style Toggle Switch */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={isEnabled}
                  onClick={() => handleToggle(key)}
                  aria-label={`${details.title}: ${isEnabled ? 'On' : 'Off'}`}
                  className={`min-h-11 min-w-[76px] px-2 rounded-full transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple flex-shrink-0 inline-flex items-center justify-center ${
                    isEnabled ? 'bg-brand-purple' : 'bg-stroke-light dark:bg-stroke-dark'
                  }`}
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

        {/* Secondary Action Link */}
        <div className="pt-2 flex justify-between items-center text-xs">
          <span className="text-content-mutedLight dark:text-content-mutedDark">
            Every read logs an immutable entry in the audit trail.
          </span>
          <button
            onClick={() => setIsAuditDrawerOpen(true)}
            className="font-bold text-brand-purple dark:text-[#A894FF] hover:underline flex items-center space-x-1"
          >
            <span>View Audit Trail</span>
            <span>&rarr;</span>
          </button>
        </div>
      </div>

      <section className="p-6 rounded-lg bg-surface-light dark:bg-surface-dark border border-stroke-light dark:border-stroke-dark shadow-soft-light space-y-4" aria-labelledby="uploaded-files-heading">
        <div>
          <h3 id="uploaded-files-heading" className="text-sm font-bold text-content-mainLight dark:text-content-mainDark">Uploaded files</h3>
          <p className="mt-1 text-xs text-content-mutedLight dark:text-content-mutedDark">Files you shared with {twinName}. You can remove them at any time.</p>
        </div>
        {attachments.length === 0 ? (
          <p className="py-3 text-sm text-content-mutedLight dark:text-content-mutedDark">You haven't uploaded any files yet.</p>
        ) : attachments.map((item) => (
          <div key={item.id} className="flex items-center gap-3 border-t border-stroke-light dark:border-stroke-dark pt-3">
            <FileText className="h-5 w-5 text-brand-purple flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <a
                href={api.getAttachmentUrl ? api.getAttachmentUrl(userId, item.id) : '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="truncate text-sm font-semibold text-content-mainLight dark:text-content-mainDark hover:text-brand-purple dark:hover:text-[#A894FF] hover:underline block"
                title={`View ${item.name}`}
              >
                {item.name}
              </a>
              <p className="text-xs text-content-mutedLight dark:text-content-mutedDark">{(item.size_bytes / (1024 * 1024)).toFixed(2)} MB</p>
            </div>
            <a
              href={api.getAttachmentUrl ? api.getAttachmentUrl(userId, item.id) : '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="h-11 w-11 grid place-items-center rounded-full text-content-mutedLight dark:text-content-mutedDark hover:text-brand-purple hover:bg-surface-subtleLight dark:hover:bg-surface-subtleDark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple"
              aria-label={`View ${item.name}`}
              title="View file"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
            <button
              type="button"
              onClick={() => handleDeleteAttachment(item.id)}
              className="h-11 w-11 grid place-items-center rounded-full text-rose-600 hover:bg-rose-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple"
              aria-label={`Delete ${item.name}`}
              title="Delete file"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </section>

      {/* SLIDE-UP DRAWER FOR AUDIT TRAIL */}
      <SlideUpDrawer
        isOpen={isAuditDrawerOpen}
        onClose={() => setIsAuditDrawerOpen(false)}
        title="Data Access Audit Trail"
        subtitle="Verifiable transparency of every data access request by endpoint and purpose"
        badge="Immutable Log"
      >
        <div className="space-y-3">
          {auditLogs.length === 0 ? (
            <p className="text-sm text-content-mutedLight dark:text-content-mutedDark py-6 text-center">
              No audit records yet.
            </p>
          ) : (
            auditLogs.map((log) => (
              <div
                key={log.id}
                className="p-3.5 rounded-2xl bg-surface-subtleLight dark:bg-surface-subtleDark border border-stroke-light dark:border-stroke-dark space-y-1 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-content-mainLight dark:text-content-mainDark font-mono">
                    {log.endpoint} &bull; {log.purpose}
                  </span>
                  <span className="text-[11px] font-mono text-content-mutedLight dark:text-content-mutedDark">
                    {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-content-mutedLight dark:text-content-mutedDark">Accessed Sources:</span>
                  <span className="font-semibold text-brand-purple dark:text-[#A894FF]">
                    {log.sources_accessed}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </SlideUpDrawer>
    </div>
  );
}
