import React, { useEffect, useRef, useState } from 'react';
import {
  Camera, FileText, Image, Mic, Plus, Send, Square, Video, X
} from 'lucide-react';
import {
  MAX_ATTACHMENT_BYTES, ONE_ATTACHMENT_MESSAGE, validateAttachmentFiles
} from '../utils/attachmentValidation';

const ACCEPT = {
  document: '.pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain',
  image: '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp',
  video: '.mp4,.webm,video/mp4,video/webm'
};

function formatTime(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

export default function ChatComposer({
  api, userId, twinName, value, onChange, onSend, isLoading, attachment, setAttachment
}) {
  const textareaRef = useRef(null);
  const inputRef = useRef(null);
  const menuRef = useRef(null);
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [accept, setAccept] = useState(ACCEPT.document);
  const [capture, setCapture] = useState(false);
  const [status, setStatus] = useState('');
  const [progress, setProgress] = useState(0);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [language, setLanguage] = useState(() => navigator.language || 'en-US');

  const showStatus = (message) => {
    setStatus(message);
    window.clearTimeout(showStatus.timeout);
    showStatus.timeout = window.setTimeout(() => setStatus(''), 6500);
  };

  useEffect(() => {
    if (!menuOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpen]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`;
    textarea.style.overflowY = textarea.scrollHeight > 144 ? 'auto' : 'hidden';
  }, [value]);

  const stopTracks = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const stopRecording = () => {
    recognitionRef.current?.stop?.();
    recognitionRef.current = null;
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    window.clearInterval(timerRef.current);
    setRecording(false);
    stopTracks();
  };

  useEffect(() => {
    const stopOnHidden = () => { if (document.hidden) stopRecording(); };
    const stopOnBlur = () => stopRecording();
    document.addEventListener('visibilitychange', stopOnHidden);
    window.addEventListener('blur', stopOnBlur);
    return () => {
      document.removeEventListener('visibilitychange', stopOnHidden);
      window.removeEventListener('blur', stopOnBlur);
      stopRecording();
    };
  }, []);

  const upload = async (files) => {
    const result = validateAttachmentFiles(files, Boolean(attachment));
    if (result.error) return showStatus(result.error);
    setStatus('');
    setProgress(1);
    const previewUrl = result.file.type.startsWith('image/') ? URL.createObjectURL(result.file) : '';
    try {
      const uploaded = await api.uploadAttachment(userId, result.file, setProgress);
      setAttachment({ ...uploaded, previewUrl });
      setProgress(100);
    } catch (error) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setProgress(0);
      showStatus(error.message);
    }
  };

  const choose = (kind, shouldCapture = false) => {
    if (attachment) return showStatus(ONE_ATTACHMENT_MESSAGE);
    setAccept(shouldCapture ? 'image/*' : ACCEPT[kind]);
    setCapture(shouldCapture);
    setMenuOpen(false);
    window.setTimeout(() => inputRef.current?.click(), 0);
  };

  const removeAttachment = async () => {
    if (attachment?.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    const id = attachment?.id;
    setAttachment(null);
    setProgress(0);
    setStatus('');
    if (id) api.deleteAttachment(userId, id).catch(() => showStatus("Hmm, I couldn't remove that file. Try again?"));
    textareaRef.current?.focus();
  };

  const handlePaste = (event) => {
    const imageFiles = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith('image/'));
    if (!imageFiles.length) return;
    event.preventDefault();
    upload(imageFiles);
  };

  const handleSubmit = async () => {
    if (isLoading || (!value.trim() && !attachment)) return;
    await onSend();
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const beginTimer = () => {
    setRecordingSeconds(0);
    timerRef.current = window.setInterval(() => {
      setRecordingSeconds((seconds) => {
        if (seconds >= 59) {
          showStatus("That's the max length. Here's what I caught.");
          window.setTimeout(stopRecording, 0);
        }
        return seconds + 1;
      });
    }, 1000);
  };

  const startFallback = (stream) => {
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
    const recorder = new MediaRecorder(stream, { mimeType });
    recorderRef.current = recorder;
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunksRef.current.push(event.data);
      const size = chunksRef.current.reduce((sum, chunk) => sum + chunk.size, 0);
      if (size >= MAX_ATTACHMENT_BYTES) {
        showStatus("That's the max length. Here's what I caught.");
        if (recorder.state === 'recording') recorder.stop();
      }
    };
    recorder.onstop = async () => {
      window.clearInterval(timerRef.current);
      setRecording(false);
      stopTracks();
      const blob = new Blob(chunksRef.current, { type: mimeType }).slice(0, MAX_ATTACHMENT_BYTES, mimeType);
      chunksRef.current = [];
      try {
        const result = await api.transcribe(userId, blob);
        onChange((value ? `${value} ` : '') + result.transcript);
        requestAnimationFrame(() => textareaRef.current?.focus());
      } catch (error) {
        showStatus(error.message || "Hmm, I couldn't catch that. Try again?");
      }
    };
    recorder.start(500);
  };

  const toggleMic = async () => {
    if (recording) return stopRecording();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      setRecording(true);
      beginTimer();
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Recognition) return startFallback(stream);
      stopTracks();
      const recognition = new Recognition();
      recognitionRef.current = recognition;
      recognition.lang = language;
      recognition.continuous = true;
      recognition.interimResults = true;
      const startingText = value;
      let finalText = '';
      recognition.onresult = (event) => {
        let interim = '';
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const text = event.results[index][0].transcript;
          if (event.results[index].isFinal) finalText += text;
          else interim += text;
        }
        onChange([startingText, finalText, interim].filter(Boolean).join(startingText ? ' ' : ''));
      };
      recognition.onerror = () => showStatus("Hmm, I couldn't catch that. Try again?");
      recognition.onend = () => {
        window.clearInterval(timerRef.current);
        setRecording(false);
        recognitionRef.current = null;
      };
      recognition.start();
    } catch {
      setRecording(false);
      showStatus("Hmm, I couldn't access your microphone. Check permission and try again?");
    }
  };

  return (
    <div
      className="fixed bottom-16 md:bottom-0 left-0 md:left-64 right-0 z-30 px-3 pb-2 md:pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-8 bg-gradient-to-t from-app-light via-app-light/95 dark:from-app-dark dark:via-app-dark/95 to-transparent"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => { event.preventDefault(); upload(event.dataTransfer.files); }}
    >
      <div className="max-w-3xl mx-auto">
        {status && (
          <div className="mb-2 px-4 py-2 rounded-lg bg-white dark:bg-zinc-100 text-zinc-800 border border-rose-200 text-xs shadow-md" role="status" aria-live="polite">
            {status}
          </div>
        )}
        <div className="relative rounded-[26px] bg-white dark:bg-zinc-100 text-zinc-900 border border-zinc-200 shadow-xl focus-within:ring-2 focus-within:ring-brand-purple">
          {attachment && (
            <div className="mx-3 mt-3 flex items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-2 pr-3">
              {attachment.previewUrl ? <img src={attachment.previewUrl} alt="Attachment preview" className="h-11 w-11 rounded object-cover" /> : <FileText className="h-6 w-6 text-brand-purple" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold">{attachment.name}</p>
                <div className="mt-1 h-1 overflow-hidden rounded bg-zinc-200"><div className="h-full bg-brand-gradient" style={{ width: `${progress}%` }} /></div>
              </div>
              <button type="button" onClick={removeAttachment} className="h-11 w-11 grid place-items-center rounded-full hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple" aria-label="Remove attachment"><X className="h-4 w-4" /></button>
            </div>
          )}
          <div className="flex items-end gap-1 p-1.5">
            <div ref={menuRef} className="relative">
              <button type="button" onClick={() => attachment ? showStatus(ONE_ATTACHMENT_MESSAGE) : setMenuOpen((open) => !open)} className="h-11 w-11 grid place-items-center rounded-full hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple" aria-label="Add attachment" aria-expanded={menuOpen}><Plus className="h-5 w-5" /></button>
              {menuOpen && (
                <div className="absolute bottom-12 left-0 w-52 rounded-lg border border-zinc-200 bg-white p-1.5 shadow-xl" role="menu">
                  <button type="button" onClick={() => choose('document')} className="w-full h-11 px-3 flex items-center gap-3 rounded-md text-sm hover:bg-zinc-100"><FileText className="h-4 w-4" />Upload file</button>
                  <button type="button" onClick={() => choose('image')} className="w-full h-11 px-3 flex items-center gap-3 rounded-md text-sm hover:bg-zinc-100"><Image className="h-4 w-4" />Upload image</button>
                  <button type="button" onClick={() => choose('video')} className="w-full h-11 px-3 flex items-center gap-3 rounded-md text-sm hover:bg-zinc-100"><Video className="h-4 w-4" />Upload video</button>
                  <button type="button" onClick={() => choose('image', true)} className="w-full h-11 px-3 flex items-center gap-3 rounded-md text-sm hover:bg-zinc-100 sm:hidden"><Camera className="h-4 w-4" />Take photo</button>
                </div>
              )}
            </div>
            <input ref={inputRef} type="file" className="hidden" accept={accept} capture={capture ? 'environment' : undefined} multiple onChange={(event) => { upload(event.target.files); event.target.value = ''; }} />
            <textarea
              ref={textareaRef}
              rows={1}
              value={value}
              onFocus={() => { if (status) setStatus(''); }}
              onChange={(event) => {
                if (status) setStatus('');
                onChange(event.target.value);
              }}
              onPaste={handlePaste}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSubmit(); }
              }}
              placeholder={`Ask ${twinName || 'Echo'} anything...`}
              aria-label={`Message ${twinName || 'Echo'}`}
              className="min-h-11 max-h-36 flex-1 resize-none bg-transparent px-2 py-3 text-sm leading-5 text-zinc-900 placeholder:text-zinc-500 focus:outline-none"
            />
            <select value={language} onChange={(event) => setLanguage(event.target.value)} className="mb-1 h-9 max-w-20 rounded-md bg-zinc-100 px-1 text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple" aria-label="Voice language">
              <option value={navigator.language || 'en-US'}>{(navigator.language || 'en-US').split('-')[0].toUpperCase()}</option>
              <option value="en-US">EN</option><option value="hi-IN">HI</option><option value="kn-IN">KN</option>
            </select>
            <button type="button" onClick={toggleMic} className={`h-11 w-11 grid place-items-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-purple ${recording ? 'animate-pulse bg-rose-100 text-rose-600' : 'hover:bg-zinc-100'}`} aria-label={recording ? `Stop recording, ${formatTime(recordingSeconds)}` : 'Start voice input'}>{recording ? <Square className="h-4 w-4 fill-current" /> : <Mic className="h-5 w-5" />}</button>
            <button type="button" onClick={handleSubmit} disabled={isLoading || (!value.trim() && !attachment)} className="h-11 w-11 grid place-items-center rounded-full bg-brand-gradient text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-purple" aria-label="Send message"><Send className="h-4 w-4" /></button>
          </div>
          {recording && <div className="absolute -top-7 right-3 rounded-full bg-white px-2 py-1 text-xs font-semibold text-rose-600 shadow">Recording {formatTime(recordingSeconds)}</div>}
        </div>
      </div>
    </div>
  );
}
