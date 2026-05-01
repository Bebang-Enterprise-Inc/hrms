"""Specifically: does PM001 have ANY bin at PCS-BKI? And what about indented/ordered?"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}
PCS = "PINNACLE COLD STORAGE SOLUTIONS - BKI"

for item in ["PM001", "FG001"]:
    # Get ALL Bin rows for this item at PCS (or anywhere with PINNACLE)
    rows = frappe.db.sql(f"""
        SELECT warehouse, item_code, actual_qty, reserved_qty, ordered_qty, indented_qty, planned_qty, projected_qty, reserved_qty_for_production
        FROM `tabBin`
        WHERE item_code = '{item}'
          AND warehouse LIKE '%PINNACLE%'
    """, as_dict=True)
    result[item] = rows

# Item master defaults
for item in ["PM001", "FG001"]:
    item_doc = frappe.get_doc("Item", item)
    item_defaults = []
    for d in (item_doc.item_defaults or []):
        item_defaults.append({
            "company": d.company,
            "default_warehouse": d.default_warehouse,
            "default_supplier": d.default_supplier,
        })
    result[f"{item}_master"] = {
        "item_group": item_doc.item_group,
        "stock_uom": item_doc.stock_uom,
        "is_stock_item": item_doc.is_stock_item,
        "include_item_in_manufacturing": item_doc.include_item_in_manufacturing,
        "item_defaults": item_defaults,
    }

# Recent open MRs that requested PM001 at PCS-BKI
recent_mr = frappe.db.sql("""
    SELECT mri.parent, mri.warehouse, mri.qty, mri.ordered_qty, mri.received_qty, mri.stock_qty,
           mr.status, mr.material_request_type, mr.transaction_date
    FROM `tabMaterial Request Item` mri
    JOIN `tabMaterial Request` mr ON mr.name = mri.parent
    WHERE mri.item_code = 'PM001'
      AND mri.warehouse LIKE '%PINNACLE%'
      AND mr.creation > NOW() - INTERVAL 4 HOUR
    ORDER BY mr.creation DESC
    LIMIT 10
""", as_dict=True)
result["recent_mrs_pm001_pcs"] = recent_mr

print(json.dumps(result, indent=2, default=str))
