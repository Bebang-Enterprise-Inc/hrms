#!/usr/bin/env python3
"""
S159 fix: Create placeholder items for Brown Sugar Tapioca Balls and Ginataan Sauce,
then update the Iskrambol and Ginataang BOMs to use them instead of RM216/RM217.

RM216 = GREEN SPOON (existing item, should NOT have been used)
RM217 = ROASTED SESAME (existing item, should NOT have been used)
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

# ---------------------------------------------------------------
# Step 1: Find next available FG codes
# ---------------------------------------------------------------
print("Step 1: Finding next available FG codes...")
fg_items = frappe.get_all("Item", filters=[["name", "like", "FG%"]], pluck="name", order_by="name asc")
print(f"  Existing FG items: {sorted(fg_items)}")

# FG codes go FG001..FG022, plus FG001-A, FG001-B, FG002-A
# Next clean codes: FG023, FG024
TAPIOCA_CODE = "FG023"
GINATAAN_CODE = "FG024"

# Verify they don't exist
for code in [TAPIOCA_CODE, GINATAAN_CODE]:
    if frappe.db.exists("Item", code):
        print(f"  WARNING: {code} already exists!")
    else:
        print(f"  {code} is available")


# ---------------------------------------------------------------
# Step 2: Create placeholder items
# ---------------------------------------------------------------
print("\nStep 2: Creating placeholder items...")

for code, name, uom in [
    (TAPIOCA_CODE, "BROWN SUGAR TAPIOCA BALLS (PLACEHOLDER - pending Arnold)", "KG"),
    (GINATAAN_CODE, "GINATAAN SAUCE (PLACEHOLDER - pending Arnold)", "KG"),
]:
    if frappe.db.exists("Item", code):
        print(f"  SKIP {code}: already exists")
        continue
    item = frappe.new_doc("Item")
    item.item_code = code
    item.item_name = name
    item.item_group = "Finished Goods"
    item.stock_uom = uom
    item.is_stock_item = 1
    item.include_item_in_manufacturing = 1
    item.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  OK Created {code} ({name})")


# ---------------------------------------------------------------
# Step 3: Deactivate current Iskrambol BOM, recreate with FG023
# ---------------------------------------------------------------
print("\nStep 3: Fix Iskrambol BOM (replace RM216 with FG023)...")

old_iskrambol = frappe.db.get_value(
    "BOM",
    {"item": "MN-ISKRAMBOL", "is_active": 1, "is_default": 1, "docstatus": 1},
    "name",
)

if old_iskrambol:
    print(f"  Deactivating {old_iskrambol}...")
    frappe.db.set_value("BOM", old_iskrambol, {"is_active": 0, "is_default": 0})
    frappe.db.commit()

    # Build new ingredient list (same as before but FG023 instead of RM216)
    iskrambol_items = [
        {"item_code": "FG020", "qty": 0.306},     # Frozen Milk
        {"item_code": "FG001", "qty": 0.050},     # Leche Flan
        {"item_code": "FG005", "qty": 0.030},     # Vanilla Jelly
        {"item_code": "FG018", "qty": 0.025},     # Melon Sauce
        {"item_code": "RM007", "qty": 0.023},     # Nata
        {"item_code": "FG019", "qty": 0.015},     # Chocolate Syrup
        {"item_code": TAPIOCA_CODE, "qty": 0.012},  # Brown Sugar Tapioca Balls (was RM216)
        {"item_code": "M006",  "qty": 0.012},     # Mini Mallows
        {"item_code": "RM020", "qty": 0.007},     # Brownies
        {"item_code": "FG003", "qty": 0.002},     # Rice Crispies
        {"item_code": "PM001", "qty": 1.0},       # Cup
        {"item_code": "PM002", "qty": 1.0},       # Lid
        {"item_code": "PM003", "qty": 1.0},       # Spoon
    ]

    bom = frappe.new_doc("BOM")
    bom.item = "MN-ISKRAMBOL"
    bom.quantity = 1
    bom.uom = "Cup"
    bom.is_active = 1
    bom.is_default = 1
    bom.company = BEI
    bom.with_operations = 0
    bom.bei_source_file = "s159_container_fix_placeholders.py"
    bom.bei_source_sheet = "S159 BOM placeholder fix"
    bom.bei_source_row = 1
    bom.remarks = "S159: Iskrambol BOM v2 - FG023 placeholder for Brown Sugar Tapioca Balls (was RM216 GREEN SPOON)"

    for mat in iskrambol_items:
        mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
        if not mat_item:
            print(f"  WARNING: {mat['item_code']} not found, skipping")
            continue
        bom.append("items", {
            "item_code": mat["item_code"],
            "item_name": mat_item.item_name,
            "qty": flt(mat["qty"]),
            "uom": mat_item.stock_uom,
            "stock_uom": mat_item.stock_uom,
            "rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
        })

    bom.insert(ignore_permissions=True)
    bom.submit()
    frappe.db.commit()
    print(f"  OK Created + submitted {bom.name} ({len(bom.items)} items)")
else:
    print("  No active Iskrambol BOM found to fix")


# ---------------------------------------------------------------
# Step 4: Deactivate current Ginataang BOM, recreate with FG024
# ---------------------------------------------------------------
print("\nStep 4: Fix Ginataang BOM (replace RM217 with FG024)...")

old_ginataang = frappe.db.get_value(
    "BOM",
    {"item": "MN-GINATAANG", "is_active": 1, "is_default": 1, "docstatus": 1},
    "name",
)

if old_ginataang:
    print(f"  Deactivating {old_ginataang}...")
    frappe.db.set_value("BOM", old_ginataang, {"is_active": 0, "is_default": 0})
    frappe.db.commit()

    ginataang_items = [
        {"item_code": GINATAAN_CODE, "qty": 0.100},  # Ginataan Sauce (was RM217)
        {"item_code": "RM213",   "qty": 0.030},     # Bilo Bilo
        {"item_code": "FG004",   "qty": 0.030},     # Pandan Jelly
        {"item_code": "RM007",   "qty": 0.023},     # Nata
        {"item_code": "FG009",   "qty": 0.020},     # Sago
        {"item_code": "RM006-C", "qty": 0.017},     # Corn Kernels
        {"item_code": "FG013",   "qty": 0.013},     # Langka
        {"item_code": "FG016",   "qty": 0.010},     # Ube Sauce
        {"item_code": "PM001",   "qty": 1.0},       # Cup
        {"item_code": "PM002",   "qty": 1.0},       # Lid
        {"item_code": "PM003",   "qty": 1.0},       # Spoon
    ]

    bom = frappe.new_doc("BOM")
    bom.item = "MN-GINATAANG"
    bom.quantity = 1
    bom.uom = "Cup"
    bom.is_active = 1
    bom.is_default = 1
    bom.company = BEI
    bom.with_operations = 0
    bom.bei_source_file = "s159_container_fix_placeholders.py"
    bom.bei_source_sheet = "S159 BOM placeholder fix"
    bom.bei_source_row = 1
    bom.remarks = "S159: Ginataang BOM v2 - FG024 placeholder for Ginataan Sauce (was RM217 ROASTED SESAME)"

    for mat in ginataang_items:
        mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
        if not mat_item:
            print(f"  WARNING: {mat['item_code']} not found, skipping")
            continue
        bom.append("items", {
            "item_code": mat["item_code"],
            "item_name": mat_item.item_name,
            "qty": flt(mat["qty"]),
            "uom": mat_item.stock_uom,
            "stock_uom": mat_item.stock_uom,
            "rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
        })

    bom.insert(ignore_permissions=True)
    bom.submit()
    frappe.db.commit()
    print(f"  OK Created + submitted {bom.name} ({len(bom.items)} items)")
else:
    print("  No active Ginataang BOM found to fix")


# ---------------------------------------------------------------
# Verification
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

for item_code in ["MN-ISKRAMBOL", "MN-GINATAANG"]:
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        ["name", "company"],
        as_dict=True,
    )
    if bom:
        items = frappe.get_all("BOM Item", filters={"parent": bom.name},
                               fields=["item_code", "item_name", "qty"], order_by="idx asc")
        print(f"\n  {item_code}: {bom.name}")
        for i in items:
            marker = " <-- PLACEHOLDER" if i.item_code in (TAPIOCA_CODE, GINATAAN_CODE) else ""
            print(f"    {i.item_code}: {i.item_name} (qty={i.qty}){marker}")
    else:
        print(f"\n  {item_code}: NO active BOM")

# Confirm RM216/RM217 are NOT in any active BOM
print("\n  Checking RM216/RM217 not in active BOMs...")
for code in ["RM216", "RM217"]:
    refs = frappe.db.sql("""
        SELECT bi.parent, b.item, b.is_active
        FROM `tabBOM Item` bi
        JOIN `tabBOM` b ON b.name = bi.parent
        WHERE bi.item_code = %s AND b.is_active = 1
    """, code, as_dict=True)
    if refs:
        print(f"  WARNING: {code} still referenced in active BOMs: {[r.parent for r in refs]}")
    else:
        print(f"  OK: {code} not in any active BOM")

print("\nS159-PLACEHOLDER-FIX-DONE")
frappe.destroy()
