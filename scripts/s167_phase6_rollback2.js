/**
 * S167 Phase 6 rollback — second pass.
 * Strategy: delete bottom-up with link-clearing:
 *   1. Clear pcf_batch + pcf_fund on all test expenses (breaks the link)
 *   2. Delete BEI PCF Batch Item child rows (by batch parent)
 *   3. Delete BEI PCF Batch docs
 *   4. Delete BEI Expense Request docs
 *   5. Delete BEI Petty Cash Fund docs
 */
const { login, newBrowser } = require("./s167_lib");
const fs = require("fs");

const BATCHES = ["BEI-PCF-2026-00003", "BEI-PCF-2026-00004"];
const EXPENSES = ["BEI-EXP-2026-00078", "BEI-EXP-2026-00079", "BEI-EXP-2026-00080", "BEI-EXP-2026-00081"];
const FUNDS = ["PCF-HR and Admin", "PCF-Commissary"];

async function setValue(page, doctype, name, fieldset) {
  return await page.evaluate(async (args) => {
    const r = await fetch("/api/frappe/api/resource/" + encodeURIComponent(args.doctype) + "/" + encodeURIComponent(args.name), {
      method: "PUT",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(args.fieldset),
    });
    return { s: r.status, b: (await r.text()).slice(0, 300) };
  }, { doctype, name, fieldset });
}
async function del(page, doctype, name) {
  return await page.evaluate(async (args) => {
    const r = await fetch("/api/frappe/api/method/frappe.client.delete", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ doctype: args.doctype, name: args.name }),
    });
    return { s: r.status, b: (await r.text()).slice(0, 300) };
  }, { doctype, name });
}

(async () => {
  const { browser, page } = await newBrowser();
  await login(page, "sam");
  const log = [];

  // 1. Clear pcf_batch link on all expenses
  console.log("\n[1] Clear pcf_batch on expenses");
  for (const e of EXPENSES) {
    const r = await setValue(page, "BEI Expense Request", e, { pcf_batch: null });
    console.log(`  ${e}: ${r.s}`);
    log.push({ op: "clear_pcf_batch", name: e, result: r });
  }

  // 2. Get BEI PCF Batch Item names for both batches
  const itemNames = [];
  for (const b of BATCHES) {
    const info = await page.evaluate(async (batch) => {
      const r = await fetch("/api/frappe/api/resource/BEI PCF Batch/" + encodeURIComponent(batch), { credentials: "include" });
      const j = await r.json();
      return (j.data?.items || []).map(i => i.name);
    }, b);
    console.log(`\n[2] Items in ${b}: ${info.join(", ")}`);
    itemNames.push(...info);
  }

  // 3. Delete batch items first
  console.log("\n[3] Delete batch items");
  for (const it of itemNames) {
    const r = await del(page, "BEI PCF Batch Item", it);
    console.log(`  ${it}: ${r.s}`);
    log.push({ op: "delete_batch_item", name: it, result: r });
  }

  // 4. Delete batches
  console.log("\n[4] Delete batches");
  for (const b of BATCHES) {
    const r = await del(page, "BEI PCF Batch", b);
    console.log(`  ${b}: ${r.s} ${r.b.slice(0, 150)}`);
    log.push({ op: "delete_batch", name: b, result: r });
  }

  // 5. Delete expenses
  console.log("\n[5] Delete expenses");
  for (const e of EXPENSES) {
    const r = await del(page, "BEI Expense Request", e);
    console.log(`  ${e}: ${r.s} ${r.b.slice(0, 150)}`);
    log.push({ op: "delete_expense", name: e, result: r });
  }

  // 6. Delete funds
  console.log("\n[6] Delete funds");
  for (const f of FUNDS) {
    const r = await del(page, "BEI Petty Cash Fund", f);
    console.log(`  ${f}: ${r.s} ${r.b.slice(0, 150)}`);
    log.push({ op: "delete_fund", name: f, result: r });
  }

  // 7. Sanity
  const final = await page.evaluate(async () => {
    const r = await fetch("/api/pcf?action=get_all_pcf_funds", { credentials: "include" });
    const j = await r.json();
    return (j.data || []).filter(f => f.fund_type === "Department").map(f => f.name);
  });
  console.log("\nRemaining dept funds:", final);

  fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/phase6_rollback2_log.json", JSON.stringify(log, null, 2));
  await browser.close();
})().catch(e => { console.error("FATAL", e); process.exit(1); });
