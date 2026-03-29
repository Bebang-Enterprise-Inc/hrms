import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync, readFileSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

const JOBS = [
  { id: '91094834', folder: 'head-of-finance-and-accounting-controller', name: 'Head of Finance' },
  { id: '91090632', folder: 'accounting-manager', name: 'Accounting Manager' },
];

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--disable-dev-shm-usage', '--disable-gpu'] });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    acceptDownloads: true,
  });
  const page = await context.newPage();

  try {
    // Login
    console.log('Logging in...');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    const ef = page.locator('input[id="emailAddress"]');
    if (await ef.isVisible({ timeout: 5000 }).catch(() => false)) {
      await ef.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000);
    }
    console.log('Logged in. URL:', page.url());

    // Verify we're logged in
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(3000);
    console.log('Jobs page URL:', page.url());

    for (const job of JOBS) {
      console.log(`\n${'='.repeat(70)}`);
      console.log(`  ${job.name}`);
      console.log(`${'='.repeat(70)}`);

      const jobDir = join(BASE_DIR, job.folder);
      const resumeDir = join(jobDir, 'resumes');
      mkdirSync(resumeDir, { recursive: true });

      const candidatesFile = join(jobDir, 'all_candidates.json');
      if (!existsSync(candidatesFile)) { console.log('  No data, skipping'); continue; }

      const allCandidates = JSON.parse(readFileSync(candidatesFile, 'utf8'));
      const withResume = allCandidates.filter(c => c.metadata?.result?.hasResume);
      console.log(`  Total: ${allCandidates.length} | With resume: ${withResume.length}\n`);

      // Navigate to candidates page first — stay on this page
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(5000);
      console.log('  On candidates page:', page.url());

      // Click first candidate to open the detail panel
      const firstCandName = page.locator(`text=${withResume[0].firstName}`).first();
      if (await firstCandName.isVisible({ timeout: 3000 }).catch(() => false)) {
        await firstCandName.click();
        await page.waitForTimeout(3000);
      }

      // Now explore the Resume tab to find the download button
      const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
      if (await resumeTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await resumeTab.click();
        await page.waitForTimeout(3000);

        // Screenshot the resume tab
        await page.screenshot({ path: 'scratchpad/qa/seek_resume_tab_explore.png' });

        // Find ALL buttons and their attributes
        console.log('\n  === Exploring Resume tab buttons ===');
        const allBtns = await page.locator('button').all();
        console.log(`  Total buttons: ${allBtns.length}`);
        for (let j = 0; j < allBtns.length; j++) {
          const btn = allBtns[j];
          const title = await btn.getAttribute('title').catch(() => '');
          const label = await btn.getAttribute('aria-label').catch(() => '');
          const testId = await btn.getAttribute('data-testid').catch(() => '');
          const text = (await btn.textContent().catch(() => '')).trim().substring(0, 40);
          const visible = await btn.isVisible().catch(() => false);
          const className = (await btn.getAttribute('class').catch(() => '')).substring(0, 60);
          console.log(`  [${j}] visible=${visible} title="${title}" aria="${label}" testid="${testId}" text="${text}" class="${className}"`);
        }

        // Also check links
        const allLinks = await page.locator('a').all();
        console.log(`\n  Total links: ${allLinks.length}`);
        for (let j = 0; j < allLinks.length; j++) {
          const link = allLinks[j];
          const href = await link.getAttribute('href').catch(() => '');
          const title = await link.getAttribute('title').catch(() => '');
          const label = await link.getAttribute('aria-label').catch(() => '');
          const text = (await link.textContent().catch(() => '')).trim().substring(0, 40);
          if (href?.includes('download') || href?.includes('document') || href?.includes('resume') ||
              title?.includes('Download') || label?.includes('Download') ||
              href?.includes('blob') || href?.includes('attachment')) {
            console.log(`  [${j}] href="${href?.substring(0, 100)}" title="${title}" aria="${label}" text="${text}"`);
          }
        }

        // Check for SVG download icons
        const svgBtns = await page.locator('button:has(svg), a:has(svg)').all();
        console.log(`\n  Buttons/links with SVGs: ${svgBtns.length}`);
        for (let j = 0; j < svgBtns.length; j++) {
          const el = svgBtns[j];
          const visible = await el.isVisible().catch(() => false);
          if (!visible) continue;
          const title = await el.getAttribute('title').catch(() => '');
          const label = await el.getAttribute('aria-label').catch(() => '');
          const testId = await el.getAttribute('data-testid').catch(() => '');
          const tag = await el.evaluate(e => e.tagName).catch(() => '');
          console.log(`  [${j}] <${tag}> visible title="${title}" aria="${label}" testid="${testId}"`);
        }
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_dl_debug_error.png' }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
