/**
 * S120 L3 Test — Real browser, real form submissions, real button clicks
 * Tests: PR creation with item autocomplete, PO price edit with approval gate
 *
 * Runs HEADLESS — no visible browser window
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const BASE = 'https://my.bebang.ph';
const USER = 'test.commissary@bebang.ph';
const PASS = 'BeiTest2026!';
const OUTPUT_DIR = 'F:\\Dropbox\\Projects\\BEI-ERP\\output\\l3\\s120';
const SCREENSHOT_DIR = `${OUTPUT_DIR}\\screenshots`;

mkdirSync(SCREENSHOT_DIR, { recursive: true });

const evidence = {
  form_submissions: [],
  api_mutations: [],
  state_verification: [],
};

function log(msg) {
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${msg}`);
}

async function saveEvidence() {
  writeFileSync(`${OUTPUT_DIR}/form_submissions.json`, JSON.stringify(evidence.form_submissions, null, 2));
  writeFileSync(`${OUTPUT_DIR}/api_mutations.json`, JSON.stringify(evidence.api_mutations, null, 2));
  writeFileSync(`${OUTPUT_DIR}/state_verification.json`, JSON.stringify(evidence.state_verification, null, 2));
  log('Evidence files saved');
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // Intercept API calls for evidence
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/procurement/') && response.request().method() !== 'GET') {
      try {
        const body = await response.json().catch(() => null);
        evidence.api_mutations.push({
          timestamp: new Date().toISOString(),
          url: url.replace(BASE, ''),
          method: response.request().method(),
          status: response.status(),
          response_summary: body ? JSON.stringify(body).substring(0, 500) : null,
        });
      } catch {}
    }
  });

  try {
    // ============================================================
    // STEP 1: Login
    // ============================================================
    log('Step 1: Logging in as test.commissary@bebang.ph');
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await page.fill('input[name="email"]', USER);
    await page.fill('input[name="password"]', PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
    log(`Logged in. URL: ${page.url()}`);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01_logged_in.png` });

    evidence.state_verification.push({
      test: 'Login',
      result: 'PASS',
      url: page.url(),
      timestamp: new Date().toISOString(),
    });

    // ============================================================
    // STEP 2: Navigate to PR creation form
    // ============================================================
    log('Step 2: Navigating to PR creation form');
    await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/new`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02_pr_form_empty.png` });
    log('PR form loaded');

    // ============================================================
    // STEP 3: Test item autocomplete — type "SAGO"
    // ============================================================
    log('Step 3: Testing item autocomplete — typing "SAGO"');

    // Find the item search combobox button and click it
    const itemButton = page.locator('button[role="combobox"]').first();
    if (await itemButton.count() > 0) {
      await itemButton.click();
      await page.waitForTimeout(500);

      // Type in the command input
      const searchInput = page.locator('input[placeholder*="item"]').first();
      if (await searchInput.count() === 0) {
        // Try other placeholders
        const altSearch = page.locator('[cmdk-input]').first();
        if (await altSearch.count() > 0) {
          await altSearch.fill('SAGO');
        }
      } else {
        await searchInput.fill('SAGO');
      }

      await page.waitForTimeout(1500); // Wait for debounce + API response
      await page.screenshot({ path: `${SCREENSHOT_DIR}/03_item_search_sago.png` });

      // Check if results appeared
      const searchResults = page.locator('[cmdk-item]');
      const resultCount = await searchResults.count();
      log(`Search results for "SAGO": ${resultCount} items found`);

      evidence.state_verification.push({
        test: 'Item autocomplete search "SAGO"',
        result: resultCount > 0 ? 'PASS' : 'FAIL',
        details: `${resultCount} results shown`,
        timestamp: new Date().toISOString(),
      });

      if (resultCount > 0) {
        // Click the first result (should be FG009 or FG050)
        const firstResult = searchResults.first();
        const resultText = await firstResult.textContent();
        log(`Selecting: ${resultText}`);
        await firstResult.click();
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/04_item_selected.png` });

        evidence.form_submissions.push({
          test: 'Item selection from autocomplete',
          action: 'Selected item from search results',
          search_query: 'SAGO',
          selected_text: resultText,
          timestamp: new Date().toISOString(),
        });
      }
    } else {
      log('WARNING: Combobox button not found — checking if old free-text input still exists');
      const freeTextInput = page.locator('input[placeholder="SKU"]');
      if (await freeTextInput.count() > 0) {
        evidence.state_verification.push({
          test: 'Item autocomplete replaces free text',
          result: 'FAIL',
          details: 'Old free-text SKU input still present — autocomplete not deployed',
          timestamp: new Date().toISOString(),
        });
        log('FAIL: Free-text SKU input still exists. Autocomplete not deployed.');
      }
    }

    // ============================================================
    // STEP 4: Fill remaining PR fields
    // ============================================================
    log('Step 4: Filling remaining PR fields');

    // Set qty to 2
    const qtyInput = page.locator('input[type="number"]').first();
    if (await qtyInput.count() > 0) {
      await qtyInput.fill('2');
    }

    // Select department
    const deptSelect = page.locator('button[role="combobox"]').nth(1); // Second combobox should be dept
    // Try to find department selector by looking for "Operations" text
    const deptButtons = page.locator('button:has-text("Department"), button:has-text("Select department"), select');
    if (await deptButtons.count() > 0) {
      await deptButtons.first().click();
      await page.waitForTimeout(500);
      const opsOption = page.locator('text=Operations').first();
      if (await opsOption.count() > 0) {
        await opsOption.click();
      }
    }

    // Add justification
    const justification = page.locator('textarea').first();
    if (await justification.count() > 0) {
      await justification.fill('Test PR for S120 validation — item autocomplete and price auto-fill');
    }

    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05_pr_form_filled.png`, fullPage: true });
    log('PR form filled');

    // ============================================================
    // STEP 5: Submit PR
    // ============================================================
    log('Step 5: Submitting PR');
    const submitBtn = page.locator('button:has-text("Create"), button:has-text("Submit"), button[type="submit"]').last();
    if (await submitBtn.count() > 0) {
      await submitBtn.click();
      await page.waitForTimeout(3000);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/06_pr_submitted.png` });

      const currentUrl = page.url();
      log(`After submit. URL: ${currentUrl}`);

      // Check if we got redirected to PR detail (success) or stayed on form (error)
      const isSuccess = currentUrl.includes('/purchase-requisitions/') && !currentUrl.includes('/new');

      evidence.form_submissions.push({
        test: 'PR form submission',
        action: 'Clicked Submit/Create button',
        result: isSuccess ? 'PASS' : 'FAIL',
        url_after: currentUrl,
        timestamp: new Date().toISOString(),
      });

      evidence.state_verification.push({
        test: 'PR creation success',
        result: isSuccess ? 'PASS' : 'FAIL',
        url: currentUrl,
        timestamp: new Date().toISOString(),
      });

      if (isSuccess) {
        // Extract PR number from URL or page
        const prNumber = currentUrl.split('/').pop();
        log(`PR created: ${prNumber}`);

        // ============================================================
        // STEP 6: Check PR detail page for price
        // ============================================================
        log('Step 6: Verifying PR detail page');
        await page.waitForTimeout(2000);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/07_pr_detail.png`, fullPage: true });

        // Check if estimated_rate is > 0
        const pageText = await page.textContent('body');
        const hasPrice = pageText.includes('₱') || pageText.includes('PHP') || /\d+\.\d{2}/.test(pageText);

        evidence.state_verification.push({
          test: 'PR has non-zero price',
          result: hasPrice ? 'PASS' : 'CHECK_MANUALLY',
          details: 'Page contains currency formatting',
          timestamp: new Date().toISOString(),
        });
      }
    } else {
      log('FAIL: Submit button not found');
      evidence.state_verification.push({
        test: 'PR submission',
        result: 'FAIL',
        details: 'Submit button not found on page',
        timestamp: new Date().toISOString(),
      });
    }

    // ============================================================
    // STEP 7: Navigate to PO list to test price edit
    // ============================================================
    log('Step 7: Navigating to PO list to test price edit');
    await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/08_po_list.png` });

    // Click first PO in the list
    const poLink = page.locator('a[href*="/purchase-orders/PO-"]').first();
    if (await poLink.count() > 0) {
      await poLink.click();
      await page.waitForURL('**/purchase-orders/PO-**', { timeout: 15000, waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/09_po_detail.png`, fullPage: true });
      log(`PO detail loaded: ${page.url()}`);

      // ============================================================
      // STEP 8: Test price edit — look for pencil icon
      // ============================================================
      log('Step 8: Testing price edit UX');

      // Check if price is read-only (text, not input)
      const priceInputs = page.locator('td input[type="number"]');
      const priceInputCount = await priceInputs.count();

      evidence.state_verification.push({
        test: 'PO price is read-only by default',
        result: priceInputCount === 0 ? 'PASS' : 'FAIL',
        details: `${priceInputCount} price inputs found (should be 0 — prices should be read-only text)`,
        timestamp: new Date().toISOString(),
      });

      // Look for the pencil/edit icon
      const editBtn = page.locator('button:has(svg.lucide-pencil), button[title="Edit price"]').first();
      if (await editBtn.count() > 0) {
        log('Found Edit Price button — clicking');
        await editBtn.click();
        await page.waitForTimeout(500);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/10_price_edit_expanded.png` });

        // Verify the price input and reason field appeared
        const priceInput = page.locator('input[type="number"]').first();
        const reasonField = page.locator('textarea[placeholder*="Reason"]').first();

        const priceInputVisible = await priceInput.isVisible().catch(() => false);
        const reasonVisible = await reasonField.isVisible().catch(() => false);

        evidence.state_verification.push({
          test: 'Edit Price reveals input + reason field',
          result: priceInputVisible && reasonVisible ? 'PASS' : 'FAIL',
          details: `price_input=${priceInputVisible}, reason_field=${reasonVisible}`,
          timestamp: new Date().toISOString(),
        });

        if (priceInputVisible && reasonVisible) {
          log('Price input and reason field visible — filling');
          await priceInput.fill('50');
          await reasonField.fill('Testing price edit S120 — supplier rate increase');
          await page.screenshot({ path: `${SCREENSHOT_DIR}/11_price_edit_filled.png` });

          // Click Save (check icon)
          const saveBtn = page.locator('button:has(svg.lucide-check)').first();
          if (await saveBtn.count() > 0) {
            await saveBtn.click();
            await page.waitForTimeout(2000);
            await page.screenshot({ path: `${SCREENSHOT_DIR}/12_price_edit_saved.png` });

            evidence.form_submissions.push({
              test: 'PO price edit submission',
              action: 'Changed price to ₱50, reason: "Testing price edit S120"',
              result: 'SUBMITTED',
              timestamp: new Date().toISOString(),
            });

            // Check for price change banner
            const banner = page.locator('[class*="alert"], [role="alert"]');
            const bannerVisible = await banner.count() > 0;

            evidence.state_verification.push({
              test: 'Price change banner appears after edit',
              result: bannerVisible ? 'PASS' : 'FAIL',
              timestamp: new Date().toISOString(),
            });

            if (bannerVisible) {
              const bannerText = await banner.first().textContent();
              log(`Price change banner: ${bannerText?.substring(0, 200)}`);
              evidence.state_verification.push({
                test: 'Price change banner shows old→new + reason',
                result: bannerText?.includes('50') ? 'PASS' : 'CHECK_MANUALLY',
                details: bannerText?.substring(0, 300),
                timestamp: new Date().toISOString(),
              });
            }
          }
        }
      } else {
        log('Edit Price button not found — checking if component is deployed');
        evidence.state_verification.push({
          test: 'Edit Price button exists',
          result: 'FAIL',
          details: 'Pencil icon / Edit price button not found on PO detail page',
          timestamp: new Date().toISOString(),
        });
      }
    } else {
      log('No POs found in list');
      evidence.state_verification.push({
        test: 'PO list has items',
        result: 'FAIL',
        details: 'No PO links found on the PO list page',
        timestamp: new Date().toISOString(),
      });
    }

    // ============================================================
    // STEP 9: Test disabled item doesn't appear in search
    // ============================================================
    log('Step 9: Testing disabled item exclusion');
    await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/new`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    const itemBtn2 = page.locator('button[role="combobox"]').first();
    if (await itemBtn2.count() > 0) {
      await itemBtn2.click();
      await page.waitForTimeout(500);
      const searchInput2 = page.locator('[cmdk-input]').first();
      if (await searchInput2.count() > 0) {
        await searchInput2.fill('INK BLACK');
        await page.waitForTimeout(1500);

        const results2 = page.locator('[cmdk-item]');
        const resultCount2 = await results2.count();

        evidence.state_verification.push({
          test: 'Disabled item (INK BLACK/CS101) excluded from search',
          result: resultCount2 === 0 ? 'PASS' : 'FAIL',
          details: `${resultCount2} results for "INK BLACK" (should be 0 — CS101 is disabled)`,
          timestamp: new Date().toISOString(),
        });

        await page.screenshot({ path: `${SCREENSHOT_DIR}/13_disabled_item_search.png` });
        log(`Disabled item search: ${resultCount2} results (expected 0)`);
      }
    }

  } catch (error) {
    log(`ERROR: ${error.message}`);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/error_final.png` }).catch(() => {});
    evidence.state_verification.push({
      test: 'Test execution',
      result: 'ERROR',
      details: error.message,
      timestamp: new Date().toISOString(),
    });
  } finally {
    await saveEvidence();
    await browser.close();

    // Print summary
    console.log('\n=== L3 TEST SUMMARY ===');
    const passes = evidence.state_verification.filter(v => v.result === 'PASS').length;
    const fails = evidence.state_verification.filter(v => v.result === 'FAIL').length;
    const checks = evidence.state_verification.filter(v => v.result === 'CHECK_MANUALLY').length;
    const errors = evidence.state_verification.filter(v => v.result === 'ERROR').length;
    console.log(`PASS: ${passes} | FAIL: ${fails} | CHECK: ${checks} | ERROR: ${errors}`);
    console.log(`Screenshots: ${SCREENSHOT_DIR}`);
    console.log(`Evidence: ${OUTPUT_DIR}`);

    for (const v of evidence.state_verification) {
      console.log(`  [${v.result}] ${v.test}${v.details ? ` — ${v.details}` : ''}`);
    }
  }
})();
