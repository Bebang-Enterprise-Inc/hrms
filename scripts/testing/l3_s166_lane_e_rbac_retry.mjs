/**
 * Lane E follow-up: retry EMP-CREATE-009 / EMP-RBAC-002 with a COMPLETE payload
 * (branch + company) so the permission check is actually exercised.
 * The initial run got a TypeError 500 because the endpoint requires branch+company
 * as positional args. A proper RBAC check needs to pass signature validation first.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const OUT_DIR = "output/l3/s166/lanes/lane_e";
const EV_DIR = path.join(OUT_DIR, "evidence");

async function loginMyBebang(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1200);
}

async function apiCall(page, url, init = {}) {
  return await page.evaluate(async ({ url, init }) => {
    const r = await fetch(url, {
      method: init.method || "GET",
      headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) },
      body: init.body || undefined,
      credentials: "include",
    });
    const text = await r.text();
    let json = null; try { json = JSON.parse(text); } catch {}
    return { ok: r.ok, status: r.status, json, bodyHead: text.substring(0, 2000) };
  }, { url, init });
}

async function run() {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  await loginMyBebang(page, "test.crew1@bebang.ph");

  // Count before
  const cBefore = await apiCall(page, "/api/frappe/api/method/frappe.client.get_count?doctype=Employee");
  const before = cBefore.json?.message ?? null;

  const payload = {
    employee_name: "RBAC Test Denied Retry",
    first_name: "RBAC",
    last_name: "DeniedRetry",
    gender: "Male",
    date_of_birth: "1995-01-01",
    date_of_joining: "2026-04-07",
    status: "Active",
    branch: "Main Office",
    company: "Bebang Enterprise Inc.",
  };
  const r = await apiCall(page, "/api/frappe/api/method/hrms.api.employee_create.create_employee_direct", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const cAfter = await apiCall(page, "/api/frappe/api/method/frappe.client.get_count?doctype=Employee");
  const after = cAfter.json?.message ?? null;

  const isPermErr = /PermissionError|not permitted|permission/i.test(JSON.stringify(r.json || {}));
  const blocked = r.status === 403 || r.status === 401 || isPermErr;
  const countUnchanged = before === after;

  const evidence = {
    scenario_id: "EMP-CREATE-009_retry",
    role: "test.crew1",
    ts: new Date().toISOString(),
    request_payload: payload,
    response: { status: r.status, exception_head: (r.json?.exception || "").substring(0, 400), body_head: r.bodyHead.substring(0, 1000) },
    before_count: before,
    after_count: after,
    count_unchanged: countUnchanged,
    permission_error_detected: isPermErr,
    blocked_by_rbac: blocked,
    final_verdict: blocked && countUnchanged ? "RBAC_ENFORCED" : (!countUnchanged ? "CRITICAL_RBAC_BROKEN_EMPLOYEE_CREATED" : "RBAC_UNCLEAR_NEEDS_INVESTIGATION"),
  };
  fs.writeFileSync(path.join(EV_DIR, "EMP-CREATE-009_retry.json"), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));

  await ctx.close();
  await browser.close();
}
run().catch(e => { console.error(e); process.exit(1); });
