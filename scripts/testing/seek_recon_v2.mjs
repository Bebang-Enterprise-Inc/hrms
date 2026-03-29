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
    // Login - go to jobs page
    console.log('=== Step 1: Navigate ===');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);
    console.log('URL after initial nav:', page.url());

    // Check if on login page
    const emailField = page.locator('input[id="emailAddress"]');
    if (await emailField.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('=== Step 2: Login ===');
      await emailField.fill(EMAIL);
      await page.locator('input[id="password"]').fill(PASSWORD);
      await page.locator('button:has-text("Sign in")').first().click();

      // Wait for redirect to complete - may go through OAuth
      console.log('Waiting for login redirect...');
      await page.waitForTimeout(10000);
      console.log('URL after login wait:', page.url());

      // If we're on an OAuth page, wait more
      if (page.url().includes('oauth') || page.url().includes('integrate')) {
        console.log('On OAuth redirect page, waiting longer...');
        await page.waitForTimeout(10000);
        console.log('URL after second wait:', page.url());
      }

      // If still not on jobs page, try navigating directly
      if (!page.url().includes('/jobs')) {
        console.log('Navigating directly to /jobs...');
        await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'domcontentloaded', timeout: 15000 });
        await page.waitForTimeout(5000);
        console.log('URL after direct nav:', page.url());
      }
    }

    await page.screenshot({ path: 'scratchpad/qa/seek_v2_step2.png', fullPage: false });

    // Now we should be on the jobs page
    console.log('\n=== Step 3: Explore jobs page ===');
    console.log('Final URL:', page.url());

    // Get all links with hrefs
    const links = await page.locator('a[href]').all();
    console.log('Total links on page:', links.length);

    // Categorize interesting links
    const categories = {};
    for (const link of links) {
      const href = await link.getAttribute('href').catch(() => '');
      const text = (await link.textContent().catch(() => '')).trim().substring(0, 80);
      if (!href) continue;

      // Skip generic/nav links
      if (href === '#' || href === '/' || href.length < 5) continue;

      // Categorize
      if (href.includes('candidates') || href.includes('applicant')) {
        categories['candidates'] = categories['candidates'] || [];
        categories['candidates'].push({ text, href });
      } else if (href.includes('manage-applications')) {
        categories['manage-applications'] = categories['manage-applications'] || [];
        categories['manage-applications'].push({ text, href });
      } else if (href.match(/\/jobs\/\d+/) || href.match(/\/job\//)) {
        categories['job-detail'] = categories['job-detail'] || [];
        categories['job-detail'].push({ text, href });
      } else if (href.includes('search') || href.includes('talent')) {
        categories['talent-search'] = categories['talent-search'] || [];
        categories['talent-search'].push({ text, href });
      }
    }

    for (const [cat, items] of Object.entries(categories)) {
      console.log(`\n--- ${cat} (${items.length} links) ---`);
      for (const item of items.slice(0, 15)) {
        console.log(`  "${item.text}" -> ${item.href}`);
      }
    }

    // Also dump the HTML of the first job card to understand the structure
    console.log('\n=== Step 4: Job card HTML ===');
    const firstArticle = page.locator('article, [role="listitem"], [data-testid*="job"]').first();
    if (await firstArticle.isVisible({ timeout: 3000 }).catch(() => false)) {
      const html = await firstArticle.innerHTML();
      console.log('First job card HTML (first 2000 chars):');
      console.log(html.substring(0, 2000));
    } else {
      // Try finding the job listing area
      const mainContent = await page.locator('main, [role="main"]').first().innerHTML().catch(() => '');
      console.log('Main content HTML (first 3000 chars):');
      console.log(mainContent.substring(0, 3000));
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_v2_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
