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
    acceptDownloads: true,
  });
  const page = await context.newPage();

  try {
    await login(page);

    // Go to Head of Finance candidates, clear the filters to see all 210
    console.log('=== Navigate to candidate list ===');
    await page.goto('https://ph.employer.seek.com/candidates/?jobid=91094834', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    // Click on first candidate (WILLY GALLEGOS)
    const firstCandidate = page.locator('text=WILLY GALLEGOS').first();
    await firstCandidate.click();
    await page.waitForTimeout(3000);

    // Now click the Resumé tab
    console.log('=== Clicking Resumé tab ===');
    const resumeTab = page.locator('[role="tab"]:has-text("Resum"), button:has-text("Resum")').first();
    if (await resumeTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await resumeTab.click();
      await page.waitForTimeout(3000);
      console.log('URL after Resume tab:', page.url());
      await page.screenshot({ path: 'scratchpad/qa/seek_resume_tab.png', fullPage: false });

      // Look for download link/button
      const bodyText = await page.locator('body').textContent();
      // Search for download-related text
      const downloadMatches = bodyText.match(/(download|resume|\.pdf|\.doc|attach|view)/gi);
      console.log('Download-related text found:', downloadMatches?.slice(0, 20));

      // Look for all buttons and links in the detail panel area
      const panelLinks = await page.locator('a[href*="download"], a[href*="resume"], a[href*="document"], a[href*=".pdf"], a[download], button:has-text("Download"), button:has-text("View"), a:has-text("Download")').all();
      console.log('Download elements:', panelLinks.length);
      for (const el of panelLinks) {
        const tag = await el.evaluate(e => e.tagName);
        const text = await el.textContent().catch(() => '');
        const href = await el.getAttribute('href').catch(() => '');
        console.log(`  <${tag}> "${text.trim().substring(0, 80)}" -> ${href}`);
      }

      // Check for iframe (PDF viewer)
      const iframes = await page.locator('iframe').all();
      console.log('Iframes:', iframes.length);
      for (const iframe of iframes) {
        const src = await iframe.getAttribute('src').catch(() => '');
        console.log(`  iframe src: ${src?.substring(0, 200)}`);
      }

      // Check for object/embed (PDF viewer)
      const objects = await page.locator('object, embed').all();
      console.log('Object/embed:', objects.length);

      // Dump the resume tab content area
      console.log('\n=== Resume tab text ===');
      // Get text near the resume area (after clicking tab, the panel content changes)
      const panelText = bodyText.substring(bodyText.indexOf('Resum'));
      console.log(panelText?.substring(0, 3000));
    }

    // Also check Profile tab content to understand what data we can extract
    console.log('\n\n=== Checking Profile tab content ===');
    const profileTab = page.locator('[role="tab"]:has-text("Profile")').first();
    await profileTab.click();
    await page.waitForTimeout(2000);

    // Get the detail panel content - focus on right side panel
    // The panel shows career history, education, screening questions
    const rightPanel = page.locator('[class*="panel"], [class*="detail"], [class*="drawer"], aside, [role="dialog"]').first();
    if (await rightPanel.isVisible({ timeout: 2000 }).catch(() => false)) {
      const panelText = await rightPanel.textContent();
      console.log('Profile panel text (first 3000 chars):');
      console.log(panelText.substring(0, 3000));
    }

    // Now let's also check: how do we get ALL candidates (not just filtered 35)?
    // We need to clear filters
    console.log('\n\n=== Checking how to clear filters ===');
    const clearFilters = page.locator('button:has-text("Clear all"), a:has-text("Clear all"), button:has-text("Clear"), button:has-text("Show all")').first();
    if (await clearFilters.isVisible({ timeout: 2000 }).catch(() => false)) {
      console.log('Found "Clear all" button, clicking...');
      await clearFilters.click();
      await page.waitForTimeout(3000);

      // Check how many candidates now
      const bodyText2 = await page.locator('body').textContent();
      const matchCount = bodyText2.match(/(\d+)\s*matching\s*application/);
      console.log('After clearing filters:', matchCount?.[0]);
    }

    // Count how many candidate entries are visible in the list
    // Each candidate appears as a card/row in the left panel
    // Let me find the pattern
    console.log('\n=== Counting visible candidates ===');
    // Try to find all candidate name elements
    // From the earlier recon, names appear in uppercase (WILLY GALLEGOS)
    const allTextNodes = await page.locator('body').textContent();
    // Names typically appear in the list as links
    // Let's find all uppercase names pattern
    const namePattern = /[A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})*/g;
    const names = allTextNodes.match(namePattern)?.filter(n =>
      !['SEEK', 'HEAD', 'HIRING', 'DOLE', 'ACCA', 'ICAEW', 'CIMA', 'HIGH', 'NATIONAL', 'POST', 'MASTER', 'NOT', 'NEW'].some(skip => n.includes(skip))
      && n.length > 5
      && n.split(' ').length >= 2
    );
    console.log('Candidate names found:', names?.length);
    console.log('Names:', names?.slice(0, 15));

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_resume_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
