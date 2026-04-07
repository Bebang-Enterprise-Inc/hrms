import { chromium } from "playwright";
const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";

async function run() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', "test.hr@bebang.ph");
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  // Query Frappe directly (hq.bebang.ph) since cookies are there
  await page.goto(`${FRAPPE}/app`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});

  async function q(url) {
    return await page.evaluate(async (u) => {
      const r = await fetch(u, { headers: { Accept: "application/json" }, credentials: "include" });
      const text = await r.text();
      let json = null; try { json = JSON.parse(text); } catch {}
      return { status: r.status, json, bodyHead: text.substring(0, 400) };
    }, url);
  }

  const results = {};
  const F = FRAPPE;

  results.orphan_hunt = await q(`${F}/api/resource/Employee?filters=${encodeURIComponent(JSON.stringify([["employee_name","like","%L3 2026-04-07%NO_DEV%"],["status","=","Active"]]))}&limit_page_length=10`);
  results.juan = await q(`${F}/api/resource/Employee?filters=${encodeURIComponent(JSON.stringify([["employee_name","like","%Juan Dela Cruz (L3 2026-04-07%NO_DEV%"]]))}&fields=${encodeURIComponent(JSON.stringify(["name","status","relieving_date","attendance_device_id","branch"]))}&limit_page_length=5`);
  results.maria = await q(`${F}/api/resource/Employee?filters=${encodeURIComponent(JSON.stringify([["employee_name","like","%Maria Dela Cruz (L3 2026-04-07%NO_DEV%"]]))}&fields=${encodeURIComponent(JSON.stringify(["name","status","relieving_date","attendance_device_id","branch"]))}&limit_page_length=5`);

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
}
run().catch((e) => { console.error(e); process.exit(1); });
