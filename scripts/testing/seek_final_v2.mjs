import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync, readFileSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

const JOBS = [
  { id: 91094834, folder: 'head-of-finance-and-accounting-controller', name: 'Head of Finance' },
  { id: 91090632, folder: 'accounting-manager', name: 'Accounting Manager' },
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
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

  // Capture the full GraphQL request (query + auth headers)
  let capturedQuery = null;
  let capturedHeaders = null;
  page.on('request', (req) => {
    if (req.url().includes('graphql') && req.method() === 'POST') {
      try {
        const body = req.postDataJSON();
        if (body?.operationName === 'Applications') {
          capturedQuery = body;
          capturedHeaders = req.headers();
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

      // Load page to capture the query + auth token
      capturedQuery = null;
      capturedHeaders = null;
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(8000);

      if (!capturedQuery || !capturedHeaders) {
        console.log('  ERROR: Failed to capture GraphQL query');
        continue;
      }

      const authToken = capturedHeaders.authorization;
      const gqlQuery = capturedQuery.query;
      console.log(`  Auth token captured: ${authToken ? 'YES' : 'NO'}`);

      // PHASE 1: GraphQL replay for ALL status folders
      console.log('\nPHASE 1: Fetching ALL candidates...');
      const allMap = new Map();

      for (const status of STATUSES) {
        for (let pageNum = 1; pageNum <= 20; pageNum++) {
          const variables = {
            input: {
              jobId: job.id,
              pagination: { pageNumber: pageNum },
              sort: { sortField: 'RELEVANCE', orderBy: 'DESC' },
              filters: {
                searchText: '',
                questionnaireFilters: [],  // No filters — get ALL
                statusFolders: [status],
              },
            },
            nationalitiesInput2: { jobId: job.id },
            displayLabelInput2: { language: 'en' },
            countryNameInput2: { language: 'en' },
            displayDescriptionInput2: { language: 'en', displayFormat: 'SHORT', displayCountry: 'PH' },
          };

          // Use Playwright's request API with proper auth headers
          const response = await context.request.post('https://ph.employer.seek.com/graphql', {
            data: { operationName: 'Applications', variables, query: gqlQuery },
            headers: {
              'Content-Type': 'application/json',
              'Authorization': authToken,
              'seek-request-country': 'PH',
              'seek-request-site': 'cm-ui',
            },
          });

          const result = await response.json();
          const apps = result?.data?.applications;

          if (!apps?.result?.length) {
            if (pageNum === 1) console.log(`  ${status}: 0`);
            break;
          }

          for (const c of apps.result) allMap.set(c.adcentreProspectId, c);
          const tp = apps.pageInfo?.totalPages || 1;
          const total = apps.pageInfo?.total || 0;

          if (pageNum === 1) {
            console.log(`  ${status}: ${total} total (page 1/${tp}) — ${allMap.size} unique so far`);
          } else {
            console.log(`    page ${pageNum}/${tp}: +${apps.result.length} — ${allMap.size} unique`);
          }

          if (pageNum >= tp) break;
          await page.waitForTimeout(300);
        }
      }

      const allCandidates = [...allMap.values()];
      console.log(`\n  TOTAL UNIQUE: ${allCandidates.length}`);

      // Save raw data
      writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));

      // Save CSV
      const csvH = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Fit Level,Location\n';
      const csvR = allCandidates.map(c => {
        const d = new Date(c.appliedDateUtc).toISOString().split('T')[0];
        const loc = c.profile?.result?.homeLocation?.displayDescription || '';
        return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${d}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.fitLevelV2 || ''}","${loc.replace(/"/g, '""')}"`;
      }).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvH + csvR);
      console.log('  Saved all_candidates.json + candidates_summary.csv');

      // PHASE 2: Generate rich markdown profiles from the GraphQL data (no extra scraping needed!)
      console.log('\nPHASE 2: Generating profiles...');
      let saved = 0;

      for (const c of allCandidates) {
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);

        const wh = c.profile?.result?.workHistory || [];
        const careerText = wh.map(w => {
          const s = w.startDate ? `${w.startDate.month || '?'}/${w.startDate.year || '?'}` : '?';
          const e = w.endDate ? `${w.endDate.month || '?'}/${w.endDate.year || '?'}` : 'Present';
          return `### ${w.title || 'Unknown'} — ${w.company || 'Unknown'}\n*${s} – ${e}*\n\n${w.achievements || ''}`;
        }).join('\n\n');

        const edu = (c.profile?.result?.education || []).map(e =>
          `- **${e.name || 'Degree'}** — ${e.institute || ''} (${e.completionDate?.year || ''})`
        ).join('\n');

        const skills = (c.profile?.result?.skills || []).map(s => `- ${s.keyword}`).join('\n');
        const mq = (c.matchedQualities || []).map(q => `- ${q.displayLabel} (${(q.relevanceScore*100).toFixed(0)}%)`).join('\n');

        const qa = (c.questionnaireSubmission?.result?.questions || []).map(q => {
          const ans = (q.answers || []).map(a => a.text).join(', ');
          const flag = q.status === 'MUST_HAVE_MET' ? ' ✅' : q.status === 'MUST_HAVE_NOT_MET' ? ' ❌' : '';
          return `**Q:** ${q.text}\n**A:** ${ans}${flag}`;
        }).join('\n\n');

        const att = (c.attachmentsV2?.result || []).map(a => `- ${a.fileName} (${a.attachmentType})`).join('\n');
        const loc = c.profile?.result?.homeLocation?.displayDescription || 'N/A';

        const md = `# ${fn}

| Field | Value |
|-------|-------|
| **Candidate ID** | ${c.adcentreProspectId} |
| **Email** | ${c.email} |
| **Phone** | ${c.phone || 'N/A'} |
| **Location** | ${loc} |
| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |
| **Company** | ${c.mostRecentCompanyName || 'N/A'} |
| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths/12) + 'y ' + (c.mostRecentRoleMonths%12) + 'm' : 'N/A'} |
| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |
| **Status** | ${c.statusFolder} |
| **Fit Level** | ${c.fitLevelV2 || 'N/A'} |
| **Has Resume** | ${c.metadata?.result?.hasResume} |
| **Source** | ${c.source || 'N/A'} |

## Matched Skills
${mq || 'None'}

## Screening Questions
${qa || 'None'}

## Career History
${careerText || 'Not available'}

## Education
${edu || 'Not available'}

## Skills
${skills || 'Not available'}

## Attachments
${att || 'None'}
`;
        writeFileSync(join(jobDir, 'profiles', `${sn}.md`), md);
        saved++;
      }

      console.log(`  Generated ${saved} profiles`);
      console.log(`\n  ${job.name} COMPLETE: ${saved} profiles from ${allCandidates.length} candidates`);
      console.log(`  Output: ${jobDir}\n`);
    }

    console.log('=== ALL COMPLETE ===');
  } catch (err) {
    console.error('Fatal:', err.message);
    console.error(err.stack);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
