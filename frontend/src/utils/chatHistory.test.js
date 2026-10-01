import assert from 'node:assert/strict';
import { CHAT_CONTEXT_TURN_LIMIT, createChatThread, readChatHistory, readChatWorkspace, retainChatHistory, titleForChat } from './chatHistory.js';

const now = Date.parse('2026-10-01T10:00:00Z');
const local = new Map();
const session = new Map();
const localStorage = {
  getItem: (key) => local.get(key) ?? null,
  setItem: (key, value) => local.set(key, value),
};
const sessionStorage = {
  getItem: (key) => session.get(key) ?? null,
};

localStorage.setItem('echo-chat-history-user-a', JSON.stringify([
  { role: 'user', content: 'I want to be placed', createdAt: now - 60_000 },
  { role: 'assistant', content: 'What role are you targeting?', createdAt: now - 30_000 },
  { role: 'user', content: 'Software engineer', createdAt: now },
]));
localStorage.setItem('echo-chat-history-user-b', JSON.stringify([
  { role: 'user', content: 'Separate account history', createdAt: now },
]));

const restored = readChatHistory('echo-chat-history-user-a', localStorage, sessionStorage, now);
assert.equal(restored.length, 3, 'restores the prior conversation when the chat is reopened');
assert.equal(restored[2].content, 'Software engineer', 'keeps the clarification needed for the next reply');
assert.equal(
  readChatHistory('echo-chat-history-user-b', localStorage, sessionStorage, now)[0].content,
  'Separate account history',
  'restores history using the active user key',
);
assert.equal(
  readChatHistory('missing', localStorage, sessionStorage, now).length,
  0,
  'does not copy another user’s chat into a new account',
);
assert.equal(CHAT_CONTEXT_TURN_LIMIT, 40, 'sends a wider rolling conversation context to Echo');
assert.equal(titleForChat(restored), 'I want to be placed', 'uses the first user message for the chat title');
assert.equal(
  retainChatHistory([{ role: 'user', content: 'too old', createdAt: now - 15 * 24 * 60 * 60 * 1000 }], now).length,
  0,
  'expires local chat history after the existing 14-day retention period',
);
assert.equal(retainChatHistory([{ role: 'system', content: 'not a user-visible turn', createdAt: now }], now).length, 0);

const legacyWorkspace = readChatWorkspace(
  'echo-chat-workspace-user-a',
  'echo-chat-history-user-a',
  localStorage,
  sessionStorage,
  now,
);
assert.equal(legacyWorkspace.threads.length, 1, 'migrates the existing single-chat history into a chat thread');
assert.equal(legacyWorkspace.threads[0].turns[2].content, 'Software engineer');
assert.equal(legacyWorkspace.activeThreadId, legacyWorkspace.threads[0].id);
assert.equal(createChatThread(now).title, 'New chat', 'starts a separate blank conversation');

localStorage.setItem('echo-chat-workspace-user-a', JSON.stringify({
  activeThreadId: 'chat-second',
  threads: [
    {
      id: 'chat-first',
      title: 'ignored title is rebuilt from the first message',
      updatedAt: now - 10_000,
      turns: [{ role: 'user', content: 'Help me with my CV', createdAt: now - 10_000 }],
    },
    {
      id: 'chat-second',
      title: 'ignored title is rebuilt from the first message',
      updatedAt: now,
      turns: [{ role: 'user', content: 'How do I prepare for interviews?', createdAt: now }],
    },
  ],
}));
const reopenedWorkspace = readChatWorkspace(
  'echo-chat-workspace-user-a',
  'echo-chat-history-user-a',
  localStorage,
  sessionStorage,
  now,
);
assert.equal(reopenedWorkspace.threads.length, 2, 'restores multiple separate saved chats');
assert.equal(reopenedWorkspace.activeThreadId, 'chat-second', 'restores the selected chat after reopening');
assert.equal(reopenedWorkspace.threads[0].title, 'Help me with my CV', 'builds the chat title from user text');
assert.equal(reopenedWorkspace.threads[1].title, 'How do I prepare for interviews?', 'keeps titles isolated by conversation');

localStorage.setItem('echo-chat-workspace-user-a', JSON.stringify({
  activeThreadId: 'chat-study',
  threads: [{
    id: 'chat-study',
    title: 'Quiz me on this assignment',
    updatedAt: now,
    learningProgress: { active: true, answered: 2, target: 5 },
    turns: [{
      role: 'user', content: 'Quiz me on this assignment', createdAt: now,
      attachment_id: 'owned-pdf-id', attachment_name: 'assignment.pdf',
    }],
  }],
}));
const studyWorkspace = readChatWorkspace(
  'echo-chat-workspace-user-a',
  'echo-chat-history-user-a',
  localStorage,
  sessionStorage,
  now,
);
assert.equal(studyWorkspace.threads[0].turns[0].attachment_id, 'owned-pdf-id', 'keeps the uploaded file linked to its chat turn');
assert.equal(studyWorkspace.threads[0].turns[0].attachment_name, 'assignment.pdf', 'keeps the uploaded file name in chat history');
assert.deepEqual(studyWorkspace.threads[0].learningProgress, { active: true, answered: 2, target: 5 }, 'restores progress for the same learning chat');

console.log('Chat history persistence tests passed.');
