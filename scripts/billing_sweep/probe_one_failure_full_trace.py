#!/usr/bin/env python3
"""Trigger a single PI generation for one failing store; capture FULL traceback.

Bypasses frappe.log_error truncation by intercepting the exception directly
via try/except in this script BEFORE the generator's savepoint catches it.
"""
from __future__ import annotations

import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json
import sys
import traceback
from datetime import datetime

import frappe  # type: ignore

# A store that FAILED at PI generation in the sweep
TARGET_COMPANY = "AYALA FAIRVIEW TERRACES - BEBANG FT INC."
TARGET_ORDER = "BEI-ORD-2026-00983"

BKI_COMPANY = "BEBANG KITCHEN INC."


def main() -> None:
    payload = {"timestamp_utc": datetime.utcnow().isoformat() + "Z"}
    si_name = None
    pi_name = None
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        from hrms.api.bki_store_pi_generator import build_store_pi

        # Create the SI exactly as the sweep did
        si = frappe.new_doc("Sales Invoice")
        si.company = BKI_COMPANY
        si.customer = TARGET_COMPANY
        si.posting_date = "2026-05-11"
        si.set_posting_time = 1
        si.posting_time = "11:30:00"
        si.naming_series = "BKI-SI-.YYYY.-.#####"
        si.debit_to = "Debtors - BKI"
        si.taxes_and_charges = "BKI Output VAT 12% Sales - BKI"
        si.currency = "PHP"
        si.custom_bei_store_order = TARGET_ORDER
        si.bei_legal_entity = BKI_COMPANY
        si.bei_store_label = "AYALA FAIRVIEW TERRACES"
        si.append("items", {"item_code": "PM003", "qty": 1, "rate": 1.00})
        template_taxes = frappe.db.sql(
            """SELECT charge_type, account_head, description, rate,
                      included_in_print_rate, cost_center
               FROM `tabSales Taxes and Charges`
               WHERE parent='BKI Output VAT 12% Sales - BKI' ORDER BY idx""",
            as_dict=True,
        )
        for t in (template_taxes or []):
            si.append("taxes", t)

        si.insert(ignore_permissions=True)
        si_name = si.name
        payload["si_inserted"] = si_name

        # Submit (this fires the generator hook). BUT — we want full traceback.
        # Instead of submit() let's manually walk build_store_pi to capture the
        # exception location and full stack.
        si.docstatus = 1  # mark as submitted for the generator's logic
        # We won't actually call frappe submit which fires all hooks; just call
        # the build directly so we see WHY it fails.

        payload["build_phase"] = {"started_at": datetime.utcnow().isoformat() + "Z"}
        try:
            pi = build_store_pi(si, TARGET_COMPANY)
            payload["build_phase"]["build_ok"] = True
            payload["build_phase"]["pi_dict"] = {
                "company": pi.company,
                "supplier": pi.supplier,
                "currency": pi.currency,
                "conversion_rate": float(pi.conversion_rate or 0),
                "set_warehouse": pi.set_warehouse,
                "credit_to": pi.credit_to,
                "update_stock": pi.update_stock,
                "items_count": len(pi.items),
                "taxes_count": len(pi.taxes),
                "first_item_expense": pi.items[0].expense_account if pi.items else None,
                "first_item_warehouse": pi.items[0].warehouse if pi.items else None,
                "first_item_cost_center": pi.items[0].cost_center if pi.items else None,
            }
            # Now try to insert the PI to capture validation errors
            try:
                pi.insert(ignore_permissions=True)
                pi_name = pi.name
                payload["insert_phase"] = {"insert_ok": True, "pi_name": pi.name}
                # Re-fetch the inserted doc to see what ERPNext actually persisted
                pi_db = frappe.get_doc("Purchase Invoice", pi.name)
                payload["insert_phase"]["after_insert"] = {
                    "expense_account_first_item": pi_db.items[0].expense_account if pi_db.items else None,
                    "warehouse_first_item": pi_db.items[0].warehouse if pi_db.items else None,
                    "cost_center_first_item": pi_db.items[0].cost_center if pi_db.items else None,
                    "credit_to": pi_db.credit_to,
                    "currency": pi_db.currency,
                    "supplier": pi_db.supplier,
                    "company": pi_db.company,
                }
            except Exception as ie:
                payload["insert_phase"] = {
                    "insert_ok": False,
                    "error": str(ie)[:1500],
                    "full_traceback": traceback.format_exc(),
                }
        except Exception as be:
            payload["build_phase"]["build_ok"] = False
            payload["build_phase"]["error"] = str(be)[:1500]
            payload["build_phase"]["full_traceback"] = traceback.format_exc()

        # Also probe warehouse defaults that ERPNext uses to override expense_account
        wh_account = frappe.db.get_value("Warehouse", TARGET_COMPANY, "account")
        payload["warehouse_default_account"] = wh_account

        # Probe Account "1104210 - Inventory-from-Commissary - FT"
        cands = frappe.db.sql(
            """SELECT name, account_number, account_type, root_type, is_group, disabled
               FROM `tabAccount`
               WHERE company=%s AND account_number IN ('1104210','1106210','2103210')""",
            TARGET_COMPANY,
            as_dict=True,
        )
        payload["s238_accounts"] = cands

        payload["status"] = "OK"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    # Cleanup any created docs
    cleanup_log = []
    try:
        if pi_name and frappe.db.exists("Purchase Invoice", pi_name):
            try:
                frappe.delete_doc("Purchase Invoice", pi_name, force=True, ignore_permissions=True)
                cleanup_log.append(f"Deleted PI {pi_name}")
            except Exception as e:
                cleanup_log.append(f"Delete PI {pi_name} failed: {str(e)[:200]}")
        if si_name and frappe.db.exists("Sales Invoice", si_name):
            try:
                doc = frappe.get_doc("Sales Invoice", si_name)
                if doc.docstatus == 1:
                    try:
                        doc.cancel()
                        cleanup_log.append(f"Cancelled SI {si_name}")
                    except Exception:
                        pass
                frappe.delete_doc("Sales Invoice", si_name, force=True, ignore_permissions=True)
                cleanup_log.append(f"Deleted SI {si_name}")
            except Exception as e:
                cleanup_log.append(f"Delete SI {si_name} failed: {str(e)[:200]}")
        frappe.db.commit()
    except Exception as e:
        cleanup_log.append(f"Cleanup wrapper failed: {str(e)[:200]}")
    payload["cleanup_log"] = cleanup_log

    out_path = "/tmp/s244_one_failure.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_ONE_FAILURE_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
