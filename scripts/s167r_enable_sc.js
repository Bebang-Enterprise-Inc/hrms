/**
 * Re-enable PCF-Supply Chain via real browser switch click + Save in admin card.
 */
const { BASE, login, shot, recordForm, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "sam");
    await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(5000);
    const card = page.locator('div').filter({ hasText: /^Supply Chain \(Department\)/ }).filter({ has: page.getByRole('button', { name: /^save$/i }) }).first();
    await card.waitFor({ state: "visible", timeout: 10000 });
    await card.scrollIntoViewIfNeeded();
    await shot(page, "p0.1_SupplyChain_reenable_before");
    const sw = card.locator('button[role="switch"]').first();
    const state0 = await sw.getAttribute("data-state");
    console.log("switch state:", state0);
    if (state0 !== "checked") {
      await sw.click();
      await page.waitForTimeout(800);
    }
    await shot(page, "p0.1_SupplyChain_reenable_toggled");
    const waitResp = page.waitForResponse(
      (r) => r.url().includes("/api/pcf") && r.request().method()==="POST" && (r.request().postData()||"").includes("update_pcf_settings"),
      { timeout: 20000 }
    );
    await card.getByRole("button", { name: /^save$/i }).first().click();
    const r = await waitResp;
    const body = await r.text();
    console.log("save:", r.status(), body.slice(0,300));
    await shot(page, "p0.1_SupplyChain_reenable_after");
    recordForm({ scenario: "0.1_SupplyChain_reenable", form: "update_pcf_settings",
      method: "BROWSER switch click + Save",
      inputs: { pcf_fund: "PCF-Supply Chain", is_enabled: true },
      submit_action: "click enable switch → click Save",
      response: { status: r.status(), body: body.slice(0,800) } });
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
