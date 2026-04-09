const { BASE, login, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "staff");
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(3000);
    // Force-expand absolutely everything in the sidebar
    for (let pass = 0; pass < 3; pass++) {
      const all = page.locator('button[aria-expanded="false"], [data-state="closed"]');
      const n = await all.count();
      for (let i = 0; i < n; i++) {
        try { await all.nth(i).click({ timeout: 500 }); await page.waitForTimeout(80); } catch {}
      }
    }
    await page.waitForTimeout(1500);
    const dump = await page.evaluate(() => {
      const nav = document.querySelector('[data-sidebar="sidebar"], nav, aside') || document;
      // Get all section headings + their child anchors
      const sections = Array.from(nav.querySelectorAll('[data-sidebar="group-label"], [data-sidebar="menu-button"]'));
      const allLinks = Array.from(nav.querySelectorAll('a')).map(a => a.getAttribute('href')||'').filter(Boolean);
      const text = (nav.innerText || "").slice(0, 4000);
      return { allLinks, headingCount: sections.length, text };
    });
    console.log("ALL anchors visible to test.staff:");
    for (const h of dump.allLinks) console.log(" ", h);
    console.log("\nSidebar text snippet:");
    console.log(dump.text.slice(0, 2000));

    // Try to navigate to /dashboard/store-ops/pcf directly
    console.log("\nDirect nav to /dashboard/store-ops/pcf:");
    await page.goto(`${BASE}/dashboard/store-ops/pcf`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(3000);
    console.log("  url:", page.url());
    const txt = await page.evaluate(() => document.body.innerText.slice(0, 500));
    console.log("  body:", txt);
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
