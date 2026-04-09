/**
 * S167 REDO Phase 1.3 + 1.4 — browser edit + submit batch (continuation).
 */
const { BASE, login, shot, attachNetwork, recordForm, recordDefect, newBrowser } = require("./s167_lib");

(async () => {
  const sref = { current: "p1.3" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "supv");
    console.log("Logged in: test.supervisor@bebang.ph");

    // 1.3 Edit 7-Eleven ₱150 → ₱180 via inline dialog
    sref.current = "1.3";
    console.log("\n[1.3] edit 7-Eleven 150→180 via inline dialog");
    await page.goto(`${BASE}/dashboard/store-ops/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(5000);
    await shot(page, "p1.3_before_edit");

    // Click the edit button for 7-Eleven via aria-label
    const editBtn = page.locator('button[aria-label="Edit expense 7-Eleven"]').first();
    await editBtn.waitFor({ state: "visible", timeout: 10000 });
    await editBtn.click();
    await page.waitForTimeout(2500);
    await shot(page, "p1.3_dialog_open");

    // Dialog amount input
    const dlg = page.locator('[role="dialog"]').first();
    await dlg.waitFor({ state: "visible", timeout: 10000 });
    const amtInput = dlg.locator('input[type="number"]').first();
    await amtInput.click();
    await amtInput.fill("");
    await amtInput.fill("180");
    await shot(page, "p1.3_amount_changed");

    let editResp = null;
    try {
      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("edit_pending_expense"),
        { timeout: 20000 }
      );
      const saveBtn = dlg.getByRole("button", { name: /^save|^update/i }).last();
      await saveBtn.click();
      const r = await waitResp;
      editResp = { status: r.status(), body: (await r.text()).slice(0,1200) };
    } catch (e) { editResp = { status: 0, error: e.message }; recordDefect("1.3_edit", e.message); }
    await page.waitForTimeout(2500);
    await shot(page, "p1.3_after_edit");
    recordForm({ scenario: "1.3_edit", form: "edit_pending_expense", method: "BROWSER inline dialog clicks",
      inputs: { expense: "7-Eleven", old_amount: 150, new_amount: 180 },
      submit_action: "click Edit button → fill 180 → click Save", response: editResp });
    console.log(`  [1.3] ${editResp?.status === 200 ? "PASS" : "FAIL: "+(editResp.error||editResp.body||"").slice(0,200)}`);

    // 1.4 Submit Batch
    sref.current = "1.4";
    console.log("\n[1.4] Submit Batch");
    await page.goto(`${BASE}/dashboard/store-ops/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(4000);
    await shot(page, "p1.4_before_submit");
    let submitResp = null;
    try {
      const submitBtn = page.getByRole("button", { name: /^submit batch$/i }).first();
      await submitBtn.waitFor({ state: "visible", timeout: 12000 });
      const waitSubmit = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("submit_batch_now"),
        { timeout: 25000 }
      );
      await submitBtn.click();
      const r = await waitSubmit;
      submitResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { submitResp = { status: 0, error: e.message }; recordDefect("1.4_submit", e.message); }
    await shot(page, "p1.4_after_submit");
    recordForm({ scenario: "1.4_submit", form: "submit_batch_now_store", method: "BROWSER click Submit Batch",
      inputs: { pcf_fund: "PCF-TEST-STORE-BGC - BEI" },
      submit_action: "click Submit Batch", response: submitResp });
    console.log(`  [1.4] ${submitResp?.status === 200 ? "PASS" : "FAIL: "+(submitResp.error||submitResp.body||"").slice(0,300)}`);
  } finally { await browser.close(); }
  console.log("\n=== Phase 1.3 + 1.4 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
