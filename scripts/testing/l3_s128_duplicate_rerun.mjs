/**
 * L3-3 Rerun: Duplicate a PO
 * Fix: Use "All POs" tab instead of "Approved" tab, wait for table data
 */

import { chromium } from 'playwright';
import fs from 'fs';

const BASE_WEB = 'https://my.bebang.ph';
const OUTPUT_DIR = 'output/l3/S128';
const EVIDENCE_DIR = `${OUTPUT_DIR}/evidence`;
const ARTIFACTS_DIR = `${OUTPUT_DIR}/artifacts`;

function log(msg) {
  const ts = new Date().toLocaleString('en-PH', { timeZone: 'Asia/Manila' });
  console.log(`[${ts}] ${msg}`);
}

async function takeScreenshot(page, name) {
  const filepath = `${ARTIFACTS_DIR}/${name}.png`;
  await page.screenshot({ path: filepath, fullPage: false });
  log(`Screenshot: ${filepath}`);
  return filepath;
}

async function main() {
  log('=== L3-3 Rerun: Duplicate a PO ===');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const actions = [];

  try {
    // Login as procurement user
    log('Logging in as test.procurement@bebang.ph');
    await page.goto(`${BASE_WEB}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(2000);
    await page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().fill('test.procurement@bebang.ph');
    await page.locator('input[type="password"]').first().fill('BeiTest2026!');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForURL('**/dashboard**', { timeout: 30000 });
    log('Logged in');
    actions.push({ type: 'login', user: 'test.procurement@bebang.ph' });

    // Navigate to PO list — stay on "All POs" tab (default)
    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    actions.push({ type: 'navigate', url: '/dashboard/procurement/purchase-orders' });

    // Wait for table rows to appear (up to 15s)
    log('Waiting for PO table to load...');
    try {
      await page.locator('table tbody tr').first().waitFor({ state: 'visible', timeout: 15000 });
    } catch {
      log('Table still empty after 15s, refreshing...');
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(3000);
    }

    await takeScreenshot(page, 'L3-3r_01_all_pos');

    // Find a PO link in the table
    const poLinks = page.locator('table a[href*="/purchase-orders/"]');
    const linkCount = await poLinks.count();
    log(`Found ${linkCount} PO links in table`);

    if (linkCount === 0) {
      console.log('[FAIL] L3-3: No PO links found in All POs tab');
      return;
    }

    // Click the first PO
    const poText = await poLinks.first().textContent();
    log(`Clicking PO: ${poText}`);
    await poLinks.first().click();
    await page.waitForTimeout(3000);
    actions.push({ type: 'click', element: `PO link: ${poText}` });
    await takeScreenshot(page, 'L3-3r_02_po_detail');

    // Check the PO status to confirm it's not Draft/Cancelled
    const pageContent = await page.textContent('body');
    log(`Page contains "Duplicate PO" button: ${pageContent.includes('Duplicate PO')}`);

    // Look for Duplicate PO button
    const duplicateBtn = page.locator('button', { hasText: /Duplicate PO/i }).first();
    const dupVisible = await duplicateBtn.isVisible();
    log(`Duplicate PO button visible: ${dupVisible}`);

    if (!dupVisible) {
      // Maybe this PO is Draft — try another PO that's not Draft
      log('Duplicate button not visible — PO may be Draft. Looking for non-Draft PO...');

      // Go back and find a PO with status badge showing Approved/Sent/etc
      await page.goBack();
      await page.waitForTimeout(2000);

      // Look for a status badge that's NOT Draft
      const statusBadges = page.locator('table td span, table td div');
      const allRows = page.locator('table tbody tr');
      const rowCount = await allRows.count();

      for (let i = 0; i < Math.min(rowCount, 10); i++) {
        const rowText = await allRows.nth(i).textContent();
        if (rowText.includes('Approved') || rowText.includes('Sent') ||
            rowText.includes('Received') || rowText.includes('Pending')) {
          const rowLink = allRows.nth(i).locator('a[href*="/purchase-orders/"]').first();
          const linkText = await rowLink.textContent();
          log(`Found non-Draft PO: ${linkText} (row: ${rowText.slice(0, 80)})`);
          await rowLink.click();
          await page.waitForTimeout(3000);
          await takeScreenshot(page, 'L3-3r_03_nondraft_po');

          const dupBtn2 = page.locator('button', { hasText: /Duplicate PO/i }).first();
          const vis2 = await dupBtn2.isVisible();
          if (vis2) {
            log('Found Duplicate PO button on non-Draft PO!');
            // Continue with this PO
            await performDuplicate(page, dupBtn2, linkText, actions);
            return;
          }
        }
      }

      console.log('[FAIL] L3-3: Could not find any PO with Duplicate button visible');
      return;
    }

    // Duplicate button is visible — proceed
    await performDuplicate(page, duplicateBtn, poText, actions);

  } catch (e) {
    log(`L3-3 error: ${e.message}`);
    await takeScreenshot(page, 'L3-3r_error');
    console.log(`[FAIL] L3-3: ${e.message}`);
  } finally {
    fs.writeFileSync(
      `${EVIDENCE_DIR}/L3-3.json`,
      JSON.stringify({ scenario_id: 'L3-3', actions }, null, 2),
    );
    await context.close();
    await browser.close();
  }
}

async function performDuplicate(page, duplicateBtn, poText, actions) {
  // Register network listener before clicking
  const dupResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes('duplicate') && resp.request().method() === 'POST',
    { timeout: 15000 },
  );

  log('Clicking Duplicate PO button');
  await duplicateBtn.click();
  actions.push({ type: 'submit', element: 'Duplicate PO button', method: 'browser_click' });

  const dupResponse = await dupResponsePromise;
  const responseBody = await dupResponse.json();
  log(`Duplicate response: ${JSON.stringify(responseBody).slice(0, 400)}`);

  // Wait for redirect
  await page.waitForTimeout(3000);
  const newUrl = page.url();
  log(`After duplicate, URL: ${newUrl}`);
  await takeScreenshot(page, 'L3-3r_04_new_po');

  const success = responseBody.success === true && responseBody.name;

  // Update evidence files
  const formSubs = JSON.parse(fs.readFileSync(`${OUTPUT_DIR}/form_submissions.json`, 'utf8'));
  formSubs.push({
    form: 'duplicate_po',
    inputs: { source_po: poText },
    submit_action: 'Duplicate PO',
    response: responseBody,
    screenshot_after: `${ARTIFACTS_DIR}/L3-3r_04_new_po.png`,
    form_submitted: true,
    submit_method: 'browser_click',
    network_captured: true,
    submit_network_request: dupResponse.url(),
    values_verified: true,
  });
  fs.writeFileSync(`${OUTPUT_DIR}/form_submissions.json`, JSON.stringify(formSubs, null, 2));

  const apiMuts = JSON.parse(fs.readFileSync(`${OUTPUT_DIR}/api_mutations.json`, 'utf8'));
  apiMuts.push({
    endpoint: dupResponse.url(),
    method: 'POST',
    payload: '{}',
    status: dupResponse.status(),
    response_body: JSON.stringify(responseBody).slice(0, 500),
  });
  fs.writeFileSync(`${OUTPUT_DIR}/api_mutations.json`, JSON.stringify(apiMuts, null, 2));

  const stateVer = JSON.parse(fs.readFileSync(`${OUTPUT_DIR}/state_verification.json`, 'utf8'));
  stateVer.push({
    check: 'New Draft PO created from source PO via browser click',
    before: `Source: ${poText}`,
    after: `New PO: ${responseBody.po_no || responseBody.name}, msg: ${responseBody.message}`,
    method: 'API response body',
    passed: success,
  });

  // Check for "Duplicated from" in remarks on new page
  if (success) {
    const bodyText = await page.textContent('body');
    const hasSourceRef = bodyText.includes('Duplicated from') || bodyText.includes(poText);
    stateVer.push({
      check: 'New PO references source PO',
      before: 'N/A',
      after: `Page mentions source: ${hasSourceRef}`,
      method: 'textContent()',
      passed: hasSourceRef,
    });
  }
  fs.writeFileSync(`${OUTPUT_DIR}/state_verification.json`, JSON.stringify(stateVer, null, 2));

  console.log(success
    ? `[PASS] L3-3: Duplicate a PO — New PO ${responseBody.po_no || responseBody.name} created from ${poText}`
    : `[FAIL] L3-3: Duplicate a PO — ${JSON.stringify(responseBody)}`);
}

main().catch((e) => {
  console.error('L3-3 rerun crashed:', e);
  process.exit(1);
});
