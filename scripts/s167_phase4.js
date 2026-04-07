/**
 * S167 Phase 4 — Admin edit HR fund ₱8k / 70%, verify test.hr sees the change.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, newBrowser } = require("./s167_lib");

(async () => {
  const scenarioRef = { current: "phase4" };

  // ---- 4.1 Admin edit HR fund via API (update_pcf_settings now accepts is_enabled; also fund_amount + threshold) ----
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = "4.1_edit_hr_fund";
      await login(page, "sam");
      // Capture original values first for Phase 6 rollback
      const before = await page.evaluate(async () => {
        const r = await fetch("/api/frappe/api/resource/BEI Petty Cash Fund/" + encodeURIComponent("PCF-HR and Admin"), { credentials: "include" });
        const j = await r.json();
        return { fund_amount: j.data?.fund_amount, threshold_percentage: j.data?.threshold_percentage };
      });
      console.log("before:", before);

      const res = await page.evaluate(async () => {
        const r = await fetch("/api/pcf", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            action: "update_pcf_settings",
            pcf_fund: "PCF-HR and Admin",
            fund_amount: 8000,
            threshold_percentage: 70,
          }),
        });
        return { status: r.status, body: (await r.text()).slice(0, 1500) };
      });
      console.log("update_pcf_settings:", res);

      const after = await page.evaluate(async () => {
        const r = await fetch("/api/frappe/api/resource/BEI Petty Cash Fund/" + encodeURIComponent("PCF-HR and Admin"), { credentials: "include" });
        const j = await r.json();
        return { fund_amount: j.data?.fund_amount, threshold_percentage: j.data?.threshold_percentage };
      });
      console.log("after:", after);

      recordForm({
        scenario: "4.1_edit_hr_fund",
        form: "update_pcf_settings",
        inputs: { pcf_fund: "PCF-HR and Admin", fund_amount: 8000, threshold_percentage: 70 },
        submit_action: "POST /api/pcf update_pcf_settings",
        response: res,
      });
      recordState({
        scenario: "4.1_edit_hr_fund",
        check: "hr_fund_settings_updated",
        before: JSON.stringify(before),
        after: JSON.stringify(after),
        passed: after.fund_amount === 8000 && after.threshold_percentage === 70,
      });

      // Save original for rollback
      const fs = require("fs");
      fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase4_original_hr_settings.json", JSON.stringify(before, null, 2));
    } finally { await browser.close(); }
  }

  // ---- 4.2 Verify as test.hr ----
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = "4.2_verify_hr_view";
      await login(page, "hr");
      await page.goto(`${BASE}/dashboard/hr-admin/pcf`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(3000);
      await shot(page, "phase4_hr_view_updated");
      const text = await page.evaluate(() => document.body.innerText);
      const hasEightK = /₱8,000|8000|8,000/.test(text);
      const has70 = /70%/.test(text);
      console.log("hr view — ₱8,000 visible:", hasEightK, "| 70% visible:", has70);
      recordState({
        scenario: "4.2_verify_hr_view",
        check: "hr_sees_updated_settings",
        before: "5000/60%",
        after: `8000_visible=${hasEightK} 70pct_visible=${has70}`,
        passed: hasEightK && has70,
      });
    } finally { await browser.close(); }
  }

  console.log("\n=== Phase 4 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
