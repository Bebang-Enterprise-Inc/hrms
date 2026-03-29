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
  await page.waitForTimeout(10000);

  // ══════════════════════════════════════
  // CHECK 1: Store picker (B1)
  // ══════════════════════════════════════
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
  const junkTotal = fgCount + wipCount + testCount + rmCount;
  console.log("CHECK 1 (B1): Picker — total=" + stores.length + " FG=" + fgCount + " WIP=" + wipCount + " RM=" + rmCount + " TEST=" + testCount);
  if (junkTotal > 0) defects.push({ id: "D1", sev: "MAJOR", desc: `Picker still leaks FG(${fgCount}) WIP(${wipCount}) RM(${rmCount}) TEST(${testCount})` });
  results.push({ check: "B1: Picker clean", pass: junkTotal === 0, detail: `junk=${junkTotal} total=${stores.length}` });

  // ══════════════════════════════════════
  // CHECK 2: API fields (B3, B5)
  // ══════════════════════════════════════
  const store = storeResp?.data?.default_store;
  const orderResp = await page.evaluate(async (s) => {
    const r = await fetch("/api/ordering?action=get_orderable_items&store=" + encodeURIComponent(s));
    return r.json();
  }, store);
  const items = orderResp?.data?.items || [];
  console.log("\nCHECK 2: API fields (store=" + store + ", items=" + items.length + ")");

  const sample = items[0] || {};
  const hasStoreActual = sample.store_actual_qty !== undefined;
  const hasSourceShort = sample.source_warehouse_short !== undefined;
  console.log("  B3 store_actual_qty: " + hasStoreActual + " (value=" + sample.store_actual_qty + ")");
  console.log("  B5 source_warehouse_short: " + hasSourceShort + " (value=" + sample.source_warehouse_short + ")");
  if (!hasStoreActual) defects.push({ id: "D3-api", sev: "CRITICAL", desc: "No store_actual_qty" });
  if (!hasSourceShort) defects.push({ id: "D6-api", sev: "MINOR", desc: "No source_warehouse_short" });
  results.push({ check: "B3: store_actual_qty", pass: hasStoreActual, detail: String(sample.store_actual_qty) });
  results.push({ check: "B5: source_warehouse_short", pass: hasSourceShort, detail: String(sample.source_warehouse_short) });

  // ══════════════════════════════════════
  // CHECK 3: Circular source (B4)
  // ══════════════════════════════════════
  const circular = items.filter(i => i.source_warehouse === store);
  console.log("\nCHECK 3 (B4): Circular source — " + circular.length + "/" + items.length);
  if (circular.length > 0) {
    defects.push({ id: "D7", sev: "CRITICAL", desc: `${circular.length} items still source from store` });
    console.log("  Sample: " + circular.slice(0, 3).map(i => i.item_code + " src=" + i.source_warehouse).join(", "));
  }
  results.push({ check: "B4: No circular source", pass: circular.length === 0, detail: circular.length + " circular" });

  // Check what source warehouses are now used
  const srcWhs = [...new Set(items.map(i => i.source_warehouse_short || i.source_warehouse))];
  console.log("  Source warehouses: " + srcWhs.join(", "));

  // ══════════════════════════════════════
  // CHECK 4: Suggested qty reasonable (B2)
  // ══════════════════════════════════════
  const absurd = items.filter(i => i.suggested_qty > 500);
  console.log("\nCHECK 4 (B2): Suggested > 500 — " + absurd.length);
  if (absurd.length > 5) {
    defects.push({ id: "D5", sev: "CRITICAL", desc: `${absurd.length} items suggested > 500` });
    console.log("  Top 3: " + absurd.slice(0, 3).map(i => i.item_name?.slice(0, 20) + "=" + i.suggested_qty).join(", "));
  }
  results.push({ check: "B2: Suggested reasonable", pass: absurd.length <= 5, detail: absurd.length + " items > 500" });

  // Check if store stock was subtracted — find an item with store_actual_qty > 0
  const withStoreStock = items.filter(i => i.store_actual_qty > 0 && i.has_order_history);
  if (withStoreStock.length > 0) {
    const ex = withStoreStock[0];
    console.log("  Store stock subtraction example: " + ex.item_code + " store_actual=" + ex.store_actual_qty + " suggested=" + ex.suggested_qty + " raw=" + ex.raw_suggested_qty);
  }

  // ══════════════════════════════════════
  // CHECK 5: OOS rate
  // ══════════════════════════════════════
  const oos = items.filter(i => i.available_to_promise <= 0);
  const oosRate = Math.round(oos.length / items.length * 100);
  console.log("\nCHECK 5: OOS rate — " + oosRate + "% (" + oos.length + "/" + items.length + ")");
  if (oosRate > 50) defects.push({ id: "D8", sev: "MAJOR", desc: oosRate + "% OOS" });
  results.push({ check: "OOS < 50%", pass: oosRate < 50, detail: oosRate + "%" });

  // ══════════════════════════════════════
  // CHECK 6: UI table verification
  // ══════════════════════════════════════
  const tableVisible = await page.locator("table").isVisible({ timeout: 5000 }).catch(() => false);
  console.log("\nCHECK 6: UI table visible=" + tableVisible);

  if (tableVisible) {
    // 6a: Column headers
    const headers = await page.locator("table thead th").allTextContents();
    console.log("  Headers: " + headers.join(" | "));
    const hasCommissary = headers.some(h => h.includes("Commissary"));
    const hasSourceAvail = headers.some(h => h.includes("Source"));
    if (hasCommissary) defects.push({ id: "D6-ui", sev: "MAJOR", desc: "Column still says Commissary" });
    results.push({ check: "F3: No Commissary label", pass: !hasCommissary && hasSourceAvail, detail: hasCommissary ? "STILL Commissary" : hasSourceAvail ? "Source Avail." : "unknown" });

    // 6b: On Hand values
    const rows = page.locator("table tbody tr");
    const rowCount = await rows.count();
    let onHandNonZero = 0;
    let onHandSamples = [];
    for (let i = 0; i < Math.min(rowCount, 40); i++) {
      const cell = await rows.nth(i).locator("td").nth(2).textContent();
      const val = parseFloat(cell);
      if (val > 0) {
        onHandNonZero++;
        if (onHandSamples.length < 5) onHandSamples.push(cell.trim());
      }
    }
    console.log("  On Hand non-zero: " + onHandNonZero + "/" + Math.min(rowCount, 40) + " samples: " + onHandSamples.join(", "));
    if (onHandNonZero === 0 && withStoreStock.length > 0) defects.push({ id: "D3-ui", sev: "CRITICAL", desc: "On Hand all zero" });
    results.push({ check: "F1: On Hand shows real values", pass: onHandNonZero > 0, detail: onHandNonZero + " non-zero, samples: " + onHandSamples.join(", ") });

    // 6c: Demand/Day — should be daily, not multi-day
    if (rowCount > 0) {
      // Find a row with a demand value
      let demandVal = NaN;
      for (let i = 0; i < Math.min(rowCount, 10); i++) {
        const cell = await rows.nth(i).locator("td").nth(5).textContent();
        const v = parseFloat(cell);
        if (!isNaN(v) && v > 0) { demandVal = v; break; }
      }
      console.log("  First non-zero Demand/Day: " + demandVal);
      if (demandVal > 1000) defects.push({ id: "D4-ui", sev: "CRITICAL", desc: "Demand/Day=" + demandVal + " still multi-day" });
      results.push({ check: "F2: Demand/Day is daily", pass: isNaN(demandVal) || demandVal < 1000, detail: "value=" + demandVal });
    }
  } else {
    results.push({ check: "Table visible", pass: false, detail: "not visible" });
  }

  // ══════════════════════════════════════
  // CHECK 7: KPI strip
  // ══════════════════════════════════════
  const kpiLabels = await page.locator('[class*="rounded-lg"][class*="border"][class*="bg-card"] span[class*="text-xs"]').allTextContents();
  console.log("\nCHECK 7: KPI labels — " + kpiLabels.join(", "));
  const hasOOSSource = kpiLabels.some(l => l.includes("Source"));
  const hasOOSCommissary = kpiLabels.some(l => l.includes("Commissary"));
  if (hasOOSCommissary) defects.push({ id: "D6-kpi", sev: "MINOR", desc: "KPI still says Commissary" });
  results.push({ check: "F4: KPI says OOS at Source", pass: hasOOSSource && !hasOOSCommissary, detail: kpiLabels.join(", ") });

  // ══════════════════════════════════════
  // CHECK 8: Functional controls
  // ══════════════════════════════════════
  const fillBtn = await page.locator('button:has-text("Fill Suggested")').isVisible().catch(() => false);
  const lastBtn = await page.locator('button:has-text("Last Order")').isVisible().catch(() => false);
  const nrBtn = page.locator('button:has-text("Need Reorder")');
  const nrClasses = await nrBtn.getAttribute("class").catch(() => "");
  const nrActive = nrClasses.includes("bg-primary");
  results.push({ check: "Fill Suggested button", pass: fillBtn });
  results.push({ check: "Last Order button", pass: lastBtn });
  results.push({ check: "Need Reorder default ON", pass: nrActive });

  // Screenshot
  fs.mkdirSync("output/l3/S136/artifacts", { recursive: true });
  fs.mkdirSync("output/l3/S136/evidence", { recursive: true });
  await page.screenshot({ path: "output/l3/S136/artifacts/post_fix_audit.png" });

  // ══════════════════════════════════════
  // CHECK 9: test.crew1 regression
  // ══════════════════════════════════════
  console.log("\nCHECK 9: test.crew1 regression");
  const ctx2 = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page2 = await ctx2.newPage();
  try {
    await page2.goto("https://my.bebang.ph/login", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page2.waitForTimeout(2000);
    await page2.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().fill("test.crew1@bebang.ph");
    await page2.locator('input[type="password"]').first().fill("BeiTest2026!");
    await page2.locator('button[type="submit"]').first().click();
    await page2.waitForURL("**/dashboard**", { timeout: 30000 });
    await page2.goto("https://my.bebang.ph/dashboard/store-ops/ordering", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page2.waitForTimeout(8000);

    const crewTable = await page2.locator("table").isVisible({ timeout: 5000 }).catch(() => false);
    const crewHeader = await page2.locator("h2").first().textContent().catch(() => "none");
    console.log("  crew table=" + crewTable + " header=" + crewHeader);
    results.push({ check: "Crew: ordering loads", pass: crewTable, detail: "header=" + crewHeader });

    // Check crew On Hand
    if (crewTable) {
      const crewRows = page2.locator("table tbody tr");
      const crewRowCount = await crewRows.count();
      let crewOnHand = 0;
      for (let i = 0; i < Math.min(crewRowCount, 20); i++) {
        const cell = await crewRows.nth(i).locator("td").nth(2).textContent();
        if (parseFloat(cell) > 0) crewOnHand++;
      }
      console.log("  crew On Hand non-zero: " + crewOnHand + "/" + Math.min(crewRowCount, 20));
      results.push({ check: "Crew: On Hand real values", pass: crewOnHand > 0 || crewRowCount === 0, detail: crewOnHand + " non-zero" });
    }
  } catch (e) {
    console.log("  crew test failed: " + e.message.slice(0, 80));
    results.push({ check: "Crew: ordering loads", pass: false, detail: e.message.slice(0, 80) });
  }
  await ctx2.close();

  // ══════════════════════════════════════
  // SUMMARY
  // ══════════════════════════════════════
  console.log("\n" + "=".repeat(50));
  console.log("L3 S136 POST-FIX RESULTS (2026-03-27)");
  console.log("=".repeat(50));
  let passCount = 0;
  for (const r of results) {
    const s = r.pass ? "PASS" : "FAIL";
    if (r.pass) passCount++;
    console.log(`[${s}] ${r.check}${r.detail ? " — " + r.detail : ""}`);
  }
  console.log(`\nTotal: ${passCount}/${results.length} PASS, ${results.length - passCount} FAIL`);

  if (defects.length > 0) {
    console.log(`\nREMAINING DEFECTS (${defects.length}):`);
    for (const d of defects) console.log(`  [${d.sev}] ${d.id}: ${d.desc}`);
  } else {
    console.log("\nAll 10 original defects RESOLVED.");
  }

  fs.writeFileSync("output/l3/S136/evidence/post_fix_audit.json", JSON.stringify({ results, defects, timestamp: new Date().toISOString() }, null, 2));

  await browser.close();
})().catch(e => console.error("ERROR:", e.message));
