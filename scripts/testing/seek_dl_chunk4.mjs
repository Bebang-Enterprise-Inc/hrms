import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

const candidates = JSON.parse(fs.readFileSync('F:/Dropbox/Projects/BEI-ERP/recruitment/chunk_4.json', 'utf-8'));

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileExists(folder, sanitizedName) {
  const resumeDir = path.join(BASE_DIR, folder, 'resumes');
  for (const ext of ['pdf', 'doc', 'docx', 'rtf']) {
    if (fs.existsSync(path.join(resumeDir, `${sanitizedName}.${ext}`))) return true;
  }
  return false;
}

async function login(page) {
  console.log('Logging in to SEEK...');
  await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(5000);

  // Take a screenshot to see what we're dealing with
  const url = page.url();
  console.log('  Current URL after goto /jobs:', url);

  // Wait for either email field or jobs page content
  try {
    await page.waitForSelector('input#emailAddress', { timeout: 10000 });
    console.log('  Found login form, filling credentials...');
    await page.fill('input#emailAddress', SEEK_EMAIL);
    await page.waitForTimeout(500);
    await page.fill('input#password', SEEK_PASSWORD);
    await page.waitForTimeout(500);
    await page.click('button:has-text("Sign in")');
    await page.waitForTimeout(8000);
    console.log('  Login submitted, current URL:', page.url());
  } catch {
    console.log('  No login form found (possibly already logged in)');
    console.log('  Page title:', await page.title());
  }
}

async function needsLogin(page) {
  const url = page.url();
  if (url.includes('/authenticate') || url.includes('/login') || url.includes('/sign-in') || url.includes('oauth')) {
    return true;
  }
  // Also check for login form on page
  const emailField = await page.$('input#emailAddress');
  return !!emailField;
}

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();

  // Login first
  await login(page);

  // After login, verify we're actually logged in by navigating to a candidates page
  console.log('Verifying login state...');
  await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(3000);
  console.log('Post-login URL:', page.url());
  console.log('Post-login title:', await page.title());

  let downloaded = 0, skipped = 0, noButton = 0, errors = 0;

  for (let i = 0; i < candidates.length; i++) {
    const { jobId, folder, pid, name } = candidates[i];
    const sanitizedName = sanitize(name);
    const resumeDir = path.join(BASE_DIR, folder, 'resumes');

    // Ensure directory exists
    fs.mkdirSync(resumeDir, { recursive: true });

    // Skip if already exists
    if (fileExists(folder, sanitizedName)) {
      console.log(`[${i + 1}/${candidates.length}] SKIP (exists): ${name}`);
      skipped++;
      continue;
    }

    console.log(`[${i + 1}/${candidates.length}] Processing: ${name} (pid=${pid})`);

    try {
      const url = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(4000);

      const currentUrl = page.url();
      console.log(`  URL after nav: ${currentUrl}`);

      // Check if redirected to login
      if (await needsLogin(page)) {
        console.log('  Session expired, re-logging in...');
        await login(page);
        // Retry the candidate page
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForTimeout(4000);

        if (await needsLogin(page)) {
          console.log('  STILL on login page after re-login, skipping');
          errors++;
          continue;
        }
      }

      // Look for download button with multiple selectors
      let downloadBtn = await page.$('button[aria-label="Download document"]');
      if (!downloadBtn) {
        // Try waiting a bit more
        await page.waitForTimeout(3000);
        downloadBtn = await page.$('button[aria-label="Download document"]');
      }
      if (!downloadBtn) {
        // Try alternate selectors
        downloadBtn = await page.$('[aria-label="Download document"]');
      }
      if (!downloadBtn) {
        console.log(`  NO DOWNLOAD BUTTON for ${name}`);
        noButton++;
        continue;
      }

      // Click and wait for download
      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        downloadBtn.click(),
      ]);

      const suggestedName = download.suggestedFilename();
      const ext = suggestedName.includes('.') ? suggestedName.split('.').pop() : 'pdf';
      const destPath = path.join(resumeDir, `${sanitizedName}.${ext}`);

      await download.saveAs(destPath);
      console.log(`  SAVED: ${destPath}`);
      downloaded++;
    } catch (err) {
      console.log(`  ERROR for ${name}: ${err.message}`);
      errors++;
    }
  }

  await browser.close();

  console.log('\n=== RESULTS ===');
  console.log(`Downloaded: ${downloaded}`);
  console.log(`Skipped (exists): ${skipped}`);
  console.log(`No download button: ${noButton}`);
  console.log(`Errors: ${errors}`);
  console.log(`Total candidates: ${candidates.length}`);
})();
