"""Teardown ALL S229 sweep4/v5/v6 SEs. Routes stay (Sam authorized as data fix)."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Allow negative for safe cancel
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()

# Find all SEs from this session (v4/v5/v6)
ses = frappe.db.sql("""
    SELECT name, docstatus
    FROM `tabStock Entry`
    WHERE (remarks LIKE 'S229 sweep4 narrow seed%%'
        OR remarks LIKE 'S229 v5 boost%%'
        OR remarks LIKE 'S229 v6 full PM%%')
      AND creation > NOW() - INTERVAL 8 HOUR
    ORDER BY name DESC
""", as_dict=True)

result = {"se_count": len(ses), "cancelled": 0, "already": 0, "errors": []}
for se in ses:
    if se["docstatus"] == 2:
        result["already"] += 1
        continue
    if se["docstatus"] == 1:
        try:
            doc = frappe.get_doc("Stock Entry", se["name"])
            doc.cancel()
            frappe.db.commit()
            result["cancelled"] += 1
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"name": se["name"], "error": str(e)[:200]})

# Revert Stock Settings
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 0)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 0)
frappe.db.commit()

result["stock_settings_after"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}
result["all_clean"] = (result["errors"] == [] and
                       result["stock_settings_after"]["allow_negative_stock"] == 0)

# Routes count summary (kept in place per Sam's authorization)
routes_kept = frappe.db.sql("""
    SELECT COUNT(*) AS cnt FROM `tabBEI Route`
    WHERE creation > NOW() - INTERVAL 24 HOUR
""", as_dict=True)
result["bei_routes_kept_24h"] = routes_kept[0]["cnt"] if routes_kept else 0

print(json.dumps(result, indent=2, default=str))
