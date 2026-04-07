/**
 * S166 Wave 1-Full Blocker Diagnostic
 *
 * Answers 3 questions before dispatching Lane A:
 *   Q1 — EmployeeDetailDialog row trigger (Wave 0 selector failure)
 *   Q2 — Is the Clearance module a stub or functional with separation context?
 *   Q3 — Is Compensation Setup modal broken? Is the per-employee page functional?
 *
 * Read-only. No mutations. Headless.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const OUT_DIR = "output/l3/s166/lanes/wave1_full_diagnostic";
const SHOTS = path.join(OUT_DIR, "screenshots");
const APIS = path.join(OUT_DIR, "api_queries");

fs.mkdirSync(SHOTS, { recursive: true });
fs.mkdirSync(APIS, { recursive: true });

const findings = { q1: {}, q2: {}, q3: {}, started_at: new Date().toISOString() };

async function loginMyBebang(page, email) {
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
}

async function apiGet(page, p) {
  return await page.evaluate(async (path) => {
    try {
      const r = await fetch(path, { headers: { Accept: "application/json" } });
      const text = await r.text();
      let json = null; try { json = JSON.parse(text); } catch {}
      return { ok: r.ok, status: r.status, json, head: text.substring(0, 800) };
    } catch (e) { return { ok: false, error: String(e) }; }
  }, p);
}

async function dialogVisible(page) {
  return await page.locator('[role="dialog"]').count() > 0;
}

// ─────────────────────────────────────────────────────────────────
// Q1 — Find the row trigger that opens EmployeeDetailDialog
// ─────────────────────────────────────────────────────────────────
async function probeQ1(browser) {
  console.log("\n=== Q1: EmployeeDetailDialog row trigger ===");
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();
  await loginMyBebang(page, "test.hr@bebang.ph");
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(8000); // longer wait for TanStack Query to finish
  await page.screenshot({ path: path.join(SHOTS, "q1_employee_master_loaded.png"), fullPage: true });

  // Deep DOM inventory
  const deepInventory = await page.evaluate(() => {
    return {
      tables: document.querySelectorAll("table").length,
      tbody_trs: document.querySelectorAll("tbody tr").length,
      role_rows: document.querySelectorAll('[role="row"]').length,
      data_state_rows: document.querySelectorAll('[data-state]').length,
      buttons_total: document.querySelectorAll("button").length,
      buttons_with_bio: Array.from(document.querySelectorAll("button")).filter(b => /9\d{6}/.test(b.innerText || "")).length,
      first_table_rows: document.querySelectorAll("table tbody tr").length,
      body_text_head: (document.body.innerText || "").substring(0, 1500),
    };
  });
  console.log("  deep inventory:", JSON.stringify(deepInventory).substring(0, 500));
  findings.q1.deep_inventory = deepInventory;

  const attempts = [];
  const tryClick = async (label, fn) => {
    try {
      // dismiss any open dialog first
      await page.keyboard.press("Escape").catch(() => {});
      await page.waitForTimeout(300);
      const before = await dialogVisible(page);
      const result = await fn();
      await page.waitForTimeout(1500);
      const after = await dialogVisible(page);
      const opened = !before && after;
      attempts.push({ label, opened, info: result || null });
      console.log(`  [${opened ? "OPEN" : "----"}] ${label}`);
      if (opened) {
        await page.screenshot({ path: path.join(SHOTS, `q1_${label.replace(/[^a-z0-9]/gi, "_")}_OPENED.png`) });
      }
      return opened;
    } catch (e) {
      attempts.push({ label, opened: false, error: String(e).substring(0, 200) });
      console.log(`  [ERR ] ${label}: ${e.message?.substring(0, 100)}`);
      return false;
    }
  };

  // Inventory row buttons in first data row
  const rowProbe = await page.evaluate(() => {
    const out = { roleRows: 0, dataRowAttrs: [], firstRowButtons: [], firstRowLinks: [], firstRowDataAttrs: {} };
    const rows = Array.from(document.querySelectorAll('[role="row"]'));
    out.roleRows = rows.length;
    if (rows.length > 1) {
      const r = rows[1]; // skip header row
      out.firstRowDataAttrs = Object.fromEntries(
        Array.from(r.attributes).filter(a => a.name.startsWith("data-") || a.name === "role").map(a => [a.name, a.value])
      );
      out.firstRowButtons = Array.from(r.querySelectorAll("button")).map(b => ({
        text: (b.innerText || "").substring(0, 50),
        aria: b.getAttribute("aria-label") || "",
        cls: (b.className || "").substring(0, 80),
      }));
      out.firstRowLinks = Array.from(r.querySelectorAll("a")).map(a => ({
        text: (a.innerText || "").substring(0, 50),
        href: a.getAttribute("href") || "",
      }));
    }
    return out;
  });
  console.log("  row inventory:", JSON.stringify(rowProbe).substring(0, 400));
  findings.q1.row_inventory = rowProbe;

  // Inspect first tbody tr
  const trProbe = await page.evaluate(() => {
    const tr = document.querySelectorAll("tbody tr")[0];
    if (!tr) return null;
    return {
      attrs: Object.fromEntries(Array.from(tr.attributes).map(a => [a.name, a.value])),
      class: tr.className?.substring(0, 200),
      text: (tr.innerText || "").substring(0, 200),
      buttons: Array.from(tr.querySelectorAll("button")).map(b => ({ text: (b.innerText || "").substring(0, 40), aria: b.getAttribute("aria-label") || "" })),
      links: Array.from(tr.querySelectorAll("a")).map(a => ({ text: (a.innerText || "").substring(0, 40), href: a.getAttribute("href") || "" })),
      tds_count: tr.querySelectorAll("td").length,
      first_td_class: tr.querySelector("td")?.className?.substring(0, 200),
    };
  });
  console.log("  first tr probe:", JSON.stringify(trProbe).substring(0, 600));
  findings.q1.first_tr_probe = trProbe;

  // Strategy 1: click first tbody tr
  await tryClick("tbody_tr_first_click", async () => {
    await page.locator('tbody tr').first().click({ timeout: 5000 });
  });

  // Strategy 1a: click the employee-name button inside first row (NOT Actions)
  if (!await dialogVisible(page))
  await tryClick("first_row_name_button", async () => {
    await page.locator('tbody tr').first().locator('button').first().click({ timeout: 5000 });
  });

  // Strategy 1b: click the Actions button
  if (!await dialogVisible(page))
  await tryClick("first_row_actions_button", async () => {
    await page.locator('tbody tr').first().getByRole('button', { name: /actions/i }).click({ timeout: 5000 });
  });

  // Strategy 1b: legacy role row
  if (!await dialogVisible(page))
  await tryClick("role_row_nth1_click", async () => {
    await page.locator('[role="row"]').nth(1).click({ timeout: 5000 });
  });

  if (!await dialogVisible(page)) {
    // Strategy 2: click first cell text within row
    await tryClick("role_row_nth1_cell_click", async () => {
      await page.locator('[role="row"]').nth(1).locator('[role="cell"]').first().click({ timeout: 5000 });
    });
  }

  if (!await dialogVisible(page)) {
    // Strategy 3: click employee name text
    await tryClick("row_text_click", async () => {
      await page.locator('[role="row"]').nth(1).locator('div, span').filter({ hasText: /^9\d{6}$/ }).first().click({ timeout: 5000 });
    });
  }

  if (!await dialogVisible(page)) {
    // Strategy 4: enumerate buttons in first row and try each
    if (rowProbe.firstRowButtons.length > 0) {
      for (let i = 0; i < Math.min(rowProbe.firstRowButtons.length, 5); i++) {
        if (await dialogVisible(page)) break;
        await tryClick(`row_button_idx${i}`, async () => {
          await page.locator('[role="row"]').nth(1).locator("button").nth(i).click({ timeout: 4000 });
        });
      }
    }
  }

  if (!await dialogVisible(page)) {
    // Strategy 5: click on the table row's main clickable div (shadcn data-table cell)
    await tryClick("first_employee_button_text", async () => {
      // Lane F's button list showed entries like "Aaron Jan P. Bautista\n9000746" — these ARE clickable buttons
      await page.getByRole("button", { name: /9\d{6}/ }).first().click({ timeout: 5000 });
    });
  }

  if (!await dialogVisible(page)) {
    // Strategy 6: keyboard nav
    await tryClick("keyboard_tab_enter", async () => {
      await page.locator('[role="row"]').nth(1).focus();
      await page.keyboard.press("Enter");
    });
  }

  findings.q1.attempts = attempts;
  findings.q1.success = attempts.some(a => a.opened);

  if (findings.q1.success) {
    // Inspect what's IN the dialog
    const dialogContent = await page.evaluate(() => {
      const d = document.querySelector('[role="dialog"]');
      if (!d) return null;
      return {
        text_head: (d.innerText || "").substring(0, 1500),
        h2: Array.from(d.querySelectorAll("h2,h3")).map(h => h.innerText),
        buttons: Array.from(d.querySelectorAll("button")).slice(0, 20).map(b => (b.innerText || "").substring(0, 50)),
        tabs: Array.from(d.querySelectorAll('[role="tab"]')).map(t => t.innerText),
        inputs: Array.from(d.querySelectorAll("input")).slice(0, 20).map(i => ({ name: i.name, type: i.type, placeholder: i.placeholder })),
      };
    });
    findings.q1.dialog_content = dialogContent;
  }

  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────
// Q2 — Is Clearance a stub?
// ─────────────────────────────────────────────────────────────────
async function probeQ2(browser) {
  console.log("\n=== Q2: Clearance module ===");
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();
  await loginMyBebang(page, "test.hr@bebang.ph");

  // 2a: separations list
  await page.goto(`${BASE}/dashboard/hr/separations`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, "q2_separations_list.png") });

  const separationsProbe = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("button")).map(b => (b.innerText || "").substring(0, 60)).filter(Boolean);
    const links = Array.from(document.querySelectorAll("a")).map(a => ({ text: (a.innerText || "").substring(0, 60), href: a.getAttribute("href") })).filter(l => l.href && !l.href.startsWith("/dashboard"));
    const rows = document.querySelectorAll('[role="row"]').length;
    const text = (document.body.innerText || "").substring(0, 2500);
    return { button_count: buttons.length, buttons: buttons.slice(0, 30), row_count: rows, text };
  });
  findings.q2.separations_page = separationsProbe;

  // 2b: backend doctype enumeration
  console.log("  enumerating clearance doctypes...");
  const dtSearch = await apiGet(page, "/api/frappe/api/resource/DocType?filters=" + encodeURIComponent('[["name","like","%Clearance%"]]') + "&limit_page_length=50");
  fs.writeFileSync(path.join(APIS, "clearance_doctypes.json"), JSON.stringify(dtSearch, null, 2));
  findings.q2.clearance_doctypes = dtSearch.json?.data || dtSearch;

  const sepDt = await apiGet(page, "/api/frappe/api/resource/DocType?filters=" + encodeURIComponent('[["name","like","%Separation%"]]') + "&limit_page_length=50");
  fs.writeFileSync(path.join(APIS, "separation_doctypes.json"), JSON.stringify(sepDt, null, 2));
  findings.q2.separation_doctypes = sepDt.json?.data || sepDt;

  // 2c: existing BEI Clearance records
  for (const dt of ["BEI Clearance", "Employee Separation", "BEI Employee Separation", "Clearance"]) {
    const r = await apiGet(page, `/api/frappe/api/resource/${encodeURIComponent(dt)}?fields=["name"]&limit_page_length=10`);
    if (r.ok) {
      findings.q2[`records_${dt.replace(/\s/g, "_")}`] = r.json?.data || [];
      fs.writeFileSync(path.join(APIS, `records_${dt.replace(/\s/g, "_")}.json`), JSON.stringify(r, null, 2));
      console.log(`  ${dt}: ${(r.json?.data || []).length} records`);
    }
  }

  // 2d: clearance station / item doctypes
  for (const dt of ["BEI Clearance Station", "BEI Clearance Item", "Clearance Station", "Employee Clearance Station"]) {
    const r = await apiGet(page, `/api/frappe/api/resource/${encodeURIComponent(dt)}?limit_page_length=20`);
    if (r.ok) {
      findings.q2[`stations_${dt.replace(/\s/g, "_")}`] = r.json?.data || [];
      console.log(`  ${dt}: ${(r.json?.data || []).length} records`);
    }
  }

  // 2e: visit /clearance as HR (Lane F said only "Clearance Status" / milestone tracker shown)
  await page.goto(`${BASE}/clearance`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, "q2_clearance_page.png") });
  const clearProbe = await page.evaluate(() => {
    return {
      h1: document.querySelector("h1")?.innerText,
      text: (document.body.innerText || "").substring(0, 2000),
      buttons: Array.from(document.querySelectorAll("button")).map(b => (b.innerText || "").substring(0, 50)).filter(Boolean).slice(0, 30),
      has_stations_word: /station/i.test(document.body.innerText || ""),
      has_documenso_word: /documenso/i.test(document.body.innerText || ""),
      has_item_return: /item.{0,5}return|return.{0,5}item/i.test(document.body.innerText || ""),
    };
  });
  findings.q2.clearance_page_view = clearProbe;

  // 2f: try clicking into an existing separation record if any visible
  const sepLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="/separat"], a[href*="/clearance/"]')).map(a => a.href).slice(0, 10);
  });
  findings.q2.separation_links_seen = sepLinks;

  // Try opening a separation detail
  await page.goto(`${BASE}/dashboard/hr/separations`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2000);
  const firstSepClick = await page.evaluate(() => {
    const rows = document.querySelectorAll('[role="row"]');
    return rows.length;
  });
  if (firstSepClick > 1) {
    try {
      await page.locator('[role="row"]').nth(1).click({ timeout: 4000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: path.join(SHOTS, "q2_separation_detail_opened.png") });
      const detail = await page.evaluate(() => ({
        url: location.href,
        h1: document.querySelector("h1")?.innerText,
        text: (document.body.innerText || "").substring(0, 2500),
      }));
      findings.q2.separation_detail = detail;
    } catch (e) {
      findings.q2.separation_detail_error = String(e).substring(0, 200);
    }
  }

  await ctx.close();
}

// ─────────────────────────────────────────────────────────────────
// Q3 — Compensation modal vs per-employee page
// ─────────────────────────────────────────────────────────────────
async function probeQ3(browser) {
  console.log("\n=== Q3: Compensation Setup ===");
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();
  await loginMyBebang(page, "test.hr@bebang.ph");

  // 3a: list page
  await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(SHOTS, "q3_comp_list.png") });

  // Try clicking first employee row button
  let modalContent = null;
  try {
    await page.getByRole("button", { name: /9\d{6}/ }).first().click({ timeout: 5000 });
    await page.waitForTimeout(2000);
    const isDialog = await page.locator('[role="dialog"]').count() > 0;
    if (isDialog) {
      await page.screenshot({ path: path.join(SHOTS, "q3_comp_list_modal.png") });
      modalContent = await page.evaluate(() => {
        const d = document.querySelector('[role="dialog"]');
        return {
          text: (d.innerText || "").substring(0, 2000),
          inputs: Array.from(d.querySelectorAll("input")).map(i => ({ name: i.name, placeholder: i.placeholder, type: i.type })),
          buttons: Array.from(d.querySelectorAll("button")).map(b => (b.innerText || "").substring(0, 50)),
          h2: Array.from(d.querySelectorAll("h2,h3")).map(h => h.innerText),
        };
      });
    } else {
      // maybe it navigated
      modalContent = { navigated_to: page.url() };
      await page.screenshot({ path: path.join(SHOTS, "q3_comp_list_navigated.png") });
    }
  } catch (e) {
    modalContent = { error: String(e).substring(0, 200) };
  }
  findings.q3.list_click_result = modalContent;

  // 3b: per-employee page direct
  // Get an employee ID first
  const empList = await apiGet(page, '/api/frappe/api/resource/Employee?fields=["name","employee_name"]&filters=' + encodeURIComponent('[["status","=","Active"]]') + '&limit_page_length=3');
  const sampleEmp = empList.json?.data?.[0]?.name;
  findings.q3.sample_employee = sampleEmp;

  if (sampleEmp) {
    await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup/${encodeURIComponent(sampleEmp)}`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(8000);
    await page.screenshot({ path: path.join(SHOTS, "q3_comp_per_employee.png"), fullPage: true });

    const perEmpProbe = await page.evaluate(() => {
      const text = (document.body.innerText || "").substring(0, 4000);
      return {
        url: location.href,
        h1: document.querySelector("h1")?.innerText,
        text,
        button_count: document.querySelectorAll("button").length,
        buttons: Array.from(document.querySelectorAll("button")).map(b => (b.innerText || "").substring(0, 50)).filter(Boolean).slice(0, 50),
        input_count: document.querySelectorAll("input").length,
        inputs: Array.from(document.querySelectorAll("input")).map(i => ({ name: i.name, placeholder: i.placeholder, type: i.type })).slice(0, 30),
        has_salary_structure: /salary.structure/i.test(text),
        has_basic_pay: /basic.pay|base.salary|monthly.rate/i.test(text),
        has_allowance: /allowance/i.test(text),
        has_earnings: /earning/i.test(text),
        has_deductions: /deduction/i.test(text),
        has_save_button: /^save$/i.test(Array.from(document.querySelectorAll("button")).map(b => (b.innerText || "").trim()).join("|")),
        has_404: /404|not found|page not found/i.test(text),
      };
    });
    findings.q3.per_employee_page = perEmpProbe;
  }

  await ctx.close();
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  try {
    await probeQ1(browser);
    await probeQ2(browser);
    await probeQ3(browser);
  } catch (e) {
    findings.fatal = String(e);
    console.error("FATAL", e);
  } finally {
    await browser.close();
  }
  findings.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(OUT_DIR, "findings.json"), JSON.stringify(findings, null, 2));
  console.log("\n>>> wrote", path.join(OUT_DIR, "findings.json"));
  console.log("Q1 row trigger found:", findings.q1.success);
  console.log("Q2 clearance doctypes:", Array.isArray(findings.q2.clearance_doctypes) ? findings.q2.clearance_doctypes.length : "ERR");
  console.log("Q3 per-employee page has fields:", findings.q3.per_employee_page?.has_salary_structure || findings.q3.per_employee_page?.has_basic_pay);
}

run().catch(e => { console.error(e); process.exit(1); });
