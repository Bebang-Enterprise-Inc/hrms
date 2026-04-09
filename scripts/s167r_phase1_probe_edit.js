const { BASE, login, shot, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "supv");
    await page.goto(`${BASE}/dashboard/store-ops/pcf/pending`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(5000);
    await shot(page, "p1_probe_pending");
    const d = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('[role="row"], tr, li, .card, [class*="card"]'))
        .filter(r => /7-?Eleven/i.test(r.innerText||""));
      const out = rows.slice(0,3).map(r => ({
        tag: r.tagName, cls: (r.className||"").toString().slice(0,100),
        text: (r.innerText||"").slice(0,300),
        buttons: Array.from(r.querySelectorAll('button')).map(b=>({text:(b.innerText||"").trim().slice(0,40),aria:b.getAttribute('aria-label')||"",title:b.getAttribute('title')||""})),
        svgIcons: r.querySelectorAll('svg').length,
      }));
      return out;
    });
    console.log(JSON.stringify(d, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
