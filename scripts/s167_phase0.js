/**
 * S167 Phase 0 — Create 3 dept funds + verify 6 account fund resolutions.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

// Dept values match the native <select id="create_department"> options in the admin dialog.
// NOTE: plan specified "HR and Admin - BEI" etc, but UI only offers short labels.
const FUNDS = [
  { dept: "HR",         custodian: "test.hr@bebang.ph",         amount: 5000, threshold: 60, label: "HR" },
  { dept: "Warehouse",  custodian: "test.warehouse@bebang.ph",  amount: 5000, threshold: 60, label: "Warehouse" },
  { dept: "Commissary", custodian: "test.commissary@bebang.ph", amount: 5000, threshold: 60, label: "Commissary" },
];

// Accounts to verify fund resolution for
const VERIFY = [
  { who: "staff",    route: "/dashboard/store-ops/pcf",  expect: /PCF|fund/i },
  { who: "supv",     route: "/dashboard/store-ops/pcf",  expect: /PCF|fund/i },
  { who: "hr",       route: "/dashboard/hr-admin/pcf",   expect: /PCF|HR/i },
  { who: "warehouse",route: "/dashboard/warehouse/pcf",  expect: /PCF|Supply/i },
  { who: "commi",    route: "/dashboard/commissary/pcf", expect: /PCF|Commissary/i },
  { who: "finance",  route: "/dashboard/accounting/pcf", expect: /PCF/i },
];

async function createFund(page, fund, scenarioRef) {
  scenarioRef.current = `0.1_${fund.label}`;
  console.log(`\n[0.1 ${fund.label}] Creating fund for ${fund.dept}`);

  await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2000);

  // Open Create Department Fund dialog
  const createBtn = page.getByRole("button", { name: /create department fund/i }).first();
  await createBtn.waitFor({ timeout: 10000 });
  await createBtn.click();
  await page.waitForTimeout(1200);
  await shot(page, `phase0_${fund.label}_dialog_open`);

  // Dialog open. Probe for Department select (shadcn combobox usually button[role=combobox])
  const dialog = page.getByRole("dialog").first();
  await dialog.waitFor({ timeout: 5000 });

  // Department — native select
  try {
    await page.locator("#create_department").selectOption(fund.dept);
  } catch (e) {
    recordDefect(`0.1_${fund.label}`, `select department failed: ${e.message}`, "");
    await shot(page, `phase0_${fund.label}_dept_fail`);
    return false;
  }
  await page.locator("#create_custodian").fill(fund.custodian);
  await page.locator("#create_fund_amount").fill(String(fund.amount));
  await page.locator("#create_threshold").fill(String(fund.threshold));

  await shot(page, `phase0_${fund.label}_dialog_filled`);

  // Submit — "Create" button in dialog
  const saveBtn = dialog.getByRole("button", { name: /^create$/i }).first();
  await saveBtn.click();

  // Wait for either success toast, dialog close, or error
  let outcome = "unknown";
  try {
    await Promise.race([
      page.waitForSelector('[role="dialog"]', { state: "detached", timeout: 10000 }),
      page.waitForSelector('text=/created|success|saved/i', { timeout: 10000 }),
    ]);
    outcome = "dialog_closed_or_toast";
  } catch { outcome = "timeout"; }

  await page.waitForTimeout(1500);
  await shot(page, `phase0_${fund.label}_after_save`);

  recordForm({
    scenario: `0.1_${fund.label}`,
    form: "create_department_fund",
    inputs: { department: fund.dept, custodian: fund.custodian, fund_amount: fund.amount, threshold_percentage: fund.threshold },
    submit_action: "Save",
    response: outcome,
    screenshot_after: `phase0_${fund.label}_after_save.png`,
  });
  recordState({
    scenario: `0.1_${fund.label}`,
    check: `fund_created_${fund.label}`,
    before: "no dept fund",
    after: outcome,
    passed: outcome !== "timeout",
  });

  return outcome !== "timeout";
}

async function verifyFund(page, v, scenarioRef) {
  scenarioRef.current = `0.2_${v.who}`;
  console.log(`\n[0.2 ${v.who}] GET ${v.route}`);
  await page.goto(`${BASE}${v.route}`, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(2500);
  const body = await page.evaluate(() => document.body.innerText.slice(0, 3000));
  const noFund = /no pcf fund assigned|not configured/i.test(body);
  const hasFund = /₱|php|pending|fund/i.test(body) && !noFund;
  await shot(page, `phase0_verify_${v.who}`);
  recordState({
    scenario: `0.2_${v.who}`,
    check: `fund_resolution_${v.who}`,
    before: "logged_in",
    after: noFund ? "no_pcf_fund_assigned" : "fund_visible",
    passed: !noFund,
    url: page.url(),
  });
  console.log(`  ${v.who}: ${noFund ? "NO FUND" : "OK"}`);
  return !noFund;
}

(async () => {
  const scenarioRef = { current: "boot" };

  // --- Phase 0.1: create 3 dept funds as sam ---
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      await login(page, "sam");
      console.log("Logged in as sam");
      for (const f of FUNDS) {
        try { await createFund(page, f, scenarioRef); }
        catch (e) {
          console.log(`  ERROR ${f.label}:`, e.message);
          recordDefect(`0.1_${f.label}`, e.message, "createFund threw");
          await shot(page, `phase0_${f.label}_ERROR`);
        }
      }
    } finally { await browser.close(); }
  }

  // --- Phase 0.2: verify each account ---
  for (const v of VERIFY) {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      await login(page, v.who);
      await verifyFund(page, v, scenarioRef);
    } catch (e) {
      console.log(`  ERROR verify ${v.who}:`, e.message);
      recordDefect(`0.2_${v.who}`, e.message, "login or verifyFund threw");
    } finally { await browser.close(); }
  }

  console.log("\n=== Phase 0 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
