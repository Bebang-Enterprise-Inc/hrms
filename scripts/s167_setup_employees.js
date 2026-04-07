/**
 * S167 setup — create minimal Employee records linking test users to their
 * target dept/branch so the PCF resolver works. All changes are tracked in
 * s167_data_manifest.json for Phase 6 rollback.
 *
 * Strategy: use existing un-linked employees and SET their user_id via
 * frappe.client.set_value. This is minimal and fully reversible.
 *   - test.hr@bebang.ph    -> Employee 9001789 (HR and Admin - BEI)
 *   - test.commissary@bebang.ph -> Employee 9000005 (Commissary - BEI)
 * For the store tests, we need branch=TEST-STORE-BGC employees but none
 * exist, so we temporarily move 2 HR employees (with no user_id) into
 * TEST-STORE-BGC branch + store department + link test.staff / test.supervisor.
 *   - test.staff@bebang.ph -> Employee 9000070 (save original branch + department)
 *   - test.supervisor@bebang.ph -> Employee 9000103 (same)
 */
const { login, newBrowser } = require("./s167_lib");
const fs = require("fs");

const EMPS = [
  // { emp, user, fields:{...}, reason }
  {
    emp: "9001789",
    user: "test.hr@bebang.ph",
    set: { user_id: "test.hr@bebang.ph" },
    // department already = HR and Admin - BEI
    reason: "link test.hr to existing HR employee",
  },
  {
    emp: "9000005",
    user: "test.commissary@bebang.ph",
    set: { user_id: "test.commissary@bebang.ph" },
    reason: "link test.commissary to existing Commissary employee",
  },
  {
    emp: "9000070",
    user: "test.staff@bebang.ph",
    set: { user_id: "test.staff@bebang.ph", branch: "TEST-STORE-BGC" },
    reason: "link test.staff + move to TEST-STORE-BGC branch for Phase 1",
  },
  {
    emp: "9000103",
    user: "test.supervisor@bebang.ph",
    set: { user_id: "test.supervisor@bebang.ph", branch: "TEST-STORE-BGC" },
    reason: "link test.supervisor + move to TEST-STORE-BGC branch for Phase 1",
  },
];

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");

  const manifest = [];
  for (const e of EMPS) {
    // 1. Read original values
    const fields = Object.keys(e.set);
    const orig = await page.evaluate(async (args) => {
      const r = await fetch("/api/frappe/api/method/frappe.client.get_value", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          doctype: "Employee",
          filters: JSON.stringify({ name: args.emp }),
          fieldname: JSON.stringify(args.fields),
        }).toString(),
      });
      return await r.text();
    }, { emp: e.emp, fields });
    let origParsed = {};
    try { origParsed = JSON.parse(orig).message || {}; } catch {}
    console.log(`\n${e.emp} (${e.user}) original:`, origParsed);

    // 2. Apply changes
    const setRes = await page.evaluate(async (args) => {
      const r = await fetch("/api/frappe/api/method/frappe.client.set_value", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          doctype: "Employee",
          name: args.emp,
          fieldname: JSON.stringify(args.set),
        }).toString(),
      });
      return { status: r.status, body: (await r.text()).slice(0, 1000) };
    }, { emp: e.emp, set: e.set });
    console.log(`  set -> ${setRes.status}:`, setRes.body.slice(0, 250));

    manifest.push({
      emp: e.emp,
      user: e.user,
      changed_fields: e.set,
      original_values: origParsed,
      set_result: setRes,
      reason: e.reason,
    });
  }

  fs.writeFileSync(
    "F:/Dropbox/Projects/BEI-ERP/output/l3/s167/s167_employee_changes.json",
    JSON.stringify(manifest, null, 2)
  );
  console.log("\nManifest written — needed for Phase 6 rollback");

  await browser.close();
})().catch(e => console.error("FATAL", e));
