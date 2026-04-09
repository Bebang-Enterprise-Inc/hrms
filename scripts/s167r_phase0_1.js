/**
 * S167 REDO Phase 0.1 — BROWSER: sam creates 3 dept funds via admin Create Department Fund dialog.
 * Dept funds were deleted in Phase 6 rollback. Re-creating them browser-only for audit-proof evidence.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

const FUNDS = [
  { dept: "HR and Admin - BEI",   custodian: "test.hr@bebang.ph",         amount: 5000, threshold: 60, label: "HR" },
  { dept: "Supply Chain - BEI",   custodian: "test.warehouse@bebang.ph",  amount: 5000, threshold: 60, label: "SupplyChain" },
  { dept: "Commissary - BEI",     custodian: "test.commissary@bebang.ph", amount: 5000, threshold: 60, label: "Commissary" },
];

(async () => {
  const sref = { current: "p0.1" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "sam");
    console.log("Logged in: sam@bebang.ph");

    for (const f of FUNDS) {
      sref.current = `0.1_${f.label}`;
      console.log(`\n[0.1 ${f.label}] create ${f.dept}`);
      await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(4000);
      await shot(page, `p0.1_${f.label}_admin`);

      // Click "Create Department Fund" button — opens dialog
      const createBtn = page.getByRole("button", { name: /create department fund/i }).first();
      await createBtn.waitFor({ state: "visible", timeout: 15000 });
      await createBtn.click();
      await page.waitForTimeout(2500);
      await shot(page, `p0.1_${f.label}_dialog_open`);

      // Dialog should have a department combobox and inputs
      // Click combobox to open, then search/pick department
      const dialog = page.locator('[role="dialog"]').first();
      await dialog.waitFor({ state: "visible", timeout: 10000 });

      // Dept is a native <select> — use selectOption with real value
      const selectEl = dialog.locator('select').first();
      const selCount = await selectEl.count();
      if (selCount > 0) {
        await selectEl.selectOption({ value: f.dept });
        console.log(`  selected dept via native select`);
      } else {
        // Fallback to shadcn combobox pattern
        const combo = dialog.getByRole("combobox").first();
        await combo.click();
        await page.waitForTimeout(1500);
        const opt = page.getByRole("option", { name: new RegExp(f.dept, "i") }).first();
        await opt.click({ timeout: 8000 });
      }
      await page.waitForTimeout(800);

      // Custodian email
      const custInput = dialog.locator('input[type="email"], input[name*="custodian"]').first();
      await custInput.click();
      await custInput.fill("");
      await custInput.fill(f.custodian);

      // Fund amount + threshold
      const numInputs = dialog.locator('input[type="number"]');
      const nInp = await numInputs.count();
      console.log(`  ${nInp} number inputs in dialog`);
      if (nInp >= 1) { await numInputs.nth(0).click(); await numInputs.nth(0).fill(""); await numInputs.nth(0).fill(String(f.amount)); }
      if (nInp >= 2) { await numInputs.nth(1).click(); await numInputs.nth(1).fill(""); await numInputs.nth(1).fill(String(f.threshold)); }
      await shot(page, `p0.1_${f.label}_filled`);

      // Submit the dialog — click Create/Save
      let createResp = null;
      try {
        const waitResp = page.waitForResponse(
          (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("create_pcf_fund"),
          { timeout: 25000 }
        );
        const submitBtn = dialog.getByRole("button", { name: /^create|^save|^submit/i }).last();
        await submitBtn.click();
        console.log("  CLICK Create (dialog)");
        const r = await waitResp;
        createResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
      } catch (e) { createResp = { status: 0, error: e.message }; recordDefect(`0.1_${f.label}`, e.message); }
      await page.waitForTimeout(2000);
      await shot(page, `p0.1_${f.label}_after_create`);

      // Many create_pcf_fund responses default is_enabled=false — toggle enable via real switch click
      await page.waitForTimeout(2000);
      await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(3500);
      // Find HR/SC/Commi card and click the enable switch
      const cardSelector = `div:has-text("${f.dept.split(" -")[0]} (Department)")`;
      const card = page.locator(cardSelector).filter({ has: page.getByRole('button', { name: /^save$/i }) }).first();
      let enableResp = null;
      try {
        await card.scrollIntoViewIfNeeded();
        const enableSwitch = card.locator('button[role="switch"]').first();
        const state0 = await enableSwitch.getAttribute("data-state").catch(() => null);
        console.log(`  enable switch initial state: ${state0}`);
        if (state0 === "unchecked") {
          await enableSwitch.click();
          await page.waitForTimeout(500);
        }
        const waitSave = page.waitForResponse(
          (r) => r.url().includes("/api/pcf") && r.request().method() === "POST" && (r.request().postData()||"").includes("update_pcf_settings"),
          { timeout: 15000 }
        );
        const saveBtn = card.getByRole("button", { name: /^save$/i }).first();
        await saveBtn.click();
        const r = await waitSave;
        enableResp = { status: r.status(), body: (await r.text()).slice(0, 800) };
      } catch (e) { enableResp = { status: 0, error: e.message }; recordDefect(`0.1_enable_${f.label}`, e.message); }
      await shot(page, `p0.1_${f.label}_enabled`);

      recordForm({ scenario: `0.1_${f.label}`, form: "create_pcf_fund + enable", method: "BROWSER dialog clicks + switch + save",
        inputs: f, submit_action: "combobox pick + fill + Create click → navigate + switch click + Save click",
        response: createResp, enable_response: enableResp });
      recordState({ scenario: `0.1_${f.label}`, check: `fund_${f.label}_created_and_enabled`,
        before: "no fund",
        after: `create:${createResp?.status} enable:${enableResp?.status}`,
        passed: createResp?.status === 200 && enableResp?.status === 200 });
      console.log(`  [0.1 ${f.label}] create:${createResp?.status} enable:${enableResp?.status}`);
    }
  } finally { await browser.close(); }
  console.log("\n=== Phase 0.1 REDO done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
