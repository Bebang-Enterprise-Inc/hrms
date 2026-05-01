"""PM001 + FG001 specifically at Pinnacle Cold Storage Solutions - BKI."""
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

# All bins for PM001 and FG001
for item in ["PM001", "FG001"]:
    rows = frappe.get_all("Bin",
        filters={"item_code": item},
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty", "ordered_qty", "indented_qty"],
        order_by="actual_qty desc",
        limit=50)
    result[item] = {
        "total_bins": len(rows),
        "all_bins": rows,
    }

# Specifically look up PCS-BKI bins (case insensitive)
pcs_bins = []
for r in result.get("PM001", {}).get("all_bins", []) + result.get("FG001", {}).get("all_bins", []):
    if "PINNACLE" in (r.get("warehouse") or "").upper():
        pcs_bins.append(r)
result["pcs_bki_bins"] = pcs_bins

# Recent stock entries that touched PCS-BKI for these items
recent_se = frappe.db.sql("""
    SELECT sed.parent, sed.s_warehouse, sed.t_warehouse, sed.item_code, sed.qty, se.creation, se.docstatus, se.stock_entry_type
    FROM `tabStock Entry Detail` sed
    JOIN `tabStock Entry` se ON se.name = sed.parent
    WHERE sed.item_code IN ('PM001','FG001')
      AND (sed.s_warehouse LIKE '%PINNACLE%' OR sed.t_warehouse LIKE '%PINNACLE%')
      AND se.creation > NOW() - INTERVAL 4 HOUR
    ORDER BY se.creation DESC
    LIMIT 30
""", as_dict=True)
result["recent_se_touching_pcs"] = recent_se

print(json.dumps(result, indent=2, default=str))
