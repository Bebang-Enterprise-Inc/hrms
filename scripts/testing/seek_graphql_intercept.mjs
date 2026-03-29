import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';

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

  // Intercept GraphQL REQUESTS (not just responses) to capture the query structure
  const graphqlRequests = [];
  page.on('request', async (request) => {
    if (request.url().includes('graphql') && request.method() === 'POST') {
      try {
        const postData = request.postDataJSON();
        if (postData && JSON.stringify(postData).includes('application')) {
          graphqlRequests.push({
            url: request.url(),
            headers: request.headers(),
            body: postData,
          });
        }
      } catch {}
    }
  });

  // Also intercept responses for the applications query
  const graphqlResponses = [];
  page.on('response', async (response) => {
    if (response.url().includes('graphql') && response.request().method() === 'POST') {
      try {
        const body = await response.json().catch(() => null);
        if (body && JSON.stringify(body).includes('applications')) {
          graphqlResponses.push({
            url: response.url(),
            body,
          });
        }
      } catch {}
    }
  });

  try {
    await login(page);

    // Load candidate list
    await page.goto('https://ph.employer.seek.com/candidates/?jobid=91094834', {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    await page.waitForTimeout(8000);

    console.log(`Intercepted ${graphqlRequests.length} GraphQL requests with 'application'`);

    // Save the GraphQL request details (query + variables + headers)
    for (let i = 0; i < graphqlRequests.length; i++) {
      const req = graphqlRequests[i];
      console.log(`\n=== Request ${i+1} ===`);
      console.log('URL:', req.url);
      console.log('Query:', JSON.stringify(req.body).substring(0, 500));

      // Save full request
      writeFileSync(
        join(BASE_DIR, `graphql_request_${i+1}.json`),
        JSON.stringify({
          url: req.url,
          headers: req.headers,
          body: req.body,
        }, null, 2)
      );
    }

    // Now use the intercepted GraphQL query to fetch ALL candidates
    // by modifying the variables (remove filters, increase page size)
    if (graphqlRequests.length > 0) {
      const lastReq = graphqlRequests[graphqlRequests.length - 1];
      console.log('\n=== Using GraphQL query to fetch all candidates ===');
      console.log('Variables:', JSON.stringify(lastReq.body.variables || lastReq.body[0]?.variables));

      // Make the request via page.evaluate to use existing auth cookies
      const allCandidates = [];

      for (let pageNum = 1; pageNum <= 15; pageNum++) {
        console.log(`  Fetching page ${pageNum}...`);

        // Modify the variables to remove filters and set page number
        const requestBody = JSON.parse(JSON.stringify(lastReq.body));

        // Handle both single query and array format
        const query = Array.isArray(requestBody) ? requestBody[0] : requestBody;

        // Update pagination
        if (query.variables) {
          query.variables.pageNumber = pageNum;
          query.variables.pageSize = 20;
          // Remove any filters to get all candidates
          if (query.variables.filters) {
            // Keep only the jobId filter, remove screening/location filters
            const jobFilter = query.variables.filters;
            // Just clear all filters to get ALL candidates
            delete query.variables.filters;
          }
          if (query.variables.statusFolder === undefined) {
            // Don't filter by status - get all
          }
        }

        const result = await page.evaluate(async (payload) => {
          const response = await fetch('https://ph.employer.seek.com/graphql', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: JSON.stringify(payload),
          });
          return response.json();
        }, Array.isArray(requestBody) ? requestBody : query);

        const apps = Array.isArray(result)
          ? result[0]?.data?.applications
          : result?.data?.applications;

        if (!apps?.result?.length) {
          console.log(`  No more results on page ${pageNum}`);
          break;
        }

        console.log(`  Got ${apps.result.length} candidates (total so far: ${allCandidates.length + apps.result.length})`);
        allCandidates.push(...apps.result);

        const pageInfo = apps.pageInfo;
        console.log(`  Page info: ${JSON.stringify(pageInfo)}`);

        if (pageNum >= (pageInfo?.totalPages || 1)) {
          console.log('  Reached last page');
          break;
        }

        await page.waitForTimeout(1000); // Rate limit
      }

      console.log(`\nTotal candidates fetched: ${allCandidates.length}`);

      // Save all candidate data
      writeFileSync(
        join(BASE_DIR, 'head-of-finance-and-accounting-controller', 'all_candidates.json'),
        JSON.stringify(allCandidates, null, 2)
      );
      console.log('Saved all_candidates.json');

      // Print summary
      for (const c of allCandidates.slice(0, 10)) {
        console.log(`  ${c.firstName} ${c.lastName} | ${c.email} | ${c.mostRecentJobTitle} at ${c.mostRecentCompanyName}`);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
