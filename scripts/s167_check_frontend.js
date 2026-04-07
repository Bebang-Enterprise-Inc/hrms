const { BASE, login, newBrowser } = require("./s167_lib");
(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");
  // Hit the new endpoint directly
  const r = await page.evaluate(async () => {
    const res = await fetch("/api/pcf?action=list_departments", { credentials: "include" });
    return { status: res.status, body: (await res.text()).slice(0, 2000) };
  });
  console.log("list_departments:", r.status, r.body.slice(0, 1500));
  await browser.close();
})().catch(e=>console.error(e));
