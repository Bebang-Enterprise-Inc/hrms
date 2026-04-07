/**
 * S166 Lane H — post-run cleanup.
 * Finds NO_DEV test employees created during the runner and soft-deletes them.
 * Also fixes the bio_id_outlier and rewrites EMP_STATE.json + state_verification.json.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const EMAIL = "test.hr@bebang.ph";
const PASSWORD = "BeiTest2026!";
const LANE_DIR = "output/l3/s166/lanes/lane_h";

async function loginMyBebang(page) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', EMAIL);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', EMAIL).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  console.log("logged in:", page.url());
}

async function apiCall(page, url, opts = {}) {
  return page.evaluate(async ({ url, opts }) => {
    const resp = await fetch(url, opts);
    const text = await resp.text();
    let json = null; try { json = JSON.parse(text); } catch {}
    return { status: resp.status, ok: resp.ok, json, bodyHead: text.substring(0, 500) };
  }, { url, opts });
}

async function findEmployees(page) {
  // Look up employees by employee_name LIKE %NO_DEV%
  const filters = encodeURIComponent(JSON.stringify([["employee_name", "like", "%NO_DEV%"]]));
  const fields = encodeURIComponent(JSON.stringify(["name", "employee_name", "status", "attendance_device_id", "branch"]));
  const url = `/api/frappe/api/resource/Employee?filters=${filters}&fields=${fields}&limit_page_length=100`;
  const r = await apiCall(page, url);
  return r.json?.data || [];
}

async function setValue(page, empName, fieldname, value) {
  const body = new URLSearchParams();
  body.set("doctype", "Employee");
  body.set("name", empName);
  body.set("fieldname", fieldname);
  body.set("value", value);
  const r = await apiCall(page, "/api/frappe/api/method/frappe.client.set_value", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  return r;
}

async function run() {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const today = new Date().toISOString().slice(0, 10);

  const created_employees = [];
  const api_mutations_extra = [];
  const state_verification_extra = [];

  try {
    await loginMyBebang(page);

    console.log("\n=== find orphans ===");
    const found = await findEmployees(page);
    console.log(`found ${found.length} employees matching NO_DEV:`);
    for (const e of found) console.log(`  ${e.name} | ${e.employee_name} | status=${e.status} | bio=${e.attendance_device_id} | branch=${e.branch}`);

    console.log("\n=== soft delete ===");
    for (const e of found) {
      const record = { name: e.name, employee_name: e.employee_name, branch: e.branch, bio_id: e.attendance_device_id, cleanup_status: "pending" };
      // Clear bio_id first (per S164 playbook - don't leave bogus Bio IDs on non-active employees)
      const bioClear = await setValue(page, e.name, "attendance_device_id", "");
      api_mutations_extra.push({ type: "clear_bio_id", employee: e.name, ok: bioClear.ok, status: bioClear.status });
      // Set status=Left
      const statusSet = await setValue(page, e.name, "status", "Left");
      api_mutations_extra.push({ type: "soft_delete_status", employee: e.name, ok: statusSet.ok, status: statusSet.status, response: statusSet.json });
      // Set relieving_date
      const relSet = await setValue(page, e.name, "relieving_date", today);
      api_mutations_extra.push({ type: "soft_delete_relieving", employee: e.name, ok: relSet.ok, status: relSet.status });

      const allOk = bioClear.ok && statusSet.ok && relSet.ok;
      record.cleanup_status = allOk ? "deleted" : `partial_fail bio=${bioClear.ok} status=${statusSet.ok} rel=${relSet.ok}`;
      created_employees.push(record);
      console.log(`  ${e.name}: ${record.cleanup_status}`);
    }

    console.log("\n=== verify no active orphans ===");
    const afterFound = await findEmployees(page);
    const activeAfter = afterFound.filter((e) => e.status === "Active");
    console.log(`active NO_DEV employees after cleanup: ${activeAfter.length}`);
    state_verification_extra.push({
      check: "no_active_NO_DEV_orphans_postcleanup",
      status: activeAfter.length === 0 ? "PASS" : "FAIL",
      count: activeAfter.length,
      all_matching: afterFound,
    });
  } finally {
    await ctx.close();
    await browser.close();
  }

  // Merge into lane files
  const empStatePath = path.join(LANE_DIR, "EMP_STATE.json");
  fs.writeFileSync(empStatePath, JSON.stringify({ created_employees }, null, 2));

  const apiMutPath = path.join(LANE_DIR, "api_mutations.json");
  const existing = JSON.parse(fs.readFileSync(apiMutPath, "utf8"));
  fs.writeFileSync(apiMutPath, JSON.stringify([...existing, ...api_mutations_extra], null, 2));

  const svPath = path.join(LANE_DIR, "state_verification.json");
  let svExisting = [];
  try { svExisting = JSON.parse(fs.readFileSync(svPath, "utf8")); } catch {}
  fs.writeFileSync(svPath, JSON.stringify([...svExisting, ...state_verification_extra], null, 2));

  // ORPHANS.csv
  const orphanLines = ["name,employee_name,status,reason"];
  for (const e of created_employees) {
    if (e.cleanup_status !== "deleted") orphanLines.push(`${e.name},"${e.employee_name}",?,${e.cleanup_status}`);
  }
  fs.writeFileSync(path.join(LANE_DIR, "ORPHANS.csv"), orphanLines.join("\n"));

  console.log("\ncleanup complete. employees:", created_employees.length);
  for (const e of created_employees) console.log(`  ${e.name}: ${e.cleanup_status}`);
}

run().catch((e) => { console.error(e); process.exit(1); });
