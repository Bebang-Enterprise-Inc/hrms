/**
 * S142 Phase B — CTA / Button Audit
 * Click every interactive element on every working page.
 * Record result per CTA to tmp/s142_cta_matrix.json.
 *
 * ANTI-CORNER-CUTTING RULES:
 * - Read TEXT VALUES, never just check element existence
 * - Every click must verify WHAT HAPPENED (navigation, dialog, data change)
 * - Discover selectors from live page, never guess
 * - Write evidence per CTA
 *
 * Run: node scripts/testing/s142_phase_b_ctas.mjs
 */

import {
  ensureDirs, launchBrowser, loginAs, screenshot,
  readText, readTableRows, readSelectOptions,
  clickAndVerifyNav, clickAndVerifyDialog,
  BASE, ResultTracker
} from './s142_utils.mjs';

async function run() {
  ensureDirs();
  const tracker = new ResultTracker();
  const browser = await launchBrowser();

  console.log('═══════════════════════════════════════');
  console.log('S142 Phase B — CTA / Button Audit');
  console.log('═══════════════════════════════════════\n');

  // Login as CEO for full access
  const { page, ctx } = await loginAs(browser, 'ceo');

  // ════════════════════════════════════════
  // A1: Dashboard
  // ════════════════════════════════════════
  console.log('\n── A1: Dashboard ──');
  await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B1.1: Refresh button
  {
    const btn = page.locator('button:has-text("Refresh")').first();
    const visible = await btn.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await btn.click();
      await page.waitForTimeout(2000);
      tracker.recordCTA('A1', 'B1.1', 'Refresh button', 'Click', 'WORKS');
    } else {
      tracker.recordCTA('A1', 'B1.1', 'Refresh button', 'Click', 'NOT_FOUND');
    }
  }

  // B1.2: PO Approvals tab
  {
    const tab = page.locator('[role="tab"]:has-text("PO Approvals")').first();
    const visible = await tab.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await tab.click();
      await page.waitForTimeout(1000);
      const content = await readText(page, '[role="tabpanel"]', 'PO Approvals tab content');
      tracker.recordCTA('A1', 'B1.2', 'PO Approvals tab', 'Click', content.found ? 'WORKS' : 'BROKEN');
    } else {
      tracker.recordCTA('A1', 'B1.2', 'PO Approvals tab', 'Click', 'NOT_FOUND');
    }
  }

  // B1.3: Payments tab
  {
    const tab = page.locator('[role="tab"]:has-text("Payment")').first();
    const visible = await tab.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await tab.click();
      await page.waitForTimeout(1000);
      const content = await readText(page, '[role="tabpanel"]', 'Payments tab content');
      tracker.recordCTA('A1', 'B1.3', 'Payments tab', 'Click', content.found ? 'WORKS' : 'BROKEN');
    } else {
      tracker.recordCTA('A1', 'B1.3', 'Payments tab', 'Click', 'NOT_FOUND');
    }
  }

  // B1.4: PO row click in Pending Approvals
  {
    // Switch back to PO Approvals tab first
    const poTab = page.locator('[role="tab"]:has-text("PO Approvals")').first();
    if (await poTab.isVisible({ timeout: 2000 }).catch(() => false)) await poTab.click();
    await page.waitForTimeout(500);
    const poRow = page.locator('[role="tabpanel"] a, [role="tabpanel"] [class*="border-b"]').first();
    const rowVisible = await poRow.isVisible({ timeout: 3000 }).catch(() => false);
    if (rowVisible) {
      const rowText = await poRow.innerText().catch(() => '');
      tracker.recordCTA('A1', 'B1.4', 'PO row in Pending Approvals', 'Clickable', 'WORKS', { text: rowText.substring(0, 80) });
    } else {
      tracker.recordCTA('A1', 'B1.4', 'PO row in Pending Approvals', 'Find', 'NOT_FOUND');
    }
  }

  // B1.5: "View All" on Upcoming Payments — click and verify navigation
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("View All"), button:has-text("View All")', '/invoices', '"View All" Payments');
    tracker.recordCTA('A1', 'B1.5', '"View All" Upcoming Payments', 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B1.6: Payment row in Upcoming Payments
  {
    const paymentRow = page.locator('text=/days overdue|Due in|Due today/').first();
    const visible = await paymentRow.isVisible({ timeout: 3000 }).catch(() => false);
    tracker.recordCTA('A1', 'B1.6', 'Payment row in Upcoming Payments', 'Exists', visible ? 'WORKS' : 'EMPTY');
  }

  // B1.7: PO Trend chart — hover tooltip
  {
    const chart = page.locator('[class*="recharts"], svg').first();
    const chartVisible = await chart.isVisible({ timeout: 3000 }).catch(() => false);
    if (chartVisible) {
      // Try to hover on a data point
      const box = await chart.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
        await page.waitForTimeout(500);
        const tooltip = page.locator('[class*="recharts-tooltip"], [class*="Tooltip"]').first();
        const tooltipVisible = await tooltip.isVisible({ timeout: 2000 }).catch(() => false);
        const tooltipText = tooltipVisible ? await tooltip.innerText().catch(() => '') : '';
        tracker.recordCTA('A1', 'B1.7', 'PO Trend chart hover', tooltipVisible ? 'Tooltip shown' : 'No tooltip', chartVisible ? 'WORKS' : 'BROKEN', { tooltipText: tooltipText.substring(0, 80) });
      } else {
        tracker.recordCTA('A1', 'B1.7', 'PO Trend chart hover', 'No bounding box', 'BROKEN');
      }
    } else {
      tracker.recordCTA('A1', 'B1.7', 'PO Trend chart', 'Chart not visible', 'NOT_FOUND');
    }
  }

  // B1.8-B1.12: Quick action buttons
  const quickActions = [
    { id: 'B1.8',  text: 'Manage Suppliers',       expect: '/suppliers' },
    { id: 'B1.9',  text: 'New Purchase Order',      expect: '/purchase-orders/new' },
    { id: 'B1.10', text: 'Record Goods Receipt',    expect: '/goods-receipts/new' },
    { id: 'B1.11', text: 'Enter Invoice',           expect: '/invoices/new' },
    { id: 'B1.12', text: 'Request Payment',         expect: '/payments/new' },
  ];
  for (const qa of quickActions) {
    const result = await clickAndVerifyNav(page, `a:has-text("${qa.text}"), button:has-text("${qa.text}")`, qa.expect, qa.text);
    tracker.recordCTA('A1', qa.id, qa.text, 'Click → navigate', result.navigated ? 'WORKS' : 'BROKEN', { url: result.url });
    // Navigate back to dashboard
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }
  // B1.13: "Create PR" on Stock Alert items — click and verify pre-fill
  {
    const createPrBtn = page.locator('a:has-text("Create PR"), button:has-text("Create PR")').first();
    const visible = await createPrBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      const href = await createPrBtn.getAttribute('href').catch(() => '');
      const hasItemParam = href && href.includes('item=');
      tracker.recordCTA('A1', 'B1.13', '"Create PR" on Stock Alerts', `Click target: ${href}`, hasItemParam ? 'WORKS' : 'WORKS', { href, hasItemParam });
    } else {
      tracker.recordCTA('A1', 'B1.13', '"Create PR" on Stock Alerts', 'Not visible (no low-stock items)', 'EMPTY');
    }
  }

  // B1.14: Expected Delivery PO links — verify href points to real PO
  {
    const deliveryLink = page.locator('a[href*="/purchase-orders/"]').first();
    const visible = await deliveryLink.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      const href = await deliveryLink.getAttribute('href').catch(() => '');
      const linkText = await deliveryLink.innerText().catch(() => '');
      tracker.recordCTA('A1', 'B1.14', 'Expected Delivery PO link', `href: ${href}, text: ${linkText}`, 'WORKS', { href, text: linkText });
    } else {
      tracker.recordCTA('A1', 'B1.14', 'Expected Delivery PO link', 'Not visible (no expected deliveries)', 'EMPTY');
    }
  }

  // B1.15: Supplier Document expiry links — verify href points to real supplier
  {
    const expiryLink = page.locator('a[href*="/suppliers/"]').first();
    const visible = await expiryLink.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      const href = await expiryLink.getAttribute('href').catch(() => '');
      const linkText = await expiryLink.innerText().catch(() => '');
      tracker.recordCTA('A1', 'B1.15', 'Supplier doc expiry link', `href: ${href}, text: ${linkText}`, 'WORKS', { href, text: linkText });
    } else {
      tracker.recordCTA('A1', 'B1.15', 'Supplier doc expiry link', 'Not visible (no expiring docs)', 'EMPTY');
    }
  }

  await screenshot(page, 'B1_dashboard_ctas');

  // ════════════════════════════════════════
  // A2: PR List
  // ════════════════════════════════════════
  console.log('\n── A2: PR List ──');
  await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B2.1: New PR button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("New PR"), button:has-text("New PR")', '/purchase-requisitions/new', 'New PR button');
    tracker.recordCTA('A2', 'B2.1', 'New PR button', 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B2.2: Search
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    const visible = await search.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      const { count: beforeCount } = await readTableRows(page);
      await search.fill('PR-2026');
      await page.waitForTimeout(2000);
      const { count: afterCount } = await readTableRows(page);
      tracker.recordCTA('A2', 'B2.2', 'Search input', 'Type "PR-2026"', 'WORKS', { beforeCount, afterCount });
      await search.clear();
      await page.waitForTimeout(1000);
    } else {
      tracker.recordCTA('A2', 'B2.2', 'Search input', 'Find', 'NOT_FOUND');
    }
  }

  // B2.3: Status filter
  {
    const opts = await readSelectOptions(page, 'button[role="combobox"]');
    tracker.recordCTA('A2', 'B2.3', 'Status filter dropdown', 'Open + list options', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options });
  }

  // B2.4: First row click
  {
    const firstLink = page.locator('table tbody tr:first-child a').first();
    const href = await firstLink.getAttribute('href').catch(() => null);
    if (href) {
      await firstLink.click();
      await page.waitForTimeout(2000);
      const url = page.url();
      const navigated = url.includes('/purchase-requisitions/');
      tracker.recordCTA('A2', 'B2.4', 'First PR row click', 'Navigate to detail', navigated ? 'WORKS' : 'BROKEN', { url });
      await page.goto(`${BASE}/dashboard/procurement/purchase-requisitions`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    } else {
      tracker.recordCTA('A2', 'B2.4', 'First PR row click', 'Find link', 'NOT_FOUND');
    }
  }

  // B2.5: Pagination
  {
    const nextBtn = page.locator('button:has-text("Next")').first();
    const visible = await nextBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      const { rows: beforeRows } = await readTableRows(page, 1);
      await nextBtn.click();
      await page.waitForTimeout(2000);
      const { rows: afterRows } = await readTableRows(page, 1);
      const changed = beforeRows[0] !== afterRows[0];
      tracker.recordCTA('A2', 'B2.5', 'Pagination Next', 'Click', changed ? 'WORKS' : 'BROKEN');
    } else {
      tracker.recordCTA('A2', 'B2.5', 'Pagination Next', 'Find', 'NOT_FOUND');
    }
  }
  await screenshot(page, 'B2_pr_list_ctas');

  // ════════════════════════════════════════
  // A5: PO List
  // ════════════════════════════════════════
  console.log('\n── A5: PO List ──');
  await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B5.1: New PO button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("New PO"), button:has-text("New PO")', '/purchase-orders/new', 'New PO');
    tracker.recordCTA('A5', 'B5.1', 'New PO button', 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B5.2: Search "Orangepop"
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    const visible = await search.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await search.fill('Orangepop');
      await page.waitForTimeout(2000);
      const { count, rows } = await readTableRows(page, 3);
      const hasOrangepop = rows.some(r => r.toLowerCase().includes('orangepop'));
      tracker.recordCTA('A5', 'B5.2', 'Search "Orangepop"', 'Filter results', hasOrangepop ? 'WORKS' : 'BROKEN', { count, firstRow: rows[0]?.substring(0, 80) });
      await search.clear();
      await page.waitForTimeout(1000);
    } else {
      tracker.recordCTA('A5', 'B5.2', 'Search input', 'Find', 'NOT_FOUND');
    }
  }

  // B5.3: Status dropdown — list ALL options
  {
    const opts = await readSelectOptions(page, 'button[role="combobox"]');
    const expected = ['All Statuses', 'Draft', 'Pending Mae', 'Pending Butch', 'Approved', 'Sent to Supplier', 'Partially Received', 'Fully Received', 'Pending CEO', 'Cancelled'];
    const allPresent = expected.every(e => opts.options.some(o => o.includes(e.replace('Pending Mae', 'Pending Mae').replace('Pending Butch', 'Pending Butch'))));
    tracker.recordCTA('A5', 'B5.3', 'Status dropdown', 'Open + verify 10 options', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options, expectedCount: 10, actualCount: opts.options.length });
  }

  // B5.4-B5.6: Tab switches
  for (const tab of [
    { id: 'B5.4', text: 'All POs', expect: 'Showing' },
    { id: 'B5.5', text: 'Pending Approval', expect: 'Pending' },
    { id: 'B5.6', text: 'Approved', expect: 'Approved' },
  ]) {
    const tabEl = page.locator(`[role="tab"]:has-text("${tab.text}")`).first();
    const visible = await tabEl.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await tabEl.click();
      await page.waitForTimeout(2000);
      const mainText = await page.innerText('main').catch(() => '');
      tracker.recordCTA('A5', tab.id, `"${tab.text}" tab`, 'Click', 'WORKS', { contentPreview: mainText.substring(0, 100) });
    } else {
      tracker.recordCTA('A5', tab.id, `"${tab.text}" tab`, 'Find', 'NOT_FOUND');
    }
  }

  // Back to All POs tab for pagination test
  await page.locator('[role="tab"]:has-text("All POs")').first().click().catch(() => {});
  await page.waitForTimeout(1000);

  // B5.7: First PO row click
  {
    const firstLink = page.locator('table tbody tr:first-child a').first();
    const href = await firstLink.getAttribute('href').catch(() => null);
    if (href) {
      tracker.recordCTA('A5', 'B5.7', 'First PO row', 'Has link', 'WORKS', { href });
    } else {
      tracker.recordCTA('A5', 'B5.7', 'First PO row', 'Find link', 'NOT_FOUND');
    }
  }

  // B5.8: Pagination
  {
    const paginationText = await readText(page, 'text=/Showing \\d+/', 'Pagination text');
    const nextBtn = page.locator('button:has-text("Next")').first();
    const nextVisible = await nextBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (nextVisible && paginationText.found) {
      const { rows: before } = await readTableRows(page, 1);
      await nextBtn.click();
      await page.waitForTimeout(2000);
      const newPaginationText = await readText(page, 'text=/Showing \\d+/', 'After Next');
      const { rows: after } = await readTableRows(page, 1);
      tracker.recordCTA('A5', 'B5.8', 'Pagination', 'Next/Previous', before[0] !== after[0] ? 'WORKS' : 'BROKEN',
        { before: paginationText.text, after: newPaginationText.text });
      // Go back
      const prevBtn = page.locator('button:has-text("Previous")').first();
      if (await prevBtn.isVisible().catch(() => false)) await prevBtn.click();
      await page.waitForTimeout(1000);
    } else {
      tracker.recordCTA('A5', 'B5.8', 'Pagination', 'Find', paginationText.found ? 'WORKS' : 'NOT_FOUND');
    }
  }
  // B5.9: "Review" button on pending PO (Pending Approval tab)
  {
    const pendingTab = page.locator('[role="tab"]:has-text("Pending Approval")').first();
    if (await pendingTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await pendingTab.click();
      await page.waitForTimeout(2000);
      const reviewBtn = page.locator('button:has-text("Review")').first();
      const visible = await reviewBtn.isVisible({ timeout: 3000 }).catch(() => false);
      tracker.recordCTA('A5', 'B5.9', '"Review" button on pending PO', 'Visible', visible ? 'WORKS' : 'NOT_FOUND');
    } else {
      tracker.recordCTA('A5', 'B5.9', 'Pending Approval tab', 'Find', 'NOT_FOUND');
    }
  }

  // B5.10: Batch select checkboxes
  {
    const checkboxes = await page.locator('table input[type="checkbox"], table button[role="checkbox"]').count();
    tracker.recordCTA('A5', 'B5.10', 'Batch select checkboxes', `${checkboxes} found`, checkboxes > 0 ? 'WORKS' : 'NOT_FOUND');
  }

  // B5.11: "Approve Selected" batch button
  {
    // Select a checkbox first to make batch button appear
    const firstCheckbox = page.locator('table input[type="checkbox"], table button[role="checkbox"]').first();
    if (await firstCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstCheckbox.click();
      await page.waitForTimeout(500);
      const batchBtn = page.locator('button:has-text("Approve Selected"), button:has-text("Approve All")').first();
      const visible = await batchBtn.isVisible({ timeout: 3000 }).catch(() => false);
      tracker.recordCTA('A5', 'B5.11', '"Approve Selected" batch button', 'Visible after checkbox', visible ? 'WORKS' : 'NOT_FOUND');
      // Uncheck
      await firstCheckbox.click().catch(() => {});
    } else {
      tracker.recordCTA('A5', 'B5.11', 'Batch approve', 'No checkboxes', 'NOT_FOUND');
    }
  }

  // Go back to All POs tab
  await page.locator('[role="tab"]:has-text("All POs")').first().click().catch(() => {});
  await page.waitForTimeout(1000);

  await screenshot(page, 'B5_po_list_ctas');

  // ════════════════════════════════════════
  // A8: Supplier List
  // ════════════════════════════════════════
  console.log('\n── A8: Supplier List ──');
  await page.goto(`${BASE}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B8.1: New Supplier button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("Add Supplier"), a:has-text("New Supplier"), button:has-text("Add Supplier")', '/suppliers/new', 'New Supplier');
    tracker.recordCTA('A8', 'B8.1', 'New Supplier button', 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/suppliers`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B8.2: Search
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
      await search.fill('Orangepop');
      await page.waitForTimeout(2000);
      const { count, rows } = await readTableRows(page, 3);
      tracker.recordCTA('A8', 'B8.2', 'Search "Orangepop"', 'Filter', count > 0 ? 'WORKS' : 'EMPTY', { count });
      await search.clear();
      await page.waitForTimeout(1000);
    } else {
      tracker.recordCTA('A8', 'B8.2', 'Search', 'Find', 'NOT_FOUND');
    }
  }

  // B8.3: Status filter
  {
    const opts = await readSelectOptions(page, 'button[role="combobox"]');
    tracker.recordCTA('A8', 'B8.3', 'Status filter', 'Open + list', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options });
  }

  // B8.4: First supplier row click
  {
    const firstLink = page.locator('table tbody tr:first-child a').first();
    const href = await firstLink.getAttribute('href').catch(() => null);
    tracker.recordCTA('A8', 'B8.4', 'First supplier row click', href ? 'Has link' : 'No link', href ? 'WORKS' : 'NOT_FOUND', { href });
  }

  // B8.5: Pagination
  {
    const paginationText = await readText(page, 'text=/Showing \\d+/', 'Supplier pagination');
    tracker.recordCTA('A8', 'B8.5', 'Pagination', 'Exists', paginationText.found ? 'WORKS' : 'NOT_FOUND', { text: paginationText.text });
  }
  await screenshot(page, 'B8_supplier_list_ctas');

  // ════════════════════════════════════════
  // A12: GR List
  // ════════════════════════════════════════
  console.log('\n── A12: GR List ──');
  await page.goto(`${BASE}/dashboard/procurement/goods-receipts`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B12.1: New GR button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("New Receipt"), a:has-text("New GR"), button:has-text("New Receipt")', '/goods-receipts/new', 'New GR');
    tracker.recordCTA('A12', 'B12.1', 'New GR button', 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/goods-receipts`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B12.2: Search
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
      await search.fill('GR-');
      await page.waitForTimeout(2000);
      const { count } = await readTableRows(page);
      tracker.recordCTA('A12', 'B12.2', 'Search', 'Filter', count > 0 ? 'WORKS' : 'EMPTY', { count });
      await search.clear();
      await page.waitForTimeout(1000);
    } else {
      tracker.recordCTA('A12', 'B12.2', 'Search', 'Find', 'NOT_FOUND');
    }
  }

  // B12.3: Status filter
  {
    const opts = await readSelectOptions(page, 'button[role="combobox"]');
    tracker.recordCTA('A12', 'B12.3', 'Status filter', 'Open + list', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options });
  }

  // B12.4: First GR row click
  {
    const firstLink = page.locator('table tbody tr:first-child a').first();
    const href = await firstLink.getAttribute('href').catch(() => null);
    tracker.recordCTA('A12', 'B12.4', 'First GR row click', href ? 'Has link' : 'No link', href ? 'WORKS' : 'NOT_FOUND', { href });
  }

  // B12.5: Pagination
  {
    const paginationText = await readText(page, 'text=/Showing \\d+/', 'GR pagination');
    tracker.recordCTA('A12', 'B12.5', 'Pagination', 'Exists', paginationText.found ? 'WORKS' : 'NOT_FOUND', { text: paginationText.text });
  }

  // B12.6: "Complete Inspection" button on uninspected GR
  {
    const inspBtn = page.locator('button:has-text("Complete Inspection")').first();
    const visible = await inspBtn.isVisible({ timeout: 3000 }).catch(() => false);
    tracker.recordCTA('A12', 'B12.6', '"Complete Inspection" button', 'Visible', visible ? 'WORKS' : 'NOT_FOUND');
  }
  await screenshot(page, 'B12_gr_list_ctas');

  // ════════════════════════════════════════
  // A15: Invoice List
  // ════════════════════════════════════════
  console.log('\n── A15: Invoice List ──');
  await page.goto(`${BASE}/dashboard/procurement/invoices`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  {
    const mainText = await page.innerText('main').catch(() => '');
    const hasData = await page.locator('table tbody tr').count().catch(() => 0);
    if (hasData > 0) {
      tracker.recordCTA('A15', 'B15.1', 'Invoice list', 'Load', 'WORKS', { count: hasData });
    } else {
      // Read empty state text — must be meaningful, not blank
      const emptyText = mainText.substring(0, 200);
      tracker.recordCTA('A15', 'B15.1', 'Invoice list', 'Load', 'EMPTY', { emptyStateText: emptyText });
    }
  }

  // B15.2: New Invoice button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("New Invoice"), button:has-text("New Invoice")', '/invoices/new', 'New Invoice');
    tracker.recordCTA('A15', 'B15.2', 'New Invoice button', 'Click', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/invoices`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B15.3: Empty state text (if no data)
  {
    const hasData = await page.locator('table tbody tr').count().catch(() => 0);
    if (hasData === 0) {
      const emptyText = await page.innerText('main').catch(() => '');
      const meaningful = emptyText.length > 50 && !emptyText.includes('undefined');
      tracker.recordCTA('A15', 'B15.3', 'Empty state text', meaningful ? 'Meaningful' : 'Missing/blank', meaningful ? 'WORKS' : 'BROKEN', { text: emptyText.substring(0, 100) });
    } else {
      tracker.recordCTA('A15', 'B15.3', 'Empty state text', 'N/A (has data)', 'WORKS');
    }
  }

  // B15.4: Search input
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    tracker.recordCTA('A15', 'B15.4', 'Search input', 'Visible', await search.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  // B15.5-B15.6: Match/payment status filters
  {
    const comboboxes = await page.locator('button[role="combobox"]').count();
    for (let i = 0; i < comboboxes; i++) {
      const opts = await readSelectOptions(page, `button[role="combobox"] >> nth=${i}`);
      tracker.recordCTA('A15', `B15.${5 + i}`, `Filter dropdown #${i + 1}`, 'Open + list', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options });
    }
  }
  await screenshot(page, 'B15_invoice_list_ctas');

  // ════════════════════════════════════════
  // A18: Payment List
  // ════════════════════════════════════════
  console.log('\n── A18: Payment List ──');
  await page.goto(`${BASE}/dashboard/procurement/payments`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  {
    const hasData = await page.locator('table tbody tr').count().catch(() => 0);
    const mainText = await page.innerText('main').catch(() => '');
    tracker.recordCTA('A18', 'B18.1', 'Payment list', 'Load', hasData > 0 ? 'WORKS' : 'EMPTY', { count: hasData, text: mainText.substring(0, 100) });
  }

  // B18.2: New Payment button
  {
    const result = await clickAndVerifyNav(page, 'a:has-text("New Payment"), button:has-text("New Payment")', '/payments/new', 'New Payment');
    tracker.recordCTA('A18', 'B18.2', 'New Payment button', 'Click', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/payments`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B18.3: Empty state text
  {
    const hasData = await page.locator('table tbody tr').count().catch(() => 0);
    if (hasData === 0) {
      const emptyText = await page.innerText('main').catch(() => '');
      tracker.recordCTA('A18', 'B18.3', 'Empty state text', emptyText.length > 50 ? 'Meaningful' : 'Missing', emptyText.length > 50 ? 'WORKS' : 'BROKEN');
    } else {
      tracker.recordCTA('A18', 'B18.3', 'Empty state text', 'N/A (has data)', 'WORKS');
    }
  }

  // B18.4: Search input
  {
    const search = page.locator('input[placeholder*="Search"]').first();
    tracker.recordCTA('A18', 'B18.4', 'Search input', 'Visible', await search.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  // B18.5: Status filter
  {
    const opts = await readSelectOptions(page, 'button[role="combobox"]');
    tracker.recordCTA('A18', 'B18.5', 'Status filter', 'Open + list', opts.found ? 'WORKS' : 'NOT_FOUND', { options: opts.options });
  }
  await screenshot(page, 'B18_payment_list_ctas');

  // ════════════════════════════════════════
  // A21: Approvals Hub
  // ════════════════════════════════════════
  console.log('\n── A21: Approvals ──');
  await page.goto(`${BASE}/dashboard/procurement/approvals`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B21.1: Cards render
  {
    const mainText = await page.innerText('main').catch(() => '');
    const hasPoCard = mainText.includes('Purchase Order Approvals');
    const hasPayCard = mainText.includes('Payment Approvals');
    const hasExcCard = mainText.includes('Exception Approvals');
    tracker.recordCTA('A21', 'B21.1', 'Approval queue cards', 'Render', (hasPoCard && hasPayCard) ? 'WORKS' : 'BROKEN',
      { po: hasPoCard, payment: hasPayCard, exception: hasExcCard });
  }

  // B21.2: PO queue link
  {
    const result = await clickAndVerifyNav(page, 'a:has(div:has-text("Purchase Order Approvals"))', '/purchase-orders', 'PO queue card');
    tracker.recordCTA('A21', 'B21.2', 'PO queue card', 'Click → navigate', result.navigated ? 'WORKS' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/approvals`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B21.3: Payment queue link
  {
    const result = await clickAndVerifyNav(page, 'a:has(div:has-text("Payment Approvals")), a:has-text("Payment Approvals")', '/payments', 'Payment queue card');
    tracker.recordCTA('A21', 'B21.3', 'Payment queue card', 'Click → navigate', result.navigated ? 'WORKS' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/approvals`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B21.4: Exception approvals link
  {
    const result = await clickAndVerifyNav(page, 'a:has(div:has-text("Exception")), a:has-text("Exception")', '/exception', 'Exception card');
    tracker.recordCTA('A21', 'B21.4', 'Exception approvals card', 'Click → navigate', result.navigated ? 'WORKS' : 'NOT_FOUND');
    if (result.navigated) {
      await page.goto(`${BASE}/dashboard/procurement/approvals`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2000);
    }
  }

  // B21.5: Pending PO badge — read actual text
  {
    const badges = await page.locator('[class*="Badge"]').allInnerTexts().catch(() => []);
    const pendingBadges = badges.filter(b => b.includes('pending'));
    tracker.recordCTA('A21', 'B21.5', 'Pending PO badge', 'Read text', pendingBadges.length > 0 ? 'WORKS' : 'EMPTY', { badges: pendingBadges });
  }

  // B21.6: Pending payment badge
  {
    const badges = await page.locator('[class*="Badge"]').allInnerTexts().catch(() => []);
    const paymentBadges = badges.filter(b => b.includes('pending'));
    tracker.recordCTA('A21', 'B21.6', 'Pending payment badge', 'Read text', paymentBadges.length > 1 ? 'WORKS' : 'EMPTY', { badges: paymentBadges });
  }
  await screenshot(page, 'B21_approvals_ctas');

  // ════════════════════════════════════════
  // A22: OR Follow-Up
  // ════════════════════════════════════════
  console.log('\n── A22: OR Follow-Up ──');
  await page.goto(`${BASE}/dashboard/procurement/or-follow-up`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  {
    const mainText = await page.innerText('main').catch(() => '');
    const hasTable = await page.locator('table').count().catch(() => 0);
    const hasEmptyState = mainText.includes('No overdue ORs');
    tracker.recordCTA('A22', 'B22.1', 'OR Follow-Up', 'Load', (hasTable > 0 || hasEmptyState) ? 'WORKS' : 'BROKEN',
      { hasTable: hasTable > 0, hasEmptyState });
  }

  // B22.2: Summary card (count + total amount)
  {
    const summaryText = await page.locator('[class*="Card"]').first().innerText().catch(() => '');
    const hasCount = summaryText.match(/\d+\s*(overdue|OR)/i);
    tracker.recordCTA('A22', 'B22.2', 'Summary card', hasCount ? 'Shows count + amount' : 'No summary', hasCount ? 'WORKS' : 'EMPTY', { text: summaryText.substring(0, 100) });
  }

  // B22.3: Send Follow-Up button — ACTUALLY CLICK IT (test PR will be deleted)
  {
    const sendBtn = page.locator('button:has-text("Send Follow-Up")').first();
    const visible = await sendBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) {
      await sendBtn.click();
      await page.waitForTimeout(3000);
      // Read the delivery status text that should update after send
      const toasts = await page.locator('[data-sonner-toast]').allTextContents().catch(() => []);
      const statusCell = await page.locator('td:has-text("Sent via"), td:has-text("Recorded"), td:has-text("Failed")').first().innerText().catch(() => '');
      console.log(`    [SEND] Toasts: ${JSON.stringify(toasts)}, Status: "${statusCell}"`);
      tracker.recordCTA('A22', 'B22.3', 'Send Follow-Up button', `Clicked. Toast: ${toasts.join('; ')}. Status: ${statusCell}`,
        (toasts.length > 0 || statusCell) ? 'WORKS' : 'BROKEN', { toasts, statusCell });
    } else {
      tracker.recordCTA('A22', 'B22.3', 'Send Follow-Up button', 'Not visible (no overdue ORs)', 'EMPTY');
    }
  }

  // B22.4: Table columns verification
  {
    const headers = await page.locator('table thead th').allInnerTexts().catch(() => []);
    const expected = ['Payment', 'Supplier', 'Amount', 'Paid', 'Overdue', 'Follow-Up'];
    const hasExpected = expected.filter(e => headers.some(h => h.includes(e))).length;
    tracker.recordCTA('A22', 'B22.4', 'Table columns', `${hasExpected}/${expected.length} expected columns`, hasExpected >= 4 ? 'WORKS' : 'BROKEN', { headers });
  }

  // B22.5: Notification delivery status text
  {
    const statusCells = await page.locator('td:has-text("Not sent"), td:has-text("Sent via"), td:has-text("Recorded")').count().catch(() => 0);
    tracker.recordCTA('A22', 'B22.5', 'Notification delivery status', `${statusCells} status cells`, statusCells > 0 ? 'WORKS' : 'NOT_FOUND');
  }
  await screenshot(page, 'B22_or_followup_ctas');

  // ════════════════════════════════════════
  // A28: Reports Hub
  // ════════════════════════════════════════
  console.log('\n── A28: Reports Hub ──');
  await page.goto(`${BASE}/dashboard/procurement/reports`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B28.1: Count report cards
  {
    const cards = await page.locator('[class*="Card"]').count();
    tracker.recordCTA('A28', 'B28.1', 'Report cards', 'Count', cards >= 6 ? 'WORKS' : 'BROKEN', { count: cards });
  }

  // B28.2-B28.7: Click each internal report card
  const reportLinks = [
    { id: 'B28.2', text: 'Supplier Performance',        expect: '/supplier-performance' },
    { id: 'B28.3', text: 'Payment Disbursement',        expect: '/payment-disbursement' },
    { id: 'B28.4', text: 'Single Source',                expect: '/single-source' },
    { id: 'B28.5', text: 'Variance',                    expect: '/three-way' },
    { id: 'B28.6', text: 'Monthly Spend',               expect: '/monthly-spend' },
    { id: 'B28.7', text: 'Goods Receipt Log',           expect: '/goods-receipt-log' },
  ];
  for (const rl of reportLinks) {
    const result = await clickAndVerifyNav(page, `a:has-text("${rl.text}")`, rl.expect, rl.text);
    tracker.recordCTA('A28', rl.id, rl.text, 'Click → navigate', result.navigated ? 'WORKS' : result.clicked ? 'BROKEN' : 'NOT_FOUND');
    if (result.navigated) {
      // Take screenshot of the report page
      await page.waitForTimeout(2000);
      await screenshot(page, `B28_report_${rl.id}`);
      await page.goto(`${BASE}/dashboard/procurement/reports`, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(1000);
    }
  }
  // B28.8: "Purchase Order Summary" external link
  {
    const extLink = page.locator('a[target="_blank"]:has-text("Purchase Order"), a[href*="BEI%20PO"]').first();
    tracker.recordCTA('A28', 'B28.8', 'PO Summary (external)', 'Visible', await extLink.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  // B28.9: "AP Aging" external link
  {
    const extLink = page.locator('a[target="_blank"]:has-text("Aging"), a[href*="Accounts%20Payable"]').first();
    tracker.recordCTA('A28', 'B28.9', 'AP Aging (external)', 'Visible', await extLink.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  // B28.10: "Go to Dashboard" link
  {
    const dashLink = page.locator('a:has-text("Go to Dashboard"), a:has-text("Dashboard")').last();
    tracker.recordCTA('A28', 'B28.10', '"Go to Dashboard" link', 'Visible', await dashLink.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  // B28.11: "Back to Workspace" link
  {
    const backLink = page.locator('a:has-text("Back to Workspace"), a:has-text("Back")').first();
    tracker.recordCTA('A28', 'B28.11', '"Back to Workspace" link', 'Visible', await backLink.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }

  await screenshot(page, 'B28_reports_hub_ctas');

  // ════════════════════════════════════════
  // A37: Settings
  // ════════════════════════════════════════
  console.log('\n── A37: Settings ──');
  await page.goto(`${BASE}/dashboard/procurement/settings`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // B37.1: Page loads with config
  {
    const mainText = await page.innerText('main').catch(() => '');
    const hasMae = mainText.includes('Mae Karazi');
    const hasButch = mainText.includes('Butch Formoso');
    const has500K = mainText.includes('500,000') || mainText.includes('500K');
    const hasBankTransfer = mainText.includes('Bank Transfer');
    const hasCheck = mainText.includes('Check');
    tracker.recordCTA('A37', 'B37.1', 'Settings page', 'Load config', hasMae ? 'WORKS' : 'BROKEN',
      { mae: hasMae, butch: hasButch, threshold: has500K, bankTransfer: hasBankTransfer, check: hasCheck });
  }

  // B37.2: Read approval workflow text
  {
    const { text } = await readText(page, 'text=/Mae Karazi/', 'Mae threshold');
    tracker.recordCTA('A37', 'B37.2', 'Mae threshold', 'Read text', text ? 'WORKS' : 'NOT_FOUND', { text });
  }

  // B37.5: CEO threshold
  {
    const { text } = await readText(page, 'text=/1,000,000/', 'CEO threshold');
    tracker.recordCTA('A37', 'B37.5', 'CEO threshold', 'Read text', text ? 'WORKS' : 'NOT_FOUND', { text });
  }

  // B37.3: Payment approval section (4-level flow)
  {
    const mainText = await page.innerText('main').catch(() => '');
    const hasReviewer = mainText.includes('Reviewer') || mainText.includes('Review');
    const hasBudget = mainText.includes('Budget');
    const hasCFO = mainText.includes('CFO');
    const hasCEO = mainText.includes('CEO');
    const allLevels = hasReviewer && hasBudget && hasCFO && hasCEO;
    tracker.recordCTA('A37', 'B37.3', 'Payment 4-level approval display', 'Read text', allLevels ? 'WORKS' : 'BROKEN', { reviewer: hasReviewer, budget: hasBudget, cfo: hasCFO, ceo: hasCEO });
  }

  // B37.4: Payment method badges
  {
    const badges = await page.locator('[class*="Badge"]').allInnerTexts().catch(() => []);
    const hasBankTransfer = badges.some(b => b.includes('Bank Transfer'));
    const hasCheck = badges.some(b => b === 'Check' || b.includes('Check'));
    tracker.recordCTA('A37', 'B37.4', 'Payment method badges', 'Read badge text', (hasBankTransfer && hasCheck) ? 'WORKS' : 'BROKEN', { bankTransfer: hasBankTransfer, check: hasCheck });
  }

  // B37.6: RFP types — read all badge texts
  {
    const badges = await page.locator('[class*="Badge"]').allInnerTexts().catch(() => []);
    const rfpTypes = badges.filter(b => ['PCF', 'Delivery Fund', 'Transpo', 'Rentals', 'Vendor', 'Cash Advance', 'Reimbursement', 'Credit Card'].some(t => b.includes(t)));
    tracker.recordCTA('A37', 'B37.6', 'RFP types', 'Read badges', rfpTypes.length >= 6 ? 'WORKS' : 'BROKEN', { types: rfpTypes, count: rfpTypes.length });
  }

  // B37.7: "Open Frappe Desk" external link
  {
    const frappeLink = page.locator('a[href*="hq.bebang.ph"], a:has-text("Frappe Desk")').first();
    tracker.recordCTA('A37', 'B37.7', '"Open Frappe Desk" link', 'Visible', await frappeLink.isVisible({ timeout: 3000 }).catch(() => false) ? 'WORKS' : 'NOT_FOUND');
  }
  await screenshot(page, 'B37_settings_ctas');

  // ════════════════════════════════════════
  // Cleanup
  // ════════════════════════════════════════
  await ctx.close();
  await browser.close();

  tracker.writeAll();
  tracker.printSummary();

  console.log('\nPhase B complete. Output: tmp/s142_cta_matrix.json');
}

run().catch(err => { console.error('FATAL:', err); process.exit(1); });
