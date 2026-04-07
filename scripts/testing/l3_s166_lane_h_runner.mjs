/**
 * S166 Lane H — EMP-CREATE-004 NO_DEVICE_FOR_BRANCH
 *
 * Discovers an unmapped branch by trial-and-error and captures evidence for the
 * "no biometric device mapped to branch" code path of the Add New Employee flow.
 * Every employee created during discovery (mapped or unmapped) is soft-deleted
 * in the finally block via the set_value API escape hatch.
 *
 * Output: F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/lane_h/
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const EMAIL = "test.hr@bebang.ph";
const PASSWORD = "BeiTest2026!";
const COMPANY = "Bebang Enterprise Inc.";
const LANE_DIR = "output/l3/s166/lanes/lane_h";
const SHOT_DIR = path.join(LANE_DIR, "screenshots");
const EVID_DIR = path.join(LANE_DIR, "evidence");
const ART_DIR = path.join(LANE_DIR, "artifacts");

// Candidate branches most likely to lack a biometric device (offices,
// commissary sub-units, null-valued rows). Tried in order. Max 5.
const CANDIDATE_BRANCHES = [
  "BRITTANY OFFICE",
  "CAPITAL HOUSE",
  "SHAW COMMISSARY - Logistics",
  "SHAW COMMISSARY - RD QC",
  "SHAW COMMISSARY - Production",
];

const FIRST_NAMES = ["Juan", "Maria", "Pedro", "Ana"];
const LAST_NAME_BASE = "Dela Cruz";

function ts() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  // HH:MM:SS in PHT (UTC+8)
  const pht = new Date(d.getTime() + 8 * 3600_000);
  return `${p(pht.getUTCHours())}:${p(pht.getUTCMinutes())}:${p(pht.getUTCSeconds())}`;
}

const RUN_START = Date.now();

// --- State containers -----------------------------------------------
const form_submissions = [];
const api_mutations = [];
const state_verification = [];
const created_employees = []; // { name, bio_id, branch, candidate_idx, toast, api_response, cleanup_status }
const defects = [];
const attemptLogs = [];

function log(...a) { console.log("[lane_h]", ...a); }

// --- Auth -----------------------------------------------------------
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
  log("logged in:", page.url());
}

// --- Dialog helpers -------------------------------------------------
async function openDialog(page) {
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  let btn = page.getByRole("button", { name: /add new employee/i }).first();
  if (await btn.count() === 0) {
    const buttons = await page.locator("button").all();
    for (const b of buttons) {
      const t = (await b.innerText().catch(() => "")).toLowerCase();
      if (t.includes("add") && t.includes("employee")) { btn = b; break; }
    }
  }
  await btn.waitFor({ state: "visible", timeout: 15000 });
  await btn.click();
  await page.waitForTimeout(1500);
  await page.locator('[role="dialog"]').first().waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(600);
}

async function closeDialogIfOpen(page) {
  const cnt = await page.locator('[role="dialog"]').count();
  if (cnt > 0) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    if ((await page.locator('[role="dialog"]').count()) > 0) {
      const cancel = page.getByRole("button", { name: /^cancel$/i }).first();
      if (await cancel.count() > 0) await cancel.click().catch(() => {});
      await page.waitForTimeout(400);
    }
  }
}

async function popoverOpen(page) {
  const ct = await page.locator('[role="listbox"], [cmdk-list], [data-radix-popper-content-wrapper]').count();
  return ct > 0;
}

async function findComboboxTriggerByLabel(page, labelRegex) {
  const dialog = page.locator('[role="dialog"]').first();
  const combos = await dialog.locator('button[role="combobox"]').all();
  for (let i = 0; i < combos.length; i++) {
    const c = combos[i];
    const match = await c.evaluate((el, rxSrc) => {
      const rx = new RegExp(rxSrc, "i");
      let p = el.parentElement, nearest = "";
      for (let k = 0; k < 5 && p; k++) {
        const lbl = p.querySelector("label");
        if (lbl) { nearest = lbl.innerText; break; }
        p = p.parentElement;
      }
      return rx.test(nearest || "") || rx.test(el.innerText || "");
    }, labelRegex.source);
    if (match) return c;
  }
  return null;
}

async function selectCombobox(page, labelRegex, optionText, { typeFilter = true } = {}) {
  const trigger = await findComboboxTriggerByLabel(page, labelRegex);
  if (!trigger) throw new Error(`combobox not found for ${labelRegex}`);
  // Wait until not disabled (some combos start as "Loading…")
  for (let i = 0; i < 20; i++) {
    const dis = await trigger.isDisabled().catch(() => false);
    if (!dis) break;
    await page.waitForTimeout(300);
  }
  await trigger.click({ force: true });
  await page.waitForTimeout(500);
  if (!(await popoverOpen(page))) {
    // retry once
    await trigger.click({ force: true });
    await page.waitForTimeout(500);
  }
  // Type-to-filter when combo is a cmdk command (branch/company/dept/designation)
  if (typeFilter) {
    const cmdInput = page.locator('[cmdk-input], input[role="combobox"], [role="dialog"] input[type="text"]').last();
    if (await cmdInput.count() > 0) {
      // use the most recently-appeared cmdk input
      const popInput = page.locator('[cmdk-input]').last();
      if (await popInput.count() > 0) {
        await popInput.fill(optionText).catch(() => {});
        await page.waitForTimeout(400);
      }
    }
  }
  const opt = page.locator('[role="option"]').filter({ hasText: new RegExp(`^\\s*${optionText.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}\\s*$`, "i") }).first();
  let clicked = false;
  if (await opt.count() > 0) {
    await opt.click({ timeout: 3000 }).catch(() => {});
    clicked = true;
  } else {
    const opt2 = page.locator('[role="option"]').filter({ hasText: new RegExp(optionText.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&"), "i") }).first();
    if (await opt2.count() > 0) {
      await opt2.click({ timeout: 3000 }).catch(() => {});
      clicked = true;
    }
  }
  await page.waitForTimeout(400);
  const trigText = (await trigger.innerText().catch(() => "")).trim();
  const ok = clicked && new RegExp(optionText.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&"), "i").test(trigText);
  if (!ok) throw new Error(`combobox ${labelRegex} failed to set "${optionText}" (trigger="${trigText}")`);
  return trigText;
}

// --- Attempt a single create --------------------------------------
async function attemptCreate(page, branch, candidateIdx) {
  const firstName = FIRST_NAMES[candidateIdx % FIRST_NAMES.length];
  const suffix = `(L3 2026-04-07 ${ts()} NO_DEV)`;
  const lastName = `${LAST_NAME_BASE} ${suffix}`;
  const fullName = `${firstName} ${lastName}`;

  const attemptRecord = {
    candidate_idx: candidateIdx,
    branch,
    first_name: firstName,
    last_name: lastName,
    started_at: new Date().toISOString(),
    steps: [],
    toast_text: null,
    api_response: null,
    api_status: null,
    created_employee_name: null,
    outcome: null, // NO_DEVICE | MAPPED | FAILED
  };

  // Install response interceptor for create_employee_direct
  let createdResponse = null;
  const responseHandler = async (resp) => {
    try {
      const url = resp.url();
      if (/create_employee_direct/i.test(url) || /create_employee/i.test(url)) {
        const status = resp.status();
        let json = null;
        try { json = await resp.json(); } catch {}
        createdResponse = { url, status, json };
      }
    } catch {}
  };
  page.on("response", responseHandler);

  try {
    await openDialog(page);
    attemptRecord.steps.push("dialog opened");

    // Screenshot pre
    const preShot = path.join(SHOT_DIR, `EMP-CREATE-004_candidate${candidateIdx}_${branch.replace(/[^a-z0-9]+/gi, "_")}_pre.png`);
    await page.screenshot({ path: preShot, fullPage: false });
    attemptRecord.steps.push(`pre screenshot: ${preShot}`);

    // Fill text fields
    const dialog = page.locator('[role="dialog"]').first();
    await dialog.locator('#first_name').fill(firstName);
    await dialog.locator('#last_name').fill(lastName);
    await dialog.locator('#date_of_birth').fill("1995-06-15");
    attemptRecord.steps.push("text fields filled");

    // Select comboboxes
    await selectCombobox(page, /^gender/i, "Male", { typeFilter: false });
    attemptRecord.steps.push("gender=Male");

    await selectCombobox(page, /^company/i, COMPANY);
    attemptRecord.steps.push(`company=${COMPANY}`);

    await selectCombobox(page, /^branch/i, branch);
    attemptRecord.steps.push(`branch=${branch}`);

    // Department, Designation, Employment Type — pick first viable options.
    // These are required to enable the Create button; exact values don't affect NO_DEVICE path.
    try {
      await selectCombobox(page, /^department/i, "Accounts - BSC");
      attemptRecord.steps.push("department=Accounts - BSC");
    } catch (e) {
      // fallback: pick any first option
      const trig = await findComboboxTriggerByLabel(page, /^department/i);
      if (trig) {
        await trig.click({ force: true });
        await page.waitForTimeout(400);
        const first = page.locator('[role="option"]').first();
        if (await first.count() > 0) { await first.click(); attemptRecord.steps.push("department=<first>"); }
      }
    }

    try {
      await selectCombobox(page, /^designation/i, "Cashier");
      attemptRecord.steps.push("designation=Cashier");
    } catch (e) {
      const trig = await findComboboxTriggerByLabel(page, /^designation/i);
      if (trig) {
        await trig.click({ force: true });
        await page.waitForTimeout(400);
        const first = page.locator('[role="option"]').first();
        if (await first.count() > 0) { await first.click(); attemptRecord.steps.push("designation=<first>"); }
      }
    }

    try {
      await selectCombobox(page, /employment type/i, "Regular", { typeFilter: false });
      attemptRecord.steps.push("employment_type=Regular");
    } catch (e) {
      const trig = await findComboboxTriggerByLabel(page, /employment type/i);
      if (trig) {
        await trig.click({ force: true });
        await page.waitForTimeout(400);
        const first = page.locator('[role="option"]').first();
        if (await first.count() > 0) { await first.click(); attemptRecord.steps.push("employment_type=<first>"); }
      }
    }

    // Submit
    const submitBtn = dialog.getByRole("button", { name: /^create employee$/i });
    // Wait until enabled
    for (let i = 0; i < 20; i++) {
      const dis = await submitBtn.isDisabled().catch(() => true);
      if (!dis) break;
      await page.waitForTimeout(300);
    }
    const disabledAtSubmit = await submitBtn.isDisabled().catch(() => true);
    attemptRecord.steps.push(`submit disabled=${disabledAtSubmit}`);
    if (disabledAtSubmit) {
      attemptRecord.outcome = "FAILED";
      attemptRecord.error = "submit button still disabled after filling all fields";
      return attemptRecord;
    }
    await submitBtn.click();
    attemptRecord.steps.push("submit clicked");

    // Wait for toast + response
    await page.waitForTimeout(3500);

    // Read toast
    const toastLoc = page.locator('[data-sonner-toast], [role="status"]').last();
    let toastText = "";
    if (await toastLoc.count() > 0) {
      toastText = (await toastLoc.innerText().catch(() => "")).trim();
    }
    attemptRecord.toast_text = toastText;
    attemptRecord.steps.push(`toast="${toastText.substring(0, 200)}"`);

    // Wait a bit more for the response event
    await page.waitForTimeout(1000);
    attemptRecord.api_response = createdResponse?.json || null;
    attemptRecord.api_status = createdResponse?.status || null;

    // Find created employee name
    let empName = null;
    const resp = createdResponse?.json;
    if (resp) {
      empName = resp?.message?.employee?.name || resp?.message?.name || resp?.data?.name || resp?.employee?.name || null;
    }
    attemptRecord.created_employee_name = empName;

    // Post screenshot
    const postShot = path.join(SHOT_DIR, `EMP-CREATE-004_candidate${candidateIdx}_${branch.replace(/[^a-z0-9]+/gi, "_")}_post.png`);
    await page.screenshot({ path: postShot, fullPage: false });
    attemptRecord.steps.push(`post screenshot: ${postShot}`);

    // Classify outcome
    const toastLower = toastText.toLowerCase();
    const reason = resp?.message?.adms_enrollment?.reason || resp?.adms_enrollment?.reason || resp?.message?.enrollment?.reason || null;
    attemptRecord.adms_reason = reason;

    const noDeviceToast = /no\s+(biometric|bio\s+id)?\s*device\s+mapped/i.test(toastText) ||
                         /no device/i.test(toastText) ||
                         /enroll manually/i.test(toastText) ||
                         reason === "NO_DEVICE_FOR_BRANCH";
    const mappedToast = /enrolled/i.test(toastText) || /udp/i.test(toastText) || /device ip/i.test(toastLower);

    if (noDeviceToast) attemptRecord.outcome = "NO_DEVICE";
    else if (empName && mappedToast) attemptRecord.outcome = "MAPPED";
    else if (empName) attemptRecord.outcome = "CREATED_UNKNOWN";
    else attemptRecord.outcome = "FAILED";

    // Track created employee for cleanup
    if (empName) {
      created_employees.push({
        name: empName,
        bio_id: resp?.message?.employee?.attendance_device_id || resp?.message?.attendance_device_id || null,
        branch,
        full_name: fullName,
        candidate_idx: candidateIdx,
        outcome: attemptRecord.outcome,
        toast: toastText,
        cleanup_status: "pending",
      });
    }

    form_submissions.push({
      scenario: "EMP-CREATE-004",
      candidate_idx: candidateIdx,
      branch,
      payload: {
        first_name: firstName,
        last_name: lastName,
        date_of_birth: "1995-06-15",
        gender: "Male",
        company: COMPANY,
        branch,
      },
      outcome: attemptRecord.outcome,
      toast: toastText,
      created_employee_name: empName,
      api_status: attemptRecord.api_status,
      submitted_at: new Date().toISOString(),
    });

    if (createdResponse) {
      api_mutations.push({
        type: "create_employee",
        url: createdResponse.url,
        status: createdResponse.status,
        response: createdResponse.json,
        candidate_idx: candidateIdx,
      });
    }

    // Close dialog if still open
    await closeDialogIfOpen(page);
    return attemptRecord;
  } catch (e) {
    attemptRecord.outcome = "FAILED";
    attemptRecord.error = String(e).substring(0, 500);
    log(`  ERROR on candidate ${candidateIdx} (${branch}):`, attemptRecord.error);
    // Post screenshot even on error
    try {
      const errShot = path.join(SHOT_DIR, `EMP-CREATE-004_candidate${candidateIdx}_${branch.replace(/[^a-z0-9]+/gi, "_")}_error.png`);
      await page.screenshot({ path: errShot, fullPage: false });
    } catch {}
    await closeDialogIfOpen(page);
    return attemptRecord;
  } finally {
    page.off("response", responseHandler);
  }
}

// --- Cleanup --------------------------------------------------------
async function softDeleteViaApi(page, empName) {
  // Two set_value calls: status=Left, relieving_date=today
  const today = new Date().toISOString().slice(0, 10);
  const calls = [
    { fieldname: "status", value: "Left" },
    { fieldname: "relieving_date", value: today },
  ];
  const results = [];
  for (const c of calls) {
    const r = await page.evaluate(async ({ empName, fieldname, value }) => {
      const body = new URLSearchParams();
      body.set("doctype", "Employee");
      body.set("name", empName);
      body.set("fieldname", fieldname);
      body.set("value", value);
      const resp = await fetch("/api/frappe/api/method/frappe.client.set_value", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Frappe-CSRF-Token": (window.csrf_token || "") },
        body: body.toString(),
      });
      const text = await resp.text();
      let json = null; try { json = JSON.parse(text); } catch {}
      return { status: resp.status, ok: resp.ok, json, bodyHead: text.substring(0, 400) };
    }, { empName, fieldname: c.fieldname, value: c.value });
    results.push({ field: c.fieldname, value: c.value, ...r });
    api_mutations.push({
      type: "soft_delete_set_value",
      employee: empName,
      field: c.fieldname,
      value: c.value,
      status: r.status,
      ok: r.ok,
      response: r.json || r.bodyHead,
    });
  }
  return results;
}

async function verifyNoActiveOrphans(page) {
  const r = await page.evaluate(async () => {
    const url = "/api/frappe/api/resource/Employee?filters=" + encodeURIComponent(JSON.stringify([["employee_name", "like", "%NO_DEV%"], ["status", "=", "Active"]])) + "&fields=" + encodeURIComponent(JSON.stringify(["name", "employee_name", "status"])) + "&limit_page_length=50";
    const resp = await fetch(url, { headers: { Accept: "application/json" } });
    const text = await resp.text();
    let json = null; try { json = JSON.parse(text); } catch {}
    return { status: resp.status, json, bodyHead: text.substring(0, 500) };
  });
  return r;
}

// --- Main -----------------------------------------------------------
async function run() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  fs.mkdirSync(EVID_DIR, { recursive: true });
  fs.mkdirSync(ART_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  const ctx = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    recordVideo: undefined,
  });
  await ctx.tracing.start({ screenshots: true, snapshots: true, sources: false });
  const page = await ctx.newPage();

  let finalOutcome = "PRECONDITION_BLOCKED";
  let unmappedBranch = null;
  let winningAttempt = null;
  let fatal = null;

  try {
    await loginMyBebang(page);

    for (let i = 0; i < CANDIDATE_BRANCHES.length; i++) {
      const branch = CANDIDATE_BRANCHES[i];
      log(`\n=== candidate ${i}: ${branch} ===`);
      const rec = await attemptCreate(page, branch, i);
      attemptLogs.push(rec);
      log(`  outcome=${rec.outcome} toast="${(rec.toast_text || "").substring(0, 120)}"`);

      if (rec.outcome === "NO_DEVICE") {
        finalOutcome = "PASS";
        unmappedBranch = branch;
        winningAttempt = rec;
        break;
      }
      // Otherwise continue trying other candidates (MAPPED employees stay on cleanup list).
    }
  } catch (e) {
    fatal = String(e);
    log("FATAL:", e);
  } finally {
    // --- CLEANUP (binding) ---
    log("\n=== cleanup: soft-deleting all created test employees ===");
    try {
      for (const emp of created_employees) {
        try {
          const results = await softDeleteViaApi(page, emp.name);
          const allOk = results.every((r) => r.ok);
          emp.cleanup_status = allOk ? "deleted" : "partial_fail";
          log(`  ${emp.name}: ${emp.cleanup_status}`);
        } catch (e) {
          emp.cleanup_status = `error: ${String(e).substring(0, 200)}`;
          log(`  ${emp.name}: cleanup ERROR ${emp.cleanup_status}`);
        }
      }

      // Verify no orphans
      const orphanCheck = await verifyNoActiveOrphans(page);
      const orphanRows = orphanCheck?.json?.data || [];
      state_verification.push({
        check: "no_active_NO_DEV_orphans",
        status: orphanRows.length === 0 ? "PASS" : "FAIL",
        count: orphanRows.length,
        orphans: orphanRows,
      });

      // Write ORPHANS.csv
      const orphanLines = ["name,employee_name,status,reason"];
      for (const o of orphanRows) {
        orphanLines.push(`${o.name},"${(o.employee_name || "").replace(/"/g, '""')}",${o.status},active_after_cleanup`);
      }
      for (const emp of created_employees) {
        if (emp.cleanup_status !== "deleted") {
          orphanLines.push(`${emp.name},"${emp.full_name}",?,${emp.cleanup_status}`);
        }
      }
      fs.writeFileSync(path.join(LANE_DIR, "ORPHANS.csv"), orphanLines.join("\n"));
    } catch (e) {
      log("cleanup fatal:", e);
      defects.push({ scenario: "EMP-CREATE-004", severity: "high", area: "cleanup", description: String(e).substring(0, 300) });
    }

    try { await ctx.tracing.stop({ path: path.join(ART_DIR, "EMP-CREATE-004.trace.zip") }); } catch {}
    await ctx.close();
    await browser.close();
  }

  // --- Write evidence files ---
  fs.writeFileSync(path.join(LANE_DIR, "form_submissions.json"), JSON.stringify(form_submissions, null, 2));
  fs.writeFileSync(path.join(LANE_DIR, "api_mutations.json"), JSON.stringify(api_mutations, null, 2));
  fs.writeFileSync(path.join(LANE_DIR, "state_verification.json"), JSON.stringify(state_verification, null, 2));
  fs.writeFileSync(path.join(LANE_DIR, "EMP_STATE.json"), JSON.stringify({ created_employees }, null, 2));
  fs.writeFileSync(path.join(EVID_DIR, "EMP-CREATE-004.json"), JSON.stringify({
    scenario: "EMP-CREATE-004",
    final_outcome: finalOutcome,
    unmapped_branch: unmappedBranch,
    candidates_tried: CANDIDATE_BRANCHES.slice(0, attemptLogs.length),
    attempts: attemptLogs,
    winning_attempt: winningAttempt,
    fatal,
  }, null, 2));

  // DEFECTS.csv
  const defectLines = ["scenario,severity,area,description"];
  for (const d of defects) defectLines.push(`${d.scenario},${d.severity},${d.area},"${d.description.replace(/"/g, '""')}"`);
  fs.writeFileSync(path.join(LANE_DIR, "DEFECTS.csv"), defectLines.join("\n"));

  // LANE_STATE.json
  const laneState = {
    lane: "H",
    scenarios: ["EMP-CREATE-004"],
    final_outcome: finalOutcome,
    unmapped_branch: unmappedBranch,
    candidates_tried: attemptLogs.length,
    employees_created: created_employees.length,
    employees_cleaned: created_employees.filter((e) => e.cleanup_status === "deleted").length,
    runtime_ms: Date.now() - RUN_START,
    fatal,
  };
  fs.writeFileSync(path.join(LANE_DIR, "LANE_STATE.json"), JSON.stringify(laneState, null, 2));

  // SUMMARY.md
  const summary = [];
  summary.push("# S166 Lane H — EMP-CREATE-004 Summary");
  summary.push("");
  summary.push(`**Run:** ${new Date().toISOString()}`);
  summary.push(`**Final outcome:** ${finalOutcome}`);
  summary.push(`**Unmapped branch discovered:** ${unmappedBranch || "(none found)"}`);
  summary.push(`**Candidates tried:** ${attemptLogs.length} / ${CANDIDATE_BRANCHES.length}`);
  summary.push(`**Employees created (total, incl. trial-and-error):** ${created_employees.length}`);
  summary.push(`**Employees soft-deleted:** ${created_employees.filter((e) => e.cleanup_status === "deleted").length}`);
  summary.push(`**Runtime:** ${((Date.now() - RUN_START) / 1000).toFixed(1)}s`);
  summary.push("");
  summary.push("## Attempts");
  summary.push("");
  summary.push("| # | Branch | Outcome | Toast | API Reason |");
  summary.push("|---|--------|---------|-------|------------|");
  for (let i = 0; i < attemptLogs.length; i++) {
    const a = attemptLogs[i];
    const toast = (a.toast_text || "").replace(/\|/g, "/").substring(0, 80);
    summary.push(`| ${i} | ${a.branch} | ${a.outcome} | ${toast} | ${a.adms_reason || ""} |`);
  }
  summary.push("");
  if (winningAttempt) {
    summary.push("## Winning Attempt Evidence");
    summary.push("");
    summary.push(`- **Branch:** ${unmappedBranch}`);
    summary.push(`- **Toast:** \`${(winningAttempt.toast_text || "").substring(0, 300)}\``);
    summary.push(`- **API reason:** \`${winningAttempt.adms_reason || "(not found in response)"}\``);
    summary.push(`- **Employee created:** ${winningAttempt.created_employee_name || "(unknown)"}`);
  } else {
    summary.push("## PRECONDITION_BLOCKED");
    summary.push("");
    summary.push("No unmapped branch found among tried candidates. All attempts either mapped to a device or failed.");
  }
  summary.push("");
  summary.push("## Files");
  summary.push("- form_submissions.json");
  summary.push("- api_mutations.json");
  summary.push("- state_verification.json");
  summary.push("- EMP_STATE.json");
  summary.push("- ORPHANS.csv");
  summary.push("- DEFECTS.csv");
  summary.push("- evidence/EMP-CREATE-004.json");
  summary.push("- screenshots/");
  summary.push("- artifacts/EMP-CREATE-004.trace.zip");

  fs.writeFileSync(path.join(LANE_DIR, "SUMMARY.md"), summary.join("\n"));

  log("\n=== DONE ===");
  log("final_outcome:", finalOutcome);
  log("unmapped_branch:", unmappedBranch);
  log("employees_created:", created_employees.length);
  log("employees_cleaned:", created_employees.filter((e) => e.cleanup_status === "deleted").length);
  log("runtime_s:", ((Date.now() - RUN_START) / 1000).toFixed(1));
}

run().catch((e) => { console.error(e); process.exit(1); });
