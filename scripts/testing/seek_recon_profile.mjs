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

    // Go to Head of Finance candidates
    await page.goto('https://ph.employer.seek.com/candidates/?jobid=91094834', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    // Find the first candidate name link and click it
    console.log('=== Looking for candidate name links ===');

    // The candidate names appear as clickable text in the list
    // From the page text dump, WILLY GALLEGOS was the first name
    // Let's find clickable elements that look like candidate names
    const allLinks = await page.locator('a[href]').all();
    const candidateProfileLinks = [];
    for (const link of allLinks) {
      const href = await link.getAttribute('href').catch(() => '');
      // SEEK candidate profile URLs typically contain /candidates/ with a candidate ID
      if (href && href.match(/\/candidates\/\d+/) && !href.includes('recommended')) {
        const text = await link.textContent().catch(() => '');
        candidateProfileLinks.push({ text: text.trim(), href });
      }
    }
    console.log('Candidate profile links:', candidateProfileLinks.length);
    for (const l of candidateProfileLinks.slice(0, 5)) {
      console.log(`  "${l.text.substring(0, 60)}" -> ${l.href}`);
    }

    // If no direct profile links, try clicking on a candidate card
    if (candidateProfileLinks.length === 0) {
      console.log('\nNo direct profile links found. Looking for clickable candidate cards...');

      // Try finding the candidate card area and click
      // From the HTML, candidates appear after "35 matching applications"
      const candidateNameEl = page.locator('text=WILLY GALLEGOS').first();
      if (await candidateNameEl.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('Found WILLY GALLEGOS, clicking...');
        await candidateNameEl.click();
        await page.waitForTimeout(5000);
        console.log('URL after click:', page.url());
        await page.screenshot({ path: 'scratchpad/qa/seek_candidate_detail.png', fullPage: false });

        // Explore the profile/detail page
        console.log('\n=== Candidate detail page ===');
        const bodyText = await page.locator('body').textContent();
        console.log('Page text (first 4000 chars):');
        console.log(bodyText.substring(0, 4000));

        // Look for resume/CV download
        const downloadEls = await page.locator('a[download], a[href*="resume"], a[href*="document"], a[href*=".pdf"], button:has-text("resume"), button:has-text("download"), button:has-text("CV"), a:has-text("Resume"), a:has-text("Cover letter"), a:has-text("Download")').all();
        console.log('\nDownload elements:', downloadEls.length);
        for (const el of downloadEls) {
          const tag = await el.evaluate(e => e.tagName);
          const text = await el.textContent().catch(() => '');
          const href = await el.getAttribute('href').catch(() => '');
          console.log(`  <${tag}> "${text.trim().substring(0, 60)}" -> ${href}`);
        }

        // Check for cover letter section
        const coverLetterSection = page.locator('text=Cover letter, text=cover letter').first();
        if (await coverLetterSection.isVisible({ timeout: 2000 }).catch(() => false)) {
          console.log('\nCover letter section found!');
        }

        // Look for tabs (Application, Profile, Resume, etc.)
        const tabs = await page.locator('[role="tab"], button[data-testid*="tab"]').all();
        console.log('\nTabs:', tabs.length);
        for (const tab of tabs) {
          console.log(`  Tab: "${(await tab.textContent()).trim()}"`);
        }

        // Scroll down to see more content
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(2000);
        await page.screenshot({ path: 'scratchpad/qa/seek_candidate_detail_scrolled.png', fullPage: true });
      }
    } else {
      // Click the first profile link
      const first = candidateProfileLinks[0];
      console.log(`\nNavigating to: ${first.href}`);
      await page.goto(`https://ph.employer.seek.com${first.href}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(5000);
      await page.screenshot({ path: 'scratchpad/qa/seek_candidate_detail.png', fullPage: false });

      const bodyText = await page.locator('body').textContent();
      console.log('Profile page text (first 4000 chars):');
      console.log(bodyText.substring(0, 4000));
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_recon_profile_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
