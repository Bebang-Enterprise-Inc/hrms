/**
 * S142 Shared Utilities — Procurement Module QA Audit
 *
 * All test scripts import from this file. Contains:
 * - Login, screenshot, evidence helpers
 * - Result/defect recording
 * - Anti-corner-cutting assertion helpers that read TEXT VALUES
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

export const BASE = 'https://my.bebang.ph';
export const FRAPPE = 'https://hq.bebang.ph';
export const SCREENSHOT_DIR = 'tmp/s142_screenshots';
export const ARTIFACT_DIR = 'output/l3/S142/artifacts';
export const EVIDENCE_DIR = 'output/l3/evidence';
export const OUTPUT_DIR = 'output/l3/S142';

// ── Accounts ──
export const ACCOUNTS = {
  ceo:       { email: 'sam@bebang.ph',            password: '2289454' },
  staff:     { email: 'test.hr@bebang.ph',        password: 'BeiTest2026!' },
  warehouse: { email: 'test.warehouse@bebang.ph', password: 'BeiTest2026!' },
  crew:      { email: 'test.crew@bebang.ph',      password: 'BeiTest2026!' },
};

// ── Directories ──
export function ensureDirs() {
  for (const d of [SCREENSHOT_DIR, ARTIFACT_DIR, EVIDENCE_DIR, OUTPUT_DIR]) {
    fs.mkdirSync(d, { recursive: true });
  }
}

// ── Browser + Login ──
export async function launchBrowser() {
  return chromium.launch({ headless: true });
}

export async function loginAs(browser, role) {
  const { email, password } = ACCOUNTS[role];
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  // Collect console errors
  const consoleErrors = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('input[name="email"], input[autocomplete="username"]').first().fill(email);
  await page.locator('input[name="password"], input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL('**/dashboard**', { timeout: 30000 });
  console.log(`  ✓ Logged in as ${role} (${email})`);
  return { ctx, page, consoleErrors };
}

// ── Screenshot ──
export async function screenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

// ── Page Classification ──
export async function classifyPage(page) {
  const text = await page.innerText('main').catch(() => '');
  const url = page.url();

  if (text.includes('Access Restricted') || text.includes('not authorized') || text.includes("don't have permission"))
    return { status: '403', text };
  if (text.includes('404') || text.includes('not found') || text.includes('Page not found'))
    return { status: '404', text };
  if (text.trim().length < 30)
    return { status: 'SHELL', text };

  // Check for real data indicators
  const hasTable = await page.locator('table tbody tr').count().catch(() => 0);
  const hasCards = await page.locator('[class*="Card"]').count().catch(() => 0);
  const hasForm = await page.locator('form, input, select, textarea').count().catch(() => 0);

  if (hasTable > 0 || hasCards > 2 || hasForm > 0) {
    // Check for actual data vs empty state
    const emptyIndicators = ['no data', 'no items', 'no records', 'nothing here', 'No purchase', 'No suppliers', 'No goods', 'No invoices', 'No payment', 'No overdue'];
    const isEmptyState = emptyIndicators.some(ind => text.toLowerCase().includes(ind.toLowerCase()));
    if (isEmptyState) return { status: 'EMPTY', text };
    return { status: 'WORKS', text };
  }

  return { status: 'WORKS', text }; // Default for pages with cards/content but no table
}

// ── Anti-Corner-Cutting Assertions ──

/**
 * Read the actual TEXT value from a locator. NEVER just check .count() > 0.
 * Returns { found: boolean, text: string }
 */
export async function readText(page, locator, description) {
  const el = page.locator(locator).first();
  const visible = await el.isVisible({ timeout: 3000 }).catch(() => false);
  if (!visible) return { found: false, text: '' };
  const text = await el.innerText().catch(() => '');
  console.log(`    [TEXT] ${description}: "${text.substring(0, 100)}"`);
  return { found: true, text };
}

/**
 * Read ALL text content of a table's visible rows (first 5).
 * Returns array of row text contents.
 */
export async function readTableRows(page, maxRows = 5) {
  const rows = [];
  const count = await page.locator('table tbody tr').count().catch(() => 0);
  for (let i = 0; i < Math.min(count, maxRows); i++) {
    const text = await page.locator(`table tbody tr:nth-child(${i + 1})`).innerText().catch(() => '');
    rows.push(text);
  }
  return { count, rows };
}

/**
 * Open a Select/combobox and read ALL option texts.
 * Returns the option labels as an array.
 */
export async function readSelectOptions(page, triggerLocator) {
  const trigger = page.locator(triggerLocator).first();
  const visible = await trigger.isVisible({ timeout: 3000 }).catch(() => false);
  if (!visible) return { found: false, options: [] };

  await trigger.click();
  await page.waitForTimeout(500);

  const options = await page.locator('[role="option"]').allInnerTexts().catch(() => []);
  // Close dropdown
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  console.log(`    [OPTIONS] ${options.length} options: ${JSON.stringify(options.slice(0, 8))}${options.length > 8 ? '...' : ''}`);
  return { found: true, options };
}

/**
 * Click a button/link and verify navigation to a URL pattern.
 * Returns { clicked: boolean, navigated: boolean, url: string }
 */
export async function clickAndVerifyNav(page, locator, expectedUrlPattern, description) {
  const el = page.locator(locator).first();
  const visible = await el.isVisible({ timeout: 3000 }).catch(() => false);
  if (!visible) {
    console.log(`    [CLICK] ${description}: NOT FOUND`);
    return { clicked: false, navigated: false, url: '' };
  }
  const beforeUrl = page.url();
  await el.click();
  await page.waitForTimeout(2000);
  const afterUrl = page.url();
  const navigated = afterUrl !== beforeUrl && (expectedUrlPattern ? afterUrl.includes(expectedUrlPattern) : true);
  console.log(`    [CLICK] ${description}: ${navigated ? 'navigated' : 'no navigation'} → ${afterUrl}`);
  return { clicked: true, navigated, url: afterUrl };
}

/**
 * Click a button and verify a dialog/modal appears.
 * Returns { clicked: boolean, dialogVisible: boolean, dialogText: string }
 */
export async function clickAndVerifyDialog(page, buttonLocator, description) {
  const btn = page.locator(buttonLocator).first();
  const visible = await btn.isVisible({ timeout: 3000 }).catch(() => false);
  if (!visible) {
    console.log(`    [DIALOG] ${description}: button NOT FOUND`);
    return { clicked: false, dialogVisible: false, dialogText: '' };
  }
  await btn.click();
  await page.waitForTimeout(1000);

  // Check for dialog/modal
  const dialog = page.locator('[role="dialog"], [role="alertdialog"], [class*="DialogContent"]').first();
  const dialogVisible = await dialog.isVisible({ timeout: 3000 }).catch(() => false);
  const dialogText = dialogVisible ? await dialog.innerText().catch(() => '') : '';

  console.log(`    [DIALOG] ${description}: ${dialogVisible ? 'OPENED' : 'NOT FOUND'} — "${dialogText.substring(0, 80)}"`);

  // Close dialog if opened
  if (dialogVisible) {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
  }

  return { clicked: true, dialogVisible, dialogText };
}

// ── Result Recording ──
export class ResultTracker {
  constructor() {
    this.results = [];
    this.defects = [];
    this.pageAudit = [];
    this.ctaMatrix = [];
  }

  pass(id, test, detail) {
    this.results.push({ id, test, status: 'PASS', detail, error: null });
    console.log(`  [PASS] ${id}: ${test}`);
  }

  fail(id, test, detail, error) {
    this.results.push({ id, test, status: 'FAIL', detail, error });
    console.log(`  [FAIL] ${id}: ${test} — ${error}`);
  }

  skip(id, test, reason) {
    this.results.push({ id, test, status: 'SKIP', detail: reason, error: null });
    console.log(`  [SKIP] ${id}: ${test} — ${reason}`);
  }

  defect(desc, severity, type, scenario, error, impact, rootCause, suggestedFix) {
    this.defects.push({
      desc, severity, type, scenario, error, impact, rootCause, suggestedFix,
      firstSeen: new Date().toISOString()
    });
    console.log(`  [DEFECT] [${severity}] ${desc}`);
  }

  addPageResult(entry) { this.pageAudit.push(entry); }
  addCTA(entry) { this.ctaMatrix.push(entry); }

  recordCTA(page, ctaId, element, action, result, extra = {}) {
    this.ctaMatrix.push({ page, cta_id: ctaId, element, action, result, ...extra });
    if (result === 'WORKS') {
      this.pass(ctaId, `${element}: ${action}`, JSON.stringify(extra).substring(0, 200));
    } else {
      this.fail(ctaId, `${element}: ${action}`, '', result);
    }
  }

  // ── Write to disk ──
  writeAll() {
    fs.writeFileSync(path.join(OUTPUT_DIR, `procurement_audit_${new Date().toISOString().split('T')[0]}.json`),
      JSON.stringify(this.results, null, 2));

    fs.writeFileSync('tmp/s142_page_audit.json', JSON.stringify(this.pageAudit, null, 2));
    fs.writeFileSync('tmp/s142_cta_matrix.json', JSON.stringify(this.ctaMatrix, null, 2));

    if (this.defects.length > 0) {
      let md = '# S142 Procurement Module QA Audit — Defects\n\n';
      md += `**Run Date:** ${new Date().toISOString()}\n`;
      md += `**Environment:** ${BASE}\n\n`;
      for (const d of this.defects) {
        md += `## DEFECT: ${d.desc}\n`;
        md += `- **Severity:** ${d.severity}\n`;
        md += `- **Type:** ${d.type}\n`;
        md += `- **Scenario:** ${d.scenario}\n`;
        md += `- **Error:** ${d.error}\n`;
        md += `- **Impact:** ${d.impact}\n`;
        md += `- **Root Cause:** ${d.rootCause}\n`;
        md += `- **Suggested Fix:** ${d.suggestedFix}\n`;
        md += `- **First Seen:** ${d.firstSeen}\n\n`;
      }
      fs.writeFileSync(path.join(OUTPUT_DIR, 'DEFECTS.md'), md);
    }
  }

  printSummary() {
    console.log('\n========================================');
    console.log(`L3 S142 PROCUREMENT QA AUDIT (${new Date().toISOString().split('T')[0]})`);
    console.log('========================================');

    let pass = 0, fail = 0, skip = 0;
    for (const r of this.results) {
      const icon = r.status === 'PASS' ? '✓' : r.status === 'FAIL' ? '✗' : '⊘';
      console.log(`[${r.status}] ${r.id}: ${r.test}${r.error ? ' — ' + r.error : ''}`);
      if (r.status === 'PASS') pass++;
      else if (r.status === 'FAIL') fail++;
      else skip++;
    }

    console.log(`\nTotal: ${pass}/${this.results.length} PASS, ${fail} FAIL, ${skip} SKIP`);
    console.log(`Pages audited: ${this.pageAudit.length}`);
    console.log(`CTAs tested: ${this.ctaMatrix.length}`);
    console.log(`Defects found: ${this.defects.length}`);

    if (this.defects.length > 0) {
      console.log('\nDEFECTS:');
      for (const d of this.defects) console.log(`  [${d.severity}] ${d.desc}`);
    }
  }
}

// ── Page Inventory ──
export const PAGES = [
  { id: 'A1',  route: '/dashboard/procurement',                                    name: 'Dashboard', section: 'Core', needsId: false },
  { id: 'A2',  route: '/dashboard/procurement/purchase-requisitions',               name: 'PR List', section: 'Core', needsId: false },
  { id: 'A3',  route: '/dashboard/procurement/purchase-requisitions/new',           name: 'PR New', section: 'Core', needsId: false },
  { id: 'A4',  route: '/dashboard/procurement/purchase-requisitions/[id]',          name: 'PR Detail', section: 'Core', needsId: true, listPage: 'A2' },
  { id: 'A5',  route: '/dashboard/procurement/purchase-orders',                     name: 'PO List', section: 'Core', needsId: false },
  { id: 'A6',  route: '/dashboard/procurement/purchase-orders/new',                 name: 'PO New', section: 'Core', needsId: false },
  { id: 'A7',  route: '/dashboard/procurement/purchase-orders/[id]',                name: 'PO Detail', section: 'Core', needsId: true, listPage: 'A5' },
  { id: 'A8',  route: '/dashboard/procurement/suppliers',                           name: 'Supplier List', section: 'Core', needsId: false },
  { id: 'A9',  route: '/dashboard/procurement/suppliers/new',                       name: 'Supplier New', section: 'Core', needsId: false },
  { id: 'A10', route: '/dashboard/procurement/suppliers/[id]',                      name: 'Supplier Detail', section: 'Core', needsId: true, listPage: 'A8' },
  { id: 'A11', route: '/dashboard/procurement/suppliers/[id]/edit',                 name: 'Supplier Edit', section: 'Core', needsId: true, listPage: 'A8' },
  { id: 'A12', route: '/dashboard/procurement/goods-receipts',                      name: 'GR List', section: 'Core', needsId: false },
  { id: 'A13', route: '/dashboard/procurement/goods-receipts/new',                  name: 'GR New', section: 'Core', needsId: false },
  { id: 'A14', route: '/dashboard/procurement/goods-receipts/[id]',                 name: 'GR Detail', section: 'Core', needsId: true, listPage: 'A12' },
  { id: 'A15', route: '/dashboard/procurement/invoices',                            name: 'Invoice List', section: 'Core', needsId: false },
  { id: 'A16', route: '/dashboard/procurement/invoices/new',                        name: 'Invoice New', section: 'Core', needsId: false },
  { id: 'A17', route: '/dashboard/procurement/invoices/[id]',                       name: 'Invoice Detail', section: 'Core', needsId: true, listPage: 'A15' },
  { id: 'A18', route: '/dashboard/procurement/payments',                            name: 'Payment List', section: 'Core', needsId: false },
  { id: 'A19', route: '/dashboard/procurement/payments/new',                        name: 'Payment New', section: 'Core', needsId: false },
  { id: 'A20', route: '/dashboard/procurement/payments/[id]',                       name: 'Payment Detail', section: 'Core', needsId: true, listPage: 'A18' },
  { id: 'A21', route: '/dashboard/procurement/approvals',                           name: 'Approvals', section: 'Workflow', needsId: false },
  { id: 'A22', route: '/dashboard/procurement/or-follow-up',                        name: 'OR Follow-Up', section: 'Workflow', needsId: false },
  { id: 'A23', route: '/dashboard/procurement/critical-items-control-tower',        name: 'Critical Items CT', section: 'Risk', needsId: false },
  { id: 'A24', route: '/dashboard/procurement/critical-stockout-incidents',         name: 'Stockout Incidents', section: 'Risk', needsId: false },
  { id: 'A28', route: '/dashboard/procurement/reports',                             name: 'Reports Hub', section: 'Reports', needsId: false },
  { id: 'A29', route: '/dashboard/procurement/reports/monthly-spend',               name: 'Monthly Spend', section: 'Reports', needsId: false },
  { id: 'A30', route: '/dashboard/procurement/reports/supplier-performance',        name: 'Supplier Performance', section: 'Reports', needsId: false },
  { id: 'A31', route: '/dashboard/procurement/reports/single-source-suppliers',     name: 'Single-Source', section: 'Reports', needsId: false },
  { id: 'A32', route: '/dashboard/procurement/reports/three-way-match',             name: 'Three-Way Match', section: 'Reports', needsId: false },
  { id: 'A33', route: '/dashboard/procurement/reports/payment-disbursement',        name: 'Payment Disbursement', section: 'Reports', needsId: false },
  { id: 'A34', route: '/dashboard/procurement/reports/goods-receipt-log',           name: 'GR Log', section: 'Reports', needsId: false },
  { id: 'A35', route: '/dashboard/procurement/audit/aging',                         name: 'PO Aging', section: 'Audit', needsId: false },
  { id: 'A36', route: '/dashboard/procurement/audit/price-history',                 name: 'Price History', section: 'Audit', needsId: false },
  { id: 'A37', route: '/dashboard/procurement/settings',                            name: 'Settings', section: 'Admin', needsId: false },
  { id: 'A38', route: '/dashboard/accounting/soa',                                  name: 'SOA', section: 'Cross-module', needsId: false },
];

// Risky item pages — need dynamic IDs from control tower
export const RISKY_PAGES = [
  { id: 'A25', routeTemplate: '/dashboard/procurement/critical-items-control-tower/risky-items/{item}/{warehouse}', name: 'Risky Item Detail' },
  { id: 'A26', routeTemplate: '/dashboard/procurement/critical-items-control-tower/risky-items/{item}/{warehouse}/delayed-deliveries', name: 'Delayed Deliveries' },
  { id: 'A27', routeTemplate: '/dashboard/procurement/critical-items-control-tower/risky-items/{item}/{warehouse}/inbound-pipeline', name: 'Inbound Pipeline' },
];
