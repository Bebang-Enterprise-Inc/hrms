const { BASE, login, shot, attachNetwork, recordState, recordDefect, newBrowser } = require("./s167_lib");

const VERIFY = [
  { who: "staff",    route: "/dashboard/store-ops/pcf"  },
  { who: "supv",     route: "/dashboard/store-ops/pcf"  },
  { who: "hr",       route: "/dashboard/hr-admin/pcf"   },
  { who: "warehouse",route: "/dashboard/warehouse/pcf"  },
  { who: "commi",    route: "/dashboard/commissary/pcf" },
  { who: "finance",  route: "/dashboard/accounting/pcf" },
];

(async () => {
  const scenarioRef = { current: "phase0_verify" };
  for (const v of VERIFY) {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = `0.2_${v.who}`;
      await login(page, v.who);
      await page.goto(`${BASE}${v.route}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(3500);
      const text = await page.evaluate(() => document.body.innerText.slice(0, 5000));
      const noFund = /no pcf fund (assigned|configured|is configured)|not configured/i.test(text);
      await shot(page, `phase0_verify2_${v.who}`);
      const summary = text.split("\n").filter(l => l.trim()).slice(-20).join(" | ").slice(0, 500);
      recordState({
        scenario: `0.2_${v.who}`,
        check: `fund_resolution_${v.who}`,
        before: "logged_in",
        after: noFund ? "no_pcf_fund_assigned" : "fund_visible",
        passed: !noFund,
        url: page.url(),
        page_tail: summary,
      });
      console.log(`[0.2 ${v.who}] ${noFund ? "NO FUND" : "OK"}  tail=${summary.slice(0, 160)}`);
    } catch (e) {
      recordDefect(`0.2_${v.who}`, e.message);
      console.log(`[0.2 ${v.who}] ERROR ${e.message.slice(0,150)}`);
    } finally { await browser.close(); }
  }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
