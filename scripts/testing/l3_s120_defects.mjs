/**
 * S120 Defect fixes test — only testing the 3 fixes:
 * 1. PR auto-fills price from Item master when ₱0
 * 2. PR→PO fallback to standard_rate when contracted+estimated are both 0
 * 3. "Submit for Approval" button removed from PR page
 */
import { chromium } from 'playwright';

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
  const p = await login(browser, 'test.commissary@bebang.ph');

  // DEFECT 1: Create PR with item, verify price auto-fills (not ₱0)
  log('=== DEFECT 1: PR price auto-fill from Item master ===');
  await p.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);

  // Select FG009
  await p.locator('button[role="combobox"]').nth(1).click();
  await p.waitForTimeout(500);
  await p.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('SAGO');
  await p.waitForTimeout(2000);
  for (let i = 0; i < await p.locator('[role="option"]').count(); i++) {
    if ((await p.locator('[role="option"]').nth(i).textContent()).includes('FG009')) {
      await p.locator('[role="option"]').nth(i).click();
      break;
    }
  }
  await p.waitForTimeout(1000);
  const rate = parseFloat(await p.locator('input[name="items.0.estimated_rate"]').inputValue());
  check('1.1 Price auto-filled on form', rate > 0, `₱${rate}`);

  // Fill and submit
  await p.locator('input[name="items.0.qty"]').fill('2');
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  await p.locator('button[role="combobox"]').first().click({ force: true });
  await p.waitForTimeout(500);
  await p.locator('[role="option"]:has-text("Operations")').first().click();
  await p.waitForTimeout(500);
  await p.locator('textarea').first().fill('Defect test');

  await p.locator('button:has-text("Create PR")').click();
  await p.waitForTimeout(5000);
  const prUrl = p.url();
  const prName = prUrl.split('/').pop();
  check('1.2 PR created', !prUrl.includes('/new'), prName);

  // Check the PR detail shows non-zero price
  await p.waitForTimeout(2000);
  const prBody = await p.textContent('body');
  check('1.3 PR detail shows price > ₱0', prBody.includes('42.35') || prBody.includes('42,35'));
  const hasZero = prBody.includes('₱0.00') && !prBody.includes('₱0.00 →'); // exclude banner text
  check('1.4 PR detail does NOT show ₱0.00', !hasZero);

  // DEFECT 2: Convert to PO, verify price carries through
  log('=== DEFECT 2: PR→PO price fallback chain ===');
  await p.locator('button:has-text("Convert to PO")').click();
  await p.waitForTimeout(1500);
  const sCb = p.locator('[role="dialog"] button[role="combobox"]').first();
  if (await sCb.count() > 0) {
    await sCb.click();
    await p.waitForTimeout(500);
    await p.locator('[role="option"]').first().click();
    await p.waitForTimeout(500);
  }
  await p.locator('[role="dialog"] button:has-text("Create PO")').click();
  await p.waitForTimeout(5000);
  const poUrl = p.url();
  const poName = poUrl.split('/').pop();
  check('2.1 PO created', poUrl.includes('/purchase-orders/PO-'), poName);

  const poBody = await p.textContent('body');
  check('2.2 PO has price > ₱0', poBody.includes('42.35') || poBody.includes('42,35'));
  await p.close();

  // DEFECT 3: "Submit for Approval" button removed from PR page
  log('=== DEFECT 3: Submit for Approval removed ===');
  const p2 = await login(browser, 'test.commissary@bebang.ph');

  // Create another PR to check the button
  await p2.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await p2.waitForTimeout(3000);
  await p2.locator('button[role="combobox"]').nth(1).click();
  await p2.waitForTimeout(500);
  await p2.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('SAGO');
  await p2.waitForTimeout(2000);
  for (let i = 0; i < await p2.locator('[role="option"]').count(); i++) {
    if ((await p2.locator('[role="option"]').nth(i).textContent()).includes('FG009')) {
      await p2.locator('[role="option"]').nth(i).click();
      break;
    }
  }
  await p2.waitForTimeout(1000);
  await p2.locator('input[name="items.0.qty"]').fill('1');
  await p2.keyboard.press('Escape');
  await p2.waitForTimeout(300);
  await p2.locator('button[role="combobox"]').first().click({ force: true });
  await p2.waitForTimeout(500);
  await p2.locator('[role="option"]:has-text("Operations")').first().click();
  await p2.waitForTimeout(500);
  await p2.locator('textarea').first().fill('Defect 3 test');
  await p2.locator('button:has-text("Create PR")').click();
  await p2.waitForTimeout(5000);

  // Check PR detail page — should NOT have Submit for Approval button
  await p2.waitForTimeout(2000);
  const submitBtn = p2.locator('button:has-text("Submit for Approval")');
  const hasSubmitBtn = await submitBtn.count() > 0;
  check('3.1 "Submit for Approval" button REMOVED', !hasSubmitBtn, hasSubmitBtn ? 'STILL PRESENT' : 'gone');

  // Should still have Convert to PO button
  const convertBtn = p2.locator('button:has-text("Convert to PO")');
  check('3.2 "Convert to PO" button present', await convertBtn.count() > 0);

  await p2.close();
} catch (e) {
  log(`ERROR: ${e.message}`);
  fail++;
}

await browser.close();
console.log(`\n=== DEFECT FIXES: ${pass} PASS / ${fail} FAIL ===`);
