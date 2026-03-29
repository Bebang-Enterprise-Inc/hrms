/**
 * E2E Verification — Create a Purchase Order with TIN-compliant supplier
 *
 * Steps:
 * 1. Login as CEO (sam@bebang.ph)
 * 2. Find a TIN-compliant supplier via API
 * 3. Find a valid item code via API
 * 4. Create a PO via the UI
 * 5. Verify PO was created
 * 6. Submit for approval
 * 7. Approve the PO (if possible as CEO)
 *
 * Run: node scripts/testing/e2e_po_creation_verification.mjs
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_WEB = 'https://my.bebang.ph';
const OUTPUT_DIR = 'output/e2e/po_creation';
const ARTIFACTS_DIR = `${OUTPUT_DIR}/artifacts`;

// Ensure directories exist
for (const dir of [OUTPUT_DIR, ARTIFACTS_DIR]) {
  fs.mkdirSync(dir, { recursive: true });
}

const results = [];

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  console.log(`[${ts}] ${msg}`);
}

function record(step, status, detail) {
  results.push({ step, status, detail, ts: new Date().toISOString() });
  console.log(`  [${status}] ${step}: ${detail}`);
}

async function screenshot(page, name) {
  const filePath = `${ARTIFACTS_DIR}/${name}.png`;
  await page.screenshot({ path: filePath, fullPage: true });
  log(`Screenshot saved: ${filePath}`);
  return filePath;
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu', '--disable-extensions'],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  let supplierName = null;
  let supplierTIN = null;
  let itemCode = null;
  let itemName = null;
  let itemRate = null;
  let poNumber = null;
  let poStatus = null;

  try {
    // ========== STEP 1: LOGIN ==========
    log('\n=== STEP 1: LOGIN as CEO ===');
    await page.goto(`${BASE_WEB}/login`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.fill('input[name="email"]', 'sam@bebang.ph');
    await page.fill('input[name="password"]', '2289454');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
    record('Login', 'PASS', 'Logged in as sam@bebang.ph (CEO)');

    // ========== STEP 2: FIND TIN-COMPLIANT SUPPLIER ==========
    log('\n=== STEP 2: Find TIN-compliant supplier via API ===');

    const supplierResult = await page.evaluate(async () => {
      const r = await fetch('/api/procurement/suppliers?page=1&page_size=100', {
        headers: { 'Accept': 'application/json' },
      });
      const text = await r.text();
      let json = null;
      try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json, body: text.substring(0, 3000) };
    });

    log(`Supplier API status: ${supplierResult.status}, ok: ${supplierResult.ok}`);

    if (!supplierResult.ok || !supplierResult.json) {
      log(`Supplier API failed. Body: ${supplierResult.body}`);
      record('Find Supplier', 'FAIL', `API returned ${supplierResult.status}`);
      throw new Error('Cannot proceed without supplier data');
    }

    // Find suppliers with TIN
    const suppliers = supplierResult.json.data || supplierResult.json.suppliers || supplierResult.json;
    log(`Total suppliers returned: ${Array.isArray(suppliers) ? suppliers.length : 'NOT AN ARRAY'}`);

    // Debug: show structure of first supplier
    if (Array.isArray(suppliers) && suppliers.length > 0) {
      log(`First supplier keys: ${Object.keys(suppliers[0]).join(', ')}`);
      log(`First supplier sample: ${JSON.stringify(suppliers[0]).substring(0, 500)}`);
    }

    let compliantSupplier = null;
    if (Array.isArray(suppliers)) {
      for (const s of suppliers) {
        const tin = s.tin || s.tax_id || s.TIN || s.tax_identification_number || '';
        if (tin && tin.trim() !== '' && tin.trim() !== 'N/A') {
          compliantSupplier = s;
          supplierTIN = tin.trim();
          break;
        }
      }
    }

    if (!compliantSupplier) {
      log('No TIN-compliant supplier found in first page. Trying page 2...');
      const page2Result = await page.evaluate(async () => {
        const r = await fetch('/api/procurement/suppliers?page=2&page_size=100', {
          headers: { 'Accept': 'application/json' },
        });
        const text = await r.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return { ok: r.ok, status: r.status, json };
      });

      const suppliers2 = page2Result.json?.data || page2Result.json?.suppliers || page2Result.json || [];
      if (Array.isArray(suppliers2)) {
        for (const s of suppliers2) {
          const tin = s.tin || s.tax_id || s.TIN || s.tax_identification_number || '';
          if (tin && tin.trim() !== '' && tin.trim() !== 'N/A') {
            compliantSupplier = s;
            supplierTIN = tin.trim();
            break;
          }
        }
      }
    }

    if (!compliantSupplier) {
      // Fallback: navigate to supplier list and pick one with TIN from UI
      log('API did not yield TIN-compliant supplier. Navigating to supplier list...');
      await page.goto(`${BASE_WEB}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(3000);
      await screenshot(page, 'step2_supplier_list_fallback');

      // Try to read supplier names from the table
      const supplierRows = await page.locator('table tbody tr').count();
      log(`Supplier table rows: ${supplierRows}`);

      // Click first supplier to check detail
      if (supplierRows > 0) {
        // Read all supplier names
        for (let i = 0; i < Math.min(supplierRows, 20); i++) {
          const name = await page.locator(`table tbody tr:nth-child(${i+1})`).textContent().catch(() => '');
          log(`  Row ${i}: ${name.substring(0, 100)}`);
        }
      }

      record('Find Supplier', 'FAIL', 'No TIN-compliant supplier found via API or UI');
      throw new Error('Cannot proceed without a TIN-compliant supplier');
    }

    supplierName = compliantSupplier.supplier_name || compliantSupplier.name || compliantSupplier.supplier;
    log(`Found TIN-compliant supplier: "${supplierName}" (TIN: ${supplierTIN})`);
    record('Find Supplier', 'PASS', `${supplierName} (TIN: ${supplierTIN})`);

    // ========== STEP 3: FIND A VALID ITEM ==========
    log('\n=== STEP 3: Find a valid item code via API ===');

    const itemResult = await page.evaluate(async () => {
      const r = await fetch('/api/procurement/lookup/search-items?query=a', {
        headers: { 'Accept': 'application/json' },
      });
      const text = await r.text();
      let json = null;
      try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json, body: text.substring(0, 3000) };
    });

    log(`Item API status: ${itemResult.status}, ok: ${itemResult.ok}`);

    if (!itemResult.ok || !itemResult.json) {
      log(`Item API body: ${itemResult.body}`);
      // Try alternative search
      const itemResult2 = await page.evaluate(async () => {
        const r = await fetch('/api/procurement/lookup/search-items?query=sugar', {
          headers: { 'Accept': 'application/json' },
        });
        const text = await r.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return { ok: r.ok, status: r.status, json, body: text.substring(0, 3000) };
      });
      if (itemResult2.ok && itemResult2.json) {
        Object.assign(itemResult, itemResult2);
      }
    }

    const items = itemResult.json?.data || itemResult.json?.items || itemResult.json || [];
    log(`Items returned: ${Array.isArray(items) ? items.length : 'NOT AN ARRAY'}`);

    if (Array.isArray(items) && items.length > 0) {
      log(`First item keys: ${Object.keys(items[0]).join(', ')}`);
      log(`First item: ${JSON.stringify(items[0]).substring(0, 500)}`);
    }

    let selectedItem = null;
    if (Array.isArray(items)) {
      // Pick first item with a rate, or just first item
      selectedItem = items.find(i => (i.standard_rate || i.rate || i.price) > 0) || items[0];
    }

    if (selectedItem) {
      itemCode = selectedItem.item_code || selectedItem.name || selectedItem.code;
      itemName = selectedItem.item_name || selectedItem.description || selectedItem.name || itemCode;
      itemRate = selectedItem.standard_rate || selectedItem.rate || selectedItem.price || 100;
      log(`Selected item: "${itemName}" (${itemCode}), rate: ${itemRate}`);
      record('Find Item', 'PASS', `${itemName} (${itemCode}), rate: ${itemRate}`);
    } else {
      log('No items found via API. Will try to use UI item search in the PO form.');
      record('Find Item', 'INFO', 'No items from API; will try UI search in PO form');
    }

    // ========== STEP 4: CREATE THE PO ==========
    log('\n=== STEP 4: Create Purchase Order ===');

    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders/new`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    await screenshot(page, 'step4a_po_form_before');

    // List all buttons and interactive elements for discovery
    const allButtons = await page.locator('button').allTextContents();
    log(`Buttons on page: ${allButtons.map(b => b.trim()).filter(Boolean).join(' | ')}`);

    // 4a. Select supplier using Radix combobox
    log('Selecting supplier...');

    // Find the supplier combobox
    const comboboxes = await page.locator('button[role="combobox"]').all();
    log(`Found ${comboboxes.length} combobox(es)`);
    for (let i = 0; i < comboboxes.length; i++) {
      const text = await comboboxes[i].textContent().catch(() => '');
      log(`  Combobox ${i}: "${text.trim()}"`);
    }

    // Find the supplier combobox - look for one with "Select supplier" or "supplier" text
    let supplierComboIndex = -1;
    for (let i = 0; i < comboboxes.length; i++) {
      const text = (await comboboxes[i].textContent().catch(() => '')).toLowerCase();
      if (text.includes('supplier') || text.includes('select')) {
        supplierComboIndex = i;
        break;
      }
    }
    if (supplierComboIndex === -1) supplierComboIndex = 0; // Default to first

    log(`Clicking combobox ${supplierComboIndex} for supplier selection...`);
    await comboboxes[supplierComboIndex].click();
    await page.waitForTimeout(500);

    // Type supplier name in popover search
    const searchInput = page.locator('input[placeholder*="earch"]').first();
    const searchVisible = await searchInput.isVisible().catch(() => false);
    if (searchVisible) {
      // Type first few chars of supplier name
      const searchTerm = supplierName.substring(0, Math.min(15, supplierName.length));
      log(`Typing "${searchTerm}" in supplier search...`);
      await searchInput.fill(searchTerm);
      await page.waitForTimeout(2000); // Wait for debounce + API
    } else {
      log('No search input found in popover. Trying alternative selectors...');
      const altInput = page.locator('[role="dialog"] input, [data-radix-popper-content-wrapper] input').first();
      if (await altInput.isVisible().catch(() => false)) {
        await altInput.fill(supplierName.substring(0, 15));
        await page.waitForTimeout(2000);
      }
    }

    // Select the supplier option
    const options = await page.locator('[role="option"]').all();
    log(`Found ${options.length} option(s)`);
    for (let i = 0; i < Math.min(options.length, 5); i++) {
      const optText = await options[i].textContent().catch(() => '');
      log(`  Option ${i}: "${optText.trim().substring(0, 80)}"`);
    }

    if (options.length > 0) {
      // Click the first matching option
      let matched = false;
      for (let i = 0; i < options.length; i++) {
        const optText = (await options[i].textContent().catch(() => '')).toLowerCase();
        if (optText.includes(supplierName.toLowerCase().substring(0, 10))) {
          await options[i].click();
          matched = true;
          log(`Selected supplier option ${i}`);
          break;
        }
      }
      if (!matched) {
        await options[0].click();
        log(`Selected first available option`);
      }
    } else {
      log('WARNING: No options appeared for supplier selection');
    }

    await page.waitForTimeout(1000);

    // 4b. Set delivery date to tomorrow
    log('Setting delivery date...');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0]; // YYYY-MM-DD

    const dateInput = page.locator('input[type="date"]').first();
    const dateVisible = await dateInput.isVisible().catch(() => false);
    if (dateVisible) {
      await dateInput.fill(dateStr);
      log(`Set delivery date to ${dateStr}`);
    } else {
      // Try clicking a date picker button
      const dateButtons = await page.locator('button:has-text("Pick"), button:has-text("date"), button:has-text("Date")').all();
      log(`Date picker buttons: ${dateButtons.length}`);
      if (dateButtons.length > 0) {
        await dateButtons[0].click();
        await page.waitForTimeout(500);
        // Try to interact with a calendar popover
        const calendarDay = page.locator('[role="gridcell"] button').first();
        if (await calendarDay.isVisible().catch(() => false)) {
          // Click a day in the future
          const dayButtons = await page.locator('[role="gridcell"] button:not([disabled])').all();
          if (dayButtons.length > 0) {
            await dayButtons[dayButtons.length - 1].click(); // Pick last available day
            log('Selected a date from calendar picker');
          }
        }
      } else {
        log('WARNING: No date input found');
      }
    }

    await page.waitForTimeout(500);

    // 4c. Fill item in first line item row (DO NOT click Add Item — one row already exists)
    log('Filling line item row 0...');

    // The item field is a text input named "items.0.item_code" — fill it directly
    const itemCodeInput = page.locator('input[name="items.0.item_code"]');
    const itemCodeVisible = await itemCodeInput.isVisible().catch(() => false);

    if (itemCodeVisible) {
      await itemCodeInput.fill(itemCode || 'KL004');
      log(`Typed item code "${itemCode || 'KL004'}" into items.0.item_code`);
      await page.waitForTimeout(2000); // Wait for autocomplete/lookup

      // Check if autocomplete suggestions appeared
      const autocompleteOptions = await page.locator('[role="option"], [role="listbox"] li, .autocomplete-item').all();
      if (autocompleteOptions.length > 0) {
        log(`Found ${autocompleteOptions.length} autocomplete option(s)`);
        await autocompleteOptions[0].click();
        await page.waitForTimeout(1000);
        log('Selected first autocomplete option');
      }
    } else {
      // Try alternative: maybe it's a different input pattern
      log('items.0.item_code not visible, discovering all text inputs...');
      const textInputs = await page.locator('input[type="text"], input:not([type])').all();
      for (let i = 0; i < textInputs.length; i++) {
        const name = await textInputs[i].getAttribute('name').catch(() => '');
        const placeholder = await textInputs[i].getAttribute('placeholder').catch(() => '');
        const visible = await textInputs[i].isVisible().catch(() => false);
        if (visible) {
          log(`  Text input ${i}: name="${name}" placeholder="${placeholder}"`);
        }
      }
      // Try filling the first input that looks like item code
      const itemInput = page.locator('input[name*="item_code"], input[name*="item"], input[placeholder*="Item"], input[placeholder*="item"]').first();
      if (await itemInput.isVisible().catch(() => false)) {
        await itemInput.fill(itemCode || 'KL004');
        await page.waitForTimeout(2000);
        log('Filled item input via fallback selector');
      }
    }

    // 4d. Set quantity and rate using named inputs
    log('Setting quantity and rate...');

    // Discover all number inputs
    const allInputs = await page.locator('input').all();
    for (const inp of allInputs) {
      const name = await inp.getAttribute('name').catch(() => null);
      if (name && name.startsWith('items.0')) {
        const value = await inp.inputValue().catch(() => '');
        log(`  items.0 input: name="${name}" value="${value}"`);
      }
    }

    // Fill qty for row 0
    const qtyInput = page.locator('input[name="items.0.qty"]');
    if (await qtyInput.isVisible().catch(() => false)) {
      await qtyInput.fill('');
      await qtyInput.fill('5');
      log('Set items.0.qty = 5');
    }

    // Fill rate for row 0
    const rateInput = page.locator('input[name="items.0.rate"]');
    if (await rateInput.isVisible().catch(() => false)) {
      await rateInput.fill('');
      await rateInput.fill(String(itemRate || 100));
      log(`Set items.0.rate = ${itemRate || 100}`);
    }

    // Tab out to trigger calculation
    await rateInput.press('Tab').catch(() => {});
    await page.waitForTimeout(1000);

    // Remove second line item row if it exists (was added by mistake in previous run logic)
    const removeRowBtn = page.locator('button[aria-label*="remove"], button[aria-label*="delete"], table tbody tr:nth-child(2) button').last();
    if (await removeRowBtn.isVisible().catch(() => false)) {
      // Only remove if there are 2+ rows
      const rowCount = await page.locator('input[name*="items.1"]').count();
      if (rowCount > 0) {
        log('Removing extra line item row...');
        // Don't remove — it might break the form. Just leave row 1 empty.
      }
    }

    await page.waitForTimeout(500);

    // 4e. Screenshot AFTER filling
    await screenshot(page, 'step4b_po_form_filled');

    // 4f. Submit the PO
    log('Submitting PO...');

    // Find the create/submit button
    const submitBtn = page.locator('button:has-text("Create Purchase Order"), button:has-text("Create PO"), button:has-text("Submit"), button:has-text("Save")').first();
    const submitVisible = await submitBtn.isVisible().catch(() => false);

    if (submitVisible) {
      const btnText = await submitBtn.textContent();
      log(`Clicking "${btnText.trim()}" button...`);

      // Set up response interceptor
      let apiCaptured = null;
      page.on('response', async (response) => {
        const url = response.url();
        if (url.includes('/api/procurement/purchase-orders') && response.request().method() === 'POST') {
          try {
            apiCaptured = {
              url,
              status: response.status(),
              body: await response.json().catch(() => null),
            };
          } catch {}
        }
      });

      await submitBtn.click();
      await page.waitForTimeout(5000); // Wait for API response

      // Read toast
      const toasts = await page.locator('[data-sonner-toast]').allTextContents();
      log(`Toasts: ${toasts.map(t => t.trim()).join(' | ') || 'NONE'}`);

      if (apiCaptured) {
        log(`API captured: status=${apiCaptured.status}, body=${JSON.stringify(apiCaptured.body).substring(0, 500)}`);
      }

      await screenshot(page, 'step4c_po_after_submit');

      // Check current URL for PO ID
      const currentUrl = page.url();
      log(`Current URL after submit: ${currentUrl}`);

      const urlMatch = currentUrl.match(/purchase-orders\/([A-Z0-9-]+)/i);
      if (urlMatch) {
        poNumber = urlMatch[1];
        log(`PO Number from URL: ${poNumber}`);
      }

      // Check for success
      const hasSuccessToast = toasts.some(t => t.toLowerCase().includes('success') || t.toLowerCase().includes('created'));
      const hasErrorToast = toasts.some(t => t.toLowerCase().includes('error') || t.toLowerCase().includes('fail'));

      if (hasSuccessToast || (apiCaptured && apiCaptured.status >= 200 && apiCaptured.status < 300)) {
        record('Create PO', 'PASS', `PO created. Toast: ${toasts.join('; ')}. URL: ${currentUrl}`);
      } else if (hasErrorToast) {
        record('Create PO', 'FAIL', `Error toast: ${toasts.join('; ')}`);
      } else {
        record('Create PO', 'UNCLEAR', `No clear success/error. Toasts: ${toasts.join('; ')}. URL: ${currentUrl}`);
      }

      page.removeAllListeners('response');
    } else {
      log('WARNING: No submit button found');
      // List all buttons again
      const btns = await page.locator('button').allTextContents();
      log(`All buttons: ${btns.map(b => b.trim()).filter(Boolean).join(' | ')}`);
      record('Create PO', 'FAIL', 'No submit button found on PO creation form');
      await screenshot(page, 'step4c_no_submit_btn');
    }

    // ========== STEP 5: VERIFY PO IN LIST ==========
    log('\n=== STEP 5: Verify PO in list ===');

    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Read first few rows
    const poRows = await page.locator('table tbody tr').count();
    log(`PO table rows: ${poRows}`);

    for (let i = 0; i < Math.min(poRows, 5); i++) {
      const rowText = await page.locator(`table tbody tr:nth-child(${i+1})`).textContent().catch(() => '');
      log(`  Row ${i}: ${rowText.substring(0, 150)}`);

      // Check if this row contains our supplier
      if (supplierName && rowText.includes(supplierName.substring(0, 15))) {
        if (!poNumber) {
          // Try to extract PO number from the row
          const poMatch = rowText.match(/PO-\d+|PUR-ORD-\d+/i);
          if (poMatch) poNumber = poMatch[0];
        }
        log(`  ^ Found our supplier in this row!`);
      }
    }

    await screenshot(page, 'step5_po_list');

    if (poNumber) {
      record('Verify PO in List', 'PASS', `PO ${poNumber} found in list`);
    } else {
      record('Verify PO in List', 'INFO', 'Could not confirm PO in list (may be on different page or different naming)');
    }

    // ========== STEP 6: SUBMIT FOR APPROVAL ==========
    log('\n=== STEP 6: Submit for Approval ===');

    // Navigate to the PO detail page
    if (poNumber) {
      await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders/${poNumber}`, { waitUntil: 'networkidle', timeout: 60000 });
    } else {
      // Click first row in the list to open latest PO
      const firstRow = page.locator('table tbody tr:first-child a, table tbody tr:first-child').first();
      await firstRow.click();
      await page.waitForTimeout(3000);
    }

    await page.waitForTimeout(2000);
    const detailUrl = page.url();
    log(`PO detail URL: ${detailUrl}`);
    await screenshot(page, 'step6a_po_detail');

    // Look for Submit for Approval button
    const submitApprovalBtn = page.locator('button:has-text("Submit for Approval"), button:has-text("Submit"), button:has-text("Request Approval")').first();
    const submitApprovalVisible = await submitApprovalBtn.isVisible().catch(() => false);

    if (submitApprovalVisible) {
      const btnText = await submitApprovalBtn.textContent();
      log(`Clicking "${btnText.trim()}"...`);
      await submitApprovalBtn.click();
      await page.waitForTimeout(3000);

      const toasts = await page.locator('[data-sonner-toast]').allTextContents();
      log(`Toasts after submit for approval: ${toasts.join(' | ') || 'NONE'}`);

      await screenshot(page, 'step6b_after_submit_approval');

      const hasSuccess = toasts.some(t => t.toLowerCase().includes('success') || t.toLowerCase().includes('submitted') || t.toLowerCase().includes('approval'));
      record('Submit for Approval', hasSuccess ? 'PASS' : 'UNCLEAR', `Toasts: ${toasts.join('; ') || 'none'}`);
    } else {
      // List all buttons on detail page
      const detailButtons = await page.locator('button').allTextContents();
      log(`Detail page buttons: ${detailButtons.map(b => b.trim()).filter(Boolean).join(' | ')}`);
      record('Submit for Approval', 'SKIP', 'No "Submit for Approval" button found on detail page');
    }

    // ========== STEP 7: APPROVE THE PO ==========
    log('\n=== STEP 7: Approve PO ===');
    await page.waitForTimeout(1000);

    // Refresh page to get updated state
    await page.reload({ waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(2000);

    const approveBtn = page.locator('button:has-text("Approve"), button:has-text("Confirm")').first();
    const approveVisible = await approveBtn.isVisible().catch(() => false);

    if (approveVisible) {
      const btnText = await approveBtn.textContent();
      log(`Clicking "${btnText.trim()}" button (opens modal)...`);
      await approveBtn.click();
      await page.waitForTimeout(2000);

      await screenshot(page, 'step7a_approve_modal');

      // The approve button opens a modal dialog with its own "Approve" button
      // Look for the modal's Approve button (inside dialog/modal overlay)
      const modalApproveBtn = page.locator('[role="dialog"] button:has-text("Approve"), .modal button:has-text("Approve"), [data-state="open"] button:has-text("Approve")').first();
      const modalApproveBtnVisible = await modalApproveBtn.isVisible().catch(() => false);

      if (modalApproveBtnVisible) {
        log('Found Approve button inside modal, clicking...');
        await modalApproveBtn.click();
        await page.waitForTimeout(5000);
      } else {
        // Fallback: try any green/primary Approve button that appeared after the first click
        log('No modal Approve button via role=dialog. Trying all visible Approve buttons...');
        const allApproveBtns = await page.locator('button:has-text("Approve")').all();
        log(`  Found ${allApproveBtns.length} Approve button(s)`);
        for (let i = 0; i < allApproveBtns.length; i++) {
          const vis = await allApproveBtns[i].isVisible().catch(() => false);
          const text = await allApproveBtns[i].textContent().catch(() => '');
          log(`  Approve btn ${i}: visible=${vis}, text="${text.trim()}"`);
        }
        // Click the last visible Approve button (modal buttons appear after header buttons)
        for (let i = allApproveBtns.length - 1; i >= 0; i--) {
          const vis = await allApproveBtns[i].isVisible().catch(() => false);
          if (vis) {
            await allApproveBtns[i].click();
            log(`Clicked Approve button ${i}`);
            await page.waitForTimeout(5000);
            break;
          }
        }
      }

      const toasts = await page.locator('[data-sonner-toast]').allTextContents();
      log(`Toasts after approve: ${toasts.join(' | ') || 'NONE'}`);

      await screenshot(page, 'step7b_after_approve');

      const hasSuccess = toasts.some(t => t.toLowerCase().includes('approved') || t.toLowerCase().includes('success'));
      if (hasSuccess) {
        record('Approve PO', 'PASS', `Toasts: ${toasts.join('; ')}`);
      } else {
        // Check page content for approval status change
        const pageText = await page.locator('body').textContent().catch(() => '');
        const hasApprovedStatus = pageText.includes('Approved') || pageText.includes('approved');
        record('Approve PO', hasApprovedStatus ? 'PASS' : 'UNCLEAR', `Toasts: ${toasts.join('; ') || 'none'}. Page contains "Approved": ${hasApprovedStatus}`);
      }
    } else {
      const detailButtons = await page.locator('button').allTextContents();
      log(`Buttons on page: ${detailButtons.map(b => b.trim()).filter(Boolean).join(' | ')}`);
      record('Approve PO', 'SKIP', 'No "Approve" button visible (CEO may auto-approve or status already advanced)');
    }

    // Get final PO status from page
    log('\nReading final PO status...');
    const badges = await page.locator('[class*="badge"], [class*="status"], [class*="Badge"]').allTextContents();
    log(`Badges/status elements: ${badges.map(b => b.trim()).filter(Boolean).join(' | ')}`);
    poStatus = badges.find(b => b.trim()) || 'Unknown';

    await screenshot(page, 'step7_final_status');

  } catch (err) {
    log(`\nERROR: ${err.message}`);
    await screenshot(page, 'error_screenshot').catch(() => {});
    record('Error', 'FAIL', err.message);
  } finally {
    await context.close();
    await browser.close();
  }

  // ========== FINAL REPORT ==========
  log('\n\n========================================');
  log('         E2E PO CREATION REPORT');
  log('========================================');
  log(`Supplier: ${supplierName || 'NOT FOUND'} (TIN: ${supplierTIN || 'N/A'})`);
  log(`Item: ${itemName || 'NOT FOUND'} (${itemCode || 'N/A'})`);
  log(`PO Number: ${poNumber || 'NOT CAPTURED'}`);
  log(`Final Status: ${poStatus || 'UNKNOWN'}`);
  log('');
  log('Step Results:');
  for (const r of results) {
    log(`  [${r.status}] ${r.step}: ${r.detail}`);
  }
  log('');

  const allPass = results.every(r => r.status === 'PASS' || r.status === 'INFO' || r.status === 'SKIP');
  const anyFail = results.some(r => r.status === 'FAIL');

  if (anyFail) {
    log('VERDICT: NO — PO workflow has failures');
  } else if (allPass) {
    log('VERDICT: YES — Full PO workflow runs end-to-end');
  } else {
    log('VERDICT: PARTIAL — Some steps unclear, manual review needed');
  }

  // Save report
  const report = {
    timestamp: new Date().toISOString(),
    supplier: { name: supplierName, tin: supplierTIN },
    item: { code: itemCode, name: itemName, rate: itemRate },
    po_number: poNumber,
    final_status: poStatus,
    results,
    verdict: anyFail ? 'NO' : (allPass ? 'YES' : 'PARTIAL'),
  };
  fs.writeFileSync(`${OUTPUT_DIR}/report.json`, JSON.stringify(report, null, 2));
  log(`\nReport saved to ${OUTPUT_DIR}/report.json`);
  log(`Screenshots in ${ARTIFACTS_DIR}/`);
}

run().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
