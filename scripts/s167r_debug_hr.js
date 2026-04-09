const { BASE, login, shot, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  try {
    await login(page, "hr");
    await page.goto(`${BASE}/dashboard/hr-admin/pcf`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(7000);
    const text = await page.evaluate(() => document.body.innerText);
    console.log("=== HR page text (first 3000) ===");
    console.log(text.slice(0, 3000));
  } finally { await browser.close(); }
})();
