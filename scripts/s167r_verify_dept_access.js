/**
 * Verify each dept user can reach their OWN PCF dashboard + sidebar shows
 * their own PCF anchors once they land on the dept route.
 */
const { BASE, login, shot, newBrowser } = require("./s167_lib");

const TESTS = [
  { who: "staff",     path: "/dashboard/store-ops/pcf",    mustSee: /petty cash fund/i,   anchor: "/dashboard/store-ops/pcf" },
  { who: "supv",      path: "/dashboard/store-ops/pcf",    mustSee: /petty cash fund/i,   anchor: "/dashboard/store-ops/pcf" },
  { who: "hr",        path: "/dashboard/hr-admin/pcf",     mustSee: /petty cash fund/i,   anchor: "/dashboard/hr-admin/pcf" },
  { who: "warehouse", path: "/dashboard/warehouse/pcf",    mustSee: /petty cash fund/i,   anchor: "/dashboard/warehouse/pcf" },
  { who: "commi",     path: "/dashboard/commissary/pcf",   mustSee: /petty cash fund/i,   anchor: "/dashboard/commissary/pcf" },
  { who: "finance",   path: "/dashboard/accounting/pcf",   mustSee: /petty cash fund/i,   anchor: "/dashboard/accounting/pcf" },
];

(async () => {
  for (const t of TESTS) {
    const { browser, page } = await newBrowser();
    try {
      await login(page, t.who);
      await page.goto(`${BASE}${t.path}`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(4000);
      await shot(page, `verify_dept_${t.who}`);
      // Check page title/body
      const text = await page.evaluate(() => document.body.innerText);
      const pageRenders = t.mustSee.test(text);
      const notForbidden = !/not permitted|not configured|access denied/i.test(text);
      // Check sidebar anchor for own dept PCF is present
      const hasOwnAnchor = await page.evaluate((anchor) => {
        return Array.from(document.querySelectorAll('a')).some(a => (a.getAttribute('href')||'').includes(anchor));
      }, t.anchor);
      // Count cross-dept PCF anchors (NOT their own)
      const ownPrefix = t.anchor;
      const crossLinks = await page.evaluate((own) => {
        return Array.from(document.querySelectorAll('a'))
          .map(a => a.getAttribute('href') || '')
          .filter(h => /\/dashboard\/.+\/pcf/.test(h) && !h.startsWith(own));
      }, ownPrefix);
      console.log(`\n[${t.who}] -> ${t.path}`);
      console.log(`  renders:${pageRenders} notForbidden:${notForbidden} hasOwnAnchor:${hasOwnAnchor}`);
      if (crossLinks.length) {
        console.log(`  LEAKS (${crossLinks.length}): ${JSON.stringify([...new Set(crossLinks)].slice(0,10))}`);
      } else {
        console.log(`  LEAKS: none`);
      }
    } finally { await browser.close(); }
  }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
