/**
 * S167 REDO Phase 1 — BROWSER: store PCF lifecycle.
 * 1.1a Mercury Drug ₱250 | 1.1b 7-Eleven ₱150 | 1.1c Globe Telecom ₱299
 * 1.2 custodian fund-wide pending | 1.3 edit 7-Eleven 150→180 | 1.4 submit batch
 */
const { BASE, RECEIPT, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const EXPENSES = [
  { vendor: "Mercury Drug",   description: "Store first aid supplies S167 REDO", amount: 250, date: "2026-04-09", label: "MercuryDrug" },
  { vendor: "7-Eleven",       description: "Snacks for store team S167 REDO",    amount: 150, date: "2026-04-09", label: "7Eleven" },
  { vendor: "Globe Telecom",  description: "Store mobile prepaid S167 REDO",     amount: 299, date: "2026-04-09", label: "Globe" },
];

async function addExpense(page, exp, sref) {
  sref.current = `1.1_${exp.label}`;
  console.log(`\n[1.1 ${exp.label}] add ${exp.vendor} ₱${exp.amount}`);
  await page.goto(`${BASE}/dashboard/store-ops/pcf/add`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(2500);
  await page.locator('input[name="manual_vendor"]').fill(exp.vendor);
  await page.locator('textarea[name="manual_description"]').fill(exp.description);
  await page.locator('input[name="manual_amount"]').fill(String(exp.amount));
  await page.locator('input[name="manual_date"]').fill(exp.date);
  await page.locator('#pcf_receipt_photo').setInputFiles(RECEIPT);
  await page.waitForTimeout(5500);
  await shot(page, `p1.1_${exp.label}_filled`);
  const waitPost = page.waitForResponse(
    (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("add_expense_to_pending"),
    { timeout: 30000 }
  );
  await page.getByRole("button", { name: /add to pending/i }).click();
  let resp = null;
  try { const r = await waitPost; resp = { status: r.status(), body: (await r.text()).slice(0, 1200) }; }
  catch (e) { resp = { status: 0, error: e.message }; }
  await page.waitForTimeout(2500);
  await shot(page, `p1.1_${exp.label}_after`);
  const passed = resp.status === 200;
  recordForm({ scenario: `1.1_${exp.label}`, form: "add_expense_to_pending_store", method: "BROWSER UI form clicks",
    inputs: exp, submit_action: "click 'Add to Pending'", response: resp });
  recordState({ scenario: `1.1_${exp.label}`, check: `store_${exp.label}_added`,
    before: "pending list", after: passed ? "added" : `error_${resp.status}`, passed });
  console.log(`  [1.1 ${exp.label}] ${passed ? "PASS" : "FAIL: " + (resp.error||resp.body||"").slice(0,150)}`);
  return passed;
}

(async () => {
  const sref = { current: "p1" };

  // --- Phase 1.1: test.staff adds 3 expenses ---
  const { browser: b1, page: p1 } = await newBrowser();
  attachNetwork(p1, sref);
  try {
    await login(p1, "staff");
    console.log("Logged in: test.staff@bebang.ph");
    for (const e of EXPENSES) await addExpense(p1, e, sref);
  } finally { await b1.close(); }

  // --- Phase 1.2: test.supervisor sees fund-wide pending ---
  const { browser: b2, page: p2 } = await newBrowser();
  attachNetwork(p2, sref);
  try {
    await login(p2, "supv");
    console.log("\n[1.2] supervisor fund-wide pending view");
    sref.current = "1.2";
    await p2.goto(`${BASE}/dashboard/store-ops/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await p2.waitForTimeout(4500);
    await shot(p2, "p1.2_supv_pending");
    const text = await p2.evaluate(() => document.body.innerText.slice(0, 4000));
    const hasAll3 = /Mercury Drug/i.test(text) && /7-?Eleven/i.test(text) && /Globe/i.test(text);
    const total = /₱\s?699|699/.test(text);
    recordState({ scenario: "1.2_supv_pending", check: "custodian_sees_all_3",
      before: "pending list", after: `all3:${hasAll3} total699:${total}`, passed: hasAll3 });
    console.log(`  all3:${hasAll3} total699:${total}`);

    // --- Phase 1.3: inline edit 7-Eleven ₱150 → ₱180 ---
    sref.current = "1.3";
    console.log("\n[1.3] edit 7-Eleven 150 → 180 via inline dialog");
    await shot(p2, "p1.3_before_edit");
    // Find the 7-Eleven row edit button (pencil icon button adjacent to 150)
    // Strategy: locate row containing "7-Eleven" then click its edit button
    const row = p2.locator('tr,div').filter({ hasText: /7-?Eleven/i }).filter({ hasText: /150/ }).first();
    const editBtn = row.getByRole("button").first();
    // Many card UIs — try a generic Edit search in any 7-Eleven container
    try {
      await editBtn.click({ timeout: 8000 });
    } catch (e) {
      // Fallback: click any button with accessible name edit near 7-Eleven text
      const altEdit = p2.locator('[role="button"]:near(:text("7-Eleven"))').first();
      await altEdit.click({ timeout: 5000 }).catch(()=>{});
    }
    await p2.waitForTimeout(2500);
    await shot(p2, "p1.3_dialog_open");

    // In dialog, amount input → 180
    const dlg = p2.locator('[role="dialog"]').first();
    const amountInput = dlg.locator('input[type="number"], input[name*="amount"]').first();
    await amountInput.click();
    await amountInput.fill("");
    await amountInput.fill("180");
    await shot(p2, "p1.3_amount_changed");

    let editResp = null;
    try {
      const waitResp = p2.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("edit_pending_expense"),
        { timeout: 20000 }
      );
      const saveBtn = dlg.getByRole("button", { name: /^save|^update/i }).last();
      await saveBtn.click();
      const r = await waitResp;
      editResp = { status: r.status(), body: (await r.text()).slice(0,1200) };
    } catch (e) { editResp = { status: 0, error: e.message }; recordDefect("1.3_edit", e.message); }
    await p2.waitForTimeout(2500);
    await shot(p2, "p1.3_after_edit");
    recordForm({ scenario: "1.3_edit", form: "edit_pending_expense", method: "BROWSER inline dialog clicks",
      inputs: { expense: "7-Eleven", old_amount: 150, new_amount: 180 },
      submit_action: "click row edit → fill 180 → click Save", response: editResp });
    console.log(`  [1.3] ${editResp?.status === 200 ? "PASS" : "FAIL: "+(editResp.error||editResp.body||"").slice(0,200)}`);

    // --- Phase 1.4: submit batch ---
    sref.current = "1.4";
    console.log("\n[1.4] Submit Batch");
    await p2.goto(`${BASE}/dashboard/store-ops/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await p2.waitForTimeout(4000);
    await shot(p2, "p1.4_before_submit");
    let submitResp = null;
    try {
      const submitBtn = p2.getByRole("button", { name: /^submit batch$/i }).first();
      await submitBtn.waitFor({ state: "visible", timeout: 12000 });
      const waitSubmit = p2.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("submit_batch_now"),
        { timeout: 25000 }
      );
      await submitBtn.click();
      const r = await waitSubmit;
      submitResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { submitResp = { status: 0, error: e.message }; recordDefect("1.4_submit", e.message); }
    await shot(p2, "p1.4_after_submit");
    recordForm({ scenario: "1.4_submit", form: "submit_batch_now_store", method: "BROWSER click Submit Batch",
      inputs: { pcf_fund: "PCF-TEST-STORE-BGC - BEI" },
      submit_action: "click Submit Batch", response: submitResp });
    console.log(`  [1.4] ${submitResp?.status === 200 ? "PASS" : "FAIL: "+(submitResp.error||submitResp.body||"").slice(0,200)}`);
  } finally { await b2.close(); }

  console.log("\n=== Phase 1 REDO done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
