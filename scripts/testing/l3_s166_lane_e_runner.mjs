/**
 * S166 Lane E — RBAC L3 runner
 * Scenarios: EMP-CREATE-008, EMP-CREATE-009, EMP-RBAC-001..005
 * Evidence dir: output/l3/s166/lanes/lane_e
 *
 * Rules: no git ops, no plan edits, no employee creation. Real browser
 * sessions (test.crew1, test.finance). Headless. Any unexpected creation
 * is a CRITICAL RBAC defect and logged to DEFECTS.csv + ORPHANS.csv.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const OUT_DIR = "output/l3/s166/lanes/lane_e";
const EV_DIR = path.join(OUT_DIR, "evidence");
const SS_DIR = path.join(OUT_DIR, "screenshots");

fs.mkdirSync(EV_DIR, { recursive: true });
fs.mkdirSync(SS_DIR, { recursive: true });

const form_submissions = [];
const api_mutations = [];
const state_verification = [];
const defects = [];
const orphans = [];

function nowIso() { return new Date().toISOString(); }

async function loginMyBebang(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1200);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  return page.url();
}

async function apiCall(page, url, init = {}) {
  return await page.evaluate(async ({ url, init }) => {
    try {
      const r = await fetch(url, {
        method: init.method || "GET",
        headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) },
        body: init.body || undefined,
        credentials: "include",
      });
      const text = await r.text();
      let json = null; try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json, bodyHead: text.substring(0, 1500) };
    } catch (e) { return { ok: false, status: 0, error: String(e).substring(0, 400) }; }
  }, { url, init });
}

async function employeeCount(page) {
  const r = await apiCall(page, "/api/frappe/api/method/frappe.client.get_count?doctype=Employee");
  return r.ok ? (r.json?.message ?? null) : null;
}

function writeEvidence(id, obj) {
  fs.writeFileSync(path.join(EV_DIR, `${id}.json`), JSON.stringify(obj, null, 2));
}

// ─── Scenarios ───

async function runUiVisibilityCheck(page, scenarioId, role, note) {
  const resp = await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 }).catch(e => ({ _err: String(e) }));
  await page.waitForTimeout(1500);
  const httpStatus = resp && resp.status ? resp.status() : null;
  const url = page.url();
  const bodyText = await page.locator("body").innerText().catch(() => "");
  const restricted = /access restricted|forbidden|not authori[sz]ed|permission/i.test(bodyText);
  const addBtn = page.getByRole("button", { name: /add new employee/i });
  const addBtnCount = await addBtn.count().catch(() => 0);
  const addBtnVisible = addBtnCount > 0 ? await addBtn.first().isVisible().catch(() => false) : false;
  const ss = path.join(SS_DIR, `${scenarioId}_page.png`);
  await page.screenshot({ path: ss, fullPage: true }).catch(() => {});

  const pass = restricted || !addBtnVisible;
  const evidence = {
    scenario_id: scenarioId, role, ts: nowIso(), final_url: url, http_status: httpStatus,
    access_restricted_text: restricted, add_button_count: addBtnCount, add_button_visible: addBtnVisible,
    pass, screenshot: ss, note,
  };
  writeEvidence(scenarioId, evidence);
  form_submissions.push({ scenario_id: scenarioId, role, type: "rbac-ui", action: "navigate /dashboard/hr/employee-master", result: pass ? "pass" : "fail", evidence_ref: `evidence/${scenarioId}.json` });
  if (!pass) defects.push({ scenario_id: scenarioId, severity: "CRITICAL", desc: "crew can see Add New Employee button on employee master page", evidence: ss });
  return pass;
}

async function runApiCreateBlockCheck(page, scenarioId, role) {
  const before = await employeeCount(page);
  const payload = {
    employee_name: "RBAC Test Denied",
    first_name: "RBAC",
    last_name: "Denied",
    gender: "Male",
    date_of_birth: "1995-01-01",
    date_of_joining: "2026-04-07",
    status: "Active",
  };
  const r = await apiCall(page, "/api/frappe/api/method/hrms.api.employee_create.create_employee_direct", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const after = await employeeCount(page);
  const blocked = (r.status === 403 || r.status === 401 || (r.json && /PermissionError|permi[st]/i.test(JSON.stringify(r.json))));
  const noCreate = before !== null && after !== null && before === after;
  const pass = blocked && noCreate;

  api_mutations.push({ scenario_id: scenarioId, role, endpoint: "hrms.api.employee_create.create_employee_direct", method: "POST", status: r.status, ok: r.ok, body_head: r.bodyHead || r.error, blocked, ts: nowIso() });
  state_verification.push({ scenario_id: scenarioId, check: "employee_count_unchanged", before, after, unchanged: noCreate });
  writeEvidence(scenarioId, { scenario_id: scenarioId, role, ts: nowIso(), request: { payload }, response: r, before, after, blocked, pass });
  form_submissions.push({ scenario_id: scenarioId, role, type: "rbac-api", action: "POST create_employee_direct", result: pass ? "pass" : "fail", evidence_ref: `evidence/${scenarioId}.json` });

  if (!blocked) {
    defects.push({ scenario_id: scenarioId, severity: "CRITICAL", desc: `RBAC BROKEN: crew create_employee_direct returned ${r.status}, not 403`, evidence: `evidence/${scenarioId}.json` });
    // Capture any created employee names for Wave 2 cleanup
    if (r.json?.message?.name) orphans.push({ scenario_id: scenarioId, doctype: "Employee", name: r.json.message.name });
  }
  return pass;
}

async function runFieldSetValueCheck(page, scenarioId, role) {
  // Pick any employee (HR area_sup or an existing test employee)
  const list = await apiCall(page, '/api/frappe/api/resource/Employee?fields=["name","cell_number"]&limit_page_length=1');
  const target = list.ok ? list.json?.data?.[0] : null;
  if (!target) {
    writeEvidence(scenarioId, { scenario_id: scenarioId, role, ts: nowIso(), skipped: true, reason: "could not fetch an Employee record as crew", list });
    form_submissions.push({ scenario_id: scenarioId, role, type: "rbac-api", action: "set_value cell_number", result: "skip", evidence_ref: `evidence/${scenarioId}.json` });
    state_verification.push({ scenario_id: scenarioId, check: "target_fetch_failed", detail: "no employee visible to crew" });
    return null;
  }
  const originalPhone = target.cell_number;
  const tamper = "09999999999";
  const r = await apiCall(page, "/api/frappe/api/method/frappe.client.set_value", {
    method: "POST",
    body: JSON.stringify({ doctype: "Employee", name: target.name, fieldname: "cell_number", value: tamper }),
  });
  // Verify unchanged
  const verify = await apiCall(page, `/api/frappe/api/resource/Employee/${encodeURIComponent(target.name)}?fields=["name","cell_number"]`);
  const after = verify.ok ? verify.json?.data?.cell_number : null;
  const blocked = (r.status === 403 || r.status === 401);
  const unchanged = after === originalPhone || after !== tamper;
  const pass = blocked && unchanged;

  api_mutations.push({ scenario_id: scenarioId, role, endpoint: "frappe.client.set_value", method: "POST", target: target.name, status: r.status, blocked, ts: nowIso() });
  state_verification.push({ scenario_id: scenarioId, check: "cell_number_unchanged", target: target.name, before: originalPhone, after, unchanged });
  writeEvidence(scenarioId, { scenario_id: scenarioId, role, target, request_status: r.status, response_head: r.bodyHead, verify, blocked, unchanged, pass });
  form_submissions.push({ scenario_id: scenarioId, role, type: "rbac-api", action: "set_value Employee.cell_number", result: pass ? "pass" : "fail", evidence_ref: `evidence/${scenarioId}.json` });
  if (!pass) defects.push({ scenario_id: scenarioId, severity: "CRITICAL", desc: `Crew set_value on Employee.cell_number not blocked (status ${r.status}, after=${after})`, evidence: `evidence/${scenarioId}.json` });
  return pass;
}

async function runFinanceVisibilityCheck(page, scenarioId) {
  // Employee Master page: document add-button visibility
  const resp1 = await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => null);
  await page.waitForTimeout(1500);
  const empMasterUrl = page.url();
  const addBtn = page.getByRole("button", { name: /add new employee/i });
  const addCount = await addBtn.count().catch(() => 0);
  const addVisible = addCount > 0 ? await addBtn.first().isVisible().catch(() => false) : false;
  const ss1 = path.join(SS_DIR, `${scenarioId}_employee_master.png`);
  await page.screenshot({ path: ss1, fullPage: true }).catch(() => {});

  // Salary approval queue
  const resp2 = await page.goto(`${BASE}/dashboard/hr/payroll/sensitive-changes`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => null);
  await page.waitForTimeout(1500);
  const sensUrl = page.url();
  const sensBody = await page.locator("body").innerText().catch(() => "");
  const sensRestricted = /access restricted|forbidden|not authori[sz]ed/i.test(sensBody);
  const ss2 = path.join(SS_DIR, `${scenarioId}_sensitive_changes.png`);
  await page.screenshot({ path: ss2, fullPage: true }).catch(() => {});

  const pass = !sensRestricted; // finance should SEE sensitive-changes; add-button visibility is documented only
  writeEvidence(scenarioId, {
    scenario_id: scenarioId, role: "test.finance", ts: nowIso(),
    employee_master: { url: empMasterUrl, add_button_count: addCount, add_button_visible: addVisible, screenshot: ss1 },
    sensitive_changes: { url: sensUrl, access_restricted: sensRestricted, screenshot: ss2 },
    pass,
  });
  form_submissions.push({ scenario_id: scenarioId, role: "test.finance", type: "rbac-ui", action: "finance visibility: employee-master + sensitive-changes", result: pass ? "pass" : "fail", evidence_ref: `evidence/${scenarioId}.json` });
  state_verification.push({ scenario_id: scenarioId, check: "finance_can_see_sensitive_changes", restricted: sensRestricted });
  if (!pass) defects.push({ scenario_id: scenarioId, severity: "HIGH", desc: "finance role cannot see sensitive-changes queue", evidence: ss2 });
  return pass;
}

async function runDetailDialogCheck(page, scenarioId) {
  const resp = await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => null);
  await page.waitForTimeout(1800);
  const ss1 = path.join(SS_DIR, `${scenarioId}_landing.png`);
  await page.screenshot({ path: ss1, fullPage: true }).catch(() => {});
  // If page is restricted, that's a valid pass — crew has no access
  const bodyText = await page.locator("body").innerText().catch(() => "");
  const restricted = /access restricted|forbidden|not authori[sz]ed|permission/i.test(bodyText);
  if (restricted) {
    writeEvidence(scenarioId, { scenario_id: scenarioId, role: "test.crew1", ts: nowIso(), access_restricted: true, pass: true, screenshot: ss1, note: "page blocked at route level — implicit RBAC pass; dialog probe not applicable" });
    form_submissions.push({ scenario_id: scenarioId, role: "test.crew1", type: "rbac-ui", action: "open EmployeeDetailDialog", result: "pass", evidence_ref: `evidence/${scenarioId}.json`, note: "access-restricted at route" });
    state_verification.push({ scenario_id: scenarioId, check: "page_restricted", restricted: true });
    return true;
  }

  // Try to probe a row
  const triggers = [
    () => page.locator("table tbody tr").first().locator("td").first(),
    () => page.locator("table tbody tr").first().locator("button").first(),
    () => page.locator("table tbody tr").first().locator("a").first(),
    () => page.locator("table tbody tr").first(),
  ];
  let dialog = null;
  let openedBy = null;
  for (let i = 0; i < triggers.length; i++) {
    try {
      const t = triggers[i]();
      if ((await t.count()) === 0) continue;
      await t.click({ force: true, timeout: 3000 });
      await page.waitForTimeout(800);
      const d = page.locator('[role="dialog"]').first();
      if (await d.count() > 0 && await d.isVisible().catch(() => false)) {
        dialog = d; openedBy = `trigger_${i}`; break;
      }
    } catch {}
  }

  const ss2 = path.join(SS_DIR, `${scenarioId}_dialog.png`);
  await page.screenshot({ path: ss2, fullPage: true }).catch(() => {});

  if (!dialog) {
    // Defect: cannot open dialog; logged and skipped
    const defect = { scenario_id: scenarioId, severity: "MEDIUM", desc: "EmployeeDetailDialog trigger not reachable as crew (also a Wave 0 discovery failure for HR)", evidence: ss2 };
    defects.push(defect);
    writeEvidence(scenarioId, { scenario_id: scenarioId, role: "test.crew1", ts: nowIso(), dialog_opened: false, skipped: true, reason: "row dialog trigger not reachable", screenshots: [ss1, ss2] });
    form_submissions.push({ scenario_id: scenarioId, role: "test.crew1", type: "rbac-ui", action: "open EmployeeDetailDialog", result: "skip", evidence_ref: `evidence/${scenarioId}.json`, note: "dialog trigger not reachable" });
    state_verification.push({ scenario_id: scenarioId, check: "dialog_trigger_unreachable", reachable: false });
    return null;
  }

  // Inspect dialog
  const saveButtons = await dialog.locator("button", { hasText: /save/i }).all();
  const saveStates = [];
  for (const b of saveButtons) {
    saveStates.push({ text: (await b.innerText().catch(() => "")).trim(), disabled: await b.isDisabled().catch(() => null), visible: await b.isVisible().catch(() => null) });
  }
  const allSaveLocked = saveStates.length === 0 || saveStates.every(s => s.disabled === true || s.visible === false);

  // Compensation field inspection: look for inputs near "Compensation" / "Salary" / "Monthly"
  const compHtml = await dialog.innerHTML().catch(() => "");
  const hasCompInput = /name=["']?(monthly_rate|salary|base_salary|compensation)/i.test(compHtml);
  const compInputs = await dialog.locator('input[name*="rate" i], input[name*="salary" i], input[name*="compensation" i]').all();
  const compStates = [];
  for (const c of compInputs) {
    compStates.push({
      name: await c.getAttribute("name").catch(() => null),
      visible: await c.isVisible().catch(() => null),
      readOnly: await c.getAttribute("readonly").catch(() => null),
      disabled: await c.isDisabled().catch(() => null),
      value: await c.inputValue().catch(() => null),
    });
  }
  const compProtected = !hasCompInput || compStates.every(s => s.visible === false || s.readOnly !== null || s.disabled === true || /•|\*|hidden|masked/i.test(s.value || ""));

  const pass = allSaveLocked && compProtected;
  writeEvidence(scenarioId, {
    scenario_id: scenarioId, role: "test.crew1", ts: nowIso(),
    opened_by: openedBy, save_buttons: saveStates, compensation_inputs: compStates,
    all_save_locked: allSaveLocked, compensation_protected: compProtected, pass,
    screenshots: [ss1, ss2],
  });
  form_submissions.push({ scenario_id: scenarioId, role: "test.crew1", type: "rbac-ui", action: "EmployeeDetailDialog field lockdown", result: pass ? "pass" : "fail", evidence_ref: `evidence/${scenarioId}.json` });
  state_verification.push({ scenario_id: scenarioId, check: "dialog_fields_locked", save_locked: allSaveLocked, comp_protected: compProtected });
  if (!pass) defects.push({ scenario_id: scenarioId, severity: "CRITICAL", desc: "crew can edit/see compensation or save personal edits in EmployeeDetailDialog", evidence: ss2 });
  return pass;
}

// ─── Main ───

async function run() {
  const started = Date.now();
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  const results = {};
  try {
    // ── Crew session ──
    const crewCtx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const crewPage = await crewCtx.newPage();
    const crewLoginUrl = await loginMyBebang(crewPage, "test.crew1@bebang.ph");
    console.log("[crew login]", crewLoginUrl);

    results["EMP-CREATE-008"] = await runUiVisibilityCheck(crewPage, "EMP-CREATE-008", "test.crew1", "crew cannot see Add New Employee");
    results["EMP-RBAC-001"]   = await runUiVisibilityCheck(crewPage, "EMP-RBAC-001", "test.crew1", "crew employee-master visibility");

    results["EMP-CREATE-009"] = await runApiCreateBlockCheck(crewPage, "EMP-CREATE-009", "test.crew1");
    results["EMP-RBAC-002"]   = await runApiCreateBlockCheck(crewPage, "EMP-RBAC-002", "test.crew1");
    results["EMP-RBAC-003"]   = await runFieldSetValueCheck(crewPage, "EMP-RBAC-003", "test.crew1");
    results["EMP-RBAC-005"]   = await runDetailDialogCheck(crewPage, "EMP-RBAC-005");

    await crewCtx.close();

    // ── Finance session ──
    const finCtx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const finPage = await finCtx.newPage();
    const finLoginUrl = await loginMyBebang(finPage, "test.finance@bebang.ph");
    console.log("[finance login]", finLoginUrl);
    results["EMP-RBAC-004"] = await runFinanceVisibilityCheck(finPage, "EMP-RBAC-004");
    await finCtx.close();

  } catch (e) {
    console.error("FATAL", e);
    defects.push({ scenario_id: "LANE_E", severity: "FATAL", desc: String(e).substring(0, 600) });
  } finally {
    await browser.close();
  }

  // Write artifacts
  fs.writeFileSync(path.join(OUT_DIR, "form_submissions.json"), JSON.stringify(form_submissions, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "api_mutations.json"), JSON.stringify(api_mutations, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "state_verification.json"), JSON.stringify(state_verification, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "EMP_STATE.json"), JSON.stringify({ created: [], updated: [], deleted: [], note: "Lane E creates nothing by design" }, null, 2));

  const summary = {
    lane: "E",
    topic: "RBAC",
    scenarios: Object.keys(results).length,
    results,
    defects_count: defects.length,
    runtime_sec: Math.round((Date.now() - started) / 1000),
    ts: nowIso(),
  };
  fs.writeFileSync(path.join(OUT_DIR, "LANE_STATE.json"), JSON.stringify(summary, null, 2));

  // SUMMARY.md
  const lines = [];
  lines.push("# Lane E — RBAC Summary");
  lines.push("");
  lines.push(`Run: ${nowIso()}  |  Runtime: ${summary.runtime_sec}s`);
  lines.push("");
  lines.push("| Scenario | Role | Result |");
  lines.push("|---|---|---|");
  for (const [id, v] of Object.entries(results)) {
    const label = v === true ? "PASS" : v === false ? "FAIL" : v === null ? "SKIP" : "UNKNOWN";
    lines.push(`| ${id} | ${id === "EMP-RBAC-004" ? "test.finance" : "test.crew1"} | ${label} |`);
  }
  lines.push("");
  lines.push(`Defects: ${defects.length}`);
  if (defects.length) {
    for (const d of defects) lines.push(`- [${d.severity}] ${d.scenario_id}: ${d.desc}`);
  }
  fs.writeFileSync(path.join(OUT_DIR, "SUMMARY.md"), lines.join("\n"));

  // DEFECTS.csv
  const defHeader = "scenario_id,severity,description,evidence";
  const defRows = defects.map(d => [d.scenario_id, d.severity, (d.desc || "").replace(/,/g, ";"), d.evidence || ""].join(","));
  fs.writeFileSync(path.join(OUT_DIR, "DEFECTS.csv"), [defHeader, ...defRows].join("\n"));

  // ORPHANS.csv (only if anything was unexpectedly created)
  const orpHeader = "scenario_id,doctype,name";
  const orpRows = orphans.map(o => [o.scenario_id, o.doctype, o.name].join(","));
  fs.writeFileSync(path.join(OUT_DIR, "ORPHANS.csv"), [orpHeader, ...orpRows].join("\n"));

  console.log("\n=== Lane E Complete ===");
  console.log(JSON.stringify(summary, null, 2));
}

run().catch(e => { console.error(e); process.exit(1); });
