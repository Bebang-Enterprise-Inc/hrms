/**
 * S167 Phase 3.2b retry — fill Final COA + Approve HR batch (browser).
 * Prereq: suggested_coa cleared via SSM workaround (DEFECT-009).
 */
const { BASE, login, shot, attachNetwork, recordForm, recordDefect, newBrowser } = require("./s167_lib");

const HR_BATCH = "BEI-PCF-2026-00004";
const FINAL_COA = "5100 - Cost of Goods Sold - BEI";

(async () => {
  const sref = { current: "3.2b_retry" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "finance");
    await page.goto(`${BASE}/dashboard/accounting/pcf/review/${HR_BATCH}`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(6000);
    await shot(page, "p3.2b_retry_before");

    const coaInputs = page.locator('input[placeholder="Enter COA code"]');
    const n = await coaInputs.count();
    console.log(`COA inputs: ${n}`);
    for (let i = 0; i < n; i++) {
      const inp = coaInputs.nth(i);
      await inp.click();
      await inp.fill("");
      await inp.fill(FINAL_COA);
      await page.waitForTimeout(250);
    }
    await shot(page, "p3.2b_retry_filled");

    let resp = null;
    try {
      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && (r.request().postData()||"").includes("approve_batch_with_coa"),
        { timeout: 60000 }
      );
      await page.getByRole("button", { name: /approve with coa/i }).first().click();
      await page.waitForTimeout(1500);
      // Dialog confirm
      const dialogBtn = page.locator('[role="dialog"]').getByRole("button", { name: /approve|confirm|yes/i }).last();
      if (await dialogBtn.count()) { try { await dialogBtn.click(); } catch {} }
      const r = await waitResp;
      resp = { status: r.status(), body: (await r.text()).slice(0, 2000) };
    } catch (e) { resp = { status: 0, error: e.message }; recordDefect("3.2b_retry", e.message); }
    await page.waitForTimeout(3000);
    await shot(page, "p3.2b_retry_after");
    recordForm({ scenario: "3.2b_retry", form: "approve_batch_with_coa", method: "BROWSER",
      inputs: { batch_name: HR_BATCH, final_coa: FINAL_COA }, submit_action: "fill 4 COAs + click Approve + confirm", response: resp });
    console.log(`  ${resp?.status === 200 ? "PASS" : "FAIL"}: ${(resp.error||resp.body||"").slice(0,400)}`);
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
