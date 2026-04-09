#!/usr/bin/env python3
"""S167 REDO Phase 6 rollback — delete test data, restore employee depts.
NOT deleted:
  - TEST-STORE-BGC - BEI warehouse (kept as test infra)
  - PCF-TEST-STORE-BGC - BEI fund (pre-existing before S167)
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

report = {"deleted": {}, "restored": {}, "errors": []}

# Target batches/expenses created during S167 (last 48h)
batches = frappe.db.sql("""
    SELECT name, pcf_fund, status, docstatus FROM `tabBEI PCF Batch`
    WHERE creation > DATE_SUB(NOW(), INTERVAL 48 HOUR)
    ORDER BY creation
""", as_dict=True)
print("Batches:", batches)
report["deleted"]["batches_found"] = [b["name"] for b in batches]

# 1. For each batch: cancel if submitted, clear coas, delete items, delete batch
for b in batches:
    name = b["name"]
    try:
        # Clear suggested/final coas on batch items to avoid link validation
        frappe.db.sql("""
            UPDATE `tabBEI PCF Batch Item`
            SET suggested_coa=NULL, final_coa=NULL, coa_confidence=0
            WHERE parent=%s
        """, (name,))

        # Cancel if submitted
        if b["docstatus"] == 1:
            try:
                doc = frappe.get_doc("BEI PCF Batch", name)
                doc.flags.ignore_permissions = True
                doc.flags.ignore_links = True
                doc.cancel()
            except Exception as e:
                print(f"  cancel {name}: {e}")
                # Brute-force: set docstatus=2
                frappe.db.sql("UPDATE `tabBEI PCF Batch` SET docstatus=2 WHERE name=%s", (name,))

        # Delete child items
        frappe.db.sql("DELETE FROM `tabBEI PCF Batch Item` WHERE parent=%s", (name,))

        # Delete batch
        frappe.db.sql("DELETE FROM `tabBEI PCF Batch` WHERE name=%s", (name,))
        print(f"  deleted batch {name}")
    except Exception as e:
        report["errors"].append(f"batch {name}: {e}")
        print(f"  ERROR batch {name}: {e}")

frappe.db.commit()

# 2. Delete expense requests (S167 test data)
exps = frappe.db.sql("""
    SELECT name, status, docstatus, pcf_batch FROM `tabBEI Expense Request`
    WHERE creation > DATE_SUB(NOW(), INTERVAL 48 HOUR)
      AND pcf_fund IN ('PCF-HR and Admin','PCF-Supply Chain','PCF-Commissary','PCF-TEST-STORE-BGC - BEI')
    ORDER BY creation
""", as_dict=True)
print(f"\nExpenses to delete: {len(exps)}")
report["deleted"]["expenses_found"] = [e["name"] for e in exps]

for e in exps:
    nm = e["name"]
    try:
        # Clear naked COA first
        frappe.db.set_value("BEI Expense Request", nm, {"internal_suggested_coa": None, "pcf_batch": None}, update_modified=False)
        if e["docstatus"] == 1:
            try:
                d = frappe.get_doc("BEI Expense Request", nm)
                d.flags.ignore_permissions = True
                d.flags.ignore_links = True
                d.cancel()
            except Exception as ex:
                print(f"  cancel exp {nm}: {ex}")
                frappe.db.sql("UPDATE `tabBEI Expense Request` SET docstatus=2 WHERE name=%s", (nm,))
        frappe.db.sql("DELETE FROM `tabBEI Expense Request` WHERE name=%s", (nm,))
        print(f"  deleted expense {nm}")
    except Exception as ex:
        report["errors"].append(f"expense {nm}: {ex}")
        print(f"  ERROR expense {nm}: {ex}")

frappe.db.commit()

# 3. Delete the 3 dept PCF funds
DEPT_FUNDS = ["PCF-HR and Admin", "PCF-Supply Chain", "PCF-Commissary"]
for f in DEPT_FUNDS:
    try:
        if frappe.db.exists("BEI Petty Cash Fund", f):
            frappe.delete_doc("BEI Petty Cash Fund", f, force=True, ignore_permissions=True)
            print(f"  deleted fund {f}")
            report["deleted"].setdefault("funds", []).append(f)
    except Exception as e:
        report["errors"].append(f"fund {f}: {e}")
        print(f"  ERROR fund {f}: {e}")

frappe.db.commit()

# 4. Restore employee depts (from manifest)
ORIGINALS = {
    "TEST-HR-001":         "Human Resources - BAG",
    "TEST-COMMISSARY-001": "Dispatch - BAG",
    "TEST-WAREHOUSE-001":  "Dispatch - BAG",
}
for emp, orig_dept in ORIGINALS.items():
    try:
        if frappe.db.exists("Employee", emp):
            frappe.db.set_value("Employee", emp, "department", orig_dept, update_modified=False)
            print(f"  restored {emp} -> {orig_dept}")
            report["restored"][emp] = orig_dept
    except Exception as e:
        report["errors"].append(f"restore {emp}: {e}")

frappe.db.commit()

# 5. Verify final state
remaining_exp = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabBEI Expense Request`
    WHERE pcf_fund IN ('PCF-HR and Admin','PCF-Supply Chain','PCF-Commissary')
""")[0][0]
remaining_batches = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabBEI PCF Batch`
    WHERE pcf_fund IN ('PCF-HR and Admin','PCF-Supply Chain','PCF-Commissary')
""")[0][0]
remaining_funds = frappe.db.sql("""
    SELECT name FROM `tabBEI Petty Cash Fund` WHERE fund_type='Department'
""", as_dict=True)
store_fund = frappe.db.get_value("BEI Petty Cash Fund", "PCF-TEST-STORE-BGC - BEI", ["name","is_enabled"], as_dict=True)

print("\n=== POST-ROLLBACK STATE ===")
print(f"  dept expenses remaining: {remaining_exp}")
print(f"  dept batches remaining: {remaining_batches}")
print(f"  dept funds remaining: {remaining_funds}")
print(f"  store fund (preserved): {store_fund}")

report["final"] = {
    "dept_expenses_remaining": remaining_exp,
    "dept_batches_remaining": remaining_batches,
    "dept_funds_remaining": [f["name"] for f in remaining_funds],
    "store_fund_preserved": store_fund,
}
print("\n=== REPORT ===")
print(json.dumps(report, indent=2, default=str))
frappe.destroy()
