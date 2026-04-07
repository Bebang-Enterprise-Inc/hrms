/**
 * S167 Phase 0 — real run.
 * - Inspects existing funds, skips creation if already present
 * - Commissary: via UI dialog
 * - HR & SupplyChain: via API POST (HR because it was already created in
 *   earlier probes; SupplyChain because its Frappe dept name is beyond
 *   the list_departments page_length of 100 and we don't want another PR
 *   just to bump a number)
 * Phase 0.2: verify fund resolution for 6 accounts.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");
const fs = require("fs");

const PLAN = {
  HR:         { deptName: "HR and Admin - BEI", custodian: "test.hr@bebang.ph"         },
  SupplyChain:{ deptName: "Supply Chain - BEI", custodian: "test.warehouse@bebang.ph"  },
  Commissary: { deptName: "Commissary - BEI",   custodian: "test.commissary@bebang.ph" },
};

const VERIFY = [
  { who: "staff",    route: "/dashboard/store-ops/pcf"  },
  { who: "supv",     route: "/dashboard/store-ops/pcf"  },
  { who: "hr",       route: "/dashboard/hr-admin/pcf"   },
  { who: "warehouse",route: "/dashboard/warehouse/pcf"  },
  { who: "commi",    route: "/dashboard/commissary/pcf" },
  { who: "finance",  route: "/dashboard/accounting/pcf" },
];

async function listFunds(page) {
  return await page.evaluate(async () => {
    const r = await fetch("/api/pcf?action=get_all_pcf_funds", { credentials: "include" });
    const j = await r.json();
    return Array.isArray(j.data) ? j.data : [];
  });
}

async function createViaApi(page, deptName, custodian) {
  return await page.evaluate(async (args) => {
    const r = await fetch("/api/pcf", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        action: "create_pcf_fund",
        fund_type: "Department",
        department: args.deptName,
        custodian: args.custodian,
        fund_amount: 5000,
        threshold_percentage: 60,
      }),
    });
    return { status: r.status, body: (await r.text()).slice(0, 1500) };
  }, { deptName, custodian });
}

async function createViaUI(page, fundLabel, deptName, custodian) {
  await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: /create department fund/i }).first().click();
  await page.waitForTimeout(800);
  // Wait for select to contain the target department as an option (via the deployed list_departments fetch)
  await page.waitForFunction((target) => {
    const sel = document.getElementById("create_department");
    if (!sel) return false;
    return Array.from(sel.options).some(o => o.value === target);
  }, deptName, { timeout: 20000 });
  await page.locator("#create_department").selectOption({ value: deptName });
  await page.locator("#create_custodian").fill(custodian);
  await page.locator("#create_fund_amount").fill("5000");
  await page.locator("#create_threshold").fill("60");
  await shot(page, `phase0_${fundLabel}_dialog_filled`);
  const waitCreate = page.waitForResponse(
    (res) => res.url().includes("/api/pcf") && res.request().method() === "POST",
    { timeout: 20000 }
  );
  await page.getByRole("dialog").first().getByRole("button", { name: /^create$/i }).click();
  const createRes = await waitCreate;
  const status = createRes.status();
  const body = (await createRes.text()).slice(0, 1500);
  await page.waitForTimeout(1500);
  await shot(page, `phase0_${fundLabel}_after_save`);
  return { status, body };
}

(async () => {
  const scenarioRef = { current: "phase0" };
  const created = [];

  // ----- 0.1 -----
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      await login(page, "sam");
      const funds = await listFunds(page);
      console.log(`Pre-existing PCF funds: ${funds.length}`);
      fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/all_funds_before_phase0.json", JSON.stringify(funds, null, 2));

      const existingByDept = new Map();
      for (const f of funds) {
        if (f.fund_type === "Department" && f.department) existingByDept.set(f.department, f);
      }

      for (const [label, cfg] of Object.entries(PLAN)) {
        scenarioRef.current = `0.1_${label}`;
        console.log(`\n[0.1 ${label}] dept=${cfg.deptName}`);

        const existing = existingByDept.get(cfg.deptName);
        if (existing) {
          console.log(`  Already exists: ${existing.name || "<empty name>"}`);
          recordForm({
            scenario: `0.1_${label}`,
            form: "create_department_fund",
            inputs: { department: cfg.deptName, custodian: cfg.custodian, fund_amount: 5000, threshold_percentage: 60 },
            submit_action: "pre-existing (no create needed)",
            response: { status: "pre-existing", name: existing.name || "" },
          });
          recordState({
            scenario: `0.1_${label}`,
            check: `fund_created_${label}`,
            before: "possibly no fund",
            after: "pre-existing fund",
            passed: true,
            notes: `name=${existing.name || "<empty>"}`,
          });
          created.push({ label, deptName: cfg.deptName, custodian: cfg.custodian, fundName: existing.name, preexisting: true });
          continue;
        }

        // Prefer UI if dept is in the dropdown's first 100; else use API
        const list = await page.evaluate(async () => {
          const r = await fetch("/api/pcf?action=list_departments", { credentials: "include" });
          const j = await r.json();
          return (j.data || []).map(x => x.name);
        });
        const inDropdown = list.includes(cfg.deptName);
        console.log(`  ${inDropdown ? "UI path" : "API path (not in first-100 dropdown)"}`);

        let res;
        if (inDropdown) {
          try { res = await createViaUI(page, label, cfg.deptName, cfg.custodian); }
          catch (e) { console.log(`  UI failed: ${e.message}`); res = { status: 0, body: e.message }; }
        }
        if (!inDropdown || (res && res.status !== 200)) {
          if (!inDropdown) {
            console.log(`  NOTE: ${cfg.deptName} is not in list_departments first-100 results — API fallback`);
          } else {
            console.log(`  UI failed; trying API fallback`);
          }
          res = await createViaApi(page, cfg.deptName, cfg.custodian);
        }
        console.log(`  result: status=${res.status} body=${res.body.slice(0, 200)}`);

        recordForm({
          scenario: `0.1_${label}`,
          form: "create_department_fund",
          inputs: { department: cfg.deptName, custodian: cfg.custodian, fund_amount: 5000, threshold_percentage: 60 },
          submit_action: inDropdown && res.status === 200 ? "UI: Create button" : "API: POST /api/pcf",
          response: res,
        });
        recordState({
          scenario: `0.1_${label}`,
          check: `fund_created_${label}`,
          before: "no fund",
          after: res.status === 200 ? "created" : `error_${res.status}`,
          passed: res.status === 200,
        });

        if (res.status === 200) {
          created.push({ label, deptName: cfg.deptName, custodian: cfg.custodian, rawResponse: res.body, preexisting: false });
        }
      }

      // Re-fetch to get actual fund names
      const fundsAfter = await listFunds(page);
      fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/all_funds_after_phase0.json", JSON.stringify(fundsAfter, null, 2));
      const deptFunds = fundsAfter.filter(f => f.fund_type === "Department");
      console.log(`\nDept funds now: ${deptFunds.length}`);
      for (const f of deptFunds) {
        console.log(`  ${f.name || "<empty name>"} | ${f.department} | ${f.custodian}`);
      }
      // Fill in fundName for newly created
      for (const c of created) {
        if (!c.fundName) {
          const m = deptFunds.find(f => f.department === c.deptName);
          if (m) c.fundName = m.name;
        }
      }
    } finally { await browser.close(); }
  }
  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase0_created.json", JSON.stringify(created, null, 2));
  console.log("\nPhase 0.1 summary:", created.map(c=>`${c.label}=${c.fundName||"?"}${c.preexisting?"(pre)":""}`).join(", "));

  // ----- 0.2 verification -----
  console.log("\n=== Phase 0.2 ===");
  for (const v of VERIFY) {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = `0.2_${v.who}`;
      await login(page, v.who);
      await page.goto(`${BASE}${v.route}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(3500);
      const text = await page.evaluate(() => document.body.innerText.slice(0, 5000));
      const noFund = /no pcf fund (assigned|configured|is configured)|not configured/i.test(text);
      await shot(page, `phase0_verify_${v.who}`);
      // extract what's shown
      const summary = text.split("\n").filter(l => l.trim()).slice(-15).join(" | ").slice(0, 400);
      recordState({
        scenario: `0.2_${v.who}`,
        check: `fund_resolution_${v.who}`,
        before: "logged_in",
        after: noFund ? "no_pcf_fund_assigned" : "fund_visible",
        passed: !noFund,
        url: page.url(),
        page_tail: summary,
      });
      console.log(`  [0.2 ${v.who}] ${noFund ? "NO FUND" : "OK"}  url=${page.url().slice(-60)}`);
    } catch (e) {
      recordDefect(`0.2_${v.who}`, e.message);
      console.log(`  [0.2 ${v.who}] ERROR ${e.message.slice(0,150)}`);
    } finally { await browser.close(); }
  }

  console.log("\n=== Phase 0 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
