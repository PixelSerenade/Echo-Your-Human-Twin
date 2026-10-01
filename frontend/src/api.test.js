import assert from 'node:assert/strict';
import { apiRequest } from './api.js';

globalThis.window = { location: { hostname: 'localhost' } };
try {
  const { BASE_URL } = await import('./api.js?localhost-check');
  assert.equal(BASE_URL, 'http://localhost:8003');
  globalThis.window.location.hostname = 'echo.up.railway.app';
  const hosted = await import('./api.js?hosted-check');
  assert.equal(hosted.BASE_URL, '');
} finally {
  delete globalThis.window;
}

const originalFetch = globalThis.fetch;
try {
  globalThis.fetch = async () => new Response('Gateway unavailable', { status: 502 });
  await assert.rejects(apiRequest('/test'), /Gateway unavailable/);

  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ loc: ['body', 'name'], msg: 'required' }] }), {
    status: 422,
    headers: { 'Content-Type': 'application/json' },
  });
  await assert.rejects(apiRequest('/test'), /name: required/);

  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await apiRequest('/test'), null);
} finally {
  globalThis.fetch = originalFetch;
}

console.log('API response handling tests passed.');
