/**
 * Selector discovery for S125 L3 re-run.
 * Find the REAL selectors for: Needs Attention toggle, banner, store name display.
 */
import { chromium } from "playwright";
import fs from "fs";

const BASE = "https://my.bebang.ph";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();

  // Login
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 60000 });
  await page.locator('input[autocomplete="username"], input[name="email"]').first().fill("test.crew1@bebang.ph");
  await page.locator('input[type="password"]').first().fill("BeiTest2026!");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(8000);

  await page.goto(`${BASE}/dashboard/store-ops/inventory`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(5000);

  // Screenshot full page
  await page.screenshot({ path: "output/l3/S125/screenshots/discover_full.png", fullPage: true });

  // Get ALL buttons and toggle-like elements
  const buttons = await page.locator("button").allTextContents();
  console.log("=== BUTTONS ===");
  buttons.forEach((b, i) => { if (b.trim()) console.log(`  [${i}] "${b.trim().substring(0, 80)}"`) });

  // Get ALL tab/toggle elements
  const tabs = await page.locator('[role="tab"], [role="tablist"] *, [data-state]').allTextContents();
  console.log("\n=== TABS/TOGGLES ===");
  tabs.forEach((t, i) => { if (t.trim()) console.log(`  [${i}] "${t.trim().substring(0, 80)}"`) });

  // Get ALL elements containing "Needs" or "Attention" or "All Items"
  const needsEls = await page.locator('text=/needs|attention|all items|all stock/i').allTextContents();
  console.log("\n=== NEEDS ATTENTION / ALL ITEMS ===");
  needsEls.forEach((n, i) => console.log(`  [${i}] "${n.trim().substring(0, 100)}"`));

  // Get ALL elements containing "Next delivery" or "Order window" or "Place Order"
  const bannerEls = await page.locator('text=/next delivery|order window|place order|cutoff/i').allTextContents();
  console.log("\n=== BANNER ELEMENTS ===");
  bannerEls.forEach((b, i) => console.log(`  [${i}] "${b.trim().substring(0, 100)}"`));

  // Get ALL elements with rounded-lg border classes (banner candidates)
  const roundedEls = await page.locator('.rounded-lg').allTextContents();
  console.log("\n=== ROUNDED-LG ELEMENTS (banner candidates) ===");
  roundedEls.forEach((r, i) => { if (r.trim().length > 5 && r.trim().length < 200) console.log(`  [${i}] "${r.trim().substring(0, 120)}"`) });

  // Get store name display area
  const h1s = await page.locator('h1, h2, h3, [class*="title"]').allTextContents();
  console.log("\n=== HEADINGS ===");
  h1s.forEach((h, i) => { if (h.trim()) console.log(`  [${i}] "${h.trim().substring(0, 80)}"`) });

  // Specifically look at the summary strip cards
  const summaryCards = await page.locator('[class*="card"]').evaluateAll(els =>
    els.map(el => ({ text: el.textContent.trim(), classes: el.className }))
  );
  console.log("\n=== CARD ELEMENTS ===");
  summaryCards.forEach((c, i) => {
    if (c.text.length > 2 && c.text.length < 100)
      console.log(`  [${i}] text="${c.text}" class="${c.classes.substring(0, 60)}"`)
  });

  await browser.close();
})();
