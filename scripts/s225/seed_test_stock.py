"""S225 re-test seeding: top up PM001 + FG001 at PINNACLE COLD STORAGE - BKI.

Per /l3-v2-bei-erp Test Data Seeding rule: seed missing test data via
/frappe-bulk-edits (or its underlying SSM/Frappe pattern) BEFORE running
scenarios that depend on it. Track in teardown_ledger.json. Tear down at closeout.

This script runs INSIDE the production frappe_backend container.
Returns JSON with the seeded SE names for the teardown ledger.
"""
import os, json, sys
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
from frappe.utils import nowdate, now_datetime
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

PCS = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
SEED_PLAN = [
    # (item_code, qty_to_add, target_warehouse, label)
    ("PM001", 500, PCS, "S225 retest seed: PM001 at PCS-BKI"),
    ("FG001", 5000, PCS, "S225 retest seed: FG001 at PCS-BKI"),
]

result = {"seeded_stock_entries": [], "errors": []}

# Pre-state for ledger
pre_state = {}
for item, qty, wh, label in SEED_PLAN:
    bin_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, "actual_qty") or 0
    pre_state[f"{item}@{wh}"] = float(bin_q)
result["pre_state"] = pre_state

# Resolve item rate (use last purchase / valuation rate or just 1.0 for non-stock-impact test seed)
def get_item_rate(item_code):
    rate = frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate") or 0
    if rate and float(rate) > 0:
        return float(rate)
    return 1.0  # fallback for test seeding


for item_code, qty, target_wh, label in SEED_PLAN:
    try:
        rate = get_item_rate(item_code)
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt"
        se.purpose = "Material Receipt"
        se.posting_date = nowdate()
        se.posting_time = now_datetime().strftime("%H:%M:%S")
        se.set_posting_time = 1
        se.company = frappe.db.get_value("Warehouse", target_wh, "company")
        se.append("items", {
            "item_code": item_code,
            "qty": qty,
            "uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
            "stock_uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
            "conversion_factor": 1,
            "t_warehouse": target_wh,
            "basic_rate": rate,
            "allow_zero_valuation_rate": 1,
        })
        se.remarks = label
        se.insert(ignore_permissions=True)
        se.submit()
        frappe.db.commit()
        result["seeded_stock_entries"].append({
            "name": se.name,
            "item_code": item_code,
            "qty": qty,
            "warehouse": target_wh,
            "label": label,
            "doctype": "Stock Entry",
            "action_to_reverse": "CANCEL",
        })
    except Exception as e:
        frappe.db.rollback()
        result["errors"].append({"item": item_code, "qty": qty, "wh": target_wh, "error": str(e)[:300]})

# Post-state
post_state = {}
for item, qty, wh, label in SEED_PLAN:
    bin_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, "actual_qty") or 0
    proj_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, "projected_qty") or 0
    post_state[f"{item}@{wh}"] = {"actual_qty": float(bin_q), "projected_qty": float(proj_q)}
result["post_state"] = post_state

print(json.dumps(result, indent=2, default=str))
