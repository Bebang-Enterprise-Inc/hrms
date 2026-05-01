"""S225 comprehensive teardown — cancel ALL S229-labeled SEs, restore Stock Settings.

Finds every SE with remarks LIKE 'S229 retest seed%%' from the last 4 hours and cancels.
With allow_negative_stock=1 already on, cancels won't be blocked. After cancellation,
toggles Stock Settings back to 0 and verifies.
"""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {
    "stock_settings_before_teardown": {
        "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
        "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
    },
    "cancelled_count": 0,
    "already_cancelled": 0,
    "errors": [],
}

# Ensure allow_negative_stock stays ON during cancel
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 1)
frappe.db.commit()

ses = frappe.db.sql("""
    SELECT name, docstatus
    FROM `tabStock Entry`
    WHERE remarks LIKE 'S229 retest seed%%'
      AND creation > NOW() - INTERVAL 4 HOUR
    ORDER BY name DESC
""", as_dict=True)

for se in ses:
    name = se["name"]
    if se["docstatus"] == 2:
        result["already_cancelled"] += 1
        continue
    if se["docstatus"] == 1:
        try:
            doc = frappe.get_doc("Stock Entry", name)
            doc.cancel()
            frappe.db.commit()
            result["cancelled_count"] += 1
        except Exception as e:
            frappe.db.rollback()
            result["errors"].append({"name": name, "error": str(e)[:200]})

# Now toggle Stock Settings OFF
frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 0)
frappe.db.set_single_value("Stock Settings", "allow_negative_stock_for_batch", 0)
frappe.db.commit()

result["stock_settings_after_teardown"] = {
    "allow_negative_stock": frappe.db.get_single_value("Stock Settings", "allow_negative_stock"),
    "allow_negative_stock_for_batch": frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"),
}

result["total_seeded_ses_found"] = len(ses)
result["all_clean"] = (result["errors"] == [] and
                        result["stock_settings_after_teardown"]["allow_negative_stock"] == 0 and
                        result["stock_settings_after_teardown"]["allow_negative_stock_for_batch"] == 0)

print(json.dumps(result, indent=2, default=str))
