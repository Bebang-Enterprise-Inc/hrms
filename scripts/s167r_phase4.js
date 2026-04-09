/**
 * S167 Phase 4 — sam edits HR fund to 8000/70 via real admin dialog.
 * 4.2 test.hr verifies updated values render.
 */
const { BASE, login, shot, attachNetwork, recordForm, recordState, recordDefect, newBrowser } = require("./s167_lib");

async function probeAdminFor(page, fundName) {
  const dump = await page.evaluate((fn) => {
    const cards = Array.from(document.querySelectorAll('[class*="card"], div')).filter(d => (d.innerText||"").includes(fn) && (d.innerText||"").length < 2000);
    const header = cards[0];
    return { found: !!header, sample: (header?.innerText||"").slice(0,500) };
  }, fundName);
  return dump;
}

(async () => {
  const sref = { current: "p4" };
  const { browser, page } = await newBrowser();
  attachNetwork(page, sref);
  try {
    await login(page, "sam");
    console.log("Logged in: sam@bebang.ph");

    // 4.1 Open PCF admin, edit HR fund
    sref.current = "4.1_edit";
    console.log("\n[4.1] Open PCF admin");
    await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(5000);
    await shot(page, "p4.1_admin");

    // Find card containing "HR and Admin" and click its Edit/Settings button
    const hrCardText = await page.locator('text=HR and Admin').first();
    await hrCardText.waitFor({ state: "visible", timeout: 10000 });
    // Scroll to it
    await hrCardText.scrollIntoViewIfNeeded();
    await shot(page, "p4.1_hr_visible");

    // Card containing "HR and Admin (Department)" header and a Save button
    const hrCard = page.locator('div').filter({ hasText: /^HR and Admin \(Department\)/ }).filter({ has: page.getByRole('button', { name: /^save$/i }) }).first();
    await hrCard.waitFor({ state: "visible", timeout: 10000 });
    await hrCard.scrollIntoViewIfNeeded();
    await shot(page, "p4.1_hr_card");

    // Number inputs within card: 0=fund_amount, 1=threshold
    const numInputs = hrCard.locator('input[type="number"]');
    const amtInput = numInputs.nth(0);
    const thrInput = numInputs.nth(1);

    let saveResp = null;
    try {
      await amtInput.click();
      await amtInput.fill("");
      await amtInput.fill("8000");
      await thrInput.click();
      await thrInput.fill("");
      await thrInput.fill("70");
      await shot(page, "p4.1_filled");

      const waitResp = page.waitForResponse(
        (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("update_pcf_settings"),
        { timeout: 20000 }
      );
      const saveBtn = hrCard.getByRole("button", { name: /^save$/i }).first();
      await saveBtn.click();
      const r = await waitResp;
      saveResp = { status: r.status(), body: (await r.text()).slice(0, 1500) };
    } catch (e) { saveResp = { status: 0, error: e.message }; recordDefect("4.1_save", e.message); }
    await page.waitForTimeout(2500);
    await shot(page, "p4.1_after");
    recordForm({ scenario: "4.1_edit_hr_fund", form: "update_pcf_settings", method: "BROWSER",
      inputs: { pcf_fund: "PCF-HR and Admin", fund_amount: 8000, threshold_percentage: 70 },
      submit_action: "edit admin dialog + save", response: saveResp });
    console.log(`  [4.1] ${saveResp?.status === 200 ? "PASS" : "FAIL"}: ${(saveResp.error||saveResp.body||"").slice(0,300)}`);
  } finally { await browser.close(); }

  // 4.2 test.hr logs in and verifies updated values
  const { browser: b2, page: p2 } = await newBrowser();
  try {
    await login(p2, "hr");
    await p2.goto(`${BASE}/dashboard/hr-admin/pcf`, { waitUntil: "networkidle", timeout: 45000 });
    await p2.waitForTimeout(4500);
    await shot(p2, "p4.2_hr_dashboard");
    const text = await p2.evaluate(() => document.body.innerText.slice(0, 3000));
    const has8000 = /8,?000|₱\s?8/.test(text);
    const has70 = /70\s?%|70 percent/i.test(text);
    recordState({ scenario: "4.2_verify", check: "hr_dashboard_shows_new_values",
      before: "HR 5000/60", after: `amt8k:${has8000} thr70:${has70}`,
      passed: has8000 });
    console.log(`[4.2] amt8k:${has8000} thr70:${has70}`);
  } finally { await b2.close(); }
  console.log("\n=== Phase 4 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
