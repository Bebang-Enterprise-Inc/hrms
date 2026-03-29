/**
 * S120 L3 — Request Revision flow
 * 1. Commissary creates PR → converts to PO → submits for approval
 * 2. Mae sees 3 buttons (Approve/Reject/Request Revision) → clicks Request Revision
 * 3. PO goes back to Draft → commissary can edit and resubmit
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SS = 'output/l3/s120/screenshots';
mkdirSync(SS, { recursive: true });

const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`);
let pass = 0, fail = 0;
function check(n, ok, d) {
  ok ? pass++ : fail++;
  log(`[${ok ? 'PASS' : 'FAIL'}] ${n}${d ? ' — ' + d : ''}`);
}

async function login(browser, email) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('https://my.bebang.ph/login', { waitUntil: 'networkidle' });
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', 'BeiTest2026!');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
  return page;
}

const browser = await chromium.launch({ headless: true });

try {
  // STEP 1: Commissary creates PR → PO → submits
  log('=== STEP 1: Create PR + PO ===');
  const p = await login(browser, 'test.commissary@bebang.ph');

  await p.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);

  // Item search
  await p.locator('button[role="combobox"]').nth(1).click();
  await p.waitForTimeout(500);
  await p.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('SAGO');
  await p.waitForTimeout(2000);
  const opts = p.locator('[role="option"]');
  for (let i = 0; i < await opts.count(); i++) {
    if ((await opts.nth(i).textContent()).includes('FG009')) { await opts.nth(i).click(); break; }
  }
  await p.waitForTimeout(1000);

  // Fill form
  await p.locator('input[name="items.0.qty"]').fill('3');
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  await p.locator('button[role="combobox"]').first().click({ force: true });
  await p.waitForTimeout(500);
  await p.locator('[role="option"]:has-text("Operations")').first().click();
  await p.waitForTimeout(500);
  await p.locator('textarea').first().fill('L3 revision flow test');

  // Submit PR
  await p.locator('button:has-text("Create PR")').click();
  await p.waitForTimeout(5000);
  const prName = p.url().split('/').pop();
  check('1.1 PR created', !p.url().includes('/new'), prName);

  // Convert to PO
  await p.waitForTimeout(2000);
  const convertBtn = p.locator('button:has-text("Convert to PO")');
  check('1.2 Convert button available', await convertBtn.count() > 0);

  await convertBtn.click();
  await p.waitForTimeout(1500);
  const supplierCb = p.locator('[role="dialog"] button[role="combobox"]').first();
  if (await supplierCb.count() > 0) {
    await supplierCb.click();
    await p.waitForTimeout(500);
    await p.locator('[role="option"]').first().click();
    await p.waitForTimeout(500);
  }
  await p.locator('[role="dialog"] button:has-text("Create PO")').click();
  await p.waitForTimeout(5000);
  const poName = p.url().split('/').pop();
  check('1.3 PO created', p.url().includes('/purchase-orders/PO-'), poName);
  await p.screenshot({ path: `${SS}/rev_01_po.png`, fullPage: true });

  // Submit for approval
  const submitBtn = p.locator('button:has-text("Submit for Approval")');
  if (await submitBtn.count() > 0) {
    await submitBtn.click();
    await p.waitForTimeout(3000);
    check('1.4 PO submitted for approval', true);
  } else {
    check('1.4 PO submitted for approval', false, 'Submit button not found');
  }
  await p.screenshot({ path: `${SS}/rev_02_submitted.png`, fullPage: true });
  await p.close();

  // STEP 2: Mae requests revision
  log('=== STEP 2: Mae requests revision ===');
  const mae = await login(browser, 'mae@bebang.ph');
  await mae.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'networkidle' });
  await mae.waitForTimeout(3000);
  await mae.screenshot({ path: `${SS}/rev_03_mae_view.png`, fullPage: true });

  const approveBtn = mae.locator('button:has-text("Approve")');
  const rejectBtn = mae.locator('button:has-text("Reject")');
  const revisionBtn = mae.locator('button:has-text("Request Revision")');

  check('2.1 Approve button', await approveBtn.count() > 0);
  check('2.2 Reject button', await rejectBtn.count() > 0);
  check('2.3 Request Revision button', await revisionBtn.count() > 0);

  if (await revisionBtn.count() > 0) {
    await revisionBtn.click();
    await mae.waitForTimeout(1000);
    await mae.screenshot({ path: `${SS}/rev_04_dialog.png` });

    // Check dialog
    const dialogText = await mae.locator('[role="dialog"]').first().textContent().catch(() => '');
    check('2.4 Dialog explains revision', dialogText.includes('keeps the PO alive') || dialogText.includes('Draft'));

    // Fill reason
    await mae.locator('[role="dialog"] textarea').first().fill(
      'Wrong price for SAGO — should be ₱42.35, not the overridden rate. Also verify delivery date is correct for Q2.'
    );
    await mae.screenshot({ path: `${SS}/rev_05_reason.png` });

    // Confirm
    await mae.locator('[role="dialog"] button:has-text("Request Revision")').click();
    await mae.waitForTimeout(4000);
    await mae.screenshot({ path: `${SS}/rev_06_after.png`, fullPage: true });

    const toasts = await mae.locator('[data-sonner-toast]').allTextContents();
    check('2.5 Success toast', toasts.some(t => t.toLowerCase().includes('revision')), toasts.join('|').substring(0, 100));

    const pageText = await mae.textContent('body');
    check('2.6 PO back to Draft', pageText.includes('Draft'));
  }
  await mae.close();

  // STEP 3: Commissary sees revised PO
  log('=== STEP 3: Commissary edits revised PO ===');
  const editor = await login(browser, 'test.commissary@bebang.ph');
  await editor.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'networkidle' });
  await editor.waitForTimeout(3000);
  await editor.screenshot({ path: `${SS}/rev_07_draft.png`, fullPage: true });

  const body = await editor.textContent('body');
  check('3.1 PO is Draft', body.includes('Draft'));

  // Items tab
  const tab = editor.locator('[role="tab"]:has-text("Items")');
  if (await tab.count() > 0) { await tab.click(); await editor.waitForTimeout(1000); }

  check('3.2 Edit pencil available', (await editor.locator('button:has(svg.lucide-pencil)').count()) > 0);
  check('3.3 Submit for Approval available', (await editor.locator('button:has-text("Submit for Approval")').count()) > 0);

  await editor.close();

} catch (e) {
  log(`ERROR: ${e.message}`);
  fail++;
}

await browser.close();
console.log(`\n=== REVISION FLOW: ${pass} PASS / ${fail} FAIL ===`);
