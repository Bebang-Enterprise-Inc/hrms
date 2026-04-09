import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
rows = frappe.db.sql("""SELECT name, manual_vendor, manual_amount, status, pcf_batch FROM `tabBEI Expense Request` WHERE pcf_fund='PCF-HR and Admin' AND creation > DATE_SUB(NOW(), INTERVAL 2 HOUR) ORDER BY creation DESC""", as_dict=True)
print(json.dumps([dict(r) for r in rows], indent=2, default=str))
frappe.destroy()
