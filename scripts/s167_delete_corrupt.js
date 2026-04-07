const { login, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");
  const res = await page.evaluate(async () => {
    const r = await fetch("/api/frappe/api/method/frappe.client.delete", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ doctype: "BEI Petty Cash Fund", name: "PCF-" }),
    });
    return { status: r.status, body: (await r.text()).slice(0, 1500) };
  });
  console.log("delete PCF- :", res.status, res.body);
  await browser.close();
})().catch(e => console.error(e));
