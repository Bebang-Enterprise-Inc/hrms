import { chromium } from 'playwright';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';

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
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  try {
    await login(page);
    console.log('Logged in. URL:', page.url());

    // Navigate to Head of Finance candidates
    console.log('\n=== Navigating to Head of Finance candidates ===');
    await page.goto('https://ph.employer.seek.com/candidates/?jobid=91094834', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);
    console.log('URL:', page.url());
    await page.screenshot({ path: 'scratchpad/qa/seek_hofc_candidates.png', fullPage: false });

    // Explore page structure
    const headings = await page.locator('h1, h2, h3').all();
    for (const h of headings.slice(0, 10)) {
      console.log('Heading:', (await h.textContent()).trim().substring(0, 100));
    }

    // Look for candidate list items
    console.log('\n=== Candidate list structure ===');

    // Try various selectors for candidate cards
    const selectors = [
      'article',
      '[data-testid*="candidate"]',
      '[data-testid*="applicant"]',
      '[role="listitem"]',
      'li[class*="candidate"]',
      'div[class*="candidate"]',
      'tr[class*="candidate"]',
    ];

    for (const sel of selectors) {
      const count = await page.locator(sel).count();
      if (count > 0) {
        console.log(`Selector "${sel}": ${count} elements`);
        // Get first one's text
        const first = await page.locator(sel).first().textContent().catch(() => '');
        console.log(`  First text: "${first.trim().substring(0, 200)}"`);
      }
    }

    // Look for links to individual candidate profiles
    console.log('\n=== Candidate profile links ===');
    const profileLinks = await page.locator('a[href*="profile"], a[href*="candidate/"], a[href*="applicant/"]').all();
    console.log('Profile links found:', profileLinks.length);
    for (const link of profileLinks.slice(0, 10)) {
      const href = await link.getAttribute('href').catch(() => '');
      const text = await link.textContent().catch(() => '');
      console.log(`  "${text.trim().substring(0, 60)}" -> ${href}`);
    }

    // Check for names - candidate names are usually prominent
    const nameElements = await page.locator('h2 a, h3 a, h4 a, [data-testid*="name"] a').all();
    console.log('\nName elements:', nameElements.length);
    for (const el of nameElements.slice(0, 10)) {
      const text = await el.textContent().catch(() => '');
      const href = await el.getAttribute('href').catch(() => '');
      console.log(`  "${text.trim()}" -> ${href}`);
    }

    // Look for resume/download buttons
    const resumeEls = await page.locator('a[href*="resume"], a[href*="download"], button:has-text("Resume"), button:has-text("Download"), a:has-text("Resume"), a:has-text("Cover letter")').all();
    console.log('\nResume/download elements:', resumeEls.length);
    for (const el of resumeEls.slice(0, 10)) {
      const tag = await el.evaluate(e => e.tagName);
      const text = await el.textContent().catch(() => '');
      const href = await el.getAttribute('href').catch(() => '');
      console.log(`  <${tag}> "${text.trim().substring(0, 60)}" -> ${href}`);
    }

    // Dump visible text from the main area
    console.log('\n=== Page text (first 5000 chars) ===');
    const bodyText = await page.locator('body').textContent();
    console.log(bodyText.substring(0, 5000));

    // Also check for pagination
    console.log('\n=== Pagination ===');
    const pagination = await page.locator('nav[aria-label*="page"], [data-testid*="pagination"], a:has-text("Next"), button:has-text("Next"), a:has-text("Show more"), button:has-text("Show more")').all();
    console.log('Pagination elements:', pagination.length);
    for (const el of pagination) {
      const text = await el.textContent().catch(() => '');
      console.log(`  "${text.trim().substring(0, 60)}"`);
    }

    // Now try clicking on a single candidate to see the profile page
    console.log('\n=== Exploring first candidate profile ===');
    const firstCandLink = page.locator('a[href*="profile"], a[href*="candidate/"]').first();
    if (await firstCandLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await firstCandLink.getAttribute('href');
      console.log('Clicking first candidate:', href);
      await firstCandLink.click();
      await page.waitForTimeout(5000);
      console.log('Profile URL:', page.url());
      await page.screenshot({ path: 'scratchpad/qa/seek_candidate_profile.png', fullPage: false });

      // Check for resume download on profile
      const dlLinks = await page.locator('a[href*="resume"], a[href*="download"], a[download], button:has-text("Download")').all();
      console.log('Download elements on profile:', dlLinks.length);
      for (const dl of dlLinks) {
        const text = await dl.textContent().catch(() => '');
        const href = await dl.getAttribute('href').catch(() => '');
        console.log(`  "${text.trim()}" -> ${href}`);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_recon_list_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
