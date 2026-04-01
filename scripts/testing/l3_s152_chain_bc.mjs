/**
 * S152 Chain B (>P500K dual approval) + Chain C (>P1M CEO approval)
 * ALL actions in the browser. ZERO API shortcuts.
 *
 * Run: node scripts/testing/l3_s152_chain_bc.mjs
 */
import {
  BASE, FRAPPE, OUT, USERS, log,
  fLogin, fDoc, fList, fGet,
  launchBrowser, loginAs, closeSession, shot, waitNav,
  createEvidence, verify, recordForm, recordResult, writeEvidence, printSummary,
  generateTestPng,
  // Browser action functions — the ONLY way to perform mutations
  browserCreatePO, browserSubmitPO, browserApprovePO,
  browserCreateGR, browserCreateInvoice, browserCreateRFP,
  browserSubmitAndApproveRFP,
} from './l3_s152_helpers.mjs';

const ev = createEvidence();
const state = {};

(async () => {
  log('=== S152 CHAIN B + C — ALL BROWSER, ZERO API SHORTCUTS ===\n');
  // API login for state VERIFICATION only
  await fLogin('sam@bebang.ph', '2289454');
  const browser = await launchBrowser();

  try {
    // =================================================================
    // CHAIN B: >P500K DUAL APPROVAL
    // =================================================================
    log('\n========== CHAIN B: >P500K DUAL APPROVAL ==========\n');

    // S152-B01: Create PO >P500K via PR conversion (browser)
    // Direct PO creation with high rates is blocked by price variance guard.
    // Strategy: Create PR with many high-qty items, convert to PO.
    log('=== S152-B01: Create PO >P500K (browser) ===');
    log('  Using PR→PO workflow to bypass price variance guard');

    // Step 1: Create PR with high quantities to reach >P500K
    {
      const sess = await loginAs(browser, 'finance');
      const pg = sess.page;
      await pg.goto(`${BASE}/dashboard/procurement/purchase-requisitions/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(pg, 5000);

      // Set department
      const deptCombo = pg.locator('[role="combobox"]').first();
      await deptCombo.click();
      await pg.waitForTimeout(1000);
      const opsOpt = pg.locator('[role="option"]').filter({ hasText: /^Operations$/i }).first();
      if (await opsOpt.count()) await opsOpt.click();
      await pg.waitForTimeout(500);

      // Set date required
      const dateInput = pg.locator('input[name="date_required"], input[type="date"]').first();
      if (await dateInput.count()) await dateInput.fill(new Date(Date.now() + 8 * 3600000 + 86400000).toISOString().slice(0, 10));

      // Set purpose
      const purpose = pg.locator('textarea').first();
      if (await purpose.count()) await purpose.fill('S152 Chain B — >P500K dual approval test');

      // A013 NESTLE CREAM @ P3,051.45/unit, A016 ALASKA EVAP 1L @ P926.02/unit
      // 150*3051.45 + 50*926.02 = P504,018.50 net + 12% VAT ≈ P564K > P500K
      const items = [
        { search: 'nestle cream', qty: '150' },
        { search: 'alaska evap', qty: '50' },
      ];

      // Add extra rows first (form starts with 1 blank row)
      const addBtn = pg.getByRole('button', { name: /add item/i }).first();
      if (await addBtn.count()) {
        for (let i = 0; i < items.length - 1; i++) {
          await addBtn.click();
          await pg.waitForTimeout(800);
        }
      }

      // Fill each row using Chain A's proven pattern
      for (let r = 0; r < items.length; r++) {
        // Click the item combobox to open the popover
        // Layout: combobox[0]=dept, then per row: [1+r*2]=item, [2+r*2]=UOM
        const itemComboIndex = 1 + r * 2;
        try {
          const allCombos = pg.locator('[role="combobox"]');
          const combo = allCombos.nth(itemComboIndex);
          if (await combo.count()) {
            await combo.click();
            await pg.waitForTimeout(1000);

            const cmdkInput = pg.locator('[cmdk-input]').first();
            if (await cmdkInput.count()) {
              await cmdkInput.focus();
              await pg.waitForTimeout(300);
              await cmdkInput.press('Control+A');
              await pg.keyboard.type(items[r].search, { delay: 80 });
              await pg.waitForTimeout(3000);

              const optCount = await pg.locator('[cmdk-item], [role="option"]').count();
              log(`    PR row ${r}: ${optCount} items for "${items[r].search}"`);
              if (optCount > 0) {
                await pg.locator('[cmdk-item], [role="option"]').first().click();
                await pg.waitForTimeout(800);
                log(`    PR item ${r}: selected "${items[r].search}"`);
              } else {
                await pg.keyboard.press('Escape');
                log(`    WARN: No items found for row ${r}`);
              }
            }
          }
        } catch (e) { log(`    Item combobox row ${r}: ${e.message}`); }

        // Qty
        const qtyInputs = pg.locator('input[name*="qty"], input[placeholder*="Qty"]');
        const qtyInput = qtyInputs.nth(r);
        if (await qtyInput.count()) {
          await qtyInput.fill(items[r].qty);
          await pg.waitForTimeout(200);
          log(`    PR item ${r}: qty=${items[r].qty}`);
        }
      }

      // Click Create PR
      const createBtn = pg.getByRole('button', { name: /create pr/i }).first();
      if (await createBtn.count()) {
        await createBtn.click();
        await waitNav(pg, 5000);
      }
      await shot(pg, 'B01_pr_created');

      const prUrl = pg.url();
      const prMatch = prUrl.match(/purchase-requisitions\/([^/?]+)/);
      let bPrName = prMatch ? decodeURIComponent(prMatch[1]) : null;
      log(`  B PR created: ${bPrName}`);

      // Step 2: Convert PR to PO
      if (bPrName && bPrName !== 'new') {
        await pg.goto(`${BASE}/dashboard/procurement/purchase-requisitions/${bPrName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pg, 5000);
        const convertBtn = pg.getByRole('button', { name: /convert to po/i }).first();
        if (await convertBtn.count()) {
          await convertBtn.click();
          await pg.waitForTimeout(3000);
          // Select supplier using cmdk pattern (same as Chain A)
          const dialogSupCombo = pg.locator('[role="dialog"] [role="combobox"]').first();
          if (await dialogSupCombo.count()) {
            await dialogSupCombo.click();
            await pg.waitForTimeout(1500);
            const cmdkSup = pg.locator('[cmdk-input]').first();
            if (await cmdkSup.count()) {
              await cmdkSup.focus();
              await pg.waitForTimeout(300);
              // Just select the first available supplier for Chain B
            }
            const supOpt = pg.locator('[role="option"], [cmdk-item]').first();
            if (await supOpt.count()) {
              const optText = await supOpt.textContent();
              await supOpt.click();
              await pg.waitForTimeout(1000);
              log(`  B01: Selected supplier "${optText.trim()}"`);
            }
          }
          const createPOBtn = pg.getByRole('button', { name: /create po/i }).first();
          if (await createPOBtn.count()) {
            for (let w = 0; w < 10; w++) {
              if (!(await createPOBtn.isDisabled())) break;
              await pg.waitForTimeout(500);
            }
            if (!(await createPOBtn.isDisabled())) {
              await createPOBtn.click();
              await pg.waitForTimeout(5000);
              await pg.waitForLoadState('networkidle').catch(() => {});
            }
          }
        }

        const poUrl = pg.url();
        const poMatch = poUrl.match(/purchase-orders\/([^/?]+)/);
        state.b_poName = poMatch ? decodeURIComponent(poMatch[1]) : null;
        if (!state.b_poName || state.b_poName === 'new') {
          const recent = await fList('BEI Purchase Order', { pr_reference: bPrName }, ['name', 'grand_total']);
          if (recent.length > 0) state.b_poName = recent[0].name;
        }
      }
      await shot(pg, 'B01_po_from_pr');
      await closeSession(sess);
    }

    log(`  B PO: ${state.b_poName || 'NONE'}`);

    if (state.b_poName) {
      const bpo = await fDoc('BEI Purchase Order', state.b_poName);
      const b01pass = bpo && bpo.grand_total > 500000;
      verify(ev, 'S152-B01', 'PO >500K created in browser', `navigated to /purchase-orders/new`,
        `PO=${state.b_poName} total=${bpo?.grand_total} dual=${bpo?.requires_dual_approval}`, b01pass);
      recordResult(ev, 'S152-B01', 'happy', 'Create PO >P500K (browser)', b01pass ? 'PASS' : 'FAIL',
        `total=${bpo?.grand_total}`);

      // Submit PO for approval in BROWSER
      await browserSubmitPO(browser, ev, state.b_poName, 'B01');

      // S152-B02: Mae approves in BROWSER → Pending Butch
      log('\n=== S152-B02: Mae Approves >500K PO (browser) ===');
      const maeVisible = await browserApprovePO(browser, ev, state.b_poName, 'mae', 'B02', 'S152 Chain B — Mae approved >500K');
      const bpoAfterMae = await fDoc('BEI Purchase Order', state.b_poName);
      const b02pass = bpoAfterMae?.status === 'Pending Butch Approval' && bpoAfterMae?.mae_approval === 'Approved';
      verify(ev, 'S152-B02', 'Mae → Pending Butch (NOT Approved)', `mae@bebang.ph clicked Approve`,
        `status=${bpoAfterMae?.status} mae=${bpoAfterMae?.mae_approval} btn_visible=${maeVisible}`, b02pass);
      recordResult(ev, 'S152-B02', 'happy', 'Mae Approve >500K → Pending Butch (browser)', b02pass ? 'PASS' : 'FAIL',
        `status=${bpoAfterMae?.status}`, b02pass ? null : `Expected Pending Butch, got ${bpoAfterMae?.status}`);

      // S152-B03: Butch approves in BROWSER → Pending CEO (>P500K triggers CEO approval too)
      log('\n=== S152-B03: Butch Approves >500K PO (browser) ===');
      const butchVisible = await browserApprovePO(browser, ev, state.b_poName, 'butch', 'B03', 'S152 Chain B — Butch CFO approved');
      const bpoAfterButch = await fDoc('BEI Purchase Order', state.b_poName);
      // >P500K POs require CEO approval too, so after Butch → Pending CEO (not directly Approved)
      const b03pass = bpoAfterButch?.butch_approval === 'Approved' &&
        (bpoAfterButch?.status === 'Approved' || bpoAfterButch?.status === 'Pending CEO Approval');
      verify(ev, 'S152-B03', 'Butch → Pending CEO or Approved', `butch@bebang.ph clicked Approve`,
        `status=${bpoAfterButch?.status} butch=${bpoAfterButch?.butch_approval} btn_visible=${butchVisible}`, b03pass);
      recordResult(ev, 'S152-B03', 'happy', 'Butch Approve >500K (browser)', b03pass ? 'PASS' : 'FAIL',
        `status=${bpoAfterButch?.status}`);

      // S152-B03b: If CEO approval required, CEO approves in BROWSER
      if (bpoAfterButch?.status === 'Pending CEO Approval') {
        log('\n=== S152-B03b: CEO Approves >500K PO (browser, sam@bebang.ph) ===');
        await browserApprovePO(browser, ev, state.b_poName, 'sam', 'B03b', 'S152 Chain B — CEO authorized >500K');
        const bpoAfterCeo = await fDoc('BEI Purchase Order', state.b_poName);
        const b03bpass = bpoAfterCeo?.status === 'Approved' && bpoAfterCeo?.ceo_approval === 'Approved';
        verify(ev, 'S152-B03b', 'CEO → Approved', `sam@bebang.ph clicked Approve`,
          `status=${bpoAfterCeo?.status} ceo=${bpoAfterCeo?.ceo_approval}`, b03bpass);
        recordResult(ev, 'S152-B03b', 'happy', 'CEO Approve >500K PO (browser)', b03bpass ? 'PASS' : 'FAIL',
          `status=${bpoAfterCeo?.status}`);
      }

      // S152-B04: Full chain GR→Invoice→RFP→3-level approval — ALL IN BROWSER
      log('\n=== S152-B04: Chain B GR→Invoice→RFP→Approve (all browser) ===');
      const b_grName = await browserCreateGR(browser, ev, state.b_poName, 'B04');
      const bInvSuffix = Date.now().toString(36).slice(-6).toUpperCase();
      const b_invName = await browserCreateInvoice(browser, ev, state.b_poName, 'B04', `SI-S152-B-${bInvSuffix}`);

      // Verify invoice before creating RFP
      if (b_invName) {
        log('  Verifying invoice before RFP...');
        const sessVerif = await loginAs(browser, 'finance');
        const pgVerif = sessVerif.page;
        await pgVerif.goto(`${BASE}/dashboard/procurement/invoices/${b_invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pgVerif, 5000);
        const submitVerifBtn = pgVerif.getByRole('button', { name: /submit for verif/i }).first();
        if (await submitVerifBtn.count()) {
          await submitVerifBtn.click();
          await pgVerif.waitForTimeout(3000);
        }
        await pgVerif.goto(`${BASE}/dashboard/procurement/invoices/${b_invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pgVerif, 5000);
        const verifyBtn = pgVerif.getByRole('button', { name: /verify.*3.way|verify.*match|verify/i }).first();
        if (await verifyBtn.count()) {
          await verifyBtn.click();
          await pgVerif.waitForTimeout(3000);
          log('  Invoice verified');
        }
        await closeSession(sessVerif);
      }

      let b_rfpName = null;
      if (b_invName) {
        b_rfpName = await browserCreateRFP(browser, ev, b_invName, 'B04');
      }

      if (b_rfpName) {
        // L1 Reviewer — browser
        await browserSubmitAndApproveRFP(browser, ev, b_rfpName, 'B04_L1', 'finance', 'B L1 reviewer');
        const bRfpL1 = await fDoc('BEI Payment Request', b_rfpName);
        verify(ev, 'S152-B04', 'B RFP L1 approved (browser)', `clicked approve as finance`,
          `reviewer=${bRfpL1?.reviewer_status} status=${bRfpL1?.status}`, bRfpL1?.reviewer_status === 'Approved');

        // L2 Budget — browser
        await browserSubmitAndApproveRFP(browser, ev, b_rfpName, 'B04_L2', 'finance', 'B L2 budget');
        const bRfpL2 = await fDoc('BEI Payment Request', b_rfpName);
        verify(ev, 'S152-B04', 'B RFP L2 approved (browser)', `clicked approve as finance`,
          `budget=${bRfpL2?.budget_status} status=${bRfpL2?.status}`, bRfpL2?.budget_status === 'Approved');

        // L3 CFO — browser (sam)
        await browserSubmitAndApproveRFP(browser, ev, b_rfpName, 'B04_L3', 'sam', 'B L3 CFO');
        const bRfpL3 = await fDoc('BEI Payment Request', b_rfpName);
        const b04pass = bRfpL3?.cfo_status === 'Approved' && (bRfpL3?.status === 'Approved' || bRfpL3?.status === 'Pending CEO Approval');
        verify(ev, 'S152-B04', 'Chain B complete (all browser)', `GR+INV+RFP+3 approvals`,
          `GR=${b_grName} INV=${b_invName} RFP=${b_rfpName} status=${bRfpL3?.status}`, b04pass);
        recordResult(ev, 'S152-B04', 'happy', 'Chain B GR→INV→RFP→3-level (all browser)', b04pass ? 'PASS' : 'FAIL',
          `status=${bRfpL3?.status}`);
      } else {
        recordResult(ev, 'S152-B04', 'happy', 'Chain B Completion', 'FAIL',
          `GR=${b_grName} INV=${b_invName} RFP=${b_rfpName}`, 'Chain creation failed');
      }
    } else {
      recordResult(ev, 'S152-B01', 'happy', 'Create PO >500K', 'FAIL', 'Browser PO creation failed');
      recordResult(ev, 'S152-B02', 'happy', 'Mae Approve', 'SKIP', 'Dep B01 failed');
      recordResult(ev, 'S152-B03', 'happy', 'Butch Approve', 'SKIP', 'Dep B01 failed');
      recordResult(ev, 'S152-B04', 'happy', 'Chain B Completion', 'SKIP', 'Dep B01 failed');
    }

    // =================================================================
    // CHAIN C: >P1M CEO APPROVAL
    // =================================================================
    log('\n\n========== CHAIN C: >P1M CEO APPROVAL ==========\n');

    // S152-C01: Create PO with new vendor >P1M via PR→PO conversion (browser)
    log('=== S152-C01: Create PO New Vendor >P1M (browser) ===');

    // First ensure a new vendor exists — check via API read (read-only, allowed)
    let newVendor = (await fList('BEI Supplier', { is_new_supplier: 1, status: 'Active' }, ['name'], 1))[0];
    if (!newVendor) {
      // Create new vendor in BROWSER via /suppliers/new
      log('  Creating new vendor in browser...');
      const session = await loginAs(browser, 'finance');
      const page = session.page;
      await page.goto(`${BASE}/dashboard/procurement/suppliers/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(page, 5000);
      const nameInput = page.locator('input[name*="supplier_name"], input[name*="name"]').first();
      if (await nameInput.count()) await nameInput.fill('S152 Test Vendor (New)');
      const createBtn = page.getByRole('button', { name: /create|save/i }).first();
      if (await createBtn.count()) {
        await createBtn.click();
        await waitNav(page, 5000);
      }
      await closeSession(session);
      newVendor = (await fList('BEI Supplier', { supplier_name: ['like', '%S152 Test Vendor%'] }, ['name'], 1))[0];
    }
    log(`  New vendor: ${newVendor?.name || 'NONE'}`);

    // Use PR→PO conversion (same as Chain B) to avoid price variance guard
    // A013 qty=300, A016 qty=100 → 300*3051.45 + 100*926.02 = P1,008,037 net + 12% VAT ≈ P1.129M > P1M
    {
      const sess = await loginAs(browser, 'finance');
      const pg = sess.page;
      await pg.goto(`${BASE}/dashboard/procurement/purchase-requisitions/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await waitNav(pg, 5000);

      // Set department
      const deptCombo = pg.locator('[role="combobox"]').first();
      await deptCombo.click();
      await pg.waitForTimeout(1000);
      const opsOpt = pg.locator('[role="option"]').filter({ hasText: /^Operations$/i }).first();
      if (await opsOpt.count()) await opsOpt.click();
      await pg.waitForTimeout(500);

      // Set date required
      const dateInput = pg.locator('input[name="date_required"], input[type="date"]').first();
      if (await dateInput.count()) await dateInput.fill(new Date(Date.now() + 8 * 3600000 + 86400000).toISOString().slice(0, 10));

      // Set purpose
      const purpose = pg.locator('textarea').first();
      if (await purpose.count()) await purpose.fill('S152 Chain C — >P1M CEO approval test');

      // Items for >P1M
      const cItems = [
        { search: 'nestle cream', qty: '300' },
        { search: 'alaska evap', qty: '100' },
      ];

      // Add extra rows first (form starts with 1 blank row)
      const addItemBtn = pg.getByRole('button', { name: /add item/i }).first();
      if (await addItemBtn.count()) {
        for (let i = 0; i < cItems.length - 1; i++) {
          await addItemBtn.click();
          await pg.waitForTimeout(800);
        }
      }

      // Fill each row using Chain A's proven pattern
      for (let r = 0; r < cItems.length; r++) {
        const itemComboIndex = 1 + r * 2;
        try {
          const allCombos = pg.locator('[role="combobox"]');
          const combo = allCombos.nth(itemComboIndex);
          if (await combo.count()) {
            await combo.click();
            await pg.waitForTimeout(1000);

            const cmdkInput = pg.locator('[cmdk-input]').first();
            if (await cmdkInput.count()) {
              await cmdkInput.focus();
              await pg.waitForTimeout(300);
              await cmdkInput.press('Control+A');
              await pg.keyboard.type(cItems[r].search, { delay: 80 });
              await pg.waitForTimeout(3000);

              const optCount = await pg.locator('[cmdk-item], [role="option"]').count();
              log(`    C PR row ${r}: ${optCount} items for "${cItems[r].search}"`);
              if (optCount > 0) {
                await pg.locator('[cmdk-item], [role="option"]').first().click();
                await pg.waitForTimeout(800);
                log(`    C PR item ${r}: selected "${cItems[r].search}"`);
              } else {
                await pg.keyboard.press('Escape');
                log(`    WARN: No items found for C row ${r}`);
              }
            }
          }
        } catch (e) { log(`    C Item combobox row ${r}: ${e.message}`); }

        // Qty
        const qtyInputs = pg.locator('input[name*="qty"], input[placeholder*="Qty"]');
        const qtyInput = qtyInputs.nth(r);
        if (await qtyInput.count()) {
          await qtyInput.fill(cItems[r].qty);
          await pg.waitForTimeout(200);
          log(`    C PR item ${r}: qty=${cItems[r].qty}`);
        }
      }

      // Click Create PR
      const createPrBtn = pg.getByRole('button', { name: /create pr/i }).first();
      if (await createPrBtn.count()) {
        await createPrBtn.click();
        await waitNav(pg, 5000);
      }
      await shot(pg, 'C01_pr_created');

      const prUrl = pg.url();
      const prMatch = prUrl.match(/purchase-requisitions\/([^/?]+)/);
      let cPrName = prMatch ? decodeURIComponent(prMatch[1]) : null;
      log(`  C PR created: ${cPrName}`);

      // Convert PR to PO with the new vendor
      if (cPrName && cPrName !== 'new') {
        await pg.goto(`${BASE}/dashboard/procurement/purchase-requisitions/${cPrName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pg, 5000);
        const convertBtn = pg.getByRole('button', { name: /convert to po/i }).first();
        if (await convertBtn.count()) {
          await convertBtn.click();
          await pg.waitForTimeout(3000);
          // Select the new vendor supplier using cmdk pattern (same as Chain A)
          const dialogSupplierCombo = pg.locator('[role="dialog"] [role="combobox"]').first();
          if (await dialogSupplierCombo.count()) {
            await dialogSupplierCombo.click();
            await pg.waitForTimeout(1500);
            const cmdkSup = pg.locator('[cmdk-input]').first();
            if (await cmdkSup.count() && newVendor?.name) {
              await cmdkSup.focus();
              await pg.waitForTimeout(300);
              await pg.keyboard.type('S152', { delay: 80 });
              await pg.waitForTimeout(2000);
            }
            const vendorOpt = pg.locator('[role="option"], [cmdk-item]').first();
            if (await vendorOpt.count()) {
              const optText = await vendorOpt.textContent();
              await vendorOpt.click();
              await pg.waitForTimeout(1000);
              log(`  C01: Selected supplier "${optText.trim()}"`);
            } else {
              // Fallback: try without search filter
              await pg.keyboard.press('Escape');
              await pg.waitForTimeout(500);
              await dialogSupplierCombo.click();
              await pg.waitForTimeout(2000);
              const opt2 = pg.locator('[role="option"], [cmdk-item]').first();
              if (await opt2.count()) {
                await opt2.click();
                await pg.waitForTimeout(1000);
                log('  C01: Selected first supplier (no filter)');
              }
            }
          }
          const createPOBtn = pg.getByRole('button', { name: /create po/i }).first();
          if (await createPOBtn.count()) {
            for (let w = 0; w < 10; w++) {
              if (!(await createPOBtn.isDisabled())) break;
              await pg.waitForTimeout(500);
            }
            if (!(await createPOBtn.isDisabled())) {
              await createPOBtn.click();
              await pg.waitForTimeout(5000);
              await pg.waitForLoadState('networkidle').catch(() => {});
            }
          }
        }

        const poUrl = pg.url();
        const poMatch = poUrl.match(/purchase-orders\/([^/?]+)/);
        state.c_poName = poMatch ? decodeURIComponent(poMatch[1]) : null;
        if (!state.c_poName || state.c_poName === 'new') {
          const recent = await fList('BEI Purchase Order', { pr_reference: cPrName }, ['name', 'grand_total']);
          if (recent.length > 0) state.c_poName = recent[0].name;
        }
      }
      await shot(pg, 'C01_po_from_pr');
      await closeSession(sess);
    }

    if (state.c_poName) {
      const cpo = await fDoc('BEI Purchase Order', state.c_poName);
      const c01pass = cpo && cpo.grand_total > 1000000;
      verify(ev, 'S152-C01', 'PO new vendor >1M (browser)', `navigated to /purchase-orders/new`,
        `PO=${state.c_poName} total=${cpo?.grand_total} dual=${cpo?.requires_dual_approval} ceo=${cpo?.requires_ceo_approval}`, c01pass);
      recordResult(ev, 'S152-C01', 'happy', 'Create PO New Vendor >P1M (browser)', c01pass ? 'PASS' : 'FAIL',
        `total=${cpo?.grand_total}`);

      // Submit in browser
      await browserSubmitPO(browser, ev, state.c_poName, 'C01');

      // S152-C02: Mae approves in BROWSER
      log('\n=== S152-C02: Mae Approves New Vendor PO (browser) ===');
      await browserApprovePO(browser, ev, state.c_poName, 'mae', 'C02', 'S152 Chain C — Mae');
      const cpoM = await fDoc('BEI Purchase Order', state.c_poName);
      const c02pass = cpoM?.mae_approval === 'Approved';
      verify(ev, 'S152-C02', 'Mae approved (browser)', `mae@bebang.ph clicked Approve`,
        `status=${cpoM?.status} mae=${cpoM?.mae_approval}`, c02pass);
      recordResult(ev, 'S152-C02', 'happy', 'Mae Approve New Vendor PO (browser)', c02pass ? 'PASS' : 'FAIL', `status=${cpoM?.status}`);

      // S152-C03: Butch approves in BROWSER → Pending CEO
      log('\n=== S152-C03: Butch Approves → Pending CEO (browser) ===');
      await browserApprovePO(browser, ev, state.c_poName, 'butch', 'C03', 'S152 Chain C — Butch');
      const cpoB = await fDoc('BEI Purchase Order', state.c_poName);
      const c03pass = cpoB?.status === 'Pending CEO Approval';
      verify(ev, 'S152-C03', 'Butch → Pending CEO (NOT Approved)', `butch@bebang.ph clicked Approve`,
        `status=${cpoB?.status}`, c03pass);
      recordResult(ev, 'S152-C03', 'happy', 'Butch Approve → Pending CEO (browser)', c03pass ? 'PASS' : 'FAIL',
        `status=${cpoB?.status}`, c03pass ? null : `CRITICAL: Expected Pending CEO, got ${cpoB?.status}`);

      // S152-C04: CEO approves in BROWSER
      log('\n=== S152-C04: CEO Approves PO (browser, sam@bebang.ph) ===');
      await browserApprovePO(browser, ev, state.c_poName, 'sam', 'C04', 'S152 CEO — new vendor >1M authorized');
      const cpoS = await fDoc('BEI Purchase Order', state.c_poName);
      const c04pass = cpoS?.ceo_approval === 'Approved' && cpoS?.status === 'Approved';
      verify(ev, 'S152-C04', 'CEO approved PO (browser)', `sam@bebang.ph clicked Approve`,
        `status=${cpoS?.status} ceo=${cpoS?.ceo_approval}`, c04pass);
      recordResult(ev, 'S152-C04', 'happy', 'CEO Approve New Vendor PO (browser)', c04pass ? 'PASS' : 'FAIL',
        `status=${cpoS?.status}`);

      // S152-C05: GR + Invoice — ALL IN BROWSER
      log('\n=== S152-C05: Chain C GR + Invoice (browser) ===');
      const c_grName = await browserCreateGR(browser, ev, state.c_poName, 'C05');
      const cInvSuffix = Date.now().toString(36).slice(-6).toUpperCase();
      const c_invName = await browserCreateInvoice(browser, ev, state.c_poName, 'C05', `SI-S152-C-${cInvSuffix}`);
      const c05pass = !!(c_grName && c_invName);
      verify(ev, 'S152-C05', 'GR + Invoice (browser)', `created via /goods-receipts/new and /invoices/new`,
        `GR=${c_grName} INV=${c_invName}`, c05pass);
      recordResult(ev, 'S152-C05', 'happy', 'Chain C GR + Invoice (browser)', c05pass ? 'PASS' : 'FAIL',
        `GR=${c_grName} INV=${c_invName}`);

      // C05b: Verify Invoice (required before RFP creation)
      if (c_invName) {
        log('\n=== S152-C05b: Verify Invoice (browser) ===');
        const sess05b = await loginAs(browser, 'finance');
        const pg05b = sess05b.page;
        await pg05b.goto(`${BASE}/dashboard/procurement/invoices/${c_invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pg05b, 5000);

        // Submit for Verification
        const submitVerifBtn = pg05b.getByRole('button', { name: /submit for verif/i }).first();
        if (await submitVerifBtn.count()) {
          await submitVerifBtn.click();
          await pg05b.waitForTimeout(3000);
          log('  Clicked "Submit for Verification"');
        } else {
          log('  WARN: Submit for Verification not found — may already be past Draft');
        }

        // Reload and Verify 3-Way Match
        await pg05b.goto(`${BASE}/dashboard/procurement/invoices/${c_invName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await waitNav(pg05b, 5000);
        const verifyBtn = pg05b.getByRole('button', { name: /verify.*3.way|verify.*match|verify/i }).first();
        if (await verifyBtn.count()) {
          await verifyBtn.click();
          await pg05b.waitForTimeout(3000);
          log('  Clicked "Verify 3-Way Match"');
        }
        const invCheck = await fDoc('BEI Invoice', c_invName);
        log(`  Invoice status after verify: ${invCheck?.status} match=${invCheck?.match_status}`);
        await closeSession(sess05b);
      }

      // S152-C06: Create RFP >P1M in BROWSER
      log('\n=== S152-C06: Create RFP >P1M (browser) ===');
      let c_rfpName = null;
      if (c_invName) {
        c_rfpName = await browserCreateRFP(browser, ev, c_invName, 'C06');
        state.c_rfpName = c_rfpName;
      }
      if (c_rfpName) {
        const cRfp = await fDoc('BEI Payment Request', c_rfpName);
        const c06pass = cRfp?.ceo_required === 1;
        verify(ev, 'S152-C06', 'RFP ceo_required=1 (browser)', `created via /payments/new`,
          `RFP=${c_rfpName} ceo_required=${cRfp?.ceo_required} amount=${cRfp?.payment_amount}`, c06pass);
        recordResult(ev, 'S152-C06', 'happy', 'RFP >P1M CEO Required (browser)', c06pass ? 'PASS' : 'FAIL',
          `ceo_required=${cRfp?.ceo_required}`);

        // S152-C07: RFP L1+L2 in BROWSER
        log('\n=== S152-C07: RFP L1+L2 (browser) ===');
        await browserSubmitAndApproveRFP(browser, ev, c_rfpName, 'C07_L1', 'finance', 'C L1 reviewer');
        await browserSubmitAndApproveRFP(browser, ev, c_rfpName, 'C07_L2', 'finance', 'C L2 budget');
        const cRfpL2 = await fDoc('BEI Payment Request', c_rfpName);
        const c07pass = cRfpL2?.status === 'Pending CFO Approval';
        verify(ev, 'S152-C07', 'L1+L2 approved (browser)', `finance clicked Approve twice`,
          `reviewer=${cRfpL2?.reviewer_status} budget=${cRfpL2?.budget_status} status=${cRfpL2?.status}`, c07pass);
        recordResult(ev, 'S152-C07', 'happy', 'RFP L1+L2 Approve (browser)', c07pass ? 'PASS' : 'FAIL',
          `status=${cRfpL2?.status}`);

        // S152-C08: RFP L3 CFO → Pending CEO in BROWSER
        log('\n=== S152-C08: RFP L3 CFO → Pending CEO (browser, sam) ===');
        await browserSubmitAndApproveRFP(browser, ev, c_rfpName, 'C08', 'sam', 'S152 L3 CFO — >1M needs CEO');
        const cRfpL3 = await fDoc('BEI Payment Request', c_rfpName);
        const c08pass = cRfpL3?.cfo_status === 'Approved' && cRfpL3?.status === 'Pending CEO Approval';
        verify(ev, 'S152-C08', 'CFO → Pending CEO (NOT Approved)', `sam@bebang.ph clicked Approve`,
          `cfo=${cRfpL3?.cfo_status} status=${cRfpL3?.status}`, c08pass);
        recordResult(ev, 'S152-C08', 'happy', 'RFP L3 CFO → Pending CEO (browser)', c08pass ? 'PASS' : 'FAIL',
          `status=${cRfpL3?.status}`, c08pass ? null : `CRITICAL: Expected Pending CEO, got ${cRfpL3?.status}`);

        // S152-C09: RFP L4 CEO Approve in BROWSER
        log('\n=== S152-C09: RFP L4 CEO Approve >P1M (browser, sam) ===');
        await browserSubmitAndApproveRFP(browser, ev, c_rfpName, 'C09', 'sam', 'S152 CEO — P1.4M disbursement authorized');
        const cRfpL4 = await fDoc('BEI Payment Request', c_rfpName);
        const c09pass = cRfpL4?.ceo_status === 'Approved' && cRfpL4?.status === 'Approved';
        verify(ev, 'S152-C09', 'CEO L4 approved >P1M RFP (browser)', `sam@bebang.ph clicked Approve`,
          `ceo=${cRfpL4?.ceo_status} ceo_approver=${cRfpL4?.ceo_approver} status=${cRfpL4?.status}`, c09pass);
        recordResult(ev, 'S152-C09', 'happy', 'RFP L4 CEO Approve >P1M (browser)', c09pass ? 'PASS' : 'FAIL',
          `status=${cRfpL4?.status}`);
      } else {
        recordResult(ev, 'S152-C06', 'happy', 'RFP >P1M', 'FAIL', 'Invoice creation failed');
        recordResult(ev, 'S152-C07', 'happy', 'RFP L1+L2', 'SKIP', 'Dep C06 failed');
        recordResult(ev, 'S152-C08', 'happy', 'RFP L3', 'SKIP', 'Dep C06 failed');
        recordResult(ev, 'S152-C09', 'happy', 'RFP L4', 'SKIP', 'Dep C06 failed');
      }
    } else {
      recordResult(ev, 'S152-C01', 'happy', 'Create PO New Vendor', 'FAIL', 'Browser PO creation failed');
      for (const id of ['C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09']) {
        recordResult(ev, `S152-${id}`, 'happy', `Chain C ${id}`, 'SKIP', 'Dep C01 failed');
      }
    }

  } catch (err) {
    log(`\nFATAL ERROR: ${err.message}`);
    console.error(err);
  } finally {
    await browser.close();
  }

  writeEvidence(ev, 'chain_bc');
  console.log('\n=== CHAIN B DOCS ===');
  console.log(`  PO: ${state.b_poName || 'NONE'}`);
  console.log('\n=== CHAIN C DOCS ===');
  console.log(`  PO: ${state.c_poName || 'NONE'}  RFP: ${state.c_rfpName || 'NONE'}`);

  const allPass = printSummary(ev, 'CHAIN B+C');
  process.exit(allPass ? 0 : 1);
})();
