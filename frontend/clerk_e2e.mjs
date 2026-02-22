import { chromium } from 'playwright';

const APP_URL = 'https://moment-clone.vercel.app';
const SCREENSHOTS = '/Users/yuyamukai/dev/moment_clone/e2e-screenshots';
const CLERK_SECRET_KEY = 'sk_test_sTpAeaiiNOIPTUu67vkpkFCdXFNiR2goMLqBvUCK7Z';
const USER_ID = 'user_3A0NGXZ8GGu2F47cWcU6LYgkpgV';
const FAPI = 'allowing-antelope-59.clerk.accounts.dev';

async function getTestingToken() {
  const r = await fetch('https://api.clerk.com/v1/testing_tokens', {
    method: 'POST', headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' }
  });
  return (await r.json()).token;
}

async function getSignInTokenUrl() {
  const r = await fetch('https://api.clerk.com/v1/sign_in_tokens', {
    method: 'POST', headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER_ID, expires_in_seconds: 300 })
  });
  return (await r.json()).url;
}

async function authenticate(context) {
  const testingToken = await getTestingToken();
  const signInTicketUrl = await getSignInTokenUrl();
  const page = await context.newPage();

  // Get Vercel dev_browser JWT
  await page.goto(APP_URL + '/', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);
  const vercelCookies = await context.cookies([APP_URL]);
  const dvbCookie = vercelCookies.find(c => c.name === '__clerk_db_jwt');
  const vercelDvbJwt = dvbCookie?.value;
  console.log('  Vercel dvb JWT:', vercelDvbJwt?.slice(0,20) + '...');

  // Set up testing token interceptor
  await context.route(`https://${FAPI}/v1/**`, async route => {
    const url = new URL(route.request().url());
    url.searchParams.set('__clerk_testing_token', testingToken);
    try {
      const response = await route.fetch({ url: url.toString() });
      const json = await response.json();
      if (json?.response?.captcha_bypass === false) json.response.captcha_bypass = true;
      if (json?.client?.captcha_bypass === false) json.client.captcha_bypass = true;
      await route.fulfill({ response, json });
    } catch(e) { await route.continue({ url: url.toString() }).catch(() => {}); }
  });

  const signInUrl = `${signInTicketUrl}&redirect_url=${encodeURIComponent(APP_URL + '/dashboard')}&__clerk_db_jwt=${vercelDvbJwt}`;
  await page.goto(signInUrl, { timeout: 20000 });
  await page.waitForTimeout(3000);
  await page.goto(APP_URL + '/dashboard', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  Auth result URL:', page.url());
  await page.close();
  return context;
}

async function screenshot(page, name, label) {
  await page.waitForTimeout(4000); // allow TanStack Query to fetch and render
  await page.screenshot({ path: `${SCREENSHOTS}/${name}.png`, fullPage: true });
  console.log(`  📸 ${label} → ${name}.png`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });

  console.log('🔐 Authenticating...');
  await authenticate(context);

  const page = await context.newPage();

  // ---- 1. Dashboard ----
  console.log('\n📌 1. Dashboard');
  await page.goto(APP_URL + '/dashboard', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '07-dashboard', 'Dashboard');
  const dashboardText = await page.textContent('body');
  console.log('  Has dishes?', dashboardText.includes('チャーハン') || dashboardText.includes('fried') || dashboardText.includes('dish'));

  // ---- 2. Onboarding ----
  console.log('\n📌 2. Onboarding');
  await page.goto(APP_URL + '/onboarding', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '08-onboarding', 'Onboarding');

  // ---- 3. Dish Detail ----
  console.log('\n📌 3. Dish Detail - fried-rice');
  await page.goto(APP_URL + '/dishes/fried-rice', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '09-dish-detail', 'Dish Detail');

  // ---- 4. New Session Upload ----
  console.log('\n📌 4. Session Upload Page');
  await page.goto(APP_URL + '/sessions/new/fried-rice', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '10-session-upload', 'Session Upload');

  // ---- 5. Coaching Chat ----
  console.log('\n📌 5. Coaching Chat');
  await page.goto(APP_URL + '/chat/coaching', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '11-coaching-chat', 'Coaching Chat');

  // ---- 6. Cooking Videos Chat ----
  console.log('\n📌 6. Cooking Videos Chat');
  await page.goto(APP_URL + '/chat/cooking-videos', { waitUntil: 'networkidle', timeout: 20000 });
  console.log('  URL:', page.url());
  await screenshot(page, '12-cooking-videos-chat', 'Cooking Videos Chat');

  // ---- 7. API health check ----
  console.log('\n📌 7. API endpoints via fetch');
  const apiUrl = 'https://moment-clone-api-mx6vh55q6q-an.a.run.app';
  const apiResult = await page.evaluate(async (url) => {
    try {
      const r = await fetch(`${url}/health`);
      return { status: r.status, ok: r.ok };
    } catch(e) { return { error: e.message }; }
  }, apiUrl);
  console.log('  API health:', JSON.stringify(apiResult));

  await page.close();
  await browser.close();
  console.log('\n✅ E2E screenshots complete!');
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
