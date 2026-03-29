import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';
const BASE_DIR = 'F:/Dropbox/Projects/BEI-ERP/recruitment';
const JOB_ID = '91094834';
const JOB_FOLDER = 'head-of-finance-and-accounting-controller';

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

function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 60);
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

  // Intercept API responses to find candidate data
  const apiResponses = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('graphql') || url.includes('candidates') || url.includes('prospect') || url.includes('applications')) {
      try {
        const body = await response.json().catch(() => null);
        if (body) {
          apiResponses.push({ url: url.substring(0, 200), body });
        }
      } catch {}
    }
  });

  try {
    await login(page);
    console.log('Logged in.');

    // Go to candidate list
    console.log('\n=== Loading candidate list (intercepting API) ===');
    await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}`, {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    await page.waitForTimeout(8000);

    console.log(`Intercepted ${apiResponses.length} API responses`);
    for (const resp of apiResponses) {
      console.log(`  URL: ${resp.url}`);
      // Check if it contains candidate/prospect data
      const bodyStr = JSON.stringify(resp.body);
      if (bodyStr.includes('prospect') || bodyStr.includes('applicant') || bodyStr.includes('Gallego')) {
        console.log('  >>> Contains candidate data!');
        // Find prospect IDs
        const idMatches = bodyStr.match(/"prospectId"\s*:\s*(\d+)/g) || [];
        console.log(`  Prospect IDs found: ${idMatches.length}`);
        for (const m of idMatches.slice(0, 5)) console.log(`    ${m}`);

        // Save the full API response for analysis
        writeFileSync(
          join(BASE_DIR, JOB_FOLDER, 'api_response.json'),
          JSON.stringify(resp.body, null, 2)
        );
        console.log('  Saved api_response.json');
      }

      // Also check for GraphQL
      if (bodyStr.includes('data') && (bodyStr.includes('edge') || bodyStr.includes('node'))) {
        console.log('  >>> Possible GraphQL response');
        const keys = Object.keys(resp.body?.data || resp.body || {}).slice(0, 5);
        console.log(`  Top keys: ${keys}`);
      }
    }

    // If no API interception worked, try another approach:
    // Click candidates one by one and capture URL
    console.log('\n=== Click-based ID collection ===');
    const candidateIds = [];

    // Scroll through the candidate list and click each entry
    // The candidate entries are in the left side list
    // Let me find them by looking for elements that have specific structure

    // Find all elements with a specific testid or role in the candidate list area
    const listArea = page.locator('main, [role="main"]').first();

    // Get all anchor tags or clickable divs that might be candidates
    // From the earlier recon, clicking "WILLY GALLEGOS" text worked
    // The issue is the names are rendered with doubled first letter (WWILLY)
    // Let's just find all clickable elements in the list and click them

    // Alternative: use keyboard navigation
    // Or find the candidate list items by their structure

    // Let me dump all unique href values to find candidate links
    const allLinks = await page.locator('a[href]').all();
    for (const link of allLinks) {
      const href = await link.getAttribute('href').catch(() => '');
      if (href?.includes('selected=')) {
        const id = href.match(/selected=(\d+)/)?.[1];
        if (id) {
          const text = await link.textContent().catch(() => '');
          candidateIds.push({ id, name: text.trim().substring(0, 60) });
        }
      }
    }

    console.log(`Found ${candidateIds.length} candidate links with 'selected=' param`);

    if (candidateIds.length === 0) {
      // Try: find all text elements that when clicked change the URL
      // Or just use the known ID and find siblings
      console.log('Trying data attribute approach...');

      // Get the page source and look for candidate data
      const source = await page.content();

      // SEEK React apps often embed data in __NEXT_DATA__ or similar
      const nextDataMatch = source.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
      if (nextDataMatch) {
        console.log('Found __NEXT_DATA__');
        const nextData = JSON.parse(nextDataMatch[1]);
        writeFileSync(join(BASE_DIR, JOB_FOLDER, 'next_data.json'), JSON.stringify(nextData, null, 2));
      }

      // Try window.__PRELOADED_STATE__ or similar
      const preloadMatch = source.match(/window\.__\w+__\s*=\s*(\{[\s\S]*?\});?\s*<\/script>/);
      if (preloadMatch) {
        console.log('Found preloaded state');
        writeFileSync(join(BASE_DIR, JOB_FOLDER, 'preloaded_state.json'), preloadMatch[1]);
      }

      // Try getting candidate IDs from data-testid attributes
      const testIdEls = await page.locator('[data-testid]').all();
      const testIds = new Set();
      for (const el of testIdEls) {
        const testId = await el.getAttribute('data-testid').catch(() => '');
        if (testId?.includes('prospect') || testId?.includes('candidate') || testId?.includes('applicant')) {
          testIds.add(testId);
        }
      }
      console.log('Candidate-related data-testid values:', [...testIds]);

      // Last resort: click on the list area and use Tab to navigate
      console.log('\nLast resort: clicking candidate cards by position...');

      // The candidate list is on the left. Each card is about 100px tall.
      // Let me click at specific Y coordinates in the list area
      const listBounds = await listArea.boundingBox().catch(() => null);
      if (listBounds) {
        console.log(`List area bounds: x=${listBounds.x} y=${listBounds.y} w=${listBounds.width} h=${listBounds.height}`);

        // The first candidate card starts around y=300 (after filters)
        // Each card is roughly 80-120px tall
        for (let y = 400; y < 900; y += 100) {
          // Click in the left panel area (x ~ 300 which is middle of left panel)
          await page.mouse.click(300, y);
          await page.waitForTimeout(1000);
          const url = page.url();
          const selMatch = url.match(/selected=(\d+)/);
          if (selMatch && !candidateIds.find(c => c.id === selMatch[1])) {
            candidateIds.push({ id: selMatch[1], name: `candidate_at_y${y}` });
            console.log(`  Clicked y=${y}: ID ${selMatch[1]}`);
          }
        }
      }
    }

    console.log(`\nTotal candidate IDs collected: ${candidateIds.length}`);
    for (const c of candidateIds.slice(0, 10)) {
      console.log(`  ${c.id}: ${c.name}`);
    }

    // Now scrape the first 3
    const jobDir = join(BASE_DIR, JOB_FOLDER);
    mkdirSync(join(jobDir, 'profiles'), { recursive: true });

    const testIds = candidateIds.slice(0, 3).map(c => c.id);
    // Add the known ID if not already there
    if (!testIds.includes('2089088724')) testIds.unshift('2089088724');

    for (let i = 0; i < Math.min(testIds.length, 3); i++) {
      const cid = testIds[i];
      console.log(`\n=== [${i+1}/3] Scraping candidate ${cid} ===`);

      // Profile tab
      await page.goto(
        `https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}&selected=${cid}&tab=profile`,
        { waitUntil: 'domcontentloaded', timeout: 20000 }
      );
      await page.waitForTimeout(4000);

      // Get the right-side detail panel content
      // The detail panel is everything to the right of the candidate list
      const bodyText = await page.locator('body').textContent();

      // Find the candidate's name - it appears after the tab navigation
      // Looking for pattern: NAME\nRole at Company
      // From the screenshot, the name is in a header area of the detail panel
      let name = '';
      const h2s = await page.locator('h2').all();
      for (const h of h2s) {
        const text = (await h.textContent().catch(() => '')).trim();
        // Skip non-name headings
        if (text && text.length > 3 && text.length < 60 &&
            !text.includes('Head of Finance') && !text.includes('Live') &&
            !text.includes('job ad') && !text.includes('matching') &&
            !text.includes('Career') && !text.includes('Education') &&
            !text.includes('Screening') && !text.includes('Application')) {
          // Check if it looks like a name (has at least first+last)
          if (text.split(/\s+/).length >= 2 || text.match(/^[A-Z]/)) {
            name = text;
            break;
          }
        }
      }

      // Also try h3
      if (!name) {
        const h3s = await page.locator('h3').all();
        for (const h of h3s) {
          const text = (await h.textContent().catch(() => '')).trim();
          if (text && text.length > 3 && text.length < 60 && text.split(/\s+/).length >= 2) {
            name = text;
            break;
          }
        }
      }

      console.log(`  Name: "${name}"`);

      // Extract email and phone
      const emailMatch = bodyText.match(/[\w.+-]+@[\w.-]+\.\w{2,}/);
      const phoneMatch = bodyText.match(/(?:\+63|09)\d[\d\s-]{7,}/);
      console.log(`  Email: ${emailMatch?.[0] || 'N/A'}`);
      console.log(`  Phone: ${phoneMatch?.[0]?.trim() || 'N/A'}`);

      // Get profile section - from name to end of detail panel
      let profileText = '';
      const nameIdx = bodyText.indexOf(name);
      if (nameIdx > 0) {
        profileText = bodyText.substring(nameIdx, nameIdx + 5000);
      }

      // Screenshot the profile
      await page.screenshot({ path: `scratchpad/qa/seek_profile_${i+1}.png` });

      // Resume tab
      let resumeText = '';
      const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
      if (await resumeTab.isVisible({ timeout: 2000 }).catch(() => false)) {
        await resumeTab.click();
        await page.waitForTimeout(3000);

        const resumeBody = await page.locator('body').textContent();
        // Find the actual resume content - it's rendered inline
        // The content typically starts after "Notes and attachments" tab text
        const tabsEnd = resumeBody.lastIndexOf('Notes and attachments');
        if (tabsEnd > 0) {
          resumeText = resumeBody.substring(tabsEnd + 25, tabsEnd + 8000);
        } else {
          // Alternative: get text after last "Resumé"
          const rIdx = resumeBody.lastIndexOf('Resumé');
          if (rIdx > 0) resumeText = resumeBody.substring(rIdx + 10, rIdx + 8000);
        }

        // Screenshot resume
        await page.screenshot({ path: `scratchpad/qa/seek_resume_${i+1}.png` });
      }

      console.log(`  Profile: ${profileText.length} chars`);
      console.log(`  Resume: ${resumeText.length} chars`);

      // Save
      const safeName = sanitize(name || `candidate_${cid}`);
      const mdContent = `# ${name || cid}

**Candidate ID:** ${cid}
**Email:** ${emailMatch?.[0] || ''}
**Phone:** ${phoneMatch?.[0]?.trim() || ''}

---

## Profile
${profileText}

---

## Resume
${resumeText}
`;
      writeFileSync(join(jobDir, 'profiles', `${safeName}.md`), mdContent);
      console.log(`  Saved: ${safeName}.md`);
    }

    console.log('\n=== TEST COMPLETE ===');

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: 'scratchpad/qa/seek_test2_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
