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

async function login(page) {
  await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);
  const emailField = page.locator('input[id="emailAddress"]');
  if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailField.fill(EMAIL);
    await page.locator('input[id="password"]').fill(PASSWORD);
    await page.locator('button:has-text("Sign in")').first().click();
    await page.waitForTimeout(8000);
  }
}

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

async function fetchAllCandidatesViaGraphQL(page, jobId) {
  // Intercept the GraphQL query that loads candidates
  let capturedQuery = null;
  let capturedHeaders = {};

  const handler = async (request) => {
    if (request.url().includes('graphql') && request.method() === 'POST') {
      try {
        const postData = request.postDataJSON();
        const str = JSON.stringify(postData);
        if (str.includes('applications') && str.includes('pageSize')) {
          capturedQuery = postData;
          capturedHeaders = request.headers();
        }
      } catch {}
    }
  };

  page.on('request', handler);

  // Navigate to candidate list - forces a fresh GraphQL request
  await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${jobId}`, {
    waitUntil: 'domcontentloaded', timeout: 30000
  });
  await page.waitForTimeout(8000);

  page.removeListener('request', handler);

  if (!capturedQuery) {
    console.log('  WARNING: Could not capture GraphQL query, trying manual approach');
    return null;
  }

  console.log('  Captured GraphQL query');

  // Now replay the query for each page, fetching all candidates
  const allCandidates = [];

  for (let pageNum = 1; pageNum <= 20; pageNum++) {
    const queryBody = JSON.parse(JSON.stringify(capturedQuery));

    // Handle array format (batched queries)
    const queries = Array.isArray(queryBody) ? queryBody : [queryBody];

    // Find the applications query and modify it
    for (const q of queries) {
      if (JSON.stringify(q).includes('applications')) {
        if (q.variables) {
          q.variables.pageNumber = pageNum;
          q.variables.pageSize = 50; // max page size
        }
      }
    }

    const result = await page.evaluate(async ({ url, body }) => {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
      });
      return response.json();
    }, { url: 'https://ph.employer.seek.com/graphql', body: Array.isArray(queryBody) ? queries : queries[0] });

    // Extract applications from the result
    let apps = null;
    if (Array.isArray(result)) {
      for (const r of result) {
        if (r?.data?.applications) { apps = r.data.applications; break; }
      }
    } else {
      apps = result?.data?.applications;
    }

    if (!apps?.result?.length) {
      console.log(`  Page ${pageNum}: no results, done`);
      break;
    }

    allCandidates.push(...apps.result);
    const totalPages = apps.pageInfo?.totalPages || 1;
    console.log(`  Page ${pageNum}/${totalPages}: ${apps.result.length} candidates (total: ${allCandidates.length})`);

    if (pageNum >= totalPages) break;
    await page.waitForTimeout(1000);
  }

  return allCandidates;
}

async function scrapeProfileAndResume(page, jobId, prospectId) {
  const profileUrl = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${prospectId}&tab=profile`;
  await page.goto(profileUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000);

  let profileText = '';
  let resumeText = '';

  try {
    // Get profile panel text
    const bodyText = await page.locator('body').textContent();

    // Find profile content — starts after the candidate name
    // Skip the navigation/menu text and focus on the detail panel
    const careerIdx = bodyText.indexOf('Career history');
    const profileIdx = bodyText.indexOf('Profile');
    const startIdx = Math.max(careerIdx, profileIdx, 0);
    if (startIdx > 0) {
      profileText = bodyText.substring(startIdx, startIdx + 5000);
    }

    // Click Resume tab
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
  } catch (err) {
    console.log(`    Error scraping profile: ${err.message}`);
  }

  return { profileText, resumeText };
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

  try {
    await login(page);
    console.log('Logged in.\n');

    for (const job of JOBS) {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`Processing: ${job.name} (Job ID: ${job.id})`);
      console.log(`${'='.repeat(60)}`);

      const jobDir = join(BASE_DIR, job.folder);
      mkdirSync(join(jobDir, 'profiles'), { recursive: true });
      mkdirSync(join(jobDir, 'resumes'), { recursive: true });

      // Step 1: Fetch all candidates via GraphQL
      console.log('\nStep 1: Fetching all candidates via GraphQL...');
      let candidates = await fetchAllCandidatesViaGraphQL(page, job.id);

      if (!candidates || candidates.length === 0) {
        console.log('  No candidates found via GraphQL, skipping');
        continue;
      }

      // Save raw candidate data
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(candidates, null, 2));
      console.log(`\nTotal candidates: ${candidates.length}`);

      // Step 2: Create summary CSV
      const csvHeader = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Has Cover Letter\n';
      const csvRows = candidates.map(c => {
        const applied = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone}","${c.mostRecentJobTitle || ''}","${c.mostRecentCompanyName || ''}","${applied}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.metadata?.result?.hasCoverLetter || false}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);
      console.log('Saved candidates_summary.csv');

      // Step 3: Scrape detailed profiles + resumes for each candidate
      console.log('\nStep 3: Scraping individual profiles and resumes...');

      for (let i = 0; i < candidates.length; i++) {
        const c = candidates[i];
        const prospectId = c.adcentreProspectId;
        const fullName = `${c.firstName} ${c.lastName}`.trim();
        const safeName = sanitize(fullName);

        // Skip if already scraped
        const mdPath = join(jobDir, 'profiles', `${safeName}.md`);
        if (existsSync(mdPath)) {
          console.log(`  [${i+1}/${candidates.length}] ${fullName} — already scraped, skipping`);
          continue;
        }

        console.log(`  [${i+1}/${candidates.length}] ${fullName} (${prospectId})...`);

        const { profileText, resumeText } = await scrapeProfileAndResume(page, job.id, prospectId);

        // Save markdown profile
        const mdContent = `# ${fullName}

**Candidate ID:** ${prospectId}
**Email:** ${c.email}
**Phone:** ${c.phone}
**Current Role:** ${c.mostRecentJobTitle || 'N/A'} at ${c.mostRecentCompanyName || 'N/A'}
**Applied:** ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')}
**Status:** ${c.statusFolder}
**Has Resume:** ${c.metadata?.result?.hasResume}
**Has Cover Letter:** ${c.metadata?.result?.hasCoverLetter}

## Skills
${(c.matchedQualities || []).map(q => `- ${q.displayLabel}`).join('\n')}

## Profile / Career History
${profileText}

## Resume
${resumeText}
`;
        writeFileSync(mdPath, mdContent);

        // Rate limit
        if (i % 10 === 9) {
          console.log(`    ... pausing 3s (${i+1}/${candidates.length} done)`);
          await page.waitForTimeout(3000);
        } else {
          await page.waitForTimeout(500);
        }
      }

      console.log(`\nCompleted ${job.name}: ${candidates.length} profiles scraped`);
      console.log(`Output: ${jobDir}`);
    }

    console.log('\n\n=== ALL DONE ===');

  } catch (err) {
    console.error('Fatal error:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: 'scratchpad/qa/seek_full_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
