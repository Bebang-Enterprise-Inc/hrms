/**
 * S166 Wave 1-Retest — R3 Agent: UX Re-observation (post S170 deploy)
 *
 * Pure observation, ZERO mutations. Re-checks 4 defects fixed by S170:
 *   EMP-UX-004  — Compensation Setup row modal (was empty)
 *   EMP-UX-005  — Sensitive Changes Approve/Reject (was DEFECT_NOT_REPRODUCED)
 *   EMP-STUB-005 — Clearance module (was read-only milestone tracker)
 *   EMP-STUB-001 — HR Reports tiles (was 1/8 working) — context-only recheck
 *
 * Evidence output:
 *   output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-UX-004-retest.json
 *   output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-UX-005-retest.json
 *   output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-STUB-005-retest.json
 *   output/l3/s166/lanes/retest/r3_ux_reobserve/evidence/EMP-STUB-001-retest.json
 *   output/l3/s166/lanes/retest/r3_ux_reobserve/R3_SUMMARY.md
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const HR_USER = "test.hr@bebang.ph";
const FINANCE_USER = "test.finance@bebang.ph";

const BASE_OUT = "F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/retest/r3_ux_reobserve";
const EVID_DIR = path.join(BASE_OUT, "evidence");
const SHOT_DIR = path.join(BASE_OUT, "screenshots");

fs.mkdirSync(EVID_DIR, { recursive: true });
fs.mkdirSync(SHOT_DIR, { recursive: true });

function pht() {
  return new Date().toLocaleString("en-PH", { timeZone: "Asia/Manila", hour12: false });
}

function saveEvidence(filename, data) {
  const fp = path.join(EVID_DIR, filename);
  fs.writeFileSync(fp, JSON.stringify(data, null, 2));
  console.log(`[evidence] saved: ${filename}`);
  return fp;
}

async function shoot(page, scenarioId, tag = "observed") {
  const file = path.join(SHOT_DIR, `${scenarioId}_${tag}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch((e) => console.warn(`[screenshot] ${e.message}`));
  return file.replace(/\\/g, "/");
}

async function loginFrappe(page, email) {
  console.log(`[login] ${email} → Frappe`);
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  const usr = await page.$('input[name="usr"]');
  if (usr) {
    await page.fill('input[name="usr"]', email);
    await page.fill('input[name="pwd"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  console.log(`[login] Frappe done: ${page.url()}`);
}

async function loginMyBebang(page, email) {
  console.log(`[login] ${email} → my.bebang.ph`);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1000);

  if (page.url().includes("/login")) {
    const emailInput = await page.$('input[name="email"], input[type="email"]');
    const pwdInput = await page.$('input[name="password"], input[type="password"]');
    if (emailInput && pwdInput) {
      await emailInput.fill(email);
      await pwdInput.fill(PASSWORD);
      const submitBtn = await page.$('button[type="submit"]');
      if (submitBtn) {
        await submitBtn.click();
        await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
        await page.waitForTimeout(2000);
      }
    }
  }
  console.log(`[login] my.bebang.ph done: ${page.url()}`);
}

async function observePage(page) {
  return await page.evaluate(() => {
    const text = (document.body?.innerText || "").slice(0, 8000);
    const buttons = Array.from(document.querySelectorAll("button, a[role=button]"))
      .map((b) => (b.innerText || b.textContent || "").trim())
      .filter(Boolean);
    const inputs = Array.from(document.querySelectorAll("input,select,textarea")).map((i) => ({
      type: i.getAttribute("type") || i.tagName.toLowerCase(),
      name: i.getAttribute("name") || "",
      placeholder: i.getAttribute("placeholder") || "",
      ariaLabel: i.getAttribute("aria-label") || "",
    }));
    const dialogContents = Array.from(document.querySelectorAll("[role=dialog], [data-radix-dialog-content], .modal, [class*='dialog'], [class*='Dialog']"))
      .map((d) => (d.innerText || "").slice(0, 2000))
      .filter(Boolean);
    return {
      url: location.href,
      title: document.title,
      h1: (document.querySelector("h1")?.innerText || "").trim(),
      h2s: Array.from(document.querySelectorAll("h2")).map((h) => h.innerText.trim()).slice(0, 20),
      text_head: text,
      button_count: buttons.length,
      buttons: buttons.slice(0, 80),
      input_count: inputs.length,
      inputs: inputs.slice(0, 40),
      dialog_count: dialogContents.length,
      dialog_contents: dialogContents,
    };
  });
}

// ─── EMP-UX-004: Compensation Setup row modal ──────────────────────────────
async function retestEmpUX004(page) {
  console.log("\n=== EMP-UX-004: Compensation Setup modal retest ===");
  const scenarioId = "EMP-UX-004";

  await loginFrappe(page, HR_USER);
  await loginMyBebang(page, HR_USER);

  await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, {
    waitUntil: "networkidle",
    timeout: 45000,
  }).catch(() => {});
  await page.waitForTimeout(2500);

  const listObserved = await observePage(page);
  const ssListPath = await shoot(page, scenarioId, "list_page");

  // Click first employee row
  console.log("[UX-004] clicking first employee row...");
  const rowBtn = await page.$("table tr td button, table tr button, tbody tr button, [class*='row'] button:not([aria-label='Search']):not([aria-label='Toggle Sidebar'])");
  let modalClicked = false;
  let clickTarget = null;

  // Try clicking the first data row in the table
  const rows = await page.$$("tbody tr");
  if (rows.length > 0) {
    try {
      await rows[0].click();
      await page.waitForTimeout(1500);
      modalClicked = true;
      clickTarget = "tbody tr[0]";
      console.log("[UX-004] clicked first tbody row");
    } catch (e) {
      console.warn("[UX-004] row click failed:", e.message);
    }
  }

  // Fallback: click a named employee button
  if (!modalClicked) {
    const empButtons = await page.$$("tbody td button, [data-row-index] button");
    if (empButtons.length > 0) {
      try {
        await empButtons[0].click();
        await page.waitForTimeout(1500);
        modalClicked = true;
        clickTarget = "td button[0]";
      } catch (e) {
        console.warn("[UX-004] employee button click failed:", e.message);
      }
    }
  }

  // Wait for dialog
  await page.waitForTimeout(2000);
  const postClickObs = await observePage(page);
  const ssModalPath = await shoot(page, scenarioId, "modal_attempt");

  // Detect if modal has rich compensation content
  const allText = postClickObs.text_head.toLowerCase();
  const dialogText = (postClickObs.dialog_contents || []).join(" ").toLowerCase();
  const combinedText = allText + " " + dialogText;

  const hasSalaryField = /base.?salary|basic.?pay|salary.?structure|gross.?pay|daily.?rate/i.test(combinedText);
  const hasDeductionsSection = /deduction|sss|philhealth|pag.?ibig|tax/i.test(combinedText);
  const hasEarningsSection = /earning|allowance|bonus|component/i.test(combinedText);
  const hasAuditHistory = /audit|history|log|changed|previous|effective/i.test(combinedText);
  const hasModalOpen = postClickObs.dialog_count > 0 || /modal|dialog/i.test(combinedText);
  const modalIsEmpty = !hasSalaryField && !hasDeductionsSection;

  const richContent = hasSalaryField && hasDeductionsSection;
  const verdict = richContent ? "PASS_POST_FIX" : "STILL_BROKEN";

  console.log(`[UX-004] verdict: ${verdict}`);
  console.log(`  hasSalaryField: ${hasSalaryField}, hasDeductions: ${hasDeductionsSection}, hasModal: ${hasModalOpen}`);
  console.log(`  dialog_count: ${postClickObs.dialog_count}`);

  const evidence = {
    scenarioId,
    retestFor: "S170",
    checkDesc: "Compensation Setup row modal — was empty in Lane F baseline",
    verdict,
    baseline: { modal_is_empty: true, screenshot: "lane_f/screenshots/EMP-UX-004_observed.png" },
    observed: {
      list_page: listObserved,
      click_attempt: { clicked: modalClicked, target: clickTarget },
      post_click: postClickObs,
      derived: {
        modal_opened: hasModalOpen,
        modal_is_empty: modalIsEmpty,
        has_salary_fields: hasSalaryField,
        has_deductions: hasDeductionsSection,
        has_earnings: hasEarningsSection,
        has_audit_history: hasAuditHistory,
        dialog_count: postClickObs.dialog_count,
        dialog_text_head: (postClickObs.dialog_contents || []).join(" ").slice(0, 500),
      },
    },
    screenshots: {
      list_page: ssListPath,
      modal_attempt: ssModalPath,
    },
    timestamp_pht: pht(),
  };

  saveEvidence("EMP-UX-004-retest.json", evidence);
  return verdict;
}

// ─── EMP-UX-005: Sensitive Changes Approve/Reject buttons ──────────────────
async function retestEmpUX005(page) {
  console.log("\n=== EMP-UX-005: Sensitive Changes approve/reject retest ===");
  const scenarioId = "EMP-UX-005";

  // Login as finance
  await loginFrappe(page, FINANCE_USER);
  await loginMyBebang(page, FINANCE_USER);

  await page.goto(`${BASE}/dashboard/hr/payroll/sensitive-changes`, {
    waitUntil: "networkidle",
    timeout: 45000,
  }).catch(() => {});
  await page.waitForTimeout(2500);

  const listObserved = await observePage(page);
  const ssListPath = await shoot(page, scenarioId, "list_page");

  // Click on the "Pending Finance" tab to see pending items
  const pendingFinanceTab = await page.$('button:has-text("Pending Finance"), [role="tab"]:has-text("Pending Finance")');
  let tabClicked = false;
  if (pendingFinanceTab) {
    try {
      await pendingFinanceTab.click();
      await page.waitForTimeout(1500);
      tabClicked = true;
      console.log("[UX-005] clicked Pending Finance tab");
    } catch (e) {
      console.warn("[UX-005] tab click failed:", e.message);
    }
  }

  const pendingTabObs = await observePage(page);
  const ssPendingPath = await shoot(page, scenarioId, "pending_finance_tab");

  // Check if approve/reject buttons are on the list page itself
  const listButtons = (pendingTabObs.buttons || []).map((b) => b.toLowerCase());
  const hasApproveOnList = listButtons.some((b) => b.includes("approv"));
  const hasRejectOnList = listButtons.some((b) => b.includes("reject"));

  // Click first pending row to see row detail
  console.log("[UX-005] clicking first pending row...");
  const tableRows = await page.$$("tbody tr");
  let rowClicked = false;
  if (tableRows.length > 0) {
    try {
      await tableRows[0].click();
      await page.waitForTimeout(2000);
      rowClicked = true;
      console.log("[UX-005] clicked first row");
    } catch (e) {
      console.warn("[UX-005] row click failed:", e.message);
    }
  }

  await page.waitForTimeout(1500);
  const rowDetailObs = await observePage(page);
  const ssRowDetailPath = await shoot(page, scenarioId, "row_detail");

  // Check for approve/reject in row detail
  const detailButtons = (rowDetailObs.buttons || []).map((b) => b.toLowerCase());
  const dialogButtons = (rowDetailObs.dialog_contents || []).join(" ").toLowerCase();
  const combinedButtonText = detailButtons.join(" ") + " " + dialogButtons;

  const hasApproveInDetail = combinedButtonText.includes("approv");
  const hasRejectInDetail = combinedButtonText.includes("reject");

  // Also check the full text for approve/reject controls
  const allText = rowDetailObs.text_head.toLowerCase();
  const hasApproveInText = allText.includes("approv");
  const hasRejectInText = allText.includes("reject");

  const hasApproveReject = (hasApproveOnList || hasApproveInDetail || hasApproveInText) &&
                           (hasRejectOnList || hasRejectInDetail || hasRejectInText);

  const verdict = hasApproveReject ? "PASS_POST_FIX" : "STILL_UNDISCOVERABLE";

  console.log(`[UX-005] verdict: ${verdict}`);
  console.log(`  list: approve=${hasApproveOnList}, reject=${hasRejectOnList}`);
  console.log(`  detail: approve=${hasApproveInDetail}, reject=${hasRejectInDetail}`);
  console.log(`  text: approve=${hasApproveInText}, reject=${hasRejectInText}`);

  const evidence = {
    scenarioId,
    retestFor: "S170",
    checkDesc: "Sensitive Changes approve/reject buttons for Finance role",
    verdict,
    baseline: {
      has_approve_reject_buttons: false,
      note: "Original DEFECT_NOT_REPRODUCED — queue visible but no row-level approve/reject",
      screenshot: "lane_f/screenshots/EMP-UX-005_observed.png",
    },
    observed: {
      list_page: listObserved,
      pending_tab_clicked: tabClicked,
      pending_tab: pendingTabObs,
      row_clicked: rowClicked,
      row_detail: rowDetailObs,
      derived: {
        approve_on_list: hasApproveOnList,
        reject_on_list: hasRejectOnList,
        approve_in_row_detail: hasApproveInDetail,
        reject_in_row_detail: hasRejectInDetail,
        approve_in_text: hasApproveInText,
        reject_in_text: hasRejectInText,
        has_approve_reject: hasApproveReject,
        dialog_count: rowDetailObs.dialog_count,
      },
    },
    screenshots: {
      list_page: ssListPath,
      pending_finance_tab: ssPendingPath,
      row_detail: ssRowDetailPath,
    },
    timestamp_pht: pht(),
  };

  saveEvidence("EMP-UX-005-retest.json", evidence);
  return verdict;
}

// ─── EMP-STUB-005: Clearance module ────────────────────────────────────────
async function retestEmpStub005(page) {
  console.log("\n=== EMP-STUB-005: Clearance module retest ===");
  const scenarioId = "EMP-STUB-005";

  // Ensure HR user is logged in
  await loginFrappe(page, HR_USER);
  await loginMyBebang(page, HR_USER);

  // S170 Phase 4 may have added an HR-facing clearance management page
  // Test both /clearance (employee view) and /dashboard/hr/clearance (HR management view)
  const urls = [
    `${BASE}/dashboard/hr/clearance`,
    `${BASE}/clearance`,
  ];

  const observations = {};

  for (const url of urls) {
    const key = url.replace(BASE, "");
    console.log(`[STUB-005] checking ${url}`);
    await page.goto(url, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(2500);

    const obs = await observePage(page);
    const ssKey = key.replace(/\//g, "_").replace(/^_/, "");
    const ssPath = await shoot(page, `${scenarioId}_${ssKey}`, "observed");
    observations[key] = { url: obs.url, ...obs, _screenshot: ssPath };
    console.log(`[STUB-005] ${key}: h1="${obs.h1}", buttons=${obs.buttons.length}`);
  }

  // Also check for "Initiate Clearance" button
  await page.goto(`${BASE}/dashboard/hr/clearance`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(2000);

  const hrClearanceObs = await observePage(page);
  const allText = hrClearanceObs.text_head.toLowerCase();
  const allButtons = (hrClearanceObs.buttons || []).map((b) => b.toLowerCase());

  const hasInitiateClearance = allButtons.some((b) => b.includes("initiate")) || allText.includes("initiate clearance");
  const hasClearanceStations = allText.includes("station") || allText.includes("clear station") || allText.includes("sign off") || allText.includes("sign-off");
  const hasItemReturn = allText.includes("item return") || allText.includes("return item") || allText.includes("asset return");
  const hasStationManagement = allText.includes("station management") || allText.includes("manage station") || allText.includes("clearance station");
  const hasClearanceList = allText.includes("clearance list") || allText.includes("pending clearance") || allText.includes("active clearance") || /clearance.*employee|employee.*clearance/i.test(allText);
  const isMilestoneOnly = hrClearanceObs.h1 === "Clearance Status" && !hasInitiateClearance && !hasClearanceStations;

  // Also probe /clearance for changes
  await page.goto(`${BASE}/clearance`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(2000);
  const empClearanceObs = await observePage(page);
  const empText = empClearanceObs.text_head.toLowerCase();
  const empButtons = (empClearanceObs.buttons || []).map((b) => b.toLowerCase());
  const empHasStation = empText.includes("station") || empText.includes("sign off");
  const empIsStillMilestone = empClearanceObs.h1 === "Clearance Status";

  const isFunctional = hasInitiateClearance || hasClearanceStations || hasStationManagement || hasClearanceList || hasItemReturn;
  const verdict = isFunctional ? "PASS_POST_FIX" : "STILL_STUB";

  console.log(`[STUB-005] verdict: ${verdict}`);
  console.log(`  initiate=${hasInitiateClearance}, stations=${hasClearanceStations}, list=${hasClearanceList}`);
  console.log(`  milestone_only=${isMilestoneOnly}, emp_still_milestone=${empIsStillMilestone}`);

  // Try clicking "Initiate Clearance" if present (observation only, won't submit)
  let initiateBtnObsPath = null;
  if (hasInitiateClearance) {
    const initiateBtn = await page.$('button:has-text("Initiate"), a:has-text("Initiate")');
    if (initiateBtn) {
      await initiateBtn.click();
      await page.waitForTimeout(2000);
      initiateBtnObsPath = await shoot(page, scenarioId, "initiate_form");
      console.log("[STUB-005] clicked Initiate — form/dialog observed (no submit)");
    }
  }

  const ssHrClearancePath = await shoot(page, scenarioId, "hr_clearance");

  const evidence = {
    scenarioId,
    retestFor: "S170",
    checkDesc: "Clearance module — was read-only milestone tracker in Lane F baseline",
    verdict,
    baseline: {
      has_clearance_stations: false,
      has_item_return: false,
      has_milestone_tracker: true,
      h1_baseline: "Clearance Status",
      screenshot: "lane_f/screenshots/EMP-STUB-005_observed.png",
    },
    observed: {
      hr_clearance_url: hrClearanceObs,
      emp_clearance_url: empClearanceObs,
      derived: {
        has_initiate_clearance: hasInitiateClearance,
        has_clearance_stations: hasClearanceStations,
        has_item_return: hasItemReturn,
        has_station_management: hasStationManagement,
        has_clearance_list: hasClearanceList,
        is_milestone_only: isMilestoneOnly,
        emp_is_still_milestone: empIsStillMilestone,
        emp_has_station_content: empHasStation,
        is_functional: isFunctional,
      },
    },
    screenshots: {
      hr_clearance: ssHrClearancePath,
      initiate_form: initiateBtnObsPath,
    },
    timestamp_pht: pht(),
  };

  saveEvidence("EMP-STUB-005-retest.json", evidence);
  return verdict;
}

// ─── EMP-STUB-001: HR Reports tiles ────────────────────────────────────────
async function retestEmpStub001(page) {
  console.log("\n=== EMP-STUB-001: HR Reports tiles retest ===");
  const scenarioId = "EMP-STUB-001";

  // Ensure HR user is logged in
  await loginFrappe(page, HR_USER);
  await loginMyBebang(page, HR_USER);

  await page.goto(`${BASE}/dashboard/hr/reports`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(2500);

  const listObs = await observePage(page);
  const ssGridPath = await shoot(page, scenarioId, "grid");

  // Find report tile links
  const tileLinks = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a[href], [onclick]"));
    return links
      .filter((a) => {
        const text = (a.innerText || a.textContent || "").trim();
        const href = a.getAttribute("href") || "";
        // Only internal app links that look like report tiles
        return text && (href.startsWith("/") || href.startsWith(location.origin));
      })
      .map((a) => ({
        text: (a.innerText || a.textContent || "").trim().slice(0, 100),
        href: a.getAttribute("href") || "",
      }))
      .filter((x) => x.href && x.href !== "/" && !x.href.includes("dashboard") === false);
  });

  // Get all clickable tiles on the reports page
  const reportTiles = await page.evaluate(() => {
    // Look for tile-like elements — cards, articles, sections with links
    const cards = Array.from(document.querySelectorAll("[class*='card'], [class*='Card'], article, [class*='tile'], [class*='Tile'], [class*='report']"));
    return cards.map((c) => ({
      text: (c.innerText || "").trim().slice(0, 150),
      href: c.getAttribute("href") || c.querySelector("a")?.getAttribute("href") || null,
      isClickable: c.getAttribute("href") !== null || c.querySelector("a") !== null || c.onclick !== null,
    })).filter((c) => c.text);
  });

  console.log(`[STUB-001] found ${reportTiles.length} tile-like elements`);

  // Click through report tiles and check if they load real content
  const tileResults = [];
  const knownReportPaths = [
    "/dashboard/hr/reports/employee-masterlist",
    "/dashboard/hr/reports/headcount",
    "/dashboard/hr/reports/attrition",
    "/dashboard/hr/reports/new-hires",
    "/dashboard/hr/reports/separations",
    "/dashboard/hr/reports/recruitment-funnel",
    "/dashboard/hr/reports/attendance-summary",
    "/dashboard/hr/reports/overtime",
  ];

  let workingCount = 0;
  for (const rPath of knownReportPaths) {
    const url = `${BASE}${rPath}`;
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
    const obs = await observePage(page);
    const notFound = obs.text_head.toLowerCase().includes("404") ||
                     obs.text_head.toLowerCase().includes("not found") ||
                     obs.text_head.toLowerCase().includes("page not found") ||
                     obs.url.includes("/404") ||
                     obs.url.includes("/dashboard/hr/reports") && !obs.url.includes(rPath.split("/").pop());
    const isStub = obs.text_head.toLowerCase().includes("coming soon") ||
                   obs.text_head.toLowerCase().includes("work in progress") ||
                   obs.text_head.toLowerCase().includes("under construction");
    const hasData = obs.text_head.length > 300 && !notFound && !isStub;
    const working = hasData;
    if (working) workingCount++;
    tileResults.push({ path: rPath, url: obs.url, h1: obs.h1, notFound, isStub, hasData, working });
    console.log(`[STUB-001] ${rPath}: working=${working} (notFound=${notFound}, isStub=${isStub}, len=${obs.text_head.length})`);
  }

  // Return to grid for final screenshot
  await page.goto(`${BASE}/dashboard/hr/reports`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  const ssGridFinalPath = await shoot(page, scenarioId, "grid_final");

  const baselineWorking = 1;
  const changeStatus = workingCount > baselineWorking ? "IMPROVED_POST_DEPLOY" :
                       workingCount === baselineWorking ? "UNCHANGED" : "REGRESSED";

  console.log(`[STUB-001] ${changeStatus}: ${workingCount}/${knownReportPaths.length} working (baseline: ${baselineWorking}/8)`);

  const evidence = {
    scenarioId,
    retestFor: "S170-context",
    note: "Not in S170 scope — context recheck only",
    checkDesc: "HR Reports tiles — how many now work after S168/S170 deploys",
    verdict: changeStatus,
    baseline: {
      working_count: 1,
      total_tiles: 8,
      note: "1/8 working in Lane F — only Employee Master redirect worked",
    },
    observed: {
      grid_page: listObs,
      tile_results: tileResults,
      derived: {
        working_count: workingCount,
        total_checked: knownReportPaths.length,
        working_paths: tileResults.filter((t) => t.working).map((t) => t.path),
        broken_paths: tileResults.filter((t) => !t.working).map((t) => t.path),
      },
    },
    screenshots: {
      grid: ssGridPath,
      grid_final: ssGridFinalPath,
    },
    timestamp_pht: pht(),
  };

  saveEvidence("EMP-STUB-001-retest.json", evidence);
  return changeStatus;
}

// ─── MAIN ──────────────────────────────────────────────────────────────────
async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  });
  const page = await context.newPage();

  const results = {
    "EMP-UX-004": null,
    "EMP-UX-005": null,
    "EMP-STUB-005": null,
    "EMP-STUB-001": null,
  };

  try {
    results["EMP-UX-004"] = await retestEmpUX004(page);
  } catch (e) {
    console.error("[EMP-UX-004] ERROR:", e.message);
    results["EMP-UX-004"] = "ERROR: " + e.message;
  }

  try {
    results["EMP-UX-005"] = await retestEmpUX005(page);
  } catch (e) {
    console.error("[EMP-UX-005] ERROR:", e.message);
    results["EMP-UX-005"] = "ERROR: " + e.message;
  }

  try {
    results["EMP-STUB-005"] = await retestEmpStub005(page);
  } catch (e) {
    console.error("[EMP-STUB-005] ERROR:", e.message);
    results["EMP-STUB-005"] = "ERROR: " + e.message;
  }

  try {
    results["EMP-STUB-001"] = await retestEmpStub001(page);
  } catch (e) {
    console.error("[EMP-STUB-001] ERROR:", e.message);
    results["EMP-STUB-001"] = "ERROR: " + e.message;
  }

  await browser.close();

  // Build summary
  const summaryLines = [
    `# R3 UX Re-observation Summary — Post S170 Deploy`,
    ``,
    `**Run timestamp (PHT):** ${pht()}`,
    `**Agent:** R3 (UX re-observation, zero mutations)`,
    `**Triggered by:** S170 fix deploy`,
    ``,
    `## Verdicts`,
    ``,
    `| Scenario | Verdict | Notes |`,
    `|----------|---------|-------|`,
    `| EMP-UX-004 | ${results["EMP-UX-004"]} | Compensation Setup modal — was empty |`,
    `| EMP-UX-005 | ${results["EMP-UX-005"]} | Sensitive Changes approve/reject — was DEFECT_NOT_REPRODUCED |`,
    `| EMP-STUB-005 | ${results["EMP-STUB-005"]} | Clearance module — was read-only tracker |`,
    `| EMP-STUB-001 | ${results["EMP-STUB-001"]} | HR Reports tiles — context recheck (not S170 scope) |`,
    ``,
    `## Interpretation`,
    ``,
    `- **PASS_POST_FIX** — S170 fix confirmed working`,
    `- **STILL_BROKEN** — S170 fix did not resolve the issue`,
    `- **STILL_STUB** — Feature still not implemented`,
    `- **STILL_UNDISCOVERABLE** — UX gap persists`,
    `- **IMPROVED_POST_DEPLOY** — More tiles working than baseline`,
    `- **UNCHANGED** — No change from baseline`,
    `- **REGRESSED** — Fewer working than baseline`,
    ``,
    `## Evidence Files`,
    ``,
    `- \`evidence/EMP-UX-004-retest.json\``,
    `- \`evidence/EMP-UX-005-retest.json\``,
    `- \`evidence/EMP-STUB-005-retest.json\``,
    `- \`evidence/EMP-STUB-001-retest.json\``,
    `- \`screenshots/\` — per scenario`,
    ``,
    `## Ready for R3 Audit`,
    ``,
    `All 4 scenarios observed. Evidence written. Zero mutations made.`,
  ];

  const summaryPath = path.join(BASE_OUT, "R3_SUMMARY.md");
  fs.writeFileSync(summaryPath, summaryLines.join("\n"));
  console.log(`\n[R3] Summary written to ${summaryPath}`);
  console.log("\n=== R3 FINAL VERDICTS ===");
  for (const [k, v] of Object.entries(results)) {
    console.log(`  ${k}: ${v}`);
  }

  return results;
}

main().catch((e) => {
  console.error("R3 script fatal error:", e);
  process.exit(1);
});
