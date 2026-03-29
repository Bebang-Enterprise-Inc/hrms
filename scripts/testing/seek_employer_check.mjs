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
    // Step 1: Go to jobs page — it should redirect to login
    console.log('=== Step 1: Navigate to SEEK employer portal ===');
    await page.goto('https://ph.employer.seek.com/jobs', { waitUntil: 'networkidle', timeout: 30000 });
    await page.screenshot({ path: 'scratchpad/qa/seek_step1_landing.png', fullPage: false });
    console.log('Current URL:', page.url());
    console.log('Title:', await page.title());

    // Step 2: Check if we need to login
    console.log('\n=== Step 2: Check page state ===');
    const pageText = await page.textContent('body');
    const hasLogin = page.url().includes('login') || page.url().includes('auth') || page.url().includes('sign');
    console.log('Needs login:', hasLogin);

    // List all input fields
    const inputs = await page.locator('input').all();
    console.log('Input fields found:', inputs.length);
    for (const input of inputs) {
      const type = await input.getAttribute('type');
      const name = await input.getAttribute('name');
      const id = await input.getAttribute('id');
      const placeholder = await input.getAttribute('placeholder');
      console.log(`  Input: type=${type}, name=${name}, id=${id}, placeholder=${placeholder}`);
    }

    // List all buttons
    const buttons = await page.locator('button, a[role="button"], input[type="submit"]').all();
    console.log('Buttons found:', buttons.length);
    for (const btn of buttons.slice(0, 10)) {
      const text = await btn.textContent().catch(() => '');
      const ariaLabel = await btn.getAttribute('aria-label');
      console.log(`  Button: "${text.trim().substring(0, 60)}" aria-label="${ariaLabel}"`);
    }

    // Try to find email field
    const emailField = page.locator('input[type="email"], input[name="email"], input[id="email"], input[autocomplete="email"], input[placeholder*="mail"], input[placeholder*="Email"]').first();
    if (await emailField.isVisible({ timeout: 3000 }).catch(() => false)) {
      console.log('\n=== Step 3: Found email field, attempting login ===');
      await emailField.fill(EMAIL);
      await page.screenshot({ path: 'scratchpad/qa/seek_step2_email_filled.png' });

      // Look for password field
      const passField = page.locator('input[type="password"]').first();
      if (await passField.isVisible({ timeout: 3000 }).catch(() => false)) {
        await passField.fill(PASSWORD);
      }

      // Look for submit/next button
      const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Next"), button:has-text("Continue")').first();
      if (await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('Clicking submit button...');
        await submitBtn.click();
        await page.waitForTimeout(5000);
        await page.waitForLoadState('networkidle').catch(() => {});
        await page.screenshot({ path: 'scratchpad/qa/seek_step3_after_submit.png' });
        console.log('After submit URL:', page.url());

        // Check if password field appeared (2-step login)
        const passField2 = page.locator('input[type="password"]').first();
        if (await passField2.isVisible({ timeout: 3000 }).catch(() => false)) {
          console.log('Two-step login detected, filling password...');
          await passField2.fill(PASSWORD);
          const submitBtn2 = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Continue")').first();
          if (await submitBtn2.isVisible({ timeout: 3000 }).catch(() => false)) {
            await submitBtn2.click();
            await page.waitForTimeout(5000);
            await page.waitForLoadState('networkidle').catch(() => {});
          }
        }
      }
    } else {
      console.log('No email field visible, checking for other login flows...');
      // Maybe it's a different login page structure
      await page.screenshot({ path: 'scratchpad/qa/seek_step2_no_email.png', fullPage: true });

      // Check for links to login
      const loginLinks = await page.locator('a:has-text("Sign in"), a:has-text("Log in"), a:has-text("Login")').all();
      console.log('Login links found:', loginLinks.length);
      for (const link of loginLinks) {
        const href = await link.getAttribute('href');
        const text = await link.textContent();
        console.log(`  Link: "${text.trim()}" -> ${href}`);
      }
    }

    // Step 4: Check if we're logged in and on jobs page
    console.log('\n=== Step 4: Check final state ===');
    console.log('Final URL:', page.url());
    await page.screenshot({ path: 'scratchpad/qa/seek_step4_final.png', fullPage: true });

    // If we're on the jobs page, scrape job data
    if (page.url().includes('/jobs') || page.url().includes('employer')) {
      console.log('\n=== Step 5: Scraping job listings ===');

      // Get all visible text that looks like job data
      const bodyText = await page.textContent('body');

      // Look for job cards or listings
      const jobCards = await page.locator('[data-testid*="job"], [class*="job-card"], [class*="JobCard"], article, [role="listitem"]').all();
      console.log('Job card elements found:', jobCards.length);

      for (const card of jobCards.slice(0, 10)) {
        const cardText = await card.textContent();
        if (cardText.length > 20) {
          console.log('\n--- Job Card ---');
          console.log(cardText.trim().substring(0, 300));
        }
      }

      // Also try to get structured data from table-like structures
      const rows = await page.locator('tr, [role="row"]').all();
      console.log('\nTable rows found:', rows.length);

      // Get all headings
      const headings = await page.locator('h1, h2, h3, h4').all();
      for (const h of headings.slice(0, 10)) {
        const text = await h.textContent();
        console.log('Heading:', text.trim().substring(0, 100));
      }

      // Extract stats if visible
      const statsText = bodyText.match(/(\d+)\s*(new|applicant|candidate|view)/gi);
      if (statsText) {
        console.log('\nStats found:', statsText);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
