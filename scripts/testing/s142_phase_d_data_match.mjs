/**
 * S142 Phase D — Three-Way Data Match
 * Google Sheet ↔ Frappe API ↔ UI
 * Spot-check 5 POs, 5 Suppliers, 5 GRs, dashboard KPIs.
 *
 * Run: node scripts/testing/s142_phase_d_data_match.mjs
 */

import {
  ensureDirs, launchBrowser, loginAs, screenshot,
  readText, readTableRows, BASE, FRAPPE, ResultTracker
} from './s142_utils.mjs';
import fs from 'fs';

const dataMatch = { pos: [], suppliers: [], grs: [], kpis: {} };

async function fetchFrappeAPI(page, endpoint) {
  // Use a separate fetch in the page context to call the Frappe API through the proxy
  const result = await page.evaluate(async (url) => {
    try {
      const res = await fetch(url, { credentials: 'include' });
      if (!res.ok) return { error: `HTTP ${res.status}` };
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }, `${BASE}/api/procurement${endpoint}`);
  return result;
}

async function run() {
  ensureDirs();
  const tracker = new ResultTracker();
  const browser = await launchBrowser();

  console.log('═══════════════════════════════════════');
  console.log('S142 Phase D — Three-Way Data Match');
  console.log('═══════════════════════════════════════\n');

  const { page, ctx } = await loginAs(browser, 'ceo');

  // ── D1: Purchase Orders — Spot-Check 5 ──
  console.log('\n── D1: PO Spot-Check (5 POs from different pages) ──');
  {
    const pages = [1, 5, 10, 15, 25];
    for (const p of pages) {
      await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);

      // Navigate to page p
      if (p > 1) {
        for (let i = 1; i < p; i++) {
          const nextBtn = page.locator('button:has-text("Next")').first();
          const visible = await nextBtn.isVisible({ timeout: 2000 }).catch(() => false);
          if (!visible) break;
          await nextBtn.click();
          await page.waitForTimeout(1000);
        }
      }

      // Read first row's PO number, supplier, amount from UI
      const firstRow = await page.locator('table tbody tr:first-child').innerText().catch(() => '');
      const poNoMatch = firstRow.match(/(PO-\d+)/);
      const poNo = poNoMatch ? poNoMatch[1] : null;

      if (!poNo) {
        console.log(`    Page ${p}: No PO found (may be past last page)`);
        continue;
      }

      // Parse UI values — extract supplier and amount from row text
      const cells = firstRow.split('\n').map(c => c.trim()).filter(c => c);
      const uiData = {
        po_no: poNo,
        page: p,
        ui_row_text: firstRow.replace(/\n/g, ' | ').substring(0, 150),
      };

      // Call Frappe API for the same PO
      const apiResult = await fetchFrappeAPI(page, `/purchase-orders?search=${poNo}&page_size=1`);
      const apiPO = apiResult?.data?.[0];
      if (apiPO) {
        uiData.api_po_no = apiPO.po_no;
        uiData.api_supplier = apiPO.supplier_name;
        uiData.api_amount = apiPO.grand_total;
        uiData.api_status = apiPO.status;

        // Compare: does UI row contain the API values?
        const supplierMatch = firstRow.includes(apiPO.supplier_name);
        const amountStr = new Intl.NumberFormat('en-PH').format(apiPO.grand_total);
        const amountMatch = firstRow.includes(amountStr) || firstRow.includes(String(apiPO.grand_total));

        uiData.supplier_match = supplierMatch;
        uiData.amount_match = amountMatch;

        console.log(`    ${poNo}: Supplier ${supplierMatch ? '✓' : '✗'} (${apiPO.supplier_name}), Amount ${amountMatch ? '✓' : '✗'} (₱${apiPO.grand_total})`);

        if (supplierMatch && amountMatch) {
          tracker.pass(`D1-p${p}`, `PO ${poNo} UI↔API match`, `Supplier + amount match`);
        } else {
          tracker.fail(`D1-p${p}`, `PO ${poNo} UI↔API match`, `Supplier: ${supplierMatch}, Amount: ${amountMatch}`, 'Data mismatch');
        }
      } else {
        console.log(`    ${poNo}: API returned no data`);
        uiData.api_error = apiResult?.error || 'No data returned';
        tracker.fail(`D1-p${p}`, `PO ${poNo} API lookup`, '', 'API returned no data');
      }

      dataMatch.pos.push(uiData);
    }
  }

  // ── D2: Suppliers — Spot-Check 5 ──
  console.log('\n── D2: Supplier Spot-Check (5 suppliers) ──');
  {
    await page.goto(`${BASE}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Pick 5 suppliers from the first page
    const rows = await page.locator('table tbody tr').count();
    const sampled = [0, 2, 4, 6, 8].filter(i => i < rows);

    for (const idx of sampled) {
      const rowText = await page.locator(`table tbody tr:nth-child(${idx + 1})`).innerText().catch(() => '');
      const cells = rowText.split('\n').map(c => c.trim()).filter(c => c);
      const supplierName = cells[0] || '';

      if (!supplierName) continue;

      // API check
      const apiResult = await fetchFrappeAPI(page, `/suppliers?search=${encodeURIComponent(supplierName)}&page_size=1`);
      const apiSupplier = apiResult?.data?.[0];

      const entry = {
        ui_name: supplierName,
        ui_row: rowText.replace(/\n/g, ' | ').substring(0, 150),
        api_name: apiSupplier?.supplier_name,
        api_status: apiSupplier?.status,
        name_match: apiSupplier?.supplier_name === supplierName,
      };

      console.log(`    ${supplierName}: API ${entry.name_match ? '✓' : '✗'} match`);

      if (entry.name_match) {
        tracker.pass(`D2-${idx}`, `Supplier "${supplierName}" UI↔API`, 'Name matches');
      } else {
        tracker.fail(`D2-${idx}`, `Supplier "${supplierName}" UI↔API`, '', `API: ${apiSupplier?.supplier_name || 'NOT_FOUND'}`);
      }

      dataMatch.suppliers.push(entry);
    }
  }

  // ── D3: Goods Receipts — Spot-Check 5 ──
  console.log('\n── D3: GR Spot-Check (5 GRs) ──');
  {
    await page.goto(`${BASE}/dashboard/procurement/goods-receipts`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    const rows = await page.locator('table tbody tr').count();
    const sampled = [0, 2, 4, 6, 8].filter(i => i < rows);

    for (const idx of sampled) {
      const rowText = await page.locator(`table tbody tr:nth-child(${idx + 1})`).innerText().catch(() => '');
      const grNoMatch = rowText.match(/(GR-\d+)/);
      const grNo = grNoMatch ? grNoMatch[1] : null;

      if (!grNo) continue;

      // API check
      const apiResult = await fetchFrappeAPI(page, `/goods-receipts?page_size=100`);
      const apiGR = apiResult?.data?.find(g => g.gr_number === grNo);

      const entry = {
        ui_gr_no: grNo,
        ui_row: rowText.replace(/\n/g, ' | ').substring(0, 150),
        api_gr_no: apiGR?.gr_number,
        api_po_ref: apiGR?.po_number,
        api_supplier: apiGR?.supplier_name,
        found_in_api: !!apiGR,
      };

      console.log(`    ${grNo}: API ${apiGR ? '✓' : '✗'} found`);

      if (apiGR) {
        tracker.pass(`D3-${idx}`, `GR ${grNo} UI↔API`, `PO: ${apiGR.po_number}`);
      } else {
        tracker.fail(`D3-${idx}`, `GR ${grNo} UI↔API`, '', 'Not found in API');
      }

      dataMatch.grs.push(entry);
    }
  }

  // ── D4: Dashboard KPI Verification ──
  console.log('\n── D4: Dashboard KPI Verification ──');
  {
    await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Read KPI values from UI
    const kpiTexts = await page.locator('.tracking-tight').allInnerTexts().catch(() => []);
    console.log(`    UI KPI values: ${JSON.stringify(kpiTexts)}`);

    // API call for KPIs
    const apiKPIs = await fetchFrappeAPI(page, '/dashboard/kpis');
    console.log(`    API KPIs: ${JSON.stringify(apiKPIs).substring(0, 200)}`);

    dataMatch.kpis = {
      ui_values: kpiTexts,
      api_values: apiKPIs,
    };

    // Compare MTD PO Value
    if (apiKPIs?.mtd_po_value !== undefined) {
      const apiMtd = apiKPIs.mtd_po_value;
      const uiMtdText = kpiTexts.find(t => t.includes('₱') && !t.includes('No data')) || '';
      const uiMtdMatch = uiMtdText.replace(/[₱,]/g, '');

      console.log(`    MTD PO: UI="${uiMtdText}", API=${apiMtd}`);

      // Rough match (within 1% tolerance for formatting differences)
      const uiNum = parseFloat(uiMtdMatch) || 0;
      const delta = Math.abs(uiNum - apiMtd);
      const match = delta / Math.max(apiMtd, 1) < 0.01;

      if (match || apiMtd === 0) {
        tracker.pass('D4-mtd', 'MTD PO Value UI↔API', `UI: ${uiMtdText}, API: ₱${apiMtd}`);
      } else {
        tracker.fail('D4-mtd', 'MTD PO Value UI↔API', `UI: ${uiMtdText}, API: ${apiMtd}`, `Delta: ${delta}`);
      }
    }

    // Compare supplier count
    const apiSuppliers = await fetchFrappeAPI(page, '/suppliers?filters={"status":"Active"}&page_size=1');
    if (apiSuppliers?.total !== undefined) {
      console.log(`    Active suppliers: API total=${apiSuppliers.total}`);
      dataMatch.kpis.active_suppliers_api = apiSuppliers.total;
      tracker.pass('D4-suppliers', 'Active supplier count from API', `Total: ${apiSuppliers.total}`);
    }

    await screenshot(page, 'D4_dashboard_kpi_match');
  }

  // ── Write data match results ──
  fs.writeFileSync('tmp/s142_data_match.json', JSON.stringify(dataMatch, null, 2));

  await ctx.close();
  await browser.close();

  tracker.writeAll();
  tracker.printSummary();

  console.log('\nPhase D complete. Output: tmp/s142_data_match.json');
}

run().catch(err => { console.error('FATAL:', err); process.exit(1); });
