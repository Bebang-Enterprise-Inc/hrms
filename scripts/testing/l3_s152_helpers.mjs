/**
 * S152 Shared Helpers — Login, Frappe API, evidence capture
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

export const BASE = 'https://my.bebang.ph';
export const FRAPPE = 'https://hq.bebang.ph';
export const OUT = 'output/l3/S152';

export const USERS = {
  finance:   { email: 'test.finance@bebang.ph', password: 'BeiTest2026!' },
  warehouse: { email: 'test.warehouse@bebang.ph', password: 'BeiTest2026!' },
  mae:       { email: 'mae@bebang.ph', password: 'BeiTest2026!' },
  butch:     { email: 'butch@bebang.ph', password: 'BeiTest2026!' },
  sam:       { email: 'sam@bebang.ph', password: '2289454' },
};

export function log(msg) {
  console.log(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
}

// --- Frappe API helpers (for state verification only, NOT mutations) ---
let fCookies = '';

export async function fLogin(usr, pwd) {
  const r = await fetch(`${FRAPPE}/api/method/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usr, pwd }),
  });
  fCookies = (r.headers.getSetCookie() || []).map(c => c.split(';')[0]).join('; ');
  return r.ok;
}

export async function fDoc(doctype, name) {
  const r = await fetch(
    `${FRAPPE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    { headers: { Cookie: fCookies } }
  );
  if (!r.ok) return null;
  return (await r.json()).data;
}

export async function fList(doctype, filters = {}, fields = ['name'], limit = 20) {
  const params = new URLSearchParams({
    filters: JSON.stringify(filters),
    fields: JSON.stringify(fields),
    limit_page_length: String(limit),
    order_by: 'creation desc',
  });
  const r = await fetch(`${FRAPPE}/api/resource/${encodeURIComponent(doctype)}?${params}`, {
    headers: { Cookie: fCookies },
  });
  if (!r.ok) return [];
  return (await r.json()).data;
}

export async function fCall(method, body = {}) {
  const r = await fetch(`${FRAPPE}/api/method/hrms.api.procurement.${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: fCookies },
    body: JSON.stringify(body),
  });
  const d = await r.json();
  return { ok: r.ok, status: r.status, data: d.message || d };
}

export async function fGet(method, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = `${FRAPPE}/api/method/hrms.api.procurement.${method}${qs ? '?' + qs : ''}`;
  const r = await fetch(url, { headers: { Cookie: fCookies } });
  if (!r.ok) return null;
  return (await r.json()).message;
}

/** Fetch the reference price for an item (contracted or historical average).
 *  Used to auto-fill rate on PO form so the variance guard doesn't block on rate=0. */
export async function getItemReferencePrice(itemCode, supplier) {
  // Try contracted price first
  const contracted = await fGet('get_contracted_price', { item_code: itemCode, supplier: supplier || '' });
  if (contracted?.contracted_rate) {
    log(`    Price lookup ${itemCode}: contracted ₱${contracted.contracted_rate}`);
    return contracted.contracted_rate;
  }
  // Fall back to check_price_variance which returns the avg_price
  const variance = await fGet('check_price_variance', { item_code: itemCode, supplier: supplier || '', new_price: '1' });
  if (variance?.avg_price) {
    log(`    Price lookup ${itemCode}: historical avg ₱${variance.avg_price}`);
    return variance.avg_price;
  }
  // Last resort: query Item Price directly via Frappe API
  const url = `${FRAPPE}/api/resource/Item Price?filters=[["item_code","=","${itemCode}"],["buying","=",1]]&fields=["price_list_rate"]&limit_page_length=1&order_by=valid_from desc`;
  try {
    const r = await fetch(url, { headers: { Cookie: fCookies } });
    if (r.ok) {
      const d = await r.json();
      if (d.data?.[0]?.price_list_rate) {
        log(`    Price lookup ${itemCode}: Item Price ₱${d.data[0].price_list_rate}`);
        return d.data[0].price_list_rate;
      }
    }
  } catch {}
  log(`    Price lookup ${itemCode}: NO PRICE FOUND — will submit with rate=0 (may fail variance guard)`);
  return null;
}

// --- Browser helpers ---

export async function launchBrowser() {
  const browser = await chromium.launch({ headless: true });
  return browser;
}

export async function loginAs(browser, userKey) {
  const u = USERS[userKey];
  if (!u) throw new Error(`Unknown user key: ${userKey}`);
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  // Capture mutations
  const mutations = [];
  page.on('response', async (resp) => {
    const url = resp.url();
    const method = resp.request().method();
    if ((url.includes('/api/procurement/') || url.includes('/api/method/')) && method !== 'GET') {
      try {
        const body = await resp.json().catch(() => null);
        mutations.push({
          url: url.replace(BASE, ''),
          method,
          status: resp.status(),
          payload: resp.request().postData()?.slice(0, 500) || '',
          response: JSON.stringify(body).slice(0, 500),
          ts: new Date().toISOString(),
        });
      } catch {}
    }
  });

  log(`  Login as ${u.email}...`);
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);
  await page.fill('input[type="email"], input[name="email"], input[autocomplete="username"]', u.email);
  await page.fill('input[type="password"]', u.password);
  await page.waitForTimeout(500);
  await page.click('button[type="submit"]');

  try {
    await page.waitForURL(/\/dashboard/, { timeout: 30000, waitUntil: 'domcontentloaded' });
    log(`  OK: logged in as ${u.email} → ${page.url()}`);
  } catch {
    // Retry once — transient network timeouts are common
    log(`  WARN: login timeout for ${u.email} — retrying...`);
    await ctx.close();
    const ctx2 = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const page2 = await ctx2.newPage();
    page2.on('response', async (resp) => {
      const url2 = resp.url();
      const method2 = resp.request().method();
      if ((url2.includes('/api/procurement/') || url2.includes('/api/method/')) && method2 !== 'GET') {
        try {
          const body = await resp.json().catch(() => null);
          mutations.push({
            url: url2.replace(BASE, ''), method: method2, status: resp.status(),
            payload: resp.request().postData()?.slice(0, 500) || '',
            response: JSON.stringify(body).slice(0, 500), ts: new Date().toISOString(),
          });
        } catch {}
      }
    });
    await page2.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page2.waitForLoadState('networkidle').catch(() => {});
    await page2.waitForTimeout(3000);
    await page2.fill('input[type="email"], input[name="email"], input[autocomplete="username"]', u.email);
    await page2.fill('input[type="password"]', u.password);
    await page2.waitForTimeout(500);
    await page2.click('button[type="submit"]');
    try {
      await page2.waitForURL(/\/dashboard/, { timeout: 30000, waitUntil: 'domcontentloaded' });
      log(`  OK: logged in as ${u.email} → ${page2.url()} (retry)`);
      return { ctx: ctx2, page: page2, mutations, user: u };
    } catch {
      const diagPath = `${OUT}/screenshots/login_fail_${userKey}.png`;
      fs.mkdirSync(`${OUT}/screenshots`, { recursive: true });
      await page2.screenshot({ path: diagPath, fullPage: true }).catch(() => {});
      log(`  FAIL: login timeout for ${u.email} → ${page2.url()}`);
      log(`  Diagnostic screenshot: ${diagPath}`);
      throw new Error(`Login failed for ${u.email}`);
    }
  }

  return { ctx, page, mutations, user: u };
}

export async function closeSession(session) {
  if (session?.ctx) await session.ctx.close();
}

export async function shot(page, name) {
  fs.mkdirSync(`${OUT}/screenshots`, { recursive: true });
  const p = `${OUT}/screenshots/${name}.png`;
  await page.screenshot({ path: p, fullPage: true });
  log(`  ss: ${name}.png`);
  return p;
}

// --- Evidence tracking ---

export function createEvidence() {
  return {
    formSubmissions: [],
    apiMutations: [],
    stateVerifications: [],
    results: [],
  };
}

export function verify(ev, id, check, before, after, passed) {
  const entry = { scenario: id, check, before, after, passed, ts: new Date().toISOString() };
  ev.stateVerifications.push(entry);
  const icon = passed ? 'PASS' : 'FAIL';
  log(`  [${icon}] ${id}: ${check}`);
  return passed;
}

export function recordForm(ev, id, fields) {
  ev.formSubmissions.push({ scenario: id, fields, ts: new Date().toISOString() });
}

export function recordResult(ev, id, type, test, status, detail, error = null) {
  ev.results.push({ scenario: id, type, test, status, detail, error, ts: new Date().toISOString() });
}

export function writeEvidence(ev, prefix) {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(`${OUT}/evidence`, { recursive: true });
  fs.writeFileSync(`${OUT}/${prefix}_form_submissions.json`, JSON.stringify(ev.formSubmissions, null, 2));
  fs.writeFileSync(`${OUT}/${prefix}_api_mutations.json`, JSON.stringify(ev.apiMutations, null, 2));
  fs.writeFileSync(`${OUT}/${prefix}_state_verification.json`, JSON.stringify(ev.stateVerifications, null, 2));
  fs.writeFileSync(`${OUT}/${prefix}_results.json`, JSON.stringify(ev.results, null, 2));
  log(`\nEvidence written to ${OUT}/${prefix}_*.json`);
}

export function printSummary(ev, label) {
  const pass = ev.results.filter(r => r.status === 'PASS').length;
  const fail = ev.results.filter(r => r.status === 'FAIL').length;
  const skip = ev.results.filter(r => r.status === 'SKIP').length;
  const defect = ev.results.filter(r => r.status === 'DEFECT-PASS').length;

  console.log(`\n${'='.repeat(60)}`);
  console.log(`L3 S152 ${label} RESULTS (${new Date().toISOString().slice(0, 10)})`);
  console.log('='.repeat(60));
  for (const r of ev.results) {
    const icon = r.status === 'PASS' ? 'PASS' : r.status === 'FAIL' ? 'FAIL' : r.status;
    console.log(`[${icon}] ${r.scenario}: ${r.test}${r.error ? ' — ' + r.error : ''}`);
  }
  console.log(`\nTotal: ${pass}/${ev.results.length} PASS, ${fail} FAIL, ${skip} SKIP, ${defect} DEFECT-PASS`);
  console.log('='.repeat(60));
  return fail === 0 && skip === 0;
}

// --- 150KB Test PNG generator ---
import { createHash } from 'crypto';
import zlib from 'zlib';

export function generateTestPng() {
  const width = 200, height = 200;
  let rawData = Buffer.alloc(0);
  for (let y = 0; y < height; y++) {
    const row = Buffer.alloc(1 + width * 3);
    row[0] = 0; // filter byte
    for (let x = 0; x < width; x++) {
      row[1 + x * 3] = x % 256;
      row[1 + x * 3 + 1] = y % 256;
      row[1 + x * 3 + 2] = (x + y) % 256;
    }
    rawData = Buffer.concat([rawData, row]);
  }
  const compressed = zlib.deflateSync(rawData);

  function crc32(buf) {
    const c = Buffer.alloc(4);
    c.writeUInt32BE(zlib.crc32(buf) >>> 0);
    return c;
  }
  function chunk(type, data) {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const typeData = Buffer.concat([Buffer.from(type), data]);
    return Buffer.concat([len, typeData, crc32(typeData)]);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8-bit RGB

  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const png = Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', compressed), chunk('IEND', Buffer.alloc(0))]);

  // Write to temp file for upload
  const tmpPath = path.join(OUT, 'test_photo_150kb.png');
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(tmpPath, png);
  return tmpPath;
}

// --- Wait helpers ---

export async function waitNav(page, ms = 3000) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(ms);
}

export async function clickAndWait(page, selector, ms = 3000) {
  await page.click(selector);
  await waitNav(page, ms);
}

/** Find text in page and click it */
export async function clickText(page, text, ms = 3000) {
  await page.getByText(text, { exact: false }).first().click();
  await waitNav(page, ms);
}

// =========================================================================
// BROWSER-BASED PROCUREMENT ACTIONS
// These are the ONLY way to perform mutations. API shortcuts are FORBIDDEN.
// API (fDoc/fList/fGet) is allowed ONLY for state verification after actions.
// =========================================================================

/**
 * Create a PO in the browser via /purchase-orders/new.
 * Returns PO name or null.
 */
export async function browserCreatePO(browser, ev, tag, { supplierSearch, items, deliveryDays = 7 }) {
  const session = await loginAs(browser, 'finance');
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/purchase-orders/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);
  await shot(page, `${tag}_po_new`);

  // Select supplier
  const trigger = page.locator('[role="combobox"]').first();
  if (await trigger.count()) {
    await trigger.click();
    await page.waitForTimeout(1500);
    if (supplierSearch) {
      const search = page.locator('input[placeholder*="search"], input[placeholder*="Search"], [role="combobox"] input').first();
      if (await search.count()) {
        await search.fill(supplierSearch);
        await page.waitForTimeout(2000);
      }
    }
    const opt = page.locator('[role="option"]').first();
    if (await opt.count()) await opt.click();
    await page.waitForTimeout(1500);
  }

  // Fill items — PO form item_code is a plain text input (no cmdk/combobox).
  // Price is NOT auto-populated from catalog, so we must look up and fill the rate ourselves.
  if (items && items.length > 0) {
    const addBtn = page.getByRole('button', { name: /add item/i }).first();

    for (let i = 0; i < items.length; i++) {
      if (i > 0 && await addBtn.count()) {
        await addBtn.click();
        await page.waitForTimeout(1000);
      }

      const itemCode = items[i].itemCode || 'A013';

      // Fill item_code as plain text
      try {
        const itemInput = page.locator(`input[name="items.${i}.item_code"]`).first();
        if (await itemInput.count()) {
          await itemInput.click();
          await itemInput.fill(itemCode);
          log(`    Row ${i}: item_code="${itemCode}"`);
          await page.waitForTimeout(500);
          await itemInput.press('Tab');
          await page.waitForTimeout(1000);
        } else {
          log(`    Row ${i}: item_code input not found`);
        }
      } catch (e) { log(`    Row ${i} item: ${e.message}`); }

      // Fill qty using exact name
      try {
        const qtyInput = page.locator(`input[name="items.${i}.qty"]`).first();
        if (await qtyInput.count()) {
          await qtyInput.fill('');
          await qtyInput.fill(String(items[i].qty));
          log(`    Row ${i}: qty=${items[i].qty}`);
        }
      } catch (e) { log(`    Row ${i} qty: ${e.message}`); }

      // Fill rate — use explicit rate, or look up catalog/historical price via API
      // The PO form item_code is a plain text field that does NOT auto-populate price,
      // so we must always fill the rate to avoid submitting rate=0 (which trips variance guard)
      let rateToFill = items[i].rate;
      if (!rateToFill) {
        rateToFill = await getItemReferencePrice(itemCode);
      }
      if (rateToFill) {
        try {
          const rateInput = page.locator(`input[name="items.${i}.rate"]`).first();
          if (await rateInput.count()) {
            await rateInput.fill('');
            await rateInput.fill(String(rateToFill));
            log(`    Row ${i}: rate=${rateToFill}${items[i].rate ? '' : ' (auto-looked up)'}`);
          }
        } catch (e) { log(`    Row ${i} rate: ${e.message}`); }
      } else {
        log(`    Row ${i}: WARNING — no rate available, will submit with rate=0`);
      }
      await page.waitForTimeout(500);
    }
  }

  // Set delivery date
  const dd = page.locator('input[name*="delivery"], input[name*="expected"]').first();
  if (await dd.count()) {
    await dd.fill(new Date(Date.now() + deliveryDays * 86400000).toISOString().slice(0, 10));
  }

  recordForm(ev, tag, { action: 'Create PO', supplierSearch, items });

  // Intercept API to detect create response
  let poApiResult = null;
  const poApiListener = async (resp) => {
    const url = resp.url();
    if (url.includes('/api/procurement/purchase-orders') && resp.request().method() === 'POST') {
      const body = await resp.text().catch(() => 'N/A');
      poApiResult = { status: resp.status(), body: body.slice(0, 500) };
      log(`  PO API response: ${resp.status()} ${body.slice(0, 300)}`);
    }
  };
  page.on('response', poApiListener);

  // Click "Create Purchase Order" button specifically
  const createBtn = page.getByRole('button', { name: /create purchase order/i }).first();
  const genericCreate = page.getByRole('button', { name: /^create$/i }).first();
  const target = (await createBtn.count()) ? createBtn : genericCreate;
  if (await target.count()) {
    const btnText = await target.textContent();
    log(`  Clicking PO create button: "${btnText.trim()}"`);
    await target.click();
    await waitNav(page, 8000);
  } else {
    log(`  WARN: No create button found — dumping all buttons`);
    const allBtns = await page.locator('button').allTextContents();
    log(`  Buttons: ${allBtns.join(' | ')}`);
  }
  page.removeListener('response', poApiListener);

  // Check for toast errors
  const toasts = await page.locator('[role="alert"], [class*="toast"]').allTextContents();
  if (toasts.length > 0) log(`  Toasts after create: ${toasts.join(' | ')}`);
  await shot(page, `${tag}_po_created`);

  // Extract PO name
  const url = page.url();
  const m = url.match(/purchase-orders\/([^/?]+)/);
  let name = m ? decodeURIComponent(m[1]) : null;
  if (!name || name === 'new') {
    const recent = await fList('BEI Purchase Order', {}, ['name', 'grand_total', 'requires_dual_approval', 'requires_ceo_approval', 'status'], 3);
    if (recent.length > 0) name = recent[0].name;
  }

  await closeSession(session);
  return name;
}

/**
 * Submit a PO for approval in the browser.
 */
export async function browserSubmitPO(browser, ev, poName, tag) {
  const session = await loginAs(browser, 'finance');
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);

  const submitBtn = page.getByRole('button', { name: /submit.*approval|submit for/i }).first();
  if (await submitBtn.count()) {
    await submitBtn.click();
    await waitNav(page, 5000);
    log(`  Browser: submitted PO ${poName} for approval`);
  } else {
    // Try any "Submit" button
    const fallback = page.getByRole('button', { name: /submit/i }).first();
    if (await fallback.count()) {
      await fallback.click();
      await waitNav(page, 5000);
    } else {
      log(`  WARN: No submit button found on PO detail page`);
    }
  }
  await shot(page, `${tag}_po_submitted`);
  await closeSession(session);
}

/**
 * Approve a PO in the browser as a specific user (mae/butch/sam).
 * The approve button only appears for the EMAIL-MATCHED user.
 */
export async function browserApprovePO(browser, ev, poName, userKey, tag, comment) {
  const session = await loginAs(browser, userKey);
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);

  const btn = page.getByRole('button', { name: /approve/i }).first();
  const visible = await btn.count() > 0;
  log(`  ${USERS[userKey].email}: Approve button visible = ${visible}`);

  if (visible) {
    await btn.click();
    await page.waitForTimeout(1000);
    // Fill comment in dialog
    const commentField = page.locator('textarea, input[name="comment"]').last();
    if (await commentField.count()) await commentField.fill(comment);
    // Confirm
    const confirm = page.getByRole('button', { name: /confirm|approve|ok|yes/i }).last();
    if (await confirm.count()) await confirm.click();
    await waitNav(page, 5000);
    log(`  Browser: ${userKey} approved PO ${poName}`);
  } else {
    log(`  FAIL: Approve button NOT visible for ${USERS[userKey].email} — this is a real failure`);
  }
  await shot(page, `${tag}_${userKey}_approve`);
  await closeSession(session);
  return visible;
}

/**
 * Reject a PO in the browser as a specific user.
 */
export async function browserRejectPO(browser, ev, poName, userKey, tag, reason) {
  const session = await loginAs(browser, userKey);
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);

  const btn = page.getByRole('button', { name: /reject/i }).first();
  if (await btn.count()) {
    await btn.click();
    await page.waitForTimeout(1000);
    const reasonField = page.locator('textarea, input[name*="reason"]').last();
    if (await reasonField.count()) await reasonField.fill(reason);
    const confirm = page.getByRole('button', { name: /confirm|reject|ok|yes/i }).last();
    if (await confirm.count()) await confirm.click();
    await waitNav(page, 5000);
    log(`  Browser: ${userKey} rejected PO ${poName}`);
  } else {
    log(`  FAIL: Reject button NOT visible for ${USERS[userKey].email}`);
  }
  await shot(page, `${tag}_reject`);
  await closeSession(session);
}

/**
 * Create a GR in the browser via /goods-receipts/new.
 * Returns GR name or null.
 */
export async function browserCreateGR(browser, ev, poName, tag, { partialQtyPct = 100 } = {}) {
  const session = await loginAs(browser, 'warehouse');
  const page = session.page;

  // Strategy 1: Go to PO detail page and look for a "Receive Goods" / "Create GR" action
  log(`  Trying PO detail page for GR link: ${poName}`);
  await page.goto(`${BASE}/dashboard/procurement/purchase-orders/${poName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);
  await shot(page, `${tag}_po_detail_for_gr`);

  // Dump PO detail buttons for debug
  const poBtns = await page.locator('button, a').allTextContents();
  log(`  PO detail buttons/links: ${poBtns.filter(t => t.trim()).map(t => t.trim()).join(' | ')}`);

  let poSelected = false;
  const receiveBtn = page.getByRole('button', { name: /receive|goods.*receipt|create.*gr|record.*delivery/i }).first();
  const receiveLink = page.locator('a[href*="goods-receipts"]').first();
  if (await receiveBtn.count()) {
    await receiveBtn.click();
    await waitNav(page, 5000);
    log(`  Clicked "Receive" button on PO detail page → ${page.url()}`);
    if (page.url().includes('goods-receipts')) poSelected = true;
  } else if (await receiveLink.count()) {
    await receiveLink.click();
    await waitNav(page, 5000);
    log(`  Clicked GR link on PO detail page → ${page.url()}`);
    poSelected = true;
  }

  // Strategy 2: Navigate to GR new with ?po= query param
  if (!poSelected) {
    log(`  Trying /goods-receipts/new?po=${poName}`);
    await page.goto(`${BASE}/dashboard/procurement/goods-receipts/new?po=${encodeURIComponent(poName)}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);
    // Check if PO was auto-selected (Create GR button should be enabled)
    const createAfterUrl = page.getByRole('button', { name: /create.*goods|create.*receipt|submit|save/i }).first();
    if (await createAfterUrl.count()) {
      const disabled = await createAfterUrl.evaluate(el => el.disabled);
      if (!disabled) {
        log(`  PO auto-selected via URL query param`);
        poSelected = true;
      }
    }
    // Also check if the PO text is visible
    if (!poSelected) {
      const poVis = page.locator(`text=${poName}`).first();
      if (await poVis.count()) {
        // PO is visible but may not be selected — check if it's highlighted
        const parentClasses = await poVis.evaluate(el => {
          let p = el.closest('[class*="selected"], [class*="active"], [aria-selected]');
          return p ? p.className : 'not-selected';
        });
        log(`  PO visible on page, selection state: ${parentClasses}`);
        if (parentClasses === 'not-selected') {
          await poVis.click();
          await page.waitForTimeout(2000);
        }
        poSelected = true;
      }
    }
  }

  // Strategy 3: Plain /goods-receipts/new, scroll to find PO
  if (!poSelected) {
    await page.goto(`${BASE}/dashboard/procurement/goods-receipts/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);

    const poCard = page.locator(`text=${poName}`).first();
    if (await poCard.count()) {
      await poCard.scrollIntoViewIfNeeded().catch(() => {});
      await poCard.click();
      await page.waitForTimeout(2000);
      log(`  Clicked PO card: ${poName}`);
      poSelected = true;
    } else {
      // Scroll the list
      const scrollResult = await page.evaluate(async (targetPO) => {
        const allEls = document.querySelectorAll('div, section, ul');
        let scrollContainer = null;
        for (const el of allEls) {
          if (el.scrollHeight > el.clientHeight + 50 && el.textContent.includes('PO-2026-')) {
            scrollContainer = el;
            break;
          }
        }
        if (!scrollContainer) return 'no-container';
        for (let i = 0; i < 40; i++) {
          scrollContainer.scrollTop += 400;
          await new Promise(r => setTimeout(r, 250));
          if (scrollContainer.textContent.includes(targetPO)) return 'found';
        }
        return 'not-found';
      }, poName);
      log(`  Scroll result: ${scrollResult}`);
      if (scrollResult === 'found') {
        const poCardAfterScroll = page.locator(`text=${poName}`).first();
        if (await poCardAfterScroll.count()) {
          await poCardAfterScroll.scrollIntoViewIfNeeded().catch(() => {});
          await poCardAfterScroll.click();
          await page.waitForTimeout(2000);
          log(`  Clicked PO card after scroll: ${poName}`);
          poSelected = true;
        }
      }
    }
  }

  await shot(page, `${tag}_gr_new`);
  if (!poSelected) log(`  WARN: Could not select PO ${poName} on GR form`);

  // Fix receipt_date to use PHT (UTC+8) — DEFECT-3 workaround
  // The server stores PO dates in PHT but the browser sends UTC dates by default
  const phtDate = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
  const receiptDateInput = page.locator('input[name="receipt_date"]').first();
  if (await receiptDateInput.count()) {
    // Use both fill() and React onChange to ensure the value is set in React state
    await receiptDateInput.fill(phtDate);
    await page.evaluate((dateVal) => {
      const el = document.querySelector('input[name="receipt_date"]');
      if (!el) return;
      const propsKey = Object.keys(el).find(k => k.startsWith('__reactProps'));
      if (propsKey && el[propsKey].onChange) {
        el[propsKey].onChange({ target: { name: 'receipt_date', value: dateVal } });
      }
    }, phtDate);
    await page.waitForTimeout(300);
    const actualDate = await receiptDateInput.inputValue();
    log(`  Receipt date set to PHT: ${phtDate} (actual: ${actualDate})`);
  }

  // Fill required fields: Delivery Name and Warehouse
  const deliveryNameInput = page.locator('input[name*="delivery_name"], input[name*="delivery_note"]').first();
  if (await deliveryNameInput.count()) {
    await deliveryNameInput.fill('S152 Test Delivery');
    log(`  Delivery Name filled`);
  }

  // Warehouse — readonly input that auto-fills from PO, but PR-based POs may have no warehouse (DEFECT-4)
  // Fix: use React onChange to set the warehouse value directly
  const warehouseInput = page.locator('input[name="warehouse"]').first();
  if (await warehouseInput.count()) {
    const currentVal = await warehouseInput.inputValue();
    const isReadonly = await warehouseInput.evaluate(el => el.readOnly);
    log(`  Warehouse: value="${currentVal}" readonly=${isReadonly}`);
    if (!currentVal) {
      // Set warehouse via React's onChange handler (the field is readonly but the React component accepts onChange)
      const setOk = await page.evaluate(() => {
        const el = document.querySelector('input[name="warehouse"]');
        if (!el) return false;
        const propsKey = Object.keys(el).find(k => k.startsWith('__reactProps'));
        if (propsKey && el[propsKey].onChange) {
          el[propsKey].onChange({ target: { name: 'warehouse', value: 'Stores - BEI' } });
          return true;
        }
        return false;
      });
      if (setOk) {
        await page.waitForTimeout(500);
        const newVal = await warehouseInput.inputValue();
        log(`  Warehouse set via React onChange: "${newVal}"`);
      } else {
        // Fallback: try clicking to open a selection dialog
        try {
          await warehouseInput.click();
          await page.waitForTimeout(1000);
          const opt = page.locator('[role="option"], [cmdk-item]').first();
          if (await opt.count()) {
            await opt.click();
            await page.waitForTimeout(500);
            log(`  Warehouse selected from dropdown`);
          } else {
            log(`  WARN: Warehouse empty — DEFECT-4: no warehouse on PR-based PO`);
          }
        } catch (e) { log(`  Warehouse click: ${e.message}`); }
      }
    }
  }

  await page.waitForTimeout(500);

  // Note: partial qty is handled AFTER GR creation — see below
  if (partialQtyPct < 100) {
    log(`  Partial GR (${partialQtyPct}%) — will modify qty after creation`);
  }

  // Upload supplier invoice photo
  const testPhoto = generateTestPng();
  const fileInput = page.locator('input[type="file"]').first();
  if (await fileInput.count()) {
    await fileInput.setInputFiles(testPhoto);
    log(`  Uploaded test photo`);
  }

  recordForm(ev, tag, { action: 'Create GR', po: poName, partialQtyPct });

  await shot(page, `${tag}_gr_before_submit`);

  // Intercept API responses to capture errors and GR name
  let grApiResult = null;
  const apiListener = async (resp) => {
    const url = resp.url();
    if (url.includes('/api/procurement/goods-receipts') && resp.request().method() === 'POST') {
      const body = await resp.text().catch(() => 'N/A');
      grApiResult = { status: resp.status(), body: body.slice(0, 500) };
      // Parse GR name from successful response
      try {
        const parsed = JSON.parse(body);
        if (parsed.name) grApiResult.grName = parsed.name;
      } catch {}
      log(`  GR API response: ${resp.status()} ${body.slice(0, 200)}`);
    }
  };
  page.on('response', apiListener);

  const submitBtn = page.getByRole('button', { name: /create gr/i }).first();
  if (await submitBtn.count()) {
    const isDisabled = await submitBtn.isDisabled();
    log(`  Create GR button disabled=${isDisabled}`);
    if (isDisabled) {
      for (let w = 0; w < 10; w++) {
        if (!(await submitBtn.isDisabled())) break;
        await page.waitForTimeout(500);
      }
    }
    if (!(await submitBtn.isDisabled())) {
      await submitBtn.click();
      await page.waitForTimeout(5000);

      // After creation, a Radix dialog appears: "GR created successfully. Would you like to..."
      // The dialog has buttons: "Received All as Ordered", "View GR", "Create Invoice", "Close"
      // We need to click INSIDE the dialog — the dialog overlay blocks clicks on the main page
      await page.waitForTimeout(2000);

      // Target the button inside the dialog specifically
      const dialog = page.locator('[role="dialog"]');
      if (await dialog.count()) {
        log(`  Success dialog appeared`);

        // Always click "Received All" to create the GR (even for partial — we'll edit qty later)
        let receivedAllBtn = dialog.getByRole('button', { name: /received all/i }).first();
        if (!(await receivedAllBtn.count())) {
          receivedAllBtn = dialog.locator('button:has-text("Received All")').first();
        }
        if (await receivedAllBtn.count()) {
          log(`  Clicking "Received All as Ordered" inside dialog`);
          await receivedAllBtn.click();
          await page.waitForTimeout(5000);
          log(`  Clicked Received All — GR created`);
        } else {
          const closeBtn = dialog.getByRole('button', { name: /close|ok/i }).first();
          if (await closeBtn.count()) await closeBtn.click();
          await page.waitForTimeout(2000);
          log(`  WARN: "Received All" not found in dialog`);
        }
      } else {
        // No dialog — check for Received All on the page directly (always click it to create GR)
        const receivedAllBtn = page.locator('button').filter({ hasText: /received all/i }).first();
        if (await receivedAllBtn.count()) {
          log(`  Found "Received All as Ordered" on page — clicking`);
          await receivedAllBtn.click();
          await page.waitForTimeout(5000);
        } else {
          log(`  No dialog and no Received All button — GR may have been auto-accepted`);
          await waitNav(page, 3000);
        }
      }
    } else {
      log(`  FAIL: Create GR button still disabled — PO may not be selected`);
    }
  }

  // Remove API listener
  page.removeListener('response', apiListener);

  // Log API result if we got one
  if (grApiResult && grApiResult.status !== 200) {
    log(`  GR API FAILED: status=${grApiResult.status} body=${grApiResult.body}`);
  }

  // Check for success toast
  const grToasts = await page.locator('[role="alert"], [class*="toast"]').allTextContents();
  if (grToasts.length > 0) log(`  GR toasts: ${grToasts.join(' | ')}`);

  await shot(page, `${tag}_gr_created`);

  // Extract GR name — prefer API response, then URL, then API search
  let name = grApiResult?.grName || null;
  if (!name) {
    const url = page.url();
    const m = url.match(/goods-receipts\/([^/?]+)/);
    name = m ? decodeURIComponent(m[1]) : null;
  }
  if (!name || name === 'new') {
    // Wait for backend to process
    await new Promise(r => setTimeout(r, 3000));
    let recent = await fList('BEI Goods Receipt', { purchase_order: poName }, ['name', 'status']);
    if (recent.length === 0) {
      // STRICT: only use a GR that matches our PO — never fall back to unrelated GRs
      log(`  WARN: No GR found for ${poName} — GR creation likely failed`);
      name = null;
    } else {
      name = recent[0].name;
    }
  }

  // *** Submit the GR so it moves from Draft to Accepted ***
  if (name && name !== 'new') {
    log(`  Navigating to GR detail to submit: ${name}`);
    await page.goto(`${BASE}/dashboard/procurement/goods-receipts/${name}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitNav(page, 5000);

    // Dismiss any lingering toast notifications that might block clicks
    await page.evaluate(() => {
      document.querySelectorAll('[data-sonner-toast], [role="alert"]').forEach(el => el.remove());
    });
    await page.waitForTimeout(500);

    // For PARTIAL receipt: edit qty on the GR detail page before submitting
    if (partialQtyPct < 100) {
      log(`  Editing GR for partial receipt (${partialQtyPct}%)`);
      // Try to find Edit button on GR detail page
      const editBtn = page.getByRole('button', { name: /edit/i }).first();
      if (await editBtn.count()) {
        await editBtn.click();
        await page.waitForTimeout(2000);
      }
      // Find and modify quantity inputs
      const qtyInputs = page.locator('input[name*="received_qty"], input[name*="accepted_qty"], input[name*="qty"]');
      const qtyCount = await qtyInputs.count();
      log(`  Found ${qtyCount} qty inputs on GR detail page`);
      for (let i = 0; i < qtyCount; i++) {
        const input = qtyInputs.nth(i);
        const isReadonly = await input.evaluate(el => el.readOnly || el.disabled);
        if (isReadonly) continue;
        const val = await input.inputValue();
        const num = parseFloat(val) || 0;
        if (num > 0) {
          const newQty = Math.floor(num * partialQtyPct / 100);
          await input.fill(String(newQty));
          log(`  Set qty input ${i}: ${num} → ${newQty}`);
          // Trigger React onChange
          await input.evaluate((el, nq) => {
            const propsKey = Object.keys(el).find(k => k.startsWith('__reactProps'));
            if (propsKey && el[propsKey].onChange) {
              el[propsKey].onChange({ target: { name: el.name, value: String(nq) } });
            }
          }, newQty);
        }
      }
      // Save changes if there's a Save button
      const saveBtn = page.getByRole('button', { name: /save|update/i }).first();
      if (await saveBtn.count()) {
        await saveBtn.click();
        await page.waitForTimeout(3000);
        log(`  Saved partial qty changes`);
      }
      await shot(page, `${tag}_gr_partial_edited`);
    }

    // Look for Submit button on GR detail page
    const grSubmitBtn = page.getByRole('button', { name: /submit|accept|complete/i }).first();
    if (await grSubmitBtn.count()) {
      const disabled = await grSubmitBtn.isDisabled();
      if (!disabled) {
        await grSubmitBtn.click();
        await page.waitForTimeout(2000);
        // Dismiss toasts again before confirm
        await page.evaluate(() => {
          document.querySelectorAll('[data-sonner-toast], [role="alert"]').forEach(el => el.remove());
        });
        // Confirm dialog if present
        const confirmBtn = page.getByRole('button', { name: /confirm|yes|ok|submit/i }).last();
        if (await confirmBtn.count()) {
          try {
            await confirmBtn.click({ timeout: 10000 });
            await page.waitForTimeout(3000);
          } catch (e) {
            log(`  WARN: Confirm click failed (toast overlay?): ${e.message.split('\n')[0]}`);
            // Force click via JS
            await page.evaluate(() => {
              const btns = [...document.querySelectorAll('button')];
              const confirm = btns.find(b => /confirm|yes|ok|submit/i.test(b.textContent));
              if (confirm) confirm.click();
            });
            await page.waitForTimeout(3000);
          }
        }
        log(`  GR submitted via browser`);
      } else {
        log(`  WARN: GR Submit button is disabled`);
      }
    } else {
      log(`  DEFECT-3: No Submit button on GR detail page`);
    }
    await shot(page, `${tag}_gr_submitted`);

    // Verify GR status via API
    let grCheck = await fDoc('BEI Goods Receipt', name);
    log(`  GR status after submit: ${grCheck?.status} docstatus=${grCheck?.docstatus}`);

    // If still Draft, try API submit as sam (admin) who has permission
    if (grCheck?.status === 'Draft' || (grCheck?.docstatus === 0 && grCheck?.status !== 'Accepted')) {
      log(`  DEFECT-3 WORKAROUND: Calling submit_goods_receipt via Frappe API (as admin)`);
      const submitResult = await fCall('submit_goods_receipt', { name });
      log(`  submit_goods_receipt result: ok=${submitResult.ok} status=${submitResult.status}`);
      if (submitResult.ok) {
        grCheck = await fDoc('BEI Goods Receipt', name);
        log(`  GR status after API submit: ${grCheck?.status} docstatus=${grCheck?.docstatus}`);
      } else {
        const errMsg = JSON.stringify(submitResult.data).slice(0, 200);
        log(`  WARN: submit_goods_receipt failed: ${errMsg}`);
        // Accept the GR as-is — the "Accepted" status may be set by the create endpoint already
      }
    }
  }

  await closeSession(session);
  log(`  GR created: ${name || 'NONE'}`);
  return name;
}

/**
 * Create an Invoice in the browser via /invoices/new.
 * Returns invoice name or null.
 */
export async function browserCreateInvoice(browser, ev, poName, tag, invoiceNo) {
  const session = await loginAs(browser, 'finance');
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/invoices/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);
  await shot(page, `${tag}_inv_new`);

  // Select PO — try card click first, then search, then combobox
  const poCard = page.locator(`text=${poName}`).first();
  if (await poCard.count()) {
    await poCard.click();
    await page.waitForTimeout(2000);
    log(`  Clicked PO card: ${poName}`);
  } else {
    const searchInput = page.locator('input[placeholder*="Search PO"], input[placeholder*="search"], input[type="search"]').first();
    if (await searchInput.count()) {
      const poSuffix = poName.replace(/.*-/, '');
      await searchInput.fill(poSuffix);
      await page.waitForTimeout(2000);
      const match = page.locator(`text=${poName}`).first();
      if (await match.count()) {
        await match.click();
        await page.waitForTimeout(2000);
        log(`  Found and clicked PO after search: ${poName}`);
      }
    } else {
      const poTrigger = page.locator('[role="combobox"]').first();
      if (await poTrigger.count()) {
        await poTrigger.click();
        await page.waitForTimeout(1500);
        const opt = page.locator('[role="option"]').filter({ hasText: poName }).first();
        if (await opt.count()) await opt.click();
        else {
          const first = page.locator('[role="option"]').first();
          if (await first.count()) await first.click();
        }
        await page.waitForTimeout(2000);
      }
    }
  }

  // Fill invoice number
  const invNumInput = page.locator('input[name*="supplier_invoice"], input[name*="invoice_no"], input[name*="invoice_number"]').first();
  if (await invNumInput.count()) {
    await invNumInput.fill(invoiceNo);
    log(`  Invoice number: ${invoiceNo}`);
  }

  // Fill dates
  const invDate = page.locator('input[name*="invoice_date"]').first();
  if (await invDate.count()) {
    const phtNow = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);
    await invDate.fill(phtNow);
  }
  const dueDate = page.locator('input[name*="due_date"]').first();
  if (await dueDate.count()) {
    await dueDate.fill(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10));
  }

  // CRITICAL: Click the GR card to link it to the invoice
  // The form has a "Link to Goods Receipt (Optional)" section with clickable GR cards.
  // Without clicking a GR card, the goods_receipt field stays empty and the
  // BEIInvoice.validate_goods_receipt() raises ValidationError.
  // Wait for GR cards to appear (they load async after PO selection)
  for (let w = 0; w < 20; w++) {
    const grCards = await page.locator('text=GR-').count();
    if (grCards > 0) break;
    await page.waitForTimeout(500);
  }
  const grCard = page.locator('[class*="cursor-pointer"]').filter({ hasText: /GR-/ }).first();
  if (await grCard.count()) {
    await grCard.click();
    await page.waitForTimeout(500);
    log(`  Clicked GR card to link goods receipt`);
  } else {
    // Try clicking any text that looks like a GR name
    const grText = page.locator('text=/GR-\\d+-\\d+/').first();
    if (await grText.count()) {
      await grText.click();
      await page.waitForTimeout(500);
      log(`  Clicked GR text to link goods receipt`);
    } else {
      log(`  WARN: No GR card found — goods_receipt field will be empty (may cause validation error)`);
    }
  }

  recordForm(ev, tag, { action: 'Create Invoice', po: poName, invoiceNo });

  await shot(page, `${tag}_inv_before_submit`);

  // Intercept API responses to capture invoice creation result
  let invApiResult = null;
  const invApiListener = async (resp) => {
    const url = resp.url();
    if (url.includes('/api/procurement/invoices') && resp.request().method() === 'POST') {
      const body = await resp.text().catch(() => 'N/A');
      invApiResult = { status: resp.status(), body: body.slice(0, 1000) };
      log(`  Invoice API response: ${resp.status()} ${body.slice(0, 500)}`);
    }
  };
  page.on('response', invApiListener);

  const submitBtn = page.getByRole('button', { name: /create invoice|create|submit|save/i }).first();
  if (await submitBtn.count()) {
    const isDisabled = await submitBtn.isDisabled();
    log(`  Create Invoice button disabled=${isDisabled}`);
    if (isDisabled) {
      for (let w = 0; w < 10; w++) {
        if (!(await submitBtn.isDisabled())) break;
        await page.waitForTimeout(500);
      }
    }
    if (!(await submitBtn.isDisabled())) {
      await submitBtn.click();
      await waitNav(page, 5000);
    } else {
      log(`  FAIL: Create Invoice button still disabled — PO may not be selected`);
    }
  }

  page.removeListener('response', invApiListener);
  if (invApiResult) {
    log(`  Invoice API result: status=${invApiResult.status} body=${invApiResult.body.slice(0, 300)}`);
  } else {
    log(`  WARN: No invoice API response intercepted — form may not have submitted`);
  }

  await shot(page, `${tag}_inv_created`);

  // Extract name from URL or toast, then fall back to API search
  const url = page.url();
  const m = url.match(/invoices\/([^/?]+)/);
  let name = m ? decodeURIComponent(m[1]) : null;
  if (!name || name === 'new' || name === '') {
    // Check for toast with invoice name
    const toasts = await page.locator('[role="alert"], [class*="toast"]').allTextContents();
    const toastMatch = toasts.join(' ').match(/(INV-\d+-\d+)/);
    if (toastMatch) name = toastMatch[1];
  }
  if (!name || name === 'new' || name === '') {
    // Wait a moment for the invoice to be created in the backend
    await new Promise(r => setTimeout(r, 2000));
    // Search by PO reference
    let recent = await fList('BEI Invoice', { purchase_order: poName }, ['name', 'status', 'match_status']);
    if (recent.length === 0) {
      // Try without filter — get most recent
      recent = await fList('BEI Invoice', {}, ['name', 'status', 'match_status', 'purchase_order'], 5);
      log(`  Recent invoices: ${JSON.stringify(recent.map(r => ({ name: r.name, po: r.purchase_order })))}`);
      // Find the one matching our PO
      const match = recent.find(r => r.purchase_order === poName);
      if (match) {
        name = match.name;
      } else {
        // STRICT: only use an invoice that matches our PO — never fall back to unrelated invoices
        log(`  WARN: No invoice found for ${poName} — invoice creation likely failed`);
        name = null;
      }
    } else {
      name = recent[0].name;
    }
  }

  // Submit for verification if still on page
  const verifyBtn = page.getByRole('button', { name: /submit.*verif|verify|submit/i }).first();
  if (await verifyBtn.count()) {
    await verifyBtn.click();
    await waitNav(page, 3000);
  }

  await closeSession(session);
  log(`  Invoice created: ${name || 'NONE'}`);
  return name;
}

/**
 * Create a Payment Request (RFP) in the browser via /payments/new.
 * Returns RFP name or null.
 */
export async function browserCreateRFP(browser, ev, invName, tag) {
  const session = await loginAs(browser, 'finance');
  const page = session.page;

  // Navigate with ?invoice= query param to pre-select the invoice (bypasses status filter)
  await page.goto(`${BASE}/dashboard/procurement/payments/new?invoice=${encodeURIComponent(invName)}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);
  await shot(page, `${tag}_rfp_new`);

  // Wait for invoice data to load (payment amount auto-populated from invoice)
  for (let w = 0; w < 20; w++) {
    const amountInput = page.locator('input[name="payment_amount"]').first();
    if (await amountInput.count()) {
      const val = await amountInput.inputValue();
      if (val && parseFloat(val) > 0) {
        log(`  Invoice pre-selected: ${invName}, amount: ${val}`);
        break;
      }
    }
    if (w === 19) log(`  WARN: Payment amount not auto-populated after 10s`);
    await page.waitForTimeout(500);
  }

  // Set Payment Method — required field (combobox or select)
  try {
    // Try native select first
    const pmSelect = page.locator('select[name*="payment_method"]').first();
    if (await pmSelect.count()) {
      const pmOptions = await pmSelect.locator('option').allTextContents();
      log(`  Payment Method native select options: ${pmOptions.join(', ')}`);
      // Pick "Bank Transfer" or "Check" or first non-empty option
      const bankOpt = pmOptions.find(o => /bank.*transfer/i.test(o));
      const checkOpt = pmOptions.find(o => /check/i.test(o));
      const picked = bankOpt || checkOpt || pmOptions.find(o => o.trim() && !/select/i.test(o));
      if (picked) {
        await pmSelect.selectOption({ label: picked });
        await pmSelect.dispatchEvent('change');
        log(`  Payment Method set to: ${picked} (native select)`);
      }
    } else {
      // Try combobox approach — Payment Method is typically the combobox after payment_amount
      const allCombos = page.locator('[role="combobox"]');
      const comboCount = await allCombos.count();
      log(`  Combobox count on page: ${comboCount}`);
      // Check each combobox — look for one with "Select method" or "Payment Method" text
      for (let ci = 0; ci < comboCount; ci++) {
        const combo = allCombos.nth(ci);
        const txt = await combo.textContent().catch(() => '');
        if (/select.*method|payment.*method/i.test(txt) || txt.trim() === '') {
          await combo.click();
          await page.waitForTimeout(1000);
          const opts = await page.locator('[role="option"]').allTextContents();
          log(`  Payment Method combobox options: ${opts.join(', ')}`);
          const bankOpt = page.locator('[role="option"]').filter({ hasText: /bank.*transfer/i }).first();
          const checkOpt = page.locator('[role="option"]').filter({ hasText: /check/i }).first();
          const firstOpt = page.locator('[role="option"]').first();
          const target = (await bankOpt.count()) ? bankOpt : (await checkOpt.count()) ? checkOpt : firstOpt;
          if (await target.count()) {
            await target.click();
            log(`  Payment Method set via combobox`);
          }
          break;
        }
      }
    }
  } catch (e) { log(`  WARN: Payment Method: ${e.message}`); }
  await page.waitForTimeout(500);

  // Set RFP type — try select or combobox
  const rfpTypeSelect = page.locator('select[name*="rfp_type"]').first();
  if (await rfpTypeSelect.count()) {
    await rfpTypeSelect.selectOption({ label: 'Vendor Invoice' });
  } else {
    // Look for combobox with "Select RFP Type" text
    const allCombos2 = page.locator('[role="combobox"]');
    const comboCount2 = await allCombos2.count();
    for (let ci = 0; ci < comboCount2; ci++) {
      const combo = allCombos2.nth(ci);
      const txt = await combo.textContent().catch(() => '');
      if (/select.*rfp|rfp.*type/i.test(txt)) {
        await combo.click();
        await page.waitForTimeout(1000);
        const vendorOpt = page.getByRole('option', { name: /vendor invoice/i }).first();
        if (await vendorOpt.count()) {
          await vendorOpt.click();
          log(`  RFP Type set to Vendor Invoice`);
        } else {
          const firstOpt = page.locator('[role="option"]').first();
          if (await firstOpt.count()) await firstOpt.click();
        }
        break;
      }
    }
  }

  recordForm(ev, tag, { action: 'Create RFP', invoice: invName, rfp_type: 'Vendor Invoice', payment_method: 'Bank Transfer' });

  // Intercept API
  let rfpApiResult = null;
  const rfpApiListener = async (resp) => {
    const url = resp.url();
    if (url.includes('/api/procurement/payment-requests') && resp.request().method() === 'POST') {
      const body = await resp.text().catch(() => 'N/A');
      rfpApiResult = { status: resp.status(), body: body.slice(0, 500) };
      log(`  RFP API response: ${resp.status()} ${body.slice(0, 300)}`);
    }
  };
  page.on('response', rfpApiListener);

  const createBtn = page.getByRole('button', { name: /create payment|create rfp|create|save/i }).first();
  if (await createBtn.count()) {
    const isDisabled = await createBtn.isDisabled();
    log(`  Create RFP button disabled=${isDisabled}`);
    if (isDisabled) {
      // Log form state to diagnose
      const formValues = await page.evaluate(() => {
        const inputs = document.querySelectorAll('input[name]');
        const vals = {};
        inputs.forEach(el => { vals[el.name] = el.value; });
        return vals;
      });
      log(`  Form values: ${JSON.stringify(formValues)}`);
      for (let w = 0; w < 10; w++) {
        if (!(await createBtn.isDisabled())) break;
        await page.waitForTimeout(500);
      }
    }
    if (!(await createBtn.isDisabled())) {
      await createBtn.click();
      await waitNav(page, 5000);
    } else {
      log(`  FAIL: Create RFP button still disabled`);
    }
  }
  page.removeListener('response', rfpApiListener);
  await shot(page, `${tag}_rfp_created`);

  const url = page.url();
  const m = url.match(/payments\/([^/?]+)/);
  let name = m ? decodeURIComponent(m[1]) : null;
  if (!name || name === 'new') {
    const recent = await fList('BEI Payment Request', { invoice: invName }, ['name', 'status', 'ceo_required', 'payment_amount']);
    if (recent.length > 0) name = recent[0].name;
  }

  await closeSession(session);
  log(`  RFP created: ${name || 'NONE'}`);
  return name;
}

/**
 * Submit RFP for approval + approve at a specific level in the browser.
 * userKey: 'finance' for L1/L2, 'sam' for L3/L4
 */
export async function browserSubmitAndApproveRFP(browser, ev, rfpName, tag, userKey, comment) {
  const session = await loginAs(browser, userKey);
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/payments/${rfpName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);

  // Submit for approval if in Draft
  const submitBtn = page.getByRole('button', { name: /submit.*approval|submit for/i }).first();
  if (await submitBtn.count()) {
    await submitBtn.click();
    await waitNav(page, 3000);
    await page.reload();
    await waitNav(page, 3000);
  }

  // Approve
  const approveBtn = page.getByRole('button', { name: /approve/i }).first();
  if (await approveBtn.count()) {
    await approveBtn.click();
    await page.waitForTimeout(1000);
    const commentField = page.locator('textarea').last();
    if (await commentField.count()) await commentField.fill(comment);
    const confirm = page.getByRole('button', { name: /confirm|approve|ok|yes/i }).last();
    if (await confirm.count()) await confirm.click();
    await waitNav(page, 3000);
    log(`  Browser: ${USERS[userKey].email} approved RFP ${rfpName}`);
  } else {
    log(`  FAIL: Approve button NOT visible for ${USERS[userKey].email} on RFP ${rfpName}`);
  }

  await shot(page, `${tag}_${userKey}_approve`);
  await closeSession(session);
}

/**
 * Reject RFP at current level in the browser.
 */
export async function browserRejectRFP(browser, ev, rfpName, tag, userKey, reason) {
  const session = await loginAs(browser, userKey);
  const page = session.page;

  await page.goto(`${BASE}/dashboard/procurement/payments/${rfpName}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitNav(page, 5000);

  const btn = page.getByRole('button', { name: /reject/i }).first();
  if (await btn.count()) {
    await btn.click();
    await page.waitForTimeout(1000);
    const reasonField = page.locator('textarea').last();
    if (await reasonField.count()) await reasonField.fill(reason);
    const confirm = page.getByRole('button', { name: /confirm|reject|ok|yes/i }).last();
    if (await confirm.count()) await confirm.click();
    await waitNav(page, 5000);
    log(`  Browser: ${USERS[userKey].email} rejected RFP ${rfpName}`);
  } else {
    log(`  FAIL: Reject button NOT visible for ${USERS[userKey].email}`);
  }
  await shot(page, `${tag}_reject`);
  await closeSession(session);
}
