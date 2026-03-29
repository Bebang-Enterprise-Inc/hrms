import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASS = 'YhPpE4HnaR@adp#L';
const BASE_URL = 'https://ph.employer.seek.com';
const RECRUITMENT_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const USER_DATA_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment/.seek-browser-data';

const chunk = JSON.parse(fs.readFileSync('F:/Dropbox/Projects/BEI-ERP/recruitment/chunk_5.json', 'utf-8'));

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileExists(dir, baseName) {
  for (const ext of ['pdf', 'doc', 'docx', 'rtf']) {
    if (fs.existsSync(path.join(dir, `${baseName}.${ext}`))) return true;
  }
  return false;
}

async function doLogin(page) {
  console.log('  Filling credentials...');
  const emailField = await page.$('input#emailAddress');
  if (emailField) {
    await page.fill('input#emailAddress', SEEK_EMAIL);
    await page.waitForTimeout(500);
    await page.fill('input#password', SEEK_PASS);
    await page.waitForTimeout(500);
  }

  try {
    const frames = page.frames();
    for (const frame of frames) {
      const checkbox = await frame.$('input[type="checkbox"]');
      if (checkbox) {
        await checkbox.click();
        await page.waitForTimeout(3000);
        break;
      }
    }
  } catch (e) { /* ignore */ }

  try {
    await page.click('button:has-text("Sign in")');
  } catch (e) { /* ignore */ }

  console.log('  Waiting for login redirect... (check browser if captcha needed)');
  for (let i = 0; i < 150; i++) {
    await page.waitForTimeout(2000);
    if (!page.url().includes('authenticate.seek.com')) {
      console.log('  Login successful!');
      return true;
    }
  }
  return false;
}

async function main() {
  const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
    headless: false,
    acceptDownloads: true,
    viewport: { width: 1280, height: 900 },
  });

  const pages = context.pages();
  const page = pages.length > 0 ? pages[0] : await context.newPage();

  // Close any extra blank pages
  for (const p of context.pages()) {
    if (p !== page) await p.close();
  }

  let downloaded = 0, skipped = 0, noButton = 0, errors = 0;

  // Navigate to SEEK
  console.log('Navigating to SEEK employer portal...');
  await page.goto(`${BASE_URL}/jobs`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(5000);

  if (page.url().includes('authenticate.seek.com')) {
    const ok = await doLogin(page);
    if (!ok) {
      await context.close();
      process.exit(1);
    }
    await page.waitForTimeout(3000);
  } else {
    console.log('Already logged in!');
  }

  console.log('\n=== Starting download loop ===\n');

  for (let i = 0; i < chunk.length; i++) {
    const { jobId, folder, pid, name } = chunk[i];
    const safeName = sanitize(name);
    const resumeDir = path.join(RECRUITMENT_DIR, folder, 'resumes');
    fs.mkdirSync(resumeDir, { recursive: true });

    if (fileExists(resumeDir, safeName)) {
      console.log(`[${i + 1}/${chunk.length}] SKIP (exists): ${name}`);
      skipped++;
      continue;
    }

    console.log(`[${i + 1}/${chunk.length}] ${name} (pid=${pid})`);

    try {
      const url = `${BASE_URL}/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(6000);

      // Check if session expired
      if (page.url().includes('authenticate.seek.com')) {
        console.log('  Session expired! Re-logging in...');
        const ok = await doLogin(page);
        if (!ok) break;
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForTimeout(6000);
      }

      // Look for download button
      let downloadBtn = await page.$('button[aria-label="Download document"]');
      if (!downloadBtn) downloadBtn = await page.$('button[aria-label*="ownload"]');
      if (!downloadBtn) downloadBtn = await page.$('[aria-label="Download document"]');

      if (!downloadBtn) {
        console.log(`  NO BUTTON`);
        noButton++;
        continue;
      }

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        downloadBtn.click(),
      ]);

      const suggestedName = download.suggestedFilename();
      const ext = suggestedName.includes('.') ? suggestedName.split('.').pop() : 'pdf';
      const destPath = path.join(resumeDir, `${safeName}.${ext}`);

      await download.saveAs(destPath);
      console.log(`  SAVED: ${destPath}`);
      downloaded++;
    } catch (err) {
      const msg = err.message.substring(0, 120);
      console.log(`  ERROR: ${msg}`);
      // If browser/page closed, stop the loop
      if (msg.includes('closed') || msg.includes('destroyed')) {
        console.log('  Browser was closed. Stopping.');
        break;
      }
      errors++;
    }
  }

  try { await context.close(); } catch (e) { /* already closed */ }

  console.log('\n=== RESULTS ===');
  console.log(`Total: ${chunk.length}`);
  console.log(`Downloaded: ${downloaded}`);
  console.log(`Skipped (exists): ${skipped}`);
  console.log(`No button: ${noButton}`);
  console.log(`Errors: ${errors}`);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
