import { chromium } from 'playwright';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu'],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  try {
    // Login
    console.log('=== Logging in ===');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    const emailField = page.locator('input[id="emailAddress"]');
    if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
      await emailField.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();
      await page.waitForTimeout(8000);
    }
    console.log('URL:', page.url());

    // Find candidate links
    console.log('\n=== Looking for candidate/applicant links ===');
    const allLinks = await page.locator('a').all();
    for (const link of allLinks) {
      const href = await link.getAttribute('href').catch(() => '');
      const text = await link.textContent().catch(() => '');
      if (href && (href.includes('candidates') || href.includes('applicant') || href.includes('manage'))) {
        console.log(`Link: "${text.trim().substring(0, 80)}" -> ${href}`);
      }
    }

    // Also find "Find candidates" buttons
    const findBtns = await page.locator('a:has-text("Find candidates"), button:has-text("Find candidates")').all();
    console.log('\n"Find candidates" elements:', findBtns.length);
    for (const btn of findBtns) {
      const href = await btn.getAttribute('href').catch(() => 'no href');
      const text = await btn.textContent().catch(() => '');
      console.log(`  "${text.trim()}" -> ${href}`);
    }

    // Look for candidate count links (the numbers like "210", "64")
    const numLinks = await page.locator('a:has-text("210"), a:has-text("44 New"), a:has-text("64"), a:has-text("20 New")').all();
    console.log('\nCandidate count links:', numLinks.length);
    for (const link of numLinks) {
      const href = await link.getAttribute('href').catch(() => 'no href');
      const text = await link.textContent().catch(() => '');
      console.log(`  "${text.trim().substring(0, 40)}" -> ${href}`);
    }

    // Screenshot the jobs page
    await page.screenshot({ path: 'scratchpad/qa/seek_jobs_page.png', fullPage: false });

    // Try to find the job IDs from the page
    const content = await page.content();
    // Look for patterns like /jobs/12345 or jobId or data-job-id
    const jobPaths = [...new Set(content.match(/\/jobs\/[a-zA-Z0-9-]+/g) || [])];
    console.log('\nJob paths in page:', jobPaths.slice(0, 20));

    // Try to navigate to candidates for the first relevant job
    // Click on the candidate count for "Head of Finance"
    console.log('\n=== Trying to access Head of Finance candidates ===');

    // Find the row/card for Head of Finance
    const hofc = page.locator('text=Head of Finance and Accounting');
    if (await hofc.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Get the parent container
      const parent = hofc.locator('xpath=ancestor::article | ancestor::tr | ancestor::li | ancestor::div[contains(@class,"job")]').first();

      // Within this parent, find clickable candidate links
      const parentLinks = await parent.locator('a').all();
      console.log('Links in Head of Finance row:', parentLinks.length);
      for (const link of parentLinks) {
        const href = await link.getAttribute('href').catch(() => '');
        const text = await link.textContent().catch(() => '');
        console.log(`  "${text.trim().substring(0, 50)}" -> ${href}`);
      }
    }

    // Try direct URL pattern: /jobs/{id}/candidates
    // First extract job IDs
    for (const path of jobPaths) {
      if (path.includes('edit') || path.includes('copy') || path.includes('create')) continue;
      const candidateUrl = `https://ph.employer.seek.com${path}/candidates`;
      console.log(`\nTrying: ${candidateUrl}`);
      await page.goto(candidateUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(3000);

      const title = await page.title();
      const url = page.url();
      console.log(`Result: ${url} (title: ${title})`);

      if (!url.includes('error') && !url.includes('404')) {
        await page.screenshot({ path: 'scratchpad/qa/seek_candidates_recon.png', fullPage: false });

        // Check page content
        const bodyText = await page.locator('body').textContent();
        if (bodyText.includes('Head of Finance') || bodyText.includes('Accounting Manager') || bodyText.includes('candidate') || bodyText.includes('applicant')) {
          console.log('SUCCESS - Found candidate page!');
          console.log('Page text (first 3000 chars):');
          console.log(bodyText.substring(0, 3000));
          break;
        }
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_recon_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
