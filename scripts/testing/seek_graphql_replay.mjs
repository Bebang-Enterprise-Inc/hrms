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

const STATUSES = ['INBOX', 'PRESCREEN', 'SHORTLIST', 'INTERVIEW', 'OFFER', 'ACCEPT', 'NOT_SUITABLE'];

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
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

  // Capture the GraphQL REQUEST body
  let capturedRequest = null;
  page.on('request', (request) => {
    if (request.url().includes('graphql') && request.method() === 'POST') {
      try {
        const body = request.postDataJSON();
        const str = JSON.stringify(body);
        if (str.includes('applications') && str.includes('pageNumber') && str.includes('statusFolder')) {
          capturedRequest = { url: request.url(), body, headers: request.headers() };
        }
      } catch {}
    }
  });

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
      console.log(`  ${job.name} (Job ID: ${job.id})`);
      console.log(`${'='.repeat(70)}`);

      const jobDir = join(BASE_DIR, job.folder);
      mkdirSync(join(jobDir, 'profiles'), { recursive: true });
      mkdirSync(join(jobDir, 'resumes'), { recursive: true });

      // Load candidates page to capture the GraphQL query
      capturedRequest = null;
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(8000);

      if (!capturedRequest) {
        console.log('  ERROR: Could not capture GraphQL query');
        // Save what the request interceptor captured
        console.log('  Trying to capture by clicking a status tab...');
        // Click the Prescreen tab to force a new GraphQL request
        const prescreenTab = page.locator('text=Prescreen').first();
        if (await prescreenTab.isVisible({ timeout: 3000 }).catch(() => false)) {
          await prescreenTab.click();
          await page.waitForTimeout(5000);
        }
      }

      if (!capturedRequest) {
        console.log('  Still no GraphQL query captured, dumping all request info...');
        // Let's try another approach - just dump the query we need
        // We know the GraphQL endpoint and can construct the query
        continue;
      }

      console.log('  Captured GraphQL query!');
      writeFileSync(join(jobDir, 'graphql_query.json'), JSON.stringify(capturedRequest, null, 2));

      // Now replay for each status folder
      const allMap = new Map();

      for (const status of STATUSES) {
        for (let pageNum = 1; pageNum <= 20; pageNum++) {
          // Deep clone and modify the query
          const queryBody = JSON.parse(JSON.stringify(capturedRequest.body));

          // Modify variables - handle both array and single query
          const queries = Array.isArray(queryBody) ? queryBody : [queryBody];
          for (const q of queries) {
            if (q.variables && JSON.stringify(q).includes('statusFolder')) {
              q.variables.statusFolder = status;
              q.variables.pageNumber = pageNum;
            }
          }

          const result = await page.evaluate(async ({ url, body }) => {
            const r = await fetch(url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
            });
            return r.json();
          }, { url: capturedRequest.url, body: Array.isArray(queryBody) ? queries : queries[0] });

          // Extract applications
          let apps = null;
          if (Array.isArray(result)) {
            for (const r of result) {
              if (r?.data?.applications) { apps = r.data.applications; break; }
            }
          } else {
            apps = result?.data?.applications;
          }

          if (!apps?.result?.length) break;

          for (const c of apps.result) allMap.set(c.adcentreProspectId, c);

          const tp = apps.pageInfo?.totalPages || 1;
          if (pageNum === 1) {
            console.log(`  ${status}: page 1/${tp}, ${apps.result.length} candidates (${allMap.size} total)`);
          } else {
            console.log(`    page ${pageNum}/${tp}: +${apps.result.length} (${allMap.size} total)`);
          }

          if (pageNum >= tp) break;
          await page.waitForTimeout(500);
        }
      }

      const allCandidates = [...allMap.values()];
      console.log(`\n  TOTAL: ${allCandidates.length} unique candidates`);

      // Save
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));
      const csvH = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter,Months in Role\n';
      const csvR = allCandidates.map(c => {
        const d = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${d}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}","${c.mostRecentRoleMonths || ''}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvH + csvR);
      console.log('  Saved all_candidates.json + candidates_summary.csv\n');

      // PHASE 2: Scrape profiles + resumes
      console.log('PHASE 2: Scraping profiles + resumes...');
      let scraped = 0, errors = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const pid = c.adcentreProspectId;
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);
        const mdPath = join(jobDir, 'profiles', `${sn}.md`);

        if (existsSync(mdPath)) { continue; } // skip already done

        process.stdout.write(`  [${i+1}/${allCandidates.length}] ${fn}... `);

        try {
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${pid}&tab=profile`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2500);

          const bt = await page.locator('body').textContent();
          let profileText = '';
          const ci = bt.indexOf('Career history');
          if (ci > 0) profileText = bt.substring(ci, ci + 5000);

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

          const md = `# ${fn}\n\n| Field | Value |\n|-------|-------|\n| **Candidate ID** | ${pid} |\n| **Email** | ${c.email} |\n| **Phone** | ${c.phone || 'N/A'} |\n| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |\n| **Company** | ${c.mostRecentCompanyName || 'N/A'} |\n| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths / 12) + 'y ' + (c.mostRecentRoleMonths % 12) + 'm' : 'N/A'} |\n| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |\n| **Status** | ${c.statusFolder} |\n\n## Skills\n${(c.matchedQualities || []).map(q => '- ' + q.displayLabel + ' (' + (q.relevanceScore * 100).toFixed(0) + '%)').join('\n') || 'None'}\n\n## Career History\n${profileText || 'Not available'}\n\n## Resume Content\n${resumeText || 'Not available'}\n`;
          writeFileSync(mdPath, md);
          scraped++;
          console.log('OK');
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 60)}`);
        }

        if (i % 25 === 24) {
          console.log(`    --- ${scraped} done, ${errors} errors --- pausing 5s`);
          await page.waitForTimeout(5000);
        }
      }

      console.log(`\n  ${job.name} DONE: ${scraped} new profiles, ${errors} errors`);
      console.log(`  Output: ${jobDir}\n`);
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
