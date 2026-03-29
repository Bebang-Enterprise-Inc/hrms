/**
 * Download resumes for 3 specific candidates from SEEK job 91094834.
 * Built using only the jobstreet-bei-erp skill instructions.
 *
 * Usage: node recruitment/eval-test-2/download.mjs
 */

import { chromium } from 'playwright';
import { join } from 'path';
import { existsSync } from 'fs';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const JOB_ID = 91094834;
const RESUME_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment/eval-test-2/resumes';

const CANDIDATES = [
  { pid: '2089088724', name: 'WILLY GALLEGO' },
  { pid: '2089572392', name: 'Norman Roy Seguritan' },
  { pid: '2088127574', name: 'Dionne Carlo Camosa' },
];

function safeName(name) {
  return name.replace(/[^a-zA-Z0-9 ]/g, '').replace(/\s+/g, '_');
}

async function ensureLoggedIn(page) {
  if (page.url().includes('login') || page.url().includes('authenticate')) {
    console.log('  Session lost — re-logging in...');
    await page.waitForTimeout(2000);
    const ef = page.locator('input[id="emailAddress"]');
    if (await ef.isVisible({ timeout: 5000 }).catch(() => false)) {
      await ef.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000);
    }
  }
}

async function main() {
  // Use persistent context to help with anti-bot and session retention
  const context = await chromium.launchPersistentContext(
    'F:/Dropbox/Projects/BEI-ERP/recruitment/.seek-browser-data/',
    {
      headless: false,
      acceptDownloads: true,
    }
  );

  const page = context.pages()[0] || await context.newPage();

  try {
    // Step 1: Login — navigate to jobs page which triggers OAuth if needed
    console.log('Navigating to SEEK employer portal...');
    await page.goto('https://ph.employer.seek.com/jobs', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    await page.waitForTimeout(3000);

    // Fill login form if it appears
    const emailField = page.locator('input[id="emailAddress"]');
    if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('Login form detected — signing in...');
      await emailField.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000); // OAuth redirect takes time
    } else {
      console.log('Already logged in (no login form visible).');
    }

    // Step 2: Download resume for each candidate
    for (const candidate of CANDIDATES) {
      const safe = safeName(candidate.name);
      console.log(`\nProcessing: ${candidate.name} (${candidate.pid})`);

      // Check if already downloaded (pdf, doc, docx, rtf)
      const extensions = ['pdf', 'doc', 'docx', 'rtf'];
      const alreadyExists = extensions.some(ext =>
        existsSync(join(RESUME_DIR, `${safe}.${ext}`))
      );
      if (alreadyExists) {
        console.log(`  Skipped — file already exists for ${safe}`);
        continue;
      }

      // Navigate to the candidate's resume tab
      const url = `https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}&selected=${candidate.pid}&tab=resume`;
      await page.goto(url, { waitUntil: 'load', timeout: 20000 });
      await page.waitForTimeout(4000); // SPA needs 4s to render the resume viewer
      await ensureLoggedIn(page);       // Check for session loss after EVERY goto

      // The download button — 4th icon in the toolbar above the PDF viewer
      // aria-label="Download document" is the ONLY reliable selector
      const dlBtn = page.locator('button[aria-label="Download document"]').first();

      if (await dlBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('  Download button found — clicking...');
        const [download] = await Promise.all([
          page.waitForEvent('download', { timeout: 15000 }),
          dlBtn.click(),
        ]);
        const suggested = download.suggestedFilename() || `${safe}.pdf`;
        const ext = suggested.split('.').pop() || 'pdf';
        const savePath = join(RESUME_DIR, `${safe}.${ext}`);
        await download.saveAs(savePath);
        console.log(`  Saved: ${savePath}`);
      } else {
        console.log('  No download button — candidate may not have uploaded a resume. Skipping.');
      }
    }

    console.log('\nDone. All candidates processed.');
  } catch (err) {
    console.error('Fatal error:', err);
  } finally {
    await context.close();
  }
}

main();
