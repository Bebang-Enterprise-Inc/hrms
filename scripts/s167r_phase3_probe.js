/**
 * Probe accountant review page DOM to find buttons/selectors.
 */
const { BASE, login, shot, newBrowser } = require("./s167_lib");

(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "finance");
    await page.goto(`${BASE}/dashboard/accounting/pcf/review`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(4000);
    await shot(page, "p3_probe_review");
    const dump = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button')).map(b => ({
        text: (b.innerText||"").trim().slice(0,60),
        aria: b.getAttribute('aria-label')||"",
        disabled: b.disabled,
      })).filter(b=>b.text);
      const links = Array.from(document.querySelectorAll('a')).map(a=>({
        text:(a.innerText||"").trim().slice(0,60),
        href:a.getAttribute('href')||"",
      })).filter(l=>l.text && l.href.includes('pcf'));
      const headings = Array.from(document.querySelectorAll('h1,h2,h3')).map(h=>(h.innerText||"").trim()).filter(Boolean);
      return { url: location.pathname, title: document.title, headings: headings.slice(0,20), buttons: btns.slice(0,40), pcfLinks: links.slice(0,20) };
    });
    console.log(JSON.stringify(dump, null, 2));
    // Click into HR fund review
    const hrLink = page.locator('a[href="/dashboard/accounting/pcf/review/PCF-HR%20and%20Admin"]').first();
    if (await hrLink.count()) {
      console.log("\n=== Clicking HR fund review ===");
      await hrLink.click();
      await page.waitForTimeout(8000);
      await shot(page, "p3_probe_hr_fund");
      const detail = await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll('button')).map(b=>({
          text:(b.innerText||"").trim().slice(0,80),
          disabled:b.disabled,
        })).filter(b=>b.text);
        const inputs = Array.from(document.querySelectorAll('input,select,textarea')).map(i=>({
          tag:i.tagName.toLowerCase(), type:i.type||"", name:i.name||"", placeholder:i.placeholder||"", id:i.id||"",
        })).slice(0,30);
        const body = (document.body.innerText||"").slice(0, 3000);
        const tables = Array.from(document.querySelectorAll('table')).length;
        return { url: location.pathname, buttons: btns.slice(0,60), inputs, tables, body };
      });
      console.log(JSON.stringify(detail, null, 2));
    } else {
      console.log("\nNo HR batch link found on review page");
    }
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
