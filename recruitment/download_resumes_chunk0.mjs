import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import { join, extname } from 'path';

const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const CHUNK_FILE = join(BASE_DIR, 'chunk_0.json');
const candidates = JSON.parse(readFileSync(CHUNK_FILE, 'utf-8'));

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.\-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function alreadyExists(dir, sanitizedName) {
  for (const ext of ['.pdf', '.doc', '.docx', '.rtf']) {
    if (existsSync(join(dir, sanitizedName + ext))) return true;
  }
  return false;
}

async function doAuth0Login(page) {
  // Navigate to a protected page to trigger Auth0 redirect
  console.log('Navigating to candidates page to trigger login...');
  const firstCandidate = candidates[0];
  await page.goto(
    `https://ph.employer.seek.com/candidates/?jobid=${firstCandidate.jobId}&selected=${firstCandidate.pid}&tab=resume`,
    { waitUntil: 'load', timeout: 60000 }
  );
  await page.waitForTimeout(5000);

  const url = page.url();
  console.log('URL after navigating to protected page:', url);

  if (!url.includes('authenticate') && !url.includes('login') && !url.includes('auth0')) {
    console.log('Already logged in or no redirect. Checking page...');
    // Maybe we are logged in already
    return;
  }

  // We should now be on the Auth0 login page
  console.log('On Auth0 login page. Waiting for form to render...');
  await page.waitForTimeout(3000);

  // Screenshot for debugging
  await page.screenshot({ path: join(BASE_DIR, 'debug_login_1.png') });

  // Try to find email input
  let emailInput = null;
  const emailSelectors = [
    'input[name="email"]',
    'input[type="email"]',
    '#email',
    '#username',
    'input[name="username"]',
    'input[inputmode="email"]',
  ];

  for (const sel of emailSelectors) {
    try {
      emailInput = await page.$(sel);
      if (emailInput) {
        console.log(`Found email input: ${sel}`);
        break;
      }
    } catch (e) { /* next */ }
  }

  if (!emailInput) {
    // Maybe the page uses iframes
    const frames = page.frames();
    console.log(`Found ${frames.length} frames`);
    for (const frame of frames) {
      for (const sel of emailSelectors) {
        try {
          emailInput = await frame.$(sel);
          if (emailInput) {
            console.log(`Found email input in frame: ${sel}`);
            break;
          }
        } catch (e) { /* next */ }
      }
      if (emailInput) break;
    }
  }

  if (!emailInput) {
    // Log visible inputs for debugging
    const inputs = await page.$$eval('input', els =>
      els.map(el => ({ type: el.type, name: el.name, id: el.id, placeholder: el.placeholder }))
    );
    console.log('Visible inputs:', JSON.stringify(inputs, null, 2));
    const html = await page.content();
    console.log('Page title:', await page.title());
    // Save full HTML for debug
    const { writeFileSync } = await import('fs');
    writeFileSync(join(BASE_DIR, 'debug_login_page.html'), html);
    throw new Error('Could not find email input');
  }

  // Type email slowly to trigger any JS handlers
  await emailInput.click();
  await emailInput.fill(EMAIL);
  console.log('Filled email');
  await page.waitForTimeout(1000);

  // Click continue/submit
  const submitBtn = await page.$('button[type="submit"]');
  if (submitBtn) {
    await submitBtn.click();
    console.log('Clicked submit after email');
    await page.waitForTimeout(3000);
  }

  await page.screenshot({ path: join(BASE_DIR, 'debug_login_2.png') });

  // Find password field
  let passwordInput = null;
  for (const sel of ['input[type="password"]', 'input[name="password"]', '#password']) {
    try {
      passwordInput = await page.waitForSelector(sel, { timeout: 10000 });
      if (passwordInput) {
        console.log(`Found password input: ${sel}`);
        break;
      }
    } catch (e) { /* next */ }
  }

  if (!passwordInput) {
    // Maybe email + password on same page
    const inputs = await page.$$eval('input', els =>
      els.map(el => ({ type: el.type, name: el.name, id: el.id }))
    );
    console.log('Inputs after email step:', JSON.stringify(inputs));
    throw new Error('Could not find password input');
  }

  await passwordInput.click();
  await passwordInput.fill(PASSWORD);
  console.log('Filled password');
  await page.waitForTimeout(1000);

  // Click sign in
  const signInBtn = await page.$('button[type="submit"]');
  if (signInBtn) {
    await signInBtn.click();
    console.log('Clicked sign in');
  }

  // Wait for redirect back to employer portal
  console.log('Waiting for post-login redirect...');
  try {
    await page.waitForURL('**/ph.employer.seek.com/**', { timeout: 30000 });
    console.log('Redirected to:', page.url());
  } catch (e) {
    console.log('Redirect wait timed out. Current URL:', page.url());
  }
  await page.waitForTimeout(5000);
  await page.screenshot({ path: join(BASE_DIR, 'debug_login_3.png') });

  const finalUrl = page.url();
  console.log('Final URL after login:', finalUrl);

  if (finalUrl.includes('authenticate') || finalUrl.includes('auth0')) {
    throw new Error(`Login failed. Still on auth page: ${finalUrl}`);
  }

  console.log('Login successful!');
}

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1280, height: 720 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  let downloaded = 0;
  let skipped = 0;
  let noButton = 0;
  let loginErrors = 0;

  // Do login once
  await doAuth0Login(page);

  for (let i = 0; i < candidates.length; i++) {
    const { jobId, folder, pid, name } = candidates[i];
    const sanitizedName = sanitize(name);
    const resumeDir = join(BASE_DIR, folder, 'resumes');
    mkdirSync(resumeDir, { recursive: true });

    if (alreadyExists(resumeDir, sanitizedName)) {
      console.log(`[${i + 1}/${candidates.length}] SKIP (exists): ${name}`);
      skipped++;
      continue;
    }

    const url = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
    console.log(`[${i + 1}/${candidates.length}] Loading: ${name} ...`);

    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(4000);

      // Check if we got kicked to login
      const currentUrl = page.url();
      if (currentUrl.includes('authenticate') || currentUrl.includes('login')) {
        console.log('  Session expired, re-logging in...');
        await doAuth0Login(page);
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForTimeout(4000);

        if (page.url().includes('authenticate') || page.url().includes('login')) {
          console.log(`  LOGIN FAILED for: ${name}`);
          loginErrors++;
          continue;
        }
      }

      // Look for download button
      let downloadBtn = null;
      const downloadSelectors = [
        'button[aria-label="Download document"]',
        'a[aria-label="Download document"]',
        '[data-testid*="download"]',
        'button:has-text("Download")',
        'a:has-text("Download")',
      ];

      // Wait a bit more for SPA content to load
      await page.waitForTimeout(2000);

      for (const sel of downloadSelectors) {
        try {
          downloadBtn = await page.$(sel);
          if (downloadBtn) {
            console.log(`  Found download button: ${sel}`);
            break;
          }
        } catch (e) { /* try next */ }
      }

      if (!downloadBtn) {
        console.log(`  NO DOWNLOAD BUTTON: ${name}`);
        noButton++;
        continue;
      }

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        downloadBtn.click(),
      ]);
      const ext = extname(download.suggestedFilename()) || '.pdf';
      const savePath = join(resumeDir, sanitizedName + ext);
      await download.saveAs(savePath);
      console.log(`  DOWNLOADED: ${sanitizedName}${ext}`);
      downloaded++;
    } catch (err) {
      console.log(`  ERROR: ${name} - ${err.message}`);
      loginErrors++;
    }
  }

  await browser.close();

  console.log('\n=== RESULTS ===');
  console.log(`Downloaded: ${downloaded}`);
  console.log(`Skipped (existed): ${skipped}`);
  console.log(`No button: ${noButton}`);
  console.log(`Errors: ${loginErrors}`);
  console.log(`Total: ${candidates.length}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
