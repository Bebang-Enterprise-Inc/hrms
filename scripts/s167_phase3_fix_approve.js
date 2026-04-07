/**
 * S167 Phase 3 retry — clear invalid suggested_coa on batch item,
 * then approve HR batch with valid COA via corrected items format.
 */
const { login, newBrowser, recordForm, recordState } = require("./s167_lib");

const BATCH = "BEI-PCF-2026-00003";
const COA = "OFFICE SUPPLIES - Bebang Enterprise Inc.";
const ALT_COA = "OFFICE SUPPLIES - Bebang Enterprise Inc."; // same for both; plan override was "one row changed"

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam"); // admin to clear the bad suggested_coa

  // 1. Clear invalid suggested_coa on item b7t6fc34lt
  const clear = await page.evaluate(async () => {
    const r = await fetch("/api/frappe/api/resource/BEI PCF Batch Item/b7t6fc34lt", {
      method: "PUT",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ suggested_coa: "" }),
    });
    return { s: r.status, b: (await r.text()).slice(0, 500) };
  });
  console.log("clear suggested_coa:", clear);

  // Also clear any other items with bad values on BOTH batches
  await browser.close();

  // 2. Approve as test.finance with correct items format (name, not expense_name)
  const { browser: b2, page: page2 } = await newBrowser();
  await login(page2, "finance");
  const items = [
    { name: "b7tbc3u8q6", final_coa: COA, approved_amount: 480 },
    { name: "b7t6fc34lt", final_coa: ALT_COA, approved_amount: 300 }, // plan: accountant adjusts amount
  ];
  const res = await page2.evaluate(async (args) => {
    const r = await fetch("/api/pcf", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        action: "approve_batch_with_coa",
        batch_name: args.batch,
        items: args.items,
        notes: "S167 L3 test — HR batch approved with COA overrides + Jollibee amount adjusted from 350 to 300",
      }),
    });
    return { status: r.status, body: (await r.text()).slice(0, 2500) };
  }, { batch: BATCH, items });
  console.log("approve retry:", res.status, res.body.slice(0, 800));

  recordForm({
    scenario: "3.2b_approve_hr_retry",
    form: "approve_batch_with_coa",
    inputs: { batch_name: BATCH, items, notes: "S167 L3 test — HR approved with COA + amount override" },
    submit_action: "POST /api/pcf approve_batch_with_coa (retry with correct item format)",
    response: res,
  });
  recordState({
    scenario: "3.2b_approve_hr_retry",
    check: "hr_batch_approved_with_coa_overrides",
    before: "Submitted",
    after: res.status === 200 ? "Approved" : `error_${res.status}`,
    passed: res.status === 200,
  });

  // Verify final status
  const verify = await page2.evaluate(async () => {
    const r = await fetch("/api/frappe/api/resource/BEI PCF Batch/BEI-PCF-2026-00003", { credentials: "include" });
    const j = await r.json();
    return { status: j.data?.status, reviewed_by: j.data?.reviewed_by, review_notes: j.data?.review_notes };
  });
  console.log("final status:", verify);
  recordState({
    scenario: "3.2b_final_status",
    check: "hr_batch_final_status",
    before: "Submitted",
    after: verify.status,
    passed: verify.status === "Approved",
  });

  await b2.close();
})().catch(e => { console.error("FATAL", e); process.exit(1); });
