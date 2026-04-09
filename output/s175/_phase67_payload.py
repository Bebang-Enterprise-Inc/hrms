
#!/usr/bin/env python3
import os, json, sys, traceback
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True

BEI = "Bebang Enterprise Inc."
BKI = "Bebang Kitchen Inc."
result = {"phase6": {}, "phase7": {}}

# ===== PHASE 6: BEI 6xxxxxx =====
p6 = result["phase6"]

# HB-4 gate: re-verify 0 GL entries
gl_count = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabGL Entry` ge
    JOIN `tabAccount` a ON ge.account=a.name
    WHERE a.company=%s AND a.account_number LIKE '6%%'
""", BEI)[0][0]
p6["gl_count_pre"] = gl_count
if gl_count != 0:
    p6["HB4_BLOCKED"] = True
    print("S175_P67_JSON_START")
    print(json.dumps(result, default=str))
    print("S175_P67_JSON_END")
    sys.exit(0)

# Pre-update snapshot (rollback artifact)
pre_snapshot = frappe.db.sql("""
    SELECT name, account_number, account_name, root_type, report_type
    FROM `tabAccount` WHERE company=%s AND account_number LIKE '6%%'
    ORDER BY account_number
""", BEI, as_dict=True)
p6["pre_count"] = len(pre_snapshot)
p6["pre_breakdown"] = {}
for r in pre_snapshot:
    key = f"{r['root_type']}|{r['report_type']}"
    p6["pre_breakdown"][key] = p6["pre_breakdown"].get(key, 0) + 1

# Bulk UPDATE
rows_updated = frappe.db.sql("""
    UPDATE `tabAccount`
    SET root_type='Expense', report_type='Profit and Loss'
    WHERE company=%s AND account_number LIKE '6%%' AND root_type='Income'
""", BEI)
frappe.db.commit()

# Post verify
post_breakdown = frappe.db.sql("""
    SELECT root_type, COUNT(*)
    FROM `tabAccount` WHERE company=%s AND account_number LIKE '6%%'
    GROUP BY root_type
""", BEI, as_list=True)
p6["post_breakdown"] = {r[0]: r[1] for r in post_breakdown}
p6["post_income_count"] = p6["post_breakdown"].get("Income", 0)
p6["post_expense_count"] = p6["post_breakdown"].get("Expense", 0)
p6["success"] = (p6["post_income_count"] == 0 and p6["post_expense_count"] >= 136)

# Save snapshot to container file (too big for stdout if we embed)
snapshot_path = "/tmp/phase6_pretouch_backup.json"
with open(snapshot_path, "w") as f:
    json.dump(pre_snapshot, f, default=str, indent=2)
p6["snapshot_path"] = snapshot_path

# ===== PHASE 7: BEI Settings cutover =====
p7 = result["phase7"]

# Resolve new account: 4000210 DELIVERIES on BKI
new_account = frappe.db.get_value(
    "Account",
    {"company": BKI, "account_number": "4000210", "account_name": "DELIVERIES"},
    "name",
)
p7["new_account"] = new_account
if not new_account:
    p7["HB1_BLOCKED"] = "4000210 DELIVERIES - BKI not found"
    print("S175_P67_JSON_START")
    print(json.dumps(result, default=str))
    print("S175_P67_JSON_END")
    sys.exit(0)

# Current value
bs = frappe.get_single("BEI Settings")
p7["old_value"] = bs.bki_sales_income_account
frappe.db.set_single_value("BEI Settings", "bki_sales_income_account", new_account)
frappe.db.commit()

# Verify
bs2 = frappe.get_single("BEI Settings")
p7["new_value"] = bs2.bki_sales_income_account
p7["linked_account_exists"] = bool(frappe.db.exists("Account", bs2.bki_sales_income_account))

print("S175_P67_JSON_START")
print(json.dumps(result, default=str))
print("S175_P67_JSON_END")
frappe.destroy()
