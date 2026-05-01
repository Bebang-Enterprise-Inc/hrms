"""Check BEI Route configuration for failed stores + understand what cargo_type their items use."""
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

# All BEI Routes
result["bei_route_doctype_exists"] = bool(frappe.db.exists("DocType", "BEI Route"))
if result["bei_route_doctype_exists"]:
    routes = frappe.get_all("BEI Route",
        fields=["name", "active", "cargo_type", "source_warehouse", "modified"],
        limit=100)
    result["all_bei_routes"] = routes
    result["route_count"] = len(routes)

    # Stops per route
    stops = frappe.get_all("BEI Route Stop",
        fields=["parent", "store", "stop_order"],
        limit=200)
    result["all_bei_route_stops"] = stops
    result["stop_count"] = len(stops)

# What's PM001's cargo_category?
pm001 = frappe.get_doc("Item", "PM001")
result["PM001"] = {
    "item_name": pm001.item_name,
    "item_group": pm001.item_group,
    "cargo_category": getattr(pm001, "cargo_category", None),
    "lane": getattr(pm001, "lane", None),
    "is_stock_item": pm001.is_stock_item,
}

# Sample item used in the sweep — find a Material Request line for PM001 or FG001 from sweep window
recent_mri = frappe.db.sql("""
    SELECT mri.parent, mri.warehouse, mri.from_warehouse, mri.item_code, mri.qty,
           mr.creation, mr.status, mr.set_warehouse,
           IFNULL(mr.custom_source_warehouse, '') AS mr_source_wh,
           IFNULL(mr.custom_cargo_lane, '') AS mr_cargo_lane
    FROM `tabMaterial Request Item` mri
    JOIN `tabMaterial Request` mr ON mr.name = mri.parent
    WHERE mri.item_code IN ('PM001','FG001')
      AND mr.creation > NOW() - INTERVAL 4 HOUR
    ORDER BY mr.creation DESC
    LIMIT 10
""", as_dict=True)
result["recent_mr_lines"] = recent_mri

print(json.dumps(result, indent=2, default=str))
