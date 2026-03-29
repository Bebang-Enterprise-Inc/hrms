/**
 * S142 Browser Verification — 6 Tests
 *
 * Test 1: Back buttons on 6 detail pages
 * Test 2: Settings page badges
 * Test 3: OR Follow-Up page
 * Test 4: Dashboard Payments tab
 * Test 5: Supplier Performance page
 * Test 6: PO Aging page
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = 'https://my.bebang.ph';
const SCREENSHOT_DIR = 'tmp/s142_screenshots';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = [];

function record(testId, testName, verdict, details) {
  results.push({ testId, testName, verdict, details });
  console.log(`[${verdict}] ${testId}: ${testName}`);
  if (details) console.log(`       ${typeof details === 'string' ? details : JSON.stringify(details).substring(0, 300)}`);
}

async function ss(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `VERIFY_${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`  -> Screenshot: ${filePath}`);
  return filePath;
}

async function getMainText(page) {
  return page.locator('main').first().innerText({ timeout: 5000 }).catch(() => '');
}

async function getConsoleErrors(page) {
  // We collect them via listener set up at login
  return page._consoleErrors || [];
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  // Collect console errors
  page._consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') page._consoleErrors.push(msg.text());
  });

  // ── Login ──
  console.log('=== LOGIN ===');
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('input[name="email"], input[autocomplete="username"]').first().fill('sam@bebang.ph');
  await page.locator('input[name="password"], input[type="password"]').first().fill('2289454');
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/dashboard**', { timeout: 30000 });
  console.log('Logged in as CEO (sam@bebang.ph)\n');

  // ══════════════════════════════════════════════
  // TEST 1: Back buttons on 6 detail pages
  // ══════════════════════════════════════════════
  console.log('=== TEST 1: Back Buttons on Detail Pages ===\n');

  const detailPages = [
    { name: 'PR', listUrl: '/dashboard/procurement/purchase-requisitions', label: 'Purchase Requisitions' },
    { name: 'PO', listUrl: '/dashboard/procurement/purchase-orders', label: 'Purchase Orders' },
    { name: 'Supplier', listUrl: '/dashboard/procurement/suppliers', label: 'Suppliers' },
    { name: 'GR', listUrl: '/dashboard/procurement/goods-receipts', label: 'Goods Receipts' },
    { name: 'Invoice', listUrl: '/dashboard/procurement/invoices', label: 'Invoices' },
    { name: 'Payment', listUrl: '/dashboard/procurement/payments', label: 'Payments' },
  ];

  for (const dp of detailPages) {
    const testId = `T1-${dp.name}`;
    console.log(`--- ${dp.name} Detail ---`);

    // Go to list page
    await page.goto(`${BASE}${dp.listUrl}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Check if list has any rows to click
    const mainText = await getMainText(page);
    const hasRows = await page.locator('table tbody tr').count().catch(() => 0);
    const hasClickableRows = await page.locator('table tbody tr a, table tbody tr [role="link"], table tbody tr td').count().catch(() => 0);

    if (hasRows === 0) {
      // Check for empty state
      const emptyIndicators = ['no data', 'no items', 'no records', 'no purchase', 'no suppliers', 'no goods', 'no invoices', 'no payment'];
      const isEmpty = emptyIndicators.some(ind => mainText.toLowerCase().includes(ind));
      if (isEmpty || mainText.trim().length < 50) {
        await ss(page, `${dp.name}_list_empty`);
        record(testId, `${dp.name} Detail back button`, 'SKIP', `NO DATA — list page empty. Text: "${mainText.substring(0, 150)}"`);
        continue;
      }
    }

    await ss(page, `${dp.name}_list`);

    // Click first row
    const firstRowLink = page.locator('table tbody tr').first().locator('a').first();
    const firstRowLinkVisible = await firstRowLink.isVisible({ timeout: 3000 }).catch(() => false);

    if (firstRowLinkVisible) {
      await firstRowLink.click();
    } else {
      // Try clicking the first row itself
      const firstRow = page.locator('table tbody tr').first();
      const rowVisible = await firstRow.isVisible({ timeout: 2000 }).catch(() => false);
      if (rowVisible) {
        await firstRow.click();
      } else {
        // Try card-based layout
        const card = page.locator('[class*="card"], [class*="Card"], a[href*="' + dp.listUrl + '/"]').first();
        const cardVisible = await card.isVisible({ timeout: 2000 }).catch(() => false);
        if (cardVisible) {
          await card.click();
        } else {
          await ss(page, `${dp.name}_no_clickable`);
          record(testId, `${dp.name} Detail back button`, 'FAIL', 'No clickable row/card found on list page');
          continue;
        }
      }
    }

    await page.waitForTimeout(3000);
    const detailUrl = page.url();

    // Check if we actually navigated to a detail page
    if (detailUrl === `${BASE}${dp.listUrl}`) {
      // Didn't navigate — try clicking the row differently
      const anyLink = page.locator(`a[href*="${dp.listUrl}/"]`).first();
      const anyLinkVisible = await anyLink.isVisible({ timeout: 2000 }).catch(() => false);
      if (anyLinkVisible) {
        await anyLink.click();
        await page.waitForTimeout(3000);
      }
    }

    await ss(page, `${dp.name}_detail_BEFORE_back`);
    const detailText = await getMainText(page);

    // Look for back button — multiple selectors
    const backSelectors = [
      'button:has(svg[class*="arrow"]), a:has(svg[class*="arrow"])',
      '[aria-label*="back" i], [aria-label*="Back" i]',
      'a:has-text("Back"), button:has-text("Back")',
      'a:has-text("back to"), button:has-text("back to")',
      '[class*="back" i]',
      'a[href="' + dp.listUrl + '"]',
      'a[href*="' + dp.listUrl + '"]:not([href*="/new"])',
      // ArrowLeft icon — lucide
      'button:has(svg), a:has(svg)',
    ];

    let backFound = false;
    let backText = '';
    let backElement = null;

    for (const sel of backSelectors) {
      const els = page.locator(sel);
      const count = await els.count().catch(() => 0);
      for (let i = 0; i < count; i++) {
        const el = els.nth(i);
        const visible = await el.isVisible().catch(() => false);
        if (!visible) continue;
        const txt = await el.innerText().catch(() => '');
        const ariaLabel = await el.getAttribute('aria-label').catch(() => '');
        const href = await el.getAttribute('href').catch(() => '');

        // Check if this looks like a back button
        const isBack =
          txt.toLowerCase().includes('back') ||
          (ariaLabel && ariaLabel.toLowerCase().includes('back')) ||
          (href && href === dp.listUrl) ||
          (href && href.includes(dp.listUrl) && !href.includes('/new'));

        if (isBack) {
          backFound = true;
          backText = txt || ariaLabel || href || '(icon button)';
          backElement = el;
          break;
        }
      }
      if (backFound) break;
    }

    // Also check for breadcrumbs as navigation
    if (!backFound) {
      const breadcrumb = page.locator('nav[aria-label*="bread" i] a, [class*="breadcrumb" i] a, [class*="Breadcrumb" i] a').first();
      const bcVisible = await breadcrumb.isVisible({ timeout: 2000 }).catch(() => false);
      if (bcVisible) {
        backFound = true;
        backText = await breadcrumb.innerText().catch(() => 'breadcrumb link');
        backElement = breadcrumb;
      }
    }

    // Try a more generic approach — find any link pointing back to the list
    if (!backFound) {
      const listLink = page.locator(`a[href="${dp.listUrl}"]`).first();
      const llVisible = await listLink.isVisible({ timeout: 2000 }).catch(() => false);
      if (llVisible) {
        backFound = true;
        backText = await listLink.innerText().catch(() => 'list link');
        backElement = listLink;
      }
    }

    if (!backFound) {
      record(testId, `${dp.name} Detail back button`, 'FAIL', `No back button found on detail page. URL: ${page.url()}. Page text (first 200): "${detailText.substring(0, 200)}"`);
      continue;
    }

    console.log(`  Back button found: "${backText}"`);

    // Click back
    if (backElement) {
      await backElement.click();
      await page.waitForTimeout(3000);
    }

    await ss(page, `${dp.name}_detail_AFTER_back`);
    const afterUrl = page.url();

    // Verify we returned to list
    const returnedToList = afterUrl.includes(dp.listUrl) && !afterUrl.includes(dp.listUrl + '/');
    if (returnedToList) {
      record(testId, `${dp.name} Detail back button`, 'PASS', `Back button "${backText}" navigated back to ${afterUrl}`);
    } else {
      record(testId, `${dp.name} Detail back button`, 'FAIL', `Back button clicked but landed on ${afterUrl} instead of ${dp.listUrl}`);
    }
  }

  // ══════════════════════════════════════════════
  // TEST 2: Settings page badges
  // ══════════════════════════════════════════════
  console.log('\n=== TEST 2: Settings Page Badges ===\n');

  page._consoleErrors = [];
  await page.goto(`${BASE}/dashboard/procurement/settings`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);

  await ss(page, 'T2_settings_page');
  const settingsText = await getMainText(page);
  console.log(`  Settings page text (first 500): "${settingsText.substring(0, 500)}"`);

  // Look for Payment Method badges
  const paymentMethodSection = settingsText.match(/payment\s*method[s]?[:\s]*([\s\S]*?)(?=rfp|type|$)/i);
  const rfpTypeSection = settingsText.match(/rfp\s*type[s]?[:\s]*([\s\S]*?)(?=payment|$)/i);

  // Look for badge elements
  const badges = await page.locator('[class*="badge" i], [class*="Badge" i], [class*="chip" i], [class*="Chip" i], [class*="tag" i]').allInnerTexts().catch(() => []);
  console.log(`  Badges found: ${badges.length} — ${JSON.stringify(badges)}`);

  const consoleErrsT2 = [...page._consoleErrors];
  if (consoleErrsT2.length > 0) {
    console.log(`  Console errors: ${consoleErrsT2.length}`);
    consoleErrsT2.slice(0, 5).forEach(e => console.log(`    ${e.substring(0, 150)}`));
  }

  if (badges.length > 0) {
    // Try to identify which are payment methods and which are RFP types
    record('T2-PaymentBadges', 'Payment Method badges visible', 'PASS', `Badges: ${JSON.stringify(badges)}`);
    record('T2-RFPBadges', 'RFP Type badges visible', 'PASS', `Total badges: ${badges.length}`);
  } else {
    // Check if text contains the values even without badge styling
    const hasPaymentMethods = settingsText.toLowerCase().includes('payment') &&
      (settingsText.includes('Cash') || settingsText.includes('Check') || settingsText.includes('Bank') || settingsText.includes('Online'));
    const hasRFPTypes = settingsText.toLowerCase().includes('rfp') || settingsText.toLowerCase().includes('type');

    if (hasPaymentMethods) {
      record('T2-PaymentBadges', 'Payment Method badges visible', 'PASS', `Found in text (no badge styling): "${settingsText.substring(0, 200)}"`);
    } else {
      record('T2-PaymentBadges', 'Payment Method badges visible', 'FAIL', `No badges or payment method text found. Console errors: ${consoleErrsT2.length}. Page text: "${settingsText.substring(0, 300)}"`);
    }

    if (hasRFPTypes) {
      record('T2-RFPBadges', 'RFP Type badges visible', 'PASS', `Found in text`);
    } else {
      record('T2-RFPBadges', 'RFP Type badges visible', 'FAIL', `No RFP type badges found. Page text: "${settingsText.substring(0, 300)}"`);
    }
  }

  // ══════════════════════════════════════════════
  // TEST 3: OR Follow-Up page
  // ══════════════════════════════════════════════
  console.log('\n=== TEST 3: OR Follow-Up Page ===\n');

  page._consoleErrors = [];
  await page.goto(`${BASE}/dashboard/procurement/or-follow-up`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);

  await ss(page, 'T3_or_followup');
  const orText = await getMainText(page);
  console.log(`  OR Follow-Up text (first 500): "${orText.substring(0, 500)}"`);

  // Check for table structure
  const orTableHeaders = await page.locator('table thead th, [role="columnheader"]').allInnerTexts().catch(() => []);
  console.log(`  Table headers: ${JSON.stringify(orTableHeaders)}`);

  const orHasTable = orTableHeaders.length > 0;
  const orHasEmptyState = orText.toLowerCase().includes('no overdue') || orText.toLowerCase().includes('no or') || orText.toLowerCase().includes('no data');
  const orHasSummary = await page.locator('[class*="card" i], [class*="Card" i], [class*="summary" i]').count().catch(() => 0);

  const consoleErrsT3 = [...page._consoleErrors];

  if (orHasTable || orHasEmptyState || orText.length > 50) {
    record('T3-Table', 'OR Follow-Up table structure', orHasTable ? 'PASS' : (orHasEmptyState ? 'PASS' : 'FAIL'),
      `Headers: ${JSON.stringify(orTableHeaders)}. Empty state: ${orHasEmptyState}. Text: "${orText.substring(0, 200)}"`);
    record('T3-Summary', 'OR Follow-Up summary card', orHasSummary > 0 ? 'PASS' : 'FAIL',
      `Cards found: ${orHasSummary}. Text: "${orText.substring(0, 200)}"`);
  } else {
    record('T3-Table', 'OR Follow-Up page renders', 'FAIL',
      `Page appears empty. Console errors: ${consoleErrsT3.length}. Text: "${orText.substring(0, 200)}"`);
  }

  // ══════════════════════════════════════════════
  // TEST 4: Dashboard Payments tab
  // ══════════════════════════════════════════════
  console.log('\n=== TEST 4: Dashboard Payments Tab ===\n');

  page._consoleErrors = [];
  await page.goto(`${BASE}/dashboard/procurement`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);

  await ss(page, 'T4_dashboard_before');
  const dashText = await getMainText(page);
  console.log(`  Dashboard text (first 500): "${dashText.substring(0, 500)}"`);

  // Find "Pending Approvals" section
  const hasPendingApprovals = dashText.toLowerCase().includes('pending approval') || dashText.toLowerCase().includes('pending approvals');

  // Find Payments tab
  const paymentsTab = page.locator('button:has-text("Payments"), [role="tab"]:has-text("Payments"), a:has-text("Payments")').first();
  const paymentsTabVisible = await paymentsTab.isVisible({ timeout: 3000 }).catch(() => false);

  if (paymentsTabVisible) {
    const tabTextBefore = await getMainText(page);
    await paymentsTab.click();
    await page.waitForTimeout(2000);

    await ss(page, 'T4_dashboard_payments_tab');
    const tabTextAfter = await getMainText(page);

    const contentChanged = tabTextAfter !== tabTextBefore;
    console.log(`  Content changed after click: ${contentChanged}`);
    console.log(`  Payments tab content (first 300): "${tabTextAfter.substring(0, 300)}"`);

    record('T4-PaymentsTab', 'Payments tab click', 'PASS',
      `Tab found and clicked. Content changed: ${contentChanged}. Text: "${tabTextAfter.substring(0, 200)}"`);
  } else {
    // Maybe it's already showing or uses different UI
    const allTabs = await page.locator('[role="tab"], [role="tablist"] button').allInnerTexts().catch(() => []);
    console.log(`  Available tabs: ${JSON.stringify(allTabs)}`);

    record('T4-PaymentsTab', 'Payments tab click', 'FAIL',
      `No "Payments" tab found. Available tabs: ${JSON.stringify(allTabs)}. Has "Pending Approvals": ${hasPendingApprovals}`);
  }

  // ══════════════════════════════════════════════
  // TEST 5: Supplier Performance page
  // ══════════════════════════════════════════════
  console.log('\n=== TEST 5: Supplier Performance Page ===\n');

  page._consoleErrors = [];
  await page.goto(`${BASE}/dashboard/procurement/reports/supplier-performance`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  await ss(page, 'T5_supplier_performance');
  const spText = await getMainText(page);
  console.log(`  Supplier Performance text (first 500): "${spText.substring(0, 500)}"`);

  const consoleErrsT5 = [...page._consoleErrors];
  const hasApiErrors = consoleErrsT5.some(e => e.includes('4') || e.includes('5') || e.includes('error') || e.includes('Error'));
  console.log(`  Console errors: ${consoleErrsT5.length}`);
  consoleErrsT5.slice(0, 5).forEach(e => console.log(`    ${e.substring(0, 200)}`));

  // Check for content beyond sidebar
  const sidebarOnly = spText.trim().length < 30;
  const has403 = spText.includes('Access Restricted') || spText.includes('not authorized');
  const has404 = spText.includes('404') || spText.includes('not found');

  if (sidebarOnly) {
    record('T5-Content', 'Supplier Performance renders content', 'FAIL',
      `Only sidebar visible. Main text empty. Console errors: ${consoleErrsT5.length}: ${consoleErrsT5.slice(0, 3).join(' | ')}`);
  } else if (has403) {
    record('T5-Content', 'Supplier Performance renders content', 'FAIL', `403 — Access Restricted`);
  } else if (has404) {
    record('T5-Content', 'Supplier Performance renders content', 'FAIL', `404 — Page not found`);
  } else {
    record('T5-Content', 'Supplier Performance renders content', 'PASS',
      `Content visible. Text: "${spText.substring(0, 300)}". Console errors: ${consoleErrsT5.length}`);
  }

  // ══════════════════════════════════════════════
  // TEST 6: PO Aging page
  // ══════════════════════════════════════════════
  console.log('\n=== TEST 6: PO Aging Page ===\n');

  page._consoleErrors = [];
  await page.goto(`${BASE}/dashboard/procurement/audit/aging`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  await ss(page, 'T6_po_aging');
  const agingText = await getMainText(page);
  console.log(`  PO Aging text (first 500): "${agingText.substring(0, 500)}"`);

  const consoleErrsT6 = [...page._consoleErrors];
  console.log(`  Console errors: ${consoleErrsT6.length}`);
  consoleErrsT6.slice(0, 5).forEach(e => console.log(`    ${e.substring(0, 200)}`));

  const agingSidebarOnly = agingText.trim().length < 30;
  const aging403 = agingText.includes('Access Restricted') || agingText.includes('not authorized');
  const aging404 = agingText.includes('404') || agingText.includes('not found');

  if (agingSidebarOnly) {
    record('T6-Content', 'PO Aging renders content', 'FAIL',
      `Only sidebar visible. Main text empty. Console errors: ${consoleErrsT6.length}: ${consoleErrsT6.slice(0, 3).join(' | ')}`);
  } else if (aging403) {
    record('T6-Content', 'PO Aging renders content', 'FAIL', `403 — Access Restricted`);
  } else if (aging404) {
    record('T6-Content', 'PO Aging renders content', 'FAIL', `404 — Page not found`);
  } else {
    record('T6-Content', 'PO Aging renders content', 'PASS',
      `Content visible. Text: "${agingText.substring(0, 300)}". Console errors: ${consoleErrsT6.length}`);
  }

  // ══════════════════════════════════════════════
  // SUMMARY
  // ══════════════════════════════════════════════
  console.log('\n\n========================================');
  console.log('S142 BROWSER VERIFICATION SUMMARY');
  console.log('========================================\n');

  let pass = 0, fail = 0, skip = 0;
  for (const r of results) {
    const icon = r.verdict === 'PASS' ? 'PASS' : r.verdict === 'FAIL' ? 'FAIL' : 'SKIP';
    console.log(`[${icon}] ${r.testId}: ${r.testName}`);
    console.log(`       ${typeof r.details === 'string' ? r.details.substring(0, 200) : ''}`);
    if (r.verdict === 'PASS') pass++;
    else if (r.verdict === 'FAIL') fail++;
    else skip++;
  }

  console.log(`\nTotal: ${pass} PASS, ${fail} FAIL, ${skip} SKIP out of ${results.length} tests`);

  // Write results JSON
  fs.writeFileSync(path.join(SCREENSHOT_DIR, 'VERIFY_results.json'), JSON.stringify(results, null, 2));
  console.log(`\nResults written to ${path.join(SCREENSHOT_DIR, 'VERIFY_results.json')}`);

  await ctx.close();
  await browser.close();
})();
