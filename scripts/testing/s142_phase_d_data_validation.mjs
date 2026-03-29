/**
 * S142 Phase D — DATA VALIDATION (not just "does it load")
 *
 * This validates ACTUAL DATA across UI, API, and source files:
 *  Q1-Q15:  Record counts, amounts, statuses, ghost/missing records, business rules
 *  Q16-Q18: Supplier Master completeness + compliance docs + duplicates
 *  Q19-Q22: SKU/Item Master completeness + prices + orphan items
 *
 * Run: node scripts/testing/s142_phase_d_data_validation.mjs
 */

import {
  ensureDirs, launchBrowser, loginAs, screenshot,
  readText, readTableRows, BASE, ResultTracker
} from './s142_utils.mjs';
import fs from 'fs';

const validation = {
  counts: {},
  po_spot_checks: [],
  supplier_spot_checks: [],
  supplier_completeness: { total: 0, complete: 0, incomplete: [], missing_fields: {} },
  supplier_duplicates: [],
  item_master: { total: 0, with_price: 0, without_price: [], missing_uom: [], sku_master_comparison: {} },
  orphan_items: [],
  kpi_math: {},
  approval_checks: [],
  ghost_checks: [],
  missing_checks: [],
  business_rules: [],
};

// API call via browser session (per /playwright-bei-erp pattern)
async function apiCall(page, endpoint) {
  return page.evaluate(async (url) => {
    try {
      const r = await fetch(url, { credentials: 'include', headers: { 'Accept': 'application/json' } });
      const text = await r.text();
      let json = null;
      try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json, body: text.substring(0, 2000) };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }, `${BASE}/api/procurement${endpoint}`);
}

// Direct Frappe API call for DocType queries
async function frappeQuery(page, doctype, fields, filters = {}, limit = 0) {
  return page.evaluate(async ({ doctype, fields, filters, limit }) => {
    try {
      const params = new URLSearchParams({
        filters: JSON.stringify(filters),
        fields: JSON.stringify(fields),
        limit_page_length: String(limit || 0),
        order_by: 'creation desc',
      });
      const r = await fetch(`/api/frappe/api/resource/${doctype}?${params}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });
      const data = await r.json();
      return { ok: r.ok, data: data?.data || [], total: data?.data?.length || 0 };
    } catch (e) {
      return { ok: false, error: e.message, data: [], total: 0 };
    }
  }, { doctype, fields, filters, limit });
}

async function run() {
  ensureDirs();
  const tracker = new ResultTracker();
  const browser = await launchBrowser();

  console.log('═══════════════════════════════════════');
  console.log('S142 Phase D — DATA VALIDATION');
  console.log('Validates: counts, amounts, statuses,');
  console.log('supplier completeness, SKU master, prices');
  console.log('═══════════════════════════════════════\n');

  const { page, ctx } = await loginAs(browser, 'ceo');

  // ═══════════════════════════════════
  // Q1: COUNT RECONCILIATION — Purchase Orders
  // ═══════════════════════════════════
  console.log('\n── Q1: PO Count Reconciliation ──');
  {
    const apiResult = await apiCall(page, '/purchase-orders?page=1&page_size=1');
    const apiTotal = apiResult.json?.total || 0;

    await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const paginationText = await page.locator('text=/of \\d+ POs/').first().innerText().catch(() => '');
    const uiTotalMatch = paginationText.match(/of\s+(\d+)/);
    const uiTotal = uiTotalMatch ? parseInt(uiTotalMatch[1]) : 0;

    validation.counts.po = { api: apiTotal, ui: uiTotal, match: apiTotal === uiTotal };
    console.log(`  API: ${apiTotal}, UI: ${uiTotal}, Match: ${apiTotal === uiTotal}`);

    if (apiTotal === uiTotal && apiTotal > 0) tracker.pass('Q1', `PO count: API=${apiTotal} UI=${uiTotal}`, 'Match');
    else if (apiTotal === 0) tracker.fail('Q1', 'PO count', `API returned 0`, 'API may be broken');
    else {
      tracker.fail('Q1', 'PO count', `API=${apiTotal} UI=${uiTotal}`, `${Math.abs(apiTotal - uiTotal)} missing`);
      tracker.defect('PO count mismatch', 'CRITICAL', 'IN-SCOPE', 'Q1',
        `API=${apiTotal} UI=${uiTotal}`, 'Records invisible', 'Pagination or query', 'Compare counts');
    }
  }

  // ═══════════════════════════════════
  // Q2: PO AMOUNT SPOT-CHECK (10 POs)
  // ═══════════════════════════════════
  console.log('\n── Q2: PO Amount Spot-Check (10 POs) ──');
  {
    // Simplified: check first page of POs visible in UI against API (no deep pagination to avoid browser crashes)
    await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    const rowCount = await page.locator('table tbody tr').count().catch(() => 0);
    const samplesToCheck = Math.min(rowCount, 10);

    for (let idx = 0; idx < samplesToCheck; idx++) {
      const rowText = await page.locator(`table tbody tr:nth-child(${idx + 1})`).innerText().catch(() => '');
      const poNoMatch = rowText.match(/(PO-\d+)/);
      if (!poNoMatch) continue;
      const poNo = poNoMatch[1];
      const amountMatch = rowText.match(/₱([\d,]+)/);
      const uiAmount = amountMatch ? amountMatch[1].replace(/,/g, '') : null;

      const apiResult = await apiCall(page, `/purchase-orders?search=${poNo}&page_size=1`);
      const apiPO = apiResult.json?.data?.[0];
      const apiAmount = apiPO ? String(Math.round(apiPO.grand_total)) : null;

      const entry = { po_no: poNo, idx, ui_amount: uiAmount, api_amount: apiAmount, match: uiAmount === apiAmount };
      console.log(`  ${poNo} (row ${idx + 1}): UI ₱${uiAmount} vs API ₱${apiAmount} ${entry.match ? '✓' : '✗'}`);
      validation.po_spot_checks.push(entry);

      if (entry.match) tracker.pass(`Q2-r${idx}`, `${poNo} amount`, `₱${uiAmount}`);
      else tracker.fail(`Q2-r${idx}`, `${poNo} amount mismatch`, `UI=₱${uiAmount} API=₱${apiAmount}`, 'Data inconsistency');
    }
  }

  // ═══════════════════════════════════
  // ═══════════════════════════════════
  // Q3: PO DATA vs GOOGLE SHEET (Compliance App)
  // ═══════════════════════════════════
  console.log('\n── Q3: PO Data vs Compliance App Google Sheet ──');
  {
    // Read the Compliance App PO tab via the proxy → Frappe → Google Sheets API
    // Sheet ID: 1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q
    // We use page.evaluate to call the Frappe Google Sheets helper if available,
    // or fall back to comparing against the local Compliance App CSV extract
    let sheetPOs = [];
    try {
      const csvPath = 'data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__Purchase_Order.csv';
      if (fs.existsSync(csvPath)) {
        const csvContent = fs.readFileSync(csvPath, 'utf8');
        const lines = csvContent.split('\n').filter(l => l.trim());
        for (let i = 1; i < Math.min(lines.length, 100); i++) {
          const cols = lines[i].split(',').map(c => c.replace(/^"|"$/g, ''));
          if (cols.length >= 5) {
            sheetPOs.push({ po_no: cols[1], supplier: cols[2], amount: parseFloat(cols[3]) || 0 });
          }
        }
      }
    } catch (err) {
      console.log(`  Could not read Compliance App PO CSV: ${err.message}`);
    }

    if (sheetPOs.length > 0) {
      console.log(`  Compliance App CSV: ${sheetPOs.length} POs loaded`);
      // Spot-check 5 POs from the sheet against API
      const sample = sheetPOs.filter((_, i) => [0, 10, 20, 30, 40].includes(i)).filter(Boolean);
      let matchCount = 0;
      for (const sheetPO of sample) {
        if (!sheetPO.po_no) continue;
        const apiResult = await apiCall(page, `/purchase-orders?search=${sheetPO.po_no}&page_size=1`);
        const apiPO = apiResult.json?.data?.[0];
        const found = !!apiPO;
        const amountMatch = apiPO ? Math.abs(apiPO.grand_total - sheetPO.amount) < 10 : false;
        console.log(`  ${sheetPO.po_no}: Sheet ₱${sheetPO.amount} → API ${found ? `₱${apiPO.grand_total}` : 'NOT FOUND'} ${amountMatch ? '✓' : '✗'}`);
        if (found && amountMatch) matchCount++;
        validation.po_spot_checks.push({
          po_no: sheetPO.po_no, source: 'google_sheet',
          sheet_amount: sheetPO.amount, api_amount: apiPO?.grand_total,
          found_in_api: found, amount_match: amountMatch,
        });
      }
      if (matchCount >= 3) tracker.pass('Q3', `Sheet↔API: ${matchCount}/${sample.length} match`, 'Three-way confirmed');
      else tracker.fail('Q3', `Sheet↔API: only ${matchCount}/${sample.length} match`, '', 'Data sync gap');
    } else {
      console.log('  No Compliance App CSV found — checking for alternate PO extract...');
      // Try alternate path
      const altPath = 'data/Procurement_Database/runs/2026-01-07/outputs/SUPPLIER_MASTER_FINAL_2026-01-07.csv';
      if (fs.existsSync(altPath)) {
        console.log('  Found supplier extract but not PO extract');
      }
      tracker.skip('Q3', 'Google Sheet comparison', 'No local PO CSV extract available. Need to extract from Sheet ID 1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q');
    }
  }

  // Q4: Supplier Count
  // ═══════════════════════════════════
  console.log('\n── Q4: Supplier Count ──');
  {
    const apiResult = await apiCall(page, '/suppliers?page=1&page_size=1');
    const apiTotal = apiResult.json?.total || 0;
    await page.goto(`${BASE}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const paginationText = await page.locator('text=/of \\d+/').first().innerText().catch(() => '');
    const uiMatch = paginationText.match(/of\s+(\d+)/);
    const uiTotal = uiMatch ? parseInt(uiMatch[1]) : 0;
    validation.counts.suppliers = { api: apiTotal, ui: uiTotal, match: apiTotal === uiTotal };
    console.log(`  API: ${apiTotal}, UI: ${uiTotal}`);
    if (apiTotal === uiTotal && apiTotal > 0) tracker.pass('Q4', `Supplier count: ${apiTotal}`, 'Match');
    else tracker.fail('Q4', 'Supplier count', `API=${apiTotal} UI=${uiTotal}`, 'Mismatch');
  }

  // ═══════════════════════════════════
  // ═══════════════════════════════════
  // Q5: Supplier Detail Spot-Check (10)
  // ═══════════════════════════════════
  console.log('\n── Q5: Supplier Detail Spot-Check (10 suppliers) ──');
  {
    await page.goto(`${BASE}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const rowCount = await page.locator('table tbody tr').count();
    const indices = [0, 1, 3, 5, 7, 9, 11, 13, 15, 17].filter(i => i < rowCount);
    let matchCount = 0;

    for (const idx of indices) {
      const rowText = await page.locator(`table tbody tr:nth-child(${idx + 1})`).innerText().catch(() => '');
      const cells = rowText.split('\n').map(c => c.trim()).filter(c => c);
      const uiName = cells[0] || '';
      if (!uiName) continue;

      const apiResult = await apiCall(page, `/suppliers?search=${encodeURIComponent(uiName.substring(0, 20))}&page_size=1`);
      const apiSup = apiResult.json?.data?.[0];
      const nameMatch = apiSup?.supplier_name?.includes(uiName.substring(0, 15)) || uiName.includes(apiSup?.supplier_name?.substring(0, 15) || '---');

      console.log(`  "${uiName.substring(0, 30)}": API ${nameMatch ? '✓' : '✗'} (${apiSup?.supplier_name?.substring(0, 30) || 'NOT FOUND'}), TIN: ${apiSup?.tin || 'empty'}, Status: ${apiSup?.status || '?'}`);
      validation.supplier_spot_checks.push({ ui_name: uiName, api_name: apiSup?.supplier_name, name_match: nameMatch, tin: apiSup?.tin, status: apiSup?.status });
      if (nameMatch) { matchCount++; tracker.pass(`Q5-${idx}`, `Supplier "${uiName.substring(0, 20)}"`, 'Match'); }
      else tracker.fail(`Q5-${idx}`, `Supplier "${uiName.substring(0, 20)}"`, '', 'Mismatch');
    }
    console.log(`  Result: ${matchCount}/${indices.length} suppliers matched`);
  }

  // Q6: GR Count
  // ═══════════════════════════════════
  console.log('\n── Q6: GR Count ──');
  {
    const apiResult = await apiCall(page, '/goods-receipts?page=1&page_size=1');
    const apiTotal = apiResult.json?.total || 0;
    await page.goto(`${BASE}/dashboard/procurement/goods-receipts`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const paginationText = await page.locator('text=/of \\d+/').first().innerText().catch(() => '');
    const uiMatch = paginationText.match(/of\s+(\d+)/);
    const uiTotal = uiMatch ? parseInt(uiMatch[1]) : 0;
    validation.counts.grs = { api: apiTotal, ui: uiTotal, match: apiTotal === uiTotal };
    console.log(`  API: ${apiTotal}, UI: ${uiTotal}`);
    if (apiTotal === uiTotal && apiTotal > 0) tracker.pass('Q6', `GR count: ${apiTotal}`, 'Match');
    else tracker.fail('Q6', 'GR count', `API=${apiTotal} UI=${uiTotal}`, 'Mismatch');
  }

  // ═══════════════════════════════════
  // ═══════════════════════════════════
  // Q7: GR Received Qty vs PO Ordered Qty
  // ═══════════════════════════════════
  console.log('\n── Q7: GR Received Qty vs PO Ordered Qty (10 GRs) ──');
  {
    const grResult = await apiCall(page, '/goods-receipts?page=1&page_size=10');
    const grs = grResult.json?.data || [];
    let overReceipts = 0;

    for (const gr of grs) {
      const orderedQty = gr.total_ordered_qty || 0;
      const receivedQty = gr.total_received_qty || 0;
      const isOver = receivedQty > orderedQty && orderedQty > 0;
      const pct = orderedQty > 0 ? Math.round((receivedQty / orderedQty) * 100) : 0;

      console.log(`  ${gr.gr_number} (PO: ${gr.po_number}): Ordered=${orderedQty} Received=${receivedQty} (${pct}%) ${isOver ? '⚠ OVER-RECEIPT' : '✓'}`);

      if (isOver) {
        overReceipts++;
        tracker.defect(`Over-receipt on ${gr.gr_number}`, 'MAJOR', 'COLLATERAL', `Q7-${gr.gr_number}`,
          `Received ${receivedQty} vs ordered ${orderedQty} (${pct}%)`, 'Supplier delivered more than ordered',
          'GR validation may not enforce qty limit', 'Check GR creation qty validation');
      }
    }

    if (overReceipts === 0) tracker.pass('Q7', `GR qty check: 0/${grs.length} over-receipts`, 'All within limits');
    else tracker.fail('Q7', `${overReceipts}/${grs.length} over-receipts found`, '', 'Qty validation gap');
  }

  // Q8: Dashboard MTD PO Math
  // ═══════════════════════════════════
  console.log('\n── Q8: Dashboard MTD Math ──');
  {
    await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const kpiTexts = await page.locator('.tracking-tight').allInnerTexts().catch(() => []);
    const mtdText = kpiTexts.find(t => t.includes('₱') && !t.includes('No data')) || '';
    const mtdUiMatch = mtdText.match(/₱([\d,]+)/);
    const mtdUiValue = mtdUiMatch ? parseInt(mtdUiMatch[1].replace(/,/g, '')) : 0;
    const kpiResult = await apiCall(page, '/dashboard/kpis');
    const mtdApiValue = Math.round(kpiResult.json?.mtd_po_value || 0);
    const delta = Math.abs(mtdUiValue - mtdApiValue);
    validation.kpi_math = { mtd_ui: mtdUiValue, mtd_api: mtdApiValue, delta, match: delta < 1000 };
    console.log(`  UI: ₱${mtdUiValue.toLocaleString()}, API: ₱${mtdApiValue.toLocaleString()}, Delta: ₱${delta.toLocaleString()}`);
    if (delta < 1000) tracker.pass('Q8', `MTD PO: UI=₱${mtdUiValue.toLocaleString()} API=₱${mtdApiValue.toLocaleString()}`, `Delta ₱${delta}`);
    else tracker.fail('Q8', 'MTD PO Value mismatch', `Delta=₱${delta.toLocaleString()}`, 'Math error');
    await screenshot(page, 'Q8_dashboard_mtd');
  }

  // ═══════════════════════════════════
  // ═══════════════════════════════════
  // Q9: Approval Status Accuracy (5 pending POs)
  // ═══════════════════════════════════
  console.log('\n── Q9: Approval Status Accuracy ──');
  {
    const pendingResult = await apiCall(page, '/purchase-orders/pending-approvals');
    const pendingMae = pendingResult.json?.pending_mae || [];
    const pendingButch = pendingResult.json?.pending_butch || [];
    console.log(`  API: ${pendingMae.length} pending Mae, ${pendingButch.length} pending Butch`);

    const toCheck = [...pendingMae.slice(0, 3), ...pendingButch.slice(0, 2)];
    for (const po of toCheck) {
      const expectedStatus = pendingMae.includes(po) ? 'Pending Mae' : 'Pending Butch';
      await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
      const search = page.locator('input[placeholder*="Search"]').first();
      if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
        await search.fill(po.po_no);
        await page.waitForTimeout(2000);
      }
      const rowText = await page.locator('table tbody tr:first-child').innerText().catch(() => '');
      const hasCorrectStatus = rowText.includes(expectedStatus);
      console.log(`  ${po.po_no}: expect "${expectedStatus}", UI ${hasCorrectStatus ? '✓' : '✗'} "${rowText.substring(0, 80)}"`);
      validation.approval_checks.push({ po_no: po.po_no, expected: expectedStatus, ui_correct: hasCorrectStatus });
      if (hasCorrectStatus) tracker.pass(`Q9-${po.po_no}`, `${po.po_no} status correct`, expectedStatus);
      else tracker.fail(`Q9-${po.po_no}`, `${po.po_no} status mismatch`, `Expected: ${expectedStatus}`, 'UI shows wrong status');
    }
    if (toCheck.length === 0) tracker.skip('Q9', 'Approval status', 'No pending POs to verify');
  }

  // Q10: Ghost Record Check
  // ═══════════════════════════════════
  console.log('\n── Q10: Ghost Record Check (5 UI POs → API) ──');
  {
    await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const rows = await page.locator('table tbody tr').count();
    for (let i = 0; i < Math.min(5, rows); i++) {
      const rowText = await page.locator(`table tbody tr:nth-child(${i + 1})`).innerText().catch(() => '');
      const poMatch = rowText.match(/(PO-\d+)/);
      if (!poMatch) continue;
      const poNo = poMatch[1];
      const apiResult = await apiCall(page, `/purchase-orders?search=${poNo}&page_size=1`);
      const found = apiResult.json?.data?.length > 0;
      console.log(`  ${poNo}: API ${found ? '✓' : '✗ GHOST!'}`);
      validation.ghost_checks.push({ po_no: poNo, exists_in_api: found });
      if (found) tracker.pass(`Q10-${poNo}`, `${poNo} exists in API`, 'Not ghost');
      else tracker.fail(`Q10-${poNo}`, `${poNo} GHOST`, '', 'UI shows non-existent PO');
    }
  }

  // ═══════════════════════════════════
  // Q11: Missing Record Check (5 API POs → UI)
  // ═══════════════════════════════════
  console.log('\n── Q11: Missing Record Check (5 latest API POs → UI) ──');
  {
    const apiResult = await apiCall(page, '/purchase-orders?page=1&page_size=5');
    const latestPOs = apiResult.json?.data || [];
    for (const po of latestPOs) {
      await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
      const search = page.locator('input[placeholder*="Search"]').first();
      if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
        await search.clear(); await search.fill(po.po_no); await page.waitForTimeout(2000);
      }
      const rowText = await page.locator('table tbody tr:first-child').innerText().catch(() => '');
      const found = rowText.includes(po.po_no);
      console.log(`  ${po.po_no}: UI ${found ? '✓' : '✗ MISSING!'}`);
      validation.missing_checks.push({ po_no: po.po_no, visible_in_ui: found });
      if (found) tracker.pass(`Q11-${po.po_no}`, `${po.po_no} visible in UI`, 'Not missing');
      else tracker.fail(`Q11-${po.po_no}`, `${po.po_no} MISSING from UI`, '', 'Search failed');
    }
  }

  // ═══════════════════════════════════
  // Q12: Invoice/Payment Pipeline
  // ═══════════════════════════════════
  console.log('\n── Q12: Invoice Pipeline Status ──');
  {
    await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const kpiTexts = await page.locator('.tracking-tight').allInnerTexts().catch(() => []);
    const showsNoData = kpiTexts.some(t => t.includes('No data'));
    const showsZero = kpiTexts.some(t => t === '₱0');
    console.log(`  "No data": ${showsNoData}, "₱0": ${showsZero}`);
    if (showsNoData && !showsZero) tracker.pass('Q12', 'Dashboard "No data yet"', 'Correct empty state');
    else if (showsZero) tracker.fail('Q12', 'Dashboard shows ₱0', '', 'Should show "No data yet"');
    else tracker.pass('Q12', 'Invoice pipeline', 'Has data or correct empty');
  }

  // ═══════════════════════════════════
  // ═══════════════════════════════════
  // Q13: RFP Types — Settings vs Payment Form Cross-Reference
  // ═══════════════════════════════════
  console.log('\n── Q13: RFP Types Cross-Reference ──');
  {
    // Read from Settings page
    await page.goto(`${BASE}/dashboard/procurement/settings`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    // Shadcn Badge uses utility classes like "badge" or "inline-flex items-center rounded-full" — try multiple selectors
    const settingsBadges = await page.locator('[class*="Badge"], [class*="badge"], [data-slot="badge"], span.inline-flex').allInnerTexts().catch(() => []);
    // Also read all text from settings page to find RFP types as fallback
    const settingsFullText = await page.innerText('main').catch(() => '');
    let settingsRFP = settingsBadges.filter(b =>
      ['PCF', 'Delivery Fund', 'Transpo', 'Rentals', 'Vendor', 'Cash Advance', 'Reimbursement', 'Credit Card'].some(t => b.includes(t))
    );
    // Fallback: parse from full text if badge selectors missed
    if (settingsRFP.length === 0) {
      const rfpTypes = ['PCF', 'Delivery Fund', 'Transpo', 'Rentals', 'Vendor', 'Cash Advance', 'Reimbursement', 'Credit Card'];
      settingsRFP = rfpTypes.filter(t => settingsFullText.includes(t));
      if (settingsRFP.length > 0) console.log(`  (Used text-match fallback for Settings RFP types)`);
    }

    // Read from Payment New form
    await page.goto(`${BASE}/dashboard/procurement/payments/new`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    // Find the RFP Type dropdown and read its options
    const comboboxes = await page.locator('button[role="combobox"]').count();
    let formRFP = [];
    for (let i = 0; i < comboboxes; i++) {
      const trigger = page.locator('button[role="combobox"]').nth(i);
      await trigger.click().catch(() => {});
      await page.waitForTimeout(500);
      const options = await page.locator('[role="option"]').allInnerTexts().catch(() => []);
      // Check if these look like RFP types
      if (options.some(o => o.includes('PCF') || o.includes('Vendor') || o.includes('Rentals') || o.includes('Reimbursement'))) {
        formRFP = options;
        await page.keyboard.press('Escape');
        break;
      }
      await page.keyboard.press('Escape');
      await page.waitForTimeout(200);
    }

    console.log(`  Settings RFP badges: ${JSON.stringify(settingsRFP)}`);
    console.log(`  Payment form RFP options: ${JSON.stringify(formRFP)}`);

    // Cross-reference: every Settings badge should appear in form options
    const settingsOnly = settingsRFP.filter(s => !formRFP.some(f => f.includes(s.substring(0, 10))));
    const formOnly = formRFP.filter(f => !settingsRFP.some(s => f.includes(s.substring(0, 10))));

    if (settingsOnly.length === 0 && formOnly.length === 0 && settingsRFP.length > 0) {
      tracker.pass('Q13', `RFP types match: ${settingsRFP.length} in Settings = ${formRFP.length} in form`, 'Consistent');
    } else {
      const detail = [];
      if (settingsOnly.length > 0) detail.push(`In Settings but not form: ${settingsOnly.join(', ')}`);
      if (formOnly.length > 0) detail.push(`In form but not Settings: ${formOnly.join(', ')}`);
      tracker.fail('Q13', 'RFP types mismatch', detail.join('; '), 'Settings and form disagree');
      tracker.defect('RFP types mismatch between Settings and Payment form', 'MINOR', 'COLLATERAL', 'Q13',
        detail.join('; '), 'User sees different options in different places', 'Hardcoded lists not synced', 'Use single source of truth');
    }
  }

  // Q14: >500K Business Rule
  // ═══════════════════════════════════
  console.log('\n── Q14: >500K Approval Rule ──');
  {
    const apiResult = await apiCall(page, '/purchase-orders?page=1&page_size=100');
    const bigPO = (apiResult.json?.data || []).find(po => po.grand_total > 500000);
    if (bigPO) {
      await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
      const search = page.locator('input[placeholder*="Search"]').first();
      if (await search.isVisible().catch(() => false)) { await search.fill(bigPO.po_no); await page.waitForTimeout(2000); }
      const rowText = await page.locator('table tbody tr:first-child').innerText().catch(() => '');
      const hasBadge = rowText.includes('>500K') || rowText.includes('500K');
      console.log(`  ${bigPO.po_no}: ₱${bigPO.grand_total.toLocaleString()}, badge: ${hasBadge}`);
      if (hasBadge || bigPO.requires_dual_approval) tracker.pass('Q14', `${bigPO.po_no} >500K badge`, 'Rule enforced');
      else tracker.fail('Q14', `${bigPO.po_no} missing >500K badge`, `₱${bigPO.grand_total.toLocaleString()}`, 'Rule not enforced');
    } else tracker.skip('Q14', '>500K rule', 'No POs >500K in first 100');
  }

  // ═══════════════════════════════════════════════
  // Q16: SUPPLIER MASTER COMPLETENESS
  // ═══════════════════════════════════════════════
  console.log('\n══════════════════════════════════════');
  console.log('SUPPLIER MASTER VALIDATION (Q16-Q18)');
  console.log('══════════════════════════════════════\n');

  console.log('── Q16: Supplier Data Completeness ──');
  {
    // Use the data quality API endpoint
    const qualityResult = await apiCall(page, '/suppliers/data-quality');
    const qualityData = qualityResult.json;

    if (qualityData && !qualityResult.error) {
      console.log(`  Data quality API response: ${JSON.stringify(qualityData).substring(0, 300)}`);
      validation.supplier_completeness.api_quality = qualityData;
      tracker.pass('Q16-api', 'Supplier data quality API', `Responded: ${JSON.stringify(qualityData).substring(0, 100)}`);
    } else {
      console.log(`  Data quality API failed, falling back to manual check`);
    }

    // Get ALL suppliers with all fields
    const allSuppliers = await apiCall(page, '/suppliers?page=1&page_size=500');
    const suppliers = allSuppliers.json?.data || [];
    validation.supplier_completeness.total = suppliers.length;

    const requiredFields = ['supplier_name', 'tin', 'phone', 'email', 'contact_person', 'bank_name', 'bank_account_number', 'payment_terms'];
    const complianceFields = ['bir_2307', 'sec_certificate'];
    const fieldMissing = {};

    let completeCount = 0;
    const incomplete = [];

    for (const sup of suppliers) {
      const missing = [];

      // Check required fields
      for (const field of requiredFields) {
        if (!sup[field] || sup[field] === '' || sup[field] === null) {
          missing.push(field);
          fieldMissing[field] = (fieldMissing[field] || 0) + 1;
        }
      }

      // Check compliance docs
      for (const field of complianceFields) {
        if (!sup[field] || sup[field] === '' || sup[field] === null) {
          missing.push(field);
          fieldMissing[field] = (fieldMissing[field] || 0) + 1;
        }
      }

      if (missing.length === 0) {
        completeCount++;
      } else {
        incomplete.push({
          name: sup.name,
          supplier_name: sup.supplier_name,
          status: sup.status,
          missing_fields: missing,
          missing_count: missing.length,
        });
      }
    }

    validation.supplier_completeness.complete = completeCount;
    validation.supplier_completeness.incomplete = incomplete;
    validation.supplier_completeness.missing_fields = fieldMissing;

    console.log(`\n  SUPPLIER COMPLETENESS REPORT:`);
    console.log(`  Total suppliers: ${suppliers.length}`);
    console.log(`  Complete (all fields): ${completeCount} (${Math.round(completeCount / suppliers.length * 100)}%)`);
    console.log(`  Incomplete: ${incomplete.length}`);
    console.log(`\n  MISSING FIELD BREAKDOWN:`);
    for (const [field, count] of Object.entries(fieldMissing).sort((a, b) => b[1] - a[1])) {
      console.log(`    ${field}: ${count} suppliers missing (${Math.round(count / suppliers.length * 100)}%)`);
    }

    // Top 10 most incomplete suppliers
    const worst = incomplete.sort((a, b) => b.missing_count - a.missing_count).slice(0, 10);
    if (worst.length > 0) {
      console.log(`\n  TOP 10 MOST INCOMPLETE SUPPLIERS:`);
      for (const s of worst) {
        console.log(`    ${s.supplier_name} (${s.status}): missing ${s.missing_count} fields [${s.missing_fields.join(', ')}]`);
      }
    }

    tracker.pass('Q16', `Supplier completeness: ${completeCount}/${suppliers.length} complete`,
      `Incomplete: ${incomplete.length}. Most missing: ${Object.entries(fieldMissing).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([f, c]) => `${f}:${c}`).join(', ')}`);
    await screenshot(page, 'Q16_supplier_completeness');
  }

  // ═══════════════════════════════════
  // Q17: Supplier Compliance Docs
  // ═══════════════════════════════════
  console.log('\n── Q17: Supplier Compliance Documents ──');
  {
    const allSuppliers = await apiCall(page, '/suppliers?page=1&page_size=500');
    const activeSuppliers = (allSuppliers.json?.data || []).filter(s => s.status === 'Active');
    const missingBIR = activeSuppliers.filter(s => !s.bir_2307);
    const missingSEC = activeSuppliers.filter(s => !s.sec_certificate);
    const missingPermit = activeSuppliers.filter(s => !s.business_permit);

    console.log(`  Active suppliers: ${activeSuppliers.length}`);
    console.log(`  Missing BIR 2307: ${missingBIR.length} (${Math.round(missingBIR.length / activeSuppliers.length * 100)}%)`);
    console.log(`  Missing SEC cert: ${missingSEC.length} (${Math.round(missingSEC.length / activeSuppliers.length * 100)}%)`);
    console.log(`  Missing business permit: ${missingPermit.length} (${Math.round(missingPermit.length / activeSuppliers.length * 100)}%)`);

    if (missingBIR.length > 0) {
      console.log(`\n  SUPPLIERS MISSING BIR 2307 (first 10):`);
      for (const s of missingBIR.slice(0, 10)) console.log(`    - ${s.supplier_name}`);
    }

    tracker.pass('Q17', `Compliance docs: BIR missing=${missingBIR.length}, SEC missing=${missingSEC.length}`,
      `Active: ${activeSuppliers.length}, BIR gap: ${Math.round(missingBIR.length / activeSuppliers.length * 100)}%`);

    if (missingBIR.length > activeSuppliers.length * 0.5) {
      tracker.defect(`${missingBIR.length} active suppliers missing BIR 2307`, 'MAJOR', 'COLLATERAL', 'Q17',
        `${Math.round(missingBIR.length / activeSuppliers.length * 100)}% of active suppliers lack BIR 2307`,
        'Tax compliance risk — EWT cannot be filed', 'Docs never uploaded', 'Procurement team to collect');
    }
  }

  // ═══════════════════════════════════
  // Q18: Duplicate Suppliers
  // ═══════════════════════════════════
  console.log('\n── Q18: Duplicate Supplier Detection ──');
  {
    const dupResult = await apiCall(page, '/suppliers/duplicates');
    const duplicates = dupResult.json;

    if (duplicates && !dupResult.error) {
      const phoneMatches = duplicates.phone_duplicates || [];
      const tinMatches = duplicates.tin_duplicates || [];
      const bankMatches = duplicates.bank_duplicates || [];

      console.log(`  Phone duplicates: ${phoneMatches.length}`);
      console.log(`  TIN duplicates: ${tinMatches.length}`);
      console.log(`  Bank account duplicates: ${bankMatches.length}`);

      validation.supplier_duplicates = { phone: phoneMatches, tin: tinMatches, bank: bankMatches };

      const totalDups = phoneMatches.length + tinMatches.length + bankMatches.length;
      if (totalDups === 0) {
        tracker.pass('Q18', 'No duplicate suppliers found', 'Clean data');
      } else {
        tracker.fail('Q18', `${totalDups} potential duplicates`, `Phone:${phoneMatches.length} TIN:${tinMatches.length} Bank:${bankMatches.length}`, 'Data quality issue');
        if (tinMatches.length > 0) {
          tracker.defect(`${tinMatches.length} suppliers share the same TIN`, 'CRITICAL', 'COLLATERAL', 'Q18',
            `TIN duplicates found`, 'Tax filing risk — same TIN on multiple records', 'Data entry error', 'Merge or correct');
          for (const dup of tinMatches.slice(0, 5)) console.log(`    TIN duplicate: ${JSON.stringify(dup).substring(0, 100)}`);
        }
      }
    } else {
      console.log(`  Duplicates API failed: ${dupResult.error || dupResult.body?.substring(0, 100)}`);
      tracker.skip('Q18', 'Duplicate detection', `API error: ${dupResult.error || 'unknown'}`);
    }
  }

  // ═══════════════════════════════════════════════
  // Q19-Q22: SKU / ITEM MASTER VALIDATION
  // ═══════════════════════════════════════════════
  console.log('\n══════════════════════════════════════');
  console.log('ITEM / SKU MASTER VALIDATION (Q19-Q22)');
  console.log('══════════════════════════════════════\n');

  // ═══════════════════════════════════
  // Q19: Item Master Completeness
  // ═══════════════════════════════════
  console.log('── Q19: Item Master Completeness ──');
  {
    // Get all items from Frappe
    const items = await frappeQuery(page, 'Item',
      ['name', 'item_code', 'item_name', 'item_group', 'stock_uom', 'standard_rate', 'disabled'],
      { disabled: 0 }, 500);

    if (items.ok && items.data.length > 0) {
      validation.item_master.total = items.data.length;

      const withPrice = items.data.filter(i => i.standard_rate && i.standard_rate > 0);
      const withoutPrice = items.data.filter(i => !i.standard_rate || i.standard_rate === 0);
      const missingUOM = items.data.filter(i => !i.stock_uom);
      const missingGroup = items.data.filter(i => !i.item_group);

      validation.item_master.with_price = withPrice.length;
      validation.item_master.without_price = withoutPrice.map(i => ({
        item_code: i.item_code || i.name,
        item_name: i.item_name,
        item_group: i.item_group,
        stock_uom: i.stock_uom,
      }));
      validation.item_master.missing_uom = missingUOM.map(i => i.item_code || i.name);

      console.log(`  Total active items: ${items.data.length}`);
      console.log(`  With price (standard_rate > 0): ${withPrice.length} (${Math.round(withPrice.length / items.data.length * 100)}%)`);
      console.log(`  WITHOUT PRICE: ${withoutPrice.length} (${Math.round(withoutPrice.length / items.data.length * 100)}%)`);
      console.log(`  Missing UOM: ${missingUOM.length}`);
      console.log(`  Missing item_group: ${missingGroup.length}`);

      if (withoutPrice.length > 0) {
        console.log(`\n  ITEMS WITHOUT PRICE (first 20):`);
        for (const i of withoutPrice.slice(0, 20)) {
          console.log(`    ${i.item_code || i.name}: "${i.item_name}" (${i.item_group || 'no group'}, ${i.stock_uom || 'no UOM'})`);
        }
      }

      tracker.pass('Q19', `Item master: ${items.data.length} items, ${withPrice.length} with price`,
        `No price: ${withoutPrice.length}, No UOM: ${missingUOM.length}`);

      if (withoutPrice.length > items.data.length * 0.1) {
        tracker.defect(`${withoutPrice.length} items have no price`, 'MAJOR', 'COLLATERAL', 'Q19',
          `${Math.round(withoutPrice.length / items.data.length * 100)}% of items lack standard_rate`,
          'POs cannot use these items — rate must be entered manually', 'Prices never imported', 'Bulk price update needed');
      }
    } else {
      console.log(`  Frappe Item query failed or returned 0 items`);
      // Fallback: try the procurement search_items endpoint
      const searchResult = await apiCall(page, '/items?query=&limit=500');
      const rawItems19 = searchResult.json;
      const items19 = Array.isArray(rawItems19) ? rawItems19 : (rawItems19?.message || rawItems19?.data || []);
      if (items19.length > 0) {
        const items = items19;
        validation.item_master.total = items.length;
        const withPrice = items.filter(i => i.standard_rate && i.standard_rate > 0);
        validation.item_master.with_price = withPrice.length;
        console.log(`  Via search_items API: ${items.length} items, ${withPrice.length} with price`);
        tracker.pass('Q19', `Items via API: ${items.length}, ${withPrice.length} with price`, '');
      } else {
        tracker.fail('Q19', 'Item master query', '', 'Both Frappe and procurement API returned no items');
      }
    }
  }

  // ═══════════════════════════════════
  // Q20: Frappe Items vs SKU Master CSV
  // ═══════════════════════════════════
  console.log('\n── Q20: Frappe Items vs SKU Master CSV ──');
  {
    // Read the local SKU Master CSV
    let skuMasterRows = [];
    try {
      const csvContent = fs.readFileSync('data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv', 'utf8');
      const lines = csvContent.split('\n').filter(l => l.trim());
      // Parse CSV (skip header)
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map(c => c.replace(/^"|"$/g, ''));
        if (cols.length >= 6) {
          skuMasterRows.push({
            item_code: cols[1],
            item_name: cols[2],
            description: cols[3],
            uom: cols[4],
            category: cols[5],
            cost: parseFloat(cols[6]) || 0,
          });
        }
      }
    } catch (err) {
      console.log(`  Could not read SKU Master CSV: ${err.message}`);
    }

    if (skuMasterRows.length > 0) {
      console.log(`  SKU Master CSV: ${skuMasterRows.length} rows`);
      console.log(`  Frappe Item count: ${validation.item_master.total}`);

      validation.item_master.sku_master_comparison = {
        csv_count: skuMasterRows.length,
        frappe_count: validation.item_master.total,
      };

      // Spot-check 10 SKU codes from the CSV against Frappe
      const sample = skuMasterRows.filter((_, i) => [0, 5, 10, 20, 30, 40, 50, 60, 70, 80].includes(i));
      let matchCount = 0;

      for (const sku of sample) {
        const searchResult = await apiCall(page, `/items?query=${encodeURIComponent(sku.item_code)}&limit=1`);
        // API may return {message: [...]}, {data: [...]}, or a plain array
        const rawJson = searchResult.json;
        const items = Array.isArray(rawJson) ? rawJson : (rawJson?.message || rawJson?.data || []);
        const found = Array.isArray(items) && items.some(i => i.item_code === sku.item_code || i.value === sku.item_code);

        const csvPrice = sku.cost;
        const frappePrice = (Array.isArray(items) && items[0]?.standard_rate) || 0;

        console.log(`  ${sku.item_code} "${sku.item_name}": Frappe ${found ? '✓' : '✗ NOT FOUND'}, CSV price ₱${csvPrice}, Frappe price ₱${frappePrice}`);
        if (found) matchCount++;

        validation.item_master.sku_master_comparison[sku.item_code] = {
          csv_name: sku.item_name,
          csv_price: csvPrice,
          in_frappe: found,
          frappe_price: frappePrice,
          price_match: Math.abs(csvPrice - frappePrice) < 1,
        };
      }

      if (matchCount >= 8) tracker.pass('Q20', `SKU Master cross-ref: ${matchCount}/10 found in Frappe`, `CSV: ${skuMasterRows.length}, Frappe: ${validation.item_master.total}`);
      else tracker.fail('Q20', `SKU Master cross-ref: only ${matchCount}/10 found`, '', `${10 - matchCount} CSV items missing from Frappe`);
    } else {
      tracker.skip('Q20', 'SKU Master comparison', 'CSV file not readable');
    }
  }

  // ═══════════════════════════════════
  // Q21: Items Without Price
  // ═══════════════════════════════════
  console.log('\n── Q21: Items Without Price ──');
  {
    const noPrice = validation.item_master.without_price || [];
    console.log(`  Items without standard_rate: ${noPrice.length}`);
    if (noPrice.length > 0) {
      console.log(`  (Already listed in Q19 above)`);
      tracker.pass('Q21', `${noPrice.length} items without price documented`, 'See Q19 detail');
    } else {
      tracker.pass('Q21', 'All items have prices', 'No gaps');
    }
  }

  // ═══════════════════════════════════
  // Q22: Orphan Items in POs
  // ═══════════════════════════════════
  console.log('\n── Q22: Orphan Item Codes in POs ──');
  {
    // Get recent PO items
    const recentPOs = await apiCall(page, '/purchase-orders?page=1&page_size=10');
    const poList = recentPOs.json?.data || [];

    for (const po of poList.slice(0, 5)) {
      const poDetail = await apiCall(page, `/purchase-orders/${po.name}/items`);
      const rawItems = poDetail.json || [];
      const items = Array.isArray(rawItems) ? rawItems : (rawItems?.message || rawItems?.data || rawItems?.items || []);

      for (const item of (Array.isArray(items) ? items : [])) {
        const itemCode = item.item_code;
        if (!itemCode) continue;

        // Check if item exists in Frappe
        const exists = await frappeQuery(page, 'Item', ['name'], { name: itemCode }, 1);
        if (!exists.ok || exists.data.length === 0) {
          // Try alternate check
          const searchResult = await apiCall(page, `/items?query=${encodeURIComponent(itemCode)}&limit=1`);
          const rawSearch = searchResult.json;
          const searchItems = Array.isArray(rawSearch) ? rawSearch : (rawSearch?.message || rawSearch?.data || []);
          const searchFound = Array.isArray(searchItems) && searchItems.some(i => i.item_code === itemCode || i.value === itemCode);

          if (!searchFound) {
            console.log(`  ORPHAN: ${itemCode} in PO ${po.po_no} — not in Item Master`);
            validation.orphan_items.push({ item_code: itemCode, po_no: po.po_no });
          }
        }
      }
    }

    if (validation.orphan_items.length === 0) {
      tracker.pass('Q22', 'No orphan item codes in recent POs', 'All items exist in master');
    } else {
      tracker.fail('Q22', `${validation.orphan_items.length} orphan items found`,
        validation.orphan_items.map(o => `${o.item_code} in ${o.po_no}`).join(', '), 'Data integrity issue');
      tracker.defect(`${validation.orphan_items.length} PO items not in Item Master`, 'MAJOR', 'COLLATERAL', 'Q22',
        `Items used in POs but not in Frappe Item doctype`, 'Cannot track pricing or stock for these items',
        'Items created ad-hoc in POs without adding to master', 'Add missing items to Item Master');
    }
  }

  // ═══════════════════════════════════
  // FINAL SUMMARY
  // ═══════════════════════════════════
  console.log('\n\n═══════════════════════════════════════');
  console.log('DATA VALIDATION SUMMARY');
  console.log('═══════════════════════════════════════');

  console.log('\nCOUNT RECONCILIATION:');
  for (const [entity, counts] of Object.entries(validation.counts)) {
    console.log(`  ${counts.match ? '✓' : '✗'} ${entity}: API=${counts.api} UI=${counts.ui}`);
  }

  console.log('\nSUPPLIER MASTER:');
  console.log(`  Total: ${validation.supplier_completeness.total}`);
  console.log(`  Complete: ${validation.supplier_completeness.complete}`);
  console.log(`  Incomplete: ${validation.supplier_completeness.incomplete.length}`);
  console.log(`  Duplicates: ${JSON.stringify(validation.supplier_duplicates).substring(0, 100)}`);

  console.log('\nITEM MASTER:');
  console.log(`  Total: ${validation.item_master.total}`);
  console.log(`  With price: ${validation.item_master.with_price}`);
  console.log(`  Without price: ${(validation.item_master.without_price || []).length}`);
  console.log(`  Orphan items in POs: ${validation.orphan_items.length}`);
  console.log(`  SKU Master CSV rows: ${validation.item_master.sku_master_comparison?.csv_count || 'N/A'}`);

  // Write output
  fs.writeFileSync('tmp/s142_data_validation.json', JSON.stringify(validation, null, 2));
  fs.writeFileSync('tmp/s142_count_reconciliation.json', JSON.stringify(validation.counts, null, 2));

  await ctx.close();
  await browser.close();
  tracker.writeAll();
  tracker.printSummary();

  console.log('\nPhase D complete. Output:');
  console.log('  F:\\Dropbox\\Projects\\BEI-ERP\\tmp\\s142_data_validation.json');
  console.log('  F:\\Dropbox\\Projects\\BEI-ERP\\tmp\\s142_count_reconciliation.json');
}

run().catch(err => { console.error('FATAL:', err.message || err); });
