#!/usr/bin/env python3
"""S178 Phase 1 v3 — Fix remaining orphans + materialize store_locations column + populate."""
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
# TASK 1.1 FIX v3: Find the actual BEI root-level groups
# ============================================================
try:
    # Let's see ALL root-level groups on BEI (parent_account = NULL or empty)
    bei_roots = frappe.db.sql("""
        SELECT name, account_name, root_type, is_group
        FROM `tabAccount`
        WHERE company = 'Bebang Enterprise Inc.'
          AND (parent_account IS NULL OR parent_account = '')
        ORDER BY root_type, name
    """, as_dict=True)
    result["tasks"]["1.1_bei_roots"] = bei_roots

    # Find the correct parent for each orphan
    orphan_mapping = {
        "GR/IR CLEARING - BEI": "Asset",        # inventory clearing = current asset
        "PROPERTY, PLANT AND EQUIPMENT - BEI": "Asset",  # fixed asset = non-current asset
        "ADVANCES TO SSS - BEI": "Asset",        # prepayment / advances = current asset
    }

    fixes = []
    for orphan_name, root_type in orphan_mapping.items():
        if not frappe.db.exists("Account", orphan_name):
            fixes.append({"account": orphan_name, "status": "NOT_FOUND"})
            continue

        # Find the root-level group for this root_type on BEI
        root_candidates = [r for r in bei_roots if r["root_type"] == root_type and r["is_group"]]

        if root_candidates:
            # Pick the first root-level group
            new_parent = root_candidates[0]["name"]
            frappe.db.set_value("Account", orphan_name, "parent_account", new_parent)
            fixes.append({
                "account": orphan_name,
                "new_parent": new_parent,
                "root_type": root_type,
                "status": "FIXED_TO_ROOT",
            })
        else:
            fixes.append({"account": orphan_name, "status": "NO_ROOT_FOR_TYPE", "root_type": root_type})
            result["errors"].append(f"No {root_type} root group on BEI for {orphan_name}")

    # Also fix STOCK ADJUSTMENT which was incorrectly fixed to LOCAL AD & PROMO (Expense, wrong!)
    stock_adj = frappe.db.get_value("Account", "STOCK ADJUSTMENT - BEI",
        ["parent_account", "root_type"], as_dict=True)
    if stock_adj:
        # STOCK ADJUSTMENT should be under an Expense group, not LOCAL AD & PROMO
        expense_roots = [r for r in bei_roots if r["root_type"] == "Expense" and r["is_group"]]
        if expense_roots:
            frappe.db.set_value("Account", "STOCK ADJUSTMENT - BEI", "parent_account", expense_roots[0]["name"])
            fixes.append({
                "account": "STOCK ADJUSTMENT - BEI",
                "old_wrong_parent": stock_adj["parent_account"],
                "new_parent": expense_roots[0]["name"],
                "status": "RE-FIXED",
            })

    frappe.db.commit()
    result["tasks"]["1.1_fixes_v3"] = fixes

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
        result["tasks"]["1.1_remaining_details"] = [dict(r) for r in remaining]

except Exception as e:
    import traceback
    result["errors"].append(f"Task 1.1: {e}\n{traceback.format_exc()}")

# ============================================================
# TASK 1.3+1.4: Materialize the store_locations column + populate
# ============================================================
try:
    # Check if column exists in MariaDB
    cols = frappe.db.sql("SHOW COLUMNS FROM `tabCompany` LIKE 'store_locations'", as_dict=True)
    if not cols:
        # Add the column directly
        frappe.db.sql("ALTER TABLE `tabCompany` ADD COLUMN `store_locations` TEXT")
        frappe.db.commit()
        result["tasks"]["1.3_column"] = "CREATED_VIA_ALTER"
    else:
        result["tasks"]["1.3_column"] = "ALREADY_EXISTS"

    # Now populate
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
            frappe.db.sql(
                "UPDATE `tabCompany` SET store_locations = %s WHERE name = %s",
                (stores, company_name),
            )
            updated += 1
        else:
            not_found.append(company_name)

    frappe.db.commit()
    result["tasks"]["1.4"] = {"updated": updated, "not_found": not_found, "status": "DONE"}

    # Verify
    with_stores = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != ''"
    )[0][0]
    result["tasks"]["1.4_verified_count"] = with_stores

except Exception as e:
    import traceback
    result["errors"].append(f"Task 1.3+1.4: {e}\n{traceback.format_exc()}")

# ============================================================
# FINAL VERIFICATION
# ============================================================
try:
    vat_acct = frappe.db.get_single_value("BEI Settings", "input_vat_goods_account")
    vat_exists = bool(frappe.db.exists("Account", vat_acct)) if vat_acct else False

    orphan_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Bebang Enterprise Inc.'
          AND a.parent_account IS NOT NULL AND a.parent_account != ''
          AND p.name IS NULL
    """)[0][0]

    stores_count = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != ''"
    )[0][0]

    result["verify"] = {
        "input_vat_goods": {"value": vat_acct, "exists": vat_exists},
        "orphans_remaining": orphan_count,
        "companies_with_store_locations": stores_count,
        "store_locations_field_exists": bool(frappe.db.exists("Custom Field", "Company-store_locations")),
        "store_locations_column_exists": bool(frappe.db.sql("SHOW COLUMNS FROM `tabCompany` LIKE 'store_locations'")),
    }
    result["all_pass"] = (
        vat_exists
        and orphan_count == 0
        and stores_count >= 35
        and result["verify"]["store_locations_column_exists"]
    )
except Exception as e:
    result["errors"].append(f"Verification: {e}")

print("RESULT_BEGIN")
print(json.dumps(result, default=str, indent=2))
print("RESULT_END")
