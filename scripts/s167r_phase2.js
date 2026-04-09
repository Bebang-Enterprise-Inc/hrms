/**
 * S167 REDO Phase 2 — BROWSER-ONLY HR dept lifecycle (single-shot).
 * 2.1a NBS ₱480 | 2.1b Jollibee ₱350 | 2.2 Submit Batch
 */
const { BASE, RECEIPT, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const EXPENSES = [
  { vendor: "National Book Store", description: "Training manual S167", amount: 480, date: "2026-04-08", label: "NBS" },
  { vendor: "Jollibee",            description: "Team meeting snacks S167", amount: 350, date: "2026-04-08", label: "Jollibee" },
];

(async () => {
  const sref = { current: "p2" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "hr");
    console.log("Logged in: test.hr@bebang.ph");

    for (const exp of EXPENSES) {
      sref.current = `2.1_${exp.label}`;
      console.log(`\n[2.1 ${exp.label}] add ${exp.vendor} ₱${exp.amount} via BROWSER`);
      await page.goto(`${BASE}/dashboard/hr-admin/pcf/add`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2500);
      await page.locator('input[name="manual_vendor"]').fill(exp.vendor);
      await page.locator('textarea[name="manual_description"]').fill(exp.description);
      await page.locator('input[name="manual_amount"]').fill(String(exp.amount));
      await page.locator('input[name="manual_date"]').fill(exp.date);
      await page.locator('#pcf_receipt_photo').setInputFiles(RECEIPT);
      await page.waitForTimeout(5500);
      await shot(page, `p2.1_${exp.label}_filled`);
      const waitPost = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("add_expense_to_pending"),
        { timeout: 30000 }
      );
      await page.getByRole("button", { name: /add to pending/i }).click();
      console.log("  CLICK 'Add to Pending'");
      let resp = null;
      try {
        const r = await waitPost;
        resp = { status: r.status(), body: (await r.text()).slice(0, 1000) };
      } catch (e) { resp = { status: 0, error: e.message }; }
      await page.waitForTimeout(2500);
      await shot(page, `p2.1_${exp.label}_after`);
      const passed = resp.status === 200;
      recordForm({ scenario: `2.1_${exp.label}`, form: "add_expense_to_pending_hr", method: "BROWSER UI form clicks",
        inputs: exp, submit_action: "click 'Add to Pending'", response: resp });
      recordState({ scenario: `2.1_${exp.label}`, check: `hr_${exp.label}_BROWSER`,
        before: "pending list", after: passed ? "added" : `error_${resp.status}`, passed });
      console.log(`  [2.1 ${exp.label}] ${passed ? "PASS (BROWSER)" : "FAIL: "+(resp.error||resp.body||"").slice(0,150)}`);
    }

    // 2.2 Submit Batch
    sref.current = "2.2_submit";
    console.log("\n[2.2] Submit Batch via BROWSER");
    await page.goto(`${BASE}/dashboard/hr-admin/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(4500);
    await shot(page, "p2.2_pending");
    const text = await page.evaluate(() => document.body.innerText.slice(0, 4000));
    const hasNBS = /National Book Store/i.test(text);
    const hasJol = /Jollibee/i.test(text);
    const has830 = /₱\s?830|830/.test(text);
    console.log(`  NBS:${hasNBS} Jollibee:${hasJol} ₱830:${has830}`);
    let submitResp = null;
    try {
      const submitBtn = page.getByRole("button", { name: /^submit batch$/i }).first();
      await submitBtn.waitFor({ state: "visible", timeout: 15000 });
      const waitSubmit = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData() || "").includes("submit_batch_now"),
        { timeout: 25000 }
      );
      await submitBtn.click();
      console.log("  CLICK Submit Batch");
      const r = await waitSubmit;
      submitResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) {
      submitResp = { status: 0, error: e.message };
      recordDefect("2.2_submit", e.message);
    }
    console.log(`  submit: ${submitResp.status} ${(submitResp.body||"").slice(0,300)}`);
    await page.waitForTimeout(2500);
    await shot(page, "p2.2_after");
    recordForm({ scenario: "2.2_submit", form: "submit_batch_now_hr", method: "BROWSER UI button click",
      inputs: { pcf_fund: "PCF-HR and Admin" }, submit_action: "click Submit Batch", response: submitResp });
    recordState({ scenario: "2.2_submit", check: "hr_batch_submitted_BROWSER",
      before: "2 pending ₱830", after: submitResp?.status === 200 ? "batch created" : `error_${submitResp?.status||0}`,
      passed: submitResp?.status === 200 });
    console.log(`  [2.2] ${submitResp?.status === 200 ? "PASS (BROWSER)" : "FAIL"}`);
  } finally { await browser.close(); }
  console.log("\n=== Phase 2 BROWSER done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
