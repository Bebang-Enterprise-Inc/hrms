import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

async function main() {
  const missing = JSON.parse(readFileSync(join(BASE_DIR, 'missing_resumes.json'), 'utf-8'));
  console.log(`${missing.length} missing resumes to download\n`);

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

    let downloaded = 0, noBtn = 0, errors = 0;

    for (let i = 0; i < missing.length; i++) {
      const c = missing[i];
      const sn = sanitize(c.name);
      const resumeDir = join(BASE_DIR, c.folder, 'resumes');
      mkdirSync(resumeDir, { recursive: true });

      // Check if somehow already exists
      const exists = ['pdf', 'doc', 'docx', 'rtf', 'PDF'].some(ext => existsSync(join(resumeDir, `${sn}.${ext}`)));
      if (exists) { downloaded++; continue; }

      process.stdout.write(`  [${i+1}/${missing.length}] ${c.name}... `);

      try {
        await page.goto(
          `https://ph.employer.seek.com/candidates/?jobid=${c.seekJobId}&selected=${c.pid}&tab=resume`,
          { waitUntil: 'load', timeout: 20000 }
        );
        await page.waitForTimeout(4000);

        // Re-login if needed
        if (page.url().includes('login') || page.url().includes('authenticate')) {
          const ef2 = page.locator('input[id="emailAddress"]');
          if (await ef2.isVisible({ timeout: 3000 }).catch(() => false)) {
            await ef2.fill(EMAIL);
            await page.locator('input[id="password"]').fill(PASSWORD);
            await page.locator('button:has-text("Sign in")').first().click();
            await page.waitForTimeout(8000);
            await page.goto(
              `https://ph.employer.seek.com/candidates/?jobid=${c.seekJobId}&selected=${c.pid}&tab=resume`,
              { waitUntil: 'load', timeout: 20000 }
            );
            await page.waitForTimeout(4000);
          }
        }

        const dlBtn = page.locator('button[aria-label="Download document"]').first();
        if (await dlBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
          const [download] = await Promise.all([
            page.waitForEvent('download', { timeout: 15000 }),
            dlBtn.click(),
          ]);
          const suggested = download.suggestedFilename() || `${sn}.pdf`;
          const ext = suggested.split('.').pop() || 'pdf';
          await download.saveAs(join(resumeDir, `${sn}.${ext}`));
          downloaded++;
          console.log(`OK (${ext})`);
        } else {
          noBtn++;
          console.log('no download btn');
        }
      } catch (err) {
        errors++;
        console.log(`ERR: ${err.message.substring(0, 50)}`);
      }
    }

    console.log(`\nDone: ${downloaded} downloaded, ${noBtn} no button, ${errors} errors`);
  } catch (err) {
    console.error('Fatal:', err.message);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
