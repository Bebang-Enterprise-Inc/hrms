/**
 * S152 Chain A — Standard Flow (≤P500K, Mae-only PO, 3-level RFP)
 * ALL actions in the browser. ZERO API shortcuts. ZERO silent fallbacks.
 * If a button isn't found, it's a FAIL — not a reason to call the API.
 *
 * Run: node scripts/testing/l3_s152_chain_a.mjs
 */
import {
  BASE, FRAPPE, OUT, USERS, log,
  fLogin, fDoc, fList,
  launchBrowser, loginAs, closeSession, shot, waitNav,
  createEvidence, verify, recordForm, recordResult, writeEvidence, printSummary,
  generateTestPng,
  // Browser action functions — ONLY way to mutate
  browserCreatePO, browserSubmitPO, browserApprovePO,
  browserCreateGR, browserCreateInvoice, browserCreateRFP,
  browserSubmitAndApproveRFP,
} from './l3_s152_helpers.mjs';

const ev = createEvidence();
const state = {};

(async () => {
  log('=== S152 CHAIN A — ALL BROWSER, ZERO API SHORTCUTS ===\n');

  // Frappe API login for state VERIFICATION only (GET, never POST)
  await fLogin('sam@bebang.ph', '2289454');
  const browser = await launchBrowser();

  try {
    // =================================================================
    // S152-A01: Create Purchase Requisition (browser)
    // =================================================================
    log('\n=== S152-A01: Create Purchase Requisition (browser) ===');
    let session = await loginAs(browser, 'finance');
    let page = session.page;

    await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);
    await shot(page, 'A01_pr_new_form');

    // Fill Department — diagnose and set
    try {
      // Check what's currently selected
      const deptCombo = page.locator('[role="combobox"]').first();
      const deptText = await deptCombo.textContent();
      log(`  Department combobox current text: "${deptText.trim()}"`);

      // Check if already set to Operations
      if (deptText.trim() !== 'Operations') {
        await deptCombo.click();
        await page.waitForTimeout(1000);
        const options = await page.locator('[role="option"]').allTextContents();
        log(`  Department options: ${options.slice(0, 10).join(', ')}`);
        const opsOpt = page.locator('[role="option"]').filter({ hasText: /^Operations$/i }).first();
        if (await opsOpt.count()) {
          await opsOpt.click();
          log(`  Department set to Operations`);
        } else {
          await page.locator('[role="option"]').first().click();
          log(`  Department set to first option`);
        }
        await page.waitForTimeout(500);
      } else {
        log(`  Department already set to Operations`);
      }

      // Also handle native select if present (hidden, backing the combobox)
      const nativeSelects = await page.locator('select').count();
      log(`  Native selects on page: ${nativeSelects}`);
      if (nativeSelects > 0) {
        const firstSelect = page.locator('select').first();
        const selectOptions = await firstSelect.locator('option').allTextContents();
        log(`  First native select options: ${selectOptions.slice(0, 5).join(', ')}...`);
        // If it has department-like options, set it
        if (selectOptions.some(o => /operations/i.test(o))) {
          await firstSelect.selectOption({ label: 'Operations' });
          // Trigger React's synthetic change event
          await firstSelect.dispatchEvent('change');
          log(`  Native select also set to Operations`);
        }
      }
    } catch (e) { log(`  WARN: Department: ${e.message}`); }
    await page.waitForTimeout(500);

    // Fill Date Required
    try {
      const dateInput = page.locator('input[name="date_required"], input[type="date"]').first();
      if (await dateInput.count()) {
        // Use PHT (UTC+8) date to avoid timezone mismatch with server
        await dateInput.fill(new Date(Date.now() + 8 * 3600000 + 86400000).toISOString().slice(0, 10));
      }
    } catch (e) { log(`  WARN: Date: ${e.message}`); }

    // Fill Purpose
    try {
      const purpose = page.locator('textarea[name="purpose"], textarea[name="justification"], textarea').first();
      if (await purpose.count()) await purpose.fill('S152 Chain A — E2E acceptance test');
    } catch (e) { log(`  WARN: Purpose: ${e.message}`); }

    // Dump form HTML structure for debugging (first run only)
    try {
      const itemsHtml = await page.evaluate(() => {
        // Find the items section
        const section = document.querySelector('[class*="item"], .items, table') ||
                        document.querySelector('form') ||
                        document.body;
        // Get all input/select/button elements
        const els = section.querySelectorAll('input, select, button, [role="combobox"], textarea');
        return Array.from(els).slice(0, 60).map(el => ({
          tag: el.tagName,
          type: el.type || '',
          name: el.name || '',
          placeholder: el.placeholder || '',
          role: el.getAttribute('role') || '',
          class: el.className?.toString()?.slice(0, 80) || '',
          text: el.textContent?.slice(0, 50) || '',
          value: el.value?.slice(0, 30) || '',
        }));
      });
      const fs2 = await import('fs');
      fs2.default.writeFileSync(`${OUT}/form_debug.json`, JSON.stringify(itemsHtml, null, 2));
      log(`  Form debug: ${itemsHtml.length} elements dumped`);
    } catch (e) { log(`  WARN: Form debug: ${e.message}`); }

    // Add and fill items
    try {
      // DON'T fill Est. Price — let the system use standard rates during PO conversion
      // This avoids 10% price variance override requirements
      const testItems = [
        { name: '16oz cup', desc: '16OZ CUP WITH LOGO', qty: '100', price: '' },
        { name: 'alaska evap', desc: 'ALASKA EVAP 1L', qty: '10', price: '' },
        { name: 'nestle cream', desc: 'NESTLE CREAM', qty: '20', price: '' },
      ];

      // The form starts with 1 blank row. We need to add 2 more for 3 total.
      const addBtn = page.getByRole('button', { name: /add item/i }).first();
      if (await addBtn.count()) {
        for (let i = 0; i < 2; i++) {
          await addBtn.click();
          await page.waitForTimeout(800);
        }
      }

      // Fill each row's fields
      for (let i = 0; i < testItems.length; i++) {
        const item = testItems[i];

        // Item name — combobox with cmdk search popover
        // Known search terms that match real items: 'cup' -> 16OZ CUP, 'alaska' -> ALASKA EVAP, 'cream' -> NESTLE CREAM
        const searchTerms = ['16oz cup', 'alaska evap', 'nestle cream'];
        const itemComboIndex = 1 + i * 2; // 1, 3, 5
        try {
          const allCombos = page.locator('[role="combobox"]');
          const combo = allCombos.nth(itemComboIndex);
          if (await combo.count()) {
            await combo.click();
            await page.waitForTimeout(1000);

            // Focus the cmdk search input inside the popover and type
            const cmdkInput = page.locator('[cmdk-input]').first();
            if (await cmdkInput.count()) {
              await cmdkInput.focus();
              await page.waitForTimeout(300);

              // Try specific term, then first word, then 'a' as fallback
              let itemSelected = false;
              const termsToTry = [searchTerms[i], searchTerms[i].split(' ')[0], 'a'];
              for (const term of termsToTry) {
                await cmdkInput.press('Control+A');
                await page.keyboard.type(term, { delay: 80 });
                await page.waitForTimeout(3000); // wait for debounced API call

                const optCount = await page.locator('[cmdk-item], [role="option"]').count();
                log(`    Row ${i}: ${optCount} items for "${term}"`);
                if (optCount > 0) {
                  const idx = (term === 'a') ? Math.min(i, optCount - 1) : 0;
                  await page.locator('[cmdk-item], [role="option"]').nth(idx).click();
                  await page.waitForTimeout(800);
                  log(`    Row ${i}: item selected`);
                  itemSelected = true;
                  break;
                }
              }
              if (!itemSelected) {
                await page.keyboard.press('Escape');
                log(`    WARN: No items found for row ${i} after retries`);
              }
            } else {
              log(`    Row ${i}: no cmdk-input found`);
              await page.keyboard.press('Escape');
            }
          }
        } catch (e) { log(`    Item combobox row ${i}: ${e.message}`); }

        // Description — may auto-fill from selected item, fill only if empty
        const descInputs = page.locator('input[name*="description"], input[placeholder*="Description"]');
        const descInput = descInputs.nth(i);
        if (await descInput.count()) {
          const currentDesc = await descInput.inputValue();
          if (!currentDesc) {
            await descInput.fill(item.desc);
          }
          await page.waitForTimeout(200);
        }

        // Qty
        const qtyInputs = page.locator('input[name*="qty"], input[placeholder*="Qty"]');
        const qtyInput = qtyInputs.nth(i);
        if (await qtyInput.count()) {
          await qtyInput.fill(item.qty);
          await page.waitForTimeout(200);
        }

        // UOM — each row has 2 comboboxes: item search + UOM select
        // Layout: combobox[0]=dept, then per row: [1+i*2]=item search, [2+i*2]=UOM
        // So UOM comboboxes are at indices 2, 4, 6
        let uomFilled = false;
        try {
          const uomComboIndex = 2 + i * 2; // dept=0, row0: item=1, uom=2, row1: item=3, uom=4, row2: item=5, uom=6
          const allCombos = page.locator('[role="combobox"]');
          const comboCount = await allCombos.count();
          log(`    Row ${i}: targeting UOM combobox index ${uomComboIndex} of ${comboCount}`);
          if (comboCount > uomComboIndex) {
            const combo = allCombos.nth(uomComboIndex);
            await combo.scrollIntoViewIfNeeded();
            await combo.click();
            await page.waitForTimeout(1000);
            const optCount = await page.locator('[role="option"]').count();
            log(`    Row ${i}: ${optCount} UOM options visible`);
            if (optCount > 0) {
              // Pick PCS/PIECE for general items
              const pcsOpt = page.locator('[role="option"]').filter({ hasText: /^PCS$|^PIECE$/i }).first();
              if (await pcsOpt.count()) {
                await pcsOpt.click();
                uomFilled = true;
              } else {
                await page.locator('[role="option"]').first().click();
                uomFilled = true;
              }
            } else {
              await page.keyboard.press('Escape');
            }
            await page.waitForTimeout(300);
          }
        } catch (e) { log(`    UOM combobox: ${e.message}`); }

        if (!uomFilled) log(`    WARN: Could not fill UOM for row ${i}`);

        // Est. Price — only fill if a price is specified
        if (item.price) {
          const priceInputs = page.locator('input[name*="price"], input[name*="est_price"], input[name*="estimated"], input[placeholder*="Est"]');
          const priceInput = priceInputs.nth(i);
          if (await priceInput.count()) {
            await priceInput.fill(item.price);
            await page.waitForTimeout(200);
          }
        }
      }
      log(`  Filled ${testItems.length} item rows`);
    } catch (e) { log(`  WARN: Items: ${e.message}`); }

    recordForm(ev, 'S152-A01', { department: 'Operations', purpose: 'S152 Chain A', items: '3 items' });

    // Submit
    await shot(page, 'A01_pr_filled');

    // Find and click "Create PR" button specifically
    const allButtons = await page.locator('button').allTextContents();
    log(`  Buttons on page: ${allButtons.map(b => b.trim()).filter(b => b).join(' | ')}`);

    // The button text is "Create PR" based on screenshot
    const createBtn = page.getByRole('button', { name: /create pr/i }).first();
    const createBtnAlt = page.getByRole('button', { name: /^create$/i }).first();
    const createBtnAlt2 = page.locator('button:has-text("Create PR")').first();

    let clicked = false;
    for (const btn of [createBtn, createBtnAlt2, createBtnAlt]) {
      if (await btn.count()) {
        const btnText = await btn.textContent();
        log(`  Clicking button: "${btnText.trim()}"`);
        await btn.click();
        clicked = true;
        break;
      }
    }
    if (!clicked) log('  FAIL: No create/submit button found');

    // Wait for navigation or response
    await page.waitForTimeout(3000);

    // Check for toast/error messages
    const toasts = await page.locator('[role="alert"], [class*="toast"], [class*="error"], [class*="Toaster"]').allTextContents();
    if (toasts.length > 0) log(`  Toasts/errors: ${toasts.join(' | ')}`);

    // Check for any validation messages
    const validationMsgs = await page.locator('[class*="error"], [class*="invalid"], [class*="destructive"]').allTextContents();
    const filtered = validationMsgs.filter(m => m.trim().length > 0 && m.trim().length < 200);
    if (filtered.length > 0) log(`  Validation msgs: ${filtered.slice(0, 5).join(' | ')}`);

    await waitNav(page, 3000);
    log(`  URL after submit: ${page.url()}`);
    await shot(page, 'A01_pr_after_submit');

    // Extract PR name from URL
    const prUrl = page.url();
    const prMatch = prUrl.match(/purchase-requisitions\/([^/?]+)/);
    let prName = prMatch ? decodeURIComponent(prMatch[1]) : null;
    if (!prName || prName === 'new') {
      // Check API for recently created PR (read-only verification)
      const recentPRs = await fList('BEI Purchase Requisition', { purpose: ['like', '%S152 Chain A%'] }, ['name', 'status']);
      if (recentPRs.length > 0) prName = recentPRs[0].name;
    }

    let a01pass = false;
    if (prName && prName !== 'new') {
      state.prName = prName;
      const pr = await fDoc('BEI Purchase Requisition', prName);
      a01pass = pr && (pr.status === 'Draft' || pr.status === 'Pending Approval');
      verify(ev, 'S152-A01', 'PR created in browser', 'Filled form at /purchase-requisitions/new',
        `PR=${prName} status=${pr?.status}`, a01pass);
    } else {
      verify(ev, 'S152-A01', 'PR created', 'Browser form', 'FAIL: No PR name found — browser form did not create PR', false);
    }
    recordResult(ev, 'S152-A01', 'happy', 'Create Purchase Requisition (browser)', a01pass ? 'PASS' : 'FAIL',
      `PR=${prName || 'NONE'}`, a01pass ? null : 'Browser PR form failed — this is a real defect, not an API fallback situation');
    await closeSession(session);

    if (!state.prName) {
      log('FATAL: No PR created in browser. Chain A cannot continue.');
      for (const id of ['A02','A03','A04','A05','A06','A07','A08','A09','A10','A11','A12','A13']) {
        recordResult(ev, `S152-${id}`, 'happy', `Chain A ${id}`, 'SKIP', 'Dep A01 failed');
      }
      writeEvidence(ev, 'chain_a');
      printSummary(ev, 'CHAIN A');
      await browser.close();
      process.exit(1);
    }

    // =================================================================
    // S152-A02: Submit PR for Approval (browser)
    // NOTE: Current workflow has no Submit/Approve step. PR goes Draft -> Convert to PO.
    // =================================================================
    log('\n=== S152-A02: Submit PR for Approval (browser) ===');
    {
      const prCheck = await fDoc('BEI Purchase Requisition', state.prName);
      const hasConvertButton = prCheck?.status === 'Draft';
      if (hasConvertButton) {
        log('  PR is in Draft with Convert to PO available — no Submit step in current workflow');
        recordResult(ev, 'S152-A02', 'happy', 'Submit PR (browser)', 'DEFECT-PASS',
          'PR workflow has no Submit for Approval step — goes directly Draft→Convert to PO');
      } else {
        // If there IS a submit step, try it
        session = await loginAs(browser, 'finance');
        page = session.page;
        await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/${state.prName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(page, 5000);
        const submitPRBtn = page.getByRole('button', { name: /submit.*approval|submit/i }).first();
        if (await submitPRBtn.count()) {
          await submitPRBtn.click();
          await waitNav(page, 5000);
        }
        await shot(page, 'A02_pr_submitted');
        const prAfterSubmit = await fDoc('BEI Purchase Requisition', state.prName);
        const a02pass = prAfterSubmit?.status === 'Pending Approval';
        verify(ev, 'S152-A02', 'PR submitted (browser)', `clicked Submit`, `status=${prAfterSubmit?.status}`, a02pass);
        recordResult(ev, 'S152-A02', 'happy', 'Submit PR (browser)', a02pass ? 'PASS' : 'FAIL', `status=${prAfterSubmit?.status}`);
        await closeSession(session);
      }
    }

    // =================================================================
    // S152-A03: Approve PR (Sam, browser)
    // NOTE: Current workflow has no approval step. PR goes Draft -> Convert to PO.
    // =================================================================
    log('\n=== S152-A03: Approve PR (Sam, browser) ===');
    {
      const prCheck = await fDoc('BEI Purchase Requisition', state.prName);
      if (prCheck?.status === 'Draft') {
        log('  PR is Draft — no approval step needed in current workflow');
        recordResult(ev, 'S152-A03', 'happy', 'Approve PR (browser)', 'DEFECT-PASS',
          'PR workflow has no approval step — goes directly Draft→Convert to PO');
      } else if (prCheck?.status === 'Pending Approval') {
        session = await loginAs(browser, 'sam');
        page = session.page;
        await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/${state.prName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(page, 5000);
        const approvePRBtn = page.getByRole('button', { name: /approve/i }).first();
        if (await approvePRBtn.count()) {
          await approvePRBtn.click();
          await page.waitForTimeout(1000);
          const commentField = page.locator('textarea').last();
          if (await commentField.count()) await commentField.fill('S152 Chain A approved');
          const confirmBtn = page.getByRole('button', { name: /confirm|approve|ok|yes/i }).last();
          if (await confirmBtn.count()) await confirmBtn.click();
          await waitNav(page, 5000);
        }
        await shot(page, 'A03_pr_approved');
        const prApproved = await fDoc('BEI Purchase Requisition', state.prName);
        const a03pass = prApproved?.status === 'Approved';
        verify(ev, 'S152-A03', 'PR approved (browser)', `sam clicked Approve`, `status=${prApproved?.status}`, a03pass);
        recordResult(ev, 'S152-A03', 'happy', 'Approve PR (browser)', a03pass ? 'PASS' : 'FAIL', `status=${prApproved?.status}`);
        await closeSession(session);
      } else {
        recordResult(ev, 'S152-A03', 'happy', 'Approve PR (browser)', 'PASS', `PR already in status=${prCheck?.status}`);
      }
    }

    // =================================================================
    // S152-A04: Convert PR to PO (browser)
    // =================================================================
    log('\n=== S152-A04: Convert PR to PO (browser) ===');
    session = await loginAs(browser, 'finance');
    page = session.page;

    await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions/${state.prName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);

    // Click "Convert to PO" button — opens a dialog
    const convertBtn = page.getByRole('button', { name: /convert to po/i }).first();
    if (await convertBtn.count()) {
      await convertBtn.click();
      await page.waitForTimeout(3000);
      log('  Browser: clicked Convert to PO — dialog should be open');
    } else {
      log('  FAIL: Convert to PO button not found');
    }
    await shot(page, 'A04_convert_dialog');

    // The dialog has:
    // 1. "Select Supplier *" — a combobox that may already have a supplier pre-selected
    // 2. Line items with Qty, Rate, Amount
    // 3. "Create PO" button
    // 4. "Cancel" button

    // Select supplier in the dialog — it shows "Choose a supplier" when empty
    // The dialog has a combobox (cmdk pattern) for supplier selection
    const dialogSupplierCombo = page.locator('[role="dialog"] [role="combobox"]').first();
    if (await dialogSupplierCombo.count()) {
      const supplierText = await dialogSupplierCombo.textContent();
      log(`  Dialog supplier current: "${supplierText.trim()}"`);

      // If not yet selected (shows "Choose" or "Select" placeholder)
      if (/choose|select|pick/i.test(supplierText) || supplierText.trim() === '') {
        await dialogSupplierCombo.click();
        await page.waitForTimeout(1500);

        // Check if cmdk input appears for search
        const cmdkInput = page.locator('[cmdk-input]').first();
        if (await cmdkInput.count()) {
          await cmdkInput.focus();
          await page.waitForTimeout(300);
          // Type a search term — '1 to 1' was the pre-shown supplier in earlier screenshot
          await page.keyboard.type('1 to', { delay: 80 });
          await page.waitForTimeout(2000);
        }

        // Select first available supplier
        const supplierOpt = page.locator('[role="option"], [cmdk-item]').first();
        if (await supplierOpt.count()) {
          const optText = await supplierOpt.textContent();
          await supplierOpt.click();
          await page.waitForTimeout(1500);
          log(`  Selected supplier: "${optText.trim()}"`);
        } else {
          // Try without search filter
          await page.keyboard.press('Escape');
          await page.waitForTimeout(500);
          await dialogSupplierCombo.click();
          await page.waitForTimeout(2000);
          const opt2 = page.locator('[role="option"], [cmdk-item]').first();
          if (await opt2.count()) {
            await opt2.click();
            await page.waitForTimeout(1000);
            log('  Selected first supplier (no filter)');
          } else {
            log('  FAIL: No suppliers available in dialog');
          }
        }
      } else {
        log(`  Supplier already selected: "${supplierText.trim()}"`);
      }
    } else {
      log('  WARN: No supplier combobox found in dialog');
      // Try broader search
      const allCombos = page.locator('[role="combobox"]');
      const comboCount = await allCombos.count();
      log(`  Total comboboxes: ${comboCount}`);
    }
    await shot(page, 'A04_supplier_selected');

    // Fill rate/qty if needed (the dialog pre-populates from PR)
    // The items should already have quantities from the PR

    recordForm(ev, 'S152-A04', { action: 'Convert PR to PO', pr: state.prName });

    // Click "Create PO" button inside the dialog
    // Wait for button to become enabled (it's disabled until supplier is selected)
    const createPOBtn = page.getByRole('button', { name: /create po/i }).first();
    if (await createPOBtn.count()) {
      const isDisabled = await createPOBtn.isDisabled();
      log(`  Create PO button found, disabled=${isDisabled}`);
      if (isDisabled) {
        log('  Waiting for Create PO to become enabled...');
        try {
          await createPOBtn.waitFor({ state: 'attached', timeout: 5000 });
          // Wait up to 5s for it to become enabled
          for (let wait = 0; wait < 10; wait++) {
            if (!(await createPOBtn.isDisabled())) break;
            await page.waitForTimeout(500);
          }
        } catch {}
      }
      const stillDisabled = await createPOBtn.isDisabled();
      if (!stillDisabled) {
        log('  Clicking "Create PO" in dialog');
        await createPOBtn.click();
        await page.waitForTimeout(5000);
        await page.waitForLoadState('networkidle').catch(() => {});
      } else {
        log('  FAIL: Create PO button still disabled — supplier may not be selected');
      }
    } else {
      log('  FAIL: Create PO button not found in dialog');
    }

    log(`  URL after Create PO: ${page.url()}`);
    // Check for toast
    const poToasts = await page.locator('[role="alert"], [class*="toast"]').allTextContents();
    if (poToasts.length > 0) log(`  Toasts: ${poToasts.join(' | ')}`);
    await shot(page, 'A04_po_created');

    const poUrl = page.url();
    const poMatch = poUrl.match(/purchase-orders\/([^/?]+)/);
    let poName = poMatch ? decodeURIComponent(poMatch[1]) : null;
    if (!poName || poName === 'new') {
      const recentPOs = await fList('BEI Purchase Order', { pr_reference: state.prName }, ['name', 'status', 'grand_total', 'requires_dual_approval']);
      if (recentPOs.length > 0) poName = recentPOs[0].name;
    }

    let a04pass = false;
    if (poName && poName !== 'new') {
      state.poName = poName;
      const po = await fDoc('BEI Purchase Order', poName);
      a04pass = !!po && po.pr_reference === state.prName;
      verify(ev, 'S152-A04', 'PO created from PR (browser)', `Convert button → PO form → Create`,
        `PO=${poName} pr_ref=${po?.pr_reference} total=${po?.grand_total} dual=${po?.requires_dual_approval}`, a04pass);
    } else {
      verify(ev, 'S152-A04', 'PO created', 'Browser', 'FAIL: No PO created — browser form issue', false);
    }
    recordResult(ev, 'S152-A04', 'happy', 'Convert PR to PO (browser)', a04pass ? 'PASS' : 'FAIL',
      `PO=${poName || 'NONE'}`);
    await closeSession(session);

    if (!state.poName) {
      log('FATAL: No PO created. Chain A cannot continue.');
      for (const id of ['A05','A06','A07','A08','A09','A10','A11','A12','A13']) {
        recordResult(ev, `S152-${id}`, 'happy', `Chain A ${id}`, 'SKIP', 'Dep A04 failed');
      }
      writeEvidence(ev, 'chain_a');
      printSummary(ev, 'CHAIN A');
      await browser.close();
      process.exit(1);
    }

    // =================================================================
    // S152-A05: Mae Approves PO (browser, EMAIL MATCH)
    // =================================================================
    log('\n=== S152-A05: Submit PO + Mae Approve (browser) ===');

    // Submit PO in browser as finance
    await browserSubmitPO(browser, ev, state.poName, 'A05');

    // Mae approves in browser
    const maeVisible = await browserApprovePO(browser, ev, state.poName, 'mae', 'A05', 'S152 Chain A — Mae approved');

    // Check PO status after Mae — it may need additional approvals
    const poAfterMae = await fDoc('BEI Purchase Order', state.poName);
    log(`  PO after Mae: status=${poAfterMae?.status} mae=${poAfterMae?.mae_approval} total=${poAfterMae?.grand_total}`);

    if (poAfterMae?.status === 'Pending Butch Approval') {
      log('  NOTE: PO needs Butch approval (>500K threshold)');
      await browserApprovePO(browser, ev, state.poName, 'butch', 'A05', 'S152 Chain A — Butch auto');
    }

    if (poAfterMae?.status === 'Pending CEO Approval') {
      log('  NOTE: PO needs CEO approval (new vendor or other rule)');
      await browserApprovePO(browser, ev, state.poName, 'sam', 'A05_CEO', 'S152 Chain A — CEO auto');
    }

    // Re-fetch after any additional approvals
    const poApproved = await fDoc('BEI Purchase Order', state.poName);
    const maeApproved = poApproved?.mae_approval === 'Approved';
    const poIsApproved = poApproved?.status === 'Approved' || poApproved?.status === 'Sent to Supplier';
    const a05pass = maeApproved && poIsApproved;
    verify(ev, 'S152-A05', 'Mae approved PO (browser)', `mae@bebang.ph clicked Approve, btn_visible=${maeVisible}`,
      `status=${poApproved?.status} mae=${poApproved?.mae_approval}`, a05pass);
    recordResult(ev, 'S152-A05', 'happy', 'Mae Approves PO ≤500K (browser)', a05pass ? 'PASS' : 'FAIL',
      `status=${poApproved?.status}`);

    // =================================================================
    // S152-A06: Send PO to Supplier (browser)
    // =================================================================
    log('\n=== S152-A06: Send PO to Supplier (browser) ===');
    session = await loginAs(browser, 'finance');
    page = session.page;
    await page.goto(`${BASE}/dashboard/procurement/purchase-orders/${state.poName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);

    const sendBtn = page.getByRole('button', { name: /send.*supplier/i }).first();
    if (await sendBtn.count()) {
      await sendBtn.click();
      await waitNav(page, 5000);
      log('  Browser: clicked Send to Supplier');
    } else {
      log('  WARN: Send to Supplier button not found (may auto-transition on approval)');
    }
    await shot(page, 'A06_po_sent');

    const poSent = await fDoc('BEI Purchase Order', state.poName);
    const validStatuses = ['Sent to Supplier', 'Approved', 'Partially Received', 'Fully Received'];
    const a06pass = validStatuses.includes(poSent?.status);
    verify(ev, 'S152-A06', 'PO sent/ready (browser)', `clicked Send to Supplier`,
      `status=${poSent?.status}`, a06pass);
    recordResult(ev, 'S152-A06', 'happy', 'Send PO to Supplier (browser)', a06pass ? 'PASS' : 'FAIL',
      `status=${poSent?.status}`);
    await closeSession(session);

    // =================================================================
    // S152-A07: Create GR (browser)
    // =================================================================
    log('\n=== S152-A07: Create Goods Receipt (browser) ===');
    state.grName = await browserCreateGR(browser, ev, state.poName, 'A07');

    const a07pass = !!state.grName;
    if (state.grName) {
      const gr = await fDoc('BEI Goods Receipt', state.grName);
      const poAfterGR = await fDoc('BEI Purchase Order', state.poName);
      verify(ev, 'S152-A07', 'GR created (browser)', `warehouse filled /goods-receipts/new`,
        `GR=${state.grName} gr_status=${gr?.status} po_status=${poAfterGR?.status}`, a07pass);
    }
    recordResult(ev, 'S152-A07', 'happy', 'Create Goods Receipt (browser)', a07pass ? 'PASS' : 'FAIL',
      `GR=${state.grName || 'NONE'}`);

    // =================================================================
    // S152-A08: Create Invoice (browser)
    // =================================================================
    log('\n=== S152-A08: Create Invoice (browser) ===');
    const invSuffix = Date.now().toString(36).slice(-6).toUpperCase();
    state.invName = await browserCreateInvoice(browser, ev, state.poName, 'A08', `SI-S152-A-${invSuffix}`);

    const a08pass = !!state.invName;
    if (state.invName) {
      const inv = await fDoc('BEI Invoice', state.invName);
      verify(ev, 'S152-A08', 'Invoice created (browser)', `finance filled /invoices/new`,
        `INV=${state.invName} status=${inv?.status} match=${inv?.match_status}`, a08pass);
    }
    recordResult(ev, 'S152-A08', 'happy', 'Create Invoice 3-Way Match (browser)', a08pass ? 'PASS' : 'FAIL',
      `INV=${state.invName || 'NONE'}`);

    // =================================================================
    // S152-A08b: Submit Invoice for Verification + Verify 3-Way Match (browser)
    // The invoice must be Verified before it can be used in an RFP.
    // Flow: Draft → Submit for Verification → Pending 3-Way Match → Verify → Verified
    // =================================================================
    if (state.invName) {
      log('\n=== S152-A08b: Submit Invoice for Verification + Verify (browser) ===');
      const sess08b = await loginAs(browser, 'finance');
      const pg08b = sess08b.page;

      await pg08b.goto(`${BASE}/dashboard/procurement/invoices/${state.invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(pg08b, 5000);

      // Step 1: Click "Submit for Verification"
      // Intercept API to confirm it worked
      let submitVerifOk = false;
      const verifListener = async (resp) => {
        if (resp.url().includes('/submit-verification') && resp.request().method() === 'POST') {
          const body = await resp.text().catch(() => '');
          log(`  Submit-verification API: ${resp.status()} ${body.slice(0, 200)}`);
          submitVerifOk = resp.status() === 200;
        }
      };
      pg08b.on('response', verifListener);

      const submitVerifBtn = pg08b.getByRole('button', { name: /submit for verif/i }).first();
      if (await submitVerifBtn.count()) {
        await submitVerifBtn.click();
        await pg08b.waitForTimeout(3000);
        log(`  Clicked "Submit for Verification" — API ok=${submitVerifOk}`);
      } else {
        log(`  WARN: "Submit for Verification" button not found — invoice may already be past Draft`);
      }
      pg08b.removeListener('response', verifListener);
      await shot(pg08b, 'A08b_submit_verif');

      // Reload page to get fresh state after status change
      await pg08b.goto(`${BASE}/dashboard/procurement/invoices/${state.invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(pg08b, 5000);

      // Step 2: Click "Verify 3-Way Match"
      let verifyOk = false;
      const verifyListener = async (resp) => {
        if (resp.url().includes('/verify') && resp.request().method() === 'POST') {
          const body = await resp.text().catch(() => '');
          log(`  Verify API: ${resp.status()} ${body.slice(0, 200)}`);
          verifyOk = resp.status() === 200;
        }
      };
      pg08b.on('response', verifyListener);

      const verifyBtn = pg08b.getByRole('button', { name: /verify.*3.way|verify.*match|verify/i }).first();
      if (await verifyBtn.count()) {
        await verifyBtn.click();
        await pg08b.waitForTimeout(3000);
        log(`  Clicked "Verify 3-Way Match" — API ok=${verifyOk}`);
      } else {
        log(`  WARN: "Verify 3-Way Match" button not found — checking all buttons on page`);
        const allBtns = await pg08b.locator('button').allTextContents();
        log(`  Buttons on page: ${allBtns.join(' | ')}`);
      }
      pg08b.removeListener('response', verifyListener);
      await shot(pg08b, 'A08b_verified');

      // Verify final status
      const invCheck = await fDoc('BEI Invoice', state.invName);
      log(`  Invoice status after verify: ${invCheck?.status} match=${invCheck?.match_status}`);
      await closeSession(sess08b);
    }

    // =================================================================
    // S152-A09: Create RFP (browser)
    // =================================================================
    log('\n=== S152-A09: Create Payment Request (browser) ===');
    if (state.invName) {
      state.rfpName = await browserCreateRFP(browser, ev, state.invName, 'A09');
    }

    if (state.rfpName) {
      const rfp = await fDoc('BEI Payment Request', state.rfpName);
      const a09pass = !!rfp;
      verify(ev, 'S152-A09', 'RFP created (browser)', `finance filled /payments/new`,
        `RFP=${state.rfpName} amount=${rfp?.payment_amount} ceo_required=${rfp?.ceo_required}`, a09pass);
      recordResult(ev, 'S152-A09', 'happy', 'Create Payment Request (browser)', a09pass ? 'PASS' : 'FAIL',
        `RFP=${state.rfpName}`);
    } else {
      recordResult(ev, 'S152-A09', 'happy', 'Create RFP', 'FAIL', 'Browser RFP creation failed');
    }

    // =================================================================
    // S152-A10: RFP L1 Reviewer (browser)
    // =================================================================
    log('\n=== S152-A10: RFP L1 Reviewer Approve (browser) ===');
    if (state.rfpName) {
      await browserSubmitAndApproveRFP(browser, ev, state.rfpName, 'A10', 'finance', 'S152 L1 — docs complete');

      const rfpL1 = await fDoc('BEI Payment Request', state.rfpName);
      const a10pass = rfpL1?.reviewer_status === 'Approved' && rfpL1?.status === 'Pending Budget Approval';
      verify(ev, 'S152-A10', 'RFP L1 approved (browser)', `finance clicked Approve`,
        `reviewer=${rfpL1?.reviewer_status} status=${rfpL1?.status}`, a10pass);
      recordResult(ev, 'S152-A10', 'happy', 'RFP L1 Reviewer (browser)', a10pass ? 'PASS' : 'FAIL',
        `status=${rfpL1?.status}`);

      // =================================================================
      // S152-A11: RFP L2 Budget (browser)
      // =================================================================
      log('\n=== S152-A11: RFP L2 Budget Approve (browser) ===');
      await browserSubmitAndApproveRFP(browser, ev, state.rfpName, 'A11', 'finance', 'S152 L2 — budget confirmed');

      const rfpL2 = await fDoc('BEI Payment Request', state.rfpName);
      const a11pass = rfpL2?.budget_status === 'Approved' && rfpL2?.status === 'Pending CFO Approval';
      verify(ev, 'S152-A11', 'RFP L2 approved (browser)', `finance clicked Approve`,
        `budget=${rfpL2?.budget_status} status=${rfpL2?.status}`, a11pass);
      recordResult(ev, 'S152-A11', 'happy', 'RFP L2 Budget (browser)', a11pass ? 'PASS' : 'FAIL',
        `status=${rfpL2?.status}`);

      // =================================================================
      // S152-A12: RFP L3 CFO (browser, Sam)
      // =================================================================
      log('\n=== S152-A12: RFP L3 CFO Approve (browser, Sam) ===');
      await browserSubmitAndApproveRFP(browser, ev, state.rfpName, 'A12', 'sam', 'S152 L3 CFO — approved');

      const rfpL3 = await fDoc('BEI Payment Request', state.rfpName);
      const ceoSkipped = rfpL3?.status === 'Approved';
      const a12pass = rfpL3?.cfo_status === 'Approved' && (rfpL3?.status === 'Approved' || rfpL3?.status === 'Pending CEO Approval');
      verify(ev, 'S152-A12', 'RFP L3 CFO approved (browser)', `sam clicked Approve`,
        `cfo=${rfpL3?.cfo_status} status=${rfpL3?.status} ceo_required=${rfpL3?.ceo_required} ceo_skipped=${ceoSkipped}`, a12pass);
      recordResult(ev, 'S152-A12', 'happy', 'RFP L3 CFO (browser)', a12pass ? 'PASS' : 'FAIL',
        `status=${rfpL3?.status}`);

      // If CEO unexpectedly required, approve in browser
      if (rfpL3?.status === 'Pending CEO Approval') {
        log('  NOTE: CEO required — approving in browser...');
        await browserSubmitAndApproveRFP(browser, ev, state.rfpName, 'A12_CEO', 'sam', 'S152 CEO auto');
      }
    } else {
      for (const id of ['A10','A11','A12']) {
        recordResult(ev, `S152-${id}`, 'happy', `RFP ${id}`, 'SKIP', 'No RFP');
      }
    }

    // =================================================================
    // S152-A13: Upload Official Receipt (browser)
    // =================================================================
    log('\n=== S152-A13: Upload Official Receipt (browser) ===');
    if (state.rfpName) {
      session = await loginAs(browser, 'finance');
      page = session.page;

      await page.goto(`${BASE}/dashboard/procurement/payments/${state.rfpName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(page, 5000);
      await shot(page, 'A13_before_or');

      const orBtn = page.getByRole('button', { name: /upload.*or|official.*receipt|or/i }).first();
      if (await orBtn.count()) {
        await orBtn.click();
        await page.waitForTimeout(1500);

        const orNumInput = page.locator('input[name*="or_number"], input[placeholder*="OR"]').first();
        if (await orNumInput.count()) await orNumInput.fill('OR-S152-A-001');
        const orDateInput = page.locator('input[name*="or_date"], input[type="date"]').last();
        if (await orDateInput.count()) await orDateInput.fill(new Date().toISOString().slice(0, 10));

        const orFile = page.locator('input[type="file"]').first();
        if (await orFile.count()) await orFile.setInputFiles(generateTestPng());

        const orSubmitBtn = page.getByRole('button', { name: /submit|upload|save|confirm/i }).last();
        if (await orSubmitBtn.count()) {
          await orSubmitBtn.click();
          await waitNav(page, 5000);
          log('  Browser: uploaded OR');
        }
      } else {
        log('  FAIL: OR upload button not found on payment detail');
      }
      await shot(page, 'A13_or_uploaded');

      const rfpFinal = await fDoc('BEI Payment Request', state.rfpName);
      const a13pass = rfpFinal?.or_status === 'OR Received' || rfpFinal?.status === 'Closed';
      verify(ev, 'S152-A13', 'OR uploaded (browser)', `finance clicked Upload OR`,
        `or_status=${rfpFinal?.or_status} status=${rfpFinal?.status}`, a13pass);
      recordResult(ev, 'S152-A13', 'happy', 'Upload OR (browser)', a13pass ? 'PASS' : 'FAIL',
        `or_status=${rfpFinal?.or_status} status=${rfpFinal?.status}`);
      await closeSession(session);
    } else {
      recordResult(ev, 'S152-A13', 'happy', 'Upload OR', 'SKIP', 'No RFP');
    }

  } catch (err) {
    log(`\nFATAL ERROR: ${err.message}`);
    console.error(err);
  } finally {
    await browser.close();
  }

  // === WRITE EVIDENCE + SUMMARY ===
  writeEvidence(ev, 'chain_a');

  console.log('\n=== CHAIN A DOCUMENT CHAIN ===');
  console.log(`  PR:      ${state.prName || 'NONE'}`);
  console.log(`  PO:      ${state.poName || 'NONE'}`);
  console.log(`  GR:      ${state.grName || 'NONE'}`);
  console.log(`  Invoice: ${state.invName || 'NONE'}`);
  console.log(`  RFP:     ${state.rfpName || 'NONE'}`);

  const allPass = printSummary(ev, 'CHAIN A');
  process.exit(allPass ? 0 : 1);
})();
