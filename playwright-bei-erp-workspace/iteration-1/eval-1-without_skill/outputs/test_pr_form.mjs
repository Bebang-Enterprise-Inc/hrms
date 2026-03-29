// Playwright test: Procurement PR form on my.bebang.ph
// Scenario: Login as test.commissary, search for item SAGO, select FG009,
//           verify price auto-fills, then submit the form.
// Run with: node test_pr_form.mjs
// (Requires @playwright/test or playwright package installed)

import { chromium } from 'playwright';

const BASE_URL = 'https://my.bebang.ph';
const LOGIN_EMAIL = 'test.commissary@bebang.ph';
const LOGIN_PASSWORD = 'BeiTest2026!';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // ------------------------------------------------------------------ //
    // Step 1: Navigate to login page
    // ------------------------------------------------------------------ //
    console.log('Navigating to login page...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });

    // ------------------------------------------------------------------ //
    // Step 2: Log in as test.commissary@bebang.ph
    // ------------------------------------------------------------------ //
    console.log('Logging in...');
    await page.getByLabel(/email/i).fill(LOGIN_EMAIL);
    await page.getByLabel(/password/i).fill(LOGIN_PASSWORD);
    await page.getByRole('button', { name: /sign in|log in/i }).click();

    // Wait for post-login redirect / dashboard to load
    await page.waitForURL(`${BASE_URL}/**`, { timeout: 15_000 });
    console.log('Login successful. Current URL:', page.url());

    // ------------------------------------------------------------------ //
    // Step 3: Navigate to PR (Purchase Request) creation page
    // ------------------------------------------------------------------ //
    console.log('Navigating to PR creation page...');
    // Try direct URL first; adjust path if the app uses a different route
    await page.goto(`${BASE_URL}/procurement/purchase-request/new`, {
      waitUntil: 'networkidle',
      timeout: 15_000,
    });
    console.log('PR creation page loaded. URL:', page.url());

    // ------------------------------------------------------------------ //
    // Step 4: Type "SAGO" in the item search field
    // ------------------------------------------------------------------ //
    console.log('Searching for item "SAGO"...');

    // The item search is typically a combobox / autocomplete input.
    // Try a few common selectors; the first one that is visible wins.
    const itemSearchInput = page
      .getByRole('combobox', { name: /item|search item/i })
      .or(page.locator('input[placeholder*="item" i]'))
      .or(page.locator('input[placeholder*="search" i]'))
      .first();

    await itemSearchInput.waitFor({ state: 'visible', timeout: 10_000 });
    await itemSearchInput.click();
    await itemSearchInput.fill('SAGO');

    // Wait for the dropdown list to appear
    const dropdown = page.locator('[role="listbox"], [role="option"], ul.dropdown-menu').first();
    await dropdown.waitFor({ state: 'visible', timeout: 8_000 });

    // ------------------------------------------------------------------ //
    // Step 5: Select FG009 from the dropdown
    // ------------------------------------------------------------------ //
    console.log('Selecting FG009 from dropdown...');
    const fg009Option = page
      .getByRole('option', { name: /FG009/i })
      .or(page.locator('[role="listbox"] li', { hasText: 'FG009' }))
      .or(page.locator('ul.dropdown-menu li', { hasText: 'FG009' }))
      .first();

    await fg009Option.waitFor({ state: 'visible', timeout: 8_000 });
    await fg009Option.click();
    console.log('FG009 selected.');

    // ------------------------------------------------------------------ //
    // Step 6: Verify the price auto-fills (non-zero value)
    // ------------------------------------------------------------------ //
    console.log('Verifying price auto-fill...');

    // Price field is typically a read-only or disabled input labelled "price"
    const priceInput = page
      .getByRole('spinbutton', { name: /price|unit price/i })
      .or(page.locator('input[name*="price" i]'))
      .or(page.locator('input[id*="price" i]'))
      .first();

    await priceInput.waitFor({ state: 'visible', timeout: 8_000 });

    const priceValue = await priceInput.inputValue();
    const priceNumber = parseFloat(priceValue);

    if (isNaN(priceNumber) || priceNumber <= 0) {
      throw new Error(
        `Price auto-fill FAILED: expected a positive number, got "${priceValue}"`
      );
    }
    console.log(`Price auto-filled successfully: ${priceValue}`);

    // ------------------------------------------------------------------ //
    // Step 7: Submit the form
    // ------------------------------------------------------------------ //
    console.log('Submitting the PR form...');
    const submitButton = page
      .getByRole('button', { name: /submit|create|save/i })
      .first();

    await submitButton.waitFor({ state: 'visible', timeout: 8_000 });
    await submitButton.click();

    // Wait for success feedback: URL change, toast notification, or success banner
    await Promise.race([
      page.waitForURL(`${BASE_URL}/procurement/purchase-request/**`, {
        timeout: 15_000,
      }),
      page
        .locator('[role="status"], .toast, .alert-success, [data-testid="success"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 }),
    ]);

    console.log('PR form submitted successfully. Final URL:', page.url());
    console.log('\nAll steps passed.');

  } catch (err) {
    console.error('\nTest FAILED:', err.message);
    // Capture a screenshot on failure for debugging
    await page.screenshot({ path: 'test_pr_form_failure.png', fullPage: true });
    console.error('Screenshot saved to test_pr_form_failure.png');
    process.exitCode = 1;
  } finally {
    await context.close();
    await browser.close();
  }
})();
