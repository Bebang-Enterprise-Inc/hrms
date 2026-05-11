#!/usr/bin/env python3
"""S247 Phase 4a — Pre-deploy cost_center fix for 4 BEI Enterprise stores.

Sets Company.cost_center='Main - <ABBR>' on ROA, SMM, SMMM, SMS. Safe pre-deploy
because the current live PI generator doesn't successfully reach the cost_center
resolver on these 4 stores anyway (savepoint already rolls back per DEFECT A).

Idempotent: skips if cost_center already set. Creates 'Main - <ABBR>' Cost Center
if missing (it should already exist on every Company per ERPNext default).

Writes teardown ledger entry per change for rollback.
"""
from __future__ import annotations

import os
for d in [
    "/home/frappe/logs", "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import json
import sys
from datetime import datetime

import frappe  # type: ignore

TARGETS = [
    ("ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.", "ROA"),
    ("SM MANILA - BEBANG ENTERPRISE INC.", "SMM"),
    ("SM MEGAMALL - BEBANG ENTERPRISE INC.", "SMMM"),
    ("SM SOUTHMALL - BEBANG ENTERPRISE INC.", "SMS"),
]


def main() -> None:
    payload = {
        "sprint": "S247",
        "phase": "4a",
        "purpose": "set Company.cost_center on 4 BEI-Enterprise stores",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "results": [],
        "teardown_ledger": [],
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        for company, abbr in TARGETS:
            r = {"company": company, "abbr": abbr}
            old_cc = frappe.db.get_value("Company", company, "cost_center")
            r["old_cost_center"] = old_cc

            # S247 P4a v2: these 4 stores have a non-canonical CC tree (single leaf,
            # no root group). Pattern: `Bebang Enterprise Inc. - <Store Short> - <ABBR>`.
            # Use that existing leaf CC instead of creating `Main - <ABBR>` (would
            # require restructuring the CC tree). Note canonical mismatch in DEFECTS.md.
            target_cc_name = frappe.db.get_value(
                "Cost Center",
                {"company": company, "is_group": 0, "disabled": 0},
                "name",
                order_by="lft",
            )
            r["target_cost_center_name"] = target_cc_name
            r["target_cost_center_pre_exists"] = bool(target_cc_name)

            if not target_cc_name:
                r["status"] = "ERROR_NO_LEAF_CC"
                payload["results"].append(r)
                continue

            # Set cost_center on Company
            if old_cc == target_cc_name:
                r["status"] = "ALREADY_SET"
            else:
                frappe.db.set_value("Company", company, "cost_center", target_cc_name)
                # Verify
                new_cc = frappe.db.get_value("Company", company, "cost_center")
                r["new_cost_center"] = new_cc
                r["status"] = "SET" if new_cc == target_cc_name else "VERIFY_FAILED"
                # Add to teardown ledger
                payload["teardown_ledger"].append({
                    "doctype": "Company",
                    "name": company,
                    "field": "cost_center",
                    "old_value": old_cc,
                    "new_value": target_cc_name,
                    "action": "REVERT_FIELDS",
                })

            payload["results"].append(r)

        frappe.db.commit()

        # Post-verify
        all_set = all(
            frappe.db.get_value("Company", c, "cost_center")
            for c, _ in TARGETS
        )
        payload["all_4_stores_have_cost_center"] = all_set
        payload["status"] = "OK" if all_set else "PARTIAL"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s247_p4a_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S247_P4A_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
