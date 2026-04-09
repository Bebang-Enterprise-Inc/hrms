/**
 * Probe per-batch review page directly for HR batch BEI-PCF-2026-00004
 */
const { BASE, login, shot, newBrowser } = require("./s167_lib");

(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "finance");
    await page.goto(`${BASE}/dashboard/accounting/pcf/review/BEI-PCF-2026-00004`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(6000);
    await shot(page, "p3_probe_hr_batch");
    const d = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button')).map(b=>({
        text:(b.innerText||"").trim().slice(0,80),
        disabled:b.disabled,
      })).filter(b=>b.text);
      const inputs = Array.from(document.querySelectorAll('input,select,textarea')).map(i=>({
        tag:i.tagName.toLowerCase(), type:i.type||"", name:i.name||"", placeholder:i.placeholder||"", id:i.id||"",
      }));
      return {
        url: location.pathname,
        buttons: btns.slice(0,60),
        inputs: inputs.slice(0,50),
        tables: document.querySelectorAll('table').length,
        body: (document.body.innerText||"").slice(0,2500),
      };
    });
    console.log(JSON.stringify(d, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
