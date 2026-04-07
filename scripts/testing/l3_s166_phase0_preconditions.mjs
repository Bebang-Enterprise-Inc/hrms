/**
 * S166 Phase 0 — Preconditions Gathering
 *
 * Read-only queries against production to collect the data the lifecycle
 * scenarios need: branches, salary structure template, leave/OT types,
 * clearance stations, payroll period, Bio ID baseline, test account logins,
 * Documenso reachability.
 *
 * Output: data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/PRECONDITIONS.json
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const RUN_DIR = "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution";
const OUT = path.join(RUN_DIR, "PRECONDITIONS.json");

const ACCOUNTS = [
  "test.hr@bebang.ph",
  "test.crew1@bebang.ph",
  "test.finance@bebang.ph",
  "test.supervisor@bebang.ph",
  "test.area@bebang.ph",
];

async function loginMyBebang(page, email) {
  // Login via Frappe first (session cookies), then my.bebang.ph.
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1000);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  return page.url();
}

async function apiGet(page, path) {
  return await page.evaluate(async (p) => {
    const r = await fetch(p, { headers: { Accept: "application/json" } });
    const text = await r.text();
    let json = null;
    try { json = JSON.parse(text); } catch {}
    return { ok: r.ok, status: r.status, json, bodyHead: text.substring(0, 500) };
  }, path);
}

async function run() {
  fs.mkdirSync(RUN_DIR, { recursive: true });
  const result = {
    run_id: "s166-phase0-" + new Date().toISOString(),
    timestamp_pht: new Date().toLocaleString("en-PH", { timeZone: "Asia/Manila" }),
    accounts: {},
    branches: null,
    device_to_store: null,
    salary_structures: null,
    leave_types: null,
    overtime_types: null,
    clearance_stations: null,
    disciplinary_categories: null,
    payroll_period: null,
    bio_id_baseline: null,
    documenso_reachable: null,
    notes: [],
  };

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });

  try {
    // ── Step 1: Verify every test account can log in ──
    for (const email of ACCOUNTS) {
      const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
      const page = await ctx.newPage();
      try {
        const finalUrl = await loginMyBebang(page, email);
        const loggedIn = finalUrl.includes("/dashboard");
        result.accounts[email] = { login_ok: loggedIn, final_url: finalUrl };
        console.log(`[${loggedIn ? "OK" : "FAIL"}] ${email} → ${finalUrl}`);
      } catch (e) {
        result.accounts[email] = { login_ok: false, error: String(e).substring(0, 300) };
        console.log(`[FAIL] ${email} → ${e.message}`);
      } finally {
        await ctx.close();
      }
    }

    // ── Step 2: Use the HR session for backend queries ──
    const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const page = await ctx.newPage();
    await loginMyBebang(page, "test.hr@bebang.ph");

    // Branches + device mapping
    console.log("\n=== Query branches ===");
    const branches = await apiGet(page, "/api/frappe/api/resource/Branch?fields=[\"name\",\"branch\"]&limit_page_length=500");
    result.branches = branches.ok ? (branches.json?.data || []) : { error: branches.status, body: branches.bodyHead };

    // Try DEVICE_TO_STORE via common internal endpoints
    const deviceMapTries = [
      "/api/frappe/api/method/hrms.api.adms_config.get_device_to_store",
      "/api/frappe/api/method/hrms.api.adms.get_device_to_store_map",
      "/api/frappe/api/resource/BEI Biometric Device?fields=[\"name\",\"store_location\",\"device_serial\",\"device_ip\"]&limit_page_length=100",
    ];
    for (const p of deviceMapTries) {
      const r = await apiGet(page, p);
      if (r.ok) {
        result.device_to_store = { endpoint: p, data: r.json?.message || r.json?.data || r.json };
        console.log(`device map OK via ${p}`);
        break;
      } else {
        console.log(`device map try ${p} → ${r.status}`);
      }
    }
    if (!result.device_to_store) result.device_to_store = { error: "no endpoint returned 200", tried: deviceMapTries };

    // Salary structures
    console.log("\n=== Query salary structures ===");
    const ss = await apiGet(page, "/api/frappe/api/resource/Salary Structure?fields=[\"name\",\"is_active\",\"company\"]&limit_page_length=50");
    result.salary_structures = ss.ok ? (ss.json?.data || []) : { error: ss.status };

    // Leave types
    console.log("=== Query leave types ===");
    const lt = await apiGet(page, "/api/frappe/api/resource/Leave Type?fields=[\"name\",\"is_ppl\",\"is_lwp\",\"max_leaves_allowed\"]&limit_page_length=50");
    result.leave_types = lt.ok ? (lt.json?.data || []) : { error: lt.status };

    // OT types (try a few doctype names)
    for (const dt of ["Employee Overtime Type", "Overtime Type", "HR Overtime Type", "BEI Overtime Type"]) {
      const r = await apiGet(page, `/api/frappe/api/resource/${encodeURIComponent(dt)}?limit_page_length=50`);
      if (r.ok) { result.overtime_types = { doctype: dt, data: r.json?.data }; break; }
    }
    if (!result.overtime_types) result.overtime_types = { error: "no OT type doctype resolved" };

    // Clearance stations
    for (const dt of ["BEI Clearance Station", "Clearance Station", "BEI Clearance Item"]) {
      const r = await apiGet(page, `/api/frappe/api/resource/${encodeURIComponent(dt)}?limit_page_length=100`);
      if (r.ok) { result.clearance_stations = { doctype: dt, data: r.json?.data }; break; }
    }
    if (!result.clearance_stations) result.clearance_stations = { error: "no clearance station doctype resolved" };

    // Disciplinary categories
    for (const dt of ["Employee Grievance Type", "BEI Disciplinary Category", "Disciplinary Action Type", "BEI Disciplinary Case"]) {
      const r = await apiGet(page, `/api/frappe/api/resource/${encodeURIComponent(dt)}?limit_page_length=50`);
      if (r.ok) { result.disciplinary_categories = { doctype: dt, data: r.json?.data }; break; }
    }
    if (!result.disciplinary_categories) result.disciplinary_categories = { error: "no disciplinary doctype resolved" };

    // Current payroll period
    const pp = await apiGet(page, "/api/frappe/api/resource/Payroll Period?fields=[\"name\",\"start_date\",\"end_date\"]&order_by=start_date desc&limit_page_length=5");
    result.payroll_period = pp.ok ? (pp.json?.data || []) : { error: pp.status };

    // Bio ID baseline (max current)
    const bio = await apiGet(page, "/api/frappe/api/method/frappe.client.get_list?doctype=Employee&fields=[\"name\",\"attendance_device_id\"]&filters=[[\"attendance_device_id\",\"like\",\"9%\"]]&order_by=attendance_device_id desc&limit_page_length=5");
    result.bio_id_baseline = bio.ok ? bio.json?.message : { error: bio.status };

    // Documenso reachability
    const documenso = await page.evaluate(async () => {
      try {
        const r = await fetch("https://sign.bebang.ph/api/", { method: "HEAD", mode: "no-cors" });
        return { reached: true, status: r.status };
      } catch (e) { return { reached: false, error: String(e).substring(0, 200) }; }
    });
    result.documenso_reachable = documenso;

    await ctx.close();
  } catch (e) {
    result.fatal = String(e);
    console.error("FATAL", e);
  } finally {
    await browser.close();
  }

  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  console.log(`\n>>> wrote ${OUT}`);

  // Print a quick summary
  const ok = Object.values(result.accounts).filter(a => a.login_ok).length;
  console.log(`\nSUMMARY: ${ok}/${ACCOUNTS.length} accounts login_ok`);
  console.log(`branches: ${Array.isArray(result.branches) ? result.branches.length : "ERR"}`);
  console.log(`salary_structures: ${Array.isArray(result.salary_structures) ? result.salary_structures.length : "ERR"}`);
  console.log(`leave_types: ${Array.isArray(result.leave_types) ? result.leave_types.length : "ERR"}`);
  console.log(`documenso_reached: ${result.documenso_reachable?.reached}`);
}

run().catch((e) => { console.error(e); process.exit(1); });
