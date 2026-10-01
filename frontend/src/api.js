// Keep the API on the same local hostname as the page so SameSite session
// cookies work whether someone opens localhost or 127.0.0.1.
const pageHost = typeof window === 'undefined' ? '127.0.0.1' : window.location.hostname;
const isLocal = pageHost === 'localhost' || pageHost === '127.0.0.1';
export const BASE_URL = isLocal ? `http://${pageHost}:8003` : '';

export async function apiRequest(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers
  });

  if (!response.ok) {
    let errorDetail = 'API Request Failed';
    const body = await response.text();
    try {
      const err = JSON.parse(body);
      errorDetail = Array.isArray(err.detail)
        ? err.detail.map((item) => `${(item.loc || []).filter((part) => part !== 'body').join('.') || 'request'}: ${item.msg || 'invalid value'}`).join('; ')
        : (err.detail || JSON.stringify(err));
    } catch {
      errorDetail = body || errorDetail;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  getMemoryRegistry: (persona = 'other') => apiRequest(`/api/memory-registry?persona=${encodeURIComponent(persona)}`),
  updatePersona: (userId, persona) => apiRequest('/api/profile/persona', { method: 'PUT', body: JSON.stringify({ user_id: userId, persona }) }),
  getProfile: (userId = 'demo-alex-rivers') =>
    apiRequest(`/profile/${userId}`),

  saveProfile: (data) =>
    apiRequest('/profile', { method: 'POST', body: JSON.stringify(data) }),

  updateTwinName: (userId, twinName) =>
    apiRequest('/api/profile/twin-name', {
      method: 'PUT',
      body: JSON.stringify({ user_id: userId, twin_name: twinName })
    }),

  getPermissions: (userId = 'demo-alex-rivers') =>
    apiRequest(`/permissions?user_id=${userId}`),

  updatePermissions: (userId, permissions) =>
    apiRequest('/permissions', {
      method: 'PUT',
      body: JSON.stringify({ user_id: userId, permissions })
    }),

  askTwin: (data) =>
    apiRequest('/ask', { method: 'POST', body: JSON.stringify(data) }),

  uploadAttachment: (userId, file, onProgress = () => {}) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/api/attachments`);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-User-Id', userId);
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let payload = {};
      try { payload = JSON.parse(xhr.responseText || '{}'); } catch { payload = {}; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(payload);
      else reject(new Error(payload.detail || 'Hmm, that file did not upload. Try again?'));
    };
    xhr.onerror = () => reject(new Error('Hmm, that file did not upload. Try again?'));
    xhr.send(file);
  }),

  listAttachments: (userId) =>
    apiRequest('/api/attachments', { headers: { 'X-User-Id': userId } }),

  getAttachmentUrl: (userId, attachmentId) =>
    `${BASE_URL}/api/attachments/${attachmentId}?user_id=${encodeURIComponent(userId)}`,

  deleteAttachment: (userId, attachmentId) =>
    apiRequest(`/api/attachments/${attachmentId}`, {
      method: 'DELETE',
      headers: { 'X-User-Id': userId }
    }),

  confirmExtractedItems: (userId, attachmentId, items) =>
    apiRequest(`/api/attachments/${attachmentId}/confirm-extracted`, {
      method: 'POST',
      headers: { 'X-User-Id': userId },
      body: JSON.stringify({ items })
    }),

  transcribe: async (userId, audioBlob) => {
    const response = await fetch(`${BASE_URL}/api/transcribe`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'X-User-Id': userId,
        'Content-Type': audioBlob.type || 'audio/webm'
      },
      body: audioBlob
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Hmm, I couldn't catch that. Try again?");
    return payload;
  },

  conductDebate: (data) =>
    apiRequest('/debate', { method: 'POST', body: JSON.stringify(data) }),

  simulate: (data) =>
    apiRequest('/simulate', { method: 'POST', body: JSON.stringify(data) }),

  correctSimulation: (data) =>
    apiRequest('/simulate/correct', { method: 'POST', body: JSON.stringify(data) }),

  submitFeedback: (data) =>
    apiRequest('/feedback', { method: 'POST', body: JSON.stringify(data) }),

  getLearnedPreferences: (userId = 'demo-alex-rivers') =>
    apiRequest(`/api/preferences/learned?user_id=${encodeURIComponent(userId)}`),

  forgetLearnedPreference: (key, userId = 'demo-alex-rivers') =>
    apiRequest(`/api/preferences/learned/${encodeURIComponent(key)}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' }),

  resetLearnedPreferences: (userId = 'demo-alex-rivers') =>
    apiRequest(`/api/preferences/learned?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' }),

  getTwinKnowledge: (userId = 'demo-alex-rivers') =>
    apiRequest(`/twin-knowledge?user_id=${userId}`),

  getReminders: (userId = 'demo-alex-rivers') =>
    apiRequest(`/api/reminders?user_id=${encodeURIComponent(userId)}`),

  getPushPublicKey: () => apiRequest('/api/push/public-key'),
  savePushSubscription: (userId, subscription, timezone) => apiRequest('/api/push/subscribe', {
    method: 'POST',
    headers: { 'X-User-Id': userId },
    body: JSON.stringify({ user_id: userId, subscription, timezone })
  }),
  removePushSubscription: (userId, endpoint) => apiRequest('/api/push/subscribe', {
    method: 'DELETE',
    headers: { 'X-User-Id': userId },
    body: JSON.stringify({ user_id: userId, endpoint })
  }),
  sendPushTest: (userId) => apiRequest('/api/push/test', {
    method: 'POST',
    headers: { 'X-User-Id': userId },
    body: JSON.stringify({ user_id: userId })
  }),

  createPlanItem: (data) => apiRequest('/api/plan-items', {
    method: 'POST',
    body: JSON.stringify(data)
  }),

  updateGoal: (userId, goalId, milestones) => apiRequest(`/api/goals/${goalId}?user_id=${encodeURIComponent(userId)}`, {
    method: 'PUT',
    body: JSON.stringify({ milestones })
  }),

  deleteGoal: (userId, goalId) => apiRequest(`/api/goals/${goalId}?user_id=${encodeURIComponent(userId)}`, {
    method: 'DELETE'
  }),

  editKnowledgeItem: (source, itemId, data, userId = 'demo-alex-rivers', category = '') =>
    apiRequest(`/twin-knowledge/${source}/${itemId}?user_id=${encodeURIComponent(userId)}${category ? `&category=${encodeURIComponent(category)}` : ''}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  deleteKnowledgeItem: (source, itemId, userId = 'demo-alex-rivers', category = '') =>
    apiRequest(`/twin-knowledge/${source}/${itemId}?user_id=${encodeURIComponent(userId)}${category ? `&category=${encodeURIComponent(category)}` : ''}`, {
      method: 'DELETE'
    }),

  getAuditLog: (userId = 'demo-alex-rivers', limit = 40) =>
    apiRequest(`/audit-log?user_id=${userId}&limit=${limit}`),

  // Auth & Onboarding
  signup: (data) =>
    apiRequest('/api/auth/signup', { method: 'POST', body: JSON.stringify(data) }),

  login: (data) =>
    apiRequest('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  logout: () =>
    apiRequest('/api/auth/logout', { method: 'POST' }),

  getMe: () =>
    apiRequest('/api/auth/me'),

  saveOnboardingStep: (data) =>
    apiRequest('/api/onboarding/step', { method: 'POST', body: JSON.stringify(data) }),

  getOnboardingState: () =>
    apiRequest('/api/onboarding/state')
};
