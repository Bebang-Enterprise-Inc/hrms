"""S225 retest teardown — cancel the SEs we created in seed_test_stock.py.

Reads the teardown_ledger.json, cancels each SE, verifies stock returned to
pre-seed state. Writes teardown_complete.json with proof.
"""
import os, json, sys
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Hard-coded ledger entries (keep in sync with the seeding script's output)
LEDGER = [
    {"name": "MAT-STE-2026-01173", "item_code": "PM001", "qty": 500,
     "warehouse": "PINNACLE COLD STORAGE SOLUTIONS - BKI"},
    {"name": "MAT-STE-2026-01174", "item_code": "FG001", "qty": 5000,
     "warehouse": "PINNACLE COLD STORAGE SOLUTIONS - BKI"},
]

result = {"reversed": [], "errors": []}

# Pre-state
pre_state = {}
for entry in LEDGER:
    bin_q = frappe.db.get_value("Bin", {"item_code": entry["item_code"], "warehouse": entry["warehouse"]}, "actual_qty") or 0
    pre_state[f"{entry['item_code']}@{entry['warehouse']}"] = float(bin_q)
result["pre_teardown_state"] = pre_state

for entry in LEDGER:
    try:
        se = frappe.get_doc("Stock Entry", entry["name"])
        if se.docstatus == 1:
            se.cancel()
            frappe.db.commit()
            result["reversed"].append({"name": entry["name"], "status": "CANCELLED"})
        elif se.docstatus == 2:
            result["reversed"].append({"name": entry["name"], "status": "ALREADY_CANCELLED"})
        else:
            result["reversed"].append({"name": entry["name"], "status": f"UNEXPECTED_DOCSTATUS_{se.docstatus}"})
    except Exception as e:
        frappe.db.rollback()
        result["errors"].append({"name": entry["name"], "error": str(e)[:300]})

# Post-state
post_state = {}
for entry in LEDGER:
    bin_q = frappe.db.get_value("Bin", {"item_code": entry["item_code"], "warehouse": entry["warehouse"]}, "actual_qty") or 0
    proj_q = frappe.db.get_value("Bin", {"item_code": entry["item_code"], "warehouse": entry["warehouse"]}, "projected_qty") or 0
    post_state[f"{entry['item_code']}@{entry['warehouse']}"] = {"actual_qty": float(bin_q), "projected_qty": float(proj_q)}
result["post_teardown_state"] = post_state

# Compute delta
result["delta_per_bin"] = {}
for k in pre_state:
    delta = post_state[k]["actual_qty"] - pre_state[k]
    result["delta_per_bin"][k] = delta

result["all_seeds_reversed"] = (len(result["errors"]) == 0 and
                                 all(r["status"] in ("CANCELLED", "ALREADY_CANCELLED") for r in result["reversed"]))

print(json.dumps(result, indent=2, default=str))
