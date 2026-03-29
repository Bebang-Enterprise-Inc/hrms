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
    console.log('Logged in.\n');

    for (const job of JOBS) {
      console.log(`${'='.repeat(70)}`);
      console.log(`  ${job.name}`);
      console.log(`${'='.repeat(70)}`);

      const jobDir = join(BASE_DIR, job.folder);
      const resumeDir = join(jobDir, 'resumes');
      mkdirSync(resumeDir, { recursive: true });

      // Load candidates from already-scraped data
      const candidatesFile = join(jobDir, 'all_candidates.json');
      if (!existsSync(candidatesFile)) {
        console.log('  No all_candidates.json found, skipping');
        continue;
      }

      const allCandidates = JSON.parse(readFileSync(candidatesFile, 'utf8'));
      const withResume = allCandidates.filter(c => c.metadata?.result?.hasResume);
      console.log(`  Total: ${allCandidates.length} | With resume: ${withResume.length}\n`);

      let downloaded = 0, skipped = 0, errors = 0;

      for (let i = 0; i < withResume.length; i++) {
        const c = withResume[i];
        const pid = c.adcentreProspectId;
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);

        // Check if already downloaded (any extension)
        const existing = ['pdf', 'doc', 'docx', 'rtf'].some(ext =>
          existsSync(join(resumeDir, `${sn}.${ext}`))
        );
        if (existing) { skipped++; continue; }

        process.stdout.write(`  [${i+1}/${withResume.length}] ${fn}... `);

        try {
          // Navigate to the Resume tab
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${pid}&tab=resume`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(3000);

          // The download button is a small icon button in the toolbar below the tabs
          // It has an aria-label like "Download document" based on the tooltip
          // Selectors to try:
          const downloadSelectors = [
            'button[aria-label="Download document"]',
            'button[aria-label*="download"]',
            'button[aria-label*="Download"]',
            'a[aria-label="Download document"]',
            'a[aria-label*="download"]',
            'a[aria-label*="Download"]',
            'button[title="Download document"]',
            'button[title*="Download"]',
            'a[title="Download document"]',
            'a[title*="download"]',
            // The download icon is the 4th button in the toolbar (expand, zoom-, zoom+, download)
            'button:nth-child(4)',
          ];

          let dlButton = null;
          for (const sel of downloadSelectors) {
            const el = page.locator(sel).first();
            if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
              dlButton = el;
              break;
            }
          }

          // Also try finding by the download icon SVG or by position
          if (!dlButton) {
            // The toolbar has 4 buttons: expand, zoom out, zoom in, download
            // Try finding buttons near the resume viewer area
            const toolbarBtns = await page.locator('button[type="button"]').all();
            // The download button is typically the one with a download-related SVG
            for (const btn of toolbarBtns) {
              const html = await btn.innerHTML().catch(() => '');
              if (html.includes('download') || html.includes('Download')) {
                dlButton = btn;
                break;
              }
            }
          }

          // Last resort: find by tooltip text "Download document"
          if (!dlButton) {
            const btns = await page.locator('button').all();
            for (const btn of btns) {
              const title = await btn.getAttribute('title').catch(() => '');
              const label = await btn.getAttribute('aria-label').catch(() => '');
              if (title?.includes('Download') || label?.includes('Download') ||
                  title?.includes('download') || label?.includes('download')) {
                dlButton = btn;
                break;
              }
            }
          }

          if (dlButton) {
            try {
              const [download] = await Promise.all([
                page.waitForEvent('download', { timeout: 10000 }),
                dlButton.click(),
              ]);
              const suggested = download.suggestedFilename() || `${sn}.pdf`;
              const ext = suggested.split('.').pop() || 'pdf';
              const savePath = join(resumeDir, `${sn}.${ext}`);
              await download.saveAs(savePath);
              downloaded++;
              console.log(`OK (${suggested})`);
            } catch (dlErr) {
              errors++;
              console.log(`DOWNLOAD FAILED: ${dlErr.message.substring(0, 50)}`);
            }
          } else {
            errors++;
            console.log('NO DOWNLOAD BUTTON FOUND');

            // Debug: dump all button attributes on this page
            if (errors <= 3) {
              const allBtns = await page.locator('button').all();
              console.log(`    (${allBtns.length} buttons on page)`);
              for (const btn of allBtns.slice(0, 20)) {
                const title = await btn.getAttribute('title').catch(() => '');
                const label = await btn.getAttribute('aria-label').catch(() => '');
                const text = (await btn.textContent().catch(() => '')).trim().substring(0, 40);
                const testId = await btn.getAttribute('data-testid').catch(() => '');
                if (title || label || testId) {
                  console.log(`    btn: title="${title}" aria="${label}" testid="${testId}" text="${text}"`);
                }
              }
            }
          }
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 60)}`);
        }

        // Rate limit
        if (i % 20 === 19) {
          console.log(`    --- ${downloaded} downloaded, ${skipped} skipped, ${errors} errors --- pausing 3s`);
          await page.waitForTimeout(3000);
        }
      }

      console.log(`\n  ${job.name} DONE: ${downloaded} downloaded, ${skipped} skipped, ${errors} errors`);
      console.log(`  Resumes: ${resumeDir}\n`);
    }

    console.log('=== ALL COMPLETE ===');
  } catch (err) {
    console.error('Fatal:', err.message);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
