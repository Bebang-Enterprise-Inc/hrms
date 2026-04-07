/**
 * S167 setup: realign test employee departments to match the new dept
 * PCF funds. Save original values for Phase 6 rollback.
 */
const { login, newBrowser } = require("./s167_lib");
const fs = require("fs");

const CHANGES = [
  { emp: "TEST-HR-001",          set: { department: "HR and Admin - BEI" } },
  { emp: "TEST-COMMISSARY-001",  set: { department: "Commissary - BEI" } },
  { emp: "TEST-WAREHOUSE-001",   set: { department: "Supply Chain - BEI" } },
];

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");

  const manifest = [];
  for (const c of CHANGES) {
    // Read current values via resource API
    const orig = await page.evaluate(async (name) => {
      const r = await fetch("/api/frappe/api/resource/Employee/" + encodeURIComponent(name), {
        credentials: "include",
      });
      const j = await r.json();
      const d = j.data || {};
      return {
        department: d.department,
        branch: d.branch,
        company: d.company,
        user_id: d.user_id,
      };
    }, c.emp);

    // Apply change — use JSON body to client.set_value via resource PUT
    const put = await page.evaluate(async (args) => {
      const r = await fetch("/api/frappe/api/resource/Employee/" + encodeURIComponent(args.emp), {
        method: "PUT",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(args.set),
      });
      return { status: r.status, body: (await r.text()).slice(0, 500) };
    }, c);

    console.log(`${c.emp}: orig=${JSON.stringify(orig)} -> ${c.set.department}: ${put.status} ${put.body.slice(0,200)}`);
    manifest.push({ emp: c.emp, original: orig, applied: c.set, result: put });
  }

  fs.writeFileSync(
    "F:/Dropbox/Projects/BEI-ERP/output/l3/s167/s167_employee_dept_changes.json",
    JSON.stringify(manifest, null, 2)
  );

  await browser.close();
})().catch(e => console.error(e));
