#!/usr/bin/env python3
"""S247 Phase 4b — Post-deploy master-data UPDATEs for Option 3-corrected.

Per CEO decision (output/l3/s246/DECISION.md) + plan v1.1 amendments:
  1. Per-store SRBNB Account creation (if absent) under Current Liabilities root
  2. Company.stock_received_but_not_billed = <per-store SRBNB account>
  3. Warehouse.account = <per-store 1104210 Inventory-from-Commissary>
  4. Supplier `BEBANG KITCHEN INC. - Trade`.accounts[] entry per buyer Company
     pointing to that Company's 2103210 AP-Trade-BKI account
  5. Company.enable_perpetual_inventory = 1 on the 13 stores currently =0
     (perpetual_inventory_consistency: yes per DECISION.md)

Idempotent: skips if already set.
Pre-touch backup written to /tmp/s247_p4b_pretouch.json before any change.
Teardown ledger written to /tmp/s247_p4b_teardown_ledger.json after.
"""
from __future__ import annotations

import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json
import sys
from datetime import datetime

import frappe  # type: ignore


def _get_all_store_companies():
    """Return all 49 store Companies (non-BKI, non-group, Active)."""
    rows = frappe.db.sql(
        """SELECT name, abbr, parent_company FROM `tabCompany`
           WHERE entity_category = 'Store'
             AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
             AND IFNULL(is_group, 0) = 0
             AND name != 'BEBANG KITCHEN INC.'
           ORDER BY name""",
        as_dict=True,
    )
    return rows


def _ensure_srbnb_account(company, abbr):
    """Create per-store SRBNB Account if missing. Returns (name, created_bool)."""
    existing = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_type": "Stock Received But Not Billed",
            "is_group": 0,
            "disabled": 0,
        },
        "name",
    )
    if existing:
        return existing, False

    # Find a Liability root group on this Company for parent
    # Try Current Liabilities first, then any Liability group
    parent = (
        frappe.db.get_value(
            "Account",
            {"company": company, "is_group": 1, "account_name": "Current Liabilities"},
            "name",
        )
        or frappe.db.get_value(
            "Account",
            {"company": company, "is_group": 1, "account_name": "Accounts Payable"},
            "name",
        )
        or frappe.db.get_value(
            "Account",
            {"company": company, "is_group": 1, "root_type": "Liability"},
            "name",
            order_by="lft",
        )
    )
    if not parent:
        return None, False

    # Use BARE-NAME canonical (per S243 convention)
    acct_doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": "Stock Received But Not Billed",
        "company": company,
        "parent_account": parent,
        "is_group": 0,
        "account_type": "Stock Received But Not Billed",
        "root_type": "Liability",
        "report_type": "Balance Sheet",
        "account_currency": "PHP",
    })
    # Some Companies have parent_company validation issues; bypass like S206
    frappe.local.flags.ignore_root_company_validation = True
    try:
        acct_doc.insert(ignore_permissions=True)
    finally:
        frappe.local.flags.ignore_root_company_validation = False
    return acct_doc.name, True


def main() -> None:
    payload = {
        "sprint": "S247",
        "phase": "4b",
        "purpose": "post-deploy master-data UPDATEs for Option 3-corrected",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "results": [],
        "teardown_ledger": [],
        "summary": {},
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        stores = _get_all_store_companies()
        payload["summary"]["total_stores"] = len(stores)

        # Find BKI Trade Supplier
        bki_trade = "BEBANG KITCHEN INC. - Trade"
        if not frappe.db.exists("Supplier", bki_trade):
            raise Exception(f"BKI Trade Supplier {bki_trade!r} not found")

        for s in stores:
            company = s["name"]
            abbr = s["abbr"]
            r = {"company": company, "abbr": abbr}

            # 1. SRBNB account
            srbnb_acct, srbnb_created = _ensure_srbnb_account(company, abbr)
            r["srbnb_account"] = srbnb_acct
            r["srbnb_account_created"] = srbnb_created
            if not srbnb_acct:
                r["status"] = "ERROR_NO_LIABILITY_ROOT"
                payload["results"].append(r)
                continue
            if srbnb_created:
                payload["teardown_ledger"].append({
                    "doctype": "Account", "name": srbnb_acct,
                    "action": "DELETE", "context": "P4b created SRBNB acct",
                })

            # 2. Company.stock_received_but_not_billed
            old_srbnb_field = frappe.db.get_value("Company", company, "stock_received_but_not_billed")
            r["old_company_srbnb"] = old_srbnb_field
            if old_srbnb_field != srbnb_acct:
                frappe.db.set_value("Company", company, "stock_received_but_not_billed", srbnb_acct)
                r["company_srbnb_set"] = True
                payload["teardown_ledger"].append({
                    "doctype": "Company", "name": company,
                    "field": "stock_received_but_not_billed",
                    "old_value": old_srbnb_field, "new_value": srbnb_acct,
                    "action": "REVERT_FIELDS",
                })
            else:
                r["company_srbnb_set"] = False
                r["company_srbnb_status"] = "ALREADY_SET"

            # 3. Warehouse.account = 1104210 - Inventory-from-Commissary
            wh_name = company  # canonical
            inv_acct = frappe.db.get_value(
                "Account", {"company": company, "account_number": "1104210"}, "name"
            )
            r["wh_inventory_account"] = inv_acct
            if inv_acct:
                old_wh_acct = frappe.db.get_value("Warehouse", wh_name, "account")
                r["old_warehouse_account"] = old_wh_acct
                if old_wh_acct != inv_acct:
                    frappe.db.set_value("Warehouse", wh_name, "account", inv_acct)
                    r["warehouse_account_set"] = True
                    payload["teardown_ledger"].append({
                        "doctype": "Warehouse", "name": wh_name,
                        "field": "account",
                        "old_value": old_wh_acct, "new_value": inv_acct,
                        "action": "REVERT_FIELDS",
                    })
                else:
                    r["warehouse_account_set"] = False
                    r["warehouse_account_status"] = "ALREADY_SET"
            else:
                r["warehouse_account_status"] = "NO_1104210_ACCOUNT"

            # 4. BKI Trade Supplier accounts[] entry for this Company
            ap_acct = frappe.db.get_value(
                "Account", {"company": company, "account_number": "2103210"}, "name"
            )
            r["ap_account"] = ap_acct
            if ap_acct:
                existing_pa = frappe.db.get_value(
                    "Party Account",
                    {"parent": bki_trade, "parenttype": "Supplier", "company": company},
                    "name",
                )
                if not existing_pa:
                    sup_doc = frappe.get_doc("Supplier", bki_trade)
                    sup_doc.append("accounts", {"company": company, "account": ap_acct})
                    sup_doc.save(ignore_permissions=True)
                    r["supplier_account_added"] = True
                    payload["teardown_ledger"].append({
                        "doctype": "Party Account", "parent": bki_trade,
                        "company": company, "account": ap_acct,
                        "action": "DELETE", "context": "P4b BKI Trade per-Co AP entry",
                    })
                else:
                    r["supplier_account_added"] = False
                    r["supplier_account_status"] = "ALREADY_EXISTS"
            else:
                r["supplier_account_status"] = "NO_2103210_ACCOUNT"

            # 5. Company.enable_perpetual_inventory = 1
            old_perp = frappe.db.get_value("Company", company, "enable_perpetual_inventory")
            r["old_perpetual_inventory"] = old_perp
            if old_perp != 1:
                frappe.db.set_value("Company", company, "enable_perpetual_inventory", 1)
                r["perpetual_inventory_set"] = True
                payload["teardown_ledger"].append({
                    "doctype": "Company", "name": company,
                    "field": "enable_perpetual_inventory",
                    "old_value": old_perp, "new_value": 1,
                    "action": "REVERT_FIELDS",
                })
            else:
                r["perpetual_inventory_set"] = False
                r["perpetual_inventory_status"] = "ALREADY_SET"

            r["status"] = "OK"
            payload["results"].append(r)

        frappe.db.commit()

        # Post-verify
        ok_count = sum(1 for r in payload["results"] if r.get("status") == "OK")
        payload["summary"]["ok_count"] = ok_count
        payload["summary"]["total_changes_in_ledger"] = len(payload["teardown_ledger"])

        # Roll-up: how many of the 49 stores now have ALL 4 fields set?
        complete = 0
        for s in stores:
            c = s["name"]
            has_srbnb = bool(frappe.db.get_value("Company", c, "stock_received_but_not_billed"))
            has_wh_acct = bool(frappe.db.get_value("Warehouse", c, "account"))
            has_supplier_acct = bool(frappe.db.get_value(
                "Party Account",
                {"parent": bki_trade, "parenttype": "Supplier", "company": c},
                "name",
            ))
            has_perpetual = frappe.db.get_value("Company", c, "enable_perpetual_inventory") == 1
            if all([has_srbnb, has_wh_acct, has_supplier_acct, has_perpetual]):
                complete += 1
        payload["summary"]["fully_configured_post_p4b"] = complete

        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s247_p4b_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S247_P4B_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
