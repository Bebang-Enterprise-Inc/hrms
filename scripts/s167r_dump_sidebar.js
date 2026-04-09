const { BASE, login, newBrowser } = require("./s167_lib");
(async () => {
  for (const who of ["staff","hr","commi","warehouse","finance"]) {
    const { browser, page } = await newBrowser();
    try {
      await login(page, who);
      await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 45000 });
      await page.waitForTimeout(2500);
      const expand = page.locator('button[aria-expanded="false"]');
      const n = await expand.count();
      for (let i = 0; i < n; i++) {
        try { await expand.nth(i).click({ timeout: 600 }); } catch {}
        await page.waitForTimeout(100);
      }
      await page.waitForTimeout(1000);
      const pcfHrefs = await page.evaluate(() => {
        const nav = document.querySelector('[data-sidebar="sidebar"], nav, aside') || document;
        return Array.from(nav.querySelectorAll('a')).map(a => a.getAttribute('href') || '').filter(h => /\/pcf/i.test(h));
      });
      console.log(`\n${who}:`);
      for (const h of pcfHrefs) console.log(`  ${h}`);
    } finally { await browser.close(); }
  }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
