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

  try {
    await login(page);
    console.log('Logged in.');

    // Go to candidate list
    await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}`, {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    await page.waitForTimeout(5000);

    // Step 1: Collect candidate IDs by clicking each one in the list
    console.log('\n=== Collecting candidate IDs ===');

    // The list shows candidates as rows/cards. Let me find them.
    // Looking at the content, candidates are in the main listing area.
    // Each candidate when clicked changes the URL to include &selected=XXXXXXXXXX

    // First, let's find all elements that could be candidate entries
    // They seem to be in a list/table on the left side
    const content = await page.content();

    // Extract all prospect/candidate IDs from the HTML
    // SEEK uses prospectId in their React state
    const allIds = new Set();

    // Method 1: From data attributes
    const prospectMatches = content.match(/prospectId[=:"'\s]+(\d{5,})/gi) || [];
    for (const m of prospectMatches) {
      const id = m.match(/(\d{5,})/)?.[0];
      if (id) allIds.add(id);
    }

    // Method 2: From URL patterns in links
    const selectedMatches = content.match(/selected=(\d{5,})/g) || [];
    for (const m of selectedMatches) {
      const id = m.match(/(\d{5,})/)?.[0];
      if (id) allIds.add(id);
    }

    // Method 3: From JSON data embedded in the page
    const jsonIdMatches = content.match(/"id"\s*:\s*(\d{8,})/g) || [];
    for (const m of jsonIdMatches) {
      const id = m.match(/(\d{8,})/)?.[0];
      if (id && id.length >= 9 && id.length <= 12) allIds.add(id);
    }

    console.log(`Found ${allIds.size} candidate IDs from HTML parsing`);
    const candidateIds = [...allIds].slice(0, 3); // Just test with 3
    console.log('Test candidates:', candidateIds);

    if (candidateIds.length === 0) {
      // Fallback: click first 3 candidates in the list
      console.log('Fallback: clicking candidates to get IDs...');

      // Click on the first visible candidate name
      // From recon, "WILLY GALLEGOS" was first. Let's find candidate name elements.
      // They are uppercase links/spans in the left panel
      const leftPanel = await page.locator('body').textContent();

      // Find uppercase name patterns that appear in the candidate list
      // After "matching applications" text
      const afterApps = leftPanel.substring(leftPanel.indexOf('matching application') || 0);
      const nameRegex = /[A-Z][A-Z]+\s+[A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)*/g;
      const foundNames = [];
      let match;
      while ((match = nameRegex.exec(afterApps)) !== null) {
        const name = match[0];
        // Filter out non-name patterns
        if (name.length > 5 && name.length < 40 &&
            !['HIGH SCHOOL', 'NATIONAL CERTIFICATE', 'BACHELOR DEGREE', 'MASTER DEGREE',
              'POST GRADUATE', 'DOCTORAL DEGREE', 'NOT SUITABLE', 'METRO MANILA',
              'CLEAR ALL', 'SCREENING QUESTIONS', 'APPLY MUST', 'SORT FILTER',
              'FIND CANDIDATES', 'CREATE JOB', 'COMPANY PROFILE', 'TALENT SEARCH',
              'SEEK EMPLOYER', 'CANDIDATE MATCHES', 'JOB ADS', 'HIRING ADVICE',
              'MARKET INSIGHTS', 'ACCOUNT SETTINGS', 'SIGN OUT', 'NOTES AND',
              'INVOICE HISTORY', 'YOUR TEAM', 'PAYABLE INVOICES', 'LOGOS AND',
              'PRICE LOOKUP', 'CONTACT US', 'HIDE FILTERS'
            ].some(skip => name.includes(skip))) {
          foundNames.push(name);
        }
      }

      console.log('Candidate names found:', foundNames.slice(0, 10));

      // Click each name and capture the URL
      for (const name of foundNames.slice(0, 3)) {
        try {
          const nameEl = page.locator(`text="${name}"`).first();
          if (await nameEl.isVisible({ timeout: 2000 }).catch(() => false)) {
            await nameEl.click();
            await page.waitForTimeout(2000);
            const url = page.url();
            const selMatch = url.match(/selected=(\d+)/);
            if (selMatch) {
              candidateIds.push(selMatch[1]);
              console.log(`  ${name} -> ID ${selMatch[1]}`);
            }
          }
        } catch {}
      }
    }

    // Step 2: Scrape 3 candidates
    const jobDir = join(BASE_DIR, JOB_FOLDER);
    mkdirSync(join(jobDir, 'profiles'), { recursive: true });

    for (let i = 0; i < Math.min(candidateIds.length, 3); i++) {
      const cid = candidateIds[i];
      console.log(`\n=== [${i+1}/3] Scraping candidate ${cid} ===`);

      // Navigate to profile tab
      await page.goto(
        `https://ph.employer.seek.com/candidates/?jobid=${JOB_ID}&selected=${cid}&tab=profile`,
        { waitUntil: 'domcontentloaded', timeout: 20000 }
      );
      await page.waitForTimeout(3000);

      // Capture profile panel text
      const bodyText = await page.locator('body').textContent();

      // Extract name from heading
      const headings = await page.locator('h1, h2').all();
      let name = '';
      for (const h of headings) {
        const text = (await h.textContent().catch(() => '')).trim();
        if (text.length > 3 && text.length < 60 && !text.includes('Head of Finance') && !text.includes('Live') && !text.includes('job ad')) {
          name = text;
          break;
        }
      }
      console.log(`  Name: ${name}`);

      // Extract structured data
      const emailMatch = bodyText.match(/[\w.+-]+@[\w.-]+\.\w{2,}/);
      const phoneMatch = bodyText.match(/(?:\+63|09)\d[\d\s-]{7,}/);
      console.log(`  Email: ${emailMatch?.[0] || 'not found'}`);
      console.log(`  Phone: ${phoneMatch?.[0]?.trim() || 'not found'}`);

      // Get the profile section text
      // It starts after the candidate name and before the footer
      const profileStart = bodyText.indexOf(name);
      const profileSection = bodyText.substring(profileStart, profileStart + 4000);

      // Click Resume tab
      await page.waitForTimeout(1000);
      const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
      let resumeText = '';
      if (await resumeTab.isVisible({ timeout: 2000 }).catch(() => false)) {
        await resumeTab.click();
        await page.waitForTimeout(2000);

        const resumeBody = await page.locator('body').textContent();
        // The resume content is rendered inline after the tabs
        // Find the resume section
        const resumeIdx = resumeBody.lastIndexOf('Resumé');
        if (resumeIdx > 0) {
          // Get text from after the last "Resumé" heading (which is the content area)
          // But we need to skip nav/tab text. The actual resume content starts further in.
          resumeText = resumeBody.substring(resumeIdx + 10, resumeIdx + 8000);
        }
        console.log(`  Resume text: ${resumeText.length} chars`);
      }

      // Save
      const safeName = sanitize(name || `candidate_${cid}`);
      const mdContent = `# ${name}
- **Candidate ID:** ${cid}
- **Email:** ${emailMatch?.[0] || ''}
- **Phone:** ${phoneMatch?.[0]?.trim() || ''}

## Profile
${profileSection}

## Resume
${resumeText}
`;
      writeFileSync(join(jobDir, 'profiles', `${safeName}.md`), mdContent);
      writeFileSync(join(jobDir, 'profiles', `${safeName}.json`), JSON.stringify({
        id: cid, name, email: emailMatch?.[0] || '', phone: phoneMatch?.[0]?.trim() || '',
        profileText: profileSection, resumeText
      }, null, 2));

      console.log(`  Saved: ${safeName}.md`);

      // Screenshot for verification
      await page.screenshot({ path: `scratchpad/qa/seek_test_${i+1}.png` });
    }

    console.log('\n=== TEST COMPLETE ===');
    console.log(`Files saved to: ${join(BASE_DIR, JOB_FOLDER, 'profiles')}`);

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_test_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
