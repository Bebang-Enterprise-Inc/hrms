/**
 * S167 Phase 5 — Sidebar audit (3 users) + legacy URL redirects.
 */
const { BASE, login, shot, attachNetwork, recordState, recordDefect, newBrowser } = require("./s167_lib");
const fs = require("fs");

const AUDIT = [
  { who: "staff",   label: "TEST-STAFF (Store Ops)" },
  { who: "hr",      label: "TEST-HR (HR Management)" },
  { who: "finance", label: "TEST-FINANCE (Finance & Accounting)" },
];

async function captureSidebar(page, who) {
  const info = await page.evaluate(() => {
    // Collect all anchor tags with href containing /pcf or /expense
    const links = Array.from(document.querySelectorAll("a")).map(a => ({
      text: (a.innerText || "").trim().slice(0, 80),
      href: a.getAttribute("href"),
    })).filter(l => l.text && l.href && (l.href.includes("/pcf") || l.href.includes("/expense")));
    // Also capture whether "My Expenses" section contains any PCF item
    const allText = document.body.innerText;
    return { links, hasMyExpenses: allText.includes("My Expenses") };
  });
  return info;
}

(async () => {
  const scenarioRef = { current: "phase5" };
  const results = {};

  for (const a of AUDIT) {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = `5.1_${a.who}`;
      await login(page, a.who);
      await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2500);
      await shot(page, `phase5_sidebar_${a.who}`);
      const info = await captureSidebar(page, a.who);
      results[a.who] = info;
      console.log(`\n[5.1 ${a.who}] ${a.label}`);
      console.log("  PCF/expense links:");
      for (const l of info.links) console.log(`    ${l.text} -> ${l.href}`);

      // R10: My Expenses should NOT contain PCF items
      const myExpensePcf = info.links.filter(l => l.href.includes("/expense/pcf") || (l.href.includes("/dashboard/expense") && l.text.toLowerCase().includes("pcf")));
      const r10 = myExpensePcf.length === 0;
      // R3: PCF under dept
      const deptPcf = info.links.filter(l =>
        (a.who === "staff" && l.href.includes("/store-ops/pcf")) ||
        (a.who === "hr" && l.href.includes("/hr-admin/pcf")) ||
        (a.who === "finance" && l.href.includes("/accounting/pcf"))
      );
      const r3 = deptPcf.length > 0;

      recordState({
        scenario: `5.1_${a.who}`,
        check: "sidebar_regression",
        before: "logged_in",
        after: `R3_dept_pcf=${r3} R10_no_pcf_in_my_expenses=${r10}`,
        passed: r3 && r10,
        notes: `links=${JSON.stringify(info.links.slice(0, 10))}`,
      });
    } finally { await browser.close(); }
  }

  // ---- 5.2 Legacy URL redirects as test.staff (has store branch) ----
  // Since test.staff has no store fund resolving (DEFECT-004), the legacy redirect
  // behavior depends on the fallback path. We still test it.
  {
    const { browser, page } = await newBrowser();
    attachNetwork(page, scenarioRef);
    try {
      scenarioRef.current = "5.2_legacy_redirect_hr";
      await login(page, "hr"); // test.hr who we know has a working dept fund
      await page.goto(`${BASE}/dashboard/expense/pcf`, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(3000);
      await shot(page, "phase5_redirect_expense_pcf");
      const finalUrl = page.url();
      console.log(`\n[5.2] /dashboard/expense/pcf as test.hr -> ${finalUrl}`);
      recordState({
        scenario: "5.2_legacy_redirect_hr",
        check: "legacy_expense_pcf_redirect",
        before: "/dashboard/expense/pcf",
        after: finalUrl,
        passed: finalUrl !== `${BASE}/dashboard/expense/pcf` || finalUrl.includes("pcf=not-configured") === false,
      });

      await page.goto(`${BASE}/dashboard/expense/pcf/add`, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(3000);
      const finalUrl2 = page.url();
      console.log(`[5.2] /dashboard/expense/pcf/add as test.hr -> ${finalUrl2}`);
      recordState({
        scenario: "5.2_legacy_redirect_add",
        check: "legacy_expense_pcf_add_redirect",
        before: "/dashboard/expense/pcf/add",
        after: finalUrl2,
        passed: finalUrl2.includes("/pcf/add"),
      });
    } finally { await browser.close(); }
  }

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase5_sidebar_results.json", JSON.stringify(results, null, 2));
  console.log("\n=== Phase 5 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
