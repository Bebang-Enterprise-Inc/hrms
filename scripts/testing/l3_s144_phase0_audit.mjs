/**
 * S144 Phase 0 — Comprehensive supplier page browser audit
 * Catches ALL defects before coding starts.
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'https://my.bebang.ph';
const OUT = 'F:/Dropbox/Projects/BEI-ERP/output/l3/S144';
const findings = [];

function finding(page, category, severity, description, evidence) {
  const f = { page, category, severity, description, evidence, timestamp: new Date().toISOString() };
  findings.push(f);
  console.log(`  [${severity}] ${description}`);
}

async function shot(page, name) {
  const p = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  return p;
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  if (!page.url().includes('/login')) return true;
  await page.fill('input[name="email"]', 'sam@bebang.ph');
  await page.fill('input[name="password"]', '2289454');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);
  return !page.url().includes('/login');
}

async function auditSupplierList(page) {
  console.log('\n=== AUDIT: Supplier List Page ===');
  await page.goto(`${BASE_URL}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, 'audit_supplier_list');

  // 1. Check total count in stats card
  const statsTexts = await page.evaluate(() => {
    const cards = document.querySelectorAll('[class*="CardContent"]');
    return Array.from(cards).map(c => c.textContent.trim());
  });
  console.log(`  Stats cards: ${JSON.stringify(statsTexts.slice(0, 4))}`);

  // 2. Check status filter options
  const filterSelect = page.locator('select, [role="combobox"]').nth(0);
  let statusOptions = [];
  try {
    // Try clicking the select to see options
    const selectTrigger = page.locator('[role="combobox"], button:has-text("All Statuses"), button:has-text("Filter")').first();
    if (await selectTrigger.isVisible()) {
      await selectTrigger.click();
      await page.waitForTimeout(500);
      statusOptions = await page.evaluate(() => {
        const items = document.querySelectorAll('[role="option"]');
        return Array.from(items).map(i => i.textContent.trim());
      });
      // Close dropdown
      await page.keyboard.press('Escape');
    }
  } catch (e) { /* ignore */ }
  console.log(`  Status filter options: ${JSON.stringify(statusOptions)}`);

  const hasPendingVerification = statusOptions.some(o => o.includes('Pending'));
  if (!hasPendingVerification) {
    finding('supplier-list', 'UX', 'MAJOR', 'Status filter missing "Pending Verification" — 89 of 91 suppliers cannot be filtered', { options: statusOptions });
  }

  // 3. Check table data — look for zero amounts/orders
  const tableRows = await page.evaluate(() => {
    const rows = document.querySelectorAll('table tbody tr');
    return Array.from(rows).slice(0, 10).map(row => {
      const cells = Array.from(row.querySelectorAll('td'));
      return cells.map(c => c.textContent.trim());
    });
  });
  console.log(`  Table rows: ${tableRows.length}`);
  for (const row of tableRows.slice(0, 3)) {
    const orderCell = row.find(c => c.includes('orders'));
    if (orderCell) console.log(`    ${row[0]?.substring(0, 30)}: ${orderCell}`);
  }

  // 4. Check for stray "0" text in table
  const strayZeros = await page.evaluate(() => {
    const cells = document.querySelectorAll('table tbody td');
    return Array.from(cells).filter(c => c.textContent.trim() === '0').length;
  });
  if (strayZeros > 0) {
    finding('supplier-list', 'RENDERING', 'MINOR', `${strayZeros} table cells with bare "0" text`, {});
  }

  // 5. Check pagination
  const totalText = await page.evaluate(() => {
    const el = document.querySelector('main');
    const text = el?.innerText || '';
    const match = text.match(/(\d+)\s*(?:total|suppliers|results)/i);
    return match ? match[0] : 'not found';
  });
  console.log(`  Total indicator: ${totalText}`);

  // 6. Search functionality
  const searchInput = page.locator('input[placeholder*="Search"], input[placeholder*="search"]').first();
  if (await searchInput.isVisible()) {
    await searchInput.fill('ESV');
    await page.waitForTimeout(2000);
    await shot(page, 'audit_supplier_list_search');
    const searchResults = await page.evaluate(() => {
      const rows = document.querySelectorAll('table tbody tr');
      return rows.length;
    });
    console.log(`  Search "ESV": ${searchResults} results`);
    await searchInput.fill('');
    await page.waitForTimeout(1000);
  }

  // 7. Mobile viewport check
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(1000);
  await shot(page, 'audit_supplier_list_mobile');
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);
}

async function auditSupplierDetail(page) {
  console.log('\n=== AUDIT: Supplier Detail Page (1 To 1 Marketing) ===');

  // First get the supplier name/id from API
  const supplierData = await page.evaluate(async () => {
    const r = await fetch('/api/procurement/suppliers?page=1&page_size=5&search=1 To 1');
    const data = await r.json();
    return data.data?.[0] || null;
  });

  if (!supplierData) {
    finding('supplier-detail', 'DATA', 'CRITICAL', 'Cannot find "1 To 1 Marketing" via API search', {});
    return;
  }

  console.log(`  API data: total_po_count=${supplierData.total_po_count}, total_po_value=${supplierData.total_po_value}, total_amount=${supplierData.total_amount}`);

  await page.goto(`${BASE_URL}/dashboard/procurement/suppliers/${supplierData.name}`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, 'audit_supplier_detail');

  // 1. Check header for stray "0"
  const headerText = await page.evaluate(() => {
    const header = document.querySelector('h1')?.parentElement;
    return header?.textContent?.trim() || '';
  });
  console.log(`  Header: "${headerText.substring(0, 80)}"`);

  if (/Active\s*0/.test(headerText) || /0\s*Active/.test(headerText)) {
    finding('supplier-detail', 'RENDERING', 'MAJOR', '"0" rendered next to Active badge (is_new_supplier {0 && <JSX>} bug)', { headerText });
  }

  // 2. Check stats cards
  const statsData = await page.evaluate(() => {
    const cards = document.querySelectorAll('main [class*="Card"]');
    const stats = {};
    for (const card of cards) {
      const text = card.textContent.trim();
      if (text.includes('Total Orders')) {
        const val = text.match(/(\d+)\s*Total Orders/);
        stats.totalOrders = val ? val[1] : text.substring(0, 50);
      }
      if (text.includes('Total Amount')) {
        const val = text.match(/(₱[\d,]+)\s*Total Amount/);
        stats.totalAmount = val ? val[1] : text.substring(0, 50);
      }
      if (text.includes('Outstanding')) {
        stats.outstanding = text.substring(0, 50);
      }
      if (text.includes('Rating')) {
        stats.rating = text.substring(0, 50);
      }
    }
    return stats;
  });
  console.log(`  Stats: ${JSON.stringify(statsData)}`);

  if (statsData.totalOrders === '0' && supplierData.total_po_count > 0) {
    finding('supplier-detail', 'DATA', 'CRITICAL',
      `Total Orders shows 0 but API has ${supplierData.total_po_count} POs (field name mismatch: frontend reads total_orders, API returns total_po_count)`,
      { displayed: statsData.totalOrders, actual: supplierData.total_po_count });
  }

  if (statsData.totalAmount?.includes('₱0') && supplierData.total_po_value > 0) {
    finding('supplier-detail', 'DATA', 'CRITICAL',
      `Total Amount shows ₱0 but API has ₱${Number(supplierData.total_po_value).toLocaleString()} (field name mismatch)`,
      { displayed: statsData.totalAmount, actual: supplierData.total_po_value });
  }

  // 3. Check tabs exist
  const tabs = await page.evaluate(() => {
    const tablist = document.querySelectorAll('[role="tab"]');
    return Array.from(tablist).map(t => t.textContent.trim());
  });
  console.log(`  Tabs: ${JSON.stringify(tabs)}`);

  const hasItemsTab = tabs.some(t => t.toLowerCase().includes('item'));
  if (!hasItemsTab) {
    finding('supplier-detail', 'FEATURE', 'MAJOR', 'No "Items" tab — cannot see items purchased from this supplier', { tabs });
  }

  // 4. Check Purchase Orders tab
  const poTab = page.locator('[role="tab"]:has-text("Purchase Orders")').first();
  if (await poTab.isVisible()) {
    await poTab.click();
    await page.waitForTimeout(2000);
    await shot(page, 'audit_supplier_detail_pos');

    const poRows = await page.evaluate(() => {
      const rows = document.querySelectorAll('table tbody tr');
      return rows.length;
    });
    console.log(`  PO tab: ${poRows} rows`);
    if (poRows === 0 && supplierData.total_po_count > 0) {
      finding('supplier-detail', 'DATA', 'MAJOR', 'Purchase Orders tab shows empty but supplier has POs', {});
    }
  }

  // 5. Check Invoices tab
  const invTab = page.locator('[role="tab"]:has-text("Invoices")').first();
  if (await invTab.isVisible()) {
    await invTab.click();
    await page.waitForTimeout(2000);
    await shot(page, 'audit_supplier_detail_invoices');
  }

  // 6. Check Documents tab
  const docTab = page.locator('[role="tab"]:has-text("Documents")').first();
  if (await docTab.isVisible()) {
    await docTab.click();
    await page.waitForTimeout(2000);
    await shot(page, 'audit_supplier_detail_docs');
  }

  // 7. Check contact info renders
  const contactInfo = await page.evaluate(() => {
    const main = document.querySelector('main');
    const text = main?.innerText || '';
    return {
      hasEmail: text.includes('@'),
      hasPhone: /\d{10,11}/.test(text),
      hasTIN: /\d{3}-\d{3}-\d{3}/.test(text),
      hasBank: text.toLowerCase().includes('bank'),
    };
  });
  console.log(`  Contact: email=${contactInfo.hasEmail}, phone=${contactInfo.hasPhone}, TIN=${contactInfo.hasTIN}, bank=${contactInfo.hasBank}`);

  // 8. Mobile viewport
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(1000);
  await shot(page, 'audit_supplier_detail_mobile');
  await page.setViewportSize({ width: 1280, height: 800 });
}

async function auditSupplierEdit(page) {
  console.log('\n=== AUDIT: Supplier Edit Page ===');

  const supplierData = await page.evaluate(async () => {
    const r = await fetch('/api/procurement/suppliers?page=1&page_size=5&search=1 To 1');
    const data = await r.json();
    return data.data?.[0] || null;
  });

  if (!supplierData) return;

  await page.goto(`${BASE_URL}/dashboard/procurement/suppliers/${supplierData.name}/edit`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, 'audit_supplier_edit');

  // Check what fields are editable
  const editableFields = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input, select, textarea');
    return Array.from(inputs).map(i => ({
      name: i.name || i.id || i.placeholder || 'unnamed',
      type: i.type || i.tagName,
      value: i.value?.substring(0, 30) || '',
      disabled: i.disabled,
    }));
  });
  console.log(`  Editable fields: ${editableFields.length}`);
  for (const f of editableFields.slice(0, 10)) {
    console.log(`    ${f.name}: ${f.type} = "${f.value}" ${f.disabled ? '(disabled)' : ''}`);
  }

  // Check save button
  const saveBtn = page.locator('button:has-text("Save"), button:has-text("Update"), button[type="submit"]').first();
  const hasSave = await saveBtn.isVisible().catch(() => false);
  console.log(`  Save button: ${hasSave ? 'visible' : 'NOT FOUND'}`);

  // Check: is there an approval mechanism?
  const approvalElements = await page.evaluate(() => {
    const text = document.querySelector('main')?.innerText || '';
    return {
      hasApprovalButton: text.includes('Submit for Approval'),
      hasSaveButton: text.includes('Save') || text.includes('Update'),
      hasApprovalStatus: text.includes('Pending Approval') || text.includes('Approved') || text.includes('Rejected'),
    };
  });
  console.log(`  Approval: ${JSON.stringify(approvalElements)}`);

  if (!approvalElements.hasApprovalButton) {
    finding('supplier-edit', 'FEATURE', 'MAJOR', 'No "Submit for Approval" button — edits save directly without Mae approval', { approvalElements });
  }

  // Mobile
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(1000);
  await shot(page, 'audit_supplier_edit_mobile');
  await page.setViewportSize({ width: 1280, height: 800 });
}

async function auditSupplierNew(page) {
  console.log('\n=== AUDIT: Supplier New Page ===');
  await page.goto(`${BASE_URL}/dashboard/procurement/suppliers/new`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, 'audit_supplier_new');

  const formFields = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input, select, textarea');
    return Array.from(inputs).map(i => i.name || i.placeholder || i.id || 'unnamed');
  });
  console.log(`  Form fields: ${formFields.length} — ${formFields.slice(0, 8).join(', ')}`);
}

async function auditSupplierAPI(page) {
  console.log('\n=== AUDIT: Supplier API Responses ===');

  // Check list API field names
  const listResp = await page.evaluate(async () => {
    const r = await fetch('/api/procurement/suppliers?page=1&page_size=2');
    const data = await r.json();
    if (data.data?.[0]) {
      return { fields: Object.keys(data.data[0]), sample: data.data[0] };
    }
    return null;
  });

  if (listResp) {
    console.log(`  List API fields: ${listResp.fields.join(', ')}`);
    const hasOldNames = listResp.fields.includes('total_orders');
    const hasNewNames = listResp.fields.includes('total_po_count');
    console.log(`  Has total_orders: ${hasOldNames}, Has total_po_count: ${hasNewNames}`);
    console.log(`  Sample: total_po_count=${listResp.sample.total_po_count}, total_amount=${listResp.sample.total_amount}`);
  }

  // Check single supplier API
  const singleResp = await page.evaluate(async () => {
    const list = await fetch('/api/procurement/suppliers?page=1&page_size=1&search=1 To 1');
    const listData = await list.json();
    const name = listData.data?.[0]?.name;
    if (!name) return null;
    const r = await fetch(`/api/procurement/suppliers/${name}`);
    const data = await r.json();
    return { fields: Object.keys(data), hasTotalOrders: 'total_orders' in data, hasTotalPoCount: 'total_po_count' in data, total_po_count: data.total_po_count, total_po_value: data.total_po_value, total_orders: data.total_orders, total_amount: data.total_amount };
  });

  if (singleResp) {
    console.log(`  Single API: total_orders=${singleResp.total_orders}, total_po_count=${singleResp.total_po_count}, total_amount=${singleResp.total_amount}, total_po_value=${singleResp.total_po_value}`);

    if (singleResp.total_orders === undefined && singleResp.total_po_count > 0) {
      finding('supplier-api', 'DATA', 'CRITICAL',
        `Single supplier API returns total_po_count=${singleResp.total_po_count} but no total_orders field. Frontend reads total_orders → shows 0.`,
        singleResp);
    }
  }

  // Check supplier items endpoint (should not exist yet)
  const itemsResp = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/procurement/suppliers/1T1MI3/items');
      return { status: r.status, ok: r.ok };
    } catch { return { status: 'error' }; }
  });
  console.log(`  Supplier items API: ${itemsResp.status} (expected 404 — not built yet)`);
}

// Main
(async () => {
  console.log('S144 Phase 0 — Supplier Page Comprehensive Audit');
  console.log(`Output: ${OUT}\n`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  try {
    const loggedIn = await login(page);
    if (!loggedIn) { console.log('FATAL: Login failed'); process.exit(1); }

    await auditSupplierList(page);
    await auditSupplierDetail(page);
    await auditSupplierEdit(page);
    await auditSupplierNew(page);
    await auditSupplierAPI(page);

    // Summary
    console.log('\n=== AUDIT SUMMARY ===');
    console.log(`Total findings: ${findings.length}`);
    const bySeverity = {};
    for (const f of findings) {
      bySeverity[f.severity] = (bySeverity[f.severity] || 0) + 1;
    }
    console.log(`By severity: ${JSON.stringify(bySeverity)}`);

    for (const f of findings) {
      console.log(`  [${f.severity}] ${f.page}: ${f.description}`);
    }

    // Write findings
    fs.writeFileSync(path.join(OUT, 'phase0_audit_findings.json'), JSON.stringify(findings, null, 2));
    console.log(`\nFindings written to ${OUT}/phase0_audit_findings.json`);

  } finally {
    await browser.close();
  }
})();
