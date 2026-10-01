import fs from 'node:fs';
import path from 'node:path';

const SCREENSHOT_DIR = path.resolve('d:/Hackathon/screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function getWsUrl() {
  const res = await fetch('http://127.0.0.1:9222/json');
  const list = await res.json();
  const page = list.find((item) => item.type === 'page');
  if (!page) throw new Error('No page target found');
  return page.webSocketDebuggerUrl;
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.callbacks = new Map();
    this.ready = new Promise((resolve) => {
      this.ws.onopen = () => resolve();
    });
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.id && this.callbacks.has(data.id)) {
        const { resolve, reject } = this.callbacks.get(data.id);
        this.callbacks.delete(data.id);
        if (data.error) reject(new Error(data.error.message));
        else resolve(data.result);
      }
    };
  }

  async send(method, params = {}) {
    await this.ready;
    const currentId = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(currentId, { resolve, reject });
      this.ws.send(JSON.stringify({ id: currentId, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    return res.result?.value;
  }

  async screenshot(filePath) {
    const res = await this.send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    fs.writeFileSync(filePath, buffer);
    console.log(`Saved screenshot: ${filePath}`);
  }

  close() {
    this.ws.close();
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function run() {
  const wsUrl = await getWsUrl();
  const client = new CdpClient(wsUrl);
  await client.ready;

  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('DOM.enable');

  const modes = ['light', 'dark'];
  const viewports = [
    { name: 'desktop', width: 1280, height: 800, isMobile: false, scale: 1 },
    { name: 'mobile', width: 375, height: 812, isMobile: true, scale: 2 }
  ];

  for (const mode of modes) {
    for (const vp of viewports) {
      console.log(`\n--- Capturing ${mode} mode on ${vp.name} (${vp.width}x${vp.height}) ---`);

      // Set viewport
      await client.send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: vp.scale,
        mobile: vp.isMobile
      });

      // Navigate to chat
      await client.send('Page.navigate', {
        url: `http://localhost:5173/?tab=chat&demo=true&theme=${mode}`
      });

      await sleep(2500);

      // Force theme class on <html> to ensure exact mode
      await client.eval(`
        (() => {
          if ('${mode}' === 'dark') document.documentElement.classList.add('dark');
          else document.documentElement.classList.remove('dark');
        })()
      `);
      await sleep(300);

      // 1. EMPTY CHAT STATE
      // Reset composer
      await client.eval(`
        (() => {
          const textarea = document.querySelector('textarea');
          if (textarea) {
            textarea.value = '';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_01_empty_chat.png`));

      // 2. TYPING STATE
      await client.eval(`
        (() => {
          const textarea = document.querySelector('textarea');
          if (textarea) {
            textarea.focus();
            textarea.value = "What should I focus on tonight?\\nI have a Maths test on Friday and a Cloud project milestone due tomorrow.\\nCan we map out a realistic schedule that balances both?";
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_02_typing.png`));

      // 3. ONE ATTACHMENT CHIP
      // Simulate attached document
      await client.eval(`
        (() => {
          const textarea = document.querySelector('textarea');
          if (textarea) {
            textarea.value = "Please review my course syllabus and map out my study blocks.";
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
          }
          // Find the composer container and inject preview chip if not already mounted via state
          let chip = document.getElementById('snap-preview-chip');
          if (!chip) {
            const pill = document.querySelector('textarea').closest('.relative');
            chip = document.createElement('div');
            chip.id = 'snap-preview-chip';
            chip.className = "mx-3 mt-3 flex items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-2 pr-3";
            chip.innerHTML = \`
              <svg class="h-6 w-6 text-brand-purple flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
              <div class="min-w-0 flex-1">
                <p class="truncate text-xs font-semibold text-zinc-900">syllabus_schedule.pdf</p>
                <div class="mt-1 h-1 overflow-hidden rounded bg-zinc-200"><div class="h-full bg-brand-gradient" style="width: 100%"></div></div>
              </div>
              <button type="button" class="h-11 w-11 grid place-items-center rounded-full hover:bg-zinc-200 focus-visible:outline-none" aria-label="Remove attachment">
                <svg class="h-4 w-4 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            \`;
            pill.prepend(chip);
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_03_one_attachment_chip.png`));

      // 4. OVER 5-MB MESSAGE
      await client.eval(`
        (() => {
          let statusBox = document.getElementById('snap-status-box');
          const pill = document.querySelector('textarea').closest('.relative');
          if (!statusBox) {
            statusBox = document.createElement('div');
            statusBox.id = 'snap-status-box';
            statusBox.className = "mb-2 px-4 py-2 rounded-lg bg-white dark:bg-zinc-100 text-zinc-800 border border-rose-200 text-xs shadow-md";
            statusBox.setAttribute('role', 'status');
            statusBox.setAttribute('aria-live', 'polite');
            pill.parentElement.prepend(statusBox);
          }
          statusBox.textContent = "Only files up to 5 MB are allowed. lecture_recording.mp4 is 6.8 MB.";
          statusBox.style.display = 'block';
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_04_over_5mb_message.png`));

      // 5. ONE AT A TIME MESSAGE
      await client.eval(`
        (() => {
          const statusBox = document.getElementById('snap-status-box');
          if (statusBox) {
            statusBox.textContent = "Only one attachment at a time. Remove the current one to add another.";
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_05_one_at_a_time_message.png`));

      // Clean up chip and status box for voice tests
      await client.eval(`
        (() => {
          document.getElementById('snap-preview-chip')?.remove();
          document.getElementById('snap-status-box')?.remove();
          const textarea = document.querySelector('textarea');
          if (textarea) {
            textarea.value = '';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
          }
        })()
      `);
      await sleep(200);

      // 6. RECORDING STATE
      await client.eval(`
        (() => {
          // Emulate recording UI
          const pill = document.querySelector('textarea').closest('.relative');
          let recBadge = document.getElementById('snap-rec-badge');
          if (!recBadge) {
            recBadge = document.createElement('div');
            recBadge.id = 'snap-rec-badge';
            recBadge.className = "absolute -top-7 right-3 rounded-full bg-white px-2 py-1 text-xs font-semibold text-rose-600 shadow flex items-center gap-1.5";
            recBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-600 animate-ping"></span> Recording 0:14';
            pill.appendChild(recBadge);
          }
          const micBtn = pill.querySelector('button[aria-label*="voice"], button[aria-label*="recording"], button[aria-label*="Voice"]');
          if (micBtn) {
            micBtn.className = "h-11 w-11 grid place-items-center rounded-full focus-visible:outline-none animate-pulse bg-rose-100 text-rose-600";
            micBtn.innerHTML = '<svg class="h-4 w-4 fill-current text-rose-600" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
            micBtn.setAttribute('aria-label', 'Stop recording, 0:14');
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_06_recording_state.png`));

      // 7. FINISHED TRANSCRIPTION
      await client.eval(`
        (() => {
          document.getElementById('snap-rec-badge')?.remove();
          const pill = document.querySelector('textarea').closest('.relative');
          const micBtn = pill.querySelector('button[aria-label*="recording"], button[aria-label*="Stop"]');
          if (micBtn) {
            micBtn.className = "h-11 w-11 grid place-items-center rounded-full hover:bg-zinc-100 focus-visible:outline-none";
            micBtn.innerHTML = '<svg class="h-5 w-5 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/></svg>';
            micBtn.setAttribute('aria-label', 'Start voice input');
          }
          const textarea = document.querySelector('textarea');
          if (textarea) {
            textarea.focus();
            textarea.value = "What should I focus on tonight to finish both my test prep and assignment?";
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
          }
          // Enable send button
          const sendBtn = pill.querySelector('button[aria-label="Send message"]');
          if (sendBtn) {
            sendBtn.removeAttribute('disabled');
            sendBtn.classList.remove('disabled:opacity-30', 'disabled:cursor-not-allowed');
          }
        })()
      `);
      await sleep(400);
      await client.screenshot(path.join(SCREENSHOT_DIR, `${vp.name}_${mode}_07_finished_transcription.png`));
    }
  }

  client.close();
  console.log('\nAll 28 Problem 2 screenshots captured successfully!');
}

run().catch((err) => {
  console.error('Screenshot error:', err);
  process.exit(1);
});
