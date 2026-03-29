import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import { join, extname } from 'path';

const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const CHUNK_FILE = join(BASE_DIR, 'chunk_0.json');
const allCandidates = JSON.parse(readFileSync(CHUNK_FILE, 'utf-8'));

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.\-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function alreadyExists(dir, sanitizedName) {
  for (const ext of ['.pdf', '.doc', '.docx', '.rtf', '.txt']) {
    if (existsSync(join(dir, sanitizedName + ext))) return true;
  }
  return false;
}

// Filter to only missing candidates
const candidates = allCandidates.filter(c => {
  const sn = sanitize(c.name);
  const dir = join(BASE_DIR, c.folder, 'resumes');
  return !alreadyExists(dir, sn);
});

console.log(`${candidates.length} candidates still need resumes (out of ${allCandidates.length} total)`);
if (candidates.length === 0) {
  console.log('All done!');
  process.exit(0);
}

async function doAuth0Login(page) {
  console.log('Navigating to protected page to trigger login...');
  await page.goto(
    `https://ph.employer.seek.com/candidates/?jobid=${candidates[0].jobId}&selected=${candidates[0].pid}&tab=resume`,
    { waitUntil: 'load', timeout: 60000 }
  );
  await page.waitForTimeout(5000);

  const url = page.url();
  console.log('URL:', url);

  if (!url.includes('authenticate') && !url.includes('login') && !url.includes('auth0')) {
    console.log('Already logged in!');
    return;
  }

  console.log('On Auth0 login page...');
  await page.waitForTimeout(3000);

  // Email
  const emailInput = await page.waitForSelector('input[type="email"]', { timeout: 15000 });
  await emailInput.fill(EMAIL);
  console.log('Filled email');
  await page.waitForTimeout(1000);

  const submitBtn1 = await page.$('button[type="submit"]');
  if (submitBtn1) {
    await submitBtn1.click();
    console.log('Clicked continue');
    await page.waitForTimeout(3000);
  }

  // Password
  const passwordInput = await page.waitForSelector('input[type="password"]', { timeout: 15000 });
  await passwordInput.fill(PASSWORD);
  console.log('Filled password');
  await page.waitForTimeout(1000);

  const submitBtn2 = await page.$('button[type="submit"]');
  if (submitBtn2) {
    await submitBtn2.click();
    console.log('Clicked sign in');
  }

  // Wait for redirect
  try {
    await page.waitForURL('**/ph.employer.seek.com/**', { timeout: 30000 });
  } catch (e) {
    console.log('Redirect timeout, URL:', page.url());
  }
  await page.waitForTimeout(5000);

  const finalUrl = page.url();
  console.log('Post-login URL:', finalUrl);
  if (finalUrl.includes('authenticate') || finalUrl.includes('auth0')) {
    throw new Error(`Login failed: ${finalUrl}`);
  }
  console.log('Login OK!');
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
  let noButton = 0;
  let errors = 0;

  await doAuth0Login(page);

  for (let i = 0; i < candidates.length; i++) {
    const { jobId, folder, pid, name } = candidates[i];
    const sanitizedName = sanitize(name);
    const resumeDir = join(BASE_DIR, folder, 'resumes');
    mkdirSync(resumeDir, { recursive: true });

    const url = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
    console.log(`[${i + 1}/${candidates.length}] Loading: ${name} ...`);

    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(4000);

      // Re-login if needed
      if (page.url().includes('authenticate') || page.url().includes('login')) {
        console.log('  Session expired, re-logging in...');
        await doAuth0Login(page);
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForTimeout(4000);
      }

      // Wait extra for SPA to render
      await page.waitForTimeout(2000);

      // Look for download button
      const downloadBtn = await page.$('button[aria-label="Download document"]')
        || await page.$('a[aria-label="Download document"]');

      if (!downloadBtn) {
        console.log(`  NO DOWNLOAD BUTTON: ${name} (candidate may not have uploaded a resume)`);
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
      errors++;
    }
  }

  await browser.close();

  console.log('\n=== RETRY RESULTS ===');
  console.log(`Downloaded: ${downloaded}`);
  console.log(`No button (no resume uploaded): ${noButton}`);
  console.log(`Errors: ${errors}`);
  console.log(`Total attempted: ${candidates.length}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
