/**
 * One-shot script: authenticate via Clerk and upload a cooking video to /sessions/new/free.
 * Usage: CLERK_SECRET_KEY=... CLERK_USER_ID=... VIDEO_PATH=... DISH_NAME=... node upload_session.mjs
 */
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const APP_URL       = process.env.APP_URL          ?? 'https://moment-clone.vercel.app';
const CLERK_SK      = process.env.CLERK_SECRET_KEY;
const USER_ID       = process.env.CLERK_USER_ID;
const VIDEO_PATH    = process.env.VIDEO_PATH;
const DISH_NAME     = process.env.DISH_NAME        ?? '自由投稿テスト';
const SCREENSHOTS   = process.env.E2E_SCREENSHOTS  ?? path.resolve(__dirname, '../docs/e2e-screenshots');
const FAPI          = 'allowing-antelope-59.clerk.accounts.dev';

if (!CLERK_SK)   throw new Error('CLERK_SECRET_KEY env var is required');
if (!USER_ID)    throw new Error('CLERK_USER_ID env var is required');
if (!VIDEO_PATH) throw new Error('VIDEO_PATH env var is required');

async function getTestingToken() {
  const r = await fetch('https://api.clerk.com/v1/testing_tokens', {
    method: 'POST',
    headers: { Authorization: `Bearer ${CLERK_SK}`, 'Content-Type': 'application/json' },
  });
  if (!r.ok) throw new Error(`testing_tokens: ${r.status} ${await r.text()}`);
  const d = await r.json();
  if (!d.token) throw new Error('testing_tokens: no token in response');
  return d.token;
}

async function getSignInUrl() {
  const r = await fetch('https://api.clerk.com/v1/sign_in_tokens', {
    method: 'POST',
    headers: { Authorization: `Bearer ${CLERK_SK}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER_ID, expires_in_seconds: 300 }),
  });
  if (!r.ok) throw new Error(`sign_in_tokens: ${r.status} ${await r.text()}`);
  const d = await r.json();
  if (!d.url) throw new Error('sign_in_tokens: no url in response');
  return d.url;
}

(async () => {
  const [testingToken, signInTicketUrl] = await Promise.all([getTestingToken(), getSignInUrl()]);
  console.log('Tokens obtained. Launching browser...');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  // ── Step 1: get Vercel dev_browser JWT ──────────────────────────────────────
  const page = await context.newPage();
  await page.goto(APP_URL + '/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  const cookies = await context.cookies([APP_URL]);
  const dvb = cookies.find(c => c.name === '__clerk_db_jwt');
  if (!dvb) throw new Error('No __clerk_db_jwt on Vercel domain — Clerk.js did not initialise');
  console.log('dvb JWT:', dvb.value.slice(0, 20) + '...');

  // ── Step 2: intercept Clerk FAPI to inject testing token ────────────────────
  await context.route(`https://${FAPI}/v1/**`, async route => {
    const url = new URL(route.request().url());
    url.searchParams.set('__clerk_testing_token', testingToken);
    try {
      const response = await route.fetch({ url: url.toString() });
      const json = await response.json();
      if (json?.response?.captcha_bypass === false) json.response.captcha_bypass = true;
      if (json?.client?.captcha_bypass === false)   json.client.captcha_bypass   = true;
      await route.fulfill({ response, json });
    } catch {
      await route.continue({ url: url.toString() }).catch(() => {});
    }
  });

  // ── Step 3: sign in via one-time token URL ───────────────────────────────────
  const signInUrl = `${signInTicketUrl}&redirect_url=${encodeURIComponent(APP_URL + '/dashboard')}&__clerk_db_jwt=${dvb.value}`;
  console.log('Signing in...');
  await page.goto(signInUrl, { timeout: 20000 });
  await page.waitForTimeout(4000);
  console.log('After sign-in URL:', page.url());
  await page.screenshot({ path: `${SCREENSHOTS}/upload-01-after-signin.png` });

  // ── Step 4: navigate to upload page ─────────────────────────────────────────
  await page.goto(APP_URL + '/sessions/new/free', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('Upload page URL:', page.url());
  await page.screenshot({ path: `${SCREENSHOTS}/upload-02-upload-page.png` });

  if (!page.url().includes('/sessions/new/free')) {
    console.error('ERROR: Did not reach upload page. Got:', page.url());
    await browser.close();
    process.exit(1);
  }

  // ── Step 5: fill dish name ───────────────────────────────────────────────────
  console.log('Filling dish name:', DISH_NAME);
  const dishInput = page.locator('input[placeholder="例: 鶏の唐揚げ、ナポリタン..."]');
  await dishInput.waitFor({ timeout: 10000 });
  await dishInput.fill(DISH_NAME);
  await page.screenshot({ path: `${SCREENSHOTS}/upload-03-dish-name.png` });

  // ── Step 6: attach video file ────────────────────────────────────────────────
  console.log('Attaching video:', VIDEO_PATH);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(VIDEO_PATH);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOTS}/upload-04-file-selected.png` });

  // ── Step 7: star ratings — click 3 stars for each of the 4 rating categories
  // aria-label format: "見た目 3点", "味 3点", "食感 3点", "香り 3点"
  for (const label of ['見た目', '味', '食感', '香り']) {
    const star3 = page.locator(`button[aria-label="${label} 3点"]`);
    await star3.click();
  }
  await page.screenshot({ path: `${SCREENSHOTS}/upload-05-ratings.png` });

  // ── Step 8: capture network responses and console errors ────────────────────
  const apiErrors = [];
  page.on('response', async resp => {
    if (resp.url().includes('/api/') && resp.status() >= 400) {
      try { apiErrors.push(`${resp.status()} ${resp.url()} → ${await resp.text()}`); }
      catch { apiErrors.push(`${resp.status()} ${resp.url()}`); }
    }
  });
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('  [browser error]', msg.text());
  });

  // ── Step 9: submit ───────────────────────────────────────────────────────────
  console.log('Submitting upload...');
  const submitBtn = page.locator('button', { hasText: 'アップロードしてAI分析を開始' });
  await submitBtn.waitFor({ timeout: 5000 });
  await submitBtn.click();

  // Wait for upload to complete (status changes / redirect)
  console.log('Waiting for upload response...');
  await page.waitForTimeout(15000);
  await page.screenshot({ path: `${SCREENSHOTS}/upload-06-after-submit.png` });
  console.log('Post-submit URL:', page.url());
  // Scroll to top to see any error banners
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${SCREENSHOTS}/upload-06b-top.png` });
  if (apiErrors.length) console.log('API errors:', apiErrors);

  // Poll for a bit if still on the same page
  for (let i = 0; i < 6; i++) {
    await page.waitForTimeout(5000);
    const url = page.url();
    console.log(`  [${i+1}/6] URL:`, url);
    await page.screenshot({ path: `${SCREENSHOTS}/upload-07-poll-${i+1}.png` });
    if (url.includes('/sessions/') && !url.includes('/new/')) break;
  }

  console.log('\nDone. Screenshots saved to:', SCREENSHOTS);
  await browser.close();
})().catch(e => { console.error('Fatal:', e.message); process.exit(1); });
