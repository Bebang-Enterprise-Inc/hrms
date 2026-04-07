const { BASE, login, newBrowser } = require("./s167_lib");

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");
  await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: /create department fund/i }).first().click();
  await page.waitForTimeout(1500);
  // Inspect the select#create_department
  const options = await page.evaluate(() => {
    const sel = document.getElementById("create_department");
    if (!sel) return { error: "no select" };
    return {
      tag: sel.tagName,
      disabled: sel.disabled,
      hidden: sel.hidden,
      visible: sel.offsetParent !== null,
      options: Array.from(sel.options).map(o => ({ value: o.value, label: o.label, text: o.text })),
    };
  });
  console.log(JSON.stringify(options, null, 2));
  await browser.close();
})().catch(e=>console.error(e));
