#!/usr/bin/env python3
"""
S159 Container Script v3: Fix remaining issues.

Already done:
  - Phase 2a: 18 FG BOMs under BKI (all success)
  - MN016 Pop Lamig BOM created
  - RM216, RM217 Items exist
  - MN-ISKRAMBOL, MN-GINATAANG, MN-TIKIM-* Items created

Remaining:
  - Phase 2b: MN BOMs reference deactivated FG BOMs -> update bom_no refs, submit
  - Phase 3: Create BOMs for Iskrambol, Ginataang, Tikims (fix UOM + source lineage)
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
BKI = "Bebang Kitchen Inc."


# ---------------------------------------------------------------
# Discover UOMs
# ---------------------------------------------------------------
print("Available UOMs:")
uoms = frappe.get_all("UOM", pluck="name", limit=50)
print(f"  {uoms}")

# Find the gram UOM
gram_uom = None
for u in uoms:
    if u.lower() in ("gram", "gm", "g", "gms"):
        gram_uom = u
        break
if not gram_uom:
    # Check if we can create it or find it
    gram_uom = frappe.db.get_value("UOM", {"name": ["like", "%gram%"]}, "name")
    if not gram_uom:
        gram_uom = frappe.db.get_value("UOM", {"name": ["like", "%Gram%"]}, "name")

print(f"  Gram UOM resolved to: '{gram_uom}'")

# Also check what UOM RM216 has
rm216_uom = frappe.db.get_value("Item", "RM216", "stock_uom")
print(f"  RM216 stock_uom: '{rm216_uom}'")
rm217_uom = frappe.db.get_value("Item", "RM217", "stock_uom")
print(f"  RM217 stock_uom: '{rm217_uom}'")


# ---------------------------------------------------------------
# Phase 2b: Fix MN BOM child references + submit
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("PHASE 2b: Fix MN BOM child bom_no references + submit")
print("=" * 60)

# Build mapping: item_code -> active BOM name
print("\nBuilding active BOM name mapping...")
active_bom_map = {}
all_active_boms = frappe.get_all(
    "BOM",
    filters={"is_active": 1, "is_default": 1, "docstatus": 1},
    fields=["name", "item"],
)
for b in all_active_boms:
    active_bom_map[b.item] = b.name
print(f"  {len(active_bom_map)} active BOMs mapped")

# Get MN BOMs
mn_boms = frappe.get_all(
    "BOM",
    filters=[["item", "like", "MN%"], ["docstatus", "=", 0]],
    fields=["name", "item", "company", "docstatus"],
    order_by="item asc",
)

print(f"Found {len(mn_boms)} draft MN BOMs to fix")

phase2b_success = 0
phase2b_errors = 0

for mb in mn_boms:
    bom_name = mb.name
    item_code = mb.item

    print(f"\n  {bom_name} ({item_code})...")

    # Update bom_no references in child items
    child_items = frappe.get_all(
        "BOM Item",
        filters={"parent": bom_name},
        fields=["name", "item_code", "bom_no"],
    )

    updated_refs = 0
    for ci in child_items:
        if ci.bom_no:
            # Check if referenced BOM is active
            ref_active = frappe.db.get_value("BOM", ci.bom_no, "is_active")
            if not ref_active:
                # Find the new active BOM for this item
                new_bom = active_bom_map.get(ci.item_code)
                if new_bom:
                    frappe.db.set_value("BOM Item", ci.name, "bom_no", new_bom)
                    updated_refs += 1
                    print(f"    Updated ref {ci.item_code}: {ci.bom_no} -> {new_bom}")
                else:
                    # No active BOM for this sub-item -- clear the reference
                    frappe.db.set_value("BOM Item", ci.name, "bom_no", "")
                    updated_refs += 1
                    print(f"    Cleared ref {ci.item_code}: {ci.bom_no} (no active BOM)")

    if updated_refs:
        frappe.db.commit()
        print(f"    Updated {updated_refs} child BOM references")

    # Ensure company is BEI
    if mb.company != BEI:
        frappe.db.set_value("BOM", bom_name, {
            "company": BEI,
            "is_active": 1,
            "is_default": 1,
            "bei_source_file": "s159_container_fix_boms.py",
            "bei_source_sheet": "S159 BOM Data Fix",
        })
        frappe.db.commit()

    # Submit
    try:
        doc = frappe.get_doc("BOM", bom_name)
        doc.submit()
        frappe.db.commit()
        print(f"    Submitted {bom_name}")
        phase2b_success += 1
    except Exception as e:
        frappe.db.rollback()
        print(f"    ERROR submitting: {str(e)[:200]}")
        phase2b_errors += 1

print(f"\nPhase 2b: {phase2b_success} success, {phase2b_errors} errors out of {len(mn_boms)}")


# ---------------------------------------------------------------
# Phase 3: Create missing BOMs (fix UOM + source lineage)
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("PHASE 3: Create missing BOMs")
print("=" * 60)


def create_bom(item_code, company, items_data, quantity=1, uom=None, remarks=None):
    existing = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    if existing:
        items_count = frappe.db.count("BOM Item", {"parent": existing})
        print(f"  SKIP {item_code}: active BOM {existing} ({items_count} items)")
        return existing

    item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
    if not item:
        print(f"  ERROR: Item {item_code} not found")
        return None

    bom = frappe.new_doc("BOM")
    bom.item = item_code
    bom.quantity = flt(quantity) or 1
    bom.uom = uom or item.stock_uom
    bom.is_active = 1
    bom.is_default = 1
    bom.company = company
    bom.with_operations = 0
    bom.bei_source_file = "s159_container_fix_boms.py"
    bom.bei_source_sheet = "S159 BOM Data Fix"
    bom.bei_source_row = 1  # Int field, must be truthy

    if remarks:
        bom.remarks = remarks

    for mat in items_data:
        mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
        if not mat_item:
            print(f"  WARNING: material {mat['item_code']} not found, skipping")
            continue

        # Resolve UOM: use item's stock_uom as default, override only if explicit and valid
        mat_uom = mat.get("uom") or mat_item.stock_uom
        # Validate UOM exists
        if not frappe.db.exists("UOM", mat_uom):
            mat_uom = mat_item.stock_uom

        bom.append("items", {
            "item_code": mat["item_code"],
            "item_name": mat_item.item_name,
            "qty": flt(mat["qty"]),
            "uom": mat_uom,
            "stock_uom": mat_item.stock_uom,
            "rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
        })

    try:
        bom.insert(ignore_permissions=True)
        bom.submit()
        frappe.db.commit()
        print(f"  OK {item_code}: {bom.name} under {company} ({len(bom.items)} items)")
        return bom.name
    except Exception as e:
        frappe.db.rollback()
        print(f"  ERROR {item_code}: {str(e)[:200]}")
        return None


print("\n--- Iskrambol BOM ---")
create_bom("MN-ISKRAMBOL", BEI, [
    {"item_code": "FG020", "qty": 0.306},
    {"item_code": "FG001", "qty": 0.050},
    {"item_code": "FG005", "qty": 0.030},
    {"item_code": "FG018", "qty": 0.025},
    {"item_code": "RM007", "qty": 0.023},
    {"item_code": "FG019", "qty": 0.015},
    {"item_code": "RM216", "qty": 12.0},     # Uses item's stock_uom (Gram)
    {"item_code": "M006",  "qty": 0.012},
    {"item_code": "RM020", "qty": 0.007},
    {"item_code": "FG003", "qty": 0.002},
    {"item_code": "PM001", "qty": 1.0},
    {"item_code": "PM002", "qty": 1.0},
    {"item_code": "PM003", "qty": 1.0},
], quantity=1, uom="Cup", remarks="S159: Iskrambol BOM from Arnold's Store BOM 2026")

print("\n--- Ginataang Halo-Halo BOM ---")
create_bom("MN-GINATAANG", BEI, [
    {"item_code": "RM217",   "qty": 100.0},  # Uses item's stock_uom (Gram)
    {"item_code": "RM213",   "qty": 0.030},
    {"item_code": "FG004",   "qty": 0.030},
    {"item_code": "RM007",   "qty": 0.023},
    {"item_code": "FG009",   "qty": 0.020},
    {"item_code": "RM006-C", "qty": 0.017},
    {"item_code": "FG013",   "qty": 0.013},
    {"item_code": "FG016",   "qty": 0.010},
    {"item_code": "PM001",   "qty": 1.0},
    {"item_code": "PM002",   "qty": 1.0},
    {"item_code": "PM003",   "qty": 1.0},
], quantity=1, uom="Cup", remarks="S159: Ginataang Halo-Halo BOM from Arnold's Store BOM 2026")

print("\n--- Tikim Presidential ---")
create_bom("MN-TIKIM-PRESIDENTIAL", BEI, [
    {"item_code": "FG001-A", "qty": 0.020833}, {"item_code": "FG004", "qty": 0.012500},
    {"item_code": "FG009", "qty": 0.006667}, {"item_code": "RM006-C", "qty": 0.002717},
    {"item_code": "RM007", "qty": 0.004267}, {"item_code": "FG020", "qty": 0.048980},
    {"item_code": "RM018", "qty": 0.007071}, {"item_code": "FG013", "qty": 0.007071},
    {"item_code": "RM017", "qty": 0.007071}, {"item_code": "FG002", "qty": 0.007071},
    {"item_code": "FG016", "qty": 0.010101}, {"item_code": "FG021", "qty": 0.042105},
    {"item_code": "FG022", "qty": 0.002105},
    {"item_code": "PM020", "qty": 1.0}, {"item_code": "PM021", "qty": 1.0},
    {"item_code": "PM003", "qty": 1.0},
], quantity=1, uom="Cup", remarks="S159: Tikim Presidential")

print("\n--- Tikim Mango Graham ---")
create_bom("MN-TIKIM-MANGO-GRAHAM", BEI, [
    {"item_code": "FG001-A", "qty": 0.020833}, {"item_code": "FG020", "qty": 0.048980},
    {"item_code": "RM013", "qty": 0.010101}, {"item_code": "RM010-A", "qty": 0.010526},
    {"item_code": "RM001", "qty": 0.005000}, {"item_code": "FG021", "qty": 0.042105},
    {"item_code": "FG022", "qty": 0.002105},
    {"item_code": "PM020", "qty": 1.0}, {"item_code": "PM021", "qty": 1.0},
    {"item_code": "PM003", "qty": 1.0},
], quantity=1, uom="Cup", remarks="S159: Tikim Mango Graham")

print("\n--- Tikim Choco Brownie ---")
create_bom("MN-TIKIM-CHOCO-BROWNIE", BEI, [
    {"item_code": "FG001-A", "qty": 0.020833}, {"item_code": "FG020", "qty": 0.048980},
    {"item_code": "FG019", "qty": 0.010101}, {"item_code": "RM020", "qty": 0.028000},
    {"item_code": "M003", "qty": 0.015000}, {"item_code": "M006", "qty": 0.004412},
    {"item_code": "FG021", "qty": 0.042105}, {"item_code": "FG022", "qty": 0.002105},
    {"item_code": "PM020", "qty": 1.0}, {"item_code": "PM021", "qty": 1.0},
    {"item_code": "PM003", "qty": 1.0},
], quantity=1, uom="Cup", remarks="S159: Tikim Choco Brownie")


# ---------------------------------------------------------------
# Verification
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)

fg_bki = frappe.db.count("BOM", {"item": ["like", "FG%"], "company": BKI, "docstatus": 1, "is_active": 1})
mn_bei = frappe.db.count("BOM", {"item": ["like", "MN%"], "company": BEI, "docstatus": 1, "is_active": 1})
fg_bei_active = frappe.db.count("BOM", {"item": ["like", "FG%"], "company": BEI, "is_active": 1})

print(f"  FG BOMs under BKI (active, submitted): {fg_bki} (target: >= 17)")
print(f"  MN BOMs under BEI (active, submitted): {mn_bei} (target: >= 12)")
print(f"  FG BOMs under BEI (active):            {fg_bei_active} (target: 0)")

for item_code in ["FG001", "FG020", "MN001", "MN006", "MN016",
                   "MN-ISKRAMBOL", "MN-GINATAANG",
                   "MN-TIKIM-PRESIDENTIAL", "MN-TIKIM-MANGO-GRAHAM", "MN-TIKIM-CHOCO-BROWNIE"]:
    bom = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        ["name", "company"],
        as_dict=True,
    )
    if bom:
        items_count = frappe.db.count("BOM Item", {"parent": bom.name})
        print(f"  {item_code}: {bom.name} under {bom.company} ({items_count} items)")
    else:
        print(f"  {item_code}: NO active default BOM")

print("\nS159-V3-DONE")
frappe.destroy()
