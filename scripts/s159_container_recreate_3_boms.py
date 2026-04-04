#!/usr/bin/env python3
"""
S159: Recreate 3 deleted product BOMs from validated _CLEANROOM P05 data.

Source: BOM_RECIPES_PACKET.csv (P05 migration, 2026-03-03, 0 errors)
Fact-checked: tmp/bom_investigation/FACT_CHECK_3_MISSING_BOMS.md

Products:
  MN003 - HALOKAY UBE (19 ingredients) — Item exists
  MN004 - BANANA CINNAMON (12 ingredients) — Item MISSING, create first
  MN005 - BUKO FRUIT SALAD (13 ingredients) — Item exists
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


def create_bom(item_code, ingredients, remarks):
    """Create and submit a BOM under BEI. Skip if active BOM already exists."""
    existing = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    if existing:
        count = frappe.db.count("BOM Item", {"parent": existing})
        print(f"  SKIP {item_code}: active BOM {existing} ({count} items)")
        return existing

    item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
    if not item:
        print(f"  ERROR: Item {item_code} not found")
        return None

    bom = frappe.new_doc("BOM")
    bom.item = item_code
    bom.quantity = 1
    bom.uom = "Cup"
    bom.is_active = 1
    bom.is_default = 1
    bom.company = BEI
    bom.with_operations = 0
    bom.bei_source_file = "s159_container_recreate_3_boms.py"
    bom.bei_source_sheet = "BOM_RECIPES_PACKET.csv (P05)"
    bom.bei_source_row = 1
    bom.remarks = remarks

    for mat in ingredients:
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

    try:
        bom.insert(ignore_permissions=True)
        bom.submit()
        frappe.db.commit()
        print(f"  OK {item_code}: {bom.name} ({len(bom.items)} items)")
        return bom.name
    except Exception as e:
        frappe.db.rollback()
        print(f"  ERROR {item_code}: {str(e)[:200]}")
        return None


# ---------------------------------------------------------------
# Step 1: Create MN004 Item (doesn't exist)
# ---------------------------------------------------------------
print("Step 1: Create MN004 Item...")
if frappe.db.exists("Item", "MN004"):
    print("  SKIP: MN004 already exists")
else:
    # Use same item_group as other MN items
    mn_group = frappe.db.get_value("Item", "MN003", "item_group") or "Finished Goods"
    item = frappe.new_doc("Item")
    item.item_code = "MN004"
    item.item_name = "BANANA CINNAMON"
    item.item_group = mn_group
    item.stock_uom = "Cup"
    item.is_stock_item = 1
    item.include_item_in_manufacturing = 1
    item.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  OK Created MN004 (BANANA CINNAMON, group={mn_group})")


# ---------------------------------------------------------------
# Step 2: Create HALUKAY UBE BOM (MN003, 19 ingredients)
# Source: BOM_RECIPES_PACKET.csv rows for HALUKAY UBE
# ---------------------------------------------------------------
print("\nStep 2: HALUKAY UBE (MN003)...")
create_bom("MN003", [
    {"item_code": "FG001",   "qty": 1.0},
    {"item_code": "FG001-A", "qty": 1.0},
    {"item_code": "FG001-B", "qty": 1.0},
    {"item_code": "FG002",   "qty": 0.013},
    {"item_code": "FG003",   "qty": 0.002},
    {"item_code": "FG004",   "qty": 0.035},
    {"item_code": "FG009",   "qty": 0.019},
    {"item_code": "FG013",   "qty": 0.013},
    {"item_code": "FG016",   "qty": 0.013},
    {"item_code": "FG020",   "qty": 0.124},
    {"item_code": "PM001",   "qty": 1.0},
    {"item_code": "PM002",   "qty": 1.0},
    {"item_code": "PM003",   "qty": 1.0},
    {"item_code": "PM007",   "qty": 1.0},
    {"item_code": "RM006-B", "qty": 0.017},
    {"item_code": "RM006-C", "qty": 0.017},
    {"item_code": "RM007",   "qty": 0.012},
    {"item_code": "RM017",   "qty": 0.013},
    {"item_code": "RM018",   "qty": 0.014},
], "S159: Recreated from P05 BOM_RECIPES_PACKET.csv (HALUKAY UBE, 19 ingredients)")


# ---------------------------------------------------------------
# Step 3: Create BANANA CINNAMON BOM (MN004, 12 ingredients)
# ---------------------------------------------------------------
print("\nStep 3: BANANA CINNAMON (MN004)...")
create_bom("MN004", [
    {"item_code": "FG001",   "qty": 1.0},
    {"item_code": "FG001-A", "qty": 1.0},
    {"item_code": "FG001-B", "qty": 1.0},
    {"item_code": "FG002",   "qty": 0.041},
    {"item_code": "FG003",   "qty": 0.002},
    {"item_code": "FG005",   "qty": 0.04},
    {"item_code": "FG020",   "qty": 0.124},
    {"item_code": "PM001",   "qty": 1.0},
    {"item_code": "PM002",   "qty": 1.0},
    {"item_code": "PM003",   "qty": 1.0},
    {"item_code": "PM007",   "qty": 1.0},
    {"item_code": "RM013",   "qty": 0.033},
], "S159: Recreated from P05 BOM_RECIPES_PACKET.csv (BANANA CINNAMON, 12 ingredients)")


# ---------------------------------------------------------------
# Step 4: Create BUKO FRUIT SALAD BOM (MN005, 13 ingredients)
# ---------------------------------------------------------------
print("\nStep 4: BUKO FRUIT SALAD (MN005)...")
create_bom("MN005", [
    {"item_code": "FG001",   "qty": 1.0},
    {"item_code": "FG001-A", "qty": 1.0},
    {"item_code": "FG001-B", "qty": 1.0},
    {"item_code": "FG003",   "qty": 0.002},
    {"item_code": "FG006",   "qty": 0.046},
    {"item_code": "FG007",   "qty": 0.034},
    {"item_code": "FG020",   "qty": 0.124},
    {"item_code": "PM001",   "qty": 1.0},
    {"item_code": "PM002",   "qty": 1.0},
    {"item_code": "PM003",   "qty": 1.0},
    {"item_code": "PM007",   "qty": 1.0},
    {"item_code": "RM011",   "qty": 12.0},
    {"item_code": "RM012",   "qty": 0.065},
], "S159: Recreated from P05 BOM_RECIPES_PACKET.csv (BUKO FRUIT SALAD, 13 ingredients)")


# ---------------------------------------------------------------
# Verification
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

total_mn = frappe.db.count("BOM", {"item": ["like", "MN%"], "company": BEI, "docstatus": 1, "is_active": 1})
print(f"  Total MN BOMs under BEI (active, submitted): {total_mn} (target: >= 21)")

for item_code in ["MN003", "MN004", "MN005"]:
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        ["name", "company"],
        as_dict=True,
    )
    if bom:
        items = frappe.get_all("BOM Item", filters={"parent": bom.name},
                               fields=["item_code", "item_name", "qty"], order_by="idx asc")
        print(f"\n  {item_code}: {bom.name} under {bom.company} ({len(items)} items)")
        for i in items:
            print(f"    {i.item_code:<10} {i.item_name:<35} qty={i.qty}")
    else:
        print(f"\n  {item_code}: MISSING!")

print("\nS159-3BOMS-DONE")
frappe.destroy()
