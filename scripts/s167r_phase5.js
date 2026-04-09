/**
 * S167 Phase 5 — Sidebar audit + legacy redirects.
 * Plan: R3 PCF under dept group, R10 no PCF under My Expenses, legacy /dashboard/expense/pcf redirect.
 */
const { BASE, login, shot, recordState, recordDefect, newBrowser } = require("./s167_lib");

async function expandAllGroups(page) {
  // shadcn sidebar collapsible groups — click every group header button
  const groupButtons = page.locator('[data-sidebar="group-label"] button, button[data-sidebar="menu-button"][aria-expanded="false"]');
  const n = await groupButtons.count();
  for (let i = 0; i < n; i++) {
    try { await groupButtons.nth(i).click({ timeout: 1500 }); } catch {}
    await page.waitForTimeout(200);
  }
}

async function dumpSidebar(page) {
  return await page.evaluate(() => {
    const nav = document.querySelector('[data-sidebar="sidebar"], nav, aside');
    if (!nav) return { anchors: [], groups: [] };
    const anchors = Array.from(nav.querySelectorAll('a')).map(a => ({
      text: (a.innerText||"").trim(),
      href: a.getAttribute('href')||"",
    })).filter(a => a.text && a.href);
    const groups = Array.from(nav.querySelectorAll('[data-sidebar="group"]')).map(g => (g.innerText||"").slice(0,400));
    return { anchors, groups };
  });
}

async function auditUser(who, expectedDeptPath) {
  const { browser, page } = await newBrowser();
  const result = { user: who, anchors: [], pcfUnderDept: false, pcfUnderMyExpenses: false };
  try {
    await login(page, who);
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(3000);
    // Expand all collapsible groups
    const expandButtons = page.locator('button[aria-expanded]');
    const n = await expandButtons.count();
    for (let i = 0; i < n; i++) {
      try {
        const btn = expandButtons.nth(i);
        const exp = await btn.getAttribute('aria-expanded');
        if (exp === 'false') await btn.click({ timeout: 1000 });
      } catch {}
      await page.waitForTimeout(150);
    }
    await page.waitForTimeout(1500);
    await shot(page, `p5_sidebar_${who}`);
    const d = await dumpSidebar(page);
    result.anchors = d.anchors;
    // R3: Does a PCF anchor exist with href matching expectedDeptPath?
    const pcfAnchors = d.anchors.filter(a => /pcf/i.test(a.href));
    result.pcfAnchors = pcfAnchors;
    result.pcfUnderDept = pcfAnchors.some(a => a.href.startsWith(expectedDeptPath));
    // R10: Is there a PCF anchor under /dashboard/expense ("My Expenses")?
    result.pcfUnderMyExpenses = pcfAnchors.some(a => /\/dashboard\/expense/.test(a.href));

    // Legacy redirect test — only for hr
    if (who === "hr") {
      await page.goto(`${BASE}/dashboard/expense/pcf`, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(2500);
      result.legacy_pcf_url = page.url();
      await page.goto(`${BASE}/dashboard/expense/pcf/add`, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(2500);
      result.legacy_pcf_add_url = page.url();
    }
  } finally { await browser.close(); }
  return result;
}

(async () => {
  const checks = [
    { who: "staff",   deptPath: "/dashboard/store-ops/pcf" },
    { who: "hr",      deptPath: "/dashboard/hr-admin/pcf" },
    { who: "finance", deptPath: "/dashboard/accounting/pcf" },
  ];
  for (const c of checks) {
    console.log(`\n=== ${c.who} ===`);
    const res = await auditUser(c.who, c.deptPath);
    console.log(`  pcfAnchors: ${JSON.stringify(res.pcfAnchors?.slice(0,8))}`);
    console.log(`  R3 pcfUnderDept (${c.deptPath}): ${res.pcfUnderDept}`);
    console.log(`  R10 pcfUnderMyExpenses: ${res.pcfUnderMyExpenses}`);
    if (res.legacy_pcf_url) console.log(`  legacy /dashboard/expense/pcf -> ${res.legacy_pcf_url}`);
    if (res.legacy_pcf_add_url) console.log(`  legacy /dashboard/expense/pcf/add -> ${res.legacy_pcf_add_url}`);
    recordState({
      scenario: `5_${c.who}_sidebar`,
      check: "sidebar_R3_and_R10",
      before: "sidebar dump",
      after: `R3:${res.pcfUnderDept} R10_noPcf:${!res.pcfUnderMyExpenses}`,
      passed: res.pcfUnderDept && !res.pcfUnderMyExpenses,
      legacy_pcf_url: res.legacy_pcf_url,
      legacy_pcf_add_url: res.legacy_pcf_add_url,
    });
  }
  console.log("\n=== Phase 5 done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
