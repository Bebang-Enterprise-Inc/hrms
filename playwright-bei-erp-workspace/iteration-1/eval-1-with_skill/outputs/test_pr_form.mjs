/**
 * test_pr_form.mjs
 * Playwright test: Purchase Requisition form on my.bebang.ph
 *
 * Flow:
 *   1. Login at hq.bebang.ph (Frappe backend) as test.commissary@bebang.ph
 *   2. Navigate to the PR creation page on my.bebang.ph
 *   3. Type "SAGO" in the ItemSearchCombobox
 *   4. Select FG009 from the dropdown results
 *   5. Verify that the estimated_rate (price) field auto-fills to a non-zero value
 *   6. Submit the form (Create PR button)
 *   7. Verify the form submission triggers the expected API call and a PR is created
 *
 * Test level: L3 (API-verified via page.evaluate fetch + network interception)
 *
 * Run:
 *   npx playwright test test_pr_form.mjs --project=chromium --headed=false
 */

import { chromium } from 'playwright';

const BASE_FRAPPE   = 'https://hq.bebang.ph';
const BASE_FRONTEND = 'https://my.bebang.ph';
const PR_NEW_URL    = `${BASE_FRONTEND}/dashboard/procurement/purchase-requisitions/new`;

const TEST_USER     = 'test.commissary@bebang.ph';
const TEST_PASSWORD = 'BeiTest2026!';

// ── helpers ──────────────────────────────────────────────────────────────────

function assert(condition, message) {
  if (!condition) throw new Error(`ASSERTION FAILED: ${message}`);
}

// ── main test ─────────────────────────────────────────────────────────────────

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-extensions',
      '--no-first-run',
    ],
  });

  const context = await browser.newContext({
    locale: 'en-PH',
    timezoneId: 'Asia/Manila',
  });

  const page = await context.newPage();

  // Capture API calls related to procurement for L3 verification
  const capturedResponses = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (
      url.includes('/api/procurement/') ||
      url.includes('/api/method/hrms.api') ||
      url.includes('/api/resource/Purchase%20Requisition') ||
      url.includes('/api/resource/BEI%20Purchase%20Requisition')
    ) {
      try {
        const body = await response.json().catch(() => null);
        capturedResponses.push({ url, status: response.status(), body });
      } catch {
        capturedResponses.push({ url, status: response.status(), body: null });
      }
    }
  });

  try {
    // ── Step 1: Login at Frappe backend ─────────────────────────────────────
    console.log('[1/7] Logging in at Frappe backend...');
    await page.goto(`${BASE_FRAPPE}/login`, { waitUntil: 'networkidle' });

    await page.fill('input[name="usr"]', TEST_USER);
    await page.fill('input[name="pwd"]', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for redirect away from /login — indicates successful authentication
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15000,
    });
    console.log('    Login successful. Session cookies established.');

    // ── Step 2: Navigate to New PR page ─────────────────────────────────────
    console.log('[2/7] Navigating to New Purchase Requisition page...');
    await page.goto(PR_NEW_URL, { waitUntil: 'networkidle' });

    // Verify the page heading is present (L1)
    const heading = page.getByRole('heading', { name: 'New Purchase Requisition' });
    await heading.waitFor({ timeout: 10000 });
    console.log('    Page loaded: "New Purchase Requisition" heading visible.');

    // ── Step 3: Open the ItemSearchCombobox and type "SAGO" ─────────────────
    console.log('[3/7] Opening item search combobox and typing "SAGO"...');

    // The combobox trigger is a <Button role="combobox"> in the first table row.
    // It shows the placeholder text "Search by code or name..." when empty.
    const comboboxTrigger = page
      .getByRole('combobox')
      .first();

    await comboboxTrigger.waitFor({ timeout: 10000 });
    await comboboxTrigger.click();

    // The popover opens and renders a CommandInput (cmdk).
    // The input inside the Command popover has placeholder "Type item code or name..."
    const searchInput = page.getByPlaceholder('Type item code or name...');
    await searchInput.waitFor({ timeout: 5000 });
    await searchInput.fill('SAGO');

    console.log('    Typed "SAGO" into item search input. Waiting for results...');

    // The component debounces 300 ms then fetches /api/procurement/lookup/search-items
    // Wait for at least one CommandItem to appear with FG009
    const fg009Item = page.getByRole('option', { name: /FG009/i });
    await fg009Item.waitFor({ timeout: 8000 });
    console.log('    Dropdown results appeared. FG009 option is visible.');

    // ── Step 4: Select FG009 from the dropdown ───────────────────────────────
    console.log('[4/7] Selecting FG009 from the dropdown...');
    await fg009Item.click();

    // After selection the popover closes and the combobox trigger now shows "FG009"
    await page.waitForFunction(
      () => {
        const btn = document.querySelector('button[role="combobox"]');
        return btn && btn.textContent && btn.textContent.includes('FG009');
      },
      { timeout: 5000 }
    );
    console.log('    FG009 selected. Combobox trigger now shows item code.');

    // ── Step 5: Verify price auto-fills ──────────────────────────────────────
    console.log('[5/7] Verifying that the estimated price auto-fills...');

    // The price field is an <input type="number"> for items.0.estimated_rate.
    // After onSelect(), the component calls form.setValue(`items.0.estimated_rate`, item.standard_rate)
    // if standard_rate > 0.  We wait for its value to become non-zero.
    const priceInput = page.locator('input[type="number"]').nth(1); // index 0 = qty, index 1 = estimated_rate

    await page.waitForFunction(
      () => {
        // Find all number inputs: first is qty (default 1), second is estimated_rate
        const inputs = Array.from(document.querySelectorAll('input[type="number"]'));
        if (inputs.length < 2) return false;
        const rateInput = inputs[1];
        const val = parseFloat(rateInput.value);
        return !isNaN(val) && val > 0;
      },
      { timeout: 5000 }
    );

    const rateValue = await priceInput.inputValue();
    const rateNum = parseFloat(rateValue);
    assert(rateNum > 0, `Expected estimated_rate > 0 after FG009 selection, got: ${rateValue}`);
    console.log(`    Price auto-filled: ${rateValue} (PHP). Assertion passed.`);

    // ── Step 5b: Select a department (required field) ────────────────────────
    console.log('[5b] Selecting a department (required for form submission)...');

    // The Department field is a <Select> rendered with shadcn SelectTrigger.
    // Its trigger button contains the placeholder "Select department".
    const departmentTrigger = page.getByRole('combobox', { name: /department/i }).or(
      page.getByText('Select department')
    );

    // Fallback: locate by placeholder text inside SelectTrigger
    const deptSelect = page.locator('[data-slot="select-trigger"]').first();
    // If data-slot attr not present, fall back to finding by placeholder span text
    const deptTrigger = page.getByText('Select department');
    await deptTrigger.waitFor({ timeout: 8000 });
    await deptTrigger.click();

    // Wait for dropdown to open and pick the first available option
    const firstDeptOption = page.getByRole('option').first();
    await firstDeptOption.waitFor({ timeout: 5000 });
    await firstDeptOption.click();
    console.log('    Department selected.');

    // ── Step 6: Submit the form ───────────────────────────────────────────────
    console.log('[6/7] Submitting the PR form...');

    // Set up response interception before clicking submit
    const prCreateResponsePromise = page.waitForResponse(
      (response) =>
        (response.url().includes('/api/procurement/') ||
          response.url().includes('/api/method/') ||
          response.url().includes('/api/resource/')) &&
        response.request().method() === 'POST',
      { timeout: 15000 }
    );

    // The submit button text is "Create PR" when not pending
    const submitButton = page.getByRole('button', { name: 'Create PR' });
    await submitButton.waitFor({ timeout: 5000 });
    await submitButton.click();
    console.log('    "Create PR" button clicked. Waiting for API response...');

    // ── Step 7: Verify API response and PR creation ───────────────────────────
    console.log('[7/7] Verifying form submission and PR creation...');

    let createResponse = null;
    try {
      createResponse = await prCreateResponsePromise;
    } catch (err) {
      console.warn('    WARNING: Did not capture a POST response within timeout. May have already navigated.');
    }

    if (createResponse) {
      const status = createResponse.status();
      assert(
        status === 200 || status === 201,
        `Expected HTTP 200/201 from PR create API, got ${status}`
      );
      const body = await createResponse.json().catch(() => null);
      console.log(`    API responded with HTTP ${status}.`);
      if (body) {
        const prNumber = body?.pr_number || body?.message?.pr_number || body?.data?.name || body?.name;
        if (prNumber) {
          console.log(`    PR created: ${prNumber}`);
        }
      }
    }

    // Confirm navigation away from /new (success → redirect to /[id])
    await page.waitForURL(
      (url) => !url.pathname.endsWith('/new'),
      { timeout: 15000 }
    );
    const finalUrl = page.url();
    console.log(`    Redirected to: ${finalUrl}`);
    assert(
      finalUrl.includes('/purchase-requisitions/') && !finalUrl.endsWith('/new'),
      `Expected redirect to PR detail page, got: ${finalUrl}`
    );

    // L3: Verify via browser-session API that the PR record exists in Frappe
    const prName = finalUrl.split('/purchase-requisitions/')[1]?.split('?')[0];
    if (prName) {
      console.log(`    Verifying PR record "${prName}" exists via browser-session API...`);
      const apiResult = await page.evaluate(async (name) => {
        const r = await fetch(
          `/api/frappe/api/resource/Purchase Requisition/${encodeURIComponent(name)}`,
          { headers: { Accept: 'application/json' } }
        );
        const text = await r.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return { ok: r.ok, status: r.status, json, body: text.substring(0, 500) };
      }, prName);

      assert(
        apiResult.ok,
        `Expected PR record to be retrievable via API, got HTTP ${apiResult.status}: ${apiResult.body}`
      );
      console.log(`    L3 PASS: PR record "${prName}" confirmed in backend.`);
    }

    console.log('\n=== ALL ASSERTIONS PASSED ===');
    console.log('Test level: L3 (API-verified)');
    console.log('Test result: PASS');

    // Screenshot evidence
    await page.screenshot({
      path: 'F:/Dropbox/Projects/BEI-ERP/playwright-bei-erp-workspace/iteration-1/eval-1-with_skill/outputs/test_pr_form_result.png',
      fullPage: false,
    });
    console.log('Screenshot saved: test_pr_form_result.png');

  } catch (err) {
    console.error('\n=== TEST FAILED ===');
    console.error(err.message);

    // Capture failure screenshot
    try {
      await page.screenshot({
        path: 'F:/Dropbox/Projects/BEI-ERP/playwright-bei-erp-workspace/iteration-1/eval-1-with_skill/outputs/test_pr_form_failure.png',
        fullPage: false,
      });
      console.error('Failure screenshot saved: test_pr_form_failure.png');
    } catch {}

    // Dump captured API responses for diagnosis
    if (capturedResponses.length > 0) {
      console.error('\nCaptured API responses during test:');
      capturedResponses.forEach((r) => {
        console.error(`  ${r.status} ${r.url}`);
        if (r.body) {
          const msg = r.body?._server_messages;
          if (msg) {
            try {
              const parsed = JSON.parse(msg);
              const first = typeof parsed[0] === 'string' ? JSON.parse(parsed[0]) : parsed[0];
              console.error(`    Server error: ${first?.message}`);
            } catch {}
          }
          if (r.body?.exception) {
            console.error(`    Exception: ${r.body.exception}`);
          }
        }
      });
    }

    process.exit(1);
  } finally {
    await context.close();
    await browser.close();
  }
}

run().catch((err) => {
  console.error('Unhandled error:', err);
  process.exit(1);
});
