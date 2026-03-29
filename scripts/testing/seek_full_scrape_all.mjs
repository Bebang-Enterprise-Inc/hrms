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

// All status folders in SEEK
const STATUS_FOLDERS = ['INBOX', 'PRESCREEN', 'SHORTLIST', 'INTERVIEW', 'OFFER', 'ACCEPT', 'NOT_SUITABLE'];

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
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

  // CDP session for cache control
  const cdpSession = await context.newCDPSession(page);
  await cdpSession.send('Network.setCacheDisabled', { cacheDisabled: true });

  // Global GraphQL interceptor
  const capturedCandidates = [];
  let capturedQuery = null;

  page.on('response', async (response) => {
    if (response.url().includes('graphql') && response.request().method() === 'POST') {
      try {
        const body = await response.json();
        const str = JSON.stringify(body);
        if (str.includes('"applications"') && str.includes('"result"')) {
          const apps = Array.isArray(body)
            ? body.find(b => b?.data?.applications)?.data?.applications
            : body?.data?.applications;
          if (apps?.result?.length) {
            capturedCandidates.push(...apps.result);
          }
        }
      } catch {}
    }
  });

  page.on('request', async (request) => {
    if (request.url().includes('graphql') && request.method() === 'POST') {
      try {
        const postData = request.postDataJSON();
        const str = JSON.stringify(postData);
        if (str.includes('applications') && str.includes('pageNumber')) {
          capturedQuery = postData;
        }
      } catch {}
    }
  });

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

      // ===== PHASE 1: Collect ALL candidate IDs across ALL status folders =====
      console.log('\nPHASE 1: Collecting all candidate IDs...');

      const allCandidatesMap = new Map(); // prospectId -> candidate data

      // Load the candidate list page first
      capturedCandidates.length = 0;
      capturedQuery = null;
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(8000);

      // Add initial candidates
      for (const c of capturedCandidates) {
        allCandidatesMap.set(c.adcentreProspectId, c);
      }
      console.log(`  After initial load: ${allCandidatesMap.size} candidates`);

      // Now click each status folder tab to get all candidates
      for (const folder of STATUS_FOLDERS) {
        // Map folder name to tab text
        const tabTextMap = {
          'INBOX': 'Inbox',
          'PRESCREEN': 'Prescreen',
          'SHORTLIST': 'Shortlist',
          'INTERVIEW': 'Interview',
          'OFFER': 'Offer',
          'ACCEPT': 'Accept',
          'NOT_SUITABLE': 'Not Suitable',
        };
        const tabText = tabTextMap[folder];

        capturedCandidates.length = 0;
        const folderTab = page.locator(`[role="tab"]:has-text("${tabText}"), button:has-text("${tabText}")`).first();

        if (await folderTab.isVisible({ timeout: 2000 }).catch(() => false)) {
          await folderTab.click();
          await page.waitForTimeout(5000);

          // Add captured candidates
          for (const c of capturedCandidates) {
            allCandidatesMap.set(c.adcentreProspectId, c);
          }

          // Check if there are more pages — click Next until done
          let hasNext = true;
          while (hasNext) {
            const nextBtn = page.locator('a:has-text("Next"), button:has-text("Next")').last();
            if (await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
              const isDisabled = await nextBtn.evaluate(el => el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true').catch(() => true);
              if (isDisabled) { hasNext = false; break; }

              capturedCandidates.length = 0;
              await nextBtn.click();
              await page.waitForTimeout(4000);

              for (const c of capturedCandidates) {
                allCandidatesMap.set(c.adcentreProspectId, c);
              }
            } else {
              hasNext = false;
            }
          }

          const folderCount = capturedCandidates.length;
          console.log(`  ${tabText}: ${allCandidatesMap.size} total (cumulative)`);
        }
      }

      const allCandidates = [...allCandidatesMap.values()];
      console.log(`\n  TOTAL UNIQUE CANDIDATES: ${allCandidates.length}`);

      // Save raw data
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));

      // Save summary CSV
      const csvHeader = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter,Months in Role\n';
      const csvRows = allCandidates.map(c => {
        const applied = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${applied}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}","${c.mostRecentRoleMonths || ''}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);
      console.log('  Saved candidates_summary.csv');

      // ===== PHASE 2: Scrape profiles + download resumes =====
      console.log('\nPHASE 2: Scraping profiles and downloading resumes...');
      let scraped = 0, errors = 0, skipped = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const prospectId = c.adcentreProspectId;
        const fullName = `${c.firstName} ${c.lastName}`.trim();
        const safeName = sanitize(fullName);
        const mdPath = join(jobDir, 'profiles', `${safeName}.md`);

        // Skip if already scraped
        if (existsSync(mdPath)) {
          skipped++;
          continue;
        }

        process.stdout.write(`  [${i+1}/${allCandidates.length}] ${fullName}... `);

        try {
          // Load profile tab
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${prospectId}&tab=profile`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2500);

          const bodyText = await page.locator('body').textContent();

          // Extract career history
          let profileText = '';
          const careerIdx = bodyText.indexOf('Career history');
          if (careerIdx > 0) {
            profileText = bodyText.substring(careerIdx, careerIdx + 5000);
          }

          // Try to download the actual resume PDF
          // Look for "Resumé" link under "Application documents"
          let resumeDownloaded = false;
          const resumeLink = page.locator('a:has-text("Resumé"), a:has-text("Resume")').first();
          if (await resumeLink.isVisible({ timeout: 1500 }).catch(() => false)) {
            try {
              const [download] = await Promise.all([
                page.waitForEvent('download', { timeout: 5000 }),
                resumeLink.click(),
              ]);
              const suggestedName = download.suggestedFilename() || `${safeName}_resume.pdf`;
              const savePath = join(jobDir, 'resumes', suggestedName);
              await download.saveAs(savePath);
              resumeDownloaded = true;
              process.stdout.write('(resume downloaded) ');
            } catch {
              // Download didn't trigger — might open in new tab or be inline only
            }
          }

          // Click Resume tab to get text version
          let resumeText = '';
          const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
          if (await resumeTab.isVisible({ timeout: 1500 }).catch(() => false)) {
            await resumeTab.click();
            await page.waitForTimeout(2000);
            const resumeBody = await page.locator('body').textContent();
            const notesIdx = resumeBody.lastIndexOf('Notes and attachments');
            if (notesIdx > 0) {
              resumeText = resumeBody.substring(notesIdx + 25, notesIdx + 10000);
            }

            // If we didn't get a download yet, try finding download button on resume tab
            if (!resumeDownloaded) {
              const dlBtn = page.locator('a[download], button:has-text("Download"), a:has-text("Download")').first();
              if (await dlBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
                try {
                  const [download] = await Promise.all([
                    page.waitForEvent('download', { timeout: 5000 }),
                    dlBtn.click(),
                  ]);
                  const suggestedName = download.suggestedFilename() || `${safeName}_resume.pdf`;
                  const savePath = join(jobDir, 'resumes', suggestedName);
                  await download.saveAs(savePath);
                  resumeDownloaded = true;
                  process.stdout.write('(resume downloaded) ');
                } catch {}
              }
            }
          }

          // Save markdown profile
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
| **Resume Downloaded** | ${resumeDownloaded ? 'Yes' : 'No (text only)'} |

## Skills
${(c.matchedQualities || []).map(q => `- ${q.displayLabel} (${(q.relevanceScore * 100).toFixed(0)}%)`).join('\n') || 'None listed'}

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
          console.log(`ERROR: ${err.message.substring(0, 80)}`);
        }

        // Rate limit
        if (i % 20 === 19) {
          console.log(`    ... ${scraped} scraped, ${skipped} skipped, ${errors} errors — pausing 5s`);
          await page.waitForTimeout(5000);
        }
      }

      console.log(`\n  ${job.name} COMPLETE`);
      console.log(`    Scraped: ${scraped} | Skipped (already done): ${skipped} | Errors: ${errors}`);
      console.log(`    Output: ${jobDir}`);
    }

    console.log('\n\n=== ALL DONE ===');

  } catch (err) {
    console.error('Fatal error:', err.message);
    console.error(err.stack);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
