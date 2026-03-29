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

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu'],
  });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  // Global GraphQL interceptor — capture ALL graphql responses
  const graphqlData = {};
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
            const key = `page_${Date.now()}`;
            graphqlData[key] = apps;
            console.log(`    [GraphQL] Captured ${apps.result.length} candidates (page ${apps.pageInfo?.pageNumber}/${apps.pageInfo?.totalPages})`);
          }
        }
        // Also capture the request body for replay
        if (str.includes('"applications"')) {
          try {
            const reqBody = response.request().postDataJSON();
            if (reqBody) graphqlData['_lastQuery'] = reqBody;
          } catch {}
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
    console.log('Logged in.');

    for (const job of JOBS) {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`Processing: ${job.name} (Job ID: ${job.id})`);
      console.log(`${'='.repeat(60)}`);

      const jobDir = join(BASE_DIR, job.folder);
      mkdirSync(join(jobDir, 'profiles'), { recursive: true });

      // Reset captured data
      for (const key of Object.keys(graphqlData)) delete graphqlData[key];

      // Step 1: Load the candidate list page — this triggers the GraphQL request
      console.log('\nStep 1: Loading candidate list...');
      // Disable cache for this navigation
      await page.route('**/*', route => route.continue());
      const cdpSession = await context.newCDPSession(page);
      await cdpSession.send('Network.setCacheDisabled', { cacheDisabled: true });

      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(8000);

      // Check what we captured
      const capturedPages = Object.keys(graphqlData).filter(k => k !== '_lastQuery');
      console.log(`  Captured ${capturedPages.length} GraphQL response(s)`);

      let allCandidates = [];

      if (capturedPages.length > 0) {
        // Collect candidates from captured responses
        for (const key of capturedPages) {
          allCandidates.push(...graphqlData[key].result);
        }

        // Check if we need more pages
        const lastApps = graphqlData[capturedPages[capturedPages.length - 1]];
        const totalPages = lastApps.pageInfo?.totalPages || 1;

        if (totalPages > 1 && graphqlData._lastQuery) {
          console.log(`  Need ${totalPages} pages total, fetching remaining...`);

          for (let p = 2; p <= totalPages; p++) {
            // Clear captured data for this page
            for (const key of Object.keys(graphqlData).filter(k => k !== '_lastQuery')) delete graphqlData[key];

            // Click "Next" button to load next page
            const nextBtn = page.locator('a:has-text("Next"), button:has-text("Next")').last();
            if (await nextBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
              await nextBtn.click();
              await page.waitForTimeout(5000);

              // Collect new candidates
              const newPages = Object.keys(graphqlData).filter(k => k !== '_lastQuery');
              for (const key of newPages) {
                allCandidates.push(...graphqlData[key].result);
              }
            } else {
              console.log(`  No Next button on page ${p}`);
              break;
            }
          }
        }
      }

      // Deduplicate by adcentreProspectId
      const uniqueMap = new Map();
      for (const c of allCandidates) {
        uniqueMap.set(c.adcentreProspectId, c);
      }
      allCandidates = [...uniqueMap.values()];

      console.log(`\nTotal unique candidates: ${allCandidates.length}`);

      if (allCandidates.length === 0) {
        console.log('  No candidates found, skipping');
        continue;
      }

      // Save raw data
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));

      // Save summary CSV
      const csvHeader = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter\n';
      const csvRows = allCandidates.map(c => {
        const applied = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${applied}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);
      console.log('Saved candidates_summary.csv');

      // Step 2: Scrape profile + resume for each candidate
      console.log('\nStep 2: Scraping profiles and resumes...');
      let scraped = 0;
      let errors = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const prospectId = c.adcentreProspectId;
        const fullName = `${c.firstName} ${c.lastName}`.trim();
        const safeName = sanitize(fullName);
        const mdPath = join(jobDir, 'profiles', `${safeName}.md`);

        if (existsSync(mdPath)) {
          console.log(`  [${i+1}/${allCandidates.length}] ${fullName} — already done`);
          scraped++;
          continue;
        }

        process.stdout.write(`  [${i+1}/${allCandidates.length}] ${fullName}... `);

        try {
          // Navigate to profile
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${prospectId}&tab=profile`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2500);

          // Get career history
          const bodyText = await page.locator('body').textContent();
          const careerIdx = bodyText.indexOf('Career history');
          let profileText = '';
          if (careerIdx > 0) {
            profileText = bodyText.substring(careerIdx, careerIdx + 5000);
          }

          // Click Resume tab
          let resumeText = '';
          const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
          if (await resumeTab.isVisible({ timeout: 2000 }).catch(() => false)) {
            await resumeTab.click();
            await page.waitForTimeout(2000);
            const resumeBody = await page.locator('body').textContent();
            const notesIdx = resumeBody.lastIndexOf('Notes and attachments');
            if (notesIdx > 0) {
              resumeText = resumeBody.substring(notesIdx + 25, notesIdx + 10000);
            }
          }

          // Save
          const mdContent = `# ${fullName}

| Field | Value |
|-------|-------|
| **Candidate ID** | ${prospectId} |
| **Email** | ${c.email} |
| **Phone** | ${c.phone || 'N/A'} |
| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |
| **Company** | ${c.mostRecentCompanyName || 'N/A'} |
| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |
| **Status** | ${c.statusFolder} |
| **Has Resume** | ${c.metadata?.result?.hasResume} |
| **Has Cover Letter** | ${c.metadata?.result?.hasCoverLetter} |

## Skills
${(c.matchedQualities || []).map(q => `- ${q.displayLabel} (relevance: ${(q.relevanceScore * 100).toFixed(0)}%)`).join('\n') || 'None listed'}

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
          console.log(`ERROR: ${err.message}`);
        }

        // Rate limit
        if (i % 15 === 14) {
          console.log(`    ... ${scraped} done, ${errors} errors, pausing 5s`);
          await page.waitForTimeout(5000);
        }
      }

      console.log(`\n${job.name} complete: ${scraped} scraped, ${errors} errors`);
      console.log(`Output: ${jobDir}`);
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
