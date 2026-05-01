"""Teardown for v3 narrow seed — matches 'S229 narrow seed' label."""
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

ses = frappe.db.sql("""
    SELECT name, docstatus
    FROM `tabStock Entry`
    WHERE remarks LIKE 'S229 narrow seed%%'
      AND creation > NOW() - INTERVAL 4 HOUR
    ORDER BY name DESC
""", as_dict=True)

result = {"se_count": len(ses), "cancelled": [], "errors": []}
for se in ses:
    if se["docstatus"] == 1:
        try:
            doc = frappe.get_doc("Stock Entry", se["name"])
            doc.cancel()
            frappe.db.commit()
            result["cancelled"].append(se["name"])
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
result["all_clean"] = (result["errors"] == [] and result["stock_settings_after"]["allow_negative_stock"] == 0)
print(json.dumps(result, indent=2, default=str))
