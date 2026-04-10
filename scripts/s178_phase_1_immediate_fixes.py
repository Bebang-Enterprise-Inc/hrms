#!/usr/bin/env python3
"""S178 Phase 1 — Immediate fixes (zero dependencies).

Executes inside frappe_backend container via SSM.

Tasks:
1.1 Fix 4 BEI orphan accounts (broken parent_account)
1.2 Fix BEI Settings.input_vat_goods_account (empty → INPUT VAT - GOODS)
1.3 Create store_locations Custom Field on Company DocType
1.4 Populate store_locations from store-entity mapping
1.5 Rebuild nested-set tree (per-company if global times out)
"""
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
# TASK 1.1: Fix 4 BEI orphan accounts
# ============================================================
try:
    orphans = frappe.db.sql("""
        SELECT a.name, a.account_name, a.parent_account, a.account_number
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Bebang Enterprise Inc.'
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """, as_dict=True)

    result["tasks"]["1.1_orphans_found"] = len(orphans)
    result["tasks"]["1.1_orphan_details"] = []

    for orphan in orphans:
        old_parent = orphan["parent_account"]
        # Try to find the correct parent by matching the intended parent name pattern
        # The broken refs are like "COST OF SALES - BEI", "INVENTORY - BEI" etc.
        # These were likely renamed during COA import. Find the actual group account.
        parent_name_part = old_parent.replace(" - BEI", "").replace(" - Bebang Enterprise Inc.", "").strip()

        # Search for a matching group account on BEI
        candidates = frappe.db.sql("""
            SELECT name, account_name FROM `tabAccount`
            WHERE company = 'Bebang Enterprise Inc.'
              AND is_group = 1
              AND (account_name LIKE %s OR name LIKE %s)
            ORDER BY LENGTH(name) LIMIT 5
        """, (f"%{parent_name_part}%", f"%{parent_name_part}%"), as_dict=True)

        fix_info = {
            "account": orphan["name"],
            "old_parent": old_parent,
            "candidates": [c["name"] for c in candidates],
        }

        if candidates:
            new_parent = candidates[0]["name"]
            frappe.db.set_value("Account", orphan["name"], "parent_account", new_parent)
            fix_info["new_parent"] = new_parent
            fix_info["status"] = "FIXED"
        else:
            # If no matching group, try broader search or set to the root
            # Find the root group for this account's root_type
            acct_info = frappe.db.get_value("Account", orphan["name"], ["root_type"], as_dict=True)
            if acct_info:
                root = frappe.db.get_value("Account", {
                    "company": "Bebang Enterprise Inc.",
                    "root_type": acct_info["root_type"],
                    "is_group": 1,
                    "parent_account": ["in", ["", None]],
                }, "name")
                if root:
                    frappe.db.set_value("Account", orphan["name"], "parent_account", root)
                    fix_info["new_parent"] = root
                    fix_info["status"] = "FIXED_TO_ROOT"
                else:
                    fix_info["status"] = "UNFIXED_NO_ROOT"
                    result["errors"].append(f"No root found for {orphan['name']}")
            else:
                fix_info["status"] = "UNFIXED_NO_INFO"
                result["errors"].append(f"No root_type info for {orphan['name']}")

        result["tasks"]["1.1_orphan_details"].append(fix_info)

    frappe.db.commit()

    # Verify
    remaining = frappe.db.sql("""
        SELECT a.name FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Bebang Enterprise Inc.'
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """, as_dict=True)
    result["tasks"]["1.1_remaining_orphans"] = len(remaining)

except Exception as e:
    result["errors"].append(f"Task 1.1: {e}")

# ============================================================
# TASK 1.2: Fix BEI Settings.input_vat_goods_account
# ============================================================
try:
    account_name = frappe.db.get_value("Account",
        {"company": "Bebang Enterprise Inc.", "account_name": ["like", "%INPUT VAT%GOODS%"]},
        "name")

    if not account_name:
        # Try broader search
        account_name = frappe.db.get_value("Account",
            {"company": "Bebang Enterprise Inc.", "account_name": "INPUT VAT - GOODS"},
            "name")

    old_val = frappe.db.get_single_value("BEI Settings", "input_vat_goods_account")

    if account_name:
        frappe.db.set_single_value("BEI Settings", "input_vat_goods_account", account_name)
        frappe.db.commit()
        result["tasks"]["1.2"] = {
            "old_value": old_val or "(empty)",
            "new_value": account_name,
            "status": "FIXED",
        }
    else:
        result["tasks"]["1.2"] = {"status": "NOT_FOUND", "search": "INPUT VAT%GOODS on BEI"}
        result["errors"].append("Task 1.2: INPUT VAT - GOODS account not found on BEI")

except Exception as e:
    result["errors"].append(f"Task 1.2: {e}")

# ============================================================
# TASK 1.3: Create store_locations Custom Field on Company
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
        cf.in_standard_filter = 1
        cf.search_index = 1
        cf.insert(ignore_permissions=True)
        frappe.db.commit()
        result["tasks"]["1.3"] = {"status": "CREATED"}

except Exception as e:
    result["errors"].append(f"Task 1.3: {e}")

# ============================================================
# TASK 1.4: Populate store_locations from mapping data
# ============================================================
try:
    # Hardcoded store-to-company mapping (from the verified store_buyer_entity_register + ENTITY_TIN_RDO)
    # Grouped by Frappe Company name → list of store names
    store_map = {
        "Irresistible Infusions Inc.": "(Holding company — no stores)",
        "Bebang Enterprise Inc.": "Head Office, SM Megamall, SM Manila, SM Southmall, Robinsons Place Antipolo",
        "Bebang Kitchen Inc.": "Commissary (Shaw Blvd, Mandaluyong)",
        "BEBANG FRANCHISE CORP.": "(Franchisor entity — no stores)",
        "DMD HOLDINGS INC.": "Uptown Mall",
        "JV": "(JV entity — stores under individual JV corps)",
        "Managed Franchise": "(MF entity — stores under individual franchise corps)",
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
        "BEBANG MEGA INC.": "SM Tanza, Robinsons Place Imus, Ayala Evo City, Ayala Vermosa, Robinsons Place Gen. Trias",
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
    skipped = 0
    for company_name, stores in store_map.items():
        if frappe.db.exists("Company", company_name):
            frappe.db.set_value("Company", company_name, "store_locations", stores)
            updated += 1
        else:
            skipped += 1

    frappe.db.commit()
    result["tasks"]["1.4"] = {
        "updated": updated,
        "skipped": skipped,
        "total_mapped": len(store_map),
        "status": "DONE",
    }

except Exception as e:
    result["errors"].append(f"Task 1.4: {e}")

# ============================================================
# TASK 1.5: Rebuild nested-set tree
# ============================================================
try:
    from frappe.utils.nestedset import rebuild_tree
    rebuild_tree("Account", "parent_account")
    frappe.db.commit()
    result["tasks"]["1.5"] = {"status": "REBUILD_COMPLETE"}
except Exception as e:
    result["tasks"]["1.5"] = {"status": "REBUILD_FAILED", "error": str(e)}
    result["errors"].append(f"Task 1.5: {e}")

# ============================================================
# VERIFICATION
# ============================================================
try:
    # Check orphans again
    remaining_orphans = frappe.db.sql("""
        SELECT a.name, a.parent_account FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Bebang Enterprise Inc.'
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """, as_dict=True)
    result["verify_orphans"] = len(remaining_orphans)

    # Check BEI Settings
    vat_acct = frappe.db.get_single_value("BEI Settings", "input_vat_goods_account")
    vat_exists = bool(frappe.db.exists("Account", vat_acct)) if vat_acct else False
    result["verify_input_vat"] = {"value": vat_acct, "exists": vat_exists}

    # Check store_locations field
    cf_exists = frappe.db.exists("Custom Field", "Company-store_locations")
    result["verify_store_locations_field"] = bool(cf_exists)

    # Count companies with non-empty store_locations
    with_stores = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabCompany`
        WHERE store_locations IS NOT NULL AND store_locations != ''
    """)[0][0]
    result["verify_companies_with_store_locations"] = with_stores

    # All pass?
    result["all_pass"] = (
        len(remaining_orphans) == 0
        and vat_exists
        and bool(cf_exists)
        and with_stores >= 35
    )

except Exception as e:
    result["errors"].append(f"Verification: {e}")

print("RESULT_BEGIN")
print(json.dumps(result, default=str, indent=2))
print("RESULT_END")
