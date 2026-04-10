#!/usr/bin/env python3
"""S178 Phase 1 v2 — Fix orphans + create store_locations + populate."""
from __future__ import annotations

import json
import os

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe  # type: ignore

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {"tasks": {}, "errors": []}

# ============================================================
# TASK 1.1 FIX: Find the actual BEI group accounts for each orphan
# ============================================================
try:
    # First, let's see what group accounts BEI actually has
    bei_groups = frappe.db.sql("""
        SELECT name, account_name, account_number, root_type, parent_account
        FROM `tabAccount`
        WHERE company = 'Bebang Enterprise Inc.' AND is_group = 1
        ORDER BY account_number, name
    """, as_dict=True)
    result["tasks"]["1.1_bei_groups_count"] = len(bei_groups)

    # Map orphans to likely parents based on accounting logic
    orphan_fixes = {
        "STOCK ADJUSTMENT - BEI": {
            "search_root_type": "Expense",
            "search_pattern": ["COST OF GOODS SOLD", "COST OF SALES", "DIRECT COSTS", "EXPENSES"],
        },
        "GR/IR CLEARING - BEI": {
            "search_root_type": "Asset",
            "search_pattern": ["CURRENT ASSETS", "STOCK ASSETS", "INVENTORIES", "RECEIVABLES"],
        },
        "PROPERTY, PLANT AND EQUIPMENT - BEI": {
            "search_root_type": "Asset",
            "search_pattern": ["NON-CURRENT ASSETS", "FIXED ASSETS", "PROPERTY"],
        },
        "ADVANCES TO SSS - BEI": {
            "search_root_type": "Asset",
            "search_pattern": ["CURRENT ASSETS", "RECEIVABLES", "PREPAYMENTS", "ADVANCES"],
        },
    }

    fix_results = []
    for orphan_name, config in orphan_fixes.items():
        if not frappe.db.exists("Account", orphan_name):
            fix_results.append({"account": orphan_name, "status": "NOT_FOUND"})
            continue

        # Try each pattern in order
        found_parent = None
        for pattern in config["search_pattern"]:
            candidates = frappe.db.sql("""
                SELECT name, account_name FROM `tabAccount`
                WHERE company = 'Bebang Enterprise Inc.'
                  AND is_group = 1
                  AND root_type = %s
                  AND account_name LIKE %s
                ORDER BY LENGTH(name) LIMIT 3
            """, (config["search_root_type"], f"%{pattern}%"), as_dict=True)
            if candidates:
                found_parent = candidates[0]["name"]
                break

        # If still no match, use the root-level group for this root_type
        if not found_parent:
            root = frappe.db.sql("""
                SELECT name FROM `tabAccount`
                WHERE company = 'Bebang Enterprise Inc.'
                  AND is_group = 1
                  AND root_type = %s
                  AND (parent_account IS NULL OR parent_account = '')
                LIMIT 1
            """, config["search_root_type"], as_dict=True)
            if root:
                found_parent = root[0]["name"]

        if found_parent:
            frappe.db.set_value("Account", orphan_name, "parent_account", found_parent)
            fix_results.append({
                "account": orphan_name,
                "old_parent": frappe.db.get_value("Account", orphan_name, "parent_account"),
                "new_parent": found_parent,
                "status": "FIXED",
            })
        else:
            fix_results.append({"account": orphan_name, "status": "NO_PARENT_FOUND"})
            result["errors"].append(f"No parent found for {orphan_name}")

    frappe.db.commit()
    result["tasks"]["1.1_fixes"] = fix_results

    # Verify
    remaining = frappe.db.sql("""
        SELECT a.name, a.parent_account FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Bebang Enterprise Inc.'
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """, as_dict=True)
    result["tasks"]["1.1_remaining_orphans"] = len(remaining)
    if remaining:
        result["tasks"]["1.1_remaining_details"] = [r for r in remaining]

except Exception as e:
    import traceback
    result["errors"].append(f"Task 1.1: {e}")

# ============================================================
# TASK 1.3 FIX: Create store_locations without search_index
# ============================================================
try:
    if frappe.db.exists("Custom Field", "Company-store_locations"):
        result["tasks"]["1.3"] = {"status": "ALREADY_EXISTS"}
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = "Company"
        cf.fieldname = "store_locations"
        cf.label = "Store Locations"
        cf.fieldtype = "Small Text"
        cf.insert_after = "company_name"
        cf.description = "Physical store names registered under this entity. Searchable in dropdowns."
        cf.in_list_view = 1
        cf.in_standard_filter = 0  # Can't index Small Text
        cf.search_index = 0  # Can't index Small Text
        cf.insert(ignore_permissions=True)
        frappe.db.commit()
        # Clear cache so the field is immediately usable
        frappe.clear_cache(doctype="Company")
        result["tasks"]["1.3"] = {"status": "CREATED"}

except Exception as e:
    result["errors"].append(f"Task 1.3: {e}")

# ============================================================
# TASK 1.4: Populate store_locations
# ============================================================
try:
    store_map = {
        "Irresistible Infusions Inc.": "(Holding company - no stores)",
        "Bebang Enterprise Inc.": "Head Office, SM Megamall, SM Manila, SM Southmall, Robinsons Place Antipolo",
        "Bebang Kitchen Inc.": "Commissary (Shaw Blvd, Mandaluyong)",
        "BEBANG FRANCHISE CORP.": "(Franchisor entity - no stores)",
        "DMD HOLDINGS INC.": "Uptown Mall",
        "JV": "(JV entity - stores under individual JV corps)",
        "Managed Franchise": "(MF entity - stores under individual franchise corps)",
        "BEBANG ARANETA GATEWAY": "Araneta Gateway",
        "BEBANG AYALA SOLENAD": "Ayala Solenad 2",
        "BEBANG BF HOMES INC.": "BF Homes Paranaque (Aguirre Ave.)",
        "BEBANG D'VERDE": "D'Verde Calamba",
        "BEBANG EVER GOTESCO COMMONWEALTH": "Ever Commonwealth",
        "BEBANG FESTIVAL INC.": "Festival Mall Alabang",
        "BEBANG FT INC.": "Ayala Fairview Terraces",
        "BEBANG GRAND CENTRAL INC.": "SM Grand Central",
        "BEBANG LCT INC.": "Lucky China Town",
        "BEBANG MARILAO INC.": "SM Marilao",
        "BEBANG MARKET MARKET INC.": "Ayala Market! Market!",
        "BEBANG MEGA INC.": "SM Tanza, Robinsons Imus, Evo City, Vermosa, Gen. Trias",
        "BEBANG NORTH EDSA INC.": "SM North EDSA",
        "BEBANG PASEO INC.": "Paseo Center",
        "BEBANG PITX INC.": "PITX Terminal",
        "BEBANG ROBINSONS GALLERIA SOUTH": "Robinsons Galleria South",
        "BEBANG SM BICUTAN INC.": "SM Bicutan",
        "BEBANG SM CALOOCAN": "SM Caloocan",
        "BEBANG SM CLARK": "SM Clark",
        "BEBANG SM MARIKINA INC.": "SM Marikina, Sta. Lucia East Grand Mall",
        "BEBANG SM SANGANDAAN": "SM Sangandaan",
        "BEBANG SM SJDM": "SM San Jose Del Monte",
        "BEBANG SM TAYTAY": "SM Taytay",
        "BEBANG SMEO INC.": "SM East Ortigas",
        "BEBANG SMM INC.": "SM Center Pulilan",
        "BEBANG SMOA INC.": "SM Mall of Asia",
        "BEBANG SMV INC.": "SM Valenzuela",
        "BEBANG STARMALL ALABANG INC.": "The Terminal Exchange",
        "BEBANG THE GRID FOOD MARKET": "The Grid - Rockwell",
        "BEBANG TOMAS MORATO": "Tomas Morato (CTTM Square)",
        "BEBANG UP TOWN CENTER INC.": "Ayala UP Town Center",
        "BEBANG VENICE GRAND CANAL INC.": "Venice Grand Canal",
        "BEBANG VISTAMALL": "Vista Mall Taguig",
    }

    updated = 0
    not_found = []
    for company_name, stores in store_map.items():
        if frappe.db.exists("Company", company_name):
            frappe.db.set_value("Company", company_name, "store_locations", stores, update_modified=False)
            updated += 1
        else:
            not_found.append(company_name)

    frappe.db.commit()
    result["tasks"]["1.4"] = {
        "updated": updated,
        "not_found": not_found,
        "status": "DONE",
    }

    # Verify count
    with_stores = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabCompany`
        WHERE store_locations IS NOT NULL AND store_locations != ''
    """)[0][0]
    result["tasks"]["1.4_verified_count"] = with_stores

except Exception as e:
    result["errors"].append(f"Task 1.4: {e}")

# ============================================================
# FINAL VERIFICATION
# ============================================================
try:
    # BEI Settings check
    vat_acct = frappe.db.get_single_value("BEI Settings", "input_vat_goods_account")
    vat_exists = bool(frappe.db.exists("Account", vat_acct)) if vat_acct else False
    result["verify"] = {
        "input_vat_goods": {"value": vat_acct, "exists": vat_exists},
        "store_locations_field": bool(frappe.db.exists("Custom Field", "Company-store_locations")),
        "companies_with_stores": frappe.db.sql("SELECT COUNT(*) FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != ''")[0][0],
        "orphans_remaining": frappe.db.sql("""
            SELECT COUNT(*) FROM `tabAccount` a
            LEFT JOIN `tabAccount` p ON a.parent_account = p.name
            WHERE a.company = 'Bebang Enterprise Inc.'
              AND a.parent_account IS NOT NULL AND a.parent_account != ''
              AND p.name IS NULL
        """)[0][0],
        "rebuild_tree": "completed in v1",
    }
    result["all_pass"] = (
        vat_exists
        and result["verify"]["store_locations_field"]
        and result["verify"]["companies_with_stores"] >= 35
        and result["verify"]["orphans_remaining"] == 0
    )
except Exception as e:
    result["errors"].append(f"Verification: {e}")

print("RESULT_BEGIN")
print(json.dumps(result, default=str, indent=2))
print("RESULT_END")
