import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const APP_URL = process.env.APP_URL ?? 'https://moment-clone.vercel.app';
const API_URL = process.env.API_URL ?? 'https://moment-clone-api-mx6vh55q6q-an.a.run.app';
const SCREENSHOTS = process.env.E2E_SCREENSHOTS ?? path.resolve(__dirname, '../docs/e2e-screenshots');
const VIDEO_PATH = process.env.E2E_VIDEO_PATH ?? path.resolve(__dirname, '../sample_video/my_cooking_trimmed.mp4');
const CLERK_SECRET_KEY = process.env.CLERK_SECRET_KEY;
const USER_ID = process.env.CLERK_USER_ID;
const FAPI = 'allowing-antelope-59.clerk.accounts.dev';

if (!CLERK_SECRET_KEY) throw new Error('CLERK_SECRET_KEY env var is required');
if (!USER_ID) throw new Error('CLERK_USER_ID env var is required');

async function getTestingToken() {
  const r = await fetch('https://api.clerk.com/v1/testing_tokens', {
    method: 'POST', headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' }
  });
  if (!r.ok) throw new Error(`Clerk testing_tokens failed: ${r.status} ${await r.text()}`);
  const data = await r.json();
  if (!data.token) throw new Error('Clerk testing_tokens: no token in response');
  return data.token;
}

async function getSignInTokenUrl() {
  const r = await fetch('https://api.clerk.com/v1/sign_in_tokens', {
    method: 'POST', headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER_ID, expires_in_seconds: 300 })
  });
  if (!r.ok) throw new Error(`Clerk sign_in_tokens failed: ${r.status} ${await r.text()}`);
  const data = await r.json();
  if (!data.url) throw new Error('Clerk sign_in_tokens: no url in response');
  return data.url;
}

async function authenticate(context) {
  const testingToken = await getTestingToken();
  const signInTicketUrl = await getSignInTokenUrl();
  const page = await context.newPage();

  await page.goto(APP_URL + '/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  const vercelCookies = await context.cookies([APP_URL]);
  const dvbCookie = vercelCookies.find(c => c.name === '__clerk_db_jwt');
  if (!dvbCookie) throw new Error('No __clerk_db_jwt cookie found on Vercel domain');
  const vercelDvbJwt = dvbCookie.value;
  console.log('  Vercel dvb JWT:', vercelDvbJwt.slice(0, 20) + '...');

  await context.route(`https://${FAPI}/v1/**`, async route => {
    const url = new URL(route.request().url());
    url.searchParams.set('__clerk_testing_token', testingToken);
    try {
      const response = await route.fetch({ url: url.toString() });
      const json = await response.json();
      if (json?.response?.captcha_bypass === false) json.response.captcha_bypass = true;
      if (json?.client?.captcha_bypass === false) json.client.captcha_bypass = true;
      await route.fulfill({ response, json });
    } catch (e) { await route.continue({ url: url.toString() }).catch(() => {}); }
  });

  const signInUrl = `${signInTicketUrl}&redirect_url=${encodeURIComponent(APP_URL + '/dashboard')}&__clerk_db_jwt=${vercelDvbJwt}`;
  await page.goto(signInUrl, { timeout: 20000 });
  await page.waitForTimeout(3000);
  await page.goto(APP_URL + '/dashboard', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  Auth URL:', page.url());
  await page.close();
  return context;
}

async function screenshot(page, name, label) {
  await page.screenshot({ path: `${SCREENSHOTS}/${name}.png`, fullPage: true });
  console.log(`  📸 ${label} → ${name}.png`);
}

// Poll session status directly via Node.js fetch (avoids browser proxy limits and passes auth)
async function pollSession(sessionId, token) {
  try {
    const r = await fetch(`${API_URL}/api/sessions/${sessionId}/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return await r.json();
  } catch (e) { return { error: e.message }; }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });

  console.log('🔐 Authenticating...');
  await authenticate(context);

  const page = await context.newPage();

  // ---- 1. Navigate to upload page ----
  console.log('\n📌 1. Session Upload Page');
  await page.goto(APP_URL + '/sessions/new/fried-rice', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  console.log('  URL:', page.url());
  await screenshot(page, '20-upload-form', 'Upload form (empty)');

  // ---- 2. Attach video file ----
  console.log('\n📌 2. Attaching video file...');
  const videoInput = page.locator('input[type="file"][accept*="mp4"]');
  await videoInput.setInputFiles(VIDEO_PATH);
  await page.waitForTimeout(1000);
  await screenshot(page, '21-upload-file-attached', 'Upload form (file attached)');
  console.log('  File attached:', VIDEO_PATH);

  // ---- 3. Upload video directly from Node.js (bypasses browser fetch / proxy body limits) ----
  console.log('\n📌 3. Uploading video via Node.js fetch (bypasses browser proxy)...');

  // Get the Clerk JWT from the page
  const token = await page.evaluate(() =>
    window.Clerk?.session?.getToken().then(t => t)
  );
  console.log('  JWT obtained:', token ? token.slice(0, 20) + '...' : 'null');

  // Step 3a: Create session via API
  const sessionRes = await fetch(`${API_URL}/api/sessions/`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ dish_slug: 'fried-rice' }),
  });
  const sessionData = await sessionRes.json();
  console.log(`  POST /api/sessions/ → ${sessionRes.status}`, JSON.stringify(sessionData).slice(0, 100));
  if (!sessionRes.ok) throw new Error(`Create session failed: ${JSON.stringify(sessionData)}`);
  const sessionId = sessionData.id;

  // Step 3b: Upload video using native Web API Blob + FormData (Node.js 18+ built-in, no proxy limit)
  console.log(`  Uploading ${VIDEO_PATH} to session ${sessionId}...`);
  const { readFileSync } = await import('fs');
  const fileBuffer = readFileSync(VIDEO_PATH);
  const blob = new Blob([fileBuffer], { type: 'video/mp4' });
  const form = new FormData(); // Web API FormData — compatible with native fetch
  form.append('video', blob, 'my_cooking_short.mp4');

  const uploadRes = await fetch(`${API_URL}/api/sessions/${sessionId}/upload/`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }, // no Content-Type — browser sets multipart boundary
    body: form,
  });
  const uploadData = await uploadRes.json().catch(() => ({}));
  console.log(`  POST /api/sessions/${sessionId}/upload/ → ${uploadRes.status}`, JSON.stringify(uploadData).slice(0, 200));
  if (!uploadRes.ok) throw new Error(`Upload failed: ${JSON.stringify(uploadData)}`);

  // Step 3c: Save ratings
  await fetch(`${API_URL}/api/sessions/${sessionId}/ratings/`, {
    method: 'PATCH',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ appearance: 3, taste: 3, texture: 3, aroma: 3 }),
  });
  console.log('  Ratings saved.');

  // ---- 4. Navigate browser to session detail page ----
  console.log(`\n  Navigating browser to /sessions/${sessionId}...`);
  await page.goto(`${APP_URL}/sessions/${sessionId}`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await screenshot(page, '22-session-uploaded', 'Session detail (uploaded)');

  // ---- 4. Poll pipeline status ----
  console.log('\n📌 4. Polling pipeline status (polls every 15s, timeout 15min)...');
  const MAX_POLLS = 60; // 60 × 15s = 15 min
  let lastStatus = '';

  for (let i = 0; i < MAX_POLLS; i++) {
    const session = await pollSession(sessionId, token);
    const status = session?.status ?? 'unknown';

    if (status !== lastStatus) {
      console.log(`  [${new Date().toISOString()}] status changed: ${lastStatus || '(start)'} → ${status}`);
      lastStatus = status;
      await page.reload({ waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);

      if (status === 'processing') {
        await screenshot(page, '23-session-processing', 'Session (processing)');
      } else if (status === 'text_ready') {
        await screenshot(page, '24-session-text-ready', 'Session (text_ready — coaching text visible)');
        console.log('  Coaching text:', JSON.stringify(session.coaching_text, null, 2));
      } else if (status === 'completed') {
        await screenshot(page, '25-session-completed', 'Session (completed — coaching video visible)');
        console.log('  Coaching video URL:', session.coaching_video_url);
        break;
      } else if (status === 'failed') {
        console.error('  ❌ Pipeline failed:', session.pipeline_error);
        await screenshot(page, '25-session-failed', 'Session (failed)');
        break;
      }
    }

    if (status === 'completed' || status === 'failed') break;
    await new Promise(r => setTimeout(r, 15000));
  }

  // ---- 5. Check coaching chat ----
  console.log('\n📌 5. Coaching chat (should have pipeline message)');
  await page.goto(APP_URL + '/chat/coaching', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(4000);
  await screenshot(page, '26-coaching-chat-after-pipeline', 'Coaching chat (post-pipeline)');

  await page.close();
  await browser.close();
  console.log('\n✅ Upload test complete!');
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
