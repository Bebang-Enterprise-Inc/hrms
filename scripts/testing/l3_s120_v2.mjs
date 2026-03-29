import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const DIR = 'output/l3/s120';
const SS = `${DIR}/screenshots`;
mkdirSync(SS, { recursive: true });

const evidence = { form_submissions: [], api_mutations: [], state_verification: [] };
const log = (m) => console.log(`[${new Date().toISOString()}] ${m}`);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

page.on('response', async (r) => {
  if (r.url().includes('/api/procurement/') && r.request().method() !== 'GET') {
    const b = await r.json().catch(() => null);
    evidence.api_mutations.push({ ts: new Date().toISOString(), url: r.url().replace('https://my.bebang.ph', ''), method: r.request().method(), status: r.status(), body: b ? JSON.stringify(b).substring(0, 500) : null });
  }
});

try {
  // LOGIN
  log('LOGIN');
  await page.goto('https://my.bebang.ph/login', { waitUntil: 'networkidle' });
  await page.fill('input[name="email"]', 'test.commissary@bebang.ph');
  await page.fill('input[name="password"]', 'BeiTest2026!');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard**', { timeout: 30000, waitUntil: 'domcontentloaded' });
  log('Login OK');
  evidence.state_verification.push({ test: 'Login', result: 'PASS' });

  // PR FORM
  log('PR FORM');
  await page.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SS}/01_pr_form.png` });

  // ITEM SEARCH - combobox index 1 is the item search
  log('ITEM SEARCH');
  const itemCombobox = page.locator('button[role="combobox"]').nth(1);
  await itemCombobox.click();
  await page.waitForTimeout(500);

  // Type SAGO in the popover search input
  const searchInput = page.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first();
  await searchInput.fill('SAGO');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SS}/02_sago_search.png` });

  const results = page.locator('[role="option"]');
  const count = await results.count();
  log(`Search results: ${count}`);
  evidence.state_verification.push({ test: 'Item autocomplete SAGO', result: count > 0 ? 'PASS' : 'FAIL', details: `${count} results` });

  if (count > 0) {
    // Click first SAGO result
    for (let i = 0; i < count; i++) {
      const txt = await results.nth(i).textContent();
      if (txt.includes('FG009') || (txt.includes('SAGO') && !txt.includes('STRAW'))) {
        log(`Selecting: ${txt.substring(0, 60)}`);
        await results.nth(i).click();
        evidence.form_submissions.push({ test: 'Item selection', action: 'Selected from autocomplete', selected: txt.substring(0, 60) });
        break;
      }
    }
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SS}/03_item_selected.png` });

    // Check price auto-fill
    const rateVal = await page.locator('input[name="items.0.estimated_rate"]').inputValue();
    log(`Auto-filled rate: ${rateVal}`);
    evidence.state_verification.push({ test: 'Price auto-fill', result: parseFloat(rateVal) > 0 ? 'PASS' : 'FAIL', details: `rate=${rateVal}` });

    // Set qty
    await page.locator('input[name="items.0.qty"]').fill('2');

    // Select department
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await page.locator('button[role="combobox"]').first().click({ force: true });
    await page.waitForTimeout(500);
    const opsOption = page.locator('[role="option"]:has-text("Operations")').first();
    if (await opsOption.count() > 0) {
      await opsOption.click();
      log('Department: Operations');
    }
    await page.waitForTimeout(500);

    // Justification
    const textarea = page.locator('textarea').first();
    if (await textarea.count() > 0) {
      await textarea.fill('S120 L3 test - item autocomplete and price validation');
    }

    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SS}/04_form_filled.png`, fullPage: true });

    // SUBMIT PR
    log('SUBMIT PR');
    await page.locator('button[type="submit"], button:has-text("Create")').last().click({ force: true });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: `${SS}/05_after_submit.png` });
    const afterUrl = page.url();
    log(`After submit: ${afterUrl}`);
    const prCreated = afterUrl.includes('/purchase-requisitions/') && !afterUrl.includes('/new');
    evidence.state_verification.push({ test: 'PR creation', result: prCreated ? 'PASS' : 'FAIL', url: afterUrl });
    evidence.form_submissions.push({ test: 'PR submission', result: prCreated ? 'PASS' : 'FAIL', url: afterUrl });
  }

  // PO PRICE EDIT
  log('PO PRICE EDIT');
  await page.goto('https://my.bebang.ph/dashboard/procurement/purchase-orders', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  const poLink = page.locator('a[href*="/purchase-orders/PO-"]').first();
  if (await poLink.count() > 0) {
    await poLink.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${SS}/06_po_detail.png`, fullPage: true });
    log(`PO detail: ${page.url()}`);

    // Click Items tab
    const itemsTab = page.locator('[role="tab"]:has-text("Items")');
    if (await itemsTab.count() > 0) {
      await itemsTab.click();
      await page.waitForTimeout(1000);
    }

    // Check for pencil icon
    const editBtn = page.locator('button:has(svg.lucide-pencil), button[title="Edit price"]').first();
    const editExists = await editBtn.count() > 0;
    log(`Edit price button: ${editExists}`);
    evidence.state_verification.push({ test: 'PO price read-only with edit button', result: editExists ? 'PASS' : 'FAIL' });

    if (editExists) {
      await editBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${SS}/07_price_edit_open.png` });

      const priceInput = page.locator('input[type="number"]').first();
      const reasonField = page.locator('textarea[placeholder*="Reason"]').first();
      const priceVis = await priceInput.isVisible().catch(() => false);
      const reasonVis = await reasonField.isVisible().catch(() => false);
      log(`Price input: ${priceVis}, Reason field: ${reasonVis}`);
      evidence.state_verification.push({ test: 'Edit reveals input + reason', result: priceVis && reasonVis ? 'PASS' : 'FAIL' });

      if (priceVis && reasonVis) {
        await priceInput.fill('50');
        await reasonField.fill('S120 L3 - supplier rate increased');
        await page.screenshot({ path: `${SS}/08_price_filled.png` });

        const saveBtn = page.locator('button:has(svg.lucide-check)').first();
        if (await saveBtn.count() > 0) {
          await saveBtn.click();
          await page.waitForTimeout(3000);
          await page.screenshot({ path: `${SS}/09_price_saved.png` });
          evidence.form_submissions.push({ test: 'PO price edit', action: 'Changed to 50', result: 'SUBMITTED' });

          const banner = page.locator('[role="alert"]');
          const bannerVis = (await banner.count()) > 0;
          evidence.state_verification.push({ test: 'Price change banner', result: bannerVis ? 'PASS' : 'FAIL' });
          if (bannerVis) log(`Banner: ${(await banner.first().textContent()).substring(0, 150)}`);
        }
      }
    }
  }

  // DISABLED ITEM TEST
  log('DISABLED ITEM TEST');
  await page.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.locator('button[role="combobox"]').nth(1).click();
  await page.waitForTimeout(500);
  const si2 = page.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first();
  await si2.fill('INK BLACK');
  await page.waitForTimeout(2000);
  const r2 = await page.locator('[role="option"]').count();
  evidence.state_verification.push({ test: 'Disabled item excluded', result: r2 === 0 ? 'PASS' : 'FAIL', details: `${r2} results` });
  log(`INK BLACK: ${r2} results (expect 0)`);
  await page.screenshot({ path: `${SS}/10_disabled_search.png` });

} catch (e) {
  log(`ERROR: ${e.message}`);
  await page.screenshot({ path: `${SS}/error.png` }).catch(() => {});
  evidence.state_verification.push({ test: 'Execution', result: 'ERROR', details: e.message });
}

writeFileSync(`${DIR}/form_submissions.json`, JSON.stringify(evidence.form_submissions, null, 2));
writeFileSync(`${DIR}/api_mutations.json`, JSON.stringify(evidence.api_mutations, null, 2));
writeFileSync(`${DIR}/state_verification.json`, JSON.stringify(evidence.state_verification, null, 2));
await browser.close();

console.log('\n=== L3 SUMMARY ===');
const p = evidence.state_verification.filter(v => v.result === 'PASS').length;
const f = evidence.state_verification.filter(v => v.result === 'FAIL').length;
const e2 = evidence.state_verification.filter(v => v.result === 'ERROR').length;
console.log(`PASS: ${p} | FAIL: ${f} | ERROR: ${e2}`);
evidence.state_verification.forEach(v => console.log(`  [${v.result}] ${v.test}${v.details ? ' -- ' + v.details : ''}`));
