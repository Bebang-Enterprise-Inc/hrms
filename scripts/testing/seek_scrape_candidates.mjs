import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

const EMAIL = 'sam@bebang.ph';
const PASSWORD = 'YhPpE4HnaR@adp#L';

const JOBS = [
  {
    id: '91094834',
    name: 'Head of Finance and Accounting (Controller)',
    folder: 'head-of-finance-and-accounting-controller',
  },
  {
    id: '91090632',
    name: 'Accounting Manager',
    folder: 'accounting-manager',
  },
];

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
  console.log('Logged in. URL:', page.url());
}

async function collectCandidateIds(page, jobId) {
  console.log(`\n=== Collecting candidate IDs for job ${jobId} ===`);
  await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${jobId}`, {
    waitUntil: 'domcontentloaded', timeout: 30000
  });
  await page.waitForTimeout(5000);

  // Clear filters to see ALL candidates
  const clearBtn = page.locator('button:has-text("Clear all")').first();
  if (await clearBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await clearBtn.click();
    await page.waitForTimeout(3000);
  }

  const candidateIds = new Set();
  let pageNum = 0;
  const MAX_PAGES = 30; // safety limit

  while (pageNum < MAX_PAGES) {
    pageNum++;
    console.log(`  Page ${pageNum}...`);
    await page.waitForTimeout(2000);

    // Extract candidate IDs from the page content/links
    // Candidate names are clickable and set &selected=CANDIDATEID in URL
    const content = await page.content();

    // Find all candidate IDs from data attributes or links
    // Pattern: selected=DIGITS
    const idMatches = content.match(/selected[=:][\s"']*(\d{5,})/g) || [];
    for (const match of idMatches) {
      const id = match.match(/(\d{5,})/)?.[0];
      if (id) candidateIds.add(id);
    }

    // Also try to find candidate IDs from data-candidate-id or similar attributes
    const dataIdMatches = content.match(/candidate[_-]?id[=:"'\s]+(\d{5,})/gi) || [];
    for (const match of dataIdMatches) {
      const id = match.match(/(\d{5,})/)?.[0];
      if (id) candidateIds.add(id);
    }

    // Also find IDs from onclick handlers or data attributes
    const prospectMatches = content.match(/prospect[_-]?id[=:"'\s]+(\d{5,})/gi) || [];
    for (const match of prospectMatches) {
      const id = match.match(/(\d{5,})/)?.[0];
      if (id) candidateIds.add(id);
    }

    // Click on each visible candidate to capture their ID from URL
    // This is more reliable — click each candidate in the list
    const candidateCards = await page.locator('[data-testid*="prospect"], [data-testid*="candidate"]').all();
    if (candidateCards.length === 0) {
      // Alternative: find candidate name elements in the list
      // They appear as uppercase text that's clickable
      // Let me try getting all <a> tags that when clicked set selected= param
      // These are in the left panel list
    }

    console.log(`  IDs collected so far: ${candidateIds.size}`);

    // Check for Next button and click it
    const nextBtn = page.locator('button:has-text("Next"), a:has-text("Next")').last();
    if (await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      const isDisabled = await nextBtn.getAttribute('disabled').catch(() => null);
      if (isDisabled !== null) {
        console.log('  Next button disabled — reached last page');
        break;
      }
      await nextBtn.click();
      await page.waitForTimeout(3000);
    } else {
      console.log('  No Next button found — single page or end');
      break;
    }
  }

  // If we didn't get many IDs from content parsing, try clicking each candidate
  if (candidateIds.size < 5) {
    console.log('  Few IDs from HTML parsing, trying click-based collection...');
    await page.goto(`https://ph.employer.seek.com/candidates/?jobid=${jobId}`, {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    await page.waitForTimeout(5000);

    // Clear filters
    const clearBtn2 = page.locator('button:has-text("Clear all")').first();
    if (await clearBtn2.isVisible({ timeout: 3000 }).catch(() => false)) {
      await clearBtn2.click();
      await page.waitForTimeout(3000);
    }

    let prevSize = 0;
    let staleCount = 0;

    for (let page_i = 0; page_i < MAX_PAGES; page_i++) {
      // Get all clickable items in the candidate list area
      // Find elements that look like candidate names (typically spans/divs with names)
      const listItems = await page.locator('[role="listitem"], article, tr').all();

      for (const item of listItems) {
        try {
          await item.click({ timeout: 2000 });
          await page.waitForTimeout(500);
          const url = page.url();
          const selectedMatch = url.match(/selected=(\d+)/);
          if (selectedMatch) {
            candidateIds.add(selectedMatch[1]);
          }
        } catch {}
      }

      console.log(`  After clicking list items: ${candidateIds.size} IDs`);

      if (candidateIds.size === prevSize) {
        staleCount++;
        if (staleCount >= 2) break;
      } else {
        staleCount = 0;
      }
      prevSize = candidateIds.size;

      // Next page
      const nextBtn2 = page.locator('button:has-text("Next"), a:has-text("Next")').last();
      if (await nextBtn2.isVisible({ timeout: 2000 }).catch(() => false)) {
        const isDisabled = await nextBtn2.getAttribute('disabled').catch(() => null);
        if (isDisabled !== null) break;
        await nextBtn2.click();
        await page.waitForTimeout(3000);
      } else {
        break;
      }
    }
  }

  console.log(`  Total candidate IDs for job ${jobId}: ${candidateIds.size}`);
  return [...candidateIds];
}

async function scrapeCandidateProfile(page, jobId, candidateId) {
  const url = `https://ph.employer.seek.com/candidates/?jobid=${jobId}&selected=${candidateId}&tab=profile`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000);

  const profile = {
    id: candidateId,
    name: '',
    email: '',
    phone: '',
    location: '',
    currentRole: '',
    company: '',
    education: '',
    appliedDate: '',
    fitLevel: '',
    profileText: '',
    resumeText: '',
    coverLetter: '',
    screeningAnswers: '',
  };

  try {
    // Extract profile info from the detail panel
    const panelText = await page.locator('body').textContent();

    // Name - first large text after the selected candidate
    // The panel header typically shows: NAME\nRole at Company
    // Try to get structured data
    const nameEl = page.locator('h1, h2, [data-testid*="name"]').first();
    profile.name = (await nameEl.textContent().catch(() => '')).trim();

    // Get all text from the profile panel
    // The right panel contains all the detail
    profile.profileText = panelText.substring(
      panelText.indexOf(profile.name || 'Profile'),
      Math.min(panelText.length, panelText.indexOf(profile.name || 'Profile') + 5000)
    );

    // Extract email
    const emailMatch = profile.profileText.match(/[\w.+-]+@[\w.-]+\.\w+/);
    if (emailMatch) profile.email = emailMatch[0];

    // Extract phone
    const phoneMatch = profile.profileText.match(/(?:\+63|09)\s*\d[\d\s-]{8,}/);
    if (phoneMatch) profile.phone = phoneMatch[0].trim();

    // Extract location from profile text
    const locationPatterns = ['Metro Manila', 'Taguig', 'Makati', 'Quezon City', 'Pasig', 'Mandaluyong',
      'Paranaque', 'Caloocan', 'Manila City', 'Cavite', 'Laguna', 'Bulacan', 'Rizal', 'Cebu', 'Davao'];
    for (const loc of locationPatterns) {
      if (profile.profileText.includes(loc)) {
        profile.location = loc;
        break;
      }
    }

    // Extract fit level
    if (profile.profileText.includes('High-fit')) profile.fitLevel = 'High-fit';
    else if (profile.profileText.includes('Medium-fit')) profile.fitLevel = 'Medium-fit';
    else if (profile.profileText.includes('Low-fit')) profile.fitLevel = 'Low-fit';

    // Now click Resume tab
    const resumeTab = page.locator('[role="tab"]:has-text("Resum")').first();
    if (await resumeTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await resumeTab.click();
      await page.waitForTimeout(2000);

      // Get resume text from the panel
      const resumePageText = await page.locator('body').textContent();
      // The resume text appears after the tab section
      const resumeStart = resumePageText.lastIndexOf('Resumé');
      if (resumeStart > 0) {
        profile.resumeText = resumePageText.substring(
          resumeStart,
          Math.min(resumePageText.length, resumeStart + 8000)
        );
      }

      // Try to download the actual resume file
      // Look for download link
      const downloadLink = page.locator('a[download], a[href*="resume"][href*="download"], a:has-text("Download resume")').first();
      if (await downloadLink.isVisible({ timeout: 1000 }).catch(() => false)) {
        profile.hasResumeFile = true;
      }
    }
  } catch (err) {
    console.error(`  Error scraping ${candidateId}: ${err.message}`);
  }

  return profile;
}

function sanitizeFilename(name) {
  return name.replace(/[^a-zA-Z0-9\s.-]/g, '').replace(/\s+/g, '_').substring(0, 80);
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

    for (const job of JOBS) {
      const jobDir = join(BASE_DIR, job.folder);
      mkdirSync(jobDir, { recursive: true });
      mkdirSync(join(jobDir, 'profiles'), { recursive: true });

      // Step 1: Collect all candidate IDs
      const candidateIds = await collectCandidateIds(page, job.id);

      // Save the ID list
      writeFileSync(
        join(jobDir, 'candidate_ids.json'),
        JSON.stringify({ jobId: job.id, jobName: job.name, totalCandidates: candidateIds.length, ids: candidateIds }, null, 2)
      );
      console.log(`\nSaved ${candidateIds.length} candidate IDs for ${job.name}`);

      // Step 2: Scrape each candidate profile
      const allProfiles = [];
      for (let i = 0; i < candidateIds.length; i++) {
        const candidateId = candidateIds[i];
        console.log(`  [${i + 1}/${candidateIds.length}] Scraping candidate ${candidateId}...`);

        const profile = await scrapeCandidateProfile(page, job.id, candidateId);
        allProfiles.push(profile);

        // Save individual profile
        const filename = sanitizeFilename(profile.name || candidateId);
        writeFileSync(
          join(jobDir, 'profiles', `${filename}_${candidateId}.json`),
          JSON.stringify(profile, null, 2)
        );

        // Also save a readable text file
        const readableContent = `
# ${profile.name || 'Unknown'}
- **Email:** ${profile.email}
- **Phone:** ${profile.phone}
- **Location:** ${profile.location}
- **Fit Level:** ${profile.fitLevel}
- **Candidate ID:** ${candidateId}

## Profile Summary
${profile.profileText}

## Resume
${profile.resumeText}
`.trim();
        writeFileSync(
          join(jobDir, 'profiles', `${filename}_${candidateId}.md`),
          readableContent
        );

        // Rate limit - don't hammer the server
        if (i % 10 === 9) {
          console.log('    (pausing 5s to avoid rate limiting...)');
          await page.waitForTimeout(5000);
        }
      }

      // Step 3: Save summary CSV
      const csvHeader = 'Candidate ID,Name,Email,Phone,Location,Fit Level,Current Role\n';
      const csvRows = allProfiles.map(p =>
        `"${p.id}","${p.name}","${p.email}","${p.phone}","${p.location}","${p.fitLevel}","${p.currentRole}"`
      ).join('\n');
      writeFileSync(join(jobDir, 'candidates_summary.csv'), csvHeader + csvRows);

      console.log(`\nCompleted ${job.name}: ${allProfiles.length} profiles scraped`);
      console.log(`  Files saved to: ${jobDir}`);
    }

  } catch (err) {
    console.error('Fatal error:', err.message);
    await page.screenshot({ path: 'scratchpad/qa/seek_scrape_error.png', fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
}

main();
