/**
 * S167 Phase 6 — Rollback all test data created during this run.
 *
 * Order matters: items belong to batches belong to funds. Expenses can be
 * independent but are linked to funds. Restore employee dept changes last.
 *
 * Rollback:
 *   1. Cancel + delete BEI PCF Batches: BEI-PCF-2026-00003 (Approved) + 00004 (Rejected)
 *   2. Delete the 4 Expense Requests that belonged to those batches
 *   3. Delete the 3 dept PCF funds: PCF-HR and Admin, PCF-Supply Chain, PCF-Commissary
 *   4. Restore PCF-HR and Admin fund settings (fund_amount 5000 -> original 10000 if different)
 *      Actually 5000 was what we created it with — N/A, the fund is being deleted
 *   5. Restore TEST-HR-001, TEST-COMMISSARY-001, TEST-WAREHOUSE-001 departments to original values
 */
const { login, newBrowser } = require("./s167_lib");
const fs = require("fs");

const BATCHES = ["BEI-PCF-2026-00003", "BEI-PCF-2026-00004"];
const EXPENSES = ["BEI-EXP-2026-00078", "BEI-EXP-2026-00079"]; // HR + will also need commissary ones
const FUNDS = ["PCF-HR and Admin", "PCF-Supply Chain", "PCF-Commissary"];

async function del(page, doctype, name) {
  return await page.evaluate(async (args) => {
    const r = await fetch("/api/frappe/api/method/frappe.client.delete", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ doctype: args.doctype, name: args.name }),
    });
    return { s: r.status, b: (await r.text()).slice(0, 400) };
  }, { doctype, name });
}

async function setValue(page, doctype, name, fieldset) {
  return await page.evaluate(async (args) => {
    const r = await fetch("/api/frappe/api/resource/" + encodeURIComponent(args.doctype) + "/" + encodeURIComponent(args.name), {
      method: "PUT",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args.fieldset),
    });
    return { s: r.status, b: (await r.text()).slice(0, 400) };
  }, { doctype, name, fieldset });
}

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");

  const log = [];

  // 1. Get commissary expense names (we don't have them pre-saved)
  const commiBatch = await page.evaluate(async () => {
    const r = await fetch("/api/frappe/api/resource/BEI PCF Batch/BEI-PCF-2026-00004", { credentials: "include" });
    const j = await r.json();
    return j.data;
  });
  const commiExpenses = (commiBatch?.items || []).map(i => i.expense_request);
  console.log("Commissary batch items:", (commiBatch?.items || []).length, "expenses:", commiExpenses);
  const ALL_EXPENSES = [...EXPENSES, ...commiExpenses];

  // 2. Cancel + delete batches (cancel first if submitted)
  for (const b of BATCHES) {
    try {
      const cancel = await page.evaluate(async (name) => {
        const r = await fetch("/api/frappe/api/method/frappe.client.cancel", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ doctype: "BEI PCF Batch", name }),
        });
        return { s: r.status, b: (await r.text()).slice(0, 300) };
      }, b);
      console.log(`cancel ${b}:`, cancel.s, cancel.b.slice(0, 150));
    } catch {}
    const r = await del(page, "BEI PCF Batch", b);
    console.log(`delete batch ${b}:`, r.s, r.b.slice(0, 150));
    log.push({ op: "delete_batch", name: b, result: r });
  }

  // 3. Delete expense requests
  for (const e of ALL_EXPENSES) {
    if (!e) continue;
    try {
      await page.evaluate(async (name) => {
        await fetch("/api/frappe/api/method/frappe.client.cancel", {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ doctype: "BEI Expense Request", name }),
        });
      }, e);
    } catch {}
    const r = await del(page, "BEI Expense Request", e);
    console.log(`delete expense ${e}:`, r.s, r.b.slice(0, 150));
    log.push({ op: "delete_expense", name: e, result: r });
  }

  // 4. Delete dept PCF funds
  for (const f of FUNDS) {
    const r = await del(page, "BEI Petty Cash Fund", f);
    console.log(`delete fund ${f}:`, r.s, r.b.slice(0, 150));
    log.push({ op: "delete_fund", name: f, result: r });
  }

  // 5. Restore employee department changes
  try {
    const changes = JSON.parse(fs.readFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/s167_employee_dept_changes.json", "utf8"));
    for (const c of changes) {
      const restore = {};
      for (const [k, origVal] of Object.entries(c.original)) {
        if (origVal !== undefined) restore[k] = origVal;
      }
      const r = await setValue(page, "Employee", c.emp, restore);
      console.log(`restore ${c.emp} -> ${JSON.stringify(restore)}:`, r.s);
      log.push({ op: "restore_employee", emp: c.emp, fields: restore, result: r });
    }
  } catch (e) { console.log("restore employees failed:", e.message); }

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase6_rollback_log.json", JSON.stringify(log, null, 2));

  // 6. Sanity: confirm dept funds are gone
  const finalFunds = await page.evaluate(async () => {
    const r = await fetch("/api/pcf?action=get_all_pcf_funds", { credentials: "include" });
    const j = await r.json();
    return (j.data || []).filter(f => f.fund_type === "Department").map(f => f.name);
  });
  console.log("\nRemaining dept funds:", finalFunds);

  await browser.close();
  console.log("\n=== Phase 6 rollback done ===");
})().catch(e => { console.error("FATAL", e); process.exit(1); });
