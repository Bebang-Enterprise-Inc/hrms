/**
 * S167 Recon — Capture DOM selectors for PCF admin + add-entry forms
 * Login as sam, dump relevant page HTML/text snippets.
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = "https://my.bebang.ph";
const OUT = "F:/Dropbox/Projects/BEI-ERP/output/l3/s167";
const SHOTS = path.join(OUT, "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

const recon = {};

async function dumpPage(page, name) {
  await page.screenshot({ path: path.join(SHOTS, `recon_${name}.png`), fullPage: true });
  const html = await page.content();
  const snippet = html.length > 200000 ? html.slice(0, 200000) : html;
  fs.writeFileSync(path.join(OUT, `recon_${name}.html`), snippet);
  // Extract buttons / inputs / labels / headings
  const info = await page.evaluate(() => {
    const pick = (sel) => Array.from(document.querySelectorAll(sel)).slice(0, 40).map(el => ({
      tag: el.tagName,
      text: (el.innerText || el.value || "").slice(0, 120),
      id: el.id || null,
      name: el.getAttribute("name") || null,
      type: el.getAttribute("type") || null,
      placeholder: el.getAttribute("placeholder") || null,
      role: el.getAttribute("role") || null,
      dataTestId: el.getAttribute("data-testid") || null,
      ariaLabel: el.getAttribute("aria-label") || null,
    }));
    return {
      h1: pick("h1"),
      h2: pick("h2"),
      h3: pick("h3"),
      buttons: pick("button"),
      inputs: pick("input"),
      textareas: pick("textarea"),
      selects: pick("select"),
      comboboxes: pick("[role='combobox']"),
      dialogs: pick("[role='dialog']"),
      links: pick("a[href*='pcf']"),
      url: window.location.href,
      title: document.title,
    };
  });
  recon[name] = info;
  console.log(`  ${name}: ${info.buttons.length} buttons, ${info.inputs.length} inputs, url=${info.url}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  console.log("Logging in as sam@bebang.ph ...");
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(2000);
  if (!page.url().includes("/dashboard")) {
    await page.fill('input[type="email"], input[name="email"]', "sam@bebang.ph");
    await page.fill('input[type="password"], input[name="password"]', "2289454");
    await page.click('button[type="submit"]');
    try { await page.waitForURL("**/dashboard**", { timeout: 30000 }); } catch {}
  }
  console.log("After login:", page.url());

  console.log("\n-> /dashboard/accounting/pcf/admin");
  await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 30000 }).catch(e=>console.log("nav err",e.message));
  await page.waitForTimeout(3000);
  await dumpPage(page, "admin_list");

  // Try to open Create Department Fund dialog
  const createBtns = await page.locator("button").filter({ hasText: /create.*department.*fund|add.*department.*fund|new.*fund|create fund/i }).all();
  console.log(`  found ${createBtns.length} create-fund buttons`);
  if (createBtns.length > 0) {
    try {
      await createBtns[0].click();
      await page.waitForTimeout(1500);
      await dumpPage(page, "admin_create_dialog");
      // Close
      await page.keyboard.press("Escape");
      await page.waitForTimeout(500);
    } catch (e) { console.log("  dialog open failed:", e.message); }
  }

  console.log("\n-> /dashboard/store-ops/pcf");
  await page.goto(`${BASE}/dashboard/store-ops/pcf`, { waitUntil: "networkidle", timeout: 30000 }).catch(e=>console.log("nav err",e.message));
  await page.waitForTimeout(2500);
  await dumpPage(page, "store_pcf");

  console.log("\n-> /dashboard/store-ops/pcf/add");
  await page.goto(`${BASE}/dashboard/store-ops/pcf/add`, { waitUntil: "networkidle", timeout: 30000 }).catch(e=>console.log("nav err",e.message));
  await page.waitForTimeout(2500);
  await dumpPage(page, "store_pcf_add");

  console.log("\n-> /dashboard/accounting/pcf/review");
  await page.goto(`${BASE}/dashboard/accounting/pcf/review`, { waitUntil: "networkidle", timeout: 30000 }).catch(e=>console.log("nav err",e.message));
  await page.waitForTimeout(2500);
  await dumpPage(page, "review_queue");

  fs.writeFileSync(path.join(OUT, "recon_selectors.json"), JSON.stringify(recon, null, 2));
  console.log("\nRecon written to", path.join(OUT, "recon_selectors.json"));

  await browser.close();
})().catch(e => { console.error("FATAL", e); process.exit(1); });
