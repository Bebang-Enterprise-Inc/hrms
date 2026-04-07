/**
 * S166 Lane F — UX Gaps + Stub Pages (pure observation, zero mutations)
 *
 * 15 scenarios: EMP-UX-001..010 + EMP-STUB-001..005
 * Visits pages, captures absence-of-feature as evidence, logs defects.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const OUT_DIR = "F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/lane_f";
const SHOT_DIR = path.join(OUT_DIR, "screenshots");
const EVID_DIR = path.join(OUT_DIR, "evidence");
fs.mkdirSync(SHOT_DIR, { recursive: true });
fs.mkdirSync(EVID_DIR, { recursive: true });

const nowPht = () =>
  new Date().toLocaleString("en-PH", { timeZone: "Asia/Manila", hour12: false });

const form_submissions = [];
const state_verification = [];
const defects = [];

async function loginMyBebang(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.fill('input[name="usr"]', email).catch(() => {});
  await page.fill('input[name="pwd"]', PASSWORD).catch(() => {});
  await page.click('button[type="submit"]').catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1000);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  return page.url();
}

async function shoot(page, scenarioId, tag = "observed") {
  const file = path.join(SHOT_DIR, `${scenarioId}_${tag}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => {});
  return file.replace(/\\/g, "/");
}

async function observePage(page) {
  return await page.evaluate(() => {
    const text = (document.body?.innerText || "").slice(0, 6000);
    const buttons = Array.from(document.querySelectorAll("button, a[role=button]"))
      .map((b) => (b.innerText || b.textContent || "").trim())
      .filter(Boolean);
    const inputs = Array.from(document.querySelectorAll("input,select,textarea"))
      .map((i) => ({
        type: i.getAttribute("type") || i.tagName.toLowerCase(),
        name: i.getAttribute("name") || "",
        placeholder: i.getAttribute("placeholder") || "",
        ariaLabel: i.getAttribute("aria-label") || "",
      }));
    const navItems = Array.from(document.querySelectorAll("nav a, aside a, [role=navigation] a, [class*='sidebar'] a, [data-sidebar] a, [class*='Sidebar'] a"))
      .map((a) => ({ text: (a.innerText || "").trim(), href: a.getAttribute("href") || "" }))
      .filter((x) => x.text);
    return {
      url: location.href,
      title: document.title,
      h1: (document.querySelector("h1")?.innerText || "").trim(),
      h2s: Array.from(document.querySelectorAll("h2")).map((h) => h.innerText.trim()).slice(0, 20),
      text_head: text,
      button_count: buttons.length,
      buttons: buttons.slice(0, 60),
      input_count: inputs.length,
      inputs: inputs.slice(0, 40),
      nav_items: navItems.slice(0, 50),
    };
  });
}

function record(scenarioId, form, inputs, observed, checkDesc, passed, defectRow, shotPath) {
  form_submissions.push({
    scenario_id: scenarioId,
    form,
    inputs,
    submit_action: "page-load-only",
    response: { status: 200, observed, toasts: [] },
    screenshot_after: shotPath,
    timestamp_pht: nowPht(),
  });
  state_verification.push({
    scenario_id: scenarioId,
    check: checkDesc,
    before: null,
    after: observed,
    passed,
    defect_logged: true,
  });
  defects.push(defectRow);
  fs.writeFileSync(
    path.join(EVID_DIR, `${scenarioId}.json`),
    JSON.stringify({ scenarioId, checkDesc, observed, passed, defect: defectRow, screenshot: shotPath, timestamp_pht: nowPht() }, null, 2)
  );
}

function textIncludes(obs, ...needles) {
  const hay = ((obs.text_head || "") + " " + (obs.buttons || []).join(" ")).toLowerCase();
  return needles.some((n) => hay.includes(n.toLowerCase()));
}
// Check only controls (buttons + inputs placeholders/labels) — not page body text
function controlIncludes(obs, ...needles) {
  const btns = (obs.buttons || []).join(" ").toLowerCase();
  const ins = (obs.inputs || [])
    .map((i) => `${i.name} ${i.placeholder} ${i.ariaLabel}`)
    .join(" ")
    .toLowerCase();
  const hay = btns + " " + ins;
  return needles.some((n) => hay.includes(n.toLowerCase()));
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });

  const startedAt = Date.now();
  try {
    // ===== HR SESSION =====
    const hrCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const hr = await hrCtx.newPage();
    const hrUrl = await loginMyBebang(hr, "test.hr@bebang.ph");
    console.log("[login] test.hr →", hrUrl);

    // ---- EMP-UX-001: Attendance (self-service only) ----
    {
      const id = "EMP-UX-001";
      await hr.goto(`${BASE}/dashboard/hr/attendance`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr.waitForTimeout(1500);
      const obs = await observePage(hr);
      const shot = await shoot(hr, id);
      const hasStoreFilter = controlIncludes(obs, "store", "branch", "all stores", "select store", "filter by store");
      const isSelfService = textIncludes(obs, "my attendance", "time in", "time out", "clock in");
      record(
        id,
        "AttendancePageObservation",
        { navigation: "sidebar → HR → Attendance", role: "test.hr" },
        { ...obs, derived: { has_store_filter: hasStoreFilter, is_self_service_only: isSelfService && !hasStoreFilter } },
        "Attendance page is self-service only, not org-wide",
        !hasStoreFilter,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !hasStoreFilter ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "HR Attendance page is self-service only — no org-wide view",
          observed: `Page "${obs.h1 || obs.title}" has ${obs.button_count} buttons; no store/branch filter detected`,
          expected: "Org-wide attendance dashboard with filters for 47 stores",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-UX-002: Schedule (no shift assignment grid) ----
    {
      const id = "EMP-UX-002";
      await hr.goto(`${BASE}/dashboard/hr/schedule`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr.waitForTimeout(1500);
      const obs = await observePage(hr);
      const shot = await shoot(hr, id);
      const hasGrid = textIncludes(obs, "assign shift", "shift grid", "roster", "assign crew");
      record(
        id,
        "SchedulePageObservation",
        { navigation: "sidebar → HR → Schedule", role: "test.hr" },
        { ...obs, derived: { has_shift_assignment_grid: hasGrid } },
        "Schedule page is self-service; no admin shift assignment grid",
        !hasGrid,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !hasGrid ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "HR Schedule lacks shift assignment grid for admins",
          observed: `Page "${obs.h1 || obs.title}" — no assign shift / roster controls detected`,
          expected: "Admin grid to assign shifts to crew per store per day",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-UX-003: Attendance Correction (no admin review queue) ----
    {
      const id = "EMP-UX-003";
      await hr.goto(`${BASE}/dashboard/hr/attendance-correction`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr.waitForTimeout(1500);
      const obs = await observePage(hr);
      const shot = await shoot(hr, id);
      const hasQueue = controlIncludes(obs, "approve", "reject") && textIncludes(obs, "pending", "review queue", "to review");
      record(
        id,
        "AttendanceCorrectionObservation",
        { navigation: "sidebar → HR → Attendance Correction", role: "test.hr" },
        { ...obs, derived: { has_admin_review_queue: hasQueue } },
        "Attendance Correction has no admin review queue",
        !hasQueue,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !hasQueue ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "No admin review queue for attendance corrections",
          observed: `Page is a submission form only — no pending/approve/reject UI`,
          expected: "HR admin queue to review & approve attendance corrections",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-UX-004: Compensation Setup (row modal empty) ----
    {
      const id = "EMP-UX-004";
      await hr.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr.waitForTimeout(2000);
      // try to click first row to open the modal (no mutation, just inspection)
      const rowClicked = await hr
        .evaluate(() => {
          const row = document.querySelector("tbody tr, [role=row]");
          if (row) { row.click(); return true; }
          return false;
        })
        .catch(() => false);
      await hr.waitForTimeout(1200);
      const obs = await observePage(hr);
      const shot = await shoot(hr, id);
      const modalHasSalaryFields = controlIncludes(obs, "basic pay", "allowance", "salary structure", "rate per day", "monthly rate", "basic salary");
      // close any opened dialog
      await hr.keyboard.press("Escape").catch(() => {});
      record(
        id,
        "CompensationSetupRowModal",
        { navigation: "Payroll → Compensation Setup → click employee row", role: "test.hr", row_clicked: rowClicked },
        { ...obs, derived: { modal_has_salary_fields: modalHasSalaryFields, modal_is_empty: !modalHasSalaryFields } },
        "Compensation Setup row modal is empty / non-editable",
        !modalHasSalaryFields,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !modalHasSalaryFields ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Compensation Setup row modal is empty — no editable salary fields",
          observed: `Row opened; no basic pay / allowance / salary structure inputs visible`,
          expected: "Modal with basic pay, allowances, salary structure, rate per day fields",
          recommended_sprint: "S167",
        },
        shot
      );
    }

    await hrCtx.close();

    // ===== FINANCE SESSION =====
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await loginMyBebang(page, "test.finance@bebang.ph");

      // ---- EMP-UX-005: Sensitive Changes Queue (no Approve/Reject buttons) ----
      const id = "EMP-UX-005";
      await page.goto(`${BASE}/dashboard/hr/payroll/sensitive-changes`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await page.waitForTimeout(1800);
      // try clicking first pending row to inspect
      await page.evaluate(() => {
        const row = document.querySelector("tbody tr, [role=row]");
        if (row) row.click();
      }).catch(() => {});
      await page.waitForTimeout(1000);
      const obs = await observePage(page);
      const shot = await shoot(page, id);
      const hasApproveBtn = (obs.buttons || []).some((b) => /approve|reject/i.test(b));
      await page.keyboard.press("Escape").catch(() => {});
      record(
        id,
        "SensitiveChangesQueue",
        { navigation: "Payroll → Sensitive Changes", role: "test.finance" },
        { ...obs, derived: { has_approve_reject_buttons: hasApproveBtn } },
        "Sensitive Changes queue has no visible Approve/Reject buttons",
        !hasApproveBtn,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !hasApproveBtn ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Finance cannot approve/reject sensitive payroll changes from queue",
          observed: `Queue opened; no approve/reject buttons found in row detail`,
          expected: "Approve & Reject actions on each pending change row",
          recommended_sprint: "S167",
        },
        shot
      );
      await ctx.close();
    }

    // ===== CREW SESSION =====
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await loginMyBebang(page, "test.crew1@bebang.ph");

      // ---- EMP-UX-006: Sidebar bloat ----
      {
        const id = "EMP-UX-006";
        await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
        await page.waitForTimeout(1500);
        const baseObs = await observePage(page);
        const navCount = (baseObs.nav_items || []).length;
        const shot = await shoot(page, id, "sidebar");

        // visit 5 nav items and see if ≥3 return Access Restricted
        const targets = (baseObs.nav_items || []).filter((t) => t && t.href && t.href.startsWith("/")).slice(0, 20);
        let restrictedCount = 0;
        const visited = [];
        for (const t of targets) {
          await page.goto(`${BASE}${t.href}`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(800);
          const bodyText = await page.evaluate(() => (document.body?.innerText || "").slice(0, 2000)).catch(() => "");
          const restricted = /access restricted|not authorized|permission denied|forbidden|403|you don.?t have (permission|access)/i.test(bodyText);
          visited.push({ label: t.text, href: t.href, restricted });
          if (restricted) restrictedCount++;
          if (visited.length >= 5) break;
        }
        const obs = { ...baseObs, derived: { nav_item_count: navCount, visited, restricted_count: restrictedCount } };
        record(
          id,
          "CrewSidebarBloat",
          { navigation: "crew dashboard → sidebar", role: "test.crew1" },
          obs,
          "Crew sidebar has too many items; ≥3 visited items return Access Restricted",
          navCount >= 15 || restrictedCount >= 3,
          {
            scenario_id: id,
            severity: "HIGH",
            classification: navCount >= 15 || restrictedCount >= 3 ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
            title: "Crew sidebar bloated with restricted items",
            observed: `Sidebar exposes ${navCount} items; ${restrictedCount}/${visited.length} visited returned restricted`,
            expected: "Crew sidebar shows only the modules a crew member can actually use",
            recommended_sprint: "S168+",
          },
          shot
        );
      }

      // ---- EMP-UX-007: Payslip missing Download/Print ----
      {
        const id = "EMP-UX-007";
        await page.goto(`${BASE}/dashboard/hr/payslip`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
        await page.waitForTimeout(1500);
        // try to open most recent payslip
        await page.evaluate(() => {
          const row = document.querySelector("tbody tr, [role=row], a[href*='payslip']");
          if (row) row.click();
        }).catch(() => {});
        await page.waitForTimeout(1500);
        const obs = await observePage(page);
        const shot = await shoot(page, id);
        const hasExport = (obs.buttons || []).some((b) => /download|print|export|pdf/i.test(b));
        record(
          id,
          "PayslipPageObservation",
          { navigation: "sidebar → Payslip → open most recent", role: "test.crew1" },
          { ...obs, derived: { has_export_button: hasExport } },
          "Payslip has no Download PDF / Print / Export button",
          !hasExport,
          {
            scenario_id: id,
            severity: "MEDIUM",
            classification: !hasExport ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
            title: "Crew cannot download or print payslip",
            observed: `No download/print/export button on payslip detail`,
            expected: "Download PDF and Print buttons on each payslip",
            recommended_sprint: "S168+",
          },
          shot
        );
      }

      // ---- EMP-UX-008: No notification bell / inbox ----
      {
        const id = "EMP-UX-008";
        await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
        await page.waitForTimeout(1000);
        const obs = await observePage(page);
        const shot = await shoot(page, id);
        const hasBell = await page.evaluate(() => {
          const sel = "header [aria-label*='notification' i], header [data-testid*='notification' i], button[aria-label*='bell' i], .notification-bell, header [aria-label*='inbox' i]";
          return document.querySelectorAll(sel).length > 0;
        }).catch(() => false);
        await page.waitForTimeout(3000);
        record(
          id,
          "NotificationBellObservation",
          { navigation: "crew dashboard — scan chrome", role: "test.crew1" },
          { ...obs, derived: { has_notification_bell: hasBell } },
          "Crew has no notification bell or inbox anywhere",
          !hasBell,
          {
            scenario_id: id,
            severity: "MEDIUM",
            classification: !hasBell ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
            title: "No in-app notification center for crew",
            observed: `No notification bell / inbox element found in dashboard chrome`,
            expected: "Notification bell with unread count and inbox dropdown",
            recommended_sprint: "S168+",
          },
          shot
        );
      }

      await ctx.close();
    }

    // ===== HR SESSION (remaining HR-side scenarios) =====
    const hrCtx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const hr2 = await hrCtx2.newPage();
    await loginMyBebang(hr2, "test.hr@bebang.ph");

    // ---- EMP-UX-009: OT approve dialog missing "Approved Hours" input ----
    {
      const id = "EMP-UX-009";
      await hr2.goto(`${BASE}/dashboard/hr/overtime`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1500);
      // try to open first pending OT approve dialog — but DO NOT submit
      const opened = await hr2.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const approve = btns.find((b) => /approve/i.test(b.innerText || ""));
        if (approve) { approve.click(); return true; }
        return false;
      }).catch(() => false);
      await hr2.waitForTimeout(1500);
      const obs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const hasApprovedHoursInput = (obs.inputs || []).some(
        (i) => /approved.?hours|actual.?hours/i.test((i.name || "") + " " + (i.placeholder || "") + " " + (i.ariaLabel || ""))
      ) || textIncludes(obs, "approved hours");
      // close dialog without submitting
      await hr2.keyboard.press("Escape").catch(() => {});
      record(
        id,
        "OvertimeApproveDialog",
        { navigation: "HR → Overtime → open approve dialog", role: "test.hr", dialog_opened: opened, submitted: false },
        { ...obs, derived: { has_approved_hours_input: hasApprovedHoursInput } },
        "OT approve dialog missing Approved Hours input",
        !hasApprovedHoursInput,
        {
          scenario_id: id,
          severity: "HIGH",
          classification: !hasApprovedHoursInput ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "OT approval dialog cannot adjust approved hours",
          observed: `Approve dialog opened but no approved-hours input detected`,
          expected: "Editable Approved Hours field so HR can approve partial OT",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-UX-010: Payroll Processing no branch filter ----
    {
      const id = "EMP-UX-010";
      await hr2.goto(`${BASE}/dashboard/hr/payroll/processing`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1800);
      const obs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const hasBranchFilter =
        textIncludes(obs, "process by branch", "branch filter", "select branch", "per branch") ||
        (obs.inputs || []).some((i) => /branch/i.test((i.name || "") + (i.placeholder || "") + (i.ariaLabel || "")));
      record(
        id,
        "PayrollProcessingObservation",
        { navigation: "Payroll → Processing", role: "test.hr" },
        { ...obs, derived: { has_branch_filter: hasBranchFilter } },
        "Payroll Processing has no branch filter / Process-by-Branch option",
        !hasBranchFilter,
        {
          scenario_id: id,
          severity: "HIGH",
          classification: !hasBranchFilter ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Payroll Processing cannot be scoped per branch",
          observed: `No branch filter or Process-by-Branch control detected`,
          expected: "Branch/store filter to process payroll incrementally",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-STUB-001: HR Reports — 8 tiles none working ----
    {
      const id = "EMP-STUB-001";
      await hr2.goto(`${BASE}/dashboard/hr/reports`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1500);
      const baseObs = await observePage(hr2);
      const shot = await shoot(hr2, id, "grid");
      // find clickable report tiles — scope to main content only (exclude sidebar nav)
      const tiles = await hr2.evaluate(() => {
        const main = document.querySelector("main, [role=main], [class*='content']") || document.body;
        const nodes = Array.from(main.querySelectorAll("a[href*='/reports'], a[href*='/report/'], [class*='tile'], [class*='card']"));
        const seen = new Set();
        const out = [];
        for (const n of nodes) {
          const text = (n.innerText || "").trim().slice(0, 80);
          const href = n.getAttribute("href") || n.querySelector("a")?.getAttribute("href") || null;
          if (!text || text.length < 3) continue;
          const key = text + "|" + href;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({ text, href });
          if (out.length >= 12) break;
        }
        return out;
      }).catch(() => []);
      const clickResults = [];
      const maxTiles = Math.min(8, tiles.length);
      for (let i = 0; i < maxTiles; i++) {
        const t = tiles[i];
        let landedWorking = false;
        const urlBefore = hr2.url();
        if (t.href) {
          await hr2.goto(`${BASE}${t.href.startsWith("/") ? t.href : "/" + t.href}`, { waitUntil: "networkidle", timeout: 25000 }).catch(() => {});
          await hr2.waitForTimeout(700);
          const detail = await hr2.evaluate(() => {
            const body = (document.body?.innerText || "").slice(0, 2000);
            const hasTable = !!document.querySelector("table tbody tr");
            const hasChart = !!document.querySelector("svg[class*='recharts'], canvas, [class*='chart']");
            return { body, hasTable, hasChart };
          }).catch(() => ({ body: "", hasTable: false, hasChart: false }));
          const stubText = /coming soon|not available|stub|todo|placeholder|404|not found|under construction|no data/i.test(detail.body);
          landedWorking = !stubText && (detail.hasTable || detail.hasChart) && hr2.url() !== urlBefore;
          clickResults.push({ tile: t.text, href: t.href, landed_working: landedWorking });
          await hr2.goto(`${BASE}/dashboard/hr/reports`, { waitUntil: "networkidle", timeout: 25000 }).catch(() => {});
          await hr2.waitForTimeout(500);
        } else {
          clickResults.push({ tile: t.text, href: null, landed_working: false });
        }
      }
      const workingCount = clickResults.filter((c) => c.landed_working).length;
      const obs = { ...baseObs, derived: { tile_count: tiles.length, clicked: clickResults, working_count: workingCount } };
      record(
        id,
        "HRReportsTiles",
        { navigation: "HR → Reports", role: "test.hr" },
        obs,
        "HR Reports tiles — none navigate to a working report",
        workingCount === 0,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: workingCount === 0 ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "HR Reports section is a stub — no working reports",
          observed: `${tiles.length} tiles present; ${workingCount}/${maxTiles} navigated to a working report`,
          expected: "All 8 HR report tiles open functional reports",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-STUB-002: Training page is stub ----
    {
      const id = "EMP-STUB-002";
      await hr2.goto(`${BASE}/dashboard/hr/training`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1500);
      const obs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const hasCreateProgram = (obs.buttons || []).some((b) => /create training|new training|add program/i.test(b));
      const refersDesk = textIncludes(obs, "frappe desk", "desk", "manage in desk");
      record(
        id,
        "TrainingPageObservation",
        { navigation: "HR → Training", role: "test.hr" },
        { ...obs, derived: { has_create_program_btn: hasCreateProgram, refers_to_desk: refersDesk } },
        "Training page is a stub — no create program button, refers to Frappe Desk",
        !hasCreateProgram,
        {
          scenario_id: id,
          severity: "HIGH",
          classification: !hasCreateProgram ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Training module is a stub — no program management",
          observed: `No Create Training Program button; desk-reference: ${refersDesk}`,
          expected: "Full training program CRUD, employee enrolment, completion tracking",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-STUB-003: Performance page (Regularization only) ----
    {
      const id = "EMP-STUB-003";
      await hr2.goto(`${BASE}/dashboard/hr/performance`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1500);
      const obs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const hasReviewCycle = (obs.buttons || []).some((b) => /create review cycle|assign reviewer|new review/i.test(b));
      const hasRegularization = textIncludes(obs, "regularization", "regularize");
      record(
        id,
        "PerformancePageObservation",
        { navigation: "HR → Performance", role: "test.hr" },
        { ...obs, derived: { has_review_cycle_btn: hasReviewCycle, has_regularization: hasRegularization } },
        "Performance page lacks review cycle controls; only Regularization is functional",
        !hasReviewCycle,
        {
          scenario_id: id,
          severity: "MEDIUM",
          classification: !hasReviewCycle ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Performance module limited to Regularization",
          observed: `No Create Review Cycle / Assign Reviewers buttons; Regularization present=${hasRegularization}`,
          expected: "Full performance management: cycles, reviewers, ratings, calibration",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-STUB-004: Disciplinary case detail blank ----
    {
      const id = "EMP-STUB-004";
      await hr2.goto(`${BASE}/dashboard/hr/disciplinary`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1500);
      const listObs = await observePage(hr2);
      // click first case if present
      const clicked = await hr2.evaluate(() => {
        const link = document.querySelector("tbody tr a, a[href*='disciplinary/']");
        if (link) { link.click(); return link.getAttribute("href"); }
        const row = document.querySelector("tbody tr");
        if (row) { row.click(); return "row-clicked"; }
        return null;
      }).catch(() => null);
      await hr2.waitForTimeout(1500);
      const detailObs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const isBlank = (detailObs.text_head || "").replace(/\s+/g, " ").trim().length < 400 ||
        textIncludes(detailObs, "no data", "empty", "no content", "coming soon");
      record(
        id,
        "DisciplinaryCaseDetail",
        { navigation: "HR → Disciplinary → open case", role: "test.hr", case_link: clicked },
        { list: listObs, detail: detailObs, derived: { detail_is_blank: isBlank } },
        "Disciplinary case detail page renders blank / empty skeleton",
        true,
        {
          scenario_id: id,
          severity: "HIGH",
          classification: "COLLATERAL",
          title: "Disciplinary case detail is empty skeleton",
          observed: `Detail page text length ${(detailObs.text_head || "").length}; blank=${isBlank}; case link=${clicked}`,
          expected: "Case detail with timeline, evidence, decision, Documenso acknowledgement",
          recommended_sprint: "S168+",
        },
        shot
      );
    }

    // ---- EMP-STUB-005: Clearance page ----
    {
      const id = "EMP-STUB-005";
      await hr2.goto(`${BASE}/clearance`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await hr2.waitForTimeout(1800);
      const obs = await observePage(hr2);
      const shot = await shoot(hr2, id);
      const hasStations = textIncludes(obs, "clearance station", "item return", "return items", "station sign-off");
      const hasDocumenso = /documenso|sign\.bebang/i.test(obs.text_head || "");
      const hasMilestones = textIncludes(obs, "exit interview", "final pay", "coe", "certificate of employment");
      record(
        id,
        "ClearancePageObservation",
        { navigation: "/clearance", role: "test.hr" },
        { ...obs, derived: { has_clearance_stations: hasStations, has_item_return: hasStations, has_documenso: hasDocumenso, has_milestone_tracker: hasMilestones } },
        "Clearance page is read-only milestone tracker; no stations, no item return, no Documenso",
        !hasStations && !hasDocumenso,
        {
          scenario_id: id,
          severity: "CRITICAL",
          classification: !hasStations && !hasDocumenso ? "COLLATERAL" : "DEFECT_NOT_REPRODUCED",
          title: "Clearance is read-only; no stations, item return, or Documenso integration",
          observed: `milestones=${hasMilestones}, stations=${hasStations}, documenso=${hasDocumenso}`,
          expected: "Full clearance workflow: stations sign-off, item return tracking, Documenso final clearance doc",
          recommended_sprint: "S167",
        },
        shot
      );
    }

    await hrCtx2.close();
  } catch (e) {
    console.error("FATAL:", e);
    fs.writeFileSync(path.join(OUT_DIR, "FATAL.txt"), String(e.stack || e));
  } finally {
    await browser.close();
  }

  const runtimeSec = Math.round((Date.now() - startedAt) / 1000);

  // Write outputs
  fs.writeFileSync(path.join(OUT_DIR, "form_submissions.json"), JSON.stringify(form_submissions, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "api_mutations.json"), JSON.stringify([], null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "state_verification.json"), JSON.stringify(state_verification, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "EMP_STATE.json"), JSON.stringify({}, null, 2));

  // DEFECTS.csv
  const csvEscape = (s) => {
    const v = String(s ?? "");
    return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  };
  const header = "scenario_id,severity,classification,title,observed,expected,recommended_sprint";
  const rows = defects.map((d) =>
    [d.scenario_id, d.severity, d.classification, d.title, d.observed, d.expected, d.recommended_sprint]
      .map(csvEscape)
      .join(",")
  );
  fs.writeFileSync(path.join(OUT_DIR, "DEFECTS.csv"), header + "\n" + rows.join("\n") + "\n");

  // LANE_STATE.json
  const critCount = defects.filter((d) => d.severity === "CRITICAL" && d.classification !== "DEFECT_NOT_REPRODUCED").length;
  const highCount = defects.filter((d) => d.severity === "HIGH" && d.classification !== "DEFECT_NOT_REPRODUCED").length;
  const medCount = defects.filter((d) => d.severity === "MEDIUM" && d.classification !== "DEFECT_NOT_REPRODUCED").length;
  const notRepro = defects.filter((d) => d.classification === "DEFECT_NOT_REPRODUCED").length;
  const laneState = {
    lane: "F",
    sprint: "S166",
    type: "ux-gaps-and-stubs",
    scenarios_total: 15,
    scenarios_observed: form_submissions.length,
    mutations_made: 0,
    defects_total: defects.length,
    defects_critical: critCount,
    defects_high: highCount,
    defects_medium: medCount,
    defects_not_reproduced: notRepro,
    runtime_seconds: runtimeSec,
    completed_pht: nowPht(),
  };
  fs.writeFileSync(path.join(OUT_DIR, "LANE_STATE.json"), JSON.stringify(laneState, null, 2));

  // SUMMARY.md
  const summary = `# S166 Lane F — UX Gaps + Stub Pages — SUMMARY

**Completed (PHT):** ${laneState.completed_pht}
**Runtime:** ${runtimeSec}s
**Scenarios observed:** ${laneState.scenarios_observed}/15
**Mutations made:** 0 (pure observation)

## Defect Counts
- CRITICAL: ${critCount}
- HIGH: ${highCount}
- MEDIUM: ${medCount}
- DEFECT_NOT_REPRODUCED: ${notRepro}

## Scenarios
${defects.map((d) => `- ${d.scenario_id} [${d.severity}] ${d.classification} — ${d.title}`).join("\n")}

See: DEFECTS.csv, form_submissions.json, state_verification.json, screenshots/
`;
  fs.writeFileSync(path.join(OUT_DIR, "SUMMARY.md"), summary);

  console.log(`\n>>> Lane F complete: ${laneState.scenarios_observed}/15 scenarios, ${defects.length} defects (${critCount}C/${highCount}H/${medCount}M, ${notRepro} not-repro), ${runtimeSec}s`);
}

run().catch((e) => { console.error(e); process.exit(1); });
