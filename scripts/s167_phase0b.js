/**
 * S167 Phase 0 (workaround) — create funds via direct /api/pcf POST with correct Frappe dept names.
 * Also: discover what Frappe Department names actually exist.
 */
const { BASE, login, newBrowser, recordForm, recordState } = require("./s167_lib");
const fs = require("fs");

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");

  // Use literal Frappe dept names from plan pre-conditions
  const picked = [
    { label: "HR",         deptName: "HR and Admin - BEI",   custodian: "test.hr@bebang.ph"         },
    { label: "SupplyChain",deptName: "Supply Chain - BEI",   custodian: "test.warehouse@bebang.ph"  },
    { label: "Commissary", deptName: "Commissary - BEI",     custodian: "test.commissary@bebang.ph" },
  ];
  console.log("\nPicked mapping:");
  picked.forEach(p => console.log(`  ${p.label}: ${p.deptName || "NOT FOUND"}`));

  const created = [];
  for (const p of picked) {
    if (!p.deptName) {
      console.log(`  SKIP ${p.label}: no matching dept in Frappe`);
      continue;
    }
    const body = {
      action: "create_pcf_fund",
      fund_type: "Department",
      department: p.deptName,
      custodian: p.custodian,
      fund_amount: 5000,
      threshold_percentage: 60,
    };
    const res = await page.evaluate(async (b) => {
      try {
        const r = await fetch("/api/pcf", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(b),
        });
        const t = await r.text();
        return { status: r.status, body: t.slice(0, 2000) };
      } catch (e) { return { error: String(e) }; }
    }, body);
    console.log(`  CREATE ${p.label} -> status ${res.status} body ${(res.body||"").slice(0,200)}`);
    created.push({ label: p.label, deptName: p.deptName, custodian: p.custodian, result: res });
    recordForm({
      scenario: `0.1_${p.label}`,
      form: "create_department_fund_via_api",
      inputs: body,
      submit_action: "POST /api/pcf",
      response: `status=${res.status} body=${(res.body||"").slice(0,300)}`,
    });
    recordState({
      scenario: `0.1_${p.label}`,
      check: `fund_created_${p.label}`,
      before: "no dept fund",
      after: res.status === 200 ? "created" : `error_${res.status}`,
      passed: res.status === 200,
      notes: (res.body||"").slice(0, 300),
    });
  }

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase0b_created.json", JSON.stringify(created, null, 2));
  await browser.close();
})().catch(e => { console.error("FATAL", e); process.exit(1); });
