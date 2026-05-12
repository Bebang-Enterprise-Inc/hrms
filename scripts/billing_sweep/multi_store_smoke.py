#!/usr/bin/env python3
"""Billing-sweep multi-store smoke runner — BKI->Store PI generator validation.

For each store in STORES_READY (45) + STORES_BROKEN (4):
  1. Create + submit a test BKI SI with customer=store Company, item=PM003 @ 1.00 PHP
  2. Capture autoname result (BKI-SI-YYYY-tail-n)
  3. Probe for the paired Draft PI on the store's Company books
  4. Cancel the SI -> cascade should delete the Draft PI
  5. Force-delete the cancelled SI

Expected:
  STORES_READY (45)  -> PI created with all 12 mirror fields correct
  STORES_BROKEN (4)  -> SI submits but NO PI exists (silent _resolve_per_store_cost_center failure)

Output: /tmp/s244_sweep_result.json  with per-store breakdown + summary.
ALL artifacts cleaned up in finally block.
"""
from __future__ import annotations

import os
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import json
import sys
import traceback
from datetime import datetime

import frappe  # type: ignore

BKI_COMPANY = "BEBANG KITCHEN INC."
BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"
ITEM_CODE = "PM003"
RATE = 1.00
QTY = 1
TODAY = "2026-05-11"
TAX_TEMPLATE = "BKI Output VAT 12% Sales - BKI"
DEBIT_TO = "Debtors - BKI"

# 45 stores ready for PI generation (from probe_result.json summary)
STORES_READY = [
    "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
    "AYALA EVO CITY - BEBANG MEGA INC.",
    "AYALA FAIRVIEW TERRACES - BEBANG FT INC.",
    "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.",
    "AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.",
    "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.",
    "AYALA VERMOSA - BEBANG MEGA INC.",
    "BF HOMES - BEBANG BF HOMES INC.",
    "CTTM TOMAS MORATO - B CUBED VENTURES CORP.",
    "D'VERDE CALAMBA - TAJ FOOD CORP.",
    "EVER COMMONWEALTH - DLS DESSERT CRAFT INC.",
    "FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC.",
    "LUCKY CHINATOWN - BEBANG LCT INC.",
    "MEGAWIDE PITX - BEBANG PITX INC.",
    "MEGAWORLD PASEO CENTER - BEBANG PASEO INC.",
    "MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.",
    "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
    "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
    "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
    "ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC",
    "ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.",
    "ROBINSONS IMUS - BEBANG MEGA INC.",
    "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
    "SM BICUTAN - BEBANG SM BICUTAN INC.",
    "SM CALOOCAN - TAJ FOOD CORP.",
    "SM CLARK - RED TALDAWA FOODS OPC",
    "SM EAST ORTIGAS - BEBANG SMEO INC.",
    "SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC.",
    "SM MALL OF ASIA - BEBANG SMOA INC.",
    "SM MARIKINA - BEBANG SM MARIKINA INC.",
    "SM MARILAO - BEBANG MARILAO INC.",
    "SM NORTH EDSA - BEBANG NORTH EDSA INC.",
    "SM PULILAN - BEBANG SMM INC.",
    "SM SAN JOSE DEL MONTE - JL TRADE OPC",
    "SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC",
    "SM STA. ROSA - SWEET HARMONY FOOD CORP.",
    "SM TANZA - BEBANG MEGA INC.",
    "SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.",
    "SM VALENZUELA - BEBANG SMV INC.",
    "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
    "THE GRID ROCKWELL - TASTECARTEL CORP.",
    "THE TERMINAL - BEBANG STARMALL ALABANG INC.",
    "UP TOWN MALL BGC - DMD HOLDINGS INC.",
    "VISTA MALL TAGUIG - TRICERN FOOD CORP.",
    "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
    # S247 P4a (2026-05-12): added the 4 BEI-Enterprise stores post cost_center fix.
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]

# S247: STORES_BROKEN emptied — P4a fixed the cost_center on the 4 BEI-Enterprise stores;
# they're now in STORES_READY above. Kept as empty list to preserve verdict-loop structure.
STORES_BROKEN = []

# Real BEI Store Order # per store (queried via probe_order_per_store.py 2026-05-11)
STORE_ORDER_MAP = {
    'ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC': 'BEI-ORD-2026-00981',
    'AYALA EVO CITY - BEBANG MEGA INC.': 'BEI-ORD-2026-00982',
    'AYALA FAIRVIEW TERRACES - BEBANG FT INC.': 'BEI-ORD-2026-00983',
    'AYALA MARKET MARKET - BEBANG MARKET MARKET INC.': 'BEI-ORD-2026-00984',
    'AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.': 'BEI-ORD-2026-00985',
    'AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.': 'BEI-ORD-2026-00986',
    'AYALA VERMOSA - BEBANG MEGA INC.': 'BEI-ORD-2026-00988',
    'BF HOMES - BEBANG BF HOMES INC.': 'BEI-ORD-2026-00989',
    'CTTM TOMAS MORATO - B CUBED VENTURES CORP.': 'BEI-ORD-2026-00990',
    "D'VERDE CALAMBA - TAJ FOOD CORP.": 'BEI-ORD-2026-00991',
    'EVER COMMONWEALTH - DLS DESSERT CRAFT INC.': 'BEI-ORD-2026-00992',
    'FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC.': 'BEI-ORD-2026-00993',
    'LUCKY CHINATOWN - BEBANG LCT INC.': 'BEI-ORD-2026-00994',
    'MEGAWIDE PITX - BEBANG PITX INC.': 'BEI-ORD-2026-00995',
    'MEGAWORLD PASEO CENTER - BEBANG PASEO INC.': 'BEI-ORD-2026-00997',
    'MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.': 'BEI-ORD-2026-00998',
    'NAIA T3 - HALO-HALO TERMINAL FOOD CORP.': 'BEI-ORD-2026-00999',
    'ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.': 'BEI-ORD-2026-01000',
    'ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC': 'BEI-ORD-2026-01001',
    'ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC': 'BEI-ORD-2026-01003',
    'ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.': 'BEI-ORD-2026-01005',
    'ROBINSONS IMUS - BEBANG MEGA INC.': 'BEI-ORD-2026-01007',
    'ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.': 'BEI-ORD-2026-01008',
    'SM BICUTAN - BEBANG SM BICUTAN INC.': 'BEI-ORD-2026-01009',
    'SM CALOOCAN - TAJ FOOD CORP.': 'BEI-ORD-2026-01010',
    'SM CLARK - RED TALDAWA FOODS OPC': 'BEI-ORD-2026-01011',
    'SM EAST ORTIGAS - BEBANG SMEO INC.': 'BEI-ORD-2026-01012',
    'SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC.': 'BEI-ORD-2026-01013',
    'SM MALL OF ASIA - BEBANG SMOA INC.': 'BEI-ORD-2026-01014',
    'SM MARIKINA - BEBANG SM MARIKINA INC.': 'BEI-ORD-2026-01016',
    'SM MARILAO - BEBANG MARILAO INC.': 'BEI-ORD-2026-01017',
    'SM NORTH EDSA - BEBANG NORTH EDSA INC.': 'BEI-ORD-2026-01019',
    'SM PULILAN - BEBANG SMM INC.': 'BEI-ORD-2026-01020',
    'SM SAN JOSE DEL MONTE - JL TRADE OPC': 'BEI-ORD-2026-01021',
    'SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC': 'BEI-ORD-2026-01022',
    'SM STA. ROSA - SWEET HARMONY FOOD CORP.': 'BEI-ORD-2026-01024',
    'SM TANZA - BEBANG MEGA INC.': 'BEI-ORD-2026-01025',
    'SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.': 'BEI-ORD-2026-01026',
    'SM VALENZUELA - BEBANG SMV INC.': 'BEI-ORD-2026-01027',
    'STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.': 'BEI-ORD-2026-01028',
    'THE GRID ROCKWELL - TASTECARTEL CORP.': 'BEI-ORD-2026-01029',
    'THE TERMINAL - BEBANG STARMALL ALABANG INC.': 'BEI-ORD-2026-01030',
    'UP TOWN MALL BGC - DMD HOLDINGS INC.': 'BEI-ORD-2026-01031',
    'VISTA MALL TAGUIG - TRICERN FOOD CORP.': 'BEI-ORD-2026-01032',
    'XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.': 'BEI-ORD-2026-01033',
    'ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.': 'BEI-ORD-2026-01002',
    'SM MANILA - BEBANG ENTERPRISE INC.': 'BEI-ORD-2026-01015',
    'SM MEGAMALL - BEBANG ENTERPRISE INC.': 'BEI-ORD-2026-01018',
    'SM SOUTHMALL - BEBANG ENTERPRISE INC.': 'BEI-ORD-2026-01023',
}

# Master tracker — populated as docs are created; finally force-deletes all
CREATED: list[dict] = []


def _store_label(company_name: str) -> str:
    """The part before ' - ' is the storefront label (e.g., 'ARANETA GATEWAY')."""
    return company_name.split(" - ")[0].strip() or company_name


def _smoke_one_store(idx: int, company: str, phase: str) -> dict:
    """Run create+submit+assert+cancel+delete on one store. Returns full result dict."""
    order_no = STORE_ORDER_MAP.get(company)
    result = {
        "idx": idx,
        "company": company,
        "phase": phase,  # 'READY' or 'BROKEN'
        "store_label": _store_label(company),
        "order_no": order_no,
        "abbr": frappe.db.get_value("Company", company, "abbr"),
        "stages": {},
    }
    if not order_no:
        result["stages"]["create_submit"] = {
            "ok": False,
            "error": f"No BEI Store Order in STORE_ORDER_MAP for {company}",
        }
        return result
    si_name_pre = None
    si_name_post = None
    pi_name = None

    # --- stage create+submit ---
    try:
        si = frappe.new_doc("Sales Invoice")
        si.company = BKI_COMPANY
        si.customer = company
        si.posting_date = TODAY
        si.set_posting_time = 1
        si.posting_time = "10:00:00"
        si.naming_series = "BKI-SI-.YYYY.-.#####"
        si.debit_to = DEBIT_TO
        si.taxes_and_charges = TAX_TEMPLATE
        si.currency = "PHP"
        si.custom_bei_store_order = order_no
        # S192 + S203 mandatory fields
        si.bei_legal_entity = BKI_COMPANY
        si.bei_store_label = result["store_label"]
        si.append("items", {
            "item_code": ITEM_CODE,
            "qty": QTY,
            "rate": RATE,
        })
        template_taxes = frappe.db.sql(
            """SELECT charge_type, account_head, description, rate, included_in_print_rate, cost_center
               FROM `tabSales Taxes and Charges`
               WHERE parent=%s ORDER BY idx""",
            TAX_TEMPLATE,
            as_dict=True,
        )
        for t in (template_taxes or []):
            si.append("taxes", t)

        si.insert(ignore_permissions=True)
        si_name_pre = si.name
        CREATED.append({"doctype": "Sales Invoice", "name": si.name, "stage": "draft"})

        # Compute expected autoname BEFORE submit (post-submit it's renamed)
        # autoname formula: BKI-SI-{year}-{tail}-{existing_count + 1}
        import re as _re
        m = _re.match(r"^BEI-ORD-(\d{4})-(\d+)$", order_no)
        if m:
            year, tail = m.group(1), m.group(2)
            existing_count = frappe.db.count(
                "Sales Invoice",
                {
                    "custom_bei_store_order": order_no,
                    "company": BKI_COMPANY,
                    "name": ["!=", si.name or ""],
                },
            )
            expected_prefix = f"BKI-SI-{year}-{tail}-"
            expected_autoname = f"BKI-SI-{year}-{tail}-{existing_count + 1}"
        else:
            expected_prefix = "BKI-SI-MISC-"
            expected_autoname = None

        si.submit()
        si_name_post = si.name
        # Update tracker with post-autoname name
        CREATED[-1]["name"] = si.name
        CREATED[-1]["stage"] = "submitted"

        result["stages"]["create_submit"] = {
            "ok": True,
            "si_name_pre_autoname": si_name_pre,
            "si_name_post_autoname": si_name_post,
            "expected_autoname": expected_autoname,
            "expected_autoname_prefix": expected_prefix,
            "autoname_matches_pattern": si_name_post.startswith(expected_prefix),
            "autoname_exact_match": (si_name_post == expected_autoname) if expected_autoname else None,
            "grand_total": si.grand_total,
        }
    except Exception as e:
        result["stages"]["create_submit"] = {
            "ok": False,
            "error": str(e)[:500],
            "traceback": traceback.format_exc()[:1200],
        }
        return result

    # --- stage assert_pi ---
    try:
        pi_name = frappe.db.get_value(
            "Purchase Invoice", {"bki_si_reference": si_name_post}, "name"
        )
        result["stages"]["assert_pi"] = {"pi_name": pi_name, "pi_exists": bool(pi_name)}

        if pi_name:
            CREATED.append({"doctype": "Purchase Invoice", "name": pi_name, "stage": "draft"})
            pi = frappe.get_doc("Purchase Invoice", pi_name)
            # Capture all 20 fields like the S238 smoke test
            result["stages"]["assert_pi"].update({
                "pi_company": pi.company,
                "pi_company_matches_buyer": pi.company == company,
                "pi_supplier": pi.supplier,
                "pi_supplier_is_bki_trade": pi.supplier == BKI_TRADE_SUPPLIER,
                "pi_docstatus": pi.docstatus,
                "pi_is_draft": pi.docstatus == 0,
                "pi_currency": pi.currency,
                "pi_currency_is_php": pi.currency == "PHP",
                "pi_conversion_rate": float(pi.conversion_rate or 0),
                "pi_bill_no": pi.bill_no,
                "pi_bill_no_matches_si": pi.bill_no == si_name_post,
                "pi_bki_si_reference": pi.bki_si_reference,
                "pi_bki_si_reference_matches": pi.bki_si_reference == si_name_post,
                "pi_inter_company_invoice_reference": pi.inter_company_invoice_reference,
                "pi_update_stock": pi.update_stock,
                "pi_update_stock_is_0": pi.update_stock == 0,                # S247 v3: billing-only
                "pi_set_warehouse": pi.set_warehouse,
                "pi_set_warehouse_is_empty": not bool(pi.set_warehouse),     # S247 v3
                "pi_credit_to": pi.credit_to,
                "pi_credit_to_is_2103210": "2103210" in (pi.credit_to or ""),
                "pi_bei_legal_entity": getattr(pi, "bei_legal_entity", None),
                "pi_bei_legal_entity_is_buyer": getattr(pi, "bei_legal_entity", None) == company,
                "pi_bei_store_label": getattr(pi, "bei_store_label", None),
                "pi_grand_total": float(pi.grand_total or 0),
                "pi_items_count": len(pi.items),
                "pi_taxes_count": len(pi.taxes),
            })
            if pi.items:
                first = pi.items[0]
                # S247 v3: PI item expense_account is now SRBNB (GR/IR clearing), NOT 1104210.
                # Check by account_type via DB lookup.
                expense_acct_type = frappe.db.get_value(
                    "Account", first.expense_account or "", "account_type"
                ) if first.expense_account else None
                result["stages"]["assert_pi"].update({
                    "pi_item0_code": first.item_code,
                    "pi_item0_qty": float(first.qty or 0),
                    "pi_item0_rate": float(first.rate or 0),
                    "pi_item0_expense_account": first.expense_account,
                    "pi_item0_expense_account_type": expense_acct_type,
                    "pi_item0_expense_is_srbnb": expense_acct_type == "Stock Received But Not Billed",
                    "pi_item0_warehouse": first.warehouse,
                    "pi_item0_warehouse_is_empty": not bool(first.warehouse),   # S247 v3
                    "pi_item0_cost_center": first.cost_center,
                })
            if pi.taxes:
                first_tax = pi.taxes[0]
                result["stages"]["assert_pi"].update({
                    "pi_tax0_account": first_tax.account_head,
                    "pi_tax0_account_is_1106210": "1106210" in (first_tax.account_head or ""),
                    "pi_tax0_charge_type": first_tax.charge_type,
                    "pi_tax0_cost_center": first_tax.cost_center,
                })
        else:
            # Look for recent error logs referencing this SI
            errs = frappe.db.sql(
                """SELECT name, error, creation FROM `tabError Log`
                   WHERE error LIKE %s AND creation >= NOW() - INTERVAL 5 MINUTE
                   ORDER BY creation DESC LIMIT 2""",
                f"%{si_name_post}%",
                as_dict=True,
            )
            result["stages"]["assert_pi"]["recent_error_logs"] = [
                {
                    "name": r["name"],
                    "creation": str(r["creation"]),
                    "preview": r["error"][:400],
                }
                for r in errs
            ]
    except Exception as e:
        result["stages"]["assert_pi"] = {
            "ok": False,
            "error": str(e)[:500],
        }

    # --- stage assert_se (S247 v3: paired Stock Entry from new generator) ---
    se_name = None
    try:
        if frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
            se_name = frappe.db.get_value(
                "Stock Entry", {"bki_si_reference": si_name_post}, "name"
            )
        result["stages"]["assert_se"] = {"se_name": se_name, "se_exists": bool(se_name)}
        if se_name:
            CREATED.append({"doctype": "Stock Entry", "name": se_name, "stage": "draft"})
            se = frappe.get_doc("Stock Entry", se_name)
            result["stages"]["assert_se"].update({
                "se_company": se.company,
                "se_company_matches_buyer": se.company == company,
                "se_stock_entry_type": se.stock_entry_type,
                "se_is_material_receipt": se.stock_entry_type == "Material Receipt",
                "se_docstatus": se.docstatus,
                "se_is_draft": se.docstatus == 0,
                "se_bki_si_reference": se.bki_si_reference,
                "se_bki_si_reference_matches": se.bki_si_reference == si_name_post,
                "se_items_count": len(se.items),
            })
            if se.items:
                first_se = se.items[0]
                se_exp_acct_type = frappe.db.get_value(
                    "Account", first_se.expense_account or "", "account_type"
                ) if first_se.expense_account else None
                result["stages"]["assert_se"].update({
                    "se_item0_code": first_se.item_code,
                    "se_item0_t_warehouse": first_se.t_warehouse,
                    "se_item0_t_warehouse_matches_buyer": first_se.t_warehouse == company,
                    "se_item0_basic_rate": float(first_se.basic_rate or 0),
                    "se_item0_expense_account": first_se.expense_account,
                    "se_item0_expense_account_type": se_exp_acct_type,
                    # S247 v3: SE.item expense_account is SRBNB (GR/IR clearing — clears PI Dr)
                    "se_item0_expense_is_srbnb": se_exp_acct_type == "Stock Received But Not Billed",
                })
    except Exception as e:
        result["stages"]["assert_se"] = {"ok": False, "error": str(e)[:500]}

    # --- stage cancel ---
    try:
        si = frappe.get_doc("Sales Invoice", si_name_post)
        si.cancel()
        result["stages"]["cancel"] = {"ok": True, "si_docstatus": si.docstatus}

        pi_still_exists = bool(
            frappe.db.exists("Purchase Invoice", {"bki_si_reference": si_name_post})
        )
        se_still_exists = False
        if frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
            se_still_exists = bool(
                frappe.db.exists("Stock Entry", {"bki_si_reference": si_name_post})
            )
        result["stages"]["cancel"]["pi_still_exists_after_cancel"] = pi_still_exists
        result["stages"]["cancel"]["se_still_exists_after_cancel"] = se_still_exists
        # S247 v3: both must be gone for cascade_worked
        cascade_pi_ok = (not pi_still_exists) if pi_name else True
        cascade_se_ok = (not se_still_exists) if se_name else True
        result["stages"]["cancel"]["cascade_pi_worked"] = cascade_pi_ok
        result["stages"]["cancel"]["cascade_se_worked"] = cascade_se_ok
        result["stages"]["cancel"]["cascade_worked"] = cascade_pi_ok and cascade_se_ok
    except Exception as e:
        result["stages"]["cancel"] = {"ok": False, "error": str(e)[:500]}

    # --- stage force-delete SI ---
    try:
        frappe.delete_doc("Sales Invoice", si_name_post, force=True, ignore_permissions=True)
        result["stages"]["delete"] = {
            "ok": True,
            "si_still_exists": bool(frappe.db.exists("Sales Invoice", si_name_post)),
        }
        # Drop from tracker since we successfully cleaned it up
        CREATED[:] = [c for c in CREATED if not (c["doctype"] == "Sales Invoice" and c["name"] == si_name_post)]
        # Drop PI tracker if cascade already deleted it
        if pi_name and not frappe.db.exists("Purchase Invoice", pi_name):
            CREATED[:] = [c for c in CREATED if not (c["doctype"] == "Purchase Invoice" and c["name"] == pi_name)]
        # S247 v3: drop SE tracker if cascade already deleted it
        if se_name and not frappe.db.exists("Stock Entry", se_name):
            CREATED[:] = [c for c in CREATED if not (c["doctype"] == "Stock Entry" and c["name"] == se_name)]
    except Exception as e:
        result["stages"]["delete"] = {"ok": False, "error": str(e)[:500]}

    # --- per-store verdict (S247 v3: requires BOTH PI and SE dual-doc pass) ---
    if phase == "READY":
        ap = result["stages"].get("assert_pi", {})
        ase = result["stages"].get("assert_se", {})
        delete_ok = result["stages"].get("delete", {}).get("ok", False)
        cancel_ok = result["stages"].get("cancel", {}).get("ok", False)
        cascade_pi_ok = result["stages"].get("cancel", {}).get("cascade_pi_worked", False)
        cascade_se_ok = result["stages"].get("cancel", {}).get("cascade_se_worked", False)
        all_good = (
            result["stages"].get("create_submit", {}).get("ok", False)
            # PI assertions (S247 v3: billing-only, SRBNB expense, NO warehouse)
            and ap.get("pi_exists", False)
            and ap.get("pi_company_matches_buyer", False)
            and ap.get("pi_supplier_is_bki_trade", False)
            and ap.get("pi_currency_is_php", False)
            and ap.get("pi_update_stock_is_0", False)
            and ap.get("pi_set_warehouse_is_empty", False)
            and ap.get("pi_credit_to_is_2103210", False)
            and ap.get("pi_item0_expense_is_srbnb", False)
            and ap.get("pi_item0_warehouse_is_empty", False)
            and ap.get("pi_tax0_account_is_1106210", False)
            and ap.get("pi_bki_si_reference_matches", False)
            # SE assertions (S247 v3: Material Receipt, SRBNB expense, t_warehouse=buyer)
            and ase.get("se_exists", False)
            and ase.get("se_company_matches_buyer", False)
            and ase.get("se_is_material_receipt", False)
            and ase.get("se_is_draft", False)
            and ase.get("se_bki_si_reference_matches", False)
            and ase.get("se_item0_t_warehouse_matches_buyer", False)
            and ase.get("se_item0_expense_is_srbnb", False)
            # Cancel cascade (SE first per hooks.py order, then PI)
            and cancel_ok
            and cascade_pi_ok
            and cascade_se_ok
            and delete_ok
        )
        result["verdict"] = "PASS" if all_good else "FAIL"
    else:
        # BROKEN — expect SI submit OK, PI NOT created (defect proof)
        cs_ok = result["stages"].get("create_submit", {}).get("ok", False)
        pi_exists = result["stages"].get("assert_pi", {}).get("pi_exists", True)
        delete_ok = result["stages"].get("delete", {}).get("ok", False)
        defect_confirmed = (cs_ok and not pi_exists)
        result["verdict"] = "DEFECT_CONFIRMED" if (defect_confirmed and delete_ok) else "DEFECT_UNEXPECTED_STATE"

    return result


def _final_cleanup() -> list[str]:
    """Force-delete any artifact still in CREATED tracker."""
    log = []
    for entry in list(CREATED):
        dt = entry["doctype"]
        nm = entry["name"]
        try:
            if frappe.db.exists(dt, nm):
                doc = frappe.get_doc(dt, nm)
                if doc.docstatus == 1:
                    try:
                        doc.cancel()
                        log.append(f"Cancelled {dt} {nm}")
                    except Exception as e:
                        log.append(f"Cancel failed for {dt} {nm}: {str(e)[:200]}")
                try:
                    frappe.delete_doc(dt, nm, force=True, ignore_permissions=True)
                    log.append(f"Force-deleted {dt} {nm}")
                except Exception as e:
                    log.append(f"Delete failed for {dt} {nm}: {str(e)[:200]}")
            else:
                log.append(f"Already gone: {dt} {nm}")
        except Exception as e:
            log.append(f"Cleanup exception {dt} {nm}: {str(e)[:200]}")
    try:
        frappe.db.commit()
    except Exception:
        pass
    return log


def main() -> None:
    payload = {
        "sweep": "billing-sweep-2026-05-11",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stores_ready_count": len(STORES_READY),
        "stores_broken_count": len(STORES_BROKEN),
        "results": [],
        "cleanup_log": [],
    }

    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # Phase A — READY stores (45)
        for idx, company in enumerate(STORES_READY, start=1):
            try:
                r = _smoke_one_store(idx, company, "READY")
            except Exception as e:
                r = {"company": company, "phase": "READY", "verdict": "RUNNER_ERROR",
                     "error": str(e)[:500], "traceback": traceback.format_exc()[:1200]}
            payload["results"].append(r)
            try:
                frappe.db.commit()
            except Exception:
                pass

        # Phase B — BROKEN stores (4)
        for idx, company in enumerate(STORES_BROKEN, start=46):
            try:
                r = _smoke_one_store(idx, company, "BROKEN")
            except Exception as e:
                r = {"company": company, "phase": "BROKEN", "verdict": "RUNNER_ERROR",
                     "error": str(e)[:500], "traceback": traceback.format_exc()[:1200]}
            payload["results"].append(r)
            try:
                frappe.db.commit()
            except Exception:
                pass

        payload["status"] = "OK"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    # Always run cleanup
    payload["cleanup_log"] = _final_cleanup()
    payload["remaining_in_tracker"] = list(CREATED)

    # Summary tallies
    verdicts = {}
    for r in payload["results"]:
        v = r.get("verdict", "UNKNOWN")
        verdicts[v] = verdicts.get(v, 0) + 1
    payload["verdict_counts"] = verdicts

    out_path = "/tmp/s244_sweep_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_SWEEP_OK status={payload.get('status')} "
                     f"results={len(payload['results'])} verdicts={verdicts}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
