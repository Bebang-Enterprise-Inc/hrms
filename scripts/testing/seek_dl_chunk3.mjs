import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const STATE_FILE = 'F:/Dropbox/Projects/BEI-ERP/recruitment/.seek-auth-state.json';

const candidates = JSON.parse(fs.readFileSync('F:/Dropbox/Projects/BEI-ERP/recruitment/chunk_3.json', 'utf8'));

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileExists(dir, baseName) {
  for (const ext of ['pdf', 'doc', 'docx', 'rtf']) {
    if (fs.existsSync(path.join(dir, `${baseName}.${ext}`))) return true;
  }
  return false;
}

async function login(page) {
  console.log('Logging in to SEEK...');
  await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(5000);

  const emailInput = await page.$('input#emailAddress');
  if (emailInput) {
    await emailInput.fill(SEEK_EMAIL);
    await page.waitForTimeout(500);
    const passwordInput = await page.$('input#password');
    if (passwordInput) {
      await passwordInput.fill(SEEK_PASSWORD);
    }
    await page.waitForTimeout(500);
    const signInBtn = await page.$('button:has-text("Sign in")');
    if (signInBtn) {
      await signInBtn.click();
    }
    await page.waitForTimeout(10000);
    console.log('Login submitted.');
  } else {
    console.log('Already logged in.');
  }

  await page.context().storageState({ path: STATE_FILE });
  console.log('Auth state saved.');
}

async function createBrowserAndPage() {
  const browser = await chromium.launch({ headless: false });
  let contextOptions = { acceptDownloads: true };
  if (fs.existsSync(STATE_FILE)) {
    console.log('Loading saved auth state...');
    contextOptions.storageState = STATE_FILE;
  }
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  return { browser, context, page };
}

async function main() {
  let { browser, context, page } = await createBrowserAndPage();
  await login(page);

  let downloaded = 0, skipped = 0, noButton = 0, errors = 0;
  const MAX_RETRIES = 2;

  for (let i = 0; i < candidates.length; i++) {
    const c = candidates[i];
    const safeName = sanitize(c.name);
    const resumeDir = path.join(BASE_DIR, c.folder, 'resumes');

    fs.mkdirSync(resumeDir, { recursive: true });

    if (fileExists(resumeDir, safeName)) {
      console.log(`[${i + 1}/${candidates.length}] SKIP (exists): ${c.name}`);
      skipped++;
      continue;
    }

    console.log(`[${i + 1}/${candidates.length}] Processing: ${c.name} (pid=${c.pid})`);

    let success = false;
    for (let attempt = 0; attempt < MAX_RETRIES && !success; attempt++) {
      try {
        // Test if browser is still alive
        try {
          await page.evaluate(() => true);
        } catch {
          console.log('  Browser crashed, re-launching...');
          try { await browser.close(); } catch {}
          ({ browser, context, page } = await createBrowserAndPage());
          await login(page);
        }

        const url = `https://ph.employer.seek.com/candidates/?jobid=${c.jobId}&selected=${c.pid}&tab=resume`;
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForTimeout(4000);

        // Check for login redirect
        const currentUrl = page.url();
        if (currentUrl.includes('/auth/') || currentUrl.includes('/login') || currentUrl.includes('/authenticate')) {
          console.log('  Redirected to login, re-authenticating...');
          await login(page);
          await page.goto(url, { waitUntil: 'load', timeout: 30000 });
          await page.waitForTimeout(4000);
        }

        // Wait for download button
        let downloadBtn = null;
        try {
          downloadBtn = await page.waitForSelector('button[aria-label="Download document"]', { timeout: 8000 });
        } catch {
          downloadBtn = await page.$('[data-testid="download-resume-button"]')
            || await page.$('button:has-text("Download")');
        }

        if (!downloadBtn) {
          console.log(`  NO DOWNLOAD BUTTON for ${c.name}`);
          noButton++;
          success = true; // Don't retry, just skip
          continue;
        }

        const [download] = await Promise.all([
          page.waitForEvent('download', { timeout: 15000 }),
          downloadBtn.click(),
        ]);

        const suggestedName = download.suggestedFilename();
        const ext = suggestedName.includes('.') ? suggestedName.split('.').pop().toLowerCase() : 'pdf';
        const finalName = `${safeName}.${ext}`;
        const savePath = path.join(resumeDir, finalName);

        await download.saveAs(savePath);
        console.log(`  DOWNLOADED: ${finalName}`);
        downloaded++;
        success = true;

        // Save state every 5 downloads
        if (downloaded % 5 === 0) {
          await context.storageState({ path: STATE_FILE });
        }
      } catch (err) {
        console.log(`  ERROR (attempt ${attempt + 1}): ${err.message}`);
        if (attempt === MAX_RETRIES - 1) {
          errors++;
        }
      }
    }
  }

  try { await browser.close(); } catch {}

  console.log('\n=== RESULTS ===');
  console.log(`Total candidates: ${candidates.length}`);
  console.log(`Downloaded: ${downloaded}`);
  console.log(`Skipped (exists): ${skipped}`);
  console.log(`No download button: ${noButton}`);
  console.log(`Errors: ${errors}`);
}

main().catch(console.error);
