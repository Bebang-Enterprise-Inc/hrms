/**
 * S167 Phase 2 — HR dept PCF expense lifecycle.
 * As test.hr: add 2 expenses → view pending → submit batch.
 */
const { BASE, RECEIPT, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const EXPENSES = [
  { vendor: "National Book Store", description: "Training manual printouts S167", amount: 480, date: "2026-04-07" },
  { vendor: "Jollibee",             description: "Team meeting snacks S167",       amount: 350, date: "2026-04-07" },
];

async function addExpense(page, exp, scenarioRef, label) {
  scenarioRef.current = `2.1_${label}`;
  console.log(`\n[2.1 ${label}] add ${exp.vendor} ₱${exp.amount}`);
  await page.goto(`${BASE}/dashboard/hr-admin/pcf/add`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2000);

  await page.locator('input[name="manual_vendor"]').fill(exp.vendor);

  // Description field — probe by label
  try {
    await page.getByLabel(/description/i).fill(exp.description);
  } catch (e) {
    // fallback: textarea
    const ta = page.locator("textarea").first();
    await ta.fill(exp.description);
  }
  await page.locator('input[name="manual_amount"]').fill(String(exp.amount));
  await page.locator('input[name="manual_date"]').fill(exp.date);

  // File upload
  await page.locator('input[type="file"]').setInputFiles(RECEIPT);
  await page.waitForTimeout(800);
  await shot(page, `phase2_${label}_form_filled`);

  // Submit
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
  await page.waitForTimeout(1500);
  await shot(page, `phase2_${label}_after_submit`);

  recordForm({
    scenario: `2.1_${label}`,
    form: "add_expense_to_pending_hr",
    inputs: { vendor: exp.vendor, description: exp.description, amount: exp.amount, date: exp.date, receipt: "s167_test_receipt.png" },
    submit_action: "Add to Pending",
    response: result,
  });
  recordState({
    scenario: `2.1_${label}`,
    check: `expense_added_${label}`,
    before: "pending_list",
    after: (result && result.status === 200) ? "added_to_pending" : `error_${result?.status||"unknown"}`,
    passed: !!(result && result.status === 200),
  });
  return result;
}

(async () => {
  const scenarioRef = { current: "phase2" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, scenarioRef);
  try {
    await login(page, "hr");
    console.log("Logged in as test.hr");

    // Get fund name first so subsequent calls can reference it
    const statusRes = await page.evaluate(async () => {
      const r = await fetch("/api/pcf?action=get_pcf_status", { credentials: "include" });
      return await r.text();
    });
    console.log("hr pcf status:", statusRes.slice(0, 400));

    // Task 2.1 — add 2 expenses
    for (let i = 0; i < EXPENSES.length; i++) {
      const e = EXPENSES[i];
      try { await addExpense(page, e, scenarioRef, ["NBS", "Jollibee"][i]); }
      catch (err) {
        recordDefect(`2.1_${i}`, err.message);
        console.log(`  ERROR: ${err.message.slice(0, 200)}`);
        await shot(page, `phase2_${i}_ERROR`);
      }
    }

    // Task 2.2 — view pending + submit batch
    scenarioRef.current = "2.2_submit";
    console.log("\n[2.2] view pending + submit batch");
    await page.goto(`${BASE}/dashboard/hr-admin/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(2500);
    await shot(page, "phase2_pending_list");
    const pendingText = await page.evaluate(() => document.body.innerText.slice(0, 5000));
    console.log("pending text tail:", pendingText.split("\n").slice(-15).join(" | ").slice(0, 400));

    // Submit batch — find button
    const submitBtn = page.getByRole("button", { name: /submit batch/i }).first();
    let submitRes = null;
    try {
      const waitPost = page.waitForResponse(
        (res) => res.url().includes("/api/pcf") && res.request().method() === "POST",
        { timeout: 25000 }
      );
      await submitBtn.click();
      await page.waitForTimeout(1000);
      // Confirmation dialog?
      try {
        const confirm = page.getByRole("button", { name: /confirm|submit|yes/i }).last();
        if (await confirm.isVisible({ timeout: 1500 })) await confirm.click();
      } catch {}
      const r = await waitPost;
      submitRes = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) {
      submitRes = { status: 0, error: e.message };
    }
    await page.waitForTimeout(2000);
    await shot(page, "phase2_after_submit_batch");
    console.log("submit batch result:", submitRes);

    recordForm({
      scenario: "2.2_submit",
      form: "submit_batch_hr",
      inputs: { fund: "PCF-HR and Admin" },
      submit_action: "Submit Batch",
      response: submitRes,
    });
    recordState({
      scenario: "2.2_submit",
      check: "batch_submitted_hr",
      before: "pending_with_2_items",
      after: submitRes?.status === 200 ? "batch_submitted" : `error_${submitRes?.status||"unknown"}`,
      passed: submitRes?.status === 200,
    });
  } finally { await browser.close(); }
  console.log("\n=== Phase 2 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
