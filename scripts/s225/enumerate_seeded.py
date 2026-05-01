"""Enumerate everything seeded by seed_comprehensive.py — query by label/prefix."""
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

# Stock Entries with our label
ses = frappe.db.sql("""
    SELECT name, posting_date, docstatus
    FROM `tabStock Entry`
    WHERE remarks LIKE 'S229 retest seed%%'
      AND creation > NOW() - INTERVAL 1 HOUR
    ORDER BY name
""", as_dict=True)
result["stock_entries"] = ses
result["se_count"] = len(ses)

# BEI Routes created in last hour (filter by creation time only)
routes = frappe.db.sql("""
    SELECT name, cargo_type, source_warehouse, active, creation
    FROM `tabBEI Route`
    WHERE creation > NOW() - INTERVAL 1 HOUR
    ORDER BY name
""", as_dict=True)
result["bei_routes"] = routes
result["route_count"] = len(routes)

# Stock Settings current state
result["stock_settings"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

# Sample bin states for key items
sample_items = ["PM001","FG001","FG002","FG002-A","FG004","FG010","FG023","KL001","KL004"]
sample_bins = {}
for item in sample_items:
    for wh in ["PINNACLE COLD STORAGE SOLUTIONS - BKI", "3MD Logistics - Camangyanan - BKI"]:
        bin_q = frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, ["actual_qty","projected_qty"], as_dict=True)
        if bin_q:
            sample_bins[f"{item}@{wh[:30]}"] = {"actual": float(bin_q.actual_qty or 0), "projected": float(bin_q.projected_qty or 0)}
result["sample_bins"] = sample_bins

print(json.dumps(result, indent=2, default=str))
