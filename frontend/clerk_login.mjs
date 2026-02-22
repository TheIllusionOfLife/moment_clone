import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CLERK_SECRET_KEY = process.env.CLERK_SECRET_KEY;
const USER_ID = process.env.CLERK_USER_ID;
const APP_URL = process.env.APP_URL ?? 'https://moment-clone.vercel.app';
const FAPI = 'allowing-antelope-59.clerk.accounts.dev';
const SCREENSHOTS = process.env.E2E_SCREENSHOTS ?? path.resolve(__dirname, '../e2e-screenshots');

if (!CLERK_SECRET_KEY) throw new Error('CLERK_SECRET_KEY env var is required');
if (!USER_ID) throw new Error('CLERK_USER_ID env var is required');

async function getTestingToken() {
  const r = await fetch('https://api.clerk.com/v1/testing_tokens', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' }
  });
  if (!r.ok) throw new Error(`Clerk testing_tokens failed: ${r.status} ${await r.text()}`);
  const data = await r.json();
  if (!data.token) throw new Error('Clerk testing_tokens: no token in response');
  return data.token;
}

async function getSignInTokenUrl() {
  const r = await fetch('https://api.clerk.com/v1/sign_in_tokens', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${CLERK_SECRET_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER_ID, expires_in_seconds: 300 })
  });
  if (!r.ok) throw new Error(`Clerk sign_in_tokens failed: ${r.status} ${await r.text()}`);
  const data = await r.json();
  if (!data.url) throw new Error('Clerk sign_in_tokens: no url in response');
  return data.url;
}

(async () => {
  const testingToken = await getTestingToken();
  const signInTicketUrl = await getSignInTokenUrl();
  console.log('Got tokens, starting browser...');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Step 1: Load Vercel page to get its dev_browser JWT
  console.log('Step 1: Loading Vercel to get dev_browser JWT...');
  await page.goto(APP_URL + '/', { waitUntil: 'networkidle', timeout: 20000 });
  
  // Wait for Clerk.js to initialize and create dev_browser
  await page.waitForTimeout(3000);
  
  // Get the Vercel dev_browser JWT
  const vercelCookies = await context.cookies([APP_URL]);
  const dvbCookie = vercelCookies.find(c => c.name === '__clerk_db_jwt');
  
  if (!dvbCookie) {
    console.error('ERROR: No __clerk_db_jwt cookie on Vercel domain!');
    const allCookies = await context.cookies();
    console.log('All cookies:', allCookies.map(c => `${c.domain}: ${c.name}`).join(', '));
    await browser.close();
    process.exit(1);
  }
  
  const vercelDvbJwt = dvbCookie.value;
  console.log('Vercel dev_browser JWT:', vercelDvbJwt);

  // Step 2: Set up testing token interceptor for Clerk API calls
  console.log('Step 2: Setting up testing token interceptor...');
  await context.route(`https://${FAPI}/v1/**`, async route => {
    const url = new URL(route.request().url());
    url.searchParams.set('__clerk_testing_token', testingToken);
    try {
      const response = await route.fetch({ url: url.toString() });
      const json = await response.json();
      if (json?.response?.captcha_bypass === false) json.response.captcha_bypass = true;
      if (json?.client?.captcha_bypass === false) json.client.captcha_bypass = true;
      await route.fulfill({ response, json });
    } catch(e) {
      await route.continue({ url: url.toString() }).catch(() => {});
    }
  });

  // Step 3: Navigate to sign-in token URL with Vercel dev_browser JWT
  // This makes accounts.dev USE the same JWT as Vercel, linking the session
  const signInUrl = `${signInTicketUrl}&redirect_url=${encodeURIComponent(APP_URL + '/dashboard')}&__clerk_db_jwt=${vercelDvbJwt}`;
  console.log('Step 3: Navigating to sign-in with Vercel dev_browser JWT...');
  await page.goto(signInUrl, { timeout: 20000 });
  await page.waitForTimeout(5000);
  console.log('After sign-in redirect, URL:', page.url());
  await page.screenshot({ path: `${SCREENSHOTS}/05-after-signin.png` });

  // Step 4: Navigate back to Vercel
  console.log('Step 4: Navigating to Vercel dashboard...');
  await page.goto(APP_URL + '/dashboard', { waitUntil: 'networkidle', timeout: 20000 });
  const finalUrl = page.url();
  console.log('Final URL:', finalUrl);
  await page.screenshot({ path: `${SCREENSHOTS}/06-dashboard.png` });

  if (finalUrl.includes('/dashboard')) {
    console.log('SUCCESS! On dashboard!');
    await context.storageState({ path: '/tmp/clerk_session.json' });
    console.log('Session saved.');
  } else {
    console.log('Still not on dashboard. URL:', finalUrl);
    // Check Clerk state
    const clerkState = await page.evaluate(() => ({
      userId: window.Clerk?.user?.id,
      sessionId: window.Clerk?.session?.id,
    }));
    console.log('Clerk state:', JSON.stringify(clerkState));
  }

  await browser.close();
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
