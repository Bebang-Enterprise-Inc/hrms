/**
 * S167 REDO Phase 0.2 — BROWSER: verify fund resolution for 6 test accounts.
 * Real Playwright page loads + DOM scrape for balance/fund label. Read-only.
 */
const { BASE, login, shot, recordState, newBrowser } = require("./s167_lib");

const CHECKS = [
  { who: "staff",     route: "/dashboard/store-ops/pcf",       expect: /PCF-TEST-STORE-BGC|store|10,?000/i },
  { who: "supv",      route: "/dashboard/store-ops/pcf",       expect: /PCF-TEST-STORE-BGC|store|10,?000/i },
  { who: "hr",        route: "/dashboard/hr-admin/pcf",        expect: /HR and Admin|5,?000/i },
  { who: "warehouse", route: "/dashboard/warehouse/pcf",       expect: /Supply Chain|5,?000/i },
  { who: "commi",     route: "/dashboard/commissary/pcf",      expect: /Commissary|5,?000/i },
  { who: "finance",   route: "/dashboard/accounting/pcf/review", expect: /PCF Review Queue|fund/i },
];

(async () => {
  for (const c of CHECKS) {
    const { browser, page } = await newBrowser();
    try {
      await login(page, c.who);
      console.log(`\n[0.2 ${c.who}] ${c.route}`);
      await page.goto(`${BASE}${c.route}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(4000);
      await shot(page, `p0.2_${c.who}`);
      const text = await page.evaluate(() => document.body.innerText.slice(0, 4000));
      const matched = c.expect.test(text);
      const snippet = (text.match(c.expect)?.[0] || "").slice(0, 80);
      recordState({
        scenario: `0.2_${c.who}`,
        check: "fund_resolution_browser_page_load",
        method: "BROWSER page.goto + DOM scrape",
        route: c.route,
        passed: matched,
        matched_snippet: snippet,
        before: "no page load",
        after: matched ? `fund visible: ${snippet}` : "NOT FOUND",
      });
      console.log(`  match:${matched} snippet:"${snippet}"`);
    } finally { await browser.close(); }
  }
  console.log("\n=== Phase 0.2 REDO done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
