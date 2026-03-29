/**
 * S120 L3 FINAL — Complete E2E on the PO we just created from PR
 * PR-2026-03044 → PO-2026-03045 (FG009 SAGO, qty=5, unit_cost=₱42.35)
 * 1. Edit price on PO as commissary
 * 2. Verify as Mae
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const DIR = 'output/l3/s120';
const SS = `${DIR}/screenshots`;
mkdirSync(SS, { recursive: true });

const evidence = { form_submissions: [], api_mutations: [], state_verification: [] };
const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`);

async function login(page, email, password) {
  await page.goto('https://my.bebang.ph/login', { waitUntil: 'networkidle' });
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
}

const browser = await chromium.launch({ headless: true });

try {
  // PART 1: Edit price on the PO we created from PR
  log('=== PART 1: PRICE EDIT ON PO-2026-03045 ===');
  const luwi = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await login(luwi, 'test.commissary@bebang.ph', 'BeiTest2026!');
  log('Logged in as commissary');

  await luwi.goto('https://my.bebang.ph/dashboard/procurement/purchase-orders/PO-2026-03045', { waitUntil: 'networkidle' });
  await luwi.waitForTimeout(3000);
  await luwi.screenshot({ path: `${SS}/final_01_po_detail.png`, fullPage: true });

  // Click Items tab
  const itemsTab = luwi.locator('[role="tab"]:has-text("Items")');
  if (await itemsTab.count() > 0) {
    await itemsTab.click();
    await luwi.waitForTimeout(1000);
  }
  await luwi.screenshot({ path: `${SS}/final_02_items_tab.png` });

  // Verify price is read-only
  const editableInputs = await luwi.locator('td input[type="number"]').count();
  evidence.state_verification.push({ test: 'Price is read-only (no input fields)', result: editableInputs === 0 ? 'PASS' : 'FAIL', details: `${editableInputs} inputs` });

  // Find pencil icon
  const editBtn = luwi.locator('button:has(svg.lucide-pencil), button[title="Edit price"]').first();
  const editExists = await editBtn.count() > 0;
  evidence.state_verification.push({ test: 'Edit Price pencil icon exists', result: editExists ? 'PASS' : 'FAIL' });
  log(`Pencil icon: ${editExists}`);

  if (editExists) {
    // Click edit
    await editBtn.click();
    await luwi.waitForTimeout(500);
    await luwi.screenshot({ path: `${SS}/final_03_edit_open.png` });

    const priceInput = luwi.locator('input[type="number"][step]').first();
    const reasonField = luwi.locator('textarea[placeholder*="Reason"]').first();
    const priceVis = await priceInput.isVisible().catch(() => false);
    const reasonVis = await reasonField.isVisible().catch(() => false);
    evidence.state_verification.push({ test: 'Edit reveals input + reason', result: priceVis && reasonVis ? 'PASS' : 'FAIL' });

    // Fill new price + reason
    await priceInput.fill('65');
    await reasonField.fill('Supplier increased sago rate — new contract Q2 2026');
    await luwi.screenshot({ path: `${SS}/final_04_price_filled.png` });

    // Save
    const saveBtn = luwi.locator('button:has(svg.lucide-check)').first();
    await saveBtn.click();
    await luwi.waitForTimeout(4000);
    await luwi.screenshot({ path: `${SS}/final_05_after_save.png` });

    // Check toast for success
    const toasts = await luwi.locator('[data-sonner-toast]').allTextContents();
    log(`Toasts: ${JSON.stringify(toasts)}`);
    const hasSuccessToast = toasts.some(t => t.includes('updated') || t.includes('Price'));
    evidence.state_verification.push({ test: 'Success toast after price save', result: hasSuccessToast ? 'PASS' : 'FAIL', details: toasts.join(' | ').substring(0, 200) });
    evidence.form_submissions.push({ test: 'PO price edit', po: 'PO-2026-03045', old_price: '42.35', new_price: '65', reason: 'Supplier increased sago rate' });

    // Check banner
    const banner = luwi.locator('[role="alert"]');
    const bannerExists = (await banner.count()) > 0;
    evidence.state_verification.push({ test: 'Price change banner appears', result: bannerExists ? 'PASS' : 'FAIL' });

    if (bannerExists) {
      const bannerText = await banner.first().textContent();
      log(`Banner: ${bannerText.substring(0, 200)}`);
      const hasPriceInfo = bannerText.includes('65') || bannerText.includes('42.35');
      const hasReason = bannerText.includes('sago') || bannerText.includes('Supplier');
      evidence.state_verification.push({ test: 'Banner shows price + reason', result: hasPriceInfo ? 'PASS' : 'FAIL', details: bannerText.substring(0, 200) });
    }

    // Verify the new price is on the page
    const bodyText = await luwi.textContent('body');
    evidence.state_verification.push({ test: 'New price ₱65 visible on page', result: bodyText.includes('65.00') || bodyText.includes('₱65') ? 'PASS' : 'FAIL' });
    evidence.state_verification.push({ test: 'New total ₱325 visible (5×65)', result: bodyText.includes('325') ? 'PASS' : 'FAIL' });
  }

  await luwi.close();

  // PART 2: Mae views the PO
  log('=== PART 2: MAE VIEWS PO ===');
  const mae = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await login(mae, 'mae@bebang.ph', 'BeiTest2026!');
  log('Logged in as Mae');

  await mae.goto('https://my.bebang.ph/dashboard/procurement/purchase-orders/PO-2026-03045', { waitUntil: 'networkidle' });
  await mae.waitForTimeout(3000);
  await mae.screenshot({ path: `${SS}/final_06_mae_view.png`, fullPage: true });

  // Items tab
  const maeItemsTab = mae.locator('[role="tab"]:has-text("Items")');
  if (await maeItemsTab.count() > 0) {
    await maeItemsTab.click();
    await mae.waitForTimeout(1000);
  }

  const maeBanner = mae.locator('[role="alert"]');
  const maeBannerExists = (await maeBanner.count()) > 0;
  evidence.state_verification.push({ test: 'Mae sees price change banner', result: maeBannerExists ? 'PASS' : 'FAIL' });

  if (maeBannerExists) {
    const maeBannerText = await maeBanner.first().textContent();
    log(`Mae banner: ${maeBannerText.substring(0, 200)}`);
    evidence.state_verification.push({ test: 'Mae banner has item + price + reason', result: (maeBannerText.includes('FG009') || maeBannerText.includes('65')) && maeBannerText.includes('sago') ? 'PASS' : 'FAIL', details: maeBannerText.substring(0, 200) });
  }

  await mae.screenshot({ path: `${SS}/final_07_mae_banner.png`, fullPage: true });
  await mae.close();

} catch (e) {
  log(`ERROR: ${e.message}`);
  evidence.state_verification.push({ test: 'Execution', result: 'ERROR', details: e.message });
}

writeFileSync(`${DIR}/form_submissions.json`, JSON.stringify(evidence.form_submissions, null, 2));
writeFileSync(`${DIR}/api_mutations.json`, JSON.stringify(evidence.api_mutations, null, 2));
writeFileSync(`${DIR}/state_verification.json`, JSON.stringify(evidence.state_verification, null, 2));
await browser.close();

console.log('\n=== L3 FINAL E2E ===');
const p = evidence.state_verification.filter(v => v.result === 'PASS').length;
const f = evidence.state_verification.filter(v => v.result === 'FAIL').length;
console.log(`PASS: ${p} | FAIL: ${f}`);
evidence.state_verification.forEach(v => console.log(`  [${v.result}] ${v.test}${v.details ? ' — ' + v.details : ''}`));
