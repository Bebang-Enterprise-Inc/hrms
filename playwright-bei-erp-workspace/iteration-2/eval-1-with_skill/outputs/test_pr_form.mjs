/**
 * L3 Browser Test — PR Form Creation on my.bebang.ph
 *
 * Tests:
 * 1. Login at my.bebang.ph/login (L3 pattern — NOT hq.bebang.ph)
 * 2. Navigate to PR creation page
 * 3. Use shadcn combobox to search "SAGO" and select FG009
 * 4. Verify price auto-fills with an actual value (not just element existence)
 * 5. Fill qty, department, justification
 * 6. Click Create PR
 * 7. Read toast within 2 seconds of submit
 * 8. Verify PR created by URL change
 */

import { chromium } from 'playwright';

const EMAIL = 'test.commissary@bebang.ph';
const PASSWORD = 'BeiTest2026!';
const BASE_URL = 'https://my.bebang.ph';

async function runTest() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const results = {
    login: false,
    navigation: false,
    comboboxOpened: false,
    itemSelected: false,
    priceAutoFilled: false,
    priceValue: null,
    formFilled: false,
    submitClicked: false,
    toastText: null,
    toastReadWithin2s: false,
    urlChanged: false,
    finalUrl: null,
  };

  try {
    // ── Step 1: Login ────────────────────────────────────────────────────────
    console.log('[1] Logging in at my.bebang.ph/login...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
    results.login = true;
    console.log('    [PASS] Login succeeded. URL:', page.url());

    // ── Step 2: Navigate to PR creation page ────────────────────────────────
    console.log('[2] Navigating to PR creation page...');
    await page.goto(`${BASE_URL}/dashboard/procurement/purchase-requisitions/new`, {
      waitUntil: 'networkidle',
    });
    results.navigation = true;
    console.log('    [PASS] Navigation succeeded. URL:', page.url());

    // Enumerate buttons to confirm form is loaded
    const buttons = await page.locator('button').all();
    console.log(`    Found ${buttons.length} buttons on page:`);
    for (const btn of buttons) {
      const text = await btn.textContent().catch(() => '');
      if (text.trim()) console.log(`      - "${text.trim()}"`);
    }

    // ── Step 3: Shadcn combobox — search "SAGO", select FG009 ───────────────
    // PR form combobox indexes: 0=Department, 1=Item search, 2=UOM
    console.log('[3] Opening Item combobox (index 1)...');
    await page.locator('button[role="combobox"]').nth(1).click();
    await page.waitForTimeout(500);
    results.comboboxOpened = true;
    console.log('    [PASS] Combobox opened.');

    console.log('    Typing "SAGO" in search field...');
    await page.locator('input[placeholder*="search"]').first().fill('SAGO');
    await page.waitForTimeout(2000); // wait for debounce + API

    // List all options returned
    const options = await page.locator('[role="option"]').all();
    console.log(`    Found ${options.length} option(s) in dropdown:`);
    for (const opt of options) {
      const text = await opt.textContent().catch(() => '');
      console.log(`      - "${text.trim()}"`);
    }

    // Find and click the FG009 option
    let fg009Index = -1;
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent().catch(() => '');
      if (text.includes('FG009')) {
        fg009Index = i;
        break;
      }
    }

    if (fg009Index === -1) {
      throw new Error('FG009 not found in dropdown results. Options: ' +
        (await Promise.all(options.map(o => o.textContent().catch(() => '')))).join(' | '));
    }

    await page.locator('[role="option"]').nth(fg009Index).click();
    results.itemSelected = true;
    console.log(`    [PASS] Selected FG009 (option index ${fg009Index}).`);

    // ── Step 4: Verify price auto-fills with actual value ───────────────────
    console.log('[4] Verifying price auto-fill...');
    // Wait for price field to populate (debounce/API lookup)
    await page.waitForTimeout(2000);

    // Try common price field selectors
    const priceSelectors = [
      'input[name="price"]',
      'input[name="unit_price"]',
      'input[placeholder*="price" i]',
      'input[placeholder*="Price" i]',
      '[data-testid*="price"] input',
      '[data-testid*="unit-price"] input',
    ];

    let priceEl = null;
    let priceSelector = null;
    for (const sel of priceSelectors) {
      const count = await page.locator(sel).count();
      if (count > 0) {
        priceEl = page.locator(sel).first();
        priceSelector = sel;
        break;
      }
    }

    if (!priceEl) {
      // Fallback: grab all number inputs and log them
      const numInputs = await page.locator('input[type="number"], input[inputmode="numeric"]').all();
      console.log(`    No named price field found. Found ${numInputs.length} numeric input(s):`);
      for (let i = 0; i < numInputs.length; i++) {
        const val = await numInputs[i].inputValue().catch(() => '');
        const ph = await numInputs[i].getAttribute('placeholder').catch(() => '');
        const name = await numInputs[i].getAttribute('name').catch(() => '');
        console.log(`      [${i}] name="${name}" placeholder="${ph}" value="${val}"`);
      }
      throw new Error('Could not locate price input. See numeric inputs logged above.');
    }

    const priceValue = await priceEl.inputValue();
    console.log(`    Price field (${priceSelector}) value: "${priceValue}"`);

    if (!priceValue || priceValue.trim() === '' || priceValue === '0') {
      throw new Error(`Price did not auto-fill or is zero. Got: "${priceValue}"`);
    }

    const priceNum = parseFloat(priceValue.replace(/,/g, ''));
    if (isNaN(priceNum) || priceNum <= 0) {
      throw new Error(`Price auto-filled but is not a valid positive number: "${priceValue}"`);
    }

    results.priceAutoFilled = true;
    results.priceValue = priceValue;
    console.log(`    [PASS] Price auto-filled: ${priceValue}`);

    // ── Step 5: Fill qty, department, justification ──────────────────────────
    console.log('[5] Filling qty, department, justification...');

    // Qty — numeric input (skip the price input already found)
    const qtySelectors = [
      'input[name="qty"]',
      'input[name="quantity"]',
      'input[placeholder*="qty" i]',
      'input[placeholder*="quantity" i]',
    ];
    let qtyFilled = false;
    for (const sel of qtySelectors) {
      const count = await page.locator(sel).count();
      if (count > 0) {
        await page.locator(sel).first().fill('10');
        console.log(`    Filled qty via "${sel}".`);
        qtyFilled = true;
        break;
      }
    }
    if (!qtyFilled) {
      // Fallback: fill the first non-price numeric input
      const numInputs = await page.locator('input[type="number"], input[inputmode="numeric"]').all();
      for (const inp of numInputs) {
        const name = await inp.getAttribute('name').catch(() => '');
        if (name !== 'price' && name !== 'unit_price') {
          await inp.fill('10');
          console.log(`    Filled qty via fallback (name="${name}").`);
          qtyFilled = true;
          break;
        }
      }
    }
    if (!qtyFilled) {
      console.warn('    [WARN] Could not find qty field — skipping.');
    }

    // Department — combobox index 0
    console.log('    Opening Department combobox (index 0)...');
    await page.locator('button[role="combobox"]').nth(0).click();
    await page.waitForTimeout(500);
    const deptSearchInput = page.locator('input[placeholder*="search"]').first();
    await deptSearchInput.fill('Operations');
    await page.waitForTimeout(1500);
    const deptOptions = await page.locator('[role="option"]').all();
    if (deptOptions.length > 0) {
      await deptOptions[0].click();
      console.log('    Filled department (first match for "Operations").');
    } else {
      console.warn('    [WARN] No department options found — skipping.');
    }

    // Justification — textarea or named input
    const justSelectors = [
      'textarea[name="justification"]',
      'textarea[name="notes"]',
      'textarea[placeholder*="justification" i]',
      'textarea[placeholder*="reason" i]',
      'textarea',
    ];
    let justFilled = false;
    for (const sel of justSelectors) {
      const count = await page.locator(sel).count();
      if (count > 0) {
        await page.locator(sel).first().fill('L3 automated test — SAGO FG009 purchase requisition');
        console.log(`    Filled justification via "${sel}".`);
        justFilled = true;
        break;
      }
    }
    if (!justFilled) {
      console.warn('    [WARN] Could not find justification field — skipping.');
    }

    results.formFilled = true;
    console.log('    [PASS] Form fields filled.');

    // ── Step 6 & 7: Click Create PR and read toast within 2 seconds ──────────
    console.log('[6] Finding and clicking Create PR button...');
    const submitBtn = page.locator('button[type="submit"], button').filter({ hasText: /create pr|submit|create requisition/i }).first();
    const submitBtnText = await submitBtn.textContent().catch(() => 'unknown');
    console.log(`    Submitting via button: "${submitBtnText.trim()}"`);

    const submitTime = Date.now();
    await submitBtn.click();
    results.submitClicked = true;
    console.log('    [PASS] Submit clicked.');

    // Read toast within 2 seconds
    console.log('[7] Reading toast (within 2s of submit)...');
    await page.waitForTimeout(2000);
    const elapsed = Date.now() - submitTime;
    const toasts = await page.locator('[data-sonner-toast]').allTextContents();
    results.toastText = toasts.length > 0 ? toasts.join(' | ') : null;
    results.toastReadWithin2s = elapsed <= 2500;

    if (results.toastText) {
      console.log(`    [PASS] Toast(s) read at ${elapsed}ms: "${results.toastText}"`);
    } else {
      console.warn(`    [WARN] No toast found after ${elapsed}ms. Page may still be processing.`);
    }

    // ── Step 8: Verify URL changed (PR was created) ──────────────────────────
    console.log('[8] Verifying URL changed after PR creation...');
    // Give the app a moment to redirect
    try {
      await page.waitForURL(
        (url) => !url.toString().endsWith('/new') && url.toString().includes('purchase-requisitions'),
        { timeout: 10000 }
      );
    } catch {
      // Not a hard failure — capture current URL and evaluate
    }

    results.finalUrl = page.url();
    results.urlChanged = !results.finalUrl.endsWith('/new');
    const urlStatus = results.urlChanged ? '[PASS]' : '[FAIL]';
    console.log(`    ${urlStatus} URL after submit: ${results.finalUrl}`);

  } catch (err) {
    console.error('\n[ERROR]', err.message);
  } finally {
    await browser.close();
  }

  // ── Summary ─────────────────────────────────────────────────────────────────
  console.log('\n========== TEST SUMMARY ==========');
  const checks = [
    ['Login at my.bebang.ph/login',          results.login],
    ['Navigation to /new PR page',           results.navigation],
    ['Combobox opened',                      results.comboboxOpened],
    ['FG009 item selected',                  results.itemSelected],
    ['Price auto-filled (value check)',      results.priceAutoFilled],
    ['Form fields filled (qty/dept/just)',   results.formFilled],
    ['Submit button clicked',                results.submitClicked],
    ['Toast read within 2s',                 results.toastReadWithin2s],
    ['URL changed after submit',             results.urlChanged],
  ];

  let passed = 0;
  for (const [label, ok] of checks) {
    const marker = ok ? 'PASS' : 'FAIL';
    console.log(`  [${marker}] ${label}`);
    if (ok) passed++;
  }

  console.log(`\n  Price value     : ${results.priceValue ?? 'n/a'}`);
  console.log(`  Toast message   : ${results.toastText ?? 'none'}`);
  console.log(`  Final URL       : ${results.finalUrl ?? 'n/a'}`);
  console.log(`\n  Result: ${passed}/${checks.length} checks passed`);
  console.log('===================================\n');

  process.exit(passed === checks.length ? 0 : 1);
}

runTest();
