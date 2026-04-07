/**
 * S167 Phase 0 via UI — real L3 form submissions.
 * Creates 3 dept funds through the admin dialog and verifies resolution.
 * Tracks created fund names into phase0_created.json for rollback.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");
const fs = require("fs");
const path = require("path");

const FUNDS = [
  { label: "HR",         deptSubstr: /^HR and Admin$|^HR and Admin - BEI$/i, custodian: "test.hr@bebang.ph"        },
  { label: "SupplyChain",deptSubstr: /^Supply Chain - BEI$|^Supply Chain$/i,  custodian: "test.warehouse@bebang.ph" },
  { label: "Commissary", deptSubstr: /^Commissary - BEI$/i,                    custodian: "test.commissary@bebang.ph"},
];

const VERIFY = [
  { who: "staff",    route: "/dashboard/store-ops/pcf"  },
  { who: "supv",     route: "/dashboard/store-ops/pcf"  },
  { who: "hr",       route: "/dashboard/hr-admin/pcf"   },
  { who: "warehouse",route: "/dashboard/warehouse/pcf"  },
  { who: "commi",    route: "/dashboard/commissary/pcf" },
  { who: "finance",  route: "/dashboard/accounting/pcf" },
];

async function chooseBestDept(page, substr) {
  // Get live department list; find first match that isn't already taken
  const list = await page.evaluate(async () => {
    const r = await fetch("/api/pcf?action=list_departments", { credentials: "include" });
    const j = await r.json();
    return (j.data || []).map(x => x.name);
  });
  const match = list.find(n => substr.test(n));
  return match || null;
}

(async () => {
  const scenarioRef = { current: "phase0" };
  const created = [];

  // ---- 0.1 via UI ----
  const { browser, page } = await newBrowser();
  attachNetwork(page, scenarioRef);
  try {
    await login(page, "sam");
    console.log("Logged in as sam");

    for (const f of FUNDS) {
      scenarioRef.current = `0.1_${f.label}`;
      const deptName = await chooseBestDept(page, f.deptSubstr);
      console.log(`\n[0.1 ${f.label}] dept=${deptName}`);
      if (!deptName) {
        recordDefect(`0.1_${f.label}`, `no matching dept found for ${f.deptSubstr}`);
        continue;
      }

      await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2000);
      await page.getByRole("button", { name: /create department fund/i }).first().click();
      await page.waitForTimeout(1000);

      // Wait for the select to populate with live departments (not "Loading...")
      await page.waitForFunction(() => {
        const sel = document.getElementById("create_department");
        if (!sel) return false;
        return sel.options.length > 1 && !sel.options[0].text.toLowerCase().includes("loading");
      }, { timeout: 15000 });

      await page.locator("#create_department").selectOption({ value: deptName });
      await page.locator("#create_custodian").fill(f.custodian);
      await page.locator("#create_fund_amount").fill("5000");
      await page.locator("#create_threshold").fill("60");
      await shot(page, `phase0_${f.label}_dialog_filled`);

      // Capture the create response explicitly
      const waitCreate = page.waitForResponse(
        (res) => res.url().includes("/api/pcf") && res.request().method() === "POST",
        { timeout: 15000 }
      );
      await page.getByRole("dialog").first().getByRole("button", { name: /^create$/i }).click();
      let createResBody = null;
      try {
        const createRes = await waitCreate;
        const status = createRes.status();
        const txt = await createRes.text();
        createResBody = { status, body: txt.slice(0, 2000) };
        console.log(`  create response: ${status} ${txt.slice(0, 200)}`);
      } catch (e) { console.log("  create response wait failed:", e.message); }
      await page.waitForTimeout(1500);
      await shot(page, `phase0_${f.label}_after_save`);

      recordForm({
        scenario: `0.1_${f.label}`,
        form: "create_department_fund",
        inputs: { department: deptName, custodian: f.custodian, fund_amount: 5000, threshold_percentage: 60 },
        submit_action: "Create (dialog button)",
        response: createResBody,
        screenshot_after: `phase0_${f.label}_after_save.png`,
      });
      recordState({
        scenario: `0.1_${f.label}`,
        check: `fund_created_${f.label}`,
        before: "no fund for dept",
        after: createResBody && createResBody.status === 200 ? "created" : `error_${createResBody?.status || "unknown"}`,
        passed: !!(createResBody && createResBody.status === 200),
      });

      if (createResBody && createResBody.status === 200) {
        try {
          const parsed = JSON.parse(createResBody.body);
          created.push({ label: f.label, deptName, custodian: f.custodian, response: parsed });
        } catch {}
      }

      // close any lingering dialog
      try { await page.keyboard.press("Escape"); await page.waitForTimeout(300); } catch {}
    }

    // Discover actual fund names via get_all_pcf_funds
    const allFunds = await page.evaluate(async () => {
      const r = await fetch("/api/pcf?action=get_all_pcf_funds", { credentials: "include" });
      const j = await r.json();
      return j;
    });
    fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/all_funds_after_phase0.json", JSON.stringify(allFunds, null, 2));
    console.log(`\n  Total PCF funds visible to sam: ${Array.isArray(allFunds.data) ? allFunds.data.length : "?"}`);
  } finally { await browser.close(); }

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase0_created_ui.json", JSON.stringify(created, null, 2));
  console.log("\nCreated funds:", created.map(c => c.label).join(", "));

  // ---- 0.2 verification ----
  for (const v of VERIFY) {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = `0.2_${v.who}`;
      await login(page, v.who);
      await page.goto(`${BASE}${v.route}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(3000);
      const text = await page.evaluate(() => document.body.innerText.slice(0, 4000));
      const noFund = /no pcf fund (assigned|configured)|not configured/i.test(text);
      await shot(page, `phase0_verify_${v.who}`);
      recordState({
        scenario: `0.2_${v.who}`,
        check: `fund_resolution_${v.who}`,
        before: "logged_in",
        after: noFund ? "no_pcf_fund_assigned" : "fund_visible",
        passed: !noFund,
        url: page.url(),
      });
      console.log(`  [0.2 ${v.who}] ${noFund ? "NO FUND" : "OK"} url=${page.url()}`);
    } catch (e) {
      recordDefect(`0.2_${v.who}`, e.message);
      console.log(`  [0.2 ${v.who}] ERROR ${e.message}`);
    } finally { await browser.close(); }
  }

  console.log("\n=== Phase 0 (UI) done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
