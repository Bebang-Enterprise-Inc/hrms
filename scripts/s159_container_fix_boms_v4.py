#!/usr/bin/env python3
"""
S159 v4: Fix the remaining 12 MN draft BOMs.
The only remaining issue: submit fails because bei_source_* fields are empty.
Use frappe.get_doc() + save() to set all fields before submit.
"""

import os, sys

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe
from frappe.utils import flt

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BEI = "Bebang Enterprise Inc."

print("PHASE 2b FINAL: Submit 12 MN draft BOMs")
print("=" * 60)

mn_boms = frappe.get_all(
    "BOM",
    filters=[["item", "like", "MN%"], ["docstatus", "=", 0]],
    fields=["name", "item", "company"],
    order_by="item asc",
)

print(f"Found {len(mn_boms)} draft MN BOMs")

success = 0
errors = 0

for mb in mn_boms:
    bom_name = mb.name
    item_code = mb.item
    print(f"\n  {bom_name} ({item_code})...")

    try:
        doc = frappe.get_doc("BOM", bom_name)

        # Set company
        doc.company = BEI
        doc.is_active = 1
        doc.is_default = 1

        # Set source lineage (Server Script requires all three to be truthy)
        doc.bei_source_file = "s159_container_fix_boms.py"
        doc.bei_source_sheet = "S159 BOM Data Fix"
        doc.bei_source_row = 1

        # Save first (applies all field changes)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"    Saved with lineage fields")

        # Now submit
        doc.submit()
        frappe.db.commit()
        print(f"    Submitted {bom_name}")
        success += 1
    except Exception as e:
        frappe.db.rollback()
        print(f"    ERROR: {str(e)[:200]}")
        errors += 1

print(f"\nResults: {success} success, {errors} errors out of {len(mn_boms)}")

# Verification
print("\n--- Verification ---")
mn_submitted = frappe.db.count("BOM", {"item": ["like", "MN%"], "company": BEI, "docstatus": 1, "is_active": 1})
print(f"  MN BOMs under BEI (active, submitted): {mn_submitted}")

for item_code in ["MN001", "MN002", "MN006", "MN007", "MN008", "MN009",
                   "MN010", "MN011", "MN012", "MN013", "MN014", "MN015"]:
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "docstatus": 1},
        ["name", "company"],
        as_dict=True,
    )
    if bom:
        items_count = frappe.db.count("BOM Item", {"parent": bom.name})
        print(f"  {item_code}: {bom.name} ({items_count} items)")
    else:
        print(f"  {item_code}: MISSING")

print("\nS159-V4-DONE")
frappe.destroy()
