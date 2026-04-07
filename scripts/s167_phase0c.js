const { BASE, login, newBrowser } = require("./s167_lib");
const fs = require("fs");

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");
  const body = {
    action: "create_pcf_fund",
    fund_type: "Department",
    department: "HR and Admin - BEI",
    custodian: "test.hr@bebang.ph",
    fund_amount: 5000,
    threshold_percentage: 60,
  };
  const res = await page.evaluate(async (b) => {
    const r = await fetch("/api/pcf", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(b),
    });
    return { status: r.status, body: await r.text() };
  }, body);
  console.log("STATUS", res.status);
  console.log("FULL BODY:\n", res.body);
  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/debug_full_traceback.txt", res.body);
  await browser.close();
})().catch(e=>console.error(e));
