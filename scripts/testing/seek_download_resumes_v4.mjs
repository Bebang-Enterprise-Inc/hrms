import { chromium } from 'playwright';
import { mkdirSync, existsSync, readFileSync } from 'fs';
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
      console.log(`${'='.repeat(60)}`);
      console.log(`  ${job.name}`);
      console.log(`${'='.repeat(60)}`);

      const jobDir = join(BASE_DIR, job.folder);
      const resumeDir = join(jobDir, 'resumes');
      mkdirSync(resumeDir, { recursive: true });

      const candidatesFile = join(jobDir, 'all_candidates.json');
      if (!existsSync(candidatesFile)) { console.log('  No data, skip'); continue; }

      const allCandidates = JSON.parse(readFileSync(candidatesFile, 'utf8'));
      const withResume = allCandidates.filter(c => c.metadata?.result?.hasResume);
      console.log(`  ${withResume.length} candidates with resumes\n`);

      // Load initial candidates page — this establishes the SPA session
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(6000);

      let downloaded = 0, skipped = 0, errors = 0, noBtn = 0;

      for (let i = 0; i < withResume.length; i++) {
        const c = withResume[i];
        const pid = c.adcentreProspectId;
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);

        const alreadyDone = ['pdf', 'doc', 'docx', 'rtf'].some(ext => existsSync(join(resumeDir, `${sn}.${ext}`)));
        if (alreadyDone) { skipped++; continue; }

        process.stdout.write(`  [${i+1}/${withResume.length}] ${fn}... `);

        try {
          // SPA navigation: click the link that opens this candidate
          // Use client-side navigation by clicking a link with the right URL
          await page.evaluate((url) => {
            const a = document.createElement('a');
            a.href = url;
            a.click();
          }, `/candidates/?jobid=${job.id}&selected=${pid}&tab=resume`);
          await page.waitForTimeout(4000);

          // Check if we're still on the right page (session not lost)
          if (page.url().includes('login') || page.url().includes('authenticate')) {
            console.log('SESSION LOST - re-logging in...');
            await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
            await page.waitForTimeout(3000);
            const ef2 = page.locator('input[id="emailAddress"]');
            if (await ef2.isVisible({ timeout: 5000 }).catch(() => false)) {
              await ef2.fill(EMAIL);
              await page.locator('input[id="password"]').fill(PASSWORD);
              await page.locator('button:has-text("Sign in")').first().click();
              await page.waitForTimeout(8000);
            }
            await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${pid}&tab=resume`, {
              waitUntil: 'domcontentloaded', timeout: 15000
            });
            await page.waitForTimeout(5000);
          }

          // Look for download button
          const dlBtn = page.locator('button[aria-label="Download document"]').first();
          if (await dlBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            const [download] = await Promise.all([
              page.waitForEvent('download', { timeout: 10000 }),
              dlBtn.click(),
            ]);
            const suggested = download.suggestedFilename() || `${sn}.pdf`;
            const ext = suggested.split('.').pop() || 'pdf';
            await download.saveAs(join(resumeDir, `${sn}.${ext}`));
            downloaded++;
            console.log(`OK (${suggested})`);
          } else {
            // Maybe the Resume tab isn't active — click it
            const resumeTab = page.locator('button:has-text("Resumé")').last();
            if (await resumeTab.isVisible({ timeout: 1000 }).catch(() => false)) {
              await resumeTab.click();
              await page.waitForTimeout(2000);

              const dlBtn2 = page.locator('button[aria-label="Download document"]').first();
              if (await dlBtn2.isVisible({ timeout: 2000 }).catch(() => false)) {
                const [download] = await Promise.all([
                  page.waitForEvent('download', { timeout: 10000 }),
                  dlBtn2.click(),
                ]);
                const suggested = download.suggestedFilename() || `${sn}.pdf`;
                const ext = suggested.split('.').pop() || 'pdf';
                await download.saveAs(join(resumeDir, `${sn}.${ext}`));
                downloaded++;
                console.log(`OK (${suggested})`);
              } else {
                noBtn++;
                console.log('no dl btn after tab click');
              }
            } else {
              noBtn++;
              console.log('no resume tab');
            }
          }
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 60)}`);
        }

        if ((i + 1) % 25 === 0) {
          console.log(`    --- ${downloaded} OK, ${skipped} skip, ${noBtn} no btn, ${errors} err --- pause 3s`);
          await page.waitForTimeout(3000);
        }
      }

      console.log(`\n  ${job.name}: ${downloaded} DL, ${skipped} skip, ${noBtn} no btn, ${errors} err`);
      console.log(`  Output: ${resumeDir}\n`);
    }

    console.log('=== DONE ===');
  } catch (err) {
    console.error('Fatal:', err.message);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
