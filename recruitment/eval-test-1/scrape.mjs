/**
 * SEEK/JobStreet Candidate Scraper — Accounting Manager (Job ID: 91090632)
 *
 * Logs into ph.employer.seek.com, captures the GraphQL query template + auth token,
 * replays the Applications query for ALL status folders, deduplicates by prospectId,
 * and saves all_candidates.json + candidates_summary.csv.
 *
 * Usage:  node scrape.mjs
 * Requires: @playwright/test ^1.56.1
 */

import { chromium } from '@playwright/test';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

// ── Config ──────────────────────────────────────────────────────────────────
const EMAIL    = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const JOB_ID   = 91090632;                          // Accounting Manager
const OUT_DIR  = 'F:/Dropbox/Projects/BEI-ERP/recruitment/eval-test-1';

const STATUSES = [
  'INBOX', 'PRESCREEN', 'SHORTLIST', 'INTERVIEW', 'OFFER', 'ACCEPT', 'NOT_SUITABLE',
];

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Re-login if the page was redirected to authenticate/login. */
async function ensureLoggedIn(page) {
  if (page.url().includes('login') || page.url().includes('authenticate')) {
    await page.waitForTimeout(2000);
    const ef = page.locator('input[id="emailAddress"]');
    if (await ef.isVisible({ timeout: 5000 }).catch(() => false)) {
      await ef.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000); // OAuth redirect takes time
    }
  }
}

/** Escape a value for CSV (quote if it contains comma, quote, or newline). */
function csvEscape(val) {
  if (val == null) return '';
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

// ── Main ────────────────────────────────────────────────────────────────────
(async () => {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  // Launch persistent context so session survives across navigations
  const context = await chromium.launchPersistentContext(
    join(OUT_DIR, '.seek-browser-data'),
    { headless: false, acceptDownloads: true },
  );
  const page = await context.newPage();

  try {
    // ── Step 1: Login ─────────────────────────────────────────────────────
    console.log('[1/4] Navigating to SEEK jobs page (triggers login)...');
    await page.goto('https://ph.employer.seek.com/jobs', {
      waitUntil: 'domcontentloaded', timeout: 30000,
    });
    await page.waitForTimeout(3000);

    // Fill login form if presented
    const emailField = page.locator('input[id="emailAddress"]');
    if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('   Login form detected — filling credentials...');
      await emailField.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000); // OAuth redirect
    }
    console.log('   Logged in. Current URL:', page.url());

    // ── Step 2: Capture GraphQL query template + auth token ───────────────
    console.log('[2/4] Navigating to candidates page to capture GraphQL...');

    let queryTemplate = null;
    let authToken = null;

    page.on('request', (req) => {
      if (req.url().includes('graphql') && req.method() === 'POST') {
        try {
          const body = req.postDataJSON();
          if (body?.operationName === 'Applications') {
            queryTemplate = body.query;
            authToken = req.headers().authorization; // Bearer token
            console.log('   Captured GraphQL query template + auth token.');
          }
        } catch {}
      }
    });

    // Disable cache via CDP to ensure the GraphQL request fires
    const cdp = await context.newCDPSession(page);
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

    await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}`, {
      waitUntil: 'domcontentloaded', timeout: 30000,
    });
    await page.waitForTimeout(8000);
    await ensureLoggedIn(page);

    if (!queryTemplate || !authToken) {
      throw new Error(
        'Failed to capture GraphQL query template or auth token. ' +
        'The candidates page may not have fired the Applications request. ' +
        'Try running with headless: false and check the browser manually.',
      );
    }

    // ── Step 3: Replay GraphQL for ALL status folders ─────────────────────
    console.log('[3/4] Fetching candidates across all status folders...');
    const allMap = new Map(); // adcentreProspectId -> candidate object

    for (const status of STATUSES) {
      let folderCount = 0;

      for (let pageNum = 1; pageNum <= 20; pageNum++) {
        const variables = {
          input: {
            jobId: JOB_ID,   // Integer, not string
            pagination: { pageNumber: pageNum },
            sort: { sortField: 'RELEVANCE', orderBy: 'DESC' },
            filters: {
              searchText: '',
              questionnaireFilters: [],   // Empty = all candidates
              statusFolders: [status],
            },
          },
          // Required auxiliary variables (copied from captured request pattern)
          nationalitiesInput2: { jobId: JOB_ID },
          displayLabelInput2: { language: 'en' },
          countryNameInput2: { language: 'en' },
          displayDescriptionInput2: { language: 'en', displayFormat: 'SHORT', displayCountry: 'PH' },
        };

        // CRITICAL: Use context.request.post(), NOT page.evaluate(fetch())
        // page.evaluate(fetch()) does NOT carry the Authorization header
        const response = await context.request.post('https://ph.employer.seek.com/graphql', {
          data: { operationName: 'Applications', variables, query: queryTemplate },
          headers: {
            'Content-Type': 'application/json',
            'Authorization': authToken,
            'seek-request-country': 'PH',
          },
        });

        const result = await response.json();
        const apps = result?.data?.applications;

        if (!apps?.result?.length) break;

        for (const c of apps.result) {
          allMap.set(c.adcentreProspectId, c);
          folderCount++;
        }

        if (pageNum >= (apps.pageInfo?.totalPages || 1)) break;
      }

      console.log(`   ${status}: ${folderCount} candidate(s)`);
    }

    const allCandidates = [...allMap.values()];
    console.log(`   Total unique candidates: ${allCandidates.length}`);

    // ── Step 4: Save outputs ──────────────────────────────────────────────
    console.log('[4/4] Saving outputs...');

    // 4a. Raw JSON
    const jsonPath = join(OUT_DIR, 'all_candidates.json');
    writeFileSync(jsonPath, JSON.stringify(allCandidates, null, 2), 'utf-8');
    console.log(`   Saved: ${jsonPath}`);

    // 4b. CSV summary
    const csvHeaders = [
      'adcentreProspectId',
      'firstName',
      'lastName',
      'email',
      'phone',
      'mostRecentJobTitle',
      'mostRecentCompanyName',
      'mostRecentRoleMonths',
      'appliedDateUtc',
      'statusFolder',
      'fitLevelV2',
      'source',
      'hasResume',
      'hasCoverLetter',
    ];

    const csvRows = allCandidates.map((c) =>
      csvHeaders
        .map((h) => {
          if (h === 'hasResume')      return csvEscape(c.metadata?.result?.hasResume);
          if (h === 'hasCoverLetter') return csvEscape(c.metadata?.result?.hasCoverLetter);
          return csvEscape(c[h]);
        })
        .join(','),
    );

    const csvContent = [csvHeaders.join(','), ...csvRows].join('\n');
    const csvPath = join(OUT_DIR, 'candidates_summary.csv');
    writeFileSync(csvPath, csvContent, 'utf-8');
    console.log(`   Saved: ${csvPath}`);

    console.log('\nDone. All candidates fetched and saved.');
  } catch (err) {
    console.error('FATAL:', err.message);
    process.exitCode = 1;
  } finally {
    await context.close();
  }
})();
