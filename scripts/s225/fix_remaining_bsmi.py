"""Repoint remaining BSMI references on SM MARIKINA Company to SMK or parent."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

co_name = "SM MARIKINA - BEBANG SM MARIKINA INC."
result = {"before": {}, "fixes": [], "after": {}, "errors": []}

# All fields that might have stale BSMI refs
fields_to_check = [
    "stock_adjustment_account",
    "expenses_included_in_valuation",
    "round_off_cost_center",
    "default_employee_advance_account",
]
for f in fields_to_check:
    v = frappe.db.get_value("Company", co_name, f)
    result["before"][f] = v

# Check if each value exists; if BSMI and broken, find SMK or parent equivalent
parent = "BEBANG ENTERPRISE INC."

REPOINT = {
    "stock_adjustment_account": ("Stock Adjustment - SMK", "Stock Adjustment - Bebang Enterprise Inc.", "Account"),
    "expenses_included_in_valuation": ("Expenses Included In Valuation - SMK", "Expenses Included In Valuation - BEI", "Account"),
    "round_off_cost_center": ("Main - SMK", "Main - BEI", "Cost Center"),
}

for field, (preferred_smk, fallback_parent, doctype) in REPOINT.items():
    cur = result["before"].get(field)
    if not cur:
        continue
    if frappe.db.exists(doctype, cur):
        continue  # current value is valid, leave it
    # current is broken; find replacement
    target = preferred_smk if frappe.db.exists(doctype, preferred_smk) else (fallback_parent if frappe.db.exists(doctype, fallback_parent) else None)
    if not target:
        result["errors"].append(f"{field}: no valid replacement for {cur}")
        continue
    try:
        frappe.db.set_value("Company", co_name, field, target)
        result["fixes"].append({"field": field, "from": cur, "to": target})
    except Exception as e:
        result["errors"].append({"field": field, "error": str(e)[:200]})

frappe.db.commit()

# Verify
for f in fields_to_check:
    result["after"][f] = frappe.db.get_value("Company", co_name, f)

print(json.dumps(result, indent=2, default=str))
