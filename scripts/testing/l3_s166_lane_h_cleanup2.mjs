/**
 * S166 Lane H — cleanup attempt 2.
 * Try frappe.client.save with the full doc including status=Left.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const EMAIL = "test.hr@bebang.ph";
const PASSWORD = "BeiTest2026!";
const LANE_DIR = "output/l3/s166/lanes/lane_h";
const TARGETS = ["HR-EMP-00030", "HR-EMP-00031"];

async function loginMyBebang(page) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', EMAIL);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1000);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', EMAIL).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForTimeout(2000);
  }
  console.log("logged in:", page.url());
}

async function apiCall(page, url, opts = {}) {
  return page.evaluate(async ({ url, opts }) => {
    const resp = await fetch(url, { credentials: "include", ...opts });
    const text = await resp.text();
    let json = null; try { json = JSON.parse(text); } catch {}
    return { status: resp.status, ok: resp.ok, json, bodyHead: text.substring(0, 800) };
  }, { url, opts });
}

async function run() {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  const extra_mutations = [];
  const final_records = [];

  try {
    await loginMyBebang(page);

    for (const name of TARGETS) {
      console.log(`\n=== ${name} ===`);

      // Approach A: update via resource PUT with full body (including company-wide required fields)
      // First fetch the current doc
      const cur = await apiCall(page, `/api/frappe/api/resource/Employee/${encodeURIComponent(name)}`);
      if (!cur.ok) {
        console.log(`  fetch failed: ${cur.status} ${cur.bodyHead}`);
        continue;
      }
      const doc = cur.json?.data;
      console.log(`  current status: ${doc?.status}, relieving_date: ${doc?.relieving_date}`);

      if (doc?.status === "Left") {
        console.log("  already Left — skip");
        final_records.push({ name, employee_name: doc.employee_name, cleanup_status: "already_left" });
        continue;
      }

      // Approach A: PUT resource with only the 2 changed fields
      const putA = await apiCall(page, `/api/frappe/api/resource/Employee/${encodeURIComponent(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "Left", relieving_date: "2026-04-07" }),
      });
      extra_mutations.push({ approach: "PUT_resource_minimal", name, status: putA.status, ok: putA.ok, resp: putA.json || putA.bodyHead });
      console.log(`  [A] PUT minimal: ${putA.status} ${putA.ok ? "OK" : "FAIL"}`);
      if (!putA.ok) console.log(`     body: ${putA.bodyHead.substring(0, 300)}`);

      // Re-check
      const recheck = await apiCall(page, `/api/frappe/api/resource/Employee/${encodeURIComponent(name)}`);
      const newStatus = recheck.json?.data?.status;
      console.log(`  recheck status: ${newStatus}`);
      final_records.push({
        name,
        employee_name: doc.employee_name,
        branch: doc.branch,
        bio_id_before: doc.attendance_device_id,
        status_before: doc.status,
        status_after: newStatus,
        cleanup_status: newStatus === "Left" ? "deleted" : "failed",
      });
    }
  } finally {
    await ctx.close();
    await browser.close();
  }

  // Merge into files
  const apiMutPath = path.join(LANE_DIR, "api_mutations.json");
  const existing = JSON.parse(fs.readFileSync(apiMutPath, "utf8"));
  fs.writeFileSync(apiMutPath, JSON.stringify([...existing, ...extra_mutations], null, 2));

  console.log("\n=== final ===");
  for (const r of final_records) console.log(`  ${r.name}: ${r.cleanup_status} (${r.status_before} -> ${r.status_after})`);

  // Update EMP_STATE + ORPHANS
  fs.writeFileSync(path.join(LANE_DIR, "EMP_STATE.json"), JSON.stringify({ created_employees: final_records }, null, 2));
  const orphanLines = ["name,employee_name,branch,status_after,reason"];
  for (const r of final_records) {
    if (r.cleanup_status !== "deleted" && r.cleanup_status !== "already_left") {
      orphanLines.push(`${r.name},"${r.employee_name}",${r.branch},${r.status_after},cleanup_failed_status_not_updated`);
    }
  }
  fs.writeFileSync(path.join(LANE_DIR, "ORPHANS.csv"), orphanLines.join("\n"));
}

run().catch((e) => { console.error(e); process.exit(1); });
