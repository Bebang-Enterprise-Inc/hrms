#!/usr/bin/env python3
"""
S238 Phase 0 probe (T0 HARD STOP + T4 full state).

Captures:
- T0 HARD STOP: BEI Settings.bki_sales_naming_series (must be non-empty)
- T4: bki_si_total, bki_si_naming_series sample, existing PI count, supplier checks,
      custom field check, toggle check, bki_sales_income_account value,
      per_store_coa_parent_groups (49 stores × 3 parent group keys)

Emits JSON between S238_PROBE_BEGIN / S238_PROBE_END markers.
Read-only; no mutations.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime

for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore


def _find_parent_group_for(company: str, account_name_pattern: str) -> str | None:
    """Find parent group account for a per-store Company by matching leaf account naming.

    Mirrors s206_seed_intercompany_accounts._find_parent_group(): look up an existing
    leaf account whose name starts with the given pattern in the per-store Company,
    and return its parent_account.
    """
    rows = frappe.db.sql(
        """
        SELECT name, parent_account
        FROM `tabAccount`
        WHERE company=%s
          AND is_group=0
          AND account_name LIKE %s
        LIMIT 1
        """,
        (company, account_name_pattern + "%"),
    )
    if rows:
        return rows[0][1]
    # Fallback: try parent group itself
    grp = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company=%s AND is_group=1 AND account_name=%s
        LIMIT 1
        """,
        (company, account_name_pattern),
    )
    return grp[0][0] if grp else None


def main() -> None:
    out: dict = {
        "sprint": "S238",
        "phase": "0",
        "task": "T0+T4 probe",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # --- T0 HARD STOP: bki_sales_naming_series ---
        settings = frappe.get_single("BEI Settings")
        meta = frappe.get_meta("BEI Settings")

        out["bki_sales_naming_series"] = (settings.get("bki_sales_naming_series") or "").strip() or None
        out["bki_sales_income_account"] = settings.get("bki_sales_income_account") or None
        out["bki_sales_vat_template"] = settings.get("bki_sales_vat_template") or None
        out["bki_output_vat_account"] = settings.get("bki_output_vat_account") or None
        out["bki_default_incoterm"] = settings.get("bki_default_incoterm") or None
        out["bki_markup_jv_percent"] = settings.get("bki_markup_jv_percent")
        out["bki_markup_managed_franchise_percent"] = settings.get("bki_markup_managed_franchise_percent")
        out["bki_markup_full_franchise_percent"] = settings.get("bki_markup_full_franchise_percent")

        # --- T4: BKI SI counts ---
        si_counts = frappe.db.sql(
            """
            SELECT docstatus, COUNT(*) AS cnt
            FROM `tabSales Invoice`
            WHERE company = 'BEBANG KITCHEN INC.'
            GROUP BY docstatus
            """,
            as_dict=True,
        )
        out["bki_si_by_docstatus"] = {r["docstatus"]: r["cnt"] for r in si_counts}
        out["bki_si_total"] = sum(r["cnt"] for r in si_counts)

        # Latest 5 BKI SI naming series
        latest_si = frappe.db.sql(
            """
            SELECT name, naming_series, posting_date, customer, grand_total, docstatus
            FROM `tabSales Invoice`
            WHERE company = 'BEBANG KITCHEN INC.'
            ORDER BY creation DESC
            LIMIT 5
            """,
            as_dict=True,
        )
        out["latest_bki_si_sample"] = [
            {
                "name": r["name"],
                "naming_series": r["naming_series"],
                "posting_date": str(r["posting_date"]) if r["posting_date"] else None,
                "customer": r["customer"],
                "grand_total": float(r["grand_total"] or 0),
                "docstatus": r["docstatus"],
            }
            for r in latest_si
        ]

        # PI count where supplier is BKI variant + company is per-store (expected: 0)
        existing_store_pi = frappe.db.sql(
            """
            SELECT COUNT(*) AS cnt
            FROM `tabPurchase Invoice` pi
            WHERE pi.supplier LIKE 'BEBANG KITCHEN%'
              AND pi.company != 'BEBANG KITCHEN INC.'
            """,
            as_dict=True,
        )
        out["existing_store_bki_pi_count"] = existing_store_pi[0]["cnt"] if existing_store_pi else 0

        # Existing Suppliers matching BEBANG KITCHEN%
        bki_suppliers = frappe.db.sql(
            """
            SELECT name, supplier_group, is_internal_supplier, represents_company
            FROM `tabSupplier`
            WHERE name LIKE 'BEBANG KITCHEN%'
            """,
            as_dict=True,
        )
        out["bki_suppliers_existing"] = [dict(s) for s in bki_suppliers]
        out["existing_bki_supplier_count"] = len(bki_suppliers)
        out["bki_trade_supplier_exists"] = any(
            "trade" in (s["name"] or "").lower() and not (s.get("is_internal_supplier") or 0)
            for s in bki_suppliers
        )

        # Custom Field bki_si_reference on Purchase Invoice (expected: false)
        cf = frappe.db.exists(
            "Custom Field",
            {"dt": "Purchase Invoice", "fieldname": "bki_si_reference"},
        )
        out["custom_field_bki_si_reference_exists"] = bool(cf)
        out["custom_field_exists"] = bool(cf)  # alias for plan's MUST_CONTAIN

        # enable_bki_store_pi_generator (Custom Field on BEI Settings — expected: false)
        toggle_cf = frappe.db.exists(
            "Custom Field",
            {"dt": "BEI Settings", "fieldname": "enable_bki_store_pi_generator"},
        )
        out["toggle_field_exists"] = bool(toggle_cf)
        if toggle_cf:
            out["enable_bki_store_pi_generator_value"] = bool(
                settings.get("enable_bki_store_pi_generator") or 0
            )

        # bei_legal_entity / bei_store_label fields on Purchase Invoice (S192/S203)
        pi_meta = frappe.get_meta("Purchase Invoice")
        out["pi_has_field_bei_legal_entity"] = bool(pi_meta.has_field("bei_legal_entity"))
        out["pi_has_field_bei_store_label"] = bool(pi_meta.has_field("bei_store_label"))

        # --- per-store CoA parent groups for 49 stores ---
        # Discover per-store Companies (those with at least one canonical Warehouse).
        # tabCompany has no `disabled` column on this build; use is_group=0 + warehouse filter.
        store_companies = frappe.db.sql(
            """
            SELECT DISTINCT c.name, c.abbr
            FROM `tabCompany` c
            WHERE c.name != 'BEBANG KITCHEN INC.'
              AND IFNULL(c.is_group, 0) = 0
              AND EXISTS (
                  SELECT 1 FROM `tabWarehouse` w
                  WHERE w.company = c.name AND IFNULL(w.disabled, 0) = 0
              )
            ORDER BY c.name
            """,
            as_dict=True,
        )
        out["per_store_company_count"] = len(store_companies)

        coa_survey: dict = {}
        for sc in store_companies:
            company = sc["name"]
            abbr = sc["abbr"]
            # Stock Assets parent (Inventory-from-Commissary leaf goes under)
            stock_assets = _find_parent_group_for(company, "Stock Assets")
            # Liability parent (Accounts Payable preferred, else Current Liabilities)
            ap_parent = _find_parent_group_for(company, "Accounts Payable")
            if not ap_parent:
                ap_parent = _find_parent_group_for(company, "Current Liabilities")
            # Current Assets parent (Input VAT - BKI Inter-Co)
            current_assets = _find_parent_group_for(company, "Current Assets")
            coa_survey[company] = {
                "abbr": abbr,
                "stock_assets_parent": stock_assets,
                "ap_parent": ap_parent,
                "current_assets_parent": current_assets,
            }
        out["per_store_coa_parent_groups"] = coa_survey
        out["coa_survey_complete_count"] = sum(
            1 for v in coa_survey.values()
            if v["stock_assets_parent"] and v["ap_parent"] and v["current_assets_parent"]
        )

        # P10-D04 server script presence (CRIT-1 context)
        p10d04 = frappe.db.exists(
            "Server Script",
            {"reference_doctype": "Purchase Invoice", "name": ["like", "%legal_entity%"]},
        )
        out["p10_d04_server_script_exists"] = bool(p10d04)

        out["status"] = "OK"

    except Exception as e:
        out["status"] = "ERROR"
        out["error"] = str(e)
        out["traceback"] = traceback.format_exc()

    sys.stdout.write("S238_PROBE_BEGIN\n")
    sys.stdout.write(json.dumps(out, indent=2, default=str))
    sys.stdout.write("\nS238_PROBE_END\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
