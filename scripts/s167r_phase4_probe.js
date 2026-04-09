const { BASE, login, shot, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "sam");
    await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(6000);
    await shot(page, "p4_probe_admin");
    // Find all HR-related elements
    const found = await page.evaluate(() => {
      const nodes = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,div,span'));
      const hrNodes = nodes.filter(n => {
        const t = (n.textContent||"").trim();
        return /HR and Admin/.test(t) && t.length < 200;
      }).slice(0, 5);
      // For each, walk up looking for a "card" container
      const results = [];
      for (const hn of hrNodes) {
        let c = hn;
        for (let i = 0; i < 12 && c; i++) {
          const hasSave = Array.from(c.querySelectorAll?.('button')||[]).some(b => /save/i.test(b.innerText||""));
          if (hasSave) {
            const btns = Array.from(c.querySelectorAll('button')).map(b => (b.innerText||"").trim().slice(0,60)).filter(Boolean);
            const inputs = Array.from(c.querySelectorAll('input,textarea,[role="switch"]')).map(i => ({
              tag: i.tagName.toLowerCase(),
              type: i.getAttribute('type')||"",
              name: i.getAttribute('name')||"",
              role: i.getAttribute('role')||"",
            }));
            const cls2 = c.getAttribute?.("class")||"";
            results.push({
              tag: c.tagName, cls: cls2.slice(0,120),
              text: (c.innerText||"").slice(0,400),
              btns, inputs,
            });
            break;
          }
          c = c.parentElement;
        }
      }
      // Also dump global buttons count
      const allBtns = Array.from(document.querySelectorAll('button')).map(b => (b.innerText||"").trim().slice(0,40)).filter(Boolean);
      const dialogs = document.querySelectorAll('[role="dialog"]').length;
      return { hr: results.slice(0,3), allButtonCount: allBtns.length, sampleButtons: allBtns.slice(0,30), dialogs };
    });
    console.log(JSON.stringify(found, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
