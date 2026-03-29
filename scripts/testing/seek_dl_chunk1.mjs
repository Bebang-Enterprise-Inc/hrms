import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_URL = 'https://ph.employer.seek.com';
const CHUNK_FILE = 'F:/Dropbox/Projects/BEI-ERP/recruitment/chunk_1.json';
const RECRUITMENT_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const SCREENSHOT_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment/debug';

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileExists(folder, sanitizedName) {
  const resumeDir = path.join(RECRUITMENT_DIR, folder, 'resumes');
  for (const ext of ['pdf', 'doc', 'docx', 'rtf']) {
    if (fs.existsSync(path.join(resumeDir, `${sanitizedName}.${ext}`))) {
      return true;
    }
  }
  return false;
}

async function login(page) {
  console.log('  Navigating to login...');
  await page.goto(`${BASE_URL}/jobs`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(4000);

  const emailField = await page.$('input#emailAddress');
  if (!emailField) {
    console.log('  Already logged in');
    return true;
  }

  console.log('  Filling login form...');
  await emailField.fill(SEEK_EMAIL);
  const passwordField = await page.$('input#password');
  if (passwordField) await passwordField.fill(SEEK_PASSWORD);

  const signInBtn = await page.$('button:has-text("Sign in")');
  if (signInBtn) await signInBtn.click();
  else await page.keyboard.press('Enter');

  await page.waitForTimeout(8000);
  console.log(`  Post-login URL: ${page.url()}`);
  return true;
}

async function waitForCandidatePanel(page) {
  // Wait for loading indicator to disappear
  try {
    await page.waitForSelector('[aria-label="Loading"]', { state: 'hidden', timeout: 15000 });
  } catch (e) {
    // Loading indicator may already be gone
  }

  // Wait a bit more for content
  await page.waitForTimeout(3000);

  // Also try waiting for networkidle manually
  try {
    await page.waitForLoadState('networkidle', { timeout: 10000 });
  } catch (e) {
    // Timeout is okay
  }
}

async function main() {
  const candidates = JSON.parse(fs.readFileSync(CHUNK_FILE, 'utf-8'));
  console.log(`Loaded ${candidates.length} candidates from chunk_1.json`);

  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  const stats = { downloaded: 0, skipped: 0, noButton: 0, errors: 0 };

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  // Initial login
  await login(page);

  // Navigate to candidates list first (SPA needs this)
  const firstCandidate = candidates[0];
  console.log('\nLoading candidates list page...');
  await page.goto(`${BASE_URL}/candidates/?jobid=${firstCandidate.jobId}`, { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(8000);

  // Now try clicking on the first candidate in the list to open detail panel
  // Then switch to resume tab
  let debugCount = 0;

  for (let i = 0; i < candidates.length; i++) {
    const { jobId, folder, pid, name } = candidates[i];
    const sanitizedName = sanitize(name);
    const resumeDir = path.join(RECRUITMENT_DIR, folder, 'resumes');

    console.log(`\n[${i + 1}/${candidates.length}] ${name} (${sanitizedName})`);

    if (fileExists(folder, sanitizedName)) {
      console.log('  SKIP: file already exists');
      stats.skipped++;
      continue;
    }

    fs.mkdirSync(resumeDir, { recursive: true });

    try {
      // Navigate to the candidate's resume tab
      const url = `${BASE_URL}/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });

      // Wait for SPA content to load
      await waitForCandidatePanel(page);

      const currentUrl = page.url();
      if (currentUrl.includes('/authenticate') || currentUrl.includes('/login')) {
        console.log('  Session expired, re-logging in...');
        await login(page);
        await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        await waitForCandidatePanel(page);
      }

      if (debugCount < 3) {
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, `candidate_v3_${i+1}.png`), fullPage: true });

        // Log all aria-label elements (excluding "Site Header" and "Loading")
        const ariaElements = await page.$$eval('[aria-label]', els => els.map(e => ({
          tag: e.tagName,
          ariaLabel: e.getAttribute('aria-label'),
          visible: e.offsetParent !== null || e.offsetWidth > 0,
        })).filter(a => !['Site Header', 'Loading'].includes(a.ariaLabel)));
        console.log('  Aria elements:', JSON.stringify(ariaElements));

        // Log all buttons with text
        const buttons = await page.$$eval('button', els => els.map(e => ({
          text: e.textContent?.trim()?.substring(0, 40),
          ariaLabel: e.getAttribute('aria-label'),
          visible: e.offsetParent !== null,
        })).filter(b => b.visible));
        console.log('  Visible buttons:', JSON.stringify(buttons));

        // Check if there's a resume tab
        const tabs = await page.$$eval('[role="tab"], [role="tablist"] *, a[href*="tab="]', els => els.map(e => ({
          text: e.textContent?.trim()?.substring(0, 30),
          href: e.getAttribute('href')?.substring(0, 60),
          ariaSelected: e.getAttribute('aria-selected'),
        })));
        console.log('  Tabs:', JSON.stringify(tabs));

        debugCount++;
      }

      // Try to find download button
      let downloadBtn = null;
      const selectors = [
        'button[aria-label="Download document"]',
        '[aria-label="Download document"]',
        'button[aria-label*="ownload"]',
        'a[aria-label*="ownload"]',
        '[data-testid*="download"]',
        'button:has-text("Download")',
        'a:has-text("Download")',
      ];

      for (const sel of selectors) {
        downloadBtn = await page.$(sel);
        if (downloadBtn) {
          console.log(`  Found button: ${sel}`);
          break;
        }
      }

      if (!downloadBtn) {
        console.log('  NO BUTTON: download button not found');
        stats.noButton++;
        continue;
      }

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        downloadBtn.click(),
      ]);

      const suggestedName = download.suggestedFilename();
      const ext = path.extname(suggestedName) || '.pdf';
      const destPath = path.join(resumeDir, `${sanitizedName}${ext}`);

      await download.saveAs(destPath);
      console.log(`  DOWNLOADED: ${sanitizedName}${ext}`);
      stats.downloaded++;

    } catch (err) {
      console.log(`  ERROR: ${err.message}`);
      stats.errors++;
    }
  }

  await browser.close();

  console.log('\n========== RESULTS ==========');
  console.log(`Downloaded: ${stats.downloaded}`);
  console.log(`Skipped (exists): ${stats.skipped}`);
  console.log(`No button: ${stats.noButton}`);
  console.log(`Errors: ${stats.errors}`);
  console.log(`Total: ${candidates.length}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
