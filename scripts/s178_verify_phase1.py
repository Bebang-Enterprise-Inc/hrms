#!/usr/bin/env python3
"""S178 Phase 1 verification — compact output only."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

r = {}

# 1. Orphan count on BEI
r["orphans"] = frappe.db.sql("""
    SELECT a.name, a.parent_account FROM `tabAccount` a
    LEFT JOIN `tabAccount` p ON a.parent_account = p.name
    WHERE a.company = 'Bebang Enterprise Inc.'
      AND a.parent_account IS NOT NULL AND a.parent_account != ''
      AND p.name IS NULL
""", as_dict=True)
r["orphan_count"] = len(r["orphans"])

# 2. BEI Settings
r["input_vat"] = frappe.db.get_single_value("BEI Settings", "input_vat_goods_account")
r["input_vat_exists"] = bool(frappe.db.exists("Account", r["input_vat"])) if r["input_vat"] else False

# 3. store_locations column
r["col_exists"] = bool(frappe.db.sql("SHOW COLUMNS FROM `tabCompany` LIKE 'store_locations'"))
if r["col_exists"]:
    r["companies_with_stores"] = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != ''"
    )[0][0]
    r["sample"] = frappe.db.sql(
        "SELECT name, store_locations FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != '' LIMIT 5",
        as_dict=True
    )
else:
    r["companies_with_stores"] = 0

# 4. Custom Field
r["cf_exists"] = bool(frappe.db.exists("Custom Field", "Company-store_locations"))

# 5. The 4 specific orphan accounts
for acct in ["STOCK ADJUSTMENT - BEI", "GR/IR CLEARING - BEI",
             "PROPERTY, PLANT AND EQUIPMENT - BEI", "ADVANCES TO SSS - BEI"]:
    info = frappe.db.get_value("Account", acct, ["parent_account"], as_dict=True)
    parent_valid = False
    if info and info.get("parent_account"):
        parent_valid = bool(frappe.db.exists("Account", info["parent_account"]))
    r[f"orphan_{acct[:20]}"] = {"parent": info.get("parent_account") if info else None, "valid": parent_valid}

r["all_pass"] = (
    r["orphan_count"] == 0
    and r["input_vat_exists"]
    and r["col_exists"]
    and r["companies_with_stores"] >= 35
)

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
