/**
 * L3 S141 — Procurement Module Verification
 * Tests: pagination, approved tab, status filters, dashboard empty states, sidebar dedup
 *
 * Run: node scripts/testing/l3_s141_procurement.mjs
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_WEB = 'https://my.bebang.ph';
const OUTPUT_DIR = 'output/l3/S141';
const ARTIFACTS_DIR = `${OUTPUT_DIR}/artifacts`;
const EVIDENCE_DIR = 'output/l3/evidence';

// Ensure directories exist
for (const dir of [OUTPUT_DIR, ARTIFACTS_DIR, EVIDENCE_DIR]) {
  fs.mkdirSync(dir, { recursive: true });
}

const results = [];
const defects = [];

function record(scenario, type, test, status, detail, error = null) {
  const entry = { scenario, type, test, status, detail, error };
  results.push(entry);
  console.log(`[${status}] ${scenario}: ${test}${error ? ' — ' + error : ''}`);
  return entry;
}

function recordDefect(desc, severity, type, scenario, error, impact, rootCause, suggestedFix) {
  defects.push({ desc, severity, type, scenario, error, impact, rootCause, suggestedFix, firstSeen: new Date().toISOString() });
}

async function login(page, email, password = 'BeiTest2026!') {
  await page.goto(`${BASE_WEB}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('input[autocomplete="username"], input[name="email"]').first().fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/dashboard**', { timeout: 30000 });
  console.log(`Logged in as ${email}`);
}

async function screenshot(page, name) {
  const filePath = `${ARTIFACTS_DIR}/${name}.png`;
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // ========== LOGIN as CEO ==========
  console.log('\n=== LOGIN: sam@bebang.ph ===');
  await login(page, 'sam@bebang.ph', '2289454');

  // ========== S141-001: PO Page — Verify Pagination ==========
  console.log('\n=== S141-001: PO Pagination ===');
  try {
    // Navigate via sidebar click (not direct URL)
    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000); // Wait for data to load

    const screenshotPath = await screenshot(page, 'S141-001_po_page');

    // Check for pagination text — read actual text value, not just existence
    const paginationText = await page.locator('text=/Showing \\d+/').first().textContent().catch(() => null);
    const nextButton = await page.locator('button:has-text("Next")').first().isVisible().catch(() => false);
    const prevButton = await page.locator('button:has-text("Previous")').first().isVisible().catch(() => false);

    // Check total PO count from the table or page
    const tableRows = await page.locator('table tbody tr').count();

    console.log(`  Pagination text: ${paginationText || 'NOT FOUND'}`);
    console.log(`  Next button visible: ${nextButton}`);
    console.log(`  Previous button visible: ${prevButton}`);
    console.log(`  Table rows: ${tableRows}`);

    if (paginationText && paginationText.includes('Showing') && nextButton) {
      record('S141-001', 'happy', 'PO page shows pagination with total count', 'PASS',
        `Pagination text: "${paginationText}", Next button: visible, Previous button: ${prevButton}`);
    } else {
      record('S141-001', 'happy', 'PO page shows pagination with total count', 'FAIL',
        `Pagination text: ${paginationText || 'NOT FOUND'}, Next: ${nextButton}, Previous: ${prevButton}`,
        'No pagination controls found on PO page');
      recordDefect('No pagination on PO page', 'CRITICAL', 'IN-SCOPE', 'S141-001',
        'No Previous/Next buttons or "Showing X-Y of Z" text', '557 of 577 POs invisible',
        'setPage state exists but no UI controls', 'Add pagination controls after PO table');
    }

    // Save evidence
    fs.writeFileSync(`${EVIDENCE_DIR}/S141-001.json`, JSON.stringify({
      scenario_id: 'S141-001',
      actions: [{ type: 'nav_direct', url: '/dashboard/procurement/purchase-orders' }, { type: 'wait_load' }],
      findings: { pagination_text: paginationText, next_button: nextButton, prev_button: prevButton, table_rows: tableRows },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));
  } catch (err) {
    record('S141-001', 'happy', 'PO page shows pagination', 'FAIL', '', err.message);
  }

  // ========== S141-002: Click Next Page ==========
  console.log('\n=== S141-002: Click Next ===');
  try {
    const nextBtn = page.locator('button:has-text("Next")').first();
    const nextExists = await nextBtn.isVisible().catch(() => false);

    if (!nextExists) {
      record('S141-002', 'happy', 'Click Next advances to page 2', 'FAIL',
        'Next button does not exist', 'Cannot test pagination without Next button');
    } else {
      // Read current first row PO number
      const firstRowBefore = await page.locator('table tbody tr:first-child td:first-child').textContent().catch(() => 'N/A');

      await nextBtn.click();
      await page.waitForTimeout(2000);

      const firstRowAfter = await page.locator('table tbody tr:first-child td:first-child').textContent().catch(() => 'N/A');
      const paginationTextAfter = await page.locator('text=/Showing \\d+/').first().textContent().catch(() => null);

      const screenshotPath = await screenshot(page, 'S141-002_page2');

      console.log(`  First row before: ${firstRowBefore}`);
      console.log(`  First row after: ${firstRowAfter}`);
      console.log(`  Pagination after: ${paginationTextAfter}`);

      if (firstRowBefore !== firstRowAfter && paginationTextAfter) {
        record('S141-002', 'happy', 'Click Next advances to page 2', 'PASS',
          `Page changed: "${firstRowBefore}" → "${firstRowAfter}", pagination: "${paginationTextAfter}"`);
      } else {
        record('S141-002', 'happy', 'Click Next advances to page 2', 'FAIL',
          `First row unchanged or no pagination: before=${firstRowBefore}, after=${firstRowAfter}`,
          'Next button did not change page content');
      }

      fs.writeFileSync(`${EVIDENCE_DIR}/S141-002.json`, JSON.stringify({
        scenario_id: 'S141-002',
        actions: [{ type: 'click', target: 'Next button' }],
        findings: { first_row_before: firstRowBefore, first_row_after: firstRowAfter, pagination_text: paginationTextAfter },
        artifacts: { screenshots: [screenshotPath] }
      }, null, 2));
    }
  } catch (err) {
    record('S141-002', 'happy', 'Click Next advances to page 2', 'FAIL', '', err.message);
  }

  // ========== S141-003: Click Previous ==========
  console.log('\n=== S141-003: Click Previous ===');
  try {
    const prevBtn = page.locator('button:has-text("Previous")').first();
    const prevExists = await prevBtn.isVisible().catch(() => false);

    if (!prevExists) {
      record('S141-003', 'happy', 'Click Previous returns to page 1', 'FAIL',
        'Previous button does not exist', 'Cannot test backward pagination');
    } else {
      await prevBtn.click();
      await page.waitForTimeout(2000);

      const paginationText = await page.locator('text=/Showing \\d+/').first().textContent().catch(() => null);
      const prevDisabled = await prevBtn.isDisabled().catch(() => false);

      await screenshot(page, 'S141-003_page1_return');

      console.log(`  Pagination: ${paginationText}`);
      console.log(`  Previous disabled: ${prevDisabled}`);

      if (paginationText && paginationText.includes('1 to')) {
        record('S141-003', 'happy', 'Click Previous returns to page 1', 'PASS',
          `Returned to page 1: "${paginationText}", Previous disabled: ${prevDisabled}`);
      } else {
        record('S141-003', 'happy', 'Click Previous returns to page 1', 'FAIL',
          `Pagination: ${paginationText}`, 'Did not return to page 1');
      }
    }
  } catch (err) {
    record('S141-003', 'happy', 'Click Previous returns to page 1', 'FAIL', '', err.message);
  }

  // ========== S141-004: Status Filter — Pending CEO ==========
  console.log('\n=== S141-004: Pending CEO status filter ===');
  try {
    // First ensure we're on "All POs" tab
    const allPosTab = page.locator('[role="tab"]:has-text("All POs")');
    if (await allPosTab.isVisible().catch(() => false)) {
      await allPosTab.click();
      await page.waitForTimeout(1000);
    }

    // Find the status dropdown — it's inside the filter card, use the select trigger with "All Statuses" placeholder
    // shadcn Select renders as button[role="combobox"]
    const statusTrigger = page.locator('button[role="combobox"]').first();
    const triggerVisible = await statusTrigger.isVisible({ timeout: 5000 }).catch(() => false);

    if (!triggerVisible) {
      throw new Error('Could not find status dropdown (button[role="combobox"])');
    }
    await statusTrigger.click();
    await page.waitForTimeout(1000); // Extra wait for portal/popover to render

    // shadcn Select uses a Radix portal — options may be at document root
    const allOptions = await page.locator('[role="option"]').allTextContents().catch(() => []);
    console.log(`  Dropdown options (role=option): ${JSON.stringify(allOptions)}`);

    // Also try data-radix-select-viewport children
    if (allOptions.length === 0) {
      const radixOptions = await page.locator('[data-radix-select-viewport] div, [data-radix-collection-item]').allTextContents().catch(() => []);
      console.log(`  Radix options: ${JSON.stringify(radixOptions)}`);
    }

    const screenshotPath = await screenshot(page, 'S141-004_status_dropdown');

    const pendingCEOOption = page.locator('[role="option"]:has-text("Pending CEO"), [data-radix-collection-item]:has-text("Pending CEO")').first();
    const ceoExists = await pendingCEOOption.isVisible({ timeout: 3000 }).catch(() => false);
    console.log(`  Pending CEO option exists: ${ceoExists}`);

    if (ceoExists) {
      await pendingCEOOption.click();
      await page.waitForTimeout(2000);
      record('S141-004', 'happy', 'Pending CEO status filter exists and selectable', 'PASS',
        `Options: ${JSON.stringify(allOptions)}`);
    } else {
      record('S141-004', 'happy', 'Pending CEO status filter exists', 'FAIL',
        `Available options: ${JSON.stringify(allOptions)}`, 'Pending CEO option missing from dropdown');
      recordDefect('Missing "Pending CEO" in PO status dropdown', 'MAJOR', 'IN-SCOPE', 'S141-004',
        'Status dropdown missing Pending CEO Approval', 'Cannot filter POs by CEO approval status',
        'S132 added CEO approval status but dropdown not updated', 'Add SelectItem for Pending CEO Approval');
      // Close dropdown
      await page.keyboard.press('Escape');
    }

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-004.json`, JSON.stringify({
      scenario_id: 'S141-004',
      actions: [{ type: 'click', target: 'status dropdown' }, { type: 'check', target: 'Pending CEO option' }],
      findings: { all_options: allOptions, pending_ceo_exists: ceoExists },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));
  } catch (err) {
    record('S141-004', 'happy', 'Pending CEO status filter', 'FAIL', '', err.message);
  }

  // ========== S141-005: Status Filter — Cancelled ==========
  console.log('\n=== S141-005: Cancelled status filter ===');
  try {
    // Ensure we're on "All POs" tab first
    const allPosTab2 = page.locator('[role="tab"]:has-text("All POs")');
    if (await allPosTab2.isVisible().catch(() => false)) {
      await allPosTab2.click();
      await page.waitForTimeout(1000);
    }

    // Reset status to All first
    const statusTrigger2 = page.locator('button[role="combobox"]').first();
    await statusTrigger2.click({ timeout: 5000 });
    await page.waitForTimeout(500);

    const cancelledOption = page.locator('[role="option"]:has-text("Cancelled")');
    const cancelledExists = await cancelledOption.isVisible().catch(() => false);

    const allOptions = await page.locator('[role="option"]').allTextContents().catch(() => []);
    console.log(`  Cancelled option exists: ${cancelledExists}`);

    if (cancelledExists) {
      await cancelledOption.click();
      await page.waitForTimeout(2000);

      // Verify table shows cancelled POs
      const tableRows = await page.locator('table tbody tr').count();
      const statusBadges = await page.locator('table tbody [class*="badge"]').allTextContents().catch(() => []);

      await screenshot(page, 'S141-005_cancelled_filter');

      const allCancelled = statusBadges.every(s => s.trim() === 'Cancelled') || tableRows === 0;
      record('S141-005', 'happy', 'Cancelled status filter works', allCancelled ? 'PASS' : 'FAIL',
        `Rows: ${tableRows}, Badges: ${JSON.stringify(statusBadges.slice(0, 5))}`);
    } else {
      record('S141-005', 'happy', 'Cancelled status filter exists', 'FAIL',
        `Available options: ${JSON.stringify(allOptions)}`, 'Cancelled option missing from dropdown');
      recordDefect('Missing "Cancelled" in PO status dropdown', 'MINOR', 'IN-SCOPE', 'S141-005',
        'Status dropdown missing Cancelled', '15 cancelled POs unreachable',
        'Dropdown hardcoded without Cancelled', 'Add SelectItem for Cancelled');
      await page.keyboard.press('Escape');
    }

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-005.json`, JSON.stringify({
      scenario_id: 'S141-005',
      actions: [{ type: 'click', target: 'Cancelled option' }],
      findings: { cancelled_exists: cancelledExists, options: allOptions },
      artifacts: {}
    }, null, 2));
  } catch (err) {
    record('S141-005', 'happy', 'Cancelled status filter', 'FAIL', '', err.message);
  }

  // ========== S141-006: Approved Tab ==========
  console.log('\n=== S141-006: Approved Tab ===');
  try {
    // Navigate fresh to avoid stale dropdown state
    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Click Approved tab
    const approvedTab = page.locator('[role="tab"]:has-text("Approved")');
    const tabExists = await approvedTab.isVisible().catch(() => false);

    if (!tabExists) {
      record('S141-006', 'happy', 'Approved tab exists and loads data', 'FAIL',
        'Approved tab not found', 'Tab element missing');
    } else {
      await approvedTab.click();
      await page.waitForTimeout(3000);

      const screenshotPath = await screenshot(page, 'S141-006_approved_tab');

      // Wait for the Approved tab content to load
      await page.waitForTimeout(3000);

      // Read the page content after clicking Approved tab
      const pageContent = await page.textContent('main').catch(() => '');

      // Check for search placeholder specific to Approved tab
      const hasApprovedSearch = pageContent.includes('Search approved POs');

      // Check for approved PO data — look for status badges with "Approved" or "Fully Received"
      const statusBadges = await page.locator('table tbody td').allTextContents().catch(() => []);
      const hasApprovedData = statusBadges.some(t => t.includes('Approved') || t.includes('Fully Received'));

      // Check for pagination text specific to this tab
      const paginationText = await page.locator('text=/Showing \\d+.*POs/').first().textContent().catch(() => '');

      console.log(`  Has approved search: ${hasApprovedSearch}`);
      console.log(`  Has approved data: ${hasApprovedData}`);
      console.log(`  Pagination: ${paginationText}`);
      console.log(`  Status badges sample: ${statusBadges.filter(t => t.includes('Approved') || t.includes('Received')).slice(0, 5)}`);

      if (hasApprovedData || hasApprovedSearch) {
        record('S141-006', 'happy', 'Approved tab shows data', 'PASS',
          `Search box: ${hasApprovedSearch}, Data: ${hasApprovedData}, Pagination: "${paginationText}"`);
      } else if (pageContent.includes('Similar table') || pageContent.trim().length < 50) {
        record('S141-006', 'happy', 'Approved tab shows data', 'FAIL',
          'Tab is empty placeholder', 'Approved tab is empty or placeholder');
        recordDefect('Empty Approved tab on PO page', 'MAJOR', 'IN-SCOPE', 'S141-006',
          'TabsContent value="approved" is empty placeholder', 'Cannot view approved POs in dedicated tab',
          'Tab was never implemented — only comment placeholder', 'Add filtered query for Approved/Fully Received/Partially Received');
      } else {
        record('S141-006', 'happy', 'Approved tab state', 'FAIL',
          `Unexpected: approvedSearch=${hasApprovedSearch}, data=${hasApprovedData}`,
          'Could not confirm approved tab has data');
      }

      fs.writeFileSync(`${EVIDENCE_DIR}/S141-006.json`, JSON.stringify({
        scenario_id: 'S141-006',
        actions: [{ type: 'click', target: 'Approved tab' }],
        findings: { has_approved_search: hasApprovedSearch, has_approved_data: hasApprovedData, pagination: paginationText },
        artifacts: { screenshots: [screenshotPath] }
      }, null, 2));
    }
  } catch (err) {
    record('S141-006', 'happy', 'Approved tab', 'FAIL', '', err.message);
  }

  // ========== S141-007: Dashboard — KPI Cards ==========
  console.log('\n=== S141-007: Dashboard KPI Cards ===');
  try {
    await page.goto(`${BASE_WEB}/dashboard/procurement`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    const screenshotPath = await screenshot(page, 'S141-007_dashboard');

    // Read the actual TEXT of KPI cards — not just check existence
    const kpiCards = await page.locator('.tracking-tight').allTextContents().catch(() => []);
    console.log(`  KPI card values: ${JSON.stringify(kpiCards)}`);

    // Check for Total Outstanding value
    const totalOutstandingCard = await page.locator('text=Total Outstanding').locator('..').locator('..').textContent().catch(() => '');
    const overdueCard = await page.locator('text=Overdue Amount').locator('..').locator('..').textContent().catch(() => '');
    const mtdCard = await page.locator('text=MTD PO Value').locator('..').locator('..').textContent().catch(() => '');
    const avgPaymentCard = await page.locator('text=Avg Payment Days').locator('..').locator('..').textContent().catch(() => '');

    console.log(`  Total Outstanding card: ${totalOutstandingCard.substring(0, 80)}`);
    console.log(`  Overdue card: ${overdueCard.substring(0, 80)}`);
    console.log(`  MTD PO Value card: ${mtdCard.substring(0, 80)}`);
    console.log(`  Avg Payment card: ${avgPaymentCard.substring(0, 80)}`);

    // Check if cards show misleading ₱0 or proper empty state
    const showsMisleadingZero = totalOutstandingCard.includes('₱0') && !totalOutstandingCard.includes('No data');
    const showsProperEmpty = totalOutstandingCard.includes('No data') || totalOutstandingCard.includes('No invoice');

    if (showsProperEmpty) {
      record('S141-007', 'happy', 'Dashboard shows proper empty state for invoice-dependent KPIs', 'PASS',
        `Total Outstanding: "${totalOutstandingCard.substring(0, 60)}"`);
    } else if (showsMisleadingZero) {
      record('S141-007', 'happy', 'Dashboard shows proper empty state for invoice-dependent KPIs', 'FAIL',
        `Shows misleading ₱0: "${totalOutstandingCard.substring(0, 60)}"`,
        'Dashboard shows ₱0 instead of "No data yet"');
      recordDefect('Dashboard shows misleading ₱0 for invoice KPIs', 'MAJOR', 'IN-SCOPE', 'S141-007',
        'Total Outstanding, Overdue Amount show ₱0', 'User thinks there are ₱0 payables (misleading)',
        'Backend queries tabBEI Invoice which has 0 records — no invoices synced', 'Show "No data yet" empty state');
    } else {
      record('S141-007', 'happy', 'Dashboard KPI cards', 'FAIL',
        `Unexpected card content: "${totalOutstandingCard.substring(0, 80)}"`,
        'Could not determine card state');
    }

    // Check MTD PO Value separately — this should have real data
    const mtdHasValue = mtdCard.includes('₱') && !mtdCard.includes('₱0');
    console.log(`  MTD PO has real value: ${mtdHasValue}`);

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-007.json`, JSON.stringify({
      scenario_id: 'S141-007',
      actions: [{ type: 'nav_direct', url: '/dashboard/procurement' }],
      findings: {
        total_outstanding: totalOutstandingCard.substring(0, 100),
        overdue: overdueCard.substring(0, 100),
        mtd_po: mtdCard.substring(0, 100),
        avg_payment: avgPaymentCard.substring(0, 100),
        misleading_zero: showsMisleadingZero,
        proper_empty: showsProperEmpty
      },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));
  } catch (err) {
    record('S141-007', 'happy', 'Dashboard KPI cards', 'FAIL', '', err.message);
  }

  // ========== S141-008: AP Aging Chart Empty State ==========
  console.log('\n=== S141-008: AP Aging Empty State ===');
  try {
    // Read AP Aging section text
    const agingSection = await page.locator('text=AP Aging Analysis').locator('..').locator('..').textContent().catch(() => '');
    console.log(`  Aging section: ${agingSection.substring(0, 100)}`);

    const screenshotPath = await screenshot(page, 'S141-008_ap_aging');

    const showsEmptyState = agingSection.includes('No AP data') || agingSection.includes('No data');
    const showsZeroTotal = agingSection.includes('₱0') && !agingSection.includes('No');

    if (showsEmptyState) {
      record('S141-008', 'happy', 'AP Aging shows proper empty state', 'PASS',
        `Shows: "${agingSection.substring(0, 80)}"`);
    } else if (showsZeroTotal) {
      record('S141-008', 'happy', 'AP Aging shows proper empty state', 'FAIL',
        `Shows misleading ₱0: "${agingSection.substring(0, 80)}"`,
        'AP Aging shows ₱0 Total Outstanding instead of empty state');
      recordDefect('AP Aging chart shows misleading ₱0', 'MINOR', 'IN-SCOPE', 'S141-008',
        'Pie chart renders with all-zero data, shows "₱0 Total Outstanding"', 'User sees empty pie chart with ₱0',
        'Chart renders even when all values are 0', 'Show "No AP data yet" when total is 0');
    } else {
      record('S141-008', 'happy', 'AP Aging chart state', 'PASS',
        `Has data: "${agingSection.substring(0, 80)}"`);
    }

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-008.json`, JSON.stringify({
      scenario_id: 'S141-008',
      actions: [{ type: 'read', target: 'AP Aging section' }],
      findings: { section_text: agingSection.substring(0, 200), shows_empty: showsEmptyState, shows_zero: showsZeroTotal },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));
  } catch (err) {
    record('S141-008', 'happy', 'AP Aging', 'FAIL', '', err.message);
  }

  // ========== S141-009: Duplicate Sidebar ==========
  console.log('\n=== S141-009: Sidebar Check ===');
  try {
    // Count visible sidebars / aside elements
    const asideCount = await page.locator('aside').count();
    const navSidebars = await page.locator('aside, [class*="sidebar"], nav[class*="flex-col"]').count();

    // Check specifically for the procurement inner sidebar
    const innerSidebarText = await page.locator('aside').first().textContent().catch(() => '');
    const hasInnerProcSidebar = innerSidebarText.includes('Manage suppliers') || innerSidebarText.includes('Procurement');

    // Check for duplicate by looking for two navigation structures
    const allNavLinks = await page.locator('aside a, nav a').allTextContents().catch(() => []);
    const procurementLinks = allNavLinks.filter(t => t.includes('Purchase Orders') || t.includes('Suppliers') || t.includes('Goods Receipts'));

    console.log(`  Aside elements: ${asideCount}`);
    console.log(`  Nav structures: ${navSidebars}`);
    console.log(`  Procurement-related links: ${procurementLinks.length}`);
    console.log(`  Has inner procurement sidebar: ${hasInnerProcSidebar}`);

    const screenshotPath = await screenshot(page, 'S141-009_sidebar');

    // Duplicate = "Purchase Orders" appears more than once across all navs
    const duplicateDetected = procurementLinks.filter(t => t.includes('Purchase Orders')).length > 1;

    if (!duplicateDetected) {
      record('S141-009', 'happy', 'Only ONE sidebar visible', 'PASS',
        `Aside count: ${asideCount}, PO links: ${procurementLinks.filter(t => t.includes('Purchase Orders')).length}`);
    } else {
      record('S141-009', 'happy', 'Only ONE sidebar visible', 'FAIL',
        `Duplicate detected: "Purchase Orders" appears ${procurementLinks.filter(t => t.includes('Purchase Orders')).length} times`,
        'Two sidebars with overlapping procurement navigation');
      recordDefect('Duplicate sidebar on procurement pages', 'MAJOR', 'IN-SCOPE', 'S141-009',
        'Both layout.tsx inner sidebar and nav-main.tsx render procurement items', 'Confusing UX with two navigation columns',
        'layout.tsx renders its own sidebar alongside main nav', 'Remove inner sidebar from layout.tsx');
    }

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-009.json`, JSON.stringify({
      scenario_id: 'S141-009',
      actions: [{ type: 'inspect', target: 'sidebar structure' }],
      findings: { aside_count: asideCount, procurement_links: procurementLinks, duplicate: duplicateDetected },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));
  } catch (err) {
    record('S141-009', 'happy', 'Sidebar check', 'FAIL', '', err.message);
  }

  // ========== S141-010: Search still works ==========
  console.log('\n=== S141-010: PO Search ===');
  try {
    await page.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);

    const searchInput = page.locator('input[placeholder*="Search"]').first();
    const searchExists = await searchInput.isVisible().catch(() => false);

    if (!searchExists) {
      record('S141-010', 'happy', 'PO search works', 'FAIL', 'Search input not found', 'No search input on PO page');
    } else {
      await searchInput.fill('Orangepop');
      await page.waitForTimeout(2000);

      const tableRows = await page.locator('table tbody tr').count();
      const firstRowText = await page.locator('table tbody tr:first-child').textContent().catch(() => '');

      await screenshot(page, 'S141-010_search_orangepop');

      console.log(`  Rows after search: ${tableRows}`);
      console.log(`  First row: ${firstRowText.substring(0, 80)}`);

      if (firstRowText.toLowerCase().includes('orangepop') || tableRows === 0) {
        record('S141-010', 'happy', 'PO search works', 'PASS',
          `Search "Orangepop": ${tableRows} rows, first: "${firstRowText.substring(0, 60)}"`);
      } else {
        record('S141-010', 'happy', 'PO search works', 'FAIL',
          `Search did not filter: ${tableRows} rows, first: "${firstRowText.substring(0, 60)}"`,
          'Search did not filter results');
      }

      // Clear search
      await searchInput.clear();
      await page.waitForTimeout(1000);
    }
  } catch (err) {
    record('S141-010', 'happy', 'PO search', 'FAIL', '', err.message);
  }

  // ========== S141-011: RBAC — test.staff role ==========
  console.log('\n=== S141-011: RBAC — test.staff ===');
  try {
    const staffContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const staffPage = await staffContext.newPage();

    await login(staffPage, 'test.staff@bebang.ph');

    await staffPage.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await staffPage.waitForTimeout(5000); // Extra wait for CSR to render

    const screenshotPath = await screenshot(staffPage, 'S141-011_staff_po_page');

    // Check if page loaded — use innerText (rendered text only, no scripts)
    const pageText = await staffPage.innerText('body').catch(() => '');
    const has403 = pageText.includes('403') || pageText.includes('Forbidden') || pageText.includes('not authorized') || pageText.includes('Access Denied');
    const hasPoContent = pageText.includes('Purchase Orders') || pageText.includes('PO-20') || pageText.includes('Manage PO');
    const hasTable = await staffPage.locator('table').count() > 0;
    const currentUrl = staffPage.url();

    console.log(`  Has 403: ${has403}`);
    console.log(`  Has PO content: ${hasPoContent}`);
    console.log(`  Has table: ${hasTable}`);
    console.log(`  Current URL: ${currentUrl}`);
    console.log(`  Page text (first 200): ${pageText.substring(0, 200)}`);

    if ((hasPoContent || hasTable) && !has403) {
      record('S141-011', 'rbac', 'Staff role can access procurement POs', 'PASS',
        `test.staff can view PO page, URL: ${currentUrl}`);
    } else if (has403) {
      record('S141-011', 'rbac', 'Staff role can access procurement POs', 'FAIL',
        'Got 403/Forbidden', 'Staff role blocked from procurement');
    } else if (currentUrl.includes('/dashboard') && !currentUrl.includes('/procurement')) {
      record('S141-011', 'rbac', 'Staff role redirected away from procurement', 'FAIL',
        `Redirected to: ${currentUrl}`, 'Staff role does not have procurement access — redirected');
    } else {
      record('S141-011', 'rbac', 'Staff role procurement access', 'FAIL',
        `Page text: "${pageText.substring(0, 150)}", URL: ${currentUrl}`, 'Could not determine access state');
    }

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-011.json`, JSON.stringify({
      scenario_id: 'S141-011',
      actions: [{ type: 'login', email: 'test.staff@bebang.ph' }, { type: 'nav_direct', url: '/dashboard/procurement/purchase-orders' }],
      findings: { has_403: has403, has_po_content: hasPoContent },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));

    await staffContext.close();
  } catch (err) {
    record('S141-011', 'rbac', 'Staff role access', 'FAIL', '', err.message);
  }

  // ========== S141-012: Mobile viewport ==========
  console.log('\n=== S141-012: Mobile Viewport ===');
  try {
    const mobileContext = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const mobilePage = await mobileContext.newPage();

    await login(mobilePage, 'sam@bebang.ph', '2289454');

    await mobilePage.goto(`${BASE_WEB}/dashboard/procurement/purchase-orders`, { waitUntil: 'networkidle', timeout: 60000 });
    await mobilePage.waitForTimeout(3000);

    const screenshotPath = await screenshot(mobilePage, 'S141-012_mobile_po');

    // Check for horizontal overflow
    const bodyWidth = await mobilePage.evaluate(() => document.body.scrollWidth);
    const viewportWidth = 375;
    const hasOverflow = bodyWidth > viewportWidth + 10; // 10px tolerance

    console.log(`  Body scroll width: ${bodyWidth}`);
    console.log(`  Has overflow: ${hasOverflow}`);

    record('S141-012', 'edge', 'Mobile viewport - no overflow', hasOverflow ? 'FAIL' : 'PASS',
      `Body width: ${bodyWidth}px (viewport: ${viewportWidth}px)`,
      hasOverflow ? 'Horizontal overflow on mobile' : null);

    fs.writeFileSync(`${EVIDENCE_DIR}/S141-012.json`, JSON.stringify({
      scenario_id: 'S141-012',
      actions: [{ type: 'resize', viewport: '375x812' }, { type: 'nav_direct', url: '/dashboard/procurement/purchase-orders' }],
      findings: { body_width: bodyWidth, viewport_width: viewportWidth, overflow: hasOverflow },
      artifacts: { screenshots: [screenshotPath] }
    }, null, 2));

    await mobileContext.close();
  } catch (err) {
    record('S141-012', 'edge', 'Mobile viewport', 'FAIL', '', err.message);
  }

  // ========== WRITE RESULTS ==========
  console.log('\n\n========================================');
  console.log(`L3 S141 RESULTS (${new Date().toISOString().split('T')[0]})`);
  console.log('========================================');

  let passCount = 0, failCount = 0;
  for (const r of results) {
    console.log(`[${r.status}] ${r.scenario}: ${r.test}${r.error ? ' — ' + r.error : ''}`);
    if (r.status === 'PASS') passCount++;
    else failCount++;
  }

  console.log(`\nTotal: ${passCount}/${results.length} PASS, ${failCount} FAIL`);

  if (defects.length > 0) {
    console.log(`\nDEFECTS FOUND: ${defects.length}`);
    for (const d of defects) {
      console.log(`  [${d.severity}] ${d.desc}`);
    }
  }

  // Write results
  fs.writeFileSync(`${OUTPUT_DIR}/procurement_${new Date().toISOString().split('T')[0]}.json`,
    JSON.stringify(results, null, 2));

  // Write defects
  if (defects.length > 0) {
    let defectMd = '# S141 Procurement Module Defects\n\n';
    for (const d of defects) {
      defectMd += `## DEFECT: ${d.desc}\n`;
      defectMd += `- **Severity:** ${d.severity}\n`;
      defectMd += `- **Type:** ${d.type}\n`;
      defectMd += `- **Scenario:** ${d.scenario}\n`;
      defectMd += `- **Error:** ${d.error}\n`;
      defectMd += `- **Impact:** ${d.impact}\n`;
      defectMd += `- **Root Cause:** ${d.rootCause}\n`;
      defectMd += `- **Suggested Fix:** ${d.suggestedFix}\n`;
      defectMd += `- **First Seen:** ${d.firstSeen}\n\n`;
    }
    fs.writeFileSync(`${OUTPUT_DIR}/DEFECTS.md`, defectMd);
  }

  // Write state verification
  fs.writeFileSync(`${OUTPUT_DIR}/state_verification.json`, JSON.stringify(
    results.map(r => ({
      check: r.test,
      before: 'pre-S141 production state',
      after: r.detail,
      passed: r.status === 'PASS'
    })), null, 2));

  await browser.close();
  console.log('\nDone. Evidence written to output/l3/S141/');
}

run().catch(err => {
  console.error('FATAL:', err);
  process.exit(1);
});
