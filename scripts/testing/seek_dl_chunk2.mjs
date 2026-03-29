import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_URL = 'https://ph.employer.seek.com';
const RECRUITMENT_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

const chunk = JSON.parse(fs.readFileSync('F:/Dropbox/Projects/BEI-ERP/recruitment/chunk_2.json', 'utf8'));

function sanitizeName(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileAlreadyExists(resumeDir, sanitized) {
  for (const ext of ['pdf', 'doc', 'docx', 'rtf']) {
    if (fs.existsSync(path.join(resumeDir, `${sanitized}.${ext}`))) return true;
  }
  return false;
}

async function createBrowserAndLogin() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();

  console.log('Logging in...');
  await page.goto(`${BASE_URL}/jobs`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(3000);

  const emailInput = await page.$('input#emailAddress');
  if (emailInput) {
    await emailInput.fill(SEEK_EMAIL);
    await page.waitForTimeout(500);
    const passwordInput = await page.$('input#password');
    if (passwordInput) {
      await passwordInput.fill(SEEK_PASSWORD);
      await page.waitForTimeout(500);
    }
    const signInBtn = page.getByRole('button', { name: 'Sign in' });
    await Promise.all([
      page.waitForURL('**/jobs**', { timeout: 30000 }).catch(() => null),
      signInBtn.click(),
    ]);
    await page.waitForTimeout(5000);
  }
  console.log(`Login complete. URL: ${page.url()}`);
  return { browser, context, page };
}

(async () => {
  let { browser, context, page } = await createBrowserAndLogin();

  const stats = { downloaded: 0, skipped: 0, noButton: 0, errors: 0 };

  for (let i = 0; i < chunk.length; i++) {
    const { jobId, folder, pid, name } = chunk[i];
    const sanitized = sanitizeName(name);
    const resumeDir = path.join(RECRUITMENT_DIR, folder, 'resumes');
    fs.mkdirSync(resumeDir, { recursive: true });

    if (fileAlreadyExists(resumeDir, sanitized)) {
      console.log(`[${i + 1}/${chunk.length}] SKIP (exists): ${name}`);
      stats.skipped++;
      continue;
    }

    let success = false;
    for (let retry = 0; retry < 2; retry++) {
      try {
        // Check if page/browser is still alive
        try {
          await page.evaluate(() => true);
        } catch {
          console.log('  Browser died, relaunching...');
          try { await browser.close(); } catch {}
          ({ browser, context, page } = await createBrowserAndLogin());
        }

        const url = `${BASE_URL}/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
        console.log(`[${i + 1}/${chunk.length}] Navigating for: ${name}${retry > 0 ? ` (retry ${retry})` : ''}`);

        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => null);
        await page.waitForTimeout(5000);

        // Check if redirected to login
        const currentUrl = page.url();
        if (currentUrl.includes('login') || currentUrl.includes('auth')) {
          console.log('  Redirected to login, relaunching browser...');
          try { await browser.close(); } catch {}
          ({ browser, context, page } = await createBrowserAndLogin());
          await page.goto(url, { waitUntil: 'load', timeout: 30000 });
          await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => null);
          await page.waitForTimeout(5000);
        }

        // Wait for download button
        let downloadBtn = null;
        for (let attempt = 0; attempt < 3; attempt++) {
          downloadBtn = await page.$('button[aria-label="Download document"]');
          if (downloadBtn) break;
          downloadBtn = await page.$('[aria-label="Download document"]');
          if (downloadBtn) break;
          await page.waitForTimeout(2000);
        }

        if (!downloadBtn) {
          console.log(`  NO DOWNLOAD BUTTON for: ${name}`);
          stats.noButton++;
          success = true; // Not a retryable error
          break;
        }

        const [download] = await Promise.all([
          page.waitForEvent('download', { timeout: 15000 }),
          downloadBtn.click(),
        ]);

        const suggestedName = download.suggestedFilename();
        const ext = suggestedName.includes('.') ? suggestedName.split('.').pop() : 'pdf';
        const destPath = path.join(resumeDir, `${sanitized}.${ext}`);

        await download.saveAs(destPath);
        console.log(`  DOWNLOADED: ${destPath}`);
        stats.downloaded++;
        success = true;
        break;
      } catch (err) {
        console.log(`  ERROR (attempt ${retry + 1}): ${err.message}`);
        if (retry === 0) {
          // Try relaunching browser for next retry
          try { await browser.close(); } catch {}
          ({ browser, context, page } = await createBrowserAndLogin());
        }
      }
    }

    if (!success) {
      console.log(`  FAILED after retries: ${name}`);
      stats.errors++;
    }
  }

  try { await browser.close(); } catch {}

  console.log('\n=== RESULTS ===');
  console.log(`Downloaded: ${stats.downloaded}`);
  console.log(`Skipped (exists): ${stats.skipped}`);
  console.log(`No button: ${stats.noButton}`);
  console.log(`Errors: ${stats.errors}`);
  console.log(`Total: ${chunk.length}`);
})();
