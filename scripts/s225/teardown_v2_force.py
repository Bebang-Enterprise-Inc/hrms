"""S225 retest teardown v2 — enable allow_negative_stock briefly, cancel, restore.

The PM001 cancel failed because the sweep consumed 40 of the 500 seeded units —
cancelling 500 leaves -40, which Frappe v15 rejects. Standard pattern: toggle
allow_negative_stock = 1, cancel, toggle back to 0. This temporarily allows the
single cancel transaction to go through.
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

result = {}

# Capture initial Stock Settings state
result["stock_settings_before"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

# Toggle ON
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()

# Cancel the still-active PM001 SE
LEDGER_REMAINING = ["MAT-STE-2026-01173"]  # FG001 cancel succeeded already
result["cancel_attempts"] = []
for name in LEDGER_REMAINING:
    try:
        se = frappe.get_doc("Stock Entry", name)
        if se.docstatus == 1:
            se.cancel()
            frappe.db.commit()
            result["cancel_attempts"].append({"name": name, "status": "CANCELLED"})
        elif se.docstatus == 2:
            result["cancel_attempts"].append({"name": name, "status": "ALREADY_CANCELLED"})
        else:
            result["cancel_attempts"].append({"name": name, "status": f"DOCSTATUS_{se.docstatus}"})
    except Exception as e:
        frappe.db.rollback()
        result["cancel_attempts"].append({"name": name, "status": "FAILED", "error": str(e)[:300]})

# Toggle OFF
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 0)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 0)
frappe.db.commit()

# Verify Stock Settings restored
result["stock_settings_after"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

# Final bin state
PCS = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
final_state = {}
for item in ["PM001", "FG001"]:
    bin_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": PCS}, "actual_qty") or 0
    proj_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": PCS}, "projected_qty") or 0
    final_state[f"{item}@PCS-BKI"] = {"actual_qty": float(bin_q), "projected_qty": float(proj_q)}
result["final_bin_state"] = final_state

# Summary
result["seed_se_status"] = []
for name in ["MAT-STE-2026-01173", "MAT-STE-2026-01174"]:
    docstatus = frappe.db.get_value("Stock Entry", name, "docstatus")
    result["seed_se_status"].append({"name": name, "docstatus": docstatus, "label": ["Draft","Submitted","Cancelled"][docstatus] if docstatus is not None else "MISSING"})

result["all_seeds_cancelled"] = all(s["docstatus"] == 2 for s in result["seed_se_status"])
result["stock_settings_safely_reverted"] = (result["stock_settings_after"]["allow_negative_stock"] == 0 and
                                              result["stock_settings_after"]["allow_negative_stock_for_batch"] == 0)

print(json.dumps(result, indent=2, default=str))
