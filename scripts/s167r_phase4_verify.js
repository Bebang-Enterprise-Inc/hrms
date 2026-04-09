const { BASE, login, shot, recordState, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "hr");
    await page.goto(`${BASE}/dashboard/hr-admin/pcf`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(5000);
    await shot(page, "p4.2_verify");
    const text = await page.evaluate(() => document.body.innerText.slice(0, 4000));
    const has8k = /8,?000/.test(text);
    const has70 = /70\s?%/.test(text);
    console.log(`8000:${has8k} 70%:${has70}`);
    console.log("SNIPPET:", text.match(/.{0,80}(8,?000|70\s?%|Fund).{0,80}/)?.slice(0,3));
    recordState({ scenario: "4.2_verify_retry", check: "hr_dashboard_shows_8000_70",
      before: "HR 5000/60", after: `8k:${has8k} 70:${has70}`, passed: has8k && has70 });
  } finally { await browser.close(); }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
