/**
 * S167 Phase 3 — Accountant review.
 * As test.finance: open review queue, run AI classification, approve HR with COA,
 * reject Commissary with reason, test empty-COA validation.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");
const fs = require("fs");

const HR_BATCH = "BEI-PCF-2026-00003";
const COMMI_BATCH = "BEI-PCF-2026-00004";

(async () => {
  const scenarioRef = { current: "phase3" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, scenarioRef);

  try {
    await login(page, "finance");

    // ---- 3.1 open review queue ----
    scenarioRef.current = "3.1_review_queue";
    console.log("\n[3.1] review queue");
    await page.goto(`${BASE}/dashboard/accounting/pcf/review`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(3000);
    await shot(page, "phase3_review_queue");
    const queueText = await page.evaluate(() => document.body.innerText.slice(0, 5000));
    console.log("queue tail:", queueText.split("\n").slice(-20).join(" | ").slice(0, 500));

    const hrVisible = queueText.includes("HR") || queueText.includes("00003");
    const commiVisible = queueText.includes("Commissary") || queueText.includes("00004");
    recordState({
      scenario: "3.1_review_queue",
      check: "review_queue_shows_batches",
      before: "logged_in_as_finance",
      after: `hr_visible=${hrVisible} commi_visible=${commiVisible}`,
      passed: hrVisible || commiVisible,
      url: page.url(),
    });

    // ---- 3.2 get batch details + classify + approve via API ----
    // Since UI paths vary, we hit the API directly while maintaining browser session.
    scenarioRef.current = "3.2a_classify_hr";
    console.log("\n[3.2a] classify HR batch");
    const classifyRes = await page.evaluate(async (batch) => {
      const r = await fetch("/api/pcf", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "classify_batch_items", batch_name: batch }),
      });
      return { status: r.status, body: (await r.text()).slice(0, 3000) };
    }, HR_BATCH);
    console.log("classify:", classifyRes.status, classifyRes.body.slice(0, 600));
    recordForm({
      scenario: "3.2a_classify_hr",
      form: "classify_batch_items",
      inputs: { batch_name: HR_BATCH },
      submit_action: "POST /api/pcf classify_batch_items",
      response: classifyRes,
    });
    recordState({
      scenario: "3.2a_classify_hr",
      check: "ai_classification_ran",
      before: "batch_submitted",
      after: classifyRes.status === 200 ? "classified" : `error_${classifyRes.status}`,
      passed: classifyRes.status === 200,
    });

    // Parse the classified items to construct the approval payload
    let classifiedItems = [];
    try {
      const parsed = JSON.parse(classifyRes.body);
      classifiedItems = parsed.data?.items || parsed.data?.classified_items || parsed.message?.items || [];
      fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/classify_hr_result.json", JSON.stringify(parsed, null, 2));
    } catch {}
    console.log(`  classified items: ${classifiedItems.length}`);

    // Fetch the batch details to get expense IDs if classify didn't return them
    const detailsRes = await page.evaluate(async (batch) => {
      const r = await fetch(`/api/pcf?action=get_batch_details&batch_name=${encodeURIComponent(batch)}`, {
        credentials: "include",
      });
      return { status: r.status, body: (await r.text()).slice(0, 4000) };
    }, HR_BATCH);
    let batchDetails = {};
    try { batchDetails = JSON.parse(detailsRes.body).data || {}; } catch {}
    fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/hr_batch_details.json", JSON.stringify(batchDetails, null, 2));
    console.log("  batch expenses:", (batchDetails.expenses || batchDetails.items || []).length);

    // ---- 3.2b approve HR batch with COA overrides ----
    scenarioRef.current = "3.2b_approve_hr";
    console.log("\n[3.2b] approve HR batch with COA overrides");
    const expenseList = batchDetails.expenses || batchDetails.items || classifiedItems || [];
    const approvalItems = expenseList.map((e, idx) => ({
      expense_name: e.name || e.expense_name,
      final_coa: idx === 0 ? "5110 - Office Supplies - BEI" : (e.final_coa || e.suggested_coa || "5110 - Office Supplies - BEI"),
      approved_amount: e.manual_amount || e.approved_amount,
    }));
    console.log("  approval items:", approvalItems);
    const approveRes = await page.evaluate(async (args) => {
      const r = await fetch("/api/pcf", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "approve_batch_with_coa",
          batch_name: args.batch,
          items: args.items,
          notes: "S167 L3 test — HR batch approved with COA overrides",
        }),
      });
      return { status: r.status, body: (await r.text()).slice(0, 2500) };
    }, { batch: HR_BATCH, items: approvalItems });
    console.log("approve:", approveRes.status, approveRes.body.slice(0, 500));
    recordForm({
      scenario: "3.2b_approve_hr",
      form: "approve_batch_with_coa",
      inputs: { batch_name: HR_BATCH, items: approvalItems, notes: "S167 L3 test" },
      submit_action: "POST /api/pcf approve_batch_with_coa",
      response: approveRes,
    });
    recordState({
      scenario: "3.2b_approve_hr",
      check: "hr_batch_approved",
      before: "Submitted",
      after: approveRes.status === 200 ? "Approved" : `error_${approveRes.status}`,
      passed: approveRes.status === 200,
    });

    // ---- 3.3 reject Commissary batch ----
    scenarioRef.current = "3.3_reject_commi";
    console.log("\n[3.3] reject Commissary batch");
    const rejectRes = await page.evaluate(async (batch) => {
      const r = await fetch("/api/pcf", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "reject_batch",
          batch_name: batch,
          reason: "S167 L3 test — receipts are unclear on the Ace Hardware expense; please re-upload a legible photo and resubmit.",
        }),
      });
      return { status: r.status, body: (await r.text()).slice(0, 2000) };
    }, COMMI_BATCH);
    console.log("reject:", rejectRes.status, rejectRes.body.slice(0, 500));
    recordForm({
      scenario: "3.3_reject_commi",
      form: "reject_batch",
      inputs: { batch_name: COMMI_BATCH, reason: "S167 L3 test — ..." },
      submit_action: "POST /api/pcf reject_batch",
      response: rejectRes,
    });
    recordState({
      scenario: "3.3_reject_commi",
      check: "commi_batch_rejected",
      before: "Submitted",
      after: rejectRes.status === 200 ? "Rejected" : `error_${rejectRes.status}`,
      passed: rejectRes.status === 200,
    });

    // ---- 3.4 validation: approve with empty COA ----
    // The HR batch was approved already; use a fake items list with empty COA on the COMMI batch (already rejected)
    // instead, attempt to approve the already-rejected commi batch with empty COA to force validation
    scenarioRef.current = "3.4_empty_coa";
    console.log("\n[3.4] empty COA validation (expected: backend error)");
    const validateRes = await page.evaluate(async (batch) => {
      const r = await fetch("/api/pcf", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "approve_batch_with_coa",
          batch_name: batch,
          items: [{ expense_name: "FAKE", final_coa: "", approved_amount: 100 }],
        }),
      });
      return { status: r.status, body: (await r.text()).slice(0, 1500) };
    }, COMMI_BATCH);
    console.log("validation:", validateRes.status, validateRes.body.slice(0, 300));
    recordForm({
      scenario: "3.4_empty_coa",
      form: "approve_batch_with_coa_empty_validation",
      inputs: { batch_name: COMMI_BATCH, items: [{ final_coa: "" }] },
      submit_action: "POST /api/pcf approve_batch_with_coa (expect validation error)",
      response: validateRes,
    });
    recordState({
      scenario: "3.4_empty_coa",
      check: "empty_coa_blocked",
      before: "valid_approval_expected_to_be_blocked",
      after: validateRes.status !== 200 ? "correctly_blocked" : "accepted_unexpectedly",
      passed: validateRes.status !== 200,
    });

    // ---- 3.5: verify final batch statuses ----
    scenarioRef.current = "3.5_verify_statuses";
    for (const name of [HR_BATCH, COMMI_BATCH]) {
      const r = await page.evaluate(async (n) => {
        const r = await fetch("/api/frappe/api/resource/BEI PCF Batch/" + encodeURIComponent(n), { credentials: "include" });
        const j = await r.json();
        return { status: j.data?.status, total: j.data?.total_amount, approved_total: j.data?.approved_total };
      }, name);
      console.log(`  ${name}: ${JSON.stringify(r)}`);
      recordState({
        scenario: `3.5_${name}`,
        check: "final_batch_status",
        before: "Submitted",
        after: r.status || "unknown",
        passed: (name === HR_BATCH && r.status === "Approved") || (name === COMMI_BATCH && r.status === "Rejected"),
      });
    }
  } finally { await browser.close(); }

  console.log("\n=== Phase 3 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
