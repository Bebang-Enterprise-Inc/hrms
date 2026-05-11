#!/usr/bin/env python3
"""Billing sweep probe — verify BKI→Store PI generator preconditions per store.

Read-only. No data created. Reports per-Company readiness across all stores
that could potentially be a buyer (Customer.name == Company.name canonical match).

Output is bracketed with S244_PROBE_BEGIN / S244_PROBE_END markers so the
SSM wrapper can extract the JSON cleanly.
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

BKI_COMPANY = "BEBANG KITCHEN INC."
BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"

# Account numbers seeded by S238 PI generator
ACCT_NUMBERS = ("1104210", "1106210", "2103210")

# Custom Fields required (global)
REQUIRED_CUSTOM_FIELDS = [
    ("Sales Invoice", "custom_bei_store_order"),
    ("Purchase Invoice", "custom_bei_store_order"),
    ("Purchase Invoice", "custom_bki_paired_si"),
    ("Purchase Invoice", "bki_si_reference"),
]


def _global_state():
    out = {}

    # BEI Settings flags
    settings = frappe.get_single("BEI Settings")
    out["enable_bki_store_pi_generator"] = bool(
        getattr(settings, "enable_bki_store_pi_generator", 0)
    )
    out["bki_sales_naming_series"] = (
        getattr(settings, "bki_sales_naming_series", "") or ""
    )

    # BKI master
    out["bki_company_exists"] = bool(frappe.db.exists("Company", BKI_COMPANY))
    out["bki_trade_supplier_exists"] = bool(
        frappe.db.exists("Supplier", BKI_TRADE_SUPPLIER)
    )
    if out["bki_trade_supplier_exists"]:
        supp = frappe.db.get_value(
            "Supplier",
            BKI_TRADE_SUPPLIER,
            ["disabled", "is_internal_supplier", "supplier_group", "default_currency"],
            as_dict=True,
        )
        out["bki_trade_supplier_attrs"] = supp

    # Custom Fields
    cf_status = []
    for doctype, fieldname in REQUIRED_CUSTOM_FIELDS:
        present = frappe.get_meta(doctype).has_field(fieldname)
        cf_status.append({"doctype": doctype, "field": fieldname, "present": present})
    out["custom_fields"] = cf_status

    # SI naming hook autoname function registered?
    hooks = frappe.get_hooks("doc_events") or {}
    si_hooks = (hooks.get("Sales Invoice", {}) or {}).get("autoname", []) or []
    pi_hooks = (hooks.get("Purchase Invoice", {}) or {}).get("validate", []) or []
    si_submit_hooks = (hooks.get("Sales Invoice", {}) or {}).get("on_submit", []) or []
    si_cancel_hooks = (hooks.get("Sales Invoice", {}) or {}).get("on_cancel", []) or []
    out["si_autoname_hooks"] = list(si_hooks)
    out["si_on_submit_hooks"] = list(si_submit_hooks)
    out["si_on_cancel_hooks"] = list(si_cancel_hooks)
    out["pi_validate_hooks"] = list(pi_hooks)

    return out


def _candidate_companies():
    """Find all non-BKI, non-group, non-disabled Companies that have a matching Customer name.

    These are the buyer candidates the PI generator will fire for.
    """
    rows = frappe.db.sql(
        """SELECT c.name           AS company,
                  c.abbr           AS abbr,
                  c.default_currency AS currency,
                  c.cost_center    AS cost_center,
                  c.parent_company AS parent_company,
                  IFNULL(c.is_group, 0) AS is_group
           FROM `tabCompany` c
           WHERE c.name != %s
             AND IFNULL(c.is_group, 0) = 0
           ORDER BY c.name""",
        BKI_COMPANY,
        as_dict=True,
    )
    return rows


def _check_one_store(company):
    """Per-store probe: returns dict of all preconditions."""
    name = company["company"]
    out = {
        "company": name,
        "abbr": company.get("abbr"),
        "default_currency": company.get("currency"),
        "default_currency_is_php": company.get("currency") == "PHP",
        "cost_center": company.get("cost_center"),
        "cost_center_set": bool(company.get("cost_center")),
        "parent_company": company.get("parent_company"),
    }

    # Customer record with same name as Company?
    out["customer_exists_with_same_name"] = bool(frappe.db.exists("Customer", name))

    # Warehouse record with same name as Company?
    out["warehouse_exists_with_same_name"] = bool(frappe.db.exists("Warehouse", name))

    # Required accounts present on this Company?
    acct_status = {}
    for acct_num in ACCT_NUMBERS:
        row = frappe.db.get_value(
            "Account",
            {"company": name, "account_number": acct_num},
            ["name", "disabled", "is_group", "root_type", "account_currency"],
            as_dict=True,
        )
        acct_status[acct_num] = row or {"missing": True}
    out["accounts"] = acct_status
    out["all_accounts_present"] = all(
        not v.get("missing") for v in acct_status.values()
    )

    # Does BKI TRADE Supplier have a credit_to entry for this Company?
    bki_supplier_acct = frappe.db.get_value(
        "Party Account",
        {
            "parent": BKI_TRADE_SUPPLIER,
            "parenttype": "Supplier",
            "company": name,
        },
        ["account"],
    )
    out["bki_supplier_account_set"] = bool(bki_supplier_acct)
    out["bki_supplier_account_value"] = bki_supplier_acct

    # Roll-up readiness flag
    out["ready_for_pi_generation"] = bool(
        out["customer_exists_with_same_name"]
        and out["warehouse_exists_with_same_name"]
        and out["default_currency_is_php"]
        and out["cost_center_set"]
        and out["all_accounts_present"]
    )
    return out


def _historical_si_stats():
    """Count test SIs created during S238 build that are still on the system."""
    out = {}
    out["bki_si_total"] = frappe.db.count(
        "Sales Invoice", {"company": BKI_COMPANY}
    )
    out["bki_si_draft"] = frappe.db.count(
        "Sales Invoice", {"company": BKI_COMPANY, "docstatus": 0}
    )
    out["bki_si_submitted"] = frappe.db.count(
        "Sales Invoice", {"company": BKI_COMPANY, "docstatus": 1}
    )
    out["bki_si_cancelled"] = frappe.db.count(
        "Sales Invoice", {"company": BKI_COMPANY, "docstatus": 2}
    )
    return out


def _find_seed_data():
    """Find an item code that can be used as the test SI line item.

    Prefers a non-stock item to avoid SLE issues, or any item with positive stock.
    """
    item = frappe.db.get_value(
        "Item",
        {"item_code": "PM003", "disabled": 0},
        ["item_code", "item_name", "is_stock_item"],
        as_dict=True,
    )
    return {"pm003": item}


def main() -> None:
    payload = {
        "sprint": "billing-sweep-2026-05-11",
        "purpose": "BKI->Store PI generator per-store readiness",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "global": {},
        "stores": [],
        "history": {},
        "seed_data": {},
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        payload["global"] = _global_state()
        payload["history"] = _historical_si_stats()
        payload["seed_data"] = _find_seed_data()

        for company in _candidate_companies():
            payload["stores"].append(_check_one_store(company))

        # Summary tallies
        all_stores = payload["stores"]
        ready = [s for s in all_stores if s["ready_for_pi_generation"]]
        payload["summary"] = {
            "total_candidate_buyer_companies": len(all_stores),
            "ready_for_pi_generation": len(ready),
            "missing_customer": [
                s["company"] for s in all_stores
                if not s["customer_exists_with_same_name"]
            ],
            "missing_warehouse": [
                s["company"] for s in all_stores
                if not s["warehouse_exists_with_same_name"]
            ],
            "non_php_currency": [
                s["company"] for s in all_stores
                if not s["default_currency_is_php"]
            ],
            "missing_cost_center": [
                s["company"] for s in all_stores
                if not s["cost_center_set"]
            ],
            "missing_any_acct": [
                s["company"] for s in all_stores
                if not s["all_accounts_present"]
            ],
            "missing_bki_supplier_acct": [
                s["company"] for s in all_stores
                if not s["bki_supplier_account_set"]
            ],
        }
        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s244_probe_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_PROBE_OK path={out_path} status={payload.get('status')} stores={len(payload.get('stores', []))}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
