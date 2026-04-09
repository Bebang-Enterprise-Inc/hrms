/**
 * S167 REDO Phase 3 — Accountant browser review.
 * 3.1 queue renders | 3.2 AI classify + approve HR batch | 3.3 reject Commissary | 3.4 empty-COA validation
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const HR_BATCH = "BEI-PCF-2026-00004";
const COMMI_BATCH = "BEI-PCF-2026-00005";

async function gotoBatch(page, batch) {
  await page.goto(`${BASE}/dashboard/accounting/pcf/review/${batch}`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(5000);
}

(async () => {
  const sref = { current: "p3.1" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "finance");
    console.log("Logged in: test.finance@bebang.ph");

    // 3.1 Queue renders
    sref.current = "3.1_queue";
    console.log("\n[3.1] Review queue renders");
    await page.goto(`${BASE}/dashboard/accounting/pcf/review`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(4000);
    await shot(page, "p3.1_queue");
    const queueText = await page.evaluate(() => document.body.innerText.slice(0, 3000));
    const hasHR = /HR and Admin/.test(queueText);
    const hasCommi = /Commissary/.test(queueText);
    const hasTable = await page.locator('table').count() > 0;
    recordState({ scenario: "3.1_queue", check: "review_queue_renders",
      before: "queue page", after: `HR:${hasHR} Commi:${hasCommi} table:${hasTable}`,
      passed: hasHR && hasCommi && hasTable });
    console.log(`  HR:${hasHR} Commi:${hasCommi} table:${hasTable}`);

    // 3.4 Empty-COA validation FIRST (before we fill COAs in 3.2b)
    sref.current = "3.4_empty_coa";
    console.log("\n[3.4] Empty-COA validation — click Approve without filling COAs");
    await gotoBatch(page, HR_BATCH);
    await shot(page, "p3.4_before");
    const approveBtn = page.getByRole("button", { name: /approve with coa/i }).first();
    let validationFired = false;
    let validationMsg = "";
    try {
      // Listen for dialog/toast OR check if any alert appears
      page.once("dialog", async (d) => { validationMsg = d.message(); validationFired = true; await d.dismiss(); });
      await approveBtn.click();
      await page.waitForTimeout(2500);
      // Check toast / inline error
      const errText = await page.evaluate(() => {
        const toasts = Array.from(document.querySelectorAll('[role="status"], [data-sonner-toast], .toast, [class*="error"]'));
        return toasts.map(t => (t.innerText||"").trim()).filter(Boolean).join(" | ").slice(0, 500);
      });
      if (errText) { validationFired = true; validationMsg = errText; }
    } catch (e) { recordDefect("3.4_empty_coa", e.message); }
    await shot(page, "p3.4_after");
    recordState({ scenario: "3.4_empty_coa", check: "client_validation_blocks_empty_coa",
      before: "empty COA fields", after: validationFired ? `blocked: ${validationMsg}` : "NOT blocked",
      passed: validationFired });
    console.log(`  validation fired: ${validationFired} — ${validationMsg.slice(0,200)}`);

    // 3.2a Run AI Classification
    sref.current = "3.2a_ai_classify";
    console.log("\n[3.2a] Run AI Classification on HR batch");
    await gotoBatch(page, HR_BATCH);
    const classifyBtn = page.getByRole("button", { name: /run ai classification/i }).first();
    let classifyResp = null;
    try {
      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && (r.request().postData()||"").includes("classify_batch_items"),
        { timeout: 60000 }
      );
      await classifyBtn.click();
      const r = await waitResp;
      classifyResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { classifyResp = { status: 0, error: e.message }; recordDefect("3.2a_ai_classify", e.message); }
    await page.waitForTimeout(3000);
    await shot(page, "p3.2a_after");
    recordForm({ scenario: "3.2a_ai_classify", form: "classify_batch_items", method: "BROWSER",
      inputs: { batch_name: HR_BATCH }, submit_action: "click Run AI Classification", response: classifyResp });
    console.log(`  ${classifyResp?.status === 200 ? "PASS" : "FAIL"}: ${(classifyResp.error||classifyResp.body||"").slice(0,200)}`);

    // DEFECT-009 workaround: clear naked COA codes via direct input edit
    // Plan requires editing Final COA via real form controls — do it now.
    sref.current = "3.2b_edit_coa";
    console.log("\n[3.2b] Edit Final COA cells + Approve HR batch");
    // Use a real valid COA account name. We'll use a common one.
    const FINAL_COA = "5100 - Cost of Goods Sold - BEI";
    const coaInputs = page.locator('input[placeholder="Enter COA code"]');
    const nCoa = await coaInputs.count();
    console.log(`  found ${nCoa} COA input cells`);
    for (let i = 0; i < nCoa; i++) {
      const inp = coaInputs.nth(i);
      await inp.click();
      await inp.fill("");
      await inp.fill(FINAL_COA);
      await page.waitForTimeout(250);
    }
    await shot(page, "p3.2b_filled");

    // Click Approve with COA
    let approveResp = null;
    try {
      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && (r.request().postData()||"").includes("approve_batch_with_coa"),
        { timeout: 45000 }
      );
      await page.getByRole("button", { name: /approve with coa/i }).first().click();
      // Confirm dialog may appear
      await page.waitForTimeout(1500);
      const confirmBtn = page.getByRole("button", { name: /^confirm|^yes|^approve$/i }).first();
      if (await confirmBtn.count()) { try { await confirmBtn.click(); } catch {} }
      const r = await waitResp;
      approveResp = { status: r.status(), body: (await r.text()).slice(0, 2000) };
    } catch (e) { approveResp = { status: 0, error: e.message }; recordDefect("3.2b_approve", e.message); }
    await page.waitForTimeout(3000);
    await shot(page, "p3.2b_after");
    recordForm({ scenario: "3.2b_approve", form: "approve_batch_with_coa", method: "BROWSER",
      inputs: { batch_name: HR_BATCH, final_coa: FINAL_COA }, submit_action: "fill COAs + click Approve", response: approveResp });
    console.log(`  ${approveResp?.status === 200 ? "PASS" : "FAIL"}: ${(approveResp.error||approveResp.body||"").slice(0,300)}`);

    // 3.3 Reject Commissary Batch
    sref.current = "3.3_reject";
    console.log("\n[3.3] Reject Commissary batch");
    await gotoBatch(page, COMMI_BATCH);
    await shot(page, "p3.3_before");
    let rejectResp = null;
    try {
      await page.getByRole("button", { name: /reject batch/i }).first().click();
      await page.waitForTimeout(1500);
      // Find textarea for reason
      const reasonInput = page.locator('textarea').filter({ hasNot: page.locator('#review-notes') }).first();
      const anyTextarea = page.locator('textarea[placeholder*="reason" i], textarea[placeholder*="why" i]').first();
      const picked = (await anyTextarea.count()) ? anyTextarea : reasonInput;
      await picked.fill("S167 test reject — Commissary batch rejected as expected test case");
      await shot(page, "p3.3_dialog");
      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && /reject/i.test(r.request().postData()||""),
        { timeout: 30000 }
      );
      // Click confirm/reject button in dialog — pick button whose text includes reject inside dialog role
      const dialogRejectBtn = page.locator('[role="dialog"]').getByRole("button", { name: /reject|confirm|submit/i }).last();
      if (await dialogRejectBtn.count()) { await dialogRejectBtn.click(); }
      else { await page.getByRole("button", { name: /^reject|confirm|submit/i }).last().click(); }
      const r = await waitResp;
      rejectResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { rejectResp = { status: 0, error: e.message }; recordDefect("3.3_reject", e.message); }
    await page.waitForTimeout(3000);
    await shot(page, "p3.3_after");
    recordForm({ scenario: "3.3_reject", form: "reject_batch", method: "BROWSER",
      inputs: { batch_name: COMMI_BATCH }, submit_action: "click Reject + fill reason + confirm", response: rejectResp });
    console.log(`  ${rejectResp?.status === 200 ? "PASS" : "FAIL"}: ${(rejectResp.error||rejectResp.body||"").slice(0,300)}`);

  } finally { await browser.close(); }
  console.log("\n=== Phase 3 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
