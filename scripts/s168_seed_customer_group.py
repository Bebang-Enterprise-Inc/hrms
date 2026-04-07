#!/usr/bin/env python3
"""
S168 Phase 5.0 -- HARD BLOCKER: create Customer Group 'BKI Store'.

ERPNext requires the Customer Group to exist before any Customer can reference
it via `customer_group`. Code verifier confirmed (2026-04-07) that 'BKI Store'
does NOT exist in repo or production. This script precreates it before
s168_seed_customers.py runs.

Also verifies a default Territory exists; throws with clear Finance instruction
if not. Does NOT auto-create territories (per plan Task 5.0).

Idempotent. Emits JSON report between S168_SSM_REPORT_BEGIN / _END markers.
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
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

GROUP_NAME = "BKI Store"
PARENT_GROUP = "All Customer Groups"
TERRITORY_CANDIDATES = ["Philippines", "All Territories"]


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "5.0-customer-group",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "group": GROUP_NAME,
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        if not frappe.db.exists("Customer Group", PARENT_GROUP):
            raise ValueError(
                f"Parent Customer Group '{PARENT_GROUP}' does not exist. "
                "Frappe bootstrap is broken."
            )

        if frappe.db.exists("Customer Group", GROUP_NAME):
            report["action"] = "skipped"
            report["reason"] = "already exists"
        else:
            cg = frappe.new_doc("Customer Group")
            cg.customer_group_name = GROUP_NAME
            cg.parent_customer_group = PARENT_GROUP
            cg.is_group = 0
            cg.insert(ignore_permissions=True)
            frappe.db.commit()
            report["action"] = "created"

        # Territory pre-flight (do NOT auto-create per plan)
        found_territory = None
        for t in TERRITORY_CANDIDATES:
            if frappe.db.exists("Territory", t):
                found_territory = t
                break
        if not found_territory:
            raise ValueError(
                "No default Territory found (tried: "
                + ", ".join(TERRITORY_CANDIDATES)
                + "). Finance must create a default Territory before running "
                "s168_seed_customers.py. Do NOT auto-create territories."
            )
        report["territory_ok"] = found_territory
        report["ok"] = True
    except Exception:
        report["fatal"] = traceback.format_exc()
        report["ok"] = False
    finally:
        print("S168_SSM_REPORT_BEGIN")
        print(json.dumps(report, indent=2, default=str))
        print("S168_SSM_REPORT_END")
        try:
            frappe.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
    sys.exit(0)
