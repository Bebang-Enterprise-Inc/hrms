/**
 * S167 Phase 2 continuation — submit HR batch + add Commissary expenses + submit Commissary batch.
 * Both batches needed for Phase 3 (approve HR with COA + reject Commissary).
 */
const { BASE, RECEIPT, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");
const fs = require("fs");

const COMMISSARY_EXPENSES = [
  { vendor: "7-Eleven",  description: "Ice for production chiller S167", amount: 250, date: "2026-04-07" },
  { vendor: "Ace Hardware", description: "Replacement caster wheels S167", amount: 480, date: "2026-04-07" },
];

async function addExpenseUI(page, exp, scenarioRef, label, routePrefix) {
  scenarioRef.current = `commissary_${label}`;
  console.log(`[${label}] add ${exp.vendor} ₱${exp.amount}`);
  await page.goto(`${BASE}${routePrefix}/add`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2000);
  await page.locator('input[name="manual_vendor"]').fill(exp.vendor);
  try {
    await page.getByLabel(/description/i).fill(exp.description);
  } catch {
    await page.locator("textarea").first().fill(exp.description);
  }
  await page.locator('input[name="manual_amount"]').fill(String(exp.amount));
  await page.locator('input[name="manual_date"]').fill(exp.date);
  await page.locator('input[type="file"]').setInputFiles(RECEIPT);
  await page.waitForTimeout(700);
  await shot(page, `phase2_commi_${label}_filled`);
  const waitPost = page.waitForResponse(
    (res) => res.url().includes("/api/pcf") && res.request().method() === "POST",
    { timeout: 25000 }
  );
  await page.getByRole("button", { name: /add to pending/i }).click();
  let result = null;
  try {
    const r = await waitPost;
    result = { status: r.status(), body: (await r.text()).slice(0, 1500) };
  } catch (e) { result = { status: 0, error: e.message }; }
  await page.waitForTimeout(1200);
  recordForm({
    scenario: `2.1_commi_${label}`,
    form: "add_expense_to_pending_commissary",
    inputs: exp,
    submit_action: "Add to Pending",
    response: result,
  });
  recordState({
    scenario: `2.1_commi_${label}`,
    check: `expense_added_${label}`,
    before: "pending_list",
    after: result?.status === 200 ? "added" : `error_${result?.status}`,
    passed: result?.status === 200,
  });
  return result;
}

(async () => {
  const scenarioRef = { current: "phase2b" };
  const batches = [];

  // ---- Submit HR batch via API ----
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = "2.2_hr_submit";
      await login(page, "hr");
      const res = await page.evaluate(async () => {
        const r = await fetch("/api/pcf", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "submit_batch_now", pcf_fund: "PCF-HR and Admin" }),
        });
        return { status: r.status, body: (await r.text()).slice(0, 2000) };
      });
      console.log("HR submit_batch_now:", res.status, res.body.slice(0, 400));
      recordForm({
        scenario: "2.2_hr_submit",
        form: "submit_batch_now_hr",
        inputs: { pcf_fund: "PCF-HR and Admin" },
        submit_action: "POST /api/pcf submit_batch_now",
        response: res,
      });
      recordState({
        scenario: "2.2_hr_submit",
        check: "hr_batch_submitted",
        before: "2_pending_expenses",
        after: res.status === 200 ? "batch_created" : `error_${res.status}`,
        passed: res.status === 200,
      });
      if (res.status === 200) {
        try {
          const parsed = JSON.parse(res.body);
          batches.push({ label: "HR", ...parsed.data?.batch });
        } catch {}
      }
    } finally { await browser.close(); }
  }

  // ---- Add 2 Commissary expenses as test.commissary ----
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = "2.1_commi_setup";
      await login(page, "commi");
      await addExpenseUI(page, COMMISSARY_EXPENSES[0], scenarioRef, "ice", "/dashboard/commissary/pcf");
      await addExpenseUI(page, COMMISSARY_EXPENSES[1], scenarioRef, "wheels", "/dashboard/commissary/pcf");

      // Submit commissary batch via API
      scenarioRef.current = "2.2_commi_submit";
      const res = await page.evaluate(async () => {
        const r = await fetch("/api/pcf", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "submit_batch_now", pcf_fund: "PCF-Commissary" }),
        });
        return { status: r.status, body: (await r.text()).slice(0, 2000) };
      });
      console.log("Commissary submit_batch_now:", res.status, res.body.slice(0, 400));
      recordForm({
        scenario: "2.2_commi_submit",
        form: "submit_batch_now_commissary",
        inputs: { pcf_fund: "PCF-Commissary" },
        submit_action: "POST /api/pcf submit_batch_now",
        response: res,
      });
      recordState({
        scenario: "2.2_commi_submit",
        check: "commi_batch_submitted",
        before: "2_pending_expenses",
        after: res.status === 200 ? "batch_created" : `error_${res.status}`,
        passed: res.status === 200,
      });
      if (res.status === 200) {
        try {
          const parsed = JSON.parse(res.body);
          batches.push({ label: "Commissary", ...parsed.data?.batch });
        } catch {}
      }
    } finally { await browser.close(); }
  }

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/batches.json", JSON.stringify(batches, null, 2));
  console.log("\nBatches created:", batches);
  console.log("=== Phase 2 batches done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
