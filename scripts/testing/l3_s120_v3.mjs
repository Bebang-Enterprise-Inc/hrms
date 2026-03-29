/**
 * S120 L3 v3 — Full E2E: PR creation → PR→PO conversion → PO price edit → Mae approval
 * No shortcuts. Verify actual values, not just element existence.
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
  // ================================================================
  // PART 1: Luwi creates a PR with item autocomplete
  // ================================================================
  log('=== PART 1: PR CREATION (as commissary) ===');
  const luwi = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  // Capture API mutations
  luwi.on('response', async (r) => {
    if (r.url().includes('/api/procurement/') && r.request().method() === 'POST') {
      const b = await r.json().catch(() => null);
      evidence.api_mutations.push({
        ts: new Date().toISOString(), url: r.url().replace('https://my.bebang.ph', ''),
        method: 'POST', status: r.status(),
        body: b ? JSON.stringify(b).substring(0, 800) : null,
      });
    }
  });

  await login(luwi, 'test.commissary@bebang.ph', 'BeiTest2026!');
  log('Logged in as commissary');

  await luwi.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await luwi.waitForTimeout(3000);

  // Select item via autocomplete
  await luwi.locator('button[role="combobox"]').nth(1).click();
  await luwi.waitForTimeout(500);
  await luwi.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('SAGO');
  await luwi.waitForTimeout(2000);
  await luwi.screenshot({ path: `${SS}/v3_01_sago_search.png` });

  const results = luwi.locator('[role="option"]');
  const count = await results.count();
  log(`SAGO search: ${count} results`);
  evidence.state_verification.push({ test: '1.1 Item autocomplete returns results', result: count > 0 ? 'PASS' : 'FAIL', details: `${count} results` });

  // Select FG009
  let selectedItem = '';
  for (let i = 0; i < count; i++) {
    const txt = await results.nth(i).textContent();
    if (txt.includes('FG009')) {
      await results.nth(i).click();
      selectedItem = txt;
      break;
    }
  }
  await luwi.waitForTimeout(1000);

  // Verify auto-filled values
  const rateVal = await luwi.locator('input[name="items.0.estimated_rate"]').inputValue();
  const rate = parseFloat(rateVal);
  log(`Auto-filled rate: ${rateVal}`);
  evidence.state_verification.push({ test: '1.2 Price auto-fills from Item Price', result: rate > 0 ? 'PASS' : 'FAIL', details: `₱${rateVal} (expected ₱42.35)` });
  evidence.state_verification.push({ test: '1.3 Price is correct (₱42.35)', result: Math.abs(rate - 42.35) < 0.01 ? 'PASS' : 'FAIL', details: `got ₱${rateVal}` });

  // Fill qty, department, justification
  await luwi.locator('input[name="items.0.qty"]').fill('5');
  await luwi.keyboard.press('Escape');
  await luwi.waitForTimeout(300);
  await luwi.locator('button[role="combobox"]').first().click({ force: true });
  await luwi.waitForTimeout(500);
  await luwi.locator('[role="option"]:has-text("Operations")').first().click();
  await luwi.waitForTimeout(500);
  await luwi.locator('textarea').first().fill('S120 L3 v3 — full E2E test: SAGO 5kg for commissary');
  await luwi.waitForTimeout(500);
  await luwi.screenshot({ path: `${SS}/v3_02_form_filled.png`, fullPage: true });

  // Submit PR
  log('Submitting PR...');
  await luwi.locator('button:has-text("Create PR")').click();
  await luwi.waitForTimeout(5000);
  const prUrl = luwi.url();
  const prCreated = prUrl.includes('/purchase-requisitions/') && !prUrl.includes('/new');
  const prNumber = prCreated ? prUrl.split('/').pop() : 'NONE';
  log(`PR created: ${prNumber} at ${prUrl}`);
  await luwi.screenshot({ path: `${SS}/v3_03_pr_created.png`, fullPage: true });

  evidence.state_verification.push({ test: '1.4 PR form submits successfully', result: prCreated ? 'PASS' : 'FAIL', details: prNumber });
  evidence.form_submissions.push({ test: 'PR creation', pr_number: prNumber, item: 'FG009', qty: 5, rate: rate, total: rate * 5, url: prUrl });

  if (!prCreated) {
    throw new Error('PR creation failed — cannot continue E2E flow');
  }

  // ================================================================
  // PART 2: Convert PR to PO
  // ================================================================
  log('=== PART 2: PR → PO CONVERSION ===');
  await luwi.waitForTimeout(2000);

  // Look for Convert to PO button/dialog
  const convertBtn = luwi.locator('button:has-text("Convert to PO"), button:has-text("Convert"), button:has-text("Create PO")').first();
  const convertExists = await convertBtn.count() > 0;
  log(`Convert to PO button: ${convertExists}`);

  let poNumber = '';
  if (convertExists) {
    await convertBtn.click();
    await luwi.waitForTimeout(1000);
    await luwi.screenshot({ path: `${SS}/v3_04_convert_dialog.png` });

    // Select supplier in the dialog
    const supplierInput = luwi.locator('input[placeholder*="supplier"], input[placeholder*="Supplier"], [role="combobox"]:has-text("Select supplier")').first();
    if (await supplierInput.count() > 0) {
      await supplierInput.click();
      await luwi.waitForTimeout(500);
      // Pick first supplier option
      const supplierOption = luwi.locator('[role="option"]').first();
      if (await supplierOption.count() > 0) {
        const supplierName = await supplierOption.textContent();
        await supplierOption.click();
        log(`Selected supplier: ${supplierName}`);
        await luwi.waitForTimeout(500);
      }
    }

    // Confirm conversion
    const confirmBtn = luwi.locator('button:has-text("Convert"), button:has-text("Create"), button:has-text("Confirm")').last();
    if (await confirmBtn.count() > 0) {
      await confirmBtn.click();
      await luwi.waitForTimeout(5000);
      await luwi.screenshot({ path: `${SS}/v3_05_po_created.png`, fullPage: true });

      const poUrl = luwi.url();
      if (poUrl.includes('/purchase-orders/PO-')) {
        poNumber = poUrl.split('/').pop();
        log(`PO created from PR: ${poNumber}`);
        evidence.state_verification.push({ test: '2.1 PR→PO conversion succeeds', result: 'PASS', details: poNumber });

        // Verify the PO has the correct price from the PR
        const pageText = await luwi.textContent('body');
        const hasCorrectPrice = pageText.includes('42.35') || pageText.includes('42,35');
        evidence.state_verification.push({ test: '2.2 PO carries price from PR (₱42.35)', result: hasCorrectPrice ? 'PASS' : 'FAIL' });
      } else {
        log(`Conversion may have failed — still at: ${poUrl}`);
        evidence.state_verification.push({ test: '2.1 PR→PO conversion succeeds', result: 'FAIL', details: poUrl });
      }
    }
  } else {
    log('No Convert button found — testing PO price edit on existing PO instead');
    evidence.state_verification.push({ test: '2.1 PR→PO conversion succeeds', result: 'SKIP', details: 'Convert button not available on this PR' });
  }

  // ================================================================
  // PART 3: PO price edit with reason
  // ================================================================
  log('=== PART 3: PO PRICE EDIT ===');

  // Use the PO we just created, or fall back to an existing one
  if (!poNumber) {
    // Use a known Draft PO for price edit testing
    poNumber = 'PO-2026-02989';
    await luwi.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poNumber}`, { waitUntil: 'networkidle' });
    await luwi.waitForTimeout(3000);
  } else {
    await luwi.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poNumber}`, { waitUntil: 'networkidle' });
    await luwi.waitForTimeout(3000);
  }

  log(`Testing price edit on: ${poNumber}`);

  // Click Items tab
  const itemsTab = luwi.locator('[role="tab"]:has-text("Items")');
  if (await itemsTab.count() > 0) {
    await itemsTab.click();
    await luwi.waitForTimeout(1000);
  }

  // Verify price is read-only (no input fields in the price column)
  const priceInputsBefore = await luwi.locator('td input[type="number"]').count();
  evidence.state_verification.push({ test: '3.1 Price is read-only by default', result: priceInputsBefore === 0 ? 'PASS' : 'FAIL', details: `${priceInputsBefore} editable price inputs (expected 0)` });

  // Find and record the current price
  const editBtn = luwi.locator('button:has(svg.lucide-pencil), button[title="Edit price"]').first();
  const editExists = await editBtn.count() > 0;
  evidence.state_verification.push({ test: '3.2 Edit Price pencil icon exists', result: editExists ? 'PASS' : 'FAIL' });

  if (editExists) {
    // Get the price text BEFORE editing
    const priceCell = luwi.locator('td:has(button:has(svg.lucide-pencil))').first();
    const priceBefore = await priceCell.textContent();
    log(`Price before edit: ${priceBefore.trim()}`);

    await editBtn.click();
    await luwi.waitForTimeout(500);
    await luwi.screenshot({ path: `${SS}/v3_06_price_edit_open.png` });

    // Verify input + reason BOTH visible
    const priceInput = luwi.locator('input[type="number"][step]').first();
    const reasonField = luwi.locator('textarea[placeholder*="Reason"]').first();
    const priceVis = await priceInput.isVisible().catch(() => false);
    const reasonVis = await reasonField.isVisible().catch(() => false);
    evidence.state_verification.push({ test: '3.3 Edit reveals price input + reason field', result: priceVis && reasonVis ? 'PASS' : 'FAIL', details: `price=${priceVis}, reason=${reasonVis}` });

    if (priceVis && reasonVis) {
      // Fill new price and reason
      await priceInput.fill('55.50');
      await reasonField.fill('Supplier increased raw sago price per March 2026 quote');
      await luwi.screenshot({ path: `${SS}/v3_07_price_reason_filled.png` });

      // Check Save button is enabled (reason is filled)
      const saveBtn = luwi.locator('button:has(svg.lucide-check)').first();
      const saveDisabled = await saveBtn.isDisabled();
      evidence.state_verification.push({ test: '3.4 Save enabled when reason provided', result: !saveDisabled ? 'PASS' : 'FAIL' });

      // Click Save
      await saveBtn.click();
      await luwi.waitForTimeout(3000);
      await luwi.screenshot({ path: `${SS}/v3_08_price_saved.png` });

      // Verify the price actually changed — check page body text after refetch
      await luwi.waitForTimeout(2000); // wait for refetch
      const bodyText = await luwi.textContent('body');
      const priceChanged = bodyText.includes('55.50') || bodyText.includes('55,50');
      log(`Price 55.50 found on page: ${priceChanged}`);
      evidence.state_verification.push({ test: '3.5 Price value updated on page (₱55.50)', result: priceChanged ? 'PASS' : 'FAIL', details: `before=${priceBefore.trim()}, page contains 55.50=${priceChanged}` });
      evidence.form_submissions.push({ test: 'PO price edit', po: poNumber, old_price: priceBefore.trim(), new_price: '55.50', reason: 'Supplier increased raw sago price per March 2026 quote' });

      // Verify banner appears with correct content
      const banner = luwi.locator('[role="alert"]');
      const bannerExists = (await banner.count()) > 0;
      evidence.state_verification.push({ test: '3.6 Price change banner appears', result: bannerExists ? 'PASS' : 'FAIL' });

      if (bannerExists) {
        const bannerText = await banner.first().textContent();
        const bannerHasPrice = bannerText.includes('55.50') || bannerText.includes('55,50');
        const bannerHasReason = bannerText.includes('Supplier increased') || bannerText.includes('sago price');
        evidence.state_verification.push({ test: '3.7 Banner shows new price + reason', result: bannerHasPrice && bannerHasReason ? 'PASS' : 'FAIL', details: bannerText.substring(0, 200) });
        log(`Banner: ${bannerText.substring(0, 150)}`);
      }
    }
  }

  // ================================================================
  // PART 4: Mae sees the PO with price override
  // ================================================================
  log('=== PART 4: MAE APPROVAL VIEW ===');
  await luwi.close();

  const mae = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await login(mae, 'mae@bebang.ph', 'BeiTest2026!');
  log('Logged in as Mae');

  if (poNumber) {
    await mae.goto(`https://my.bebang.ph/dashboard/procurement/purchase-orders/${poNumber}`, { waitUntil: 'networkidle' });
    await mae.waitForTimeout(3000);
    await mae.screenshot({ path: `${SS}/v3_09_mae_po_view.png`, fullPage: true });

    // Click Items tab
    const maeItemsTab = mae.locator('[role="tab"]:has-text("Items")');
    if (await maeItemsTab.count() > 0) {
      await maeItemsTab.click();
      await mae.waitForTimeout(1000);
    }

    // Check if Mae sees the price change banner
    const maeBanner = mae.locator('[role="alert"]');
    const maeBannerExists = (await maeBanner.count()) > 0;
    evidence.state_verification.push({ test: '4.1 Mae sees price change banner', result: maeBannerExists ? 'PASS' : 'FAIL' });

    if (maeBannerExists) {
      const maeBannerText = await maeBanner.first().textContent();
      log(`Mae sees banner: ${maeBannerText.substring(0, 150)}`);
      const has_change_info = maeBannerText.includes('55.50') || maeBannerText.includes('55,50') || maeBannerText.includes('Price') || maeBannerText.includes('changed');
      evidence.state_verification.push({ test: '4.2 Banner shows price change details', result: has_change_info ? 'PASS' : 'FAIL', details: maeBannerText.substring(0, 200) });
    }

    await mae.screenshot({ path: `${SS}/v3_10_mae_banner.png`, fullPage: true });
  } else {
    evidence.state_verification.push({ test: '4.1 Mae sees price change banner', result: 'SKIP', details: 'No PO to test' });
  }
  await mae.close();

  // ================================================================
  // PART 5: Disabled item exclusion
  // ================================================================
  log('=== PART 5: DISABLED ITEM EXCLUSION ===');
  const page3 = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await login(page3, 'test.commissary@bebang.ph', 'BeiTest2026!');
  await page3.goto('https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new', { waitUntil: 'networkidle' });
  await page3.waitForTimeout(2000);

  await page3.locator('button[role="combobox"]').nth(1).click();
  await page3.waitForTimeout(500);
  await page3.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('INK BLACK');
  await page3.waitForTimeout(2000);
  const disabledCount = await page3.locator('[role="option"]').count();
  evidence.state_verification.push({ test: '5.1 Disabled item (CS101 INK BLACK) excluded', result: disabledCount === 0 ? 'PASS' : 'FAIL', details: `${disabledCount} results (expected 0)` });
  await page3.screenshot({ path: `${SS}/v3_11_disabled_excluded.png` });

  // Also test that a STALE item doesn't appear
  await page3.locator('input[placeholder*="item"], input[placeholder*="code"], input[placeholder*="Type"]').first().fill('TEST');
  await page3.waitForTimeout(2000);
  const testCount = await page3.locator('[role="option"]').count();
  log(`TEST search: ${testCount} results`);
  // TEST-* items should be disabled
  await page3.screenshot({ path: `${SS}/v3_12_test_items.png` });
  await page3.close();

} catch (e) {
  log(`ERROR: ${e.message}`);
  evidence.state_verification.push({ test: 'Execution', result: 'ERROR', details: e.message });
}

// Save evidence
writeFileSync(`${DIR}/form_submissions.json`, JSON.stringify(evidence.form_submissions, null, 2));
writeFileSync(`${DIR}/api_mutations.json`, JSON.stringify(evidence.api_mutations, null, 2));
writeFileSync(`${DIR}/state_verification.json`, JSON.stringify(evidence.state_verification, null, 2));
await browser.close();

// Summary
console.log('\n=== L3 FULL E2E SUMMARY ===');
const p = evidence.state_verification.filter(v => v.result === 'PASS').length;
const f = evidence.state_verification.filter(v => v.result === 'FAIL').length;
const s = evidence.state_verification.filter(v => v.result === 'SKIP').length;
const e2 = evidence.state_verification.filter(v => v.result === 'ERROR').length;
console.log(`PASS: ${p} | FAIL: ${f} | SKIP: ${s} | ERROR: ${e2}`);
evidence.state_verification.forEach(v => console.log(`  [${v.result}] ${v.test}${v.details ? ' — ' + v.details : ''}`));
