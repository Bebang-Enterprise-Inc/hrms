/**
 * L3 S139: Inventory Sync Verification
 * Tests: store ordering pages show stock, inventory dashboard works, no regressions
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_WEB = 'https://my.bebang.ph';
const BASE_API = 'https://hq.bebang.ph';
const OUTPUT_DIR = 'output/l3/S139';
const EVIDENCE_DIR = path.join(OUTPUT_DIR, 'evidence');
const ARTIFACTS_DIR = path.join(OUTPUT_DIR, 'artifacts');

const results = [];

function record(scenario, type, test, status, detail, error = null) {
  results.push({ scenario, type, test, status, detail, error });
  console.log(`[${status}] ${scenario}: ${test}`);
  if (error) console.log(`  Error: ${error}`);
}

async function loginUI(page, email, password = 'BeiTest2026!') {
  await page.goto(`${BASE_WEB}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('input[autocomplete="username"], input[name="email"]').first().fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/dashboard**', { timeout: 30000 });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();

  // ── Login as store staff ──
  try {
    await loginUI(page, 'test.staff@bebang.ph');
    record('S139-LOGIN', 'setup', 'Login as store staff', 'PASS', 'Logged in successfully');
  } catch (e) {
    record('S139-LOGIN', 'setup', 'Login as store staff', 'FAIL', 'Login failed', e.message);
    await browser.close();
    fs.writeFileSync(path.join(OUTPUT_DIR, 'results.json'), JSON.stringify(results, null, 2));
    process.exit(1);
  }

  // ── INV-001: Inventory landing page ──
  try {
    await page.goto(`${BASE_WEB}/dashboard/inventory`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'INV-001-landing.png'), fullPage: true });

    const pageText = await page.textContent('body');
    const hasInventoryContent = pageText.includes('Inventory') || pageText.includes('inventory') || pageText.includes('Stock');
    record('INV-001', 'workflow-surface', 'Inventory landing page loads',
      hasInventoryContent ? 'PASS' : 'FAIL',
      hasInventoryContent ? 'Inventory page rendered with content' : 'No inventory content found');
  } catch (e) {
    record('INV-001', 'workflow-surface', 'Inventory landing page loads', 'FAIL', 'Page failed to load', e.message);
  }

  // ── INV-002: Store ordering page with stock data ──
  try {
    await page.goto(`${BASE_WEB}/dashboard/inventory/ordering`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'INV-002-ordering.png'), fullPage: true });

    const pageText = await page.textContent('body');
    // Check for stock-related content: "On Hand", qty numbers, item codes
    const hasStockData = pageText.includes('On Hand') || pageText.includes('Suggested') ||
                         pageText.includes('CM') || /\d+\.\d+/.test(pageText);
    record('INV-002', 'workflow-surface', 'Store ordering page shows stock data',
      hasStockData ? 'PASS' : 'FAIL',
      hasStockData ? 'Ordering page has stock/item data' : 'No stock data visible on ordering page');
  } catch (e) {
    record('INV-002', 'workflow-surface', 'Store ordering page', 'FAIL', 'Page failed', e.message);
  }

  // ── Backend verification via separate authenticated Frappe context ──
  const apiContext = await browser.newContext({ ignoreHTTPSErrors: true });
  const apiPage = await apiContext.newPage();

  // Login to Frappe for API checks via POST
  await apiPage.request.post(`${BASE_API}/api/method/login`, {
    form: { usr: 'test.warehouse@bebang.ph', pwd: 'BeiTest2026!' }
  });

  // ── S139-VERIFY-1: Backend stock verification (API GET — allowed in L3 for verification) ──
  try {
    const apiResp = await apiPage.request.get(`${BASE_API}/api/resource/Bin?filters=[["actual_qty",">",0]]&limit_page_length=0&fields=["warehouse"]&group_by=warehouse`);
    const apiData = await apiResp.json();
    const warehouses = apiData.data || [];
    const beiStores = warehouses.filter(w => w.warehouse.endsWith('- BEI'));
    const bkiWarehouses = warehouses.filter(w => w.warehouse.endsWith('- BKI'));

    const detail = `${beiStores.length} BEI stores, ${bkiWarehouses.length} BKI warehouses, ${warehouses.length} total with stock`;
    record('S139-VERIFY-1', 'state-verification', 'Warehouses with stock coverage',
      beiStores.length >= 30 ? 'PASS' : 'FAIL', detail,
      beiStores.length < 30 ? `Only ${beiStores.length} BEI stores have stock, expected >=30` : null);

    const stateVerification = {
      check: 'Warehouses with stock > 0',
      bei_stores: beiStores.length,
      bki_warehouses: bkiWarehouses.length,
      total: warehouses.length,
      bei_store_names: beiStores.map(w => w.warehouse).sort(),
      passed: beiStores.length >= 30
    };
    fs.writeFileSync(path.join(EVIDENCE_DIR, 'S139-VERIFY-1.json'), JSON.stringify(stateVerification, null, 2));
  } catch (e) {
    record('S139-VERIFY-1', 'state-verification', 'Warehouses with stock coverage', 'FAIL', 'API call failed', e.message);
  }

  // ── S139-VERIFY-2: Total Bin count ──
  try {
    const countResp = await apiPage.request.get(`${BASE_API}/api/method/frappe.client.get_count?doctype=Bin&filters={"actual_qty":[">",0]}`);
    const countData = await countResp.json();
    const totalBins = countData.message;

    record('S139-VERIFY-2', 'state-verification', 'Total Bins with stock',
      totalBins > 1000 ? 'PASS' : 'FAIL',
      `${totalBins} Bins with stock > 0`,
      totalBins <= 1000 ? `Only ${totalBins} Bins, expected >1000` : null);
  } catch (e) {
    record('S139-VERIFY-2', 'state-verification', 'Total Bin count', 'FAIL', 'Count failed', e.message);
  }

  // ── S139-VERIFY-3: Procurement sync not broken (check Suppliers exist) ──
  try {
    // Use "Supplier" DocType (accessible to warehouse role) instead of "BEI Supplier"
    const suppResp = await apiPage.request.get(`${BASE_API}/api/method/frappe.client.get_count?doctype=Supplier`);
    const suppData = await suppResp.json();
    const suppCount = suppData.message;

    record('S139-VERIFY-3', 'state-verification', 'Procurement sync intact (Suppliers exist)',
      suppCount > 50 ? 'PASS' : 'FAIL',
      `${suppCount} Suppliers in system`,
      suppCount <= 50 ? `Only ${suppCount} suppliers, sync may be broken` : null);
  } catch (e) {
    record('S139-VERIFY-3', 'state-verification', 'Procurement sync check', 'FAIL', 'Check failed', e.message);
  }

  // ── S139-VERIFY-4: Stock Reconciliation records exist (proves sync ran) ──
  try {
    const srResp = await apiPage.request.get(`${BASE_API}/api/method/frappe.client.get_count?doctype=Stock Reconciliation`);
    const srData = await srResp.json();
    const srCount = srData.message;

    record('S139-VERIFY-4', 'state-verification', 'Stock Reconciliation records exist (sync proof)',
      srCount > 10 ? 'PASS' : 'FAIL',
      `${srCount} Stock Reconciliation records`,
      srCount <= 10 ? `Only ${srCount} SR records, expected >10` : null);
  } catch (e) {
    record('S139-VERIFY-4', 'state-verification', 'Stock Reconciliation check', 'FAIL', 'Check failed', e.message);
  }

  await apiContext.close();

  // ── Write results ──
  const date = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(path.join(OUTPUT_DIR, `inventory_${date}.json`), JSON.stringify(results, null, 2));

  // Write form_submissions.json (L3 evidence gate)
  fs.writeFileSync(path.join(OUTPUT_DIR, 'form_submissions.json'), JSON.stringify([], null, 2)); // No form submissions for infra sprint

  // Write api_mutations.json
  fs.writeFileSync(path.join(OUTPUT_DIR, 'api_mutations.json'), JSON.stringify([], null, 2)); // No mutations for infra sprint

  // Write state_verification.json
  const stateVerifications = results
    .filter(r => r.type === 'state-verification')
    .map(r => ({
      check: r.test,
      before: 'N/A (infrastructure sprint)',
      after: r.detail,
      passed: r.status === 'PASS'
    }));
  fs.writeFileSync(path.join(OUTPUT_DIR, 'state_verification.json'), JSON.stringify(stateVerifications, null, 2));

  // ── Summary ──
  console.log(`\n${'='.repeat(50)}`);
  console.log(`L3 S139 RESULTS (${date})`);
  console.log('='.repeat(50));

  let pass = 0, fail = 0;
  for (const r of results) {
    console.log(`[${r.status}] ${r.scenario}: ${r.test}`);
    if (r.status === 'PASS') pass++;
    else fail++;
  }

  console.log(`\nTotal: ${pass}/${results.length} PASS, ${fail} FAIL`);

  await browser.close();
  process.exit(fail > 0 ? 1 : 0);
})();
