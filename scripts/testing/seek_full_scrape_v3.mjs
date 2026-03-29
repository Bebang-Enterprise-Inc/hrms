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

const STATUS_TABS = ['Inbox', 'Prescreen', 'Shortlist', 'Interview', 'Offer', 'Accept', 'Not Suitable'];

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

// Wait for a GraphQL response containing applications data
function waitForApplicationsResponse(page, timeout = 15000) {
  return new Promise((resolve) => {
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) { resolved = true; resolve([]); }
    }, timeout);

    const handler = async (response) => {
      if (resolved) return;
      if (!response.url().includes('graphql')) return;
      if (response.request().method() !== 'POST') return;
      try {
        const body = await response.json();
        const str = JSON.stringify(body);
        if (!str.includes('"applications"') || !str.includes('"result"')) return;

        const apps = Array.isArray(body)
          ? body.find(b => b?.data?.applications)?.data?.applications
          : body?.data?.applications;

        if (apps?.result) {
          resolved = true;
          clearTimeout(timer);
          page.removeListener('response', handler);
          resolve(apps.result);
        }
      } catch {}
    };

    page.on('response', handler);
  });
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu'],
  });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    acceptDownloads: true,
  });
  const page = await context.newPage();

  // Disable cache
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

      const allCandidatesMap = new Map();

      // ===== PHASE 1: Collect ALL candidates from each status tab =====
      console.log('\nPHASE 1: Collecting candidates from all status tabs...');

      // Initial page load
      const initialPromise = waitForApplicationsResponse(page);
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      const initialResults = await initialPromise;
      for (const c of initialResults) allCandidatesMap.set(c.adcentreProspectId, c);
      console.log(`  Initial load: ${initialResults.length} candidates (${allCandidatesMap.size} unique)`);

      // Click each status tab
      for (const tabText of STATUS_TABS) {
        const tab = page.locator(`[role="tab"]:has-text("${tabText}")`).first();
        if (!await tab.isVisible({ timeout: 2000 }).catch(() => false)) continue;

        // Check if tab has count > 0 (tabs show count like "Inbox44")
        const tabContent = await tab.textContent().catch(() => '');
        const countMatch = tabContent.match(/(\d+)/);
        const count = countMatch ? parseInt(countMatch[1]) : 0;
        if (count === 0 && tabText !== 'Inbox') {
          console.log(`  ${tabText}: 0 candidates, skipping`);
          continue;
        }

        // Click tab and wait for GraphQL response
        const tabPromise = waitForApplicationsResponse(page);
        await tab.click();
        const tabResults = await tabPromise;
        for (const c of tabResults) allCandidatesMap.set(c.adcentreProspectId, c);
        console.log(`  ${tabText}: ${tabResults.length} candidates (${allCandidatesMap.size} total unique)`);

        // Paginate if needed
        let hasMore = true;
        while (hasMore) {
          const nextBtn = page.locator('a:has-text("Next"), button:has-text("Next")').last();
          if (!await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) { hasMore = false; break; }
          const isDisabled = await nextBtn.evaluate(el =>
            el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true' ||
            el.classList.contains('disabled')
          ).catch(() => true);
          if (isDisabled) { hasMore = false; break; }

          const nextPromise = waitForApplicationsResponse(page);
          await nextBtn.click();
          const nextResults = await nextPromise;
          if (nextResults.length === 0) { hasMore = false; break; }
          for (const c of nextResults) allCandidatesMap.set(c.adcentreProspectId, c);
          console.log(`    + page: ${nextResults.length} more (${allCandidatesMap.size} total)`);
        }
      }

      const allCandidates = [...allCandidatesMap.values()];
      console.log(`\n  TOTAL UNIQUE CANDIDATES: ${allCandidates.length}`);

      // Save raw data + CSV
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));

      const csvHeader = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter,Months in Role\n';
      const csvRows = allCandidates.map(c => {
        const applied = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${applied}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}","${c.mostRecentRoleMonths || ''}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);
      console.log('  Saved candidates_summary.csv\n');

      // ===== PHASE 2: Scrape profiles + resumes =====
      console.log('PHASE 2: Scraping profiles and resumes...');
      let scraped = 0, errors = 0, skipped = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const prospectId = c.adcentreProspectId;
        const fullName = `${c.firstName} ${c.lastName}`.trim();
        const safeName = sanitize(fullName);
        const mdPath = join(jobDir, 'profiles', `${safeName}.md`);

        if (existsSync(mdPath)) { skipped++; continue; }

        process.stdout.write(`  [${i+1}/${allCandidates.length}] ${fullName}... `);

        try {
          // Profile tab
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${prospectId}&tab=profile`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2500);

          const bodyText = await page.locator('body').textContent();
          let profileText = '';
          const careerIdx = bodyText.indexOf('Career history');
          if (careerIdx > 0) profileText = bodyText.substring(careerIdx, careerIdx + 5000);

          // Try resume PDF download from "Application documents" section
          let resumeDownloaded = false;
          const resumeDocLink = page.locator('a:has-text("Resumé")').first();
          if (c.metadata?.result?.hasResume && await resumeDocLink.isVisible({ timeout: 1500 }).catch(() => false)) {
            try {
              const [download] = await Promise.all([
                page.waitForEvent('download', { timeout: 5000 }),
                resumeDocLink.click(),
              ]);
              const ext = (download.suggestedFilename() || '').split('.').pop() || 'pdf';
              const savePath = join(jobDir, 'resumes', `${safeName}.${ext}`);
              await download.saveAs(savePath);
              resumeDownloaded = true;
              process.stdout.write('[PDF] ');
            } catch {}
          }

          // Resume tab text
          let resumeText = '';
          const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
          if (await resumeTab.isVisible({ timeout: 1500 }).catch(() => false)) {
            await resumeTab.click();
            await page.waitForTimeout(2000);
            const rb = await page.locator('body').textContent();
            const ni = rb.lastIndexOf('Notes and attachments');
            if (ni > 0) resumeText = rb.substring(ni + 25, ni + 10000);
          }

          // Save profile
          const mdContent = `# ${fullName}

| Field | Value |
|-------|-------|
| **Candidate ID** | ${prospectId} |
| **Email** | ${c.email} |
| **Phone** | ${c.phone || 'N/A'} |
| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |
| **Company** | ${c.mostRecentCompanyName || 'N/A'} |
| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths / 12) + 'y ' + (c.mostRecentRoleMonths % 12) + 'm' : 'N/A'} |
| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |
| **Status** | ${c.statusFolder} |
| **Resume File** | ${resumeDownloaded ? 'Downloaded' : 'Text only'} |

## Skills
${(c.matchedQualities || []).map(q => `- ${q.displayLabel} (${(q.relevanceScore * 100).toFixed(0)}%)`).join('\n') || 'None'}

## Career History
${profileText || 'Not available'}

## Resume Content
${resumeText || 'Not available'}
`;
          writeFileSync(mdPath, mdContent);
          scraped++;
          console.log('OK');
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 60)}`);
        }

        if (i % 20 === 19) {
          console.log(`    --- ${scraped} done, ${skipped} skipped, ${errors} errors --- pausing 5s`);
          await page.waitForTimeout(5000);
        }
      }

      console.log(`\n  ${job.name} COMPLETE: ${scraped} scraped, ${skipped} skipped, ${errors} errors`);
      console.log(`  Output: ${jobDir}\n`);
    }

    console.log('=== ALL DONE ===');

  } catch (err) {
    console.error('Fatal:', err.message);
    console.error(err.stack);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
