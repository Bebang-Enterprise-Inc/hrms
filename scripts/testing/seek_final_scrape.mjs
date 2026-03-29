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
    acceptDownloads: true,
  });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

  // Capture the GraphQL query template
  let queryTemplate = null;
  page.on('request', (req) => {
    if (req.url().includes('graphql') && req.method() === 'POST') {
      try {
        const body = req.postDataJSON();
        if (body?.operationName === 'Applications' && body?.query) {
          queryTemplate = body.query;
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

      // Load page to capture the query template
      queryTemplate = null;
      await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${job.id}`, {
        waitUntil: 'domcontentloaded', timeout: 30000
      });
      await page.waitForTimeout(8000);

      if (!queryTemplate) {
        // Try from saved file
        const savedPath = join(jobDir, 'graphql_query.json');
        if (existsSync(savedPath)) {
          const saved = JSON.parse(readFileSync(savedPath, 'utf8'));
          queryTemplate = saved.body.query;
        }
      }

      if (!queryTemplate) {
        console.log('  ERROR: No GraphQL query template captured');
        continue;
      }

      console.log('\nPHASE 1: Fetching ALL candidates via GraphQL replay...');
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
                questionnaireFilters: [],
                statusFolders: [status],
              },
            },
            nationalitiesInput2: { jobId: job.id },
            displayLabelInput2: { language: 'en' },
            countryNameInput2: { language: 'en' },
            displayDescriptionInput2: { language: 'en', displayFormat: 'SHORT', displayCountry: 'PH' },
          };

          const result = await page.evaluate(async ({ query, variables }) => {
            const r = await fetch('https://ph.employer.seek.com/graphql', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ operationName: 'Applications', variables, query }),
            });
            return r.json();
          }, { query: queryTemplate, variables });

          const apps = result?.data?.applications;
          if (!apps?.result?.length) {
            if (pageNum === 1) console.log(`  ${status}: 0`);
            break;
          }

          for (const c of apps.result) allMap.set(c.adcentreProspectId, c);
          const tp = apps.pageInfo?.totalPages || 1;

          if (pageNum === 1) {
            console.log(`  ${status}: ${apps.pageInfo?.total || apps.result.length} total (page 1/${tp}) — ${allMap.size} unique`);
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

      // PHASE 2: Save profiles from GraphQL data (already have full data!)
      console.log('\nPHASE 2: Saving profiles from GraphQL data...');
      let saved = 0;

      for (const c of allCandidates) {
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);

        // Build career history from profile.workHistory
        const wh = c.profile?.result?.workHistory || [];
        const careerText = wh.map(w => {
          const start = w.startDate ? `${w.startDate.month || ''}/${w.startDate.year || ''}` : '?';
          const end = w.endDate ? `${w.endDate.month || ''}/${w.endDate.year || ''}` : 'Present';
          return `### ${w.title || 'Unknown Role'} — ${w.company || 'Unknown'}\n*${start} – ${end}*\n\n${w.achievements || ''}`;
        }).join('\n\n');

        // Education
        const edu = c.profile?.result?.education || [];
        const eduText = edu.map(e => {
          const year = e.completionDate?.year || '';
          return `- **${e.name || 'Degree'}** — ${e.institute || 'Unknown'} (${year})`;
        }).join('\n');

        // Skills
        const skills = c.profile?.result?.skills || [];
        const skillText = skills.map(s => `- ${s.keyword}`).join('\n');

        // Matched qualities
        const mq = (c.matchedQualities || []).map(q =>
          `- ${q.displayLabel} (${(q.relevanceScore * 100).toFixed(0)}%)`
        ).join('\n');

        // Screening answers
        const qa = c.questionnaireSubmission?.result?.questions || [];
        const qaText = qa.map(q => {
          const answers = (q.answers || []).map(a => a.text).join(', ');
          return `**Q:** ${q.text}\n**A:** ${answers} ${q.status === 'MUST_HAVE_MET' ? '✅' : q.status === 'MUST_HAVE_NOT_MET' ? '❌' : ''}`;
        }).join('\n\n');

        // Attachments (resume files)
        const att = c.attachmentsV2?.result || [];
        const attText = att.map(a => `- ${a.fileName} (${a.attachmentType}, ID: ${a.attachmentId})`).join('\n');

        // Location
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
| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths / 12) + 'y ' + (c.mostRecentRoleMonths % 12) + 'm' : 'N/A'} |
| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |
| **Status** | ${c.statusFolder} |
| **Fit Level** | ${c.fitLevelV2 || 'N/A'} |
| **Has Resume** | ${c.metadata?.result?.hasResume} |
| **Has Cover Letter** | ${c.metadata?.result?.hasCoverLetter} |
| **Source** | ${c.source || 'N/A'} |

## Matched Skills
${mq || 'None'}

## Screening Questions
${qaText || 'None'}

## Career History
${careerText || 'Not available'}

## Education
${eduText || 'Not available'}

## Skills
${skillText || 'Not available'}

## Attachments
${attText || 'None'}
`;
        writeFileSync(join(jobDir, 'profiles', `${sn}.md`), md);
        saved++;
      }

      console.log(`  Saved ${saved} profiles`);

      // PHASE 3: Download resume PDFs using attachment IDs
      console.log('\nPHASE 3: Downloading resume PDFs...');
      let pdfs = 0;

      for (let i = 0; i < allCandidates.length; i++) {
        const c = allCandidates[i];
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);
        const att = c.attachmentsV2?.result || [];
        const resume = att.find(a => a.attachmentType === 'RESUME' || a.attachmentType === 'CV');

        if (!resume) continue;

        const pdfPath = join(jobDir, 'resumes', `${sn}.pdf`);
        if (existsSync(pdfPath)) { pdfs++; continue; }

        // Try to download via the candidate detail page
        try {
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${job.id}&selected=${c.adcentreProspectId}&tab=resume`,
            { waitUntil: 'domcontentloaded', timeout: 15000 }
          );
          await page.waitForTimeout(2000);

          // Look for download link
          const dlLink = page.locator('a[download], a:has-text("Download"), button:has-text("Download")').first();
          if (await dlLink.isVisible({ timeout: 2000 }).catch(() => false)) {
            const [download] = await Promise.all([
              page.waitForEvent('download', { timeout: 5000 }),
              dlLink.click(),
            ]);
            await download.saveAs(pdfPath);
            pdfs++;
            if (pdfs % 10 === 0) console.log(`  ${pdfs} PDFs downloaded so far...`);
          }
        } catch {}

        if (i % 30 === 29) await page.waitForTimeout(3000);
      }

      console.log(`  Downloaded ${pdfs} resume PDFs`);
      console.log(`\n  ${job.name} COMPLETE: ${saved} profiles, ${pdfs} PDFs`);
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
