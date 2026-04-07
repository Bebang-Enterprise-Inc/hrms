const { login, newBrowser, recordForm, recordState } = require("./s167_lib");
const fs = require("fs");

const FUNDS = [
  { label: "HR",         name: "PCF-HR and Admin",  custodian: "test.hr@bebang.ph"         },
  { label: "SupplyChain",name: "PCF-Supply Chain",  custodian: "test.warehouse@bebang.ph"  },
  { label: "Commissary", name: "PCF-Commissary",    custodian: "test.commissary@bebang.ph" },
];

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");

  // 1. Enable each fund
  for (const f of FUNDS) {
    const res = await page.evaluate(async (fund) => {
      const r = await fetch("/api/pcf", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "update_pcf_settings",
          pcf_fund: fund.name,
          is_enabled: 1,
        }),
      });
      return { status: r.status, body: (await r.text()).slice(0, 600) };
    }, f);
    console.log(`enable ${f.label}:`, res.status, res.body.slice(0, 200));
    recordForm({
      scenario: `0.1_enable_${f.label}`,
      form: "update_pcf_settings",
      inputs: { pcf_fund: f.name, is_enabled: 1 },
      submit_action: "POST /api/pcf update_pcf_settings",
      response: res,
    });
  }

  // 2. Check each test user's Employee record
  const users = [
    "test.staff@bebang.ph",
    "test.supervisor@bebang.ph",
    "test.hr@bebang.ph",
    "test.warehouse@bebang.ph",
    "test.commissary@bebang.ph",
    "test.finance@bebang.ph",
  ];
  const empInfo = {};
  for (const u of users) {
    const res = await page.evaluate(async (user) => {
      const r = await fetch("/api/frappe/api/method/frappe.client.get_value", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          doctype: "Employee",
          filters: JSON.stringify({ user_id: user, status: "Active" }),
          fieldname: JSON.stringify(["name","employee_name","branch","department","company"]),
        }).toString(),
      });
      return { status: r.status, body: (await r.text()).slice(0, 1000) };
    }, u);
    try {
      const parsed = JSON.parse(res.body);
      empInfo[u] = parsed.message || parsed.data || parsed;
    } catch { empInfo[u] = { raw: res.body }; }
    console.log(`${u}:`, JSON.stringify(empInfo[u]).slice(0, 250));
  }
  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/employee_depts.json", JSON.stringify(empInfo, null, 2));

  await browser.close();
})().catch(e => console.error("FATAL", e));
