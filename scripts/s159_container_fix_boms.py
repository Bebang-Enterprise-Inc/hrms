#!/usr/bin/env python3
"""
S159 Container Script: Fix BOM company assignments + create missing BOMs.

Runs INSIDE the Frappe Docker container via SSM. Uses direct ORM.

Phases:
  Phase 2a: Create new FG BOMs under BKI (old ones already deactivated via REST)
  Phase 2b: Update MN draft BOMs company to BEI, submit
  Phase 3:  Create Items RM216/RM217, create Iskrambol/Ginataang/Pop Lamig/Tikim BOMs
"""

import os
import sys
import json

# Step 0: Create log directories before importing frappe
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
# Helpers
# ---------------------------------------------------------------

def create_bom_under_company(item_code, company, items_data, quantity=1, uom=None, remarks=None):
    """Create and submit a BOM. Returns BOM name or None."""
    # Check for existing active default BOM
    existing = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    if existing:
        # Check company
        existing_company = frappe.db.get_value("BOM", existing, "company")
        if existing_company == company:
            print(f"  SKIP {item_code}: active BOM {existing} already under {company}")
            return existing
        else:
            print(f"  NOTE {item_code}: active BOM {existing} under {existing_company}, deactivating...")
            frappe.db.set_value("BOM", existing, {"is_active": 0, "is_default": 0})

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
    bom.bei_source_row = item_code

    if remarks:
        bom.remarks = remarks

    for mat in items_data:
        mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
        if not mat_item:
            print(f"  WARNING: material {mat['item_code']} not found, skipping")
            continue

        bom.append("items", {
            "item_code": mat["item_code"],
            "item_name": mat_item.item_name,
            "qty": flt(mat["qty"]),
            "uom": mat.get("uom") or mat_item.stock_uom,
            "stock_uom": mat_item.stock_uom,
            "rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
        })

    try:
        bom.insert(ignore_permissions=True)
        bom.submit()
        frappe.db.commit()
        print(f"  OK {item_code}: created + submitted {bom.name} under {company} ({len(bom.items)} items)")
        return bom.name
    except Exception as e:
        frappe.db.rollback()
        print(f"  ERROR {item_code}: {str(e)[:120]}")
        return None


def create_item_if_missing(item_code, item_name, item_group, stock_uom):
    """Create Item if it doesn't exist."""
    if frappe.db.exists("Item", item_code):
        print(f"  SKIP Item {item_code}: already exists")
        return True
    try:
        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = item_name
        item.item_group = item_group
        item.stock_uom = stock_uom
        item.is_stock_item = 1
        item.include_item_in_manufacturing = 1
        item.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"  OK Created Item {item_code} ({item_name})")
        return True
    except Exception as e:
        frappe.db.rollback()
        print(f"  ERROR creating Item {item_code}: {str(e)[:120]}")
        return False


# ---------------------------------------------------------------
# Phase 2a: Recreate FG ingredient BOMs under BKI
# ---------------------------------------------------------------

print("=" * 60)
print("PHASE 2a: Recreate FG ingredient BOMs under BKI")
print("=" * 60)

# These FG BOMs were deactivated in the previous run.
# Fetch all FG BOMs (active or not) and recreate under BKI.
fg_boms = frappe.get_all(
    "BOM",
    filters=[["item", "like", "FG%"]],
    fields=["name", "item", "company", "docstatus", "is_active", "quantity", "uom"],
    order_by="item asc",
)

print(f"Found {len(fg_boms)} FG BOMs total")

phase2a_success = 0
phase2a_errors = 0

for fb in fg_boms:
    item_code = fb.item
    bom_name = fb.name

    # Check if a BKI BOM already exists for this item
    bki_existing = frappe.db.get_value(
        "BOM",
        {"item": item_code, "company": BKI, "is_active": 1, "docstatus": 1},
        "name",
    )
    if bki_existing:
        print(f"  SKIP {item_code}: BKI BOM {bki_existing} already exists")
        phase2a_success += 1
        continue

    # Get the items from the existing BOM (even if deactivated)
    old_bom = frappe.get_doc("BOM", bom_name)
    items_data = []
    for item in old_bom.items:
        items_data.append({
            "item_code": item.item_code,
            "qty": item.qty,
            "uom": item.uom,
        })

    # Ensure old BOM is deactivated
    if old_bom.is_active:
        frappe.db.set_value("BOM", bom_name, {"is_active": 0, "is_default": 0})
        frappe.db.commit()

    result = create_bom_under_company(
        item_code, BKI, items_data,
        quantity=old_bom.quantity, uom=old_bom.uom,
        remarks=f"S159: company fix from {bom_name} (was BEI, now BKI)",
    )
    if result:
        phase2a_success += 1
    else:
        phase2a_errors += 1

print(f"\nPhase 2a: {phase2a_success} success, {phase2a_errors} errors out of {len(fg_boms)}")


# ---------------------------------------------------------------
# Phase 2b: Fix MN product BOMs -> BEI, submit
# ---------------------------------------------------------------

print("\n" + "=" * 60)
print("PHASE 2b: Fix MN product BOMs -> BEI + submit")
print("=" * 60)

mn_boms = frappe.get_all(
    "BOM",
    filters=[["item", "like", "MN%"]],
    fields=["name", "item", "company", "docstatus", "is_active"],
    order_by="item asc",
)

print(f"Found {len(mn_boms)} MN BOMs")

phase2b_success = 0
phase2b_errors = 0

for mb in mn_boms:
    bom_name = mb.name
    item_code = mb.item
    docstatus = mb.docstatus

    print(f"\n  Processing {bom_name} ({item_code}, company={mb.company}, docstatus={docstatus})...")

    if mb.company != BEI and docstatus == 0:
        # Draft -- can update directly
        try:
            frappe.db.set_value("BOM", bom_name, {
                "company": BEI,
                "is_active": 1,
                "is_default": 1,
                "bei_source_file": "s159_container_fix_boms.py",
                "bei_source_sheet": "S159 BOM Data Fix",
                "bei_source_row": item_code,
            })
            frappe.db.commit()
            print(f"    Updated company to BEI")
        except Exception as e:
            print(f"    ERROR updating company: {str(e)[:120]}")
            phase2b_errors += 1
            continue

    if docstatus == 0:
        # Submit
        try:
            doc = frappe.get_doc("BOM", bom_name)
            doc.submit()
            frappe.db.commit()
            print(f"    Submitted {bom_name}")
            phase2b_success += 1
        except Exception as e:
            frappe.db.rollback()
            print(f"    ERROR submitting: {str(e)[:120]}")
            phase2b_errors += 1
    elif docstatus == 1 and mb.company == BEI:
        print(f"    Already submitted under BEI")
        phase2b_success += 1
    else:
        print(f"    SKIP: docstatus={docstatus}, company={mb.company}")

print(f"\nPhase 2b: {phase2b_success} success, {phase2b_errors} errors out of {len(mn_boms)}")


# ---------------------------------------------------------------
# Phase 3: Create missing Items and BOMs
# ---------------------------------------------------------------

print("\n" + "=" * 60)
print("PHASE 3: Create missing Items and BOMs")
print("=" * 60)

# Step 1: Create new Items
print("\n--- Step 1: Create missing Items ---")
create_item_if_missing("RM216", "BROWN SUGAR TAPIOCA BALLS", "Raw Material", "Gram")
create_item_if_missing("RM217", "GINATAAN SAUCE", "Raw Material", "Gram")

# Check/create Iskrambol and Ginataang items
iskrambol_code = "MN-ISKRAMBOL"
ginataang_code = "MN-GINATAANG"

# Check if they exist under different codes
for code_pattern in ["%ISKRAMBOL%", "%iskrambol%"]:
    found = frappe.db.get_value("Item", {"item_name": ["like", code_pattern]}, "name")
    if found:
        iskrambol_code = found
        break

for code_pattern in ["%GINATAANG%", "%ginataang%"]:
    found = frappe.db.get_value("Item", {"item_name": ["like", code_pattern]}, "name")
    if found:
        ginataang_code = found
        break

create_item_if_missing(iskrambol_code, "ISKRAMBOL", "Menu Item", "Cup")
create_item_if_missing(ginataang_code, "GINATAANG HALO-HALO", "Menu Item", "Cup")

# Tikim items
for tikim in ["TIKIM-PRESIDENTIAL", "TIKIM-MANGO-GRAHAM", "TIKIM-CHOCO-BROWNIE"]:
    code = f"MN-{tikim}"
    name = tikim.replace("-", " ")
    create_item_if_missing(code, name, "Menu Item", "Cup")

# Step 2: Create Iskrambol BOM
print("\n--- Step 2: Iskrambol BOM ---")
create_bom_under_company(iskrambol_code, BEI, [
    {"item_code": "FG020", "qty": 0.306, "uom": "Kg"},
    {"item_code": "FG001", "qty": 0.050, "uom": "Kg"},
    {"item_code": "FG005", "qty": 0.030, "uom": "Kg"},
    {"item_code": "FG018", "qty": 0.025, "uom": "Kg"},
    {"item_code": "RM007", "qty": 0.023, "uom": "Kg"},
    {"item_code": "FG019", "qty": 0.015, "uom": "Kg"},
    {"item_code": "RM216", "qty": 12.0, "uom": "Gram"},
    {"item_code": "M006",  "qty": 0.012, "uom": "Kg"},
    {"item_code": "RM020", "qty": 0.007, "uom": "Kg"},
    {"item_code": "FG003", "qty": 0.002, "uom": "Kg"},
    {"item_code": "PM001", "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM002", "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM003", "qty": 1.0, "uom": "Nos"},
], quantity=1, uom="Cup", remarks="S159: Iskrambol BOM from Arnold's Store BOM 2026")

# Step 3: Ginataang Halo-Halo BOM
print("\n--- Step 3: Ginataang Halo-Halo BOM ---")
create_bom_under_company(ginataang_code, BEI, [
    {"item_code": "RM217",   "qty": 100.0, "uom": "Gram"},
    {"item_code": "RM213",   "qty": 0.030, "uom": "Kg"},
    {"item_code": "FG004",   "qty": 0.030, "uom": "Kg"},
    {"item_code": "RM007",   "qty": 0.023, "uom": "Kg"},
    {"item_code": "FG009",   "qty": 0.020, "uom": "Kg"},
    {"item_code": "RM006-C", "qty": 0.017, "uom": "Kg"},
    {"item_code": "FG013",   "qty": 0.013, "uom": "Kg"},
    {"item_code": "FG016",   "qty": 0.010, "uom": "Kg"},
    {"item_code": "PM001",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM002",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM003",   "qty": 1.0, "uom": "Nos"},
], quantity=1, uom="Cup", remarks="S159: Ginataang Halo-Halo BOM from Arnold's Store BOM 2026")

# Step 4: Pop Lamig BOM (MN016)
print("\n--- Step 4: Pop Lamig BOM ---")
create_bom_under_company("MN016", BEI, [
    {"item_code": "PM100", "qty": 0.006024, "uom": "Nos"},
    {"item_code": "FG009", "qty": 0.040,    "uom": "Kg"},
    {"item_code": "RM203", "qty": 0.026,    "uom": "Bottle"},
    {"item_code": "FG005", "qty": 0.060,    "uom": "Kg"},
    {"item_code": "PM001", "qty": 1.0,      "uom": "Nos"},
    {"item_code": "PM070", "qty": 0.000333, "uom": "Roll"},
    {"item_code": "PM102", "qty": 1.0,      "uom": "Nos"},
], quantity=1, uom="Cup", remarks="S159: Pop Lamig BOM from canonical mapping")

# Step 5: Tikim BOMs
print("\n--- Step 5: Tikim BOMs ---")

tikim_presidential = [
    {"item_code": "FG001-A", "qty": 0.020833, "uom": "Kg"},
    {"item_code": "FG004",   "qty": 0.012500, "uom": "Kg"},
    {"item_code": "FG009",   "qty": 0.006667, "uom": "Kg"},
    {"item_code": "RM006-C", "qty": 0.002717, "uom": "Kg"},
    {"item_code": "RM007",   "qty": 0.004267, "uom": "Kg"},
    {"item_code": "FG020",   "qty": 0.048980, "uom": "Kg"},
    {"item_code": "RM018",   "qty": 0.007071, "uom": "Kg"},
    {"item_code": "FG013",   "qty": 0.007071, "uom": "Kg"},
    {"item_code": "RM017",   "qty": 0.007071, "uom": "Kg"},
    {"item_code": "FG002",   "qty": 0.007071, "uom": "Kg"},
    {"item_code": "FG016",   "qty": 0.010101, "uom": "Kg"},
    {"item_code": "FG021",   "qty": 0.042105, "uom": "Kg"},
    {"item_code": "FG022",   "qty": 0.002105, "uom": "Kg"},
    {"item_code": "PM020",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM021",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM003",   "qty": 1.0, "uom": "Nos"},
]
create_bom_under_company("MN-TIKIM-PRESIDENTIAL", BEI, tikim_presidential,
                         quantity=1, uom="Cup", remarks="S159: Tikim Presidential from component recipes")

tikim_mango_graham = [
    {"item_code": "FG001-A", "qty": 0.020833, "uom": "Kg"},
    {"item_code": "FG020",   "qty": 0.048980, "uom": "Kg"},
    {"item_code": "RM013",   "qty": 0.010101, "uom": "Kg"},
    {"item_code": "RM010-A", "qty": 0.010526, "uom": "Kg"},
    {"item_code": "RM001",   "qty": 0.005000, "uom": "Kg"},
    {"item_code": "FG021",   "qty": 0.042105, "uom": "Kg"},
    {"item_code": "FG022",   "qty": 0.002105, "uom": "Kg"},
    {"item_code": "PM020",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM021",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM003",   "qty": 1.0, "uom": "Nos"},
]
create_bom_under_company("MN-TIKIM-MANGO-GRAHAM", BEI, tikim_mango_graham,
                         quantity=1, uom="Cup", remarks="S159: Tikim Mango Graham from component recipes")

tikim_choco_brownie = [
    {"item_code": "FG001-A", "qty": 0.020833, "uom": "Kg"},
    {"item_code": "FG020",   "qty": 0.048980, "uom": "Kg"},
    {"item_code": "FG019",   "qty": 0.010101, "uom": "Kg"},
    {"item_code": "RM020",   "qty": 0.028000, "uom": "Kg"},
    {"item_code": "M003",    "qty": 0.015000, "uom": "Kg"},
    {"item_code": "M006",    "qty": 0.004412, "uom": "Kg"},
    {"item_code": "FG021",   "qty": 0.042105, "uom": "Kg"},
    {"item_code": "FG022",   "qty": 0.002105, "uom": "Kg"},
    {"item_code": "PM020",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM021",   "qty": 1.0, "uom": "Nos"},
    {"item_code": "PM003",   "qty": 1.0, "uom": "Nos"},
]
create_bom_under_company("MN-TIKIM-CHOCO-BROWNIE", BEI, tikim_choco_brownie,
                         quantity=1, uom="Cup", remarks="S159: Tikim Choco Brownie from component recipes")


# ---------------------------------------------------------------
# Final Verification Summary
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

# Check specific BOMs
for item_code in ["FG001", "FG020", "MN001", "MN016", iskrambol_code, ginataang_code]:
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
        print(f"  {item_code}: NO active default BOM found")

# Items check
for code in ["RM216", "RM217"]:
    exists = frappe.db.exists("Item", code)
    print(f"  Item {code}: {'EXISTS' if exists else 'MISSING'}")

print("\nS159-CONTAINER-DONE")
frappe.destroy()
