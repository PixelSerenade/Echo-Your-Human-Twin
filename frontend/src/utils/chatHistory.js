export const CHAT_HISTORY_RETENTION_MS = 14 * 24 * 60 * 60 * 1000;
export const CHAT_CONTEXT_TURN_LIMIT = 40;

function makeThreadId(now = Date.now()) {
  const randomId = globalThis.crypto?.randomUUID?.();
  return randomId ? `chat-${randomId}` : `chat-${now}-${Math.random().toString(36).slice(2, 9)}`;
}

export function titleForChat(turns = []) {
  const firstUserMessage = turns.find((turn) => turn.role === 'user' && turn.content.trim())?.content.trim();
  if (!firstUserMessage) return 'New chat';
  return firstUserMessage.length > 38 ? `${firstUserMessage.slice(0, 37).trimEnd()}…` : firstUserMessage;
}

export function createChatThread(now = Date.now()) {
  return { id: makeThreadId(now), title: 'New chat', updatedAt: now, turns: [], learningProgress: null };
}

function normalizeLearningProgress(progress) {
  if (!progress || progress.active !== true) return null;
  const answered = Math.max(0, Math.floor(Number(progress.answered) || 0));
  const target = Math.max(5, Math.floor(Number(progress.target) || 5));
  return { active: true, answered, target };
}

export function retainChatHistory(turns, now = Date.now()) {
  if (!Array.isArray(turns)) return [];
  return turns.filter((turn) => {
    if (!turn || !['user', 'assistant'].includes(turn.role) || typeof turn.content !== 'string') return false;
    const createdAt = new Date(turn.createdAt).getTime();
    return Number.isFinite(createdAt) && now - createdAt < CHAT_HISTORY_RETENTION_MS;
  });
}

export function readChatHistory(storageKey, localStorage, sessionStorage, now = Date.now()) {
  try {
    const saved = localStorage?.getItem(storageKey) || sessionStorage?.getItem(storageKey);
    if (!saved) return [];
    const parsed = JSON.parse(saved);
    return retainChatHistory(
      Array.isArray(parsed) ? parsed.map((turn) => ({ ...turn, createdAt: turn.createdAt || now })) : [],
      now,
    );
  } catch {
    return [];
  }
}

export function readChatWorkspace(workspaceKey, legacyHistoryKey, localStorage, sessionStorage, now = Date.now()) {
  try {
    const savedWorkspace = localStorage?.getItem(workspaceKey);
    if (savedWorkspace) {
      const parsed = JSON.parse(savedWorkspace);
      if (Array.isArray(parsed?.threads)) {
        const threads = parsed.threads.map((thread) => {
          const turns = retainChatHistory(thread?.turns, now);
          const updatedAt = new Date(thread?.updatedAt).getTime();
          return {
            id: typeof thread?.id === 'string' ? thread.id : makeThreadId(now),
            title: titleForChat(turns) === 'New chat' ? 'New chat' : titleForChat(turns),
            updatedAt: Number.isFinite(updatedAt) ? updatedAt : now,
            turns,
            learningProgress: normalizeLearningProgress(thread?.learningProgress),
          };
        }).filter((thread) => (
          thread.id === parsed.activeThreadId ||
          (thread.turns.length > 0 && now - thread.updatedAt < CHAT_HISTORY_RETENTION_MS)
        ));
        if (!threads.length) threads.push(createChatThread(now));
        const activeThreadId = threads.some((thread) => thread.id === parsed.activeThreadId)
          ? parsed.activeThreadId
          : threads[0].id;
        return { activeThreadId, threads };
      }
    }

    const legacyTurns = readChatHistory(legacyHistoryKey, localStorage, sessionStorage, now);
    const migratedThread = createChatThread(now);
    migratedThread.turns = legacyTurns;
    migratedThread.title = titleForChat(legacyTurns);
    return { activeThreadId: migratedThread.id, threads: [migratedThread] };
  } catch {
    const fallbackThread = createChatThread(now);
    return { activeThreadId: fallbackThread.id, threads: [fallbackThread] };
  }
}
