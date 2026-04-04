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

EMDASH_3MD = "3MD Logistics \u2013 Camangyanan - BKI"
CORRECT_3MD = "3MD Logistics - Camangyanan - BKI"
EMDASH_RCS = "Royal Cold Storage \u2013 Taytay (RCS) - BKI"
CORRECT_RCS = "Royal Cold Storage - Taytay (RCS) - BKI"

print("Fixing BEI Route source_warehouse em-dash issues...")

routes = frappe.get_all("BEI Route", fields=["name", "source_warehouse"], limit_page_length=50)
fixed = 0
for r in routes:
    sw = r.source_warehouse or ""
    new_sw = None
    if EMDASH_3MD in sw or sw == EMDASH_3MD:
        new_sw = sw.replace(EMDASH_3MD, CORRECT_3MD)
    elif EMDASH_RCS in sw or sw == EMDASH_RCS:
        new_sw = sw.replace(EMDASH_RCS, CORRECT_RCS)

    if new_sw and new_sw != sw:
        frappe.db.set_value("BEI Route", r.name, "source_warehouse", new_sw)
        fixed += 1
        print("  Fixed %s: %s -> %s" % (r.name, repr(sw), repr(new_sw)))

frappe.db.commit()
print("Fixed %d routes" % fixed)

# Verify
routes2 = frappe.get_all("BEI Route", fields=["name", "source_warehouse", "cargo_type"], limit_page_length=50)
print("\nAll routes after fix:")
for r in routes2:
    print("  %s: cargo=%s source=%s" % (r.name, r.cargo_type, r.source_warehouse))

print("ROUTE-FIX-DONE")
frappe.destroy()
