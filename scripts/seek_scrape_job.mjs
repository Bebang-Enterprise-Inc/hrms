#!/usr/bin/env node
/**
 * SEEK/JobStreet Full Pipeline Scraper
 *
 * Usage:
 *   node scripts/seek_scrape_job.mjs <JOB_ID> <FOLDER_NAME> [--download-resumes] [--agents N]
 *
 * Examples:
 *   node scripts/seek_scrape_job.mjs 91094834 head-of-finance --download-resumes
 *   node scripts/seek_scrape_job.mjs 91090632 accounting-manager --download-resumes --agents 6
 *   node scripts/seek_scrape_job.mjs 91094834 head-of-finance  # profiles only, no resume download
 *
 * Outputs to: recruitment/{FOLDER_NAME}/
 *   all_candidates.json, candidates_summary.csv, profiles/*.md, resumes/*
 *
 * Credentials: Set SEEK_EMAIL and SEEK_PASSWORD env vars, or they default to sam@bebang.ph
 *
 * Battle-tested: 274 candidates, 261 resumes downloaded, March 2026
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync, readFileSync } from 'fs';
import { join } from 'path';

// === Config ===
const args = process.argv.slice(2);
if (args.length < 2) {
  console.log('Usage: node seek_scrape_job.mjs <JOB_ID> <FOLDER_NAME> [--download-resumes] [--agents N]');
  console.log('Example: node seek_scrape_job.mjs 91094834 head-of-finance --download-resumes --agents 6');
  process.exit(1);
}

const JOB_ID = parseInt(args[0]);
const FOLDER = args[1];
const DOWNLOAD_RESUMES = args.includes('--download-resumes');
const AGENT_COUNT = parseInt(args[args.indexOf('--agents') + 1]) || 1;
const EMAIL = process.env.SEEK_EMAIL || 'sam@bebang.ph';
const PASSWORD = process.env.SEEK_PASSWORD || '';
const BASE_DIR = join(process.cwd(), 'recruitment');

if (!PASSWORD) {
  console.error('ERROR: Set SEEK_PASSWORD env var or pass password');
  process.exit(1);
}

const STATUSES = ['INBOX', 'PRESCREEN', 'SHORTLIST', 'INTERVIEW', 'OFFER', 'ACCEPT', 'NOT_SUITABLE'];

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
}

async function ensureLoggedIn(page) {
  if (page.url().includes('login') || page.url().includes('authenticate')) {
    console.log('  Session lost — re-logging in...');
    await page.waitForTimeout(2000);
    const ef = page.locator('input[id="emailAddress"]');
    if (await ef.isVisible({ timeout: 5000 }).catch(() => false)) {
      await ef.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000);
    }
  }
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

  // Capture GraphQL query template + auth token
  let queryTemplate = null;
  let authToken = null;
  page.on('request', (req) => {
    if (req.url().includes('graphql') && req.method() === 'POST') {
      try {
        const body = req.postDataJSON();
        if (body?.operationName === 'Applications') {
          queryTemplate = body.query;
          authToken = req.headers().authorization;
        }
      } catch {}
    }
  });

  try {
    // === LOGIN ===
    console.log('Logging in...');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    await ensureLoggedIn(page);
    console.log('Logged in.\n');

    const jobDir = join(BASE_DIR, FOLDER);
    mkdirSync(join(jobDir, 'profiles'), { recursive: true });
    mkdirSync(join(jobDir, 'resumes'), { recursive: true });

    // === PHASE 1: CAPTURE GRAPHQL QUERY ===
    console.log(`Loading candidates page for job ${JOB_ID}...`);
    await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}`, {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    await page.waitForTimeout(8000);
    await ensureLoggedIn(page);

    if (!queryTemplate || !authToken) {
      console.error('ERROR: Failed to capture GraphQL query. Try again.');
      process.exit(1);
    }
    console.log('GraphQL query captured.\n');

    // === PHASE 2: FETCH ALL CANDIDATES VIA GRAPHQL ===
    console.log('Fetching ALL candidates across all status folders...');
    const allMap = new Map();

    for (const status of STATUSES) {
      for (let pageNum = 1; pageNum <= 20; pageNum++) {
        const variables = {
          input: {
            jobId: JOB_ID,
            pagination: { pageNumber: pageNum },
            sort: { sortField: 'RELEVANCE', orderBy: 'DESC' },
            filters: { searchText: '', questionnaireFilters: [], statusFolders: [status] },
          },
          nationalitiesInput2: { jobId: JOB_ID },
          displayLabelInput2: { language: 'en' },
          countryNameInput2: { language: 'en' },
          displayDescriptionInput2: { language: 'en', displayFormat: 'SHORT', displayCountry: 'PH' },
        };

        const response = await context.request.post('https://ph.employer.seek.com/graphql', {
          data: { operationName: 'Applications', variables, query: queryTemplate },
          headers: { 'Content-Type': 'application/json', 'Authorization': authToken, 'seek-request-country': 'PH' },
        });

        const result = await response.json();
        const apps = result?.data?.applications;
        if (!apps?.result?.length) { if (pageNum === 1) console.log(`  ${status}: 0`); break; }

        for (const c of apps.result) allMap.set(c.adcentreProspectId, c);
        const tp = apps.pageInfo?.totalPages || 1;
        console.log(`  ${status}: page ${pageNum}/${tp}, ${allMap.size} total unique`);
        if (pageNum >= tp) break;
        await page.waitForTimeout(300);
      }
    }

    const allCandidates = [...allMap.values()];
    console.log(`\nTOTAL: ${allCandidates.length} unique candidates\n`);

    // === SAVE RAW DATA ===
    writeFileSync(join(jobDir, 'all_candidates.json'), JSON.stringify(allCandidates, null, 2));

    const csvH = 'Prospect ID,First Name,Last Name,Email,Phone,Current Role,Company,Applied Date,Status,Has Resume,Fit Level,Location\n';
    const csvR = allCandidates.map(c => {
      const d = new Date(c.appliedDateUtc).toISOString().split('T')[0];
      const loc = c.profile?.result?.homeLocation?.displayDescription || '';
      return `"${c.adcentreProspectId}","${c.firstName}","${c.lastName}","${c.email}","${c.phone || ''}","${(c.mostRecentJobTitle || '').replace(/"/g, '""')}","${(c.mostRecentCompanyName || '').replace(/"/g, '""')}","${d}","${c.statusFolder}","${c.metadata?.result?.hasResume || false}","${c.fitLevelV2 || ''}","${loc.replace(/"/g, '""')}"`;
    }).join('\n');
    writeFileSync(join(jobDir, 'candidates_summary.csv'), csvH + csvR);
    console.log('Saved all_candidates.json + candidates_summary.csv');

    // === PHASE 3: GENERATE PROFILES ===
    console.log('\nGenerating profiles...');
    for (const c of allCandidates) {
      const fn = `${c.firstName} ${c.lastName}`.trim();
      const sn = sanitize(fn);
      const wh = (c.profile?.result?.workHistory || []).map(w => {
        const s = w.startDate ? `${w.startDate.month || '?'}/${w.startDate.year || '?'}` : '?';
        const e = w.endDate ? `${w.endDate.month || '?'}/${w.endDate.year || '?'}` : 'Present';
        return `### ${w.title || 'Unknown'} — ${w.company || 'Unknown'}\n*${s} – ${e}*\n\n${w.achievements || ''}`;
      }).join('\n\n');
      const edu = (c.profile?.result?.education || []).map(e => `- **${e.name || 'Degree'}** — ${e.institute || ''} (${e.completionDate?.year || ''})`).join('\n');
      const skills = (c.profile?.result?.skills || []).map(s => `- ${s.keyword}`).join('\n');
      const mq = (c.matchedQualities || []).map(q => `- ${q.displayLabel} (${(q.relevanceScore*100).toFixed(0)}%)`).join('\n');
      const qa = (c.questionnaireSubmission?.result?.questions || []).map(q => {
        const ans = (q.answers || []).map(a => a.text).join(', ');
        const flag = q.status === 'MUST_HAVE_MET' ? ' ✅' : q.status === 'MUST_HAVE_NOT_MET' ? ' ❌' : '';
        return `**Q:** ${q.text}\n**A:** ${ans}${flag}`;
      }).join('\n\n');
      const att = (c.attachmentsV2?.result || []).map(a => `- ${a.fileName} (${a.attachmentType})`).join('\n');
      const loc = c.profile?.result?.homeLocation?.displayDescription || 'N/A';

      const md = `# ${fn}\n\n| Field | Value |\n|-------|-------|\n| **Candidate ID** | ${c.adcentreProspectId} |\n| **Email** | ${c.email} |\n| **Phone** | ${c.phone || 'N/A'} |\n| **Location** | ${loc} |\n| **Current Role** | ${c.mostRecentJobTitle || 'N/A'} |\n| **Company** | ${c.mostRecentCompanyName || 'N/A'} |\n| **Time in Role** | ${c.mostRecentRoleMonths ? Math.floor(c.mostRecentRoleMonths/12) + 'y ' + (c.mostRecentRoleMonths%12) + 'm' : 'N/A'} |\n| **Applied** | ${new Date(c.appliedDateUtc).toLocaleDateString('en-PH')} |\n| **Status** | ${c.statusFolder} |\n| **Fit Level** | ${c.fitLevelV2 || 'N/A'} |\n| **Has Resume** | ${c.metadata?.result?.hasResume} |\n| **Source** | ${c.source || 'N/A'} |\n\n## Matched Skills\n${mq || 'None'}\n\n## Screening Questions\n${qa || 'None'}\n\n## Career History\n${wh || 'Not available'}\n\n## Education\n${edu || 'Not available'}\n\n## Skills\n${skills || 'Not available'}\n\n## Attachments\n${att || 'None'}\n`;
      writeFileSync(join(jobDir, 'profiles', `${sn}.md`), md);
    }
    console.log(`Generated ${allCandidates.length} profiles.`);

    // === PHASE 4: DOWNLOAD RESUMES ===
    if (DOWNLOAD_RESUMES) {
      const withResume = allCandidates.filter(c => c.metadata?.result?.hasResume);
      console.log(`\nDownloading resumes for ${withResume.length} candidates...`);

      let downloaded = 0, skipped = 0, noBtn = 0, errors = 0;

      for (let i = 0; i < withResume.length; i++) {
        const c = withResume[i];
        const pid = c.adcentreProspectId;
        const fn = `${c.firstName} ${c.lastName}`.trim();
        const sn = sanitize(fn);
        const resumeDir = join(jobDir, 'resumes');

        const exists = ['pdf', 'doc', 'docx', 'rtf', 'PDF'].some(ext => existsSync(join(resumeDir, `${sn}.${ext}`)));
        if (exists) { skipped++; continue; }

        process.stdout.write(`  [${i+1}/${withResume.length}] ${fn}... `);

        try {
          await page.goto(
            `https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}&selected=${pid}&tab=resume`,
            { waitUntil: 'load', timeout: 20000 }
          );
          await page.waitForTimeout(4000);
          await ensureLoggedIn(page);

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
            console.log('no file uploaded');
          }
        } catch (err) {
          errors++;
          console.log(`ERR: ${err.message.substring(0, 50)}`);
        }

        if ((i + 1) % 25 === 0) {
          console.log(`    --- ${downloaded} OK, ${skipped} skip, ${noBtn} no file, ${errors} err`);
          await page.waitForTimeout(3000);
        }
      }

      console.log(`\nResumes: ${downloaded} downloaded, ${skipped} existed, ${noBtn} no file, ${errors} errors`);
    }

    console.log(`\n=== DONE: ${FOLDER} ===`);
    console.log(`Output: ${jobDir}`);

  } catch (err) {
    console.error('Fatal:', err.message);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
