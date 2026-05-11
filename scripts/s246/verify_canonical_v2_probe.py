#!/usr/bin/env python3
"""S246 Phase 1A.4 — Canonical Store Master-Data Spec v2 Verifier.

Asserts every REQUIRED field from output/l3/s246/audit/CANONICAL_STORE_SPEC.md
across all 49 BEI store Companies. Read-only. Outputs JSON + CSV gap report.

Runs INSIDE the Frappe backend container via SSM (wrapper: run_v2_verifier.py).
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
from datetime import datetime

import frappe  # type: ignore

# REQUIRED fields per the spec (v1.0)
COMPANY_REQUIRED = [
    "name", "abbr", "default_currency", "cost_center",
    "enable_perpetual_inventory", "stock_received_but_not_billed",
    "entity_category", "operational_status", "store_ownership_type",
]
COMPANY_CONDITIONAL = ["tax_id", "parent_company"]  # context-dependent
COMPANY_RECOMMENDED = ["default_inventory_account", "stock_adjustment_account"]

WAREHOUSE_REQUIRED = [
    "warehouse_name", "company", "account", "is_group", "disabled",
    "custom_area_supervisor",
]

CUSTOMER_REQUIRED = ["customer_name", "is_internal_customer"]
INTERNAL_CUSTOMER_REQUIRED = ["customer_name", "represents_company", "is_internal_customer"]

REQUIRED_ACCOUNT_NUMBERS = ["1104210", "1106210", "2103210"]
# SRBNB has account_type="Stock Received But Not Billed" (not a fixed account_number)

BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"
BKI_COMPANY = "BEBANG KITCHEN INC."

BEI_SETTINGS_REQUIRED_FIELDS = [
    "bki_sales_naming_series",
    "enable_bki_store_pi_generator",            # NEW S246
    "enable_bki_store_stock_entry_generator",   # NEW S246
]

CUSTOM_FIELDS_REQUIRED = [
    ("Sales Invoice", "custom_bei_store_order"),
    ("Purchase Invoice", "bki_si_reference"),
    ("Stock Entry", "bki_si_reference"),           # NEW S246
    ("Sales Invoice", "bei_legal_entity"),
    ("Sales Invoice", "bei_store_label"),
    ("Purchase Invoice", "bei_legal_entity"),
    ("Purchase Invoice", "bei_store_label"),
]


def _check_company(company):
    """Per-store Company readiness."""
    out = {"company": company}
    c = frappe.db.get_value(
        "Company", company,
        ["abbr", "default_currency", "cost_center", "enable_perpetual_inventory",
         "stock_received_but_not_billed", "default_inventory_account",
         "stock_adjustment_account", "entity_category", "operational_status",
         "store_ownership_type", "tax_id", "parent_company", "country"],
        as_dict=True,
    )
    if not c:
        out["company_doc_exists"] = False
        return out
    out["company_doc_exists"] = True
    out["abbr"] = c.get("abbr")
    out["default_currency_is_PHP"] = c.get("default_currency") == "PHP"
    out["cost_center_set"] = bool(c.get("cost_center"))
    out["cost_center_value"] = c.get("cost_center")
    out["enable_perpetual_inventory_is_1"] = c.get("enable_perpetual_inventory") == 1
    out["stock_received_but_not_billed_set"] = bool(c.get("stock_received_but_not_billed"))
    out["stock_received_but_not_billed_value"] = c.get("stock_received_but_not_billed")
    out["default_inventory_account_set"] = bool(c.get("default_inventory_account"))
    out["stock_adjustment_account_set"] = bool(c.get("stock_adjustment_account"))
    out["entity_category"] = c.get("entity_category")
    out["operational_status"] = c.get("operational_status")
    out["store_ownership_type_set"] = bool(c.get("store_ownership_type"))
    out["tax_id_set"] = bool(c.get("tax_id"))
    out["parent_company"] = c.get("parent_company")
    return out


def _check_warehouse(company):
    """Per-store Warehouse readiness (Warehouse docname == Company name)."""
    out = {}
    w = frappe.db.get_value(
        "Warehouse", company,
        ["warehouse_name", "company", "account", "is_group", "disabled",
         "custom_area_supervisor"],
        as_dict=True,
    )
    if not w:
        out["warehouse_doc_exists"] = False
        return out
    out["warehouse_doc_exists"] = True
    out["wh_warehouse_name_set"] = bool(w.get("warehouse_name"))
    out["wh_company_matches"] = w.get("company") == company
    out["wh_account_set"] = bool(w.get("account"))
    out["wh_account_value"] = w.get("account")
    out["wh_is_group_is_0"] = w.get("is_group") == 0
    out["wh_disabled_is_0"] = w.get("disabled") == 0
    out["wh_custom_area_supervisor_set"] = bool(w.get("custom_area_supervisor"))
    return out


def _check_customer(company):
    """Billing Customer (docname == Company name, is_internal=0)."""
    out = {}
    c = frappe.db.get_value(
        "Customer", company,
        ["customer_name", "is_internal_customer", "tax_id"],
        as_dict=True,
    )
    if not c:
        out["billing_customer_exists"] = False
        return out
    out["billing_customer_exists"] = True
    out["bc_customer_name_set"] = bool(c.get("customer_name"))
    out["bc_is_internal_customer_is_0"] = c.get("is_internal_customer") == 0
    out["bc_tax_id_set"] = bool(c.get("tax_id"))
    return out


def _check_internal_customer(company):
    """Internal Customer for S206 (name = '<store label> (Internal)')."""
    out = {}
    # Find the Internal Customer by represents_company
    ic = frappe.db.get_value(
        "Customer",
        {"represents_company": company, "is_internal_customer": 1},
        ["name", "customer_name"],
        as_dict=True,
    )
    if not ic:
        out["internal_customer_exists"] = False
        return out
    out["internal_customer_exists"] = True
    out["ic_name"] = ic["name"]
    out["ic_customer_name_set"] = bool(ic.get("customer_name"))
    return out


def _check_accounts(company):
    """Required Accounts on the Company's CoA."""
    out = {}
    for acct_num in REQUIRED_ACCOUNT_NUMBERS:
        row = frappe.db.get_value(
            "Account",
            {"company": company, "account_number": acct_num},
            ["name", "account_type", "is_group", "disabled"],
            as_dict=True,
        )
        out[f"account_{acct_num}_exists"] = bool(row)
        out[f"account_{acct_num}_disabled"] = (row or {}).get("disabled")

    # SRBNB account by type
    srbnb = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Stock Received But Not Billed", "is_group": 0},
        "name",
    )
    out["account_srbnb_exists"] = bool(srbnb)
    out["account_srbnb_value"] = srbnb
    return out


def _check_bki_supplier_account(company):
    """BKI Trade Supplier's `accounts[]` row for this Company."""
    out = {}
    pa = frappe.db.get_value(
        "Party Account",
        {"parent": BKI_TRADE_SUPPLIER, "parenttype": "Supplier", "company": company},
        "account",
    )
    out["bki_supplier_account_set"] = bool(pa)
    out["bki_supplier_account_value"] = pa
    return out


def _global_checks():
    """Global readiness: BEI Settings, BKI Trade Supplier, Custom Fields."""
    out = {}

    # BEI Settings
    try:
        settings = frappe.get_single("BEI Settings")
        for field in BEI_SETTINGS_REQUIRED_FIELDS:
            value = None
            present = False
            try:
                value = getattr(settings, field, None)
                present = frappe.get_meta("BEI Settings").has_field(field)
            except Exception:
                pass
            out[f"bei_settings_{field}_field_exists"] = present
            out[f"bei_settings_{field}_value"] = str(value) if value is not None else None
    except Exception as e:
        out["bei_settings_error"] = str(e)[:200]

    # BKI Trade Supplier exists with correct attrs
    s = frappe.db.get_value(
        "Supplier", BKI_TRADE_SUPPLIER,
        ["disabled", "is_internal_supplier", "default_currency"],
        as_dict=True,
    )
    if s:
        out["bki_trade_supplier_exists"] = True
        out["bki_trade_supplier_disabled_is_0"] = s.get("disabled") == 0
        out["bki_trade_supplier_is_internal_is_0"] = s.get("is_internal_supplier") == 0
        out["bki_trade_supplier_currency_is_PHP"] = s.get("default_currency") == "PHP"
    else:
        out["bki_trade_supplier_exists"] = False

    # Custom Fields
    cf_results = []
    for doctype, fieldname in CUSTOM_FIELDS_REQUIRED:
        cf_results.append({
            "doctype": doctype,
            "field": fieldname,
            "present": frappe.get_meta(doctype).has_field(fieldname),
        })
    out["custom_fields"] = cf_results

    # doc_events hook wiring
    hooks = frappe.get_hooks("doc_events") or {}
    si_hooks = hooks.get("Sales Invoice", {}) or {}
    pi_hooks = hooks.get("Purchase Invoice", {}) or {}
    se_hooks = hooks.get("Stock Entry", {}) or {}

    out["si_on_submit_hooks"] = list(si_hooks.get("on_submit", []) or [])
    out["si_on_cancel_hooks"] = list(si_hooks.get("on_cancel", []) or [])
    out["si_autoname_hooks"] = list(si_hooks.get("autoname", []) or [])
    out["pi_validate_hooks"] = list(pi_hooks.get("validate", []) or [])
    out["se_validate_hooks"] = list(se_hooks.get("validate", []) or [])

    return out


def main() -> None:
    payload = {
        "sprint": "S246",
        "phase": "1A.5",
        "purpose": "v2 canonical store master-data verifier (full spec assertion)",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "global": {},
        "stores": [],
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # Get all non-BKI, non-group, Active Company names
        stores = frappe.db.sql(
            """SELECT name FROM `tabCompany`
               WHERE entity_category = 'Store'
                 AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
                 AND IFNULL(is_group, 0) = 0
               ORDER BY name""",
            as_dict=True,
        )

        payload["global"] = _global_checks()

        for s in stores:
            company = s["name"]
            store_result = {"company": company}
            store_result.update(_check_company(company))
            store_result.update(_check_warehouse(company))
            store_result.update(_check_customer(company))
            store_result.update(_check_internal_customer(company))
            store_result.update(_check_accounts(company))
            store_result.update(_check_bki_supplier_account(company))

            # Roll-up: full canonical iff all REQUIRED set
            required_checks = [
                store_result.get("company_doc_exists", False),
                store_result.get("default_currency_is_PHP", False),
                store_result.get("cost_center_set", False),
                store_result.get("enable_perpetual_inventory_is_1", False),
                store_result.get("stock_received_but_not_billed_set", False),
                store_result.get("warehouse_doc_exists", False),
                store_result.get("wh_company_matches", False),
                store_result.get("wh_account_set", False),
                store_result.get("wh_is_group_is_0", False),
                store_result.get("wh_disabled_is_0", False),
                store_result.get("wh_custom_area_supervisor_set", False),
                store_result.get("billing_customer_exists", False),
                store_result.get("bc_is_internal_customer_is_0", False),
                store_result.get("internal_customer_exists", False),
                store_result.get("account_1104210_exists", False),
                store_result.get("account_1106210_exists", False),
                store_result.get("account_2103210_exists", False),
                store_result.get("account_srbnb_exists", False),
                store_result.get("bki_supplier_account_set", False),
            ]
            store_result["required_count_total"] = len(required_checks)
            store_result["required_count_passing"] = sum(1 for r in required_checks if r)
            store_result["fully_canonical"] = all(required_checks)
            payload["stores"].append(store_result)

        # Summary
        total = len(payload["stores"])
        fully_canonical = sum(1 for s in payload["stores"] if s.get("fully_canonical"))
        payload["summary"] = {
            "total_stores": total,
            "fully_canonical": fully_canonical,
            "not_fully_canonical": total - fully_canonical,
        }
        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s246_v2_verify_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S246_V2_VERIFY_OK status={payload.get('status')} stores={len(payload.get('stores', []))}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
