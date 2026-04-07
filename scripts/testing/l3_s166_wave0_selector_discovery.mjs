/**
 * S166 Wave 0 — Selector Discovery
 *
 * Visits 37 surfaces across my.bebang.ph as various test roles, captures:
 *   - output/l3/s166/SELECTORS.json                (canonical locator catalog)
 *   - data/_CLEANROOM/.../wave0/dom_dumps/*.html   (innerHTML per surface)
 *   - data/_CLEANROOM/.../wave0/screenshots/*.png  (fullpage screenshot per surface)
 *   - data/_CLEANROOM/.../wave0/discovery_log.txt  (chronological log)
 *
 * HARD CONSTRAINTS:
 *   - No mutations. No form submits. No approve/reject clicks.
 *   - Discovery only: open surface, enumerate, record, close.
 *   - Headless only.
 *   - No commits, no git ops.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { execSync } from "child_process";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";

const REPO = "F:/Dropbox/Projects/BEI-ERP";
const WAVE_DIR = "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/wave0";
const SHOTS_DIR = path.join(WAVE_DIR, "screenshots");
const DUMPS_DIR = path.join(WAVE_DIR, "dom_dumps");
const LOG_FILE = path.join(WAVE_DIR, "discovery_log.txt");
const OUT_FILE = "output/l3/s166/SELECTORS.json";

for (const d of [WAVE_DIR, SHOTS_DIR, DUMPS_DIR, "output/l3/s166"]) {
  fs.mkdirSync(d, { recursive: true });
}

// wipe log
fs.writeFileSync(LOG_FILE, "");

function logLine(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}\n`;
  fs.appendFileSync(LOG_FILE, line);
  process.stdout.write(line);
}

function phtNow() {
  // ISO with +08:00
  const now = new Date();
  const pht = new Date(now.getTime() + 8 * 3600 * 1000);
  return pht.toISOString().replace("Z", "+08:00");
}

function gitSha() {
  try {
    return execSync("git rev-parse HEAD", { cwd: REPO }).toString().trim();
  } catch {
    return "unknown";
  }
}

// ───────────────────────────────────────────────────────────────────
// Surface manifest
// ───────────────────────────────────────────────────────────────────

const SURFACES = [
  // Dialogs / HR master pages (test.hr)
  { id: "EmployeeMasterTable",           role: "test.hr",      route: "/dashboard/hr/employee-master",            kind: "page",   notes: "capture filter/search/row-action selectors" },
  { id: "AddNewEmployeeDialog",          role: "test.hr",      route: "/dashboard/hr/employee-master",            kind: "dialog", trigger: /add new employee/i, notes: "6 comboboxes expected" },
  { id: "EmployeeDetailDialog",          role: "test.hr",      route: "/dashboard/hr/employee-master",            kind: "row-dialog", notes: "covers Personal/Contact/Address/Employment/Photo/Bank/GovID sections" },
  { id: "CompensationSetupPage",         role: "test.hr",      route: "/dashboard/hr/payroll/compensation-setup", kind: "page",   notes: "dynamic [employee] route — try list first, then navigate to first entry" },
  { id: "SensitiveChangesQueue",         role: "test.finance", route: "/dashboard/hr/payroll/sensitive-changes",  kind: "page" },
  { id: "LeaveRequestDialog",            role: "test.crew1",   route: "/dashboard/hr/leave",                       kind: "dialog", trigger: /apply leave|request leave|new leave|\+/i },
  { id: "OvertimeForm_Crew",             role: "test.crew1",   route: "/dashboard/hr/overtime",                    kind: "page" },
  { id: "OvertimeForm_HR",               role: "test.hr",      route: "/dashboard/hr/overtime",                    kind: "page" },
  { id: "AttendanceCorrectionForm",      role: "test.crew1",   route: "/dashboard/hr/attendance-correction",       kind: "page" },
  { id: "RegularizationPage",            role: "test.hr",      route: "/dashboard/hr/performance/regularization",  kind: "page" },
  { id: "TransferCreationForm",          role: "test.hr",      route: "/dashboard/hr/transfers",                   kind: "dialog", trigger: /create transfer|new transfer/i },
  { id: "DisciplinaryCaseForm",          role: "test.hr",      route: "/dashboard/hr/disciplinary",                kind: "dialog", trigger: /create|new case|new/i },
  { id: "DisciplinaryCaseDetail",        role: "test.hr",      route: "/dashboard/hr/disciplinary",                kind: "dynamic-detail", detailPrefix: "/dashboard/hr/disciplinary/" },
  { id: "SeparationsPage",               role: "test.hr",      route: "/dashboard/hr/separations",                 kind: "page" },
  { id: "ClearancePage",                 role: "test.hr",      route: "/clearance",                                kind: "page" },
  { id: "ExitInterviewClearanceRoute",   role: "test.hr",      route: "/clearance/exit-interview",                 kind: "page" },
  { id: "ExitInterviewDashboardRoute",   role: "test.hr",      route: "/dashboard/hr/exit-interview",              kind: "dynamic-detail", detailPrefix: "/dashboard/hr/exit-interview/" },
  { id: "ExitInterviewAnalytics",        role: "test.hr",      route: "/dashboard/hr/exit-interview/analytics",    kind: "page" },
  { id: "PayslipPage",                   role: "test.crew1",   route: "/dashboard/hr/payslip",                     kind: "page" },
  { id: "EnrichmentTracker",             role: "test.hr",      route: "/dashboard/hr/enrichment-tracker",          kind: "page" },
  // UX / stub pages
  { id: "ThirteenthMonthCompliance",     role: "test.hr",      route: "/dashboard/hr/compliance/13th-month",       kind: "page" },
  { id: "PayrollProcessing",             role: "test.hr",      route: "/dashboard/hr/payroll/processing",          kind: "page" },
  { id: "PayrollReviewOutput",           role: "test.hr",      route: "/dashboard/hr/payroll/review-output",       kind: "page" },
  { id: "PayrollRemittances",            role: "test.hr",      route: "/dashboard/hr/payroll/remittances",         kind: "page" },
  { id: "PayrollComparison",             role: "test.hr",      route: "/dashboard/hr/payroll/comparison",          kind: "page" },
  { id: "PayrollHistory",                role: "test.hr",      route: "/dashboard/hr/payroll/history",             kind: "page" },
  { id: "HRReports",                     role: "test.hr",      route: "/dashboard/hr/reports",                     kind: "page" },
  { id: "TrainingPage",                  role: "test.hr",      route: "/dashboard/hr/training",                    kind: "page" },
  { id: "PerformancePage",               role: "test.hr",      route: "/dashboard/hr/performance",                 kind: "page" },
  { id: "AttendancePage",                role: "test.hr",      route: "/dashboard/hr/attendance",                  kind: "page" },
  { id: "SchedulePage",                  role: "test.hr",      route: "/dashboard/hr/schedule",                    kind: "page" },
  { id: "CrewSidebar",                   role: "test.crew1",   route: "/dashboard",                                kind: "sidebar" },
];

// ───────────────────────────────────────────────────────────────────
// Auth
// ───────────────────────────────────────────────────────────────────

async function logout(page) {
  try {
    await page.goto(`${FRAPPE}/api/method/logout`, { timeout: 15000 }).catch(() => {});
    await page.goto(`${BASE}/api/auth/logout`, { timeout: 15000 }).catch(() => {});
    const ctx = page.context();
    await ctx.clearCookies();
  } catch (e) {
    logLine(`  logout warning: ${String(e).slice(0, 120)}`);
  }
}

async function loginAs(page, emailLocal) {
  const email = `${emailLocal}@bebang.ph`;
  logLine(`  logging in as ${email}`);
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  logLine(`  logged in, url=${page.url()}`);
}

// ───────────────────────────────────────────────────────────────────
// Combobox workaround helpers (lifted from spike)
// ───────────────────────────────────────────────────────────────────

async function popoverOpen(page) {
  const ct = await page.locator('[role="listbox"], [cmdk-list], [data-radix-popper-content-wrapper]').count();
  return ct > 0;
}

async function closePopoverIfOpen(page) {
  if (await popoverOpen(page)) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(250);
  }
}

async function enumerateComboboxes(rootLoc, page) {
  const combos = await rootLoc.locator('button[role="combobox"]').all();
  const results = [];
  for (let i = 0; i < combos.length; i++) {
    const c = combos[i];
    const info = await c.evaluate((el) => {
      let p = el.parentElement, lbl = "";
      for (let k = 0; k < 5 && p; k++) {
        const l = p.querySelector("label");
        if (l) { lbl = (l.innerText || "").trim(); break; }
        p = p.parentElement;
      }
      return {
        nearestLabel: lbl,
        ariaLabel: el.getAttribute("aria-label"),
        currentText: (el.innerText || "").trim().slice(0, 80),
        disabled: el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true",
      };
    });
    // Try to open and enumerate options
    let optionsObserved = [];
    let opened = false;
    if (!info.disabled) {
      try {
        await c.click({ force: true, timeout: 3000 });
        await page.waitForTimeout(400);
        if (await popoverOpen(page)) {
          opened = true;
          const opts = await page.locator('[role="option"]').all();
          for (const o of opts.slice(0, 30)) {
            const t = (await o.innerText().catch(() => "")).trim();
            if (t) optionsObserved.push(t.slice(0, 60));
          }
        }
        await closePopoverIfOpen(page);
      } catch (e) {
        await closePopoverIfOpen(page);
      }
    }
    results.push({
      index: i,
      label: info.nearestLabel,
      ariaLabel: info.ariaLabel,
      currentText: info.currentText,
      disabled: info.disabled,
      popoverOpened: opened,
      options_observed: optionsObserved,
      use_workaround: "shadcn_combobox_in_dialog",
    });
  }
  return results;
}

async function enumerateFields(rootLoc) {
  const fields = [];
  const inputs = await rootLoc.locator('input:not([type="hidden"]), textarea, select').all();
  for (const el of inputs) {
    const info = await el.evaluate((node) => {
      const tag = node.tagName.toLowerCase();
      const type = node.getAttribute("type") || tag;
      const name = node.getAttribute("name") || "";
      const id = node.getAttribute("id") || "";
      const placeholder = node.getAttribute("placeholder") || "";
      let lblText = "";
      if (id) {
        const lbl = document.querySelector(`label[for="${id}"]`);
        if (lbl) lblText = (lbl.innerText || "").trim();
      }
      if (!lblText) {
        let p = node.parentElement;
        for (let k = 0; k < 4 && p; k++) {
          const l = p.querySelector("label");
          if (l) { lblText = (l.innerText || "").trim(); break; }
          p = p.parentElement;
        }
      }
      return { tag, type, name, id, placeholder, label: lblText };
    }).catch(() => null);
    if (info) fields.push(info);
  }
  return fields;
}

async function enumerateButtons(rootLoc) {
  const btns = [];
  const all = await rootLoc.locator("button").all();
  for (const el of all.slice(0, 50)) {
    const info = await el.evaluate((node) => {
      return {
        text: (node.innerText || "").trim().slice(0, 60),
        type: node.getAttribute("type") || "button",
        ariaLabel: node.getAttribute("aria-label") || "",
        disabled: node.hasAttribute("disabled") || node.getAttribute("aria-disabled") === "true",
      };
    }).catch(() => null);
    if (info && info.text) btns.push(info);
  }
  return btns;
}

// ───────────────────────────────────────────────────────────────────
// Surface discovery
// ───────────────────────────────────────────────────────────────────

async function captureScreenshotAndDump(page, surfaceId, rootLoc) {
  const shotPath = path.join(SHOTS_DIR, `${surfaceId}.png`);
  const dumpPath = path.join(DUMPS_DIR, `${surfaceId}.html`);
  try {
    await page.screenshot({ path: shotPath, fullPage: true });
  } catch (e) {
    logLine(`  screenshot failed: ${String(e).slice(0, 120)}`);
  }
  try {
    const html = rootLoc
      ? await rootLoc.evaluate((el) => el.outerHTML).catch(() => null)
      : null;
    const fallback = html || await page.content();
    fs.writeFileSync(dumpPath, fallback);
  } catch (e) {
    logLine(`  dump failed: ${String(e).slice(0, 120)}`);
  }
  return {
    screenshot: `${WAVE_DIR}/screenshots/${surfaceId}.png`,
    dom_dump: `${WAVE_DIR}/dom_dumps/${surfaceId}.html`,
  };
}

async function gotoSurface(page, route) {
  const url = `${BASE}${route}`;
  const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1500);
  return resp;
}

async function detectPageState(page) {
  // Look for common "access restricted", "404", "coming soon", skeleton markers
  const body = await page.evaluate(() => document.body?.innerText?.slice(0, 2000) || "").catch(() => "");
  const signals = {
    access_restricted: /access restricted|not authorized|permission denied/i.test(body),
    not_found: /404|not found|page not found/i.test(body),
    coming_soon: /coming soon|under construction|stub/i.test(body),
    empty_state: /no (records|data|results|entries)/i.test(body),
  };
  return { bodyHead: body.slice(0, 400), signals };
}

async function discoverPage(page, surface) {
  const out = {
    surface_id: surface.id,
    category: "page",
    role: surface.role,
    route: surface.route,
    notes: surface.notes || "",
  };
  const resp = await gotoSurface(page, surface.route);
  out.http_status = resp?.status?.() ?? null;
  const state = await detectPageState(page);
  out.page_state = state;
  const root = page.locator("main, [role='main'], body").first();
  out.fields = await enumerateFields(root).catch(() => []);
  out.buttons = await enumerateButtons(root).catch(() => []);
  out.comboboxes_indexed = await enumerateComboboxes(root, page).catch(() => []);
  const files = await captureScreenshotAndDump(page, surface.id, root);
  Object.assign(out, files);
  return out;
}

async function discoverSidebar(page, surface) {
  const out = {
    surface_id: surface.id,
    category: "sidebar",
    role: surface.role,
    route: surface.route,
  };
  await gotoSurface(page, surface.route);
  const nav = page.locator("nav, aside, [role='navigation']").first();
  const items = await nav.evaluate((el) => {
    if (!el) return [];
    const links = Array.from(el.querySelectorAll("a, button"));
    return links.map((a) => ({
      text: (a.innerText || "").trim().slice(0, 60),
      href: a.getAttribute("href") || null,
    })).filter((x) => x.text);
  }).catch(() => []);
  out.nav_items = items;
  const files = await captureScreenshotAndDump(page, surface.id, null);
  Object.assign(out, files);
  return out;
}

async function discoverDialog(page, surface) {
  const out = {
    surface_id: surface.id,
    category: "dialog",
    role: surface.role,
    route: surface.route,
    trigger: { pattern: String(surface.trigger) },
    notes: surface.notes || "",
  };
  const resp = await gotoSurface(page, surface.route);
  out.http_status = resp?.status?.() ?? null;
  const state = await detectPageState(page);
  out.page_state = state;

  // Find trigger button
  let triggerBtn = null;
  try {
    triggerBtn = page.getByRole("button", { name: surface.trigger }).first();
    if ((await triggerBtn.count()) === 0) triggerBtn = null;
  } catch { triggerBtn = null; }

  if (!triggerBtn) {
    // enumerate
    const buttons = await page.locator("button").all();
    for (const b of buttons) {
      const t = (await b.innerText().catch(() => "")).toLowerCase();
      if (surface.trigger.test(t)) { triggerBtn = b; break; }
    }
  }

  if (!triggerBtn) {
    out.discovery_failure = `trigger button not found (pattern ${surface.trigger})`;
    const files = await captureScreenshotAndDump(page, surface.id, null);
    Object.assign(out, files);
    return out;
  }

  try {
    await triggerBtn.waitFor({ state: "visible", timeout: 10000 });
    await triggerBtn.click();
    await page.waitForTimeout(1200);
    await page.locator('[role="dialog"]').first().waitFor({ state: "visible", timeout: 8000 });
  } catch (e) {
    out.discovery_failure = `dialog did not open: ${String(e).slice(0, 160)}`;
    const files = await captureScreenshotAndDump(page, surface.id, null);
    Object.assign(out, files);
    return out;
  }

  const dialog = page.locator('[role="dialog"]').first();
  out.dialog_root = "[role='dialog']";
  out.fields = await enumerateFields(dialog).catch(() => []);
  out.buttons = await enumerateButtons(dialog).catch(() => []);
  out.comboboxes_indexed = await enumerateComboboxes(dialog, page).catch(() => []);

  // capture submit-like button but DO NOT click
  const submitLike = out.buttons.find((b) => /create|save|submit|add|approve|reject|apply/i.test(b.text));
  if (submitLike) out.submit = { label: submitLike.text, note: "NOT clicked during discovery" };

  const files = await captureScreenshotAndDump(page, surface.id, dialog);
  Object.assign(out, files);

  // close dialog
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(400);
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(300);
  return out;
}

async function discoverRowDialog(page, surface) {
  // Employee master row click
  const out = {
    surface_id: surface.id,
    category: "row-dialog",
    role: surface.role,
    route: surface.route,
    notes: surface.notes || "",
  };
  await gotoSurface(page, surface.route);
  // click first table row
  try {
    const row = page.locator("table tbody tr, [role='row']").nth(1);
    await row.waitFor({ state: "visible", timeout: 10000 });
    await row.click();
    await page.waitForTimeout(1500);
    await page.locator('[role="dialog"]').first().waitFor({ state: "visible", timeout: 8000 });
  } catch (e) {
    out.discovery_failure = `row dialog did not open: ${String(e).slice(0, 160)}`;
    const files = await captureScreenshotAndDump(page, surface.id, null);
    Object.assign(out, files);
    return out;
  }
  const dialog = page.locator('[role="dialog"]').first();
  out.dialog_root = "[role='dialog']";
  out.fields = await enumerateFields(dialog).catch(() => []);
  out.buttons = await enumerateButtons(dialog).catch(() => []);
  out.comboboxes_indexed = await enumerateComboboxes(dialog, page).catch(() => []);
  // try to enumerate visible section headings (Personal/Contact/etc)
  out.sections = await dialog.evaluate((el) => {
    const hs = Array.from(el.querySelectorAll("h1,h2,h3,h4,[role='tab'],button"));
    return hs.map((h) => (h.innerText || "").trim()).filter((t) => t && t.length < 60 && /personal|contact|address|employment|photo|bank|gov|id/i.test(t));
  }).catch(() => []);
  const files = await captureScreenshotAndDump(page, surface.id, dialog);
  Object.assign(out, files);
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(400);
  await page.keyboard.press("Escape").catch(() => {});
  return out;
}

async function discoverDynamicDetail(page, surface) {
  const out = {
    surface_id: surface.id,
    category: "dynamic-detail",
    role: surface.role,
    route: surface.route,
    detail_prefix: surface.detailPrefix,
  };
  // visit list first; find first link with detail_prefix
  await gotoSurface(page, surface.route);
  let targetHref = null;
  try {
    targetHref = await page.evaluate((prefix) => {
      const links = Array.from(document.querySelectorAll("a[href]"));
      for (const a of links) {
        const h = a.getAttribute("href") || "";
        if (h.includes(prefix) && h !== prefix && !h.endsWith("/")) return h;
      }
      return null;
    }, surface.detailPrefix);
  } catch {}
  if (!targetHref) {
    out.discovery_failure = `no detail link found under ${surface.detailPrefix} on list page; documenting list state only`;
    const files = await captureScreenshotAndDump(page, surface.id, null);
    Object.assign(out, files);
    return out;
  }
  out.resolved_detail_url = targetHref;
  const resp = await page.goto(targetHref.startsWith("http") ? targetHref : `${BASE}${targetHref}`, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1200);
  out.http_status = resp?.status?.() ?? null;
  const state = await detectPageState(page);
  out.page_state = state;
  const root = page.locator("main, [role='main'], body").first();
  out.fields = await enumerateFields(root).catch(() => []);
  out.buttons = await enumerateButtons(root).catch(() => []);
  out.comboboxes_indexed = await enumerateComboboxes(root, page).catch(() => []);
  const files = await captureScreenshotAndDump(page, surface.id, root);
  Object.assign(out, files);
  return out;
}

// ───────────────────────────────────────────────────────────────────
// Main
// ───────────────────────────────────────────────────────────────────

async function run() {
  const started = Date.now();
  const TIME_BUDGET_MS = 60 * 60 * 1000;

  const catalog = {
    discovered_at: phtNow(),
    discovered_by: "wave0-selector-discovery-agent",
    production_baseline_sha: gitSha(),
    global_workarounds: {
      shadcn_combobox_in_dialog: {
        method: "click_force_true",
        snippet: "await trigger.click({ force: true }); await page.waitForTimeout(400); await page.locator('[role=\"option\"]').filter({ hasText: /^OPTION$/i }).first().click();",
        trigger_locator_strategy: "scope to dialog -> enumerate button[role='combobox'] -> for each, walk up 5 parents to find nearest <label> -> match label text (case-insensitive)",
        verified_on: ["AddNewEmployeeDialog.Gender", "AddNewEmployeeDialog.Branch"],
        source_spike: "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/wave0/COMBOBOX_WORKAROUND.md",
      },
      login_race_condition: {
        pattern: "Login to Frappe (hq.bebang.ph/login) first -> wait networkidle -> navigate to my.bebang.ph/login -> if URL still /login, fill form and submit -> wait for dashboard",
        reference: "scripts/testing/l3_s166_phase0_preconditions.mjs",
      },
      toast_reading: {
        selector: "[data-sonner-toast]",
        wait_after_submit_ms: 1200,
        note: "not exercised in discovery (no submits) — locator provided for execution waves",
      },
    },
    surfaces: [],
    discovery_failures: [],
    summary: { total_surfaces: SURFACES.length, discovered: 0, failures: 0 },
  };

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // Group by role to minimize logins
  const byRole = new Map();
  for (const s of SURFACES) {
    if (!byRole.has(s.role)) byRole.set(s.role, []);
    byRole.get(s.role).push(s);
  }

  try {
    for (const [role, list] of byRole.entries()) {
      if (Date.now() - started > TIME_BUDGET_MS) {
        logLine(`TIME BUDGET EXCEEDED before role ${role}, stopping.`);
        break;
      }
      logLine(`\n====== ROLE ${role} (${list.length} surfaces) ======`);
      await logout(page);
      await loginAs(page, role);
      for (const surface of list) {
        if (Date.now() - started > TIME_BUDGET_MS) {
          logLine(`TIME BUDGET EXCEEDED, stopping mid-role.`);
          break;
        }
        logLine(`\n--- surface: ${surface.id} (${surface.kind}) -> ${surface.route}`);
        let record;
        try {
          if (surface.kind === "page")              record = await discoverPage(page, surface);
          else if (surface.kind === "sidebar")      record = await discoverSidebar(page, surface);
          else if (surface.kind === "dialog")       record = await discoverDialog(page, surface);
          else if (surface.kind === "row-dialog")   record = await discoverRowDialog(page, surface);
          else if (surface.kind === "dynamic-detail") record = await discoverDynamicDetail(page, surface);
          else record = { surface_id: surface.id, discovery_failure: `unknown kind ${surface.kind}` };
        } catch (e) {
          record = {
            surface_id: surface.id,
            category: surface.kind,
            role: surface.role,
            route: surface.route,
            discovery_failure: `exception: ${String(e).slice(0, 300)}`,
          };
          // capture screenshot if possible
          try {
            const files = await captureScreenshotAndDump(page, surface.id, null);
            Object.assign(record, files);
          } catch {}
        }
        catalog.surfaces.push(record);
        if (record.discovery_failure) {
          catalog.discovery_failures.push({
            surface_id: record.surface_id,
            route: record.route,
            reason: record.discovery_failure,
            screenshot: record.screenshot || null,
          });
          catalog.summary.failures += 1;
          logLine(`  FAILURE: ${record.discovery_failure}`);
        } else {
          catalog.summary.discovered += 1;
          logLine(`  OK: fields=${(record.fields||[]).length} buttons=${(record.buttons||[]).length} comboboxes=${(record.comboboxes_indexed||[]).length}`);
        }
        // always attempt to close any stray popover/dialog
        await closePopoverIfOpen(page);
        await page.keyboard.press("Escape").catch(() => {});
      }
    }
  } catch (e) {
    logLine(`FATAL: ${String(e)}`);
  } finally {
    fs.writeFileSync(OUT_FILE, JSON.stringify(catalog, null, 2));
    logLine(`\nwrote ${OUT_FILE}`);
    logLine(`summary: total=${catalog.summary.total_surfaces} discovered=${catalog.summary.discovered} failures=${catalog.summary.failures}`);
    await ctx.close();
    await browser.close();
  }
}

run().catch((e) => { console.error(e); process.exit(1); });
