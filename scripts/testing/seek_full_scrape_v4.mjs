import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
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

function waitForApps(page, timeout = 15000) {
  return new Promise((resolve) => {
    let done = false;
    const timer = setTimeout(() => { if (!done) { done = true; resolve([]); } }, timeout);
    const handler = async (response) => {
      if (done) return;
      if (!response.url().includes('graphql') || response.request().method() !== 'POST') return;
      try {
        const body = await response.json();
        const str = JSON.stringify(body);
        if (!str.includes('"applications"')) return;
        const apps = Array.isArray(body)
          ? body.find(b => b?.data?.applications)?.data?.applications
          : body?.data?.applications;
        if (apps?.result) {
          done = true; clearTimeout(timer);
          page.removeListener('response', handler);
          resolve({ results: apps.result, pageInfo: apps.pageInfo });
        }
      } catch {}
    };
    page.on('response', handler);
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--disable-dev-shm-usage', '--disable-gpu'] });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    acceptDownloads: true,
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

  try {
    // Login
    console.log('Logging in...');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    const emailField = page.locator('input[id="emailAddress"]');
    if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
      await emailField.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000);
    }
    console.log('Logged in.\n');

    for (const job of JOBS) {
      console.log(`${'='.repeat(70)}`);
      console.log(`  ${job.name} (Job ID: ${job.id})`);
      console.log(`${'='.repeat(70)}`);

      const jobDir = join(BASE_DIR, job.folder);
      mkdirSync(join(jobDir, 'profiles'), { recursive: true });
      mkdirSync(join(jobDir, 'resumes'), { recursive: true });

      const allMap = new Map();

      // PHASE 1: Collect all candidate IDs by clicking each status tab
      console.log('\nPHASE 1: Collecting ALL candidates...');

      // Load page
      const p1 = waitForApps(page);
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      const init = await p1;
      if (init.results) for (const c of init.results) allMap.set(c.adcentreProspectId, c);
      console.log(`  Initial: ${init.results?.length || 0} (${allMap.size} unique)`);

      // Find all status folder tabs — they appear as tab-like buttons in the left panel
      // From recon: "Inbox44 new", "Prescreen21", "Shortlist128", etc.
      const statusTexts = ['Inbox', 'Prescreen', 'Shortlist', 'Interview', 'Offer', 'Accept', 'Not Suitable'];

      for (const status of statusTexts) {
        // Try multiple selectors for the status tab
        let tab = null;
        for (const sel of [
          `button:has-text("${status}")`,
          `a:has-text("${status}")`,
          `[role="tab"]:has-text("${status}")`,
          `text=${status}`,
        ]) {
          const el = page.locator(sel).first();
          if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
            tab = el;
            break;
          }
        }

        if (!tab) continue;

        // Click and wait for data
        const tabPromise = waitForApps(page);
        await tab.click();
        const tabData = await tabPromise;

        if (tabData.results?.length > 0) {
          for (const c of tabData.results) allMap.set(c.adcentreProspectId, c);
          console.log(`  ${status}: ${tabData.results.length} candidates, page 1/${tabData.pageInfo?.totalPages || 1} (${allMap.size} total)`);

          // Paginate
          const totalPages = tabData.pageInfo?.totalPages || 1;
          for (let p = 2; p <= totalPages; p++) {
            const nextBtn = page.locator('a:has-text("Next")').last();
            if (!await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) break;

            const nextPromise = waitForApps(page);
            await nextBtn.click();
            const nextData = await nextPromise;
            if (!nextData.results?.length) break;
            for (const c of nextData.results) allMap.set(c.adcentreProspectId, c);
            console.log(`    page ${p}/${totalPages}: +${nextData.results.length} (${allMap.size} total)`);
          }
        } else {
          console.log(`  ${status}: 0 candidates`);
        }
      }

      const allCandidates = [...allMap.values()];
      console.log(`\n  TOTAL: ${allCandidates.length} unique candidates`);

      // Save
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));
      const csvHeader = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter,Months in Role\n';
      const csvRows = allCandidates.map(c => {
        const applied = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${applied}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}","${c.mostRecentRoleMonths || ''}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);
      console.log('  Saved all_candidates.json + candidates_summary.csv\n');

      // PHASE 2: Scrape each profile + resume (FORCE re-scrape by not skipping)
      console.log('PHASE 2: Scraping profiles + downloading resumes...');
      let scraped = 0, errors = 0, resumesDownloaded = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const pid = c.adcentreProspectId;
        const fullName = `${c.firstName} ${c.lastName}`.trim();
        const safeName = sanitize(fullName);

        process.stdout.write(`  [${i+1}/${allCandidates.length}] ${fullName}... `);

        try {
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${pid}&tab=profile`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2500);

          // Career history
          const bodyText = await page.locator('body').textContent();
          let profileText = '';
          const ci = bodyText.indexOf('Career history');
          if (ci > 0) profileText = bodyText.substring(ci, ci + 5000);

          // Try PDF download
          let resumeDownloaded = false;
          if (c.metadata?.result?.hasResume) {
            const resumeDocLink = page.locator('a:has-text("Resumé")').first();
            if (await resumeDocLink.isVisible({ timeout: 1500 }).catch(() => false)) {
              try {
                const [download] = await Promise.all([
                  page.waitForEvent('download', { timeout: 5000 }),
                  resumeDocLink.click(),
                ]);
                const suggested = download.suggestedFilename() || `${safeName}.pdf`;
                await download.saveAs(join(jobDir, 'resumes', suggested));
                resumeDownloaded = true;
                resumesDownloaded++;
                process.stdout.write('[PDF] ');
              } catch {}
            }
          }

          // Resume tab text
          let resumeText = '';
          const rt = page.locator('[role="tab"]:has-text("Resum")').first();
          if (await rt.isVisible({ timeout: 1500 }).catch(() => false)) {
            await rt.click();
            await page.waitForTimeout(2000);
            const rb = await page.locator('body').textContent();
            const ni = rb.lastIndexOf('Notes and attachments');
            if (ni > 0) resumeText = rb.substring(ni + 25, ni + 10000);
          }

          // Save markdown
          const md = `# ${fullName}

| Field | Value |
|-------|-------|
| **Candidate ID** | ${pid} |
| **Email** | ${c.email} |
| **Phone** | ${c.phone || 'N/A'} |
| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |
| **Company** | ${c.mostRecentCompanyName || 'N/A'} |
| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths / 12) + 'y ' + (c.mostRecentRoleMonths % 12) + 'm' : 'N/A'} |
| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |
| **Status** | ${c.statusFolder} |
| **Resume PDF** | ${resumeDownloaded ? 'Yes' : 'No'} |

## Skills
${(c.matchedQualities || []).map(q => `- ${q.displayLabel} (${(q.relevanceScore * 100).toFixed(0)}%)`).join('\n') || 'None'}

## Career History
${profileText || 'Not available'}

## Resume Content
${resumeText || 'Not available'}
`;
          writeFileSync(join(jobDir, 'profiles', `${safeName}.md`), md);
          scraped++;
          console.log('OK');
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 60)}`);
        }

        if (i % 25 === 24) {
          console.log(`    --- ${scraped}/${allCandidates.length} done, ${resumesDownloaded} PDFs, ${errors} errors --- pausing 5s`);
          await page.waitForTimeout(5000);
        }
      }

      console.log(`\n  ${job.name} DONE`);
      console.log(`    Profiles: ${scraped} | PDFs: ${resumesDownloaded} | Errors: ${errors}`);
      console.log(`    Output: ${jobDir}\n`);
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
