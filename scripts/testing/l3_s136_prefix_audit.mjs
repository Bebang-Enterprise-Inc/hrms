import { chromium } from "playwright";
import fs from "fs";

const results = [];
const defects = [];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  await page.goto("https://my.bebang.ph/login", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  await page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().fill("sam@bebang.ph");
  await page.locator('input[type="password"]').first().fill("2289454");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(10000);

  await page.goto("https://my.bebang.ph/dashboard/store-ops/ordering", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(8000);

  // CHECK 1: Store picker
  const storeResp = await page.evaluate(async () => {
    const r = await fetch("/api/store/user-store");
    return r.json();
  });
  const stores = storeResp?.data?.stores || [];
  const storeNames = stores.map(s => s.warehouse_name);
  const fgCount = storeNames.filter(n => n === "Finished Goods").length;
  const wipCount = storeNames.filter(n => n === "Work In Progress").length;
  const testCount = storeNames.filter(n => n.startsWith("TEST-STORE")).length;
  const rmCount = storeNames.filter(n => n === "Raw Materials").length;
  console.log("CHECK 1: Picker — total=" + stores.length + " FG=" + fgCount + " WIP=" + wipCount + " RM=" + rmCount + " TEST=" + testCount);
  if (fgCount + wipCount + testCount + rmCount > 0) defects.push({ id: "D1+D2", severity: "MAJOR", desc: `Picker leaks FG(${fgCount}) WIP(${wipCount}) RM(${rmCount}) TEST(${testCount})` });
  results.push({ check: "Picker clean", pass: fgCount + wipCount + testCount + rmCount === 0, detail: `FG=${fgCount} WIP=${wipCount} TEST=${testCount}` });

  // CHECK 2: API data
  const store = storeResp?.data?.default_store;
  const orderResp = await page.evaluate(async (s) => {
    const r = await fetch("/api/ordering?action=get_orderable_items&store=" + encodeURIComponent(s));
    return r.json();
  }, store);
  const items = orderResp?.data?.items || [];
  console.log("CHECK 2: Items=" + items.length + " store=" + store);

  // 2a: store_actual_qty
  const hasStoreActual = items[0]?.store_actual_qty !== undefined;
  console.log("  2a store_actual_qty: " + hasStoreActual);
  if (!hasStoreActual) defects.push({ id: "D3-api", severity: "CRITICAL", desc: "No store_actual_qty in API" });
  results.push({ check: "store_actual_qty field", pass: hasStoreActual });

  // 2b: source_warehouse_short
  const hasSourceShort = items[0]?.source_warehouse_short !== undefined;
  console.log("  2b source_warehouse_short: " + hasSourceShort);
  if (!hasSourceShort) defects.push({ id: "D6-api", severity: "MINOR", desc: "No source_warehouse_short in API" });
  results.push({ check: "source_warehouse_short field", pass: hasSourceShort });

  // 2c: circular source
  const circular = items.filter(i => i.source_warehouse === store);
  console.log("  2c circular source: " + circular.length + "/" + items.length);
  if (circular.length > 0) defects.push({ id: "D7", severity: "CRITICAL", desc: `${circular.length} items source from store itself` });
  results.push({ check: "No circular source", pass: circular.length === 0, detail: circular.length + " circular" });

  // 2d: absurd suggested
  const absurd = items.filter(i => i.suggested_qty > 500);
  console.log("  2d suggested > 500: " + absurd.length);
  if (absurd.length > 5) defects.push({ id: "D5", severity: "CRITICAL", desc: `${absurd.length} items suggested > 500` });
  results.push({ check: "Suggested reasonable", pass: absurd.length <= 5 });

  // 2e: OOS rate
  const oos = items.filter(i => i.available_to_promise <= 0);
  const oosRate = Math.round(oos.length / items.length * 100);
  console.log("  2e OOS rate: " + oosRate + "%");
  if (oosRate > 50) defects.push({ id: "D8", severity: "MAJOR", desc: oosRate + "% OOS" });
  results.push({ check: "OOS < 50%", pass: oosRate < 50, detail: oosRate + "%" });

  // 2f: all heuristic
  const recSources = [...new Set(items.map(i => i.recommendation_source))];
  console.log("  2f rec sources: " + recSources.join(","));
  if (recSources.length === 1 && recSources[0] === "heuristic") defects.push({ id: "D9", severity: "MAJOR", desc: "All heuristic, no snapshots" });
  results.push({ check: "Has demand snapshots", pass: recSources.length > 1 });

  // CHECK 3: Store stock
  const stockResp = await page.evaluate(async (s) => {
    const r = await fetch("/api/ordering?action=get_store_stock&store=" + encodeURIComponent(s) + "&include_zero_stock=1");
    return r.json();
  }, store);
  const stockItems = stockResp?.data?.items || [];
  const withStock = stockItems.filter(i => i.actual_qty > 0);
  console.log("CHECK 3: Stock items=" + stockItems.length + " with qty>0=" + withStock.length);
  results.push({ check: "Store has stock data", pass: withStock.length > 0, detail: withStock.length + " items" });

  // CHECK 4: UI table
  const tableVisible = await page.locator("table").isVisible({ timeout: 5000 }).catch(() => false);
  console.log("CHECK 4: Table visible=" + tableVisible);

  if (tableVisible) {
    const headers = await page.locator("table thead th").allTextContents();
    console.log("  Headers: " + headers.join(" | "));
    const hasCommissary = headers.some(h => h.includes("Commissary"));
    if (hasCommissary) defects.push({ id: "D6-ui", severity: "MAJOR", desc: "Column says Commissary" });
    results.push({ check: "No Commissary label", pass: !hasCommissary });

    const rows = page.locator("table tbody tr");
    const rowCount = await rows.count();
    let onHandNonZero = 0;
    for (let i = 0; i < Math.min(rowCount, 30); i++) {
      const cell = await rows.nth(i).locator("td").nth(2).textContent();
      if (parseFloat(cell) > 0) onHandNonZero++;
    }
    console.log("  On Hand non-zero: " + onHandNonZero + "/" + Math.min(rowCount, 30));
    if (onHandNonZero === 0 && withStock.length > 0) defects.push({ id: "D3-ui", severity: "CRITICAL", desc: "On Hand all zero despite " + withStock.length + " stock items" });
    results.push({ check: "On Hand shows real values", pass: onHandNonZero > 0 });

    // Demand/Day value check
    if (rowCount > 0) {
      const demandCell = await rows.first().locator("td").nth(5).textContent();
      const demandVal = parseFloat(demandCell);
      console.log("  First Demand/Day: " + demandVal);
      if (demandVal > 1000) defects.push({ id: "D4-ui", severity: "CRITICAL", desc: "Demand/Day=" + demandVal + " (multi-day total)" });
      results.push({ check: "Demand/Day is daily", pass: isNaN(demandVal) || demandVal < 1000, detail: String(demandVal) });
    }
  }

  // CHECK 5: Submit flow exists
  const fillBtn = await page.locator('button:has-text("Fill Suggested")').isVisible().catch(() => false);
  results.push({ check: "Fill Suggested button", pass: fillBtn });

  // CHECK 6: Last Order button
  const lastBtn = await page.locator('button:has-text("Last Order")').isVisible().catch(() => false);
  results.push({ check: "Last Order button", pass: lastBtn });

  // CHECK 7: Category filters
  const fcBtn = await page.locator('button:has-text("FC")').isVisible().catch(() => false);
  results.push({ check: "Category filters", pass: fcBtn });

  // CHECK 8: Need Reorder default ON
  const nrBtn = page.locator('button:has-text("Need Reorder")');
  const nrClasses = await nrBtn.getAttribute("class").catch(() => "");
  const nrActive = nrClasses.includes("bg-primary");
  results.push({ check: "Need Reorder default ON", pass: nrActive });

  fs.mkdirSync("output/l3/S136/artifacts", { recursive: true });
  fs.mkdirSync("output/l3/S136/evidence", { recursive: true });
  await page.screenshot({ path: "output/l3/S136/artifacts/pre_fix_audit.png" });

  // SUMMARY
  console.log("\n========================================");
  console.log("L3 S136 PRE-FIX AUDIT (2026-03-27)");
  console.log("========================================");
  let passCount = 0;
  for (const r of results) {
    const s = r.pass ? "PASS" : "FAIL";
    if (r.pass) passCount++;
    console.log(`[${s}] ${r.check}${r.detail ? " — " + r.detail : ""}`);
  }
  console.log(`\nTotal: ${passCount}/${results.length} PASS, ${results.length - passCount} FAIL`);
  console.log(`\nDEFECTS (${defects.length}):`);
  for (const d of defects) console.log(`  [${d.severity}] ${d.id}: ${d.desc}`);

  fs.writeFileSync("output/l3/S136/evidence/pre_fix_audit.json", JSON.stringify({ results, defects, timestamp: new Date().toISOString() }, null, 2));

  await browser.close();
})().catch(e => console.error("ERROR:", e.message));
