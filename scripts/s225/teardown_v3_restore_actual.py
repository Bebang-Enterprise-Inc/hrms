"""S225 teardown v3 — restore actual_qty to pre-seed levels.

After v2 force-cancel, PM001 actual=-40 and FG001 actual=3523 (vs pre-seed 0
and 3683). The deltas (-40 PM001, -160 FG001) are real consumption by sweep MRs
that the spec's cleanup didn't reverse. Add them back via Material Receipt so
the bins match pre-seed actual_qty.

This leaves indented_qty (commitments from sweep MRs) as-is — those are real
test-created records that need separate cleanup from the spec's mechanisms.
"""
import os, json
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
RESTORATIONS = [
    # (item, qty_to_add_back, label)
    ("PM001", 40, "S225 retest teardown: restore PM001 to pre-seed (sweep consumed 40)"),
    ("FG001", 160, "S225 retest teardown: restore FG001 to pre-seed (sweep consumed 160)"),
]

result = {"restored": [], "errors": []}

for item, qty, label in RESTORATIONS:
    try:
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt"
        se.purpose = "Material Receipt"
        se.posting_date = nowdate()
        se.posting_time = now_datetime().strftime("%H:%M:%S")
        se.set_posting_time = 1
        se.company = frappe.db.get_value("Warehouse", PCS, "company")
        se.append("items", {
            "item_code": item,
            "qty": qty,
            "uom": frappe.db.get_value("Item", item, "stock_uom") or "Nos",
            "stock_uom": frappe.db.get_value("Item", item, "stock_uom") or "Nos",
            "conversion_factor": 1,
            "t_warehouse": PCS,
            "basic_rate": 1.0,
            "allow_zero_valuation_rate": 1,
        })
        se.remarks = label
        se.insert(ignore_permissions=True)
        se.submit()
        frappe.db.commit()
        result["restored"].append({"name": se.name, "item": item, "qty": qty})
    except Exception as e:
        frappe.db.rollback()
        result["errors"].append({"item": item, "qty": qty, "error": str(e)[:300]})

# Final state
final = {}
for item in ["PM001", "FG001"]:
    bin_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": PCS}, "actual_qty") or 0
    proj_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": PCS}, "projected_qty") or 0
    final[f"{item}@PCS-BKI"] = {"actual_qty": float(bin_q), "projected_qty": float(proj_q)}
result["final_state"] = final

# Pre-seed reference
result["pre_seed_reference"] = {
    "PM001@PCS-BKI": {"actual_qty": 0.0, "projected_qty": 0.0},
    "FG001@PCS-BKI": {"actual_qty": 3683.0, "projected_qty": -2314.0},
}

# Comparison
result["actual_qty_matches_pre_seed"] = {
    "PM001": final["PM001@PCS-BKI"]["actual_qty"] == 0.0,
    "FG001": final["FG001@PCS-BKI"]["actual_qty"] == 3683.0,
}

print(json.dumps(result, indent=2, default=str))
