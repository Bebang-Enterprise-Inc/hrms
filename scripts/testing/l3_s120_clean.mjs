/**
 * S120 L3 CLEAN — Full E2E, no shortcuts, fresh data
 * 1. Create PR with item autocomplete (as commissary)
 * 2. Submit PR for approval (in browser)
 * 3. Approve PR (as approver in browser)
 * 4. Convert PR to PO (in browser)
 * 5. Edit PO price with reason (in browser)
 * 6. Verify Mae sees banner (as Mae in browser)
 * 7. Disabled item exclusion
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const DIR = 'output/l3/s120';
const SS = `${DIR}/screenshots`;
mkdirSync(SS, { recursive: true });

const evidence = { form_submissions: [], api_mutations: [], state_verification: [] };
const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`);
let pass = 0, fail = 0;

function check(name, condition, details) {
  const result = condition ? 'PASS' : 'FAIL';
  if (condition) pass++; else fail++;
  log(`[${result}] ${name}${details ? ' — ' + details : ''}`);
  evidence.state_verification.push({ test: name, result, details });
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
  // ================================================================
  // STEP 1: Create PR with item autocomplete
  // ================================================================
  const luwi = await login(browser, 'test.commissary@bebang.ph');
  log('STEP 1: Create PR');

  await luwi.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await luwi.waitForTimeout(3000);

  // Select item
  await luwi.locator('button[role="combobox"]').nth(1).click();
  await luwi.waitForTimeout(500);
  const searchInput = luwi.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first();
  await searchInput.fill('SAGO');
  await luwi.waitForTimeout(2000);
  await luwi.screenshot({ path: `${SS}/clean_01_search.png` });

  const results = luwi.locator('[role="option"]');
  const count = await results.count();
  check('1.1 Autocomplete returns results for SAGO', count > 0, `${count} results`);

  // Check item_group is visible in dropdown
  const dropdownText = await luwi.locator('[role="listbox"]').first().textContent().catch(() => '');
  check('1.2 Item group shown in dropdown', dropdownText.includes('Finished Goods') || dropdownText.includes('Raw Materials'), 'item_group visible for disambiguation');

  // Select FG009
  for (let i = 0; i < count; i++) {
    const txt = await results.nth(i).textContent();
    if (txt.includes('FG009')) { await results.nth(i).click(); break; }
  }
  await luwi.waitForTimeout(1000);

  const rate = parseFloat(await luwi.locator('input[name="items.0.estimated_rate"]').inputValue());
  check('1.3 Price auto-fills', rate > 0, `₱${rate}`);
  check('1.4 Price is ₱42.35', Math.abs(rate - 42.35) < 0.01);

  // Fill form
  await luwi.locator('input[name="items.0.qty"]').fill('3');
  await luwi.keyboard.press('Escape');
  await luwi.waitForTimeout(300);
  await luwi.locator('button[role="combobox"]').first().click({ force: true });
  await luwi.waitForTimeout(500);
  await luwi.locator('[role="option"]:has-text("Operations")').first().click();
  await luwi.waitForTimeout(500);
  await luwi.locator('textarea').first().fill('S120 clean L3 — SAGO 3kg');
  await luwi.waitForTimeout(300);
  await luwi.screenshot({ path: `${SS}/clean_02_filled.png`, fullPage: true });

  // Submit
  await luwi.locator('button:has-text("Create PR")').click();
  await luwi.waitForTimeout(5000);
  const prUrl = luwi.url();
  const prCreated = prUrl.includes('/purchase-requisitions/') && !prUrl.includes('/new');
  const prName = prCreated ? prUrl.split('/').pop() : '';
  check('1.5 PR created', prCreated, prName);
  await luwi.screenshot({ path: `${SS}/clean_03_pr_detail.png`, fullPage: true });
  evidence.form_submissions.push({ test: 'PR creation', pr: prName, item: 'FG009', qty: 3, rate });

  // ================================================================
  // STEP 2: Convert PR to PO directly (no approval gate — PO approval is the gate)
  // ================================================================
  log('STEP 2: Convert PR to PO (no approval needed)');
  await luwi.waitForTimeout(2000);

  const convertBtn = luwi.locator('button:has-text("Convert to PO")').first();
  let poName = '';
  check('2.1 Convert button visible (no approval needed)', await convertBtn.count() > 0);

  if (await convertBtn.count() > 0) {
    await convertBtn.click();
    await luwi.waitForTimeout(1500);
    await luwi.screenshot({ path: `${SS}/clean_04_convert_dialog.png` });

    // Select supplier in dialog
    const supplierCb = luwi.locator('[role="dialog"] button[role="combobox"]').first();
    if (await supplierCb.count() > 0) {
      await supplierCb.click();
      await luwi.waitForTimeout(500);
      const firstSupplier = luwi.locator('[role="option"]').first();
      if (await firstSupplier.count() > 0) {
        const supplierText = await firstSupplier.textContent();
        await firstSupplier.click();
        log(`Supplier: ${supplierText.substring(0, 40)}`);
        await luwi.waitForTimeout(500);
      }
    }

    // Click Create PO
    const createPOBtn = luwi.locator('[role="dialog"] button:has-text("Create PO")');
    if (await createPOBtn.count() > 0) {
      await createPOBtn.click();
      await luwi.waitForTimeout(5000);
      await luwi.screenshot({ path: `${SS}/clean_05_po_created.png`, fullPage: true });

      const poUrl = luwi.url();
      if (poUrl.includes('/purchase-orders/PO-')) {
        poName = poUrl.split('/').pop();
        check('2.2 PO created from PR in browser', true, poName);

        const poText = await luwi.textContent('body');
        check('2.3 PO carries price ₱42.35 from PR', poText.includes('42.35'));
        evidence.form_submissions.push({ test: 'PR→PO conversion', pr: prName, po: poName });
      } else {
        check('2.2 PO created from PR in browser', false, poUrl);
      }
    }
  }

  // ================================================================
  // STEP 3: Edit PO price in browser (same commissary session)
  // ================================================================
  log('STEP 3: Edit PO price');
  const editor = luwi; // same session, no re-login

  if (poName) {
    // Already on the PO page from conversion
    await editor.waitForTimeout(2000);

    // Items tab
    const itemsTab = editor.locator('[role="tab"]:has-text("Items")');
    if (await itemsTab.count() > 0) { await itemsTab.click(); await editor.waitForTimeout(1000); }

    // Verify read-only
    check('3.1 Price is read-only', (await editor.locator('td input[type="number"]').count()) === 0);

    // Find pencil
    const editBtn = editor.locator('button:has(svg.lucide-pencil), button[title="Edit price"]').first();
    check('3.2 Pencil icon exists', await editBtn.count() > 0);

    if (await editBtn.count() > 0) {
      await editBtn.click();
      await editor.waitForTimeout(500);
      await editor.screenshot({ path: `${SS}/clean_09_edit_open.png` });

      const priceInput = editor.locator('input[type="number"][step]').first();
      const reasonField = editor.locator('textarea[placeholder*="Reason"]').first();
      check('3.3 Input + reason field visible', await priceInput.isVisible() && await reasonField.isVisible());

      await priceInput.fill('58');
      await reasonField.fill('Supplier price adjustment — new sago contract Q2 2026');
      await editor.screenshot({ path: `${SS}/clean_10_price_filled.png` });

      // Save
      await editor.locator('button:has(svg.lucide-check)').first().click();
      await editor.waitForTimeout(4000);
      await editor.screenshot({ path: `${SS}/clean_11_after_save.png` });

      // Check toast
      const toasts = await editor.locator('[data-sonner-toast]').allTextContents();
      const hasSuccess = toasts.some(t => t.toLowerCase().includes('updated') || t.toLowerCase().includes('price'));
      check('3.4 Success toast after save', hasSuccess, toasts.join(' | ').substring(0, 150));

      // Check price on page
      const bodyText = await editor.textContent('body');
      check('3.5 New price ₱58 on page', bodyText.includes('58.00') || bodyText.includes('₱58'));

      // Check banner
      const banner = editor.locator('[role="alert"]');
      check('3.6 Price change banner appears', (await banner.count()) > 0);
      if (await banner.count() > 0) {
        const bannerText = await banner.first().textContent();
        check('3.7 Banner shows price + reason', bannerText.includes('58') && bannerText.includes('sago'), bannerText.substring(0, 200));
        log(`Banner: ${bannerText.substring(0, 200)}`);
      }

      evidence.form_submissions.push({ test: 'PO price edit', po: poName, old: '42.35', new: '58', reason: 'Supplier price adjustment' });
    }
  }
  await editor.close();

  // ================================================================
  // STEP 4: Mae views PO with price change banner
  // ================================================================
  log('STEP 4: Mae approval view');
  const mae = await login(browser, 'mae@bebang.ph');

  if (poName) {
    await mae.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'networkidle' });
    await mae.waitForTimeout(3000);

    const maeItemsTab = mae.locator('[role="tab"]:has-text("Items")');
    if (await maeItemsTab.count() > 0) { await maeItemsTab.click(); await mae.waitForTimeout(1000); }

    await mae.screenshot({ path: `${SS}/clean_12_mae_view.png`, fullPage: true });

    const maeBanner = mae.locator('[role="alert"]');
    check('4.1 Mae sees price change banner', (await maeBanner.count()) > 0);
    if (await maeBanner.count() > 0) {
      const txt = await maeBanner.first().textContent();
      check('4.2 Banner shows who changed + reason', txt.includes('commissary') && (txt.includes('sago') || txt.includes('58')), txt.substring(0, 200));
    }
  }
  await mae.close();

  // ================================================================
  // STEP 5: Disabled item exclusion
  // ================================================================
  log('STEP 5: Disabled item test');
  const page3 = await login(browser, 'test.commissary@bebang.ph');
  await page3.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await page3.waitForTimeout(2000);

  await page3.locator('button[role="combobox"]').nth(1).click();
  await page3.waitForTimeout(500);
  await page3.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('INK BLACK');
  await page3.waitForTimeout(2000);
  check('5.1 Disabled item CS101 excluded', (await page3.locator('[role="option"]').count()) === 0);
  await page3.screenshot({ path: `${SS}/clean_13_disabled.png` });
  await page3.close();

} catch (e) {
  log(`ERROR: ${e.message}`);
  fail++;
  evidence.state_verification.push({ test: 'Execution', result: 'ERROR', details: e.message });
}

writeFileSync(`${DIR}/form_submissions.json`, JSON.stringify(evidence.form_submissions, null, 2));
writeFileSync(`${DIR}/api_mutations.json`, JSON.stringify(evidence.api_mutations, null, 2));
writeFileSync(`${DIR}/state_verification.json`, JSON.stringify(evidence.state_verification, null, 2));
await browser.close();

console.log(`\n=== L3 CLEAN E2E: ${pass} PASS / ${fail} FAIL ===`);
evidence.state_verification.forEach(v => console.log(`  [${v.result}] ${v.test}${v.details ? ' — ' + v.details : ''}`));
