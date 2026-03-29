import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SEEK_EMAIL = 'sam@bebang.ph';
const SEEK_PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

// Only retry the ones that errored or had no button but might just need more wait time
const candidates = [
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2082287871", "name": "Mary Grace Tamondong"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2085753902", "name": "Robin Sicat"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2085088225", "name": "may marzan"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2081788623", "name": "ronald ron dimatatac"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2081796296", "name": "Ike Tom Tolentino, CPA"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2085567452", "name": "Richard Villarico"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083701725", "name": "Kenny Rovir Gador"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083505689", "name": "Ben Carlo Ramos"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2084306675", "name": "Mark Cordova"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2082742500", "name": "SK Raman"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083411623", "name": "Maria Shirdel Marantal"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2085834227", "name": "marlene arado"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083809519", "name": "Joan Irene Dañas"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083043436", "name": "Joseph Mojado"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2083045491", "name": "Jaworski Garcia"},
  {"jobId": "91094834", "folder": "head-of-finance-and-accounting-controller", "pid": "2082982491", "name": "Ermila Sevilla"},
];

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

function fileExists(folder, sanitizedName) {
  const resumeDir = path.join(BASE_DIR, folder, 'resumes');
  for (const ext of ['pdf', 'doc', 'docx', 'rtf', 'txt']) {
    if (fs.existsSync(path.join(resumeDir, `${sanitizedName}.${ext}`))) return true;
  }
  return false;
}

async function login(page) {
  console.log('Logging in to SEEK...');
  await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(5000);
  try {
    await page.waitForSelector('input#emailAddress', { timeout: 10000 });
    await page.fill('input#emailAddress', SEEK_EMAIL);
    await page.waitForTimeout(500);
    await page.fill('input#password', SEEK_PASSWORD);
    await page.waitForTimeout(500);
    await page.click('button:has-text("Sign in")');
    await page.waitForTimeout(8000);
    console.log('Login complete, URL:', page.url());
  } catch {
    console.log('Already logged in');
  }
}

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();

  await login(page);

  let downloaded = 0, skipped = 0, noButton = 0, errors = 0;

  for (let i = 0; i < candidates.length; i++) {
    const { jobId, folder, pid, name } = candidates[i];
    const sanitizedName = sanitize(name);
    const resumeDir = path.join(BASE_DIR, folder, 'resumes');
    fs.mkdirSync(resumeDir, { recursive: true });

    if (fileExists(folder, sanitizedName)) {
      console.log(`[${i + 1}/${candidates.length}] SKIP (exists): ${name}`);
      skipped++;
      continue;
    }

    console.log(`[${i + 1}/${candidates.length}] Processing: ${name} (pid=${pid})`);

    try {
      const url = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${pid}&tab=resume`;
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      // Wait longer for SPA to render
      await page.waitForTimeout(6000);

      // Try to find download button, wait up to 10s
      let downloadBtn = null;
      for (let attempt = 0; attempt < 3; attempt++) {
        downloadBtn = await page.$('button[aria-label="Download document"]');
        if (downloadBtn) break;
        downloadBtn = await page.$('[aria-label="Download document"]');
        if (downloadBtn) break;
        await page.waitForTimeout(3000);
      }

      if (!downloadBtn) {
        console.log(`  NO DOWNLOAD BUTTON for ${name}`);
        noButton++;
        continue;
      }

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

  console.log('\n=== RETRY RESULTS ===');
  console.log(`Downloaded: ${downloaded}`);
  console.log(`Skipped (exists): ${skipped}`);
  console.log(`No download button: ${noButton}`);
  console.log(`Errors: ${errors}`);
  console.log(`Total: ${candidates.length}`);
})();
