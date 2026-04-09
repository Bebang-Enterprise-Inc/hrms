/**
 * S167 Phase 3 setup — BROWSER: commissary adds 2 expenses + submits batch (reject target).
 */
const { BASE, RECEIPT, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const EXPENSES = [
  { vendor: "SM Supermarket", description: "Commissary cleaning supplies S167", amount: 420, date: "2026-04-09", label: "SM" },
  { vendor: "Puregold",       description: "Commissary packing materials S167", amount: 310, date: "2026-04-09", label: "Puregold" },
];

(async () => {
  const sref = { current: "p3setup" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "commi");
    console.log("Logged in: test.commissary@bebang.ph");

    for (const exp of EXPENSES) {
      sref.current = `3setup_${exp.label}`;
      console.log(`\n[setup ${exp.label}] add ${exp.vendor} ₱${exp.amount}`);
      await page.goto(`${BASE}/dashboard/commissary/pcf/add`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2500);
      await page.locator('input[name="manual_vendor"]').fill(exp.vendor);
      await page.locator('textarea[name="manual_description"]').fill(exp.description);
      await page.locator('input[name="manual_amount"]').fill(String(exp.amount));
      await page.locator('input[name="manual_date"]').fill(exp.date);
      await page.locator('#pcf_receipt_photo').setInputFiles(RECEIPT);
      await page.waitForTimeout(5500);
      await shot(page, `p3setup_${exp.label}_filled`);
      const waitPost = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("add_expense_to_pending"),
        { timeout: 30000 }
      );
      await page.getByRole("button", { name: /add to pending/i }).click();
      let resp = null;
      try { const r = await waitPost; resp = { status: r.status(), body: (await r.text()).slice(0, 1000) }; }
      catch (e) { resp = { status: 0, error: e.message }; }
      await page.waitForTimeout(2500);
      await shot(page, `p3setup_${exp.label}_after`);
      const passed = resp.status === 200;
      recordForm({ scenario: `3setup_${exp.label}`, form: "add_expense_to_pending_commi", method: "BROWSER",
        inputs: exp, submit_action: "click 'Add to Pending'", response: resp });
      console.log(`  ${passed ? "PASS" : "FAIL"}: ${(resp.error||resp.body||"").slice(0,200)}`);
    }

    sref.current = "3setup_submit";
    console.log("\n[setup submit] Submit Commissary Batch");
    await page.goto(`${BASE}/dashboard/commissary/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(4500);
    await shot(page, "p3setup_pending");
    let submitResp = null;
    try {
      const submitBtn = page.getByRole("button", { name: /^submit batch$/i }).first();
      await submitBtn.waitFor({ state: "visible", timeout: 15000 });
      const waitSubmit = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("submit_batch_now"),
        { timeout: 25000 }
      );
      await submitBtn.click();
      const r = await waitSubmit;
      submitResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { submitResp = { status: 0, error: e.message }; recordDefect("3setup_submit", e.message); }
    console.log(`  submit: ${submitResp.status} ${(submitResp.body||"").slice(0,300)}`);
    await shot(page, "p3setup_after");
    recordForm({ scenario: "3setup_submit", form: "submit_batch_now_commi", method: "BROWSER",
      inputs: { pcf_fund: "PCF-Commissary" }, submit_action: "click Submit Batch", response: submitResp });
    console.log(`  ${submitResp?.status === 200 ? "PASS" : "FAIL"}`);
  } finally { await browser.close(); }
  console.log("\n=== Phase 3 setup done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
