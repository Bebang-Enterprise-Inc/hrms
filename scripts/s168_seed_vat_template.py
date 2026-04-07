#!/usr/bin/env python3
"""
S168 Phase 5.2 -- seed Sales Taxes and Charges Template 'BKI Output VAT 12% Sales'.

Creates a single-row Sales Taxes and Charges Template for Bebang Kitchen Inc.:
  - name         : BKI Output VAT 12% Sales
  - company      : Bebang Kitchen Inc.
  - charge_type  : On Net Total
  - account_head : 2102205 OUTPUT VAT PAYABLE - BKI  (ICT-009, R2-C1)
  - rate         : 12.0
  - description  : "12% Output VAT (BIR)"

Pre-flight: verifies Output VAT account exists. Idempotent via frappe.db.exists.
Runs inside Frappe backend container via SSM runner. Emits JSON report between
S168_SSM_REPORT_BEGIN / _END markers.
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

COMPANY = "Bebang Kitchen Inc."
TEMPLATE_NAME = "BKI Output VAT 12% Sales"
OUTPUT_VAT_ACCOUNT = "2102205 OUTPUT VAT PAYABLE - BKI"


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "5.2-vat-template",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "company": COMPANY,
        "template": TEMPLATE_NAME,
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        if not frappe.db.exists("Account", OUTPUT_VAT_ACCOUNT):
            raise ValueError(
                f"Output VAT account '{OUTPUT_VAT_ACCOUNT}' does not exist in "
                f"{COMPANY} chart of accounts. Create it before running this script."
            )

        if frappe.db.exists("Sales Taxes and Charges Template", TEMPLATE_NAME):
            report["action"] = "skipped"
            report["reason"] = "template already exists"
        else:
            doc = frappe.new_doc("Sales Taxes and Charges Template")
            doc.title = TEMPLATE_NAME
            doc.company = COMPANY
            doc.append(
                "taxes",
                {
                    "charge_type": "On Net Total",
                    "account_head": OUTPUT_VAT_ACCOUNT,
                    "description": "12% Output VAT (BIR)",
                    "rate": 12.0,
                },
            )
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            report["action"] = "created"
            report["name"] = doc.name

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
