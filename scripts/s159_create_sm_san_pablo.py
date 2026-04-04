import os, sys

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

WH_NAME = "SM San Pablo"
COMPANY = "Bebang Enterprise Inc."
DOCNAME = "SM San Pablo - Bebang Enterprise Inc."

if frappe.db.exists("Warehouse", DOCNAME):
    print("SKIP: Warehouse already exists: %s" % DOCNAME)
else:
    # Find parent warehouse for store locations
    parent = frappe.db.get_value("Warehouse", {"warehouse_name": "Store Locations"}, "name")
    if not parent:
        parent = frappe.db.get_value("Warehouse", {"is_group": 1, "company": COMPANY}, "name")

    wh = frappe.new_doc("Warehouse")
    wh.warehouse_name = WH_NAME
    wh.company = COMPANY
    wh.parent_warehouse = parent
    wh.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created: %s (parent: %s)" % (wh.name, parent))

print("SM-SAN-PABLO-DONE")
frappe.destroy()
