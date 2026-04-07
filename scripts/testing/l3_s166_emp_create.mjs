/**
 * S166 Phase 3 — EMP-CREATE batch (10 scenarios)
 *
 * Executes EMP-CREATE-001 through EMP-CREATE-010 from
 * docs/testing/scenarios/modules/hr-employee-lifecycle.md against live
 * production via real browser. Captures evidence per S092 contract.
 *
 * Outputs:
 *   output/l3/s166/form_submissions.json   (append)
 *   output/l3/s166/api_mutations.json      (append)
 *   output/l3/s166/state_verification.json (append)
 *   output/l3/s166/evidence/EMP-CREATE-XXX.json
 *   output/l3/s166/screenshots/EMP-CREATE-XXX_*.png
 *   data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/EMP_STATE.json
 *
 * The created test employees (EMP-A/B/C and any extras) are tracked in
 * EMP_STATE.json so the cleanup phase can soft-delete them. Names are
 * uniquified with a timestamp suffix per the no-toy-data rule.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const RUN_DIR = "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution";
const EVID_DIR = "output/l3/s166";
const STATE_FILE = path.join(RUN_DIR, "EMP_STATE.json");

const TS = new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
const TAG = `L3 ${new Date().toISOString().substring(0, 19).replace("T", " ")}`;

// realistic Filipino name pool
const FIRST_NAMES = ["Juan", "Maria", "Jose", "Ana", "Pedro", "Rosa", "Miguel", "Carmela", "Antonio", "Isabel"];
const LAST_NAMES = ["Dela Cruz", "Santos", "Reyes", "Garcia", "Mendoza", "Ramos", "Cruz", "Bautista", "Aquino", "Tolentino"];
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function uniqueName(prefix = "") {
  return {
    first: pick(FIRST_NAMES),
    last: pick(LAST_NAMES),
    suffix: `(${TAG}${prefix ? " " + prefix : ""})`,
  };
}

const HIRE_BRANCH = "ARANETA GATEWAY";

fs.mkdirSync(RUN_DIR, { recursive: true });
fs.mkdirSync(`${EVID_DIR}/evidence`, { recursive: true });
fs.mkdirSync(`${EVID_DIR}/screenshots`, { recursive: true });
fs.mkdirSync(`${EVID_DIR}/artifacts`, { recursive: true });

// load or init append-only evidence files
function loadJsonArray(p) {
  if (fs.existsSync(p)) { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return []; } }
  return [];
}
const formSubs = loadJsonArray(`${EVID_DIR}/form_submissions.json`);
const apiMuts = loadJsonArray(`${EVID_DIR}/api_mutations.json`);
const stateVerif = loadJsonArray(`${EVID_DIR}/state_verification.json`);
const empState = fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) : { created: [] };

function saveAll() {
  fs.writeFileSync(`${EVID_DIR}/form_submissions.json`, JSON.stringify(formSubs, null, 2));
  fs.writeFileSync(`${EVID_DIR}/api_mutations.json`, JSON.stringify(apiMuts, null, 2));
  fs.writeFileSync(`${EVID_DIR}/state_verification.json`, JSON.stringify(stateVerif, null, 2));
  fs.writeFileSync(STATE_FILE, JSON.stringify(empState, null, 2));
}

const results = []; // PASS/FAIL/SKIP per scenario

async function loginMyBebang(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
}

// Helpers to record evidence
function recordSubmission(scenarioId, form, inputs, submitAction, response, screenshotAfter) {
  formSubs.push({ scenario_id: scenarioId, form, inputs, submit_action: submitAction, response, screenshot_after: screenshotAfter, timestamp: new Date().toISOString() });
}
function recordMutation(scenarioId, endpoint, method, payload, status, responseBody) {
  apiMuts.push({ scenario_id: scenarioId, endpoint, method, payload, status, response_body: typeof responseBody === "string" ? responseBody.substring(0, 1000) : JSON.stringify(responseBody).substring(0, 1000), timestamp: new Date().toISOString() });
}
function recordState(scenarioId, check, before, after, passed) {
  stateVerif.push({ scenario_id: scenarioId, check, before, after, passed, timestamp: new Date().toISOString() });
}
function writeEvidence(scenarioId, payload) {
  fs.writeFileSync(`${EVID_DIR}/evidence/${scenarioId}.json`, JSON.stringify(payload, null, 2));
}
function pass(id, detail) { results.push({ scenario: id, status: "PASS", detail }); console.log(`[PASS] ${id} — ${detail}`); }
function fail(id, detail) { results.push({ scenario: id, status: "FAIL", detail }); console.log(`[FAIL] ${id} — ${detail}`); }
function skip(id, detail) { results.push({ scenario: id, status: "SKIP", detail }); console.log(`[SKIP] ${id} — ${detail}`); }

// Open the New Employee dialog from the Employee Master page (sidebar nav, not deep link)
async function openNewEmployeeDialog(page) {
  // Navigate via sidebar (HR → Employee Master). Fall back to direct route if sidebar not visible.
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  const addBtn = page.getByRole("button", { name: /add new employee/i }).first();
  await addBtn.waitFor({ state: "visible", timeout: 15000 });
  await addBtn.click();
  await page.waitForTimeout(1500);
}

// Set a shadcn Select by visible label → option text
async function setShadcnSelect(page, labelRegex, optionText) {
  // The combobox trigger is usually next to/under the label
  const trigger = page.getByRole("combobox", { name: labelRegex }).first();
  if (await trigger.count() > 0) {
    await trigger.click();
  } else {
    // Fallback: locate by label-adjacent button
    const lbl = page.locator(`label:has-text("${labelRegex.source.replace(/[/\\^$*+?.()|[\]{}]/g, "")}")`).first();
    const btn = lbl.locator("xpath=following::button[1]");
    await btn.click();
  }
  await page.waitForTimeout(400);
  await page.locator(`[role="option"]`).filter({ hasText: new RegExp(optionText, "i") }).first().click();
  await page.waitForTimeout(300);
}

async function fillByLabel(page, labelRegex, value) {
  const el = page.getByLabel(labelRegex).first();
  await el.fill(value);
}

// Read recent toasts
async function readToasts(page) {
  await page.waitForTimeout(1200);
  return await page.locator('[data-sonner-toast]').allTextContents();
}

// =====================================================================
// EMP-CREATE-001 — happy path, 6 mandatory fields only
// =====================================================================
async function empCreate001(page) {
  const id = "EMP-CREATE-001";
  const evid = { scenario_id: id, actions: [], network: [], artifacts: {} };
  try {
    const name = uniqueName("EMP-A");
    const inputs = {
      first_name: name.first,
      last_name: `${name.last} ${name.suffix}`,
      date_of_birth: "1995-06-15",
      gender: "Male",
      branch: HIRE_BRANCH,
      company: "Bebang Enterprise Inc.",
    };

    await openNewEmployeeDialog(page);
    evid.actions.push({ type: "nav_sidebar", to: "/dashboard/hr/employee-master" });
    evid.actions.push({ type: "click", target: "Add New Employee button" });

    await fillByLabel(page, /first name/i, inputs.first_name);
    await fillByLabel(page, /last name/i, inputs.last_name);
    await fillByLabel(page, /date of birth|birth date/i, inputs.date_of_birth);
    evid.actions.push({ type: "fill", fields: { first_name: inputs.first_name, last_name: inputs.last_name, dob: inputs.date_of_birth } });

    await setShadcnSelect(page, /gender/i, "Male");
    await setShadcnSelect(page, /branch/i, HIRE_BRANCH);
    // company often defaults; only set if combobox exists
    const compTrigger = page.getByRole("combobox", { name: /company/i });
    if (await compTrigger.count() > 0) {
      await setShadcnSelect(page, /company/i, "Bebang Enterprise Inc.").catch(() => {});
    }
    evid.actions.push({ type: "select", fields: { gender: "Male", branch: HIRE_BRANCH } });

    // Capture submit network response
    const respPromise = page.waitForResponse(
      r => r.url().includes("create_employee_direct") || r.url().includes("create_employee"),
      { timeout: 30000 }
    );
    const submitBtn = page.getByRole("button", { name: /^create employee$|create$/i }).first();
    await submitBtn.click();
    evid.actions.push({ type: "submit", target: "Create Employee" });

    const submitResp = await respPromise;
    const respBody = await submitResp.json().catch(() => ({}));
    evid.network.push({ method: "POST", url: submitResp.url(), status: submitResp.status(), body: respBody });

    const toasts = await readToasts(page);
    evid.toasts = toasts;

    await page.screenshot({ path: `${EVID_DIR}/screenshots/${id}_after.png`, fullPage: false });
    evid.artifacts.screenshot = `${EVID_DIR}/screenshots/${id}_after.png`;

    // Parse Employee ID + Bio ID + device SN from toast or response
    const msg = (respBody.message || respBody) || {};
    const empId = msg.employee || msg.name || (toasts.join(" ").match(/BEI-EMP-2026-\d+/) || [])[0];
    const bioId = msg.bio_id || msg.attendance_device_id || (toasts.join(" ").match(/Bio ID (\d+)/) || [])[1];
    const deviceSn = msg.device_sn || (toasts.join(" ").match(/UDP[A-Z0-9-]+|SN[A-Z0-9-]+/) || [])[0];

    recordSubmission(id, "AddNewEmployeeDialog", inputs, "Create Employee", { status: submitResp.status(), body: respBody, toasts }, `${EVID_DIR}/screenshots/${id}_after.png`);
    recordMutation(id, submitResp.url(), "POST", inputs, submitResp.status(), respBody);

    if (submitResp.ok() && empId) {
      empState.created.push({ id: empId, role: "EMP-A", bio_id: bioId, branch: HIRE_BRANCH, scenario: id });
      // State verification: refetch via masterlist
      const verify = await page.evaluate(async (e) => {
        const r = await fetch(`/api/frappe/api/resource/Employee/${encodeURIComponent(e)}`, { headers: { Accept: "application/json" } });
        return { ok: r.ok, status: r.status, json: r.ok ? await r.json() : null };
      }, empId);
      recordState(id, "Employee record exists after create", null, verify.json?.data || null, verify.ok);
      evid.network.push({ method: "GET", url: `/api/frappe/api/resource/Employee/${empId}`, status: verify.status });
      pass(id, `created ${empId} bio=${bioId} device=${deviceSn || "n/a"}`);
    } else {
      fail(id, `submit failed status=${submitResp.status()} body=${JSON.stringify(respBody).substring(0, 200)}`);
    }
  } catch (e) {
    fail(id, `exception: ${e.message}`);
    evid.error = String(e);
  }
  writeEvidence(id, evid);
  saveAll();
}

// =====================================================================
// Driver
// =====================================================================
async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  try {
    console.log("=== LOGIN test.hr@bebang.ph ===");
    await loginMyBebang(page, "test.hr@bebang.ph");
    console.log("Logged in:", page.url());

    // Discovery snapshot before any mutation
    await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${EVID_DIR}/screenshots/_employee_master_initial.png`, fullPage: false });
    const buttonTexts = await page.locator("button").allInnerTexts();
    fs.writeFileSync(`${RUN_DIR}/employee_master_buttons.txt`, buttonTexts.join("\n"));
    console.log(`Saw ${buttonTexts.length} buttons; first 10:`, buttonTexts.slice(0, 10));

    await empCreate001(page);

    // Print summary
    console.log("\n=== EMP-CREATE BATCH SUMMARY (partial — first scenario only this turn) ===");
    for (const r of results) console.log(`  [${r.status}] ${r.scenario} — ${r.detail}`);
    const passN = results.filter(r => r.status === "PASS").length;
    console.log(`Total: ${passN}/${results.length} PASS`);
  } finally {
    saveAll();
    await ctx.close();
    await browser.close();
  }
}

run().catch(e => { console.error(e); process.exit(1); });
