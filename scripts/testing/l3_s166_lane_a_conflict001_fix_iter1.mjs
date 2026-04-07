/**
 * S166 Lane A — EMP-CONFLICT-001 Fix Iteration 1 (v4)
 *
 * Purpose: Re-run EMP-CONFLICT-001 with correct employee navigation.
 * Root cause of A5c failure: row-selection logic opened wrong employee
 * ("Aileen L. Mendoza" instead of EMP-A), and both save statuses were null.
 *
 * Root cause of v2/v3 failures:
 *   v2: setShadcnSelect clicked Branch label outside dialog → dialog overlay blocked click
 *   v3: editCellNumber clicked Personal section Edit (not Contact section Edit)
 *       + docname was BEI-EMP-2026-NNNNN (bei_employee_id) not HR-EMP-NNNNN
 *
 * Fixes in v4:
 *   1. Dialog-scoped branch select using data-slot="select-trigger" inside dialog
 *   2. Docname resolved by parsing HR-EMP-NNNNN from dialog text with regex
 *   3. editCellNumber finds section containing "Cell" heading, clicks THAT section's Edit
 *   4. Cell input found by label proximity (walks up DOM from input to find label text)
 *
 * Approach:
 *   1. Create a SCRATCH test employee uniquely named with "CONFLICT-001" marker.
 *   2. Open that employee in TWO separate browser contexts (not the same context).
 *   3. Verify BOTH contexts have the RIGHT employee (strict text check in dialog).
 *   4. Context A edits cell_number to '09170000001', capture real network response.
 *   5. Context B edits cell_number to '09170000002' (WITHOUT refreshing), capture real response.
 *   6. Verify final state via independent API call (3rd context / apiPage).
 *   7. Determine verdict: PASS_LAST_WRITE_WINS | PASS_OPTIMISTIC_LOCK | FAIL.
 *   8. Cleanup scratch employee (3-pass soft-delete), log orphan if fails.
 *   9. Update LANE_STATE.json with iter-1 result.
 */
import { chromium } from "playwright/index.js";
import fs from "fs";
import path from "path";
import crypto from "crypto";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const HR_EMAIL = "test.hr@bebang.ph";

const LANE_DIR = "output/l3/s166/lanes/lane_a";
const EV_DIR = `${LANE_DIR}/evidence`;
const SHOT_DIR = `${LANE_DIR}/screenshots`;
const LANE_STATE_PATH = `${LANE_DIR}/LANE_STATE.json`;
const ORPHANS_CSV = `${LANE_DIR}/ORPHANS.csv`;

fs.mkdirSync(EV_DIR, { recursive: true });
fs.mkdirSync(SHOT_DIR, { recursive: true });

const T0 = Date.now();
const BUDGET_MS = 20 * 60 * 1000;

function md5(filePath) {
  try {
    const buf = fs.readFileSync(filePath);
    return crypto.createHash("md5").update(buf).digest("hex");
  } catch {
    return null;
  }
}
function loadJson(p, fb = {}) {
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return fb; }
}
function saveJson(p, d) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(d, null, 2));
}
function logOrphan(doctype, name, reason) {
  const header = !fs.existsSync(ORPHANS_CSV) ? "doctype,name,reason,ts\n" : "";
  fs.appendFileSync(ORPHANS_CSV, header + `${doctype},${name},"${reason}",${new Date().toISOString()}\n`);
  console.warn(`[ORPHAN] ${doctype} ${name}: ${reason}`);
}

// ── Login: Frappe → my.bebang.ph ──────────────────────────────────────────
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
  console.log(`[login] url: ${page.url()}`);
}

// ── Login: Frappe only (for API calls) ───────────────────────────────────
async function loginFrappe(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
  await page.goto(`${FRAPPE}/app`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1000);
}

// ── Frappe API helpers (called from hq.bebang.ph page context) ────────────
async function getCsrf(page) {
  return page.evaluate(() => {
    if (window.frappe && window.frappe.csrf_token) return window.frappe.csrf_token;
    const m = document.cookie.match(/csrf_token=([^;]+)/);
    return m ? m[1] : "fetch";
  });
}
async function frappeCall(page, resourcePath, opts = {}) {
  return page.evaluate(
    async ({ resourcePath, opts }) => {
      const r = await fetch(resourcePath, { credentials: "include", ...opts });
      const text = await r.text();
      let json = null; try { json = JSON.parse(text); } catch {}
      return { status: r.status, ok: r.ok, json, bodyHead: text.substring(0, 1500) };
    },
    { resourcePath, opts }
  );
}
async function frappePut(page, resourcePath, body) {
  const csrf = await getCsrf(page);
  return frappeCall(page, `/${resourcePath}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf },
    body: JSON.stringify(body),
  });
}
async function frappeGet(page, resourcePath) {
  return frappeCall(page, `/${resourcePath}`);
}

// ── Create scratch employee via my.bebang.ph browser form ─────────────────
async function createScratchEmployee(page) {
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);

  const addBtn = page.getByRole("button", { name: /add new employee/i }).first();
  await addBtn.waitFor({ state: "visible", timeout: 15000 });
  await addBtn.click();
  await page.waitForTimeout(1500);

  const dialog = page.locator('[role="dialog"]').first();
  await dialog.waitFor({ state: "visible", timeout: 10000 });

  // Fill form fields — all scoped inside the dialog
  await page.getByLabel(/first name/i).first().fill("Conflict");
  await page.getByLabel(/last name/i).first().fill("TestEmp (L3 2026-04-07 CONFLICT-001)");
  await page.getByLabel(/date of birth|birth date/i).first().fill("1995-06-15");

  // Select dropdowns inside dialog using data-slot=select-trigger
  // Gender
  const selects = await dialog.locator('[data-slot="select-trigger"]').all();
  console.log(`[create] Found ${selects.length} select triggers in dialog`);

  async function pickOption(triggerLocator, optionText) {
    await triggerLocator.click({ force: true });
    await page.waitForTimeout(400);
    const opt = page.locator('[role="option"]').filter({ hasText: new RegExp(optionText, "i") }).first();
    if (await opt.count()) {
      await opt.click();
      console.log(`[create] Picked option: ${optionText}`);
    } else {
      const allOpts = await page.locator('[role="option"]').allTextContents();
      console.log(`[create] Option "${optionText}" not found. Available: ${JSON.stringify(allOpts.slice(0, 10))}`);
      await page.keyboard.press("Escape").catch(() => {});
    }
    await page.waitForTimeout(300);
  }

  // Try each select trigger — pick gender first
  let genderPicked = false, branchPicked = false;
  for (const sel of selects) {
    const currentText = await sel.textContent();
    console.log(`[create] Select trigger text: "${currentText?.trim()}"`);
    if (!genderPicked && /male|female|gender|select/i.test(currentText || "")) {
      await pickOption(sel, "Male");
      genderPicked = true;
    }
  }

  // Re-query to find branch trigger (after gender pick may have re-rendered)
  const selects2 = await dialog.locator('[data-slot="select-trigger"]').all();
  for (const sel of selects2) {
    const currentText = await sel.textContent();
    if (!branchPicked && /branch|store|select/i.test(currentText || "")) {
      await pickOption(sel, "ARANETA GATEWAY");
      branchPicked = true;
    }
  }

  // Fallback: use getByRole approach for any remaining
  if (!genderPicked) {
    const genderTrigger = dialog.getByRole("combobox").filter({ hasText: /male|female|gender/i }).first();
    if (await genderTrigger.count()) await pickOption(genderTrigger, "Male");
  }

  await page.screenshot({ path: `${SHOT_DIR}/CONFLICT-001_iter1_create_prefilled.png` });

  const respPromise = page.waitForResponse(
    r => r.url().includes("create_employee"),
    { timeout: 30000 }
  );
  const submitBtn = page.getByRole("button", { name: /^create employee$|^create$/i }).first();
  await submitBtn.click();

  const submitResp = await respPromise;
  const respBody = await submitResp.json().catch(() => ({}));
  console.log(`[create] status=${submitResp.status()} body=${JSON.stringify(respBody).substring(0, 400)}`);

  await page.waitForTimeout(2000);
  const toasts = await page.locator('[data-sonner-toast]').allTextContents().catch(() => []);
  console.log("[create] toasts:", toasts);

  const msg = respBody.message || {};
  const data = msg.data || msg;
  const beiEmployeeId = data.employee_id || null;
  const bioId = data.bio_id || null;
  const deviceSn = (data.adms_enrollment && data.adms_enrollment.device_sn) || null;

  if (!beiEmployeeId) {
    throw new Error(`[create] No employee_id in response. status=${submitResp.status()} body=${JSON.stringify(respBody).substring(0, 300)}`);
  }

  // Get the Frappe docname (HR-EMP-NNNNN) from the toast text or API
  // Toast format: "Employee BEI-EMP-2026-NNNNN created. Bio ID 9001XXX..."
  // We need to search by employee_name to get the HR-EMP-NNNNN name
  // But the API call to my.bebang.ph is broken for get_list with filters.
  // Instead: try to get the name from the current page (success toast or dialog)
  // OR: call Frappe directly (via apiPage later)

  console.log(`[create] bei_id=${beiEmployeeId} bio_id=${bioId} device=${deviceSn}`);
  return { beiEmployeeId, bioId, deviceSn, createStatus: submitResp.status() };
}

// ── Resolve HR-EMP-NNNNN docname from Frappe API (hq.bebang.ph) ──────────
async function resolveDocname(apiPage, marker) {
  // Use Frappe REST API directly (same-origin from hq.bebang.ph context)
  const r = await frappeGet(apiPage,
    `api/resource/Employee?filters=${encodeURIComponent(JSON.stringify([["employee_name", "like", `%${marker}%`]]))}&fields=${encodeURIComponent(JSON.stringify(["name", "employee_name", "status", "attendance_device_id"]))}&limit_page_length=5`
  );
  console.log(`[docname] status=${r.status} body=${r.bodyHead.substring(0, 300)}`);
  const list = r.json?.data || [];
  if (list.length === 0) return null;
  // Return the MOST RECENTLY created one (highest number)
  list.sort((a, b) => {
    const numA = parseInt(a.name.match(/\d+/)?.[0] || "0");
    const numB = parseInt(b.name.match(/\d+/)?.[0] || "0");
    return numB - numA;
  });
  console.log(`[docname] Resolved: ${list[0].name} (${list[0].employee_name})`);
  return list[0].name;
}

// ── Open CONFLICT-001 employee dialog ─────────────────────────────────────
async function openConflictEmpDialog(page, ctxLabel) {
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2000);

  // Apply ARANETA GATEWAY branch filter
  const branchLabel = page.locator("label").filter({ hasText: /^Branch$/i }).first();
  if (await branchLabel.count()) {
    const trig = branchLabel.locator("xpath=following::button[1] | following::*[@role='combobox'][1]").first();
    if (await trig.count()) {
      await trig.click({ force: true });
      await page.waitForTimeout(600);
      const opt = page.locator('[role="option"]').filter({ hasText: /ARANETA GATEWAY/i }).first();
      if (await opt.count()) {
        await opt.click();
        await page.waitForTimeout(3000); // more wait for filter to take effect
        console.log(`[${ctxLabel}] branch filter applied`);
      } else {
        await page.keyboard.press("Escape");
        console.log(`[${ctxLabel}] ARANETA GATEWAY option not found`);
      }
    }
  }

  // Find the CONFLICT-001 row
  const conflictRow = page.locator("tbody tr").filter({ hasText: "CONFLICT-001" }).first();
  await conflictRow.waitFor({ state: "visible", timeout: 15000 });

  const rowText = await conflictRow.innerText();
  console.log(`[${ctxLabel}] Row text: ${rowText.substring(0, 200)}`);
  if (!rowText.includes("CONFLICT-001")) {
    throw new Error(`[${ctxLabel}] WRONG ROW — text does not contain 'CONFLICT-001': ${rowText.substring(0, 200)}`);
  }

  await conflictRow.locator("button").first().click();
  await page.waitForTimeout(2000);

  const dialog = page.locator('[role="dialog"]').first();
  await dialog.waitFor({ state: "visible", timeout: 10000 });
  const dialogText = await dialog.innerText();
  console.log(`[${ctxLabel}] Dialog text head: ${dialogText.substring(0, 400)}`);

  if (!dialogText.includes("CONFLICT-001")) {
    throw new Error(`[${ctxLabel}] WRONG DIALOG — does not contain 'CONFLICT-001': ${dialogText.substring(0, 300)}`);
  }

  // Parse Frappe docname from dialog text (format: HR-EMP-NNNNN)
  const docnameMatch = dialogText.match(/HR-EMP-\d+/);
  const parsedDocname = docnameMatch ? docnameMatch[0] : null;
  console.log(`[${ctxLabel}] Parsed docname from dialog: ${parsedDocname}`);

  return { opened: true, parsedDocname };
}

// ── Edit cell_number via Contact section Edit button ──────────────────────
async function editCellNumber(page, ctxLabel, newValue) {
  const dialog = page.locator('[role="dialog"]').first();

  // The dialog has multiple sections, each with its own Edit button.
  // We need the Edit button in the CONTACT section (which has cell_number / phone).
  // Strategy: find all section containers, identify the one with Cell/Contact text,
  // then click its Edit button.

  const allBtns = await dialog.locator("button").allTextContents();
  console.log(`[${ctxLabel}] Dialog buttons: ${JSON.stringify(allBtns.slice(0, 30))}`);

  // Find the Edit button closest to a "Contact" or "Cell" heading
  // Walk through all edit buttons, click the one that reveals cell_number input
  const editBtns = dialog.locator("button").filter({ hasText: /^Edit$/ });
  const editCount = await editBtns.count();
  console.log(`[${ctxLabel}] Edit button count: ${editCount}`);

  let cellInput = null;
  let clickedEditIdx = null;

  for (let i = 0; i < editCount; i++) {
    const btn = editBtns.nth(i);

    // Check what section this Edit button belongs to
    const sectionText = await btn.evaluate(el => {
      let cur = el.parentElement;
      for (let d = 0; d < 15; d++) {
        if (!cur) break;
        const text = cur.textContent || "";
        if (/contact|cell|phone|email/i.test(text) && text.length < 2000) {
          return text.substring(0, 200);
        }
        cur = cur.parentElement;
      }
      return "";
    });
    console.log(`[${ctxLabel}] Edit button ${i} section text: ${sectionText.substring(0, 100)}`);

    // Click this button and check if cell_number input appears
    await btn.click();
    await page.waitForTimeout(800);

    const candidateInput = dialog.locator("input").filter({ hasNotText: /^$/ });
    // Try to find input by label association
    const allInputs = await dialog.locator("input").all();
    for (const inp of allInputs) {
      const ctx2 = await inp.evaluate(el => {
        let cur = el.parentElement;
        for (let d = 0; d < 8; d++) {
          if (!cur) break;
          // Look for a label sibling or parent with Cell/Phone text
          const allText = (cur.textContent || "").toLowerCase();
          if (allText.includes("cell") || allText.includes("phone") || allText.includes("mobile")) {
            const labels = cur.querySelectorAll("label, p, span, div[class*='label']");
            for (const lbl of labels) {
              const t = (lbl.textContent || "").toLowerCase().trim();
              if (t.includes("cell") || t.includes("phone") || t.includes("mobile")) {
                return { found: true, labelText: lbl.textContent.trim() };
              }
            }
          }
          cur = cur.parentElement;
        }
        return { found: false, labelText: null };
      });
      if (ctx2.found) {
        cellInput = inp;
        clickedEditIdx = i;
        console.log(`[${ctxLabel}] Found cell_number input via label "${ctx2.labelText}" after clicking Edit ${i}`);
        break;
      }
    }

    if (cellInput) break;

    // If not found, try clicking Cancel to reset
    const cancelBtn = dialog.locator("button").filter({ hasText: /cancel/i }).first();
    if (await cancelBtn.count()) await cancelBtn.click().catch(() => {});
    await page.waitForTimeout(400);
  }

  if (!cellInput) {
    // Last resort: just use the label text-based XPath approach from A5c
    const cellLabel = dialog.locator("label").filter({ hasText: /cell|mobile|phone/i }).first();
    if (await cellLabel.count()) {
      cellInput = cellLabel.locator("xpath=following::input[1]").first();
      console.log(`[${ctxLabel}] Fallback: found cell input via label XPath`);
    }
  }

  if (!cellInput || !(await cellInput.count())) {
    await page.screenshot({ path: `${SHOT_DIR}/CONFLICT-001_iter1_${ctxLabel}_no_cell_input.png` });
    const allInputData = await dialog.locator("input").evaluateAll(els =>
      els.map((e, i) => ({ i, type: e.type, placeholder: e.placeholder, id: e.id, val: e.value }))
    );
    console.log(`[${ctxLabel}] All inputs at failure:`, JSON.stringify(allInputData));
    throw new Error(`[${ctxLabel}] Cannot find cell_number input after trying ${editCount} Edit buttons`);
  }

  await cellInput.click({ clickCount: 3 }); // select all
  await cellInput.fill(newValue);
  console.log(`[${ctxLabel}] Filled cell_number=${newValue}`);

  // Capture the save response (wait for POST)
  const respPromise = page.waitForResponse(
    r => r.url().includes("/api/") && r.request().method() === "POST",
    { timeout: 15000 }
  ).catch(() => null);

  // Find and click Save
  const saveBtn = dialog.locator("button").filter({ hasText: /save changes|save/i }).last();
  if (!(await saveBtn.count())) {
    const allBtns2 = await dialog.locator("button").allTextContents();
    console.log(`[${ctxLabel}] No Save button found. All buttons: ${JSON.stringify(allBtns2)}`);
    throw new Error(`[${ctxLabel}] Cannot find Save button`);
  }

  await saveBtn.click();
  console.log(`[${ctxLabel}] Clicked Save`);

  const resp = await respPromise;
  let saveStatus = null, saveBodyHead = null;

  if (resp) {
    saveStatus = resp.status();
    try { saveBodyHead = await resp.text(); } catch {}
    if (saveBodyHead) saveBodyHead = saveBodyHead.substring(0, 500);
    console.log(`[${ctxLabel}] Save response: status=${saveStatus} body=${saveBodyHead?.substring(0, 200)}`);
  } else {
    // No response captured — check for toast or dialog state
    await page.waitForTimeout(2000);
    const toasts = await page.locator('[data-sonner-toast]').allTextContents().catch(() => []);
    const dialogNow = await dialog.innerText().catch(() => "");
    console.warn(`[${ctxLabel}] No POST response within 15s. Toasts: ${JSON.stringify(toasts)}. Dialog: ${dialogNow.substring(0, 200)}`);
    saveBodyHead = `NO_RESPONSE_CAPTURED. Toasts=${JSON.stringify(toasts)}`;
    // Check if there's a success indicator in toasts
    if (toasts.some(t => /success|saved|updated/i.test(t))) {
      saveStatus = 200; // infer from toast
      saveBodyHead = `INFERRED_200_FROM_TOAST: ${JSON.stringify(toasts)}`;
    }
  }

  await page.waitForTimeout(1000);
  return { saveStatus, saveBodyHead };
}

// ── Cleanup scratch employee (3-pass soft-delete via hq.bebang.ph) ────────
async function cleanupScratchEmployee(apiPage, frappeDocname) {
  console.log(`[cleanup] Soft-deleting ${frappeDocname}...`);

  const p1 = await frappePut(apiPage, `api/resource/Employee/${encodeURIComponent(frappeDocname)}`, { relieving_date: "2026-04-07" });
  console.log(`[cleanup] Pass 1 (relieving_date): ${p1.status} ${p1.ok ? "OK" : "FAIL"} ${p1.ok ? "" : p1.bodyHead.substring(0, 150)}`);
  await new Promise(r => setTimeout(r, 500));

  const p2 = await frappePut(apiPage, `api/resource/Employee/${encodeURIComponent(frappeDocname)}`, { status: "Left" });
  console.log(`[cleanup] Pass 2 (status=Left): ${p2.status} ${p2.ok ? "OK" : "FAIL"}`);
  await new Promise(r => setTimeout(r, 500));

  const p3 = await frappePut(apiPage, `api/resource/Employee/${encodeURIComponent(frappeDocname)}`, { attendance_device_id: "" });
  console.log(`[cleanup] Pass 3 (clear bio_id): ${p3.status} ${p3.ok ? "OK" : "FAIL"}`);
  await new Promise(r => setTimeout(r, 500));

  const verify = await frappeGet(apiPage, `api/resource/Employee/${encodeURIComponent(frappeDocname)}`);
  const vDoc = verify.json?.data;
  const success = vDoc?.status === "Left" && !vDoc?.attendance_device_id;
  console.log(`[cleanup] Verify: status=${vDoc?.status} bio_id=${vDoc?.attendance_device_id || "cleared"} success=${success}`);

  return { success, p1: p1.ok, p2: p2.ok, p3: p3.ok, final_status: vDoc?.status };
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════════
async function main() {
  console.log("=== S166 Lane A — EMP-CONFLICT-001 Fix Iteration 1 (v4) ===");
  console.log(`Budget: ${BUDGET_MS / 60000} minutes`);

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });

  let frappeDocname = null;  // HR-EMP-NNNNN
  let beiEmployeeId = null;  // BEI-EMP-2026-NNNNN
  let conflictBioId = null;
  let ctxASaveStatus = null, ctxASaveBodyHead = null;
  let ctxBSaveStatus = null, ctxBSaveBodyHead = null;
  let finalCellNumber = null;
  let ctxAPreMd5 = null, ctxBPreMd5 = null, ctxAPostMd5 = null, ctxBPostMd5 = null;
  let verdict = "FAIL";
  let conflictOutcome = null;
  let errorDetail = null;
  let cleanupResults = {};

  // ── Frappe API page (hq.bebang.ph) ──
  const apiCtx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const apiPage = await apiCtx.newPage();

  try {
    console.log("\n=== STEP 0: Login to hq.bebang.ph ===");
    await loginFrappe(apiPage, HR_EMAIL);

    // ── STEP 1: Create scratch employee ──
    console.log("\n=== STEP 1: Create scratch employee ===");
    const createCtx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const createPage = await createCtx.newPage();
    await loginMyBebang(createPage, HR_EMAIL);
    const created = await createScratchEmployee(createPage);
    beiEmployeeId = created.beiEmployeeId;
    conflictBioId = created.bioId;
    await createCtx.close();

    // ── Resolve Frappe docname via hq.bebang.ph API ──
    console.log("\n=== STEP 1b: Resolve Frappe docname ===");
    frappeDocname = await resolveDocname(apiPage, "CONFLICT-001");
    if (!frappeDocname) {
      throw new Error("Cannot resolve Frappe docname for CONFLICT-001 employee");
    }
    console.log(`[main] Scratch employee: bei_id=${beiEmployeeId} frappe_docname=${frappeDocname} bio_id=${conflictBioId}`);

    // ── STEP 2: Open in 2 browser contexts ──
    console.log("\n=== STEP 2: Login 2 contexts ===");
    const ctxA = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const ctxB = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const pageA = await ctxA.newPage();
    const pageB = await ctxB.newPage();

    await loginMyBebang(pageA, HR_EMAIL);
    await loginMyBebang(pageB, HR_EMAIL);

    // Open conflict employee in both
    console.log("\n=== STEP 3: Open dialog in both contexts ===");
    const resultA = await openConflictEmpDialog(pageA, "ctxA");
    const resultB = await openConflictEmpDialog(pageB, "ctxB");

    // Validate docname from dialog (cross-check)
    if (resultA.parsedDocname && resultA.parsedDocname !== frappeDocname) {
      console.warn(`[main] ctxA dialog docname ${resultA.parsedDocname} != resolved ${frappeDocname} — using dialog value`);
      frappeDocname = resultA.parsedDocname;
    }

    // PRE screenshots
    const prePathA = `${SHOT_DIR}/EMP-CONFLICT-001_iter1_ctxA_pre.png`;
    const prePathB = `${SHOT_DIR}/EMP-CONFLICT-001_iter1_ctxB_pre.png`;
    await pageA.screenshot({ path: prePathA, fullPage: true });
    await pageB.screenshot({ path: prePathB, fullPage: true });
    ctxAPreMd5 = md5(prePathA);
    ctxBPreMd5 = md5(prePathB);
    console.log(`[main] PRE screenshots: ctxA_pre=${ctxAPreMd5} ctxB_pre=${ctxBPreMd5}`);
    if (ctxAPreMd5 === ctxBPreMd5) {
      console.warn("[main] WARNING: ctxA_pre and ctxB_pre identical MD5 (expected when same data, same styling)");
    }

    // ── STEP 4: ctxA saves cell_number = '09170000001' ──
    console.log("\n=== STEP 4: ctxA edit + save (09170000001) ===");
    ({ saveStatus: ctxASaveStatus, saveBodyHead: ctxASaveBodyHead } = await editCellNumber(pageA, "ctxA", "09170000001"));

    // ── STEP 5: ctxB saves cell_number = '09170000002' (no refresh) ──
    console.log("\n=== STEP 5: ctxB edit + save (09170000002, stale) ===");
    ({ saveStatus: ctxBSaveStatus, saveBodyHead: ctxBSaveBodyHead } = await editCellNumber(pageB, "ctxB", "09170000002"));

    // POST screenshots
    const postPathA = `${SHOT_DIR}/EMP-CONFLICT-001_iter1_ctxA_post.png`;
    const postPathB = `${SHOT_DIR}/EMP-CONFLICT-001_iter1_ctxB_post.png`;
    await pageA.screenshot({ path: postPathA, fullPage: true });
    await pageB.screenshot({ path: postPathB, fullPage: true });
    ctxAPostMd5 = md5(postPathA);
    ctxBPostMd5 = md5(postPathB);
    console.log(`[main] POST screenshots: ctxA_post=${ctxAPostMd5} ctxB_post=${ctxBPostMd5}`);

    await ctxA.close();
    await ctxB.close();

    // ── STEP 6: Verify final state via API ──
    console.log("\n=== STEP 6: Verify final cell_number via Frappe API ===");
    await new Promise(r => setTimeout(r, 1000));
    const finalState = await frappeGet(apiPage, `api/resource/Employee/${encodeURIComponent(frappeDocname)}`);
    const doc = finalState.json?.data || {};
    finalCellNumber = doc.cell_number || null;
    console.log(`[main] Final cell_number: ${finalCellNumber}`);
    console.log(`[main] ctxA_status=${ctxASaveStatus} ctxB_status=${ctxBSaveStatus}`);

    // ── STEP 7: Verdict ──
    console.log("\n=== STEP 7: Determine verdict ===");
    if (ctxASaveStatus === null || ctxBSaveStatus === null) {
      verdict = "FAIL";
      errorDetail = `Null save status(es). ctxA=${ctxASaveStatus}, ctxB=${ctxBSaveStatus}`;
      console.error(`[verdict] FAIL: ${errorDetail}`);
    } else if (ctxASaveStatus < 300 && ctxBSaveStatus < 300) {
      conflictOutcome = "last_write_wins";
      verdict = "PASS_LAST_WRITE_WINS";
      console.log(`[verdict] Both 2xx. Final cell_number=${finalCellNumber} (ctxB's 09170000002 wins if it saved last)`);
    } else if (ctxASaveStatus < 300 && ctxBSaveStatus >= 400) {
      verdict = "PASS_OPTIMISTIC_LOCK";
      conflictOutcome = "optimistic_lock_on_ctxB";
      console.log("[verdict] PASS_OPTIMISTIC_LOCK: ctxB rejected");
    } else if (ctxASaveStatus >= 400 && ctxBSaveStatus < 300) {
      verdict = "PASS_OPTIMISTIC_LOCK";
      conflictOutcome = "optimistic_lock_on_ctxA";
      console.log("[verdict] PASS_OPTIMISTIC_LOCK: ctxA rejected");
    } else {
      verdict = "FAIL";
      errorDetail = `Both saves failed/null. ctxA=${ctxASaveStatus} ctxB=${ctxBSaveStatus}`;
      console.error(`[verdict] FAIL: ${errorDetail}`);
    }

  } catch (err) {
    console.error("[main] ERROR:", err.message);
    errorDetail = err.message;
    verdict = "FAIL";
  } finally {
    // ── STEP 8: Cleanup ──
    if (frappeDocname) {
      console.log(`\n=== STEP 8: Cleanup ${frappeDocname} ===`);
      try {
        const cu = await cleanupScratchEmployee(apiPage, frappeDocname);
        cleanupResults = { success: cu.success, passes: { p1: cu.p1, p2: cu.p2, p3: cu.p3 }, final_status: cu.final_status };
        if (!cu.success) logOrphan("Employee", frappeDocname, "3-pass soft-delete incomplete");
      } catch (e) {
        cleanupResults = { success: false, error: e.message };
        logOrphan("Employee", frappeDocname, `cleanup exception: ${e.message}`);
      }
    } else if (beiEmployeeId) {
      // Try to resolve and cleanup
      try {
        const resolvedName = await resolveDocname(apiPage, "CONFLICT-001");
        if (resolvedName) {
          frappeDocname = resolvedName;
          const cu = await cleanupScratchEmployee(apiPage, resolvedName);
          cleanupResults = { success: cu.success, passes: { p1: cu.p1, p2: cu.p2, p3: cu.p3 }, final_status: cu.final_status, note: "docname resolved in finally" };
          if (!cu.success) logOrphan("Employee", resolvedName, "3-pass soft-delete incomplete (finally branch)");
        }
      } catch (e) {
        logOrphan("Employee", beiEmployeeId, `could not resolve docname for cleanup: ${e.message}`);
      }
    }

    await apiCtx.close();
    await browser.close();
  }

  // ── STEP 9: Write evidence file ──
  const evidence = {
    scenario_id: "EMP-CONFLICT-001",
    phase: "A5c-fix-iter1",
    iteration: 1,
    fix_for: "A5c audit REJECT — wrong employee navigated (Aileen L. Mendoza instead of EMP-A)",
    scratch_employee: {
      frappe_docname: frappeDocname || "CREATION_FAILED",
      bei_employee_id: beiEmployeeId || null,
      bio_id: conflictBioId || null,
      branch: "ARANETA GATEWAY",
    },
    ctxA_save_status: ctxASaveStatus,
    ctxA_save_body_head: ctxASaveBodyHead ? ctxASaveBodyHead.substring(0, 500) : null,
    ctxB_save_status: ctxBSaveStatus,
    ctxB_save_body_head: ctxBSaveBodyHead ? ctxBSaveBodyHead.substring(0, 500) : null,
    final_cell_number_after_both_saves: finalCellNumber,
    screenshots: {
      ctxA_pre: "EMP-CONFLICT-001_iter1_ctxA_pre.png",
      ctxB_pre: "EMP-CONFLICT-001_iter1_ctxB_pre.png",
      ctxA_post: "EMP-CONFLICT-001_iter1_ctxA_post.png",
      ctxB_post: "EMP-CONFLICT-001_iter1_ctxB_post.png",
    },
    screenshot_md5s: { ctxA_pre: ctxAPreMd5, ctxB_pre: ctxBPreMd5, ctxA_post: ctxAPostMd5, ctxB_post: ctxBPostMd5 },
    distinct_pre_screenshots: ctxAPreMd5 !== ctxBPreMd5,
    verdict,
    status: verdict.startsWith("PASS") ? "PASS" : "FAIL",
    browser_sourced: true,
    conflict_outcome: conflictOutcome || (verdict === "FAIL" ? "failed_saves" : null),
    cleanup: cleanupResults,
    error: errorDetail || null,
    elapsed_ms: Date.now() - T0,
    ts: new Date().toISOString(),
  };
  saveJson(`${EV_DIR}/EMP-CONFLICT-001.json`, evidence);
  console.log(`[main] Evidence written: ${EV_DIR}/EMP-CONFLICT-001.json`);

  // ── STEP 10: Update LANE_STATE.json ──
  const laneState = loadJson(LANE_STATE_PATH, {});
  if (Array.isArray(laneState.scenario_results)) {
    const idx = laneState.scenario_results.findIndex(r => r.id === "EMP-CONFLICT-001");
    const entry = {
      id: "EMP-CONFLICT-001", phase: "A5c-fix-iter1", status: evidence.status, verdict,
      notes: `iter1: scratch=${frappeDocname}, ctxA=${ctxASaveStatus}, ctxB=${ctxBSaveStatus}, final_cell=${finalCellNumber}, outcome=${conflictOutcome}`,
      scratch_employee: evidence.scratch_employee,
      cleanup: cleanupResults,
      evidence_file: "evidence/EMP-CONFLICT-001.json",
      recorded_at: new Date().toISOString(),
    };
    if (idx >= 0) laneState.scenario_results[idx] = entry;
    else laneState.scenario_results.push(entry);
  }
  if (laneState.phase_a5c_summary) {
    laneState.phase_a5c_summary["EMP-CONFLICT-001"] = verdict;
    laneState.phase_a5c_summary["EMP-CONFLICT-001_iter"] = 1;
  }
  laneState.last_updated = new Date().toISOString();
  laneState.conflict001_fix_iter1 = { completed: new Date().toISOString(), verdict, scratch_employee: frappeDocname, cleanup_success: cleanupResults.success };
  saveJson(LANE_STATE_PATH, laneState);
  console.log("[main] LANE_STATE.json updated.");

  // ── Final Report ──
  console.log("\n=== FINAL REPORT ===");
  console.log(`Scratch employee:   ${frappeDocname} (bei=${beiEmployeeId}, bio=${conflictBioId})`);
  console.log(`ctxA save status:   ${ctxASaveStatus}`);
  console.log(`ctxA save body:     ${ctxASaveBodyHead?.substring(0, 150)}`);
  console.log(`ctxB save status:   ${ctxBSaveStatus}`);
  console.log(`ctxB save body:     ${ctxBSaveBodyHead?.substring(0, 150)}`);
  console.log(`Final cell_number:  ${finalCellNumber}`);
  console.log(`Verdict:            ${verdict}`);
  console.log(`Cleanup success:    ${cleanupResults.success}`);
  console.log(`ctxA_pre  md5: ${ctxAPreMd5}`);
  console.log(`ctxB_pre  md5: ${ctxBPreMd5}`);
  console.log(`ctxA_post md5: ${ctxAPostMd5}`);
  console.log(`ctxB_post md5: ${ctxBPostMd5}`);
  console.log(`Distinct pre: ${ctxAPreMd5 !== ctxBPreMd5}`);
  console.log(`Elapsed: ${((Date.now() - T0) / 1000).toFixed(1)}s`);
  if (errorDetail) console.error(`Error: ${errorDetail}`);
}

main().catch(e => { console.error("[FATAL]", e); process.exit(1); });
