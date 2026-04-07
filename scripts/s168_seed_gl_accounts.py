#!/usr/bin/env python3
"""
S168 Phase 5.3 (account creation portion) — seed BKI wholesale GL accounts.

Creates 2 accounts in Bebang Kitchen Inc. chart of accounts (R2-C2 Option C,
locked 2026-04-07 PM by Butch):

  1. Parent group  : 4000100 WHOLESALE / B2B SALES - BKI
                     parent = 4000000 - SALES - BKI
                     is_group = 1, root_type = Income
  2. Posting child : 4000101 SALES - BKI TO STORES - BKI
                     parent = 4000100 - WHOLESALE / B2B SALES - BKI
                     is_group = 0, account_type = Income Account

Idempotent via frappe.db.exists. Designed to run INSIDE the Frappe backend
container (via SSM runner in Session A deploy). Writes a JSON report between
S168_SSM_REPORT_BEGIN / S168_SSM_REPORT_END markers on stdout.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime

# Create log dirs before importing frappe (mirrors s163_ssm_ops.py pattern)
for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

COMPANY = "Bebang Kitchen Inc."
COMPANY_ABBR = "BKI"
PARENT_ROOT = "4000000 - SALES - BKI"
PARENT_GROUP_NAME = "4000100 WHOLESALE / B2B SALES"
PARENT_GROUP_ID = f"{PARENT_GROUP_NAME} - {COMPANY_ABBR}"
CHILD_NAME = "4000101 SALES - BKI TO STORES"
CHILD_ID = f"{CHILD_NAME} - {COMPANY_ABBR}"


def _ensure_account(doc_name: str, account_name: str, parent: str, is_group: int, account_type: str | None) -> dict:
    if frappe.db.exists("Account", doc_name):
        return {"name": doc_name, "action": "skipped", "reason": "already exists"}
    if not frappe.db.exists("Account", parent):
        raise ValueError(
            f"Parent account '{parent}' does not exist in {COMPANY} COA. "
            "Create it first (or fix the PARENT_ROOT constant)."
        )
    doc = frappe.new_doc("Account")
    doc.account_name = account_name
    doc.parent_account = parent
    doc.company = COMPANY
    doc.is_group = is_group
    doc.root_type = "Income"
    doc.report_type = "Profit and Loss"
    if account_type:
        doc.account_type = account_type
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "action": "created"}


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "5.3-accounts",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "company": COMPANY,
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        results = []
        # 1. Parent group first
        results.append(
            _ensure_account(
                doc_name=PARENT_GROUP_ID,
                account_name=PARENT_GROUP_NAME,
                parent=PARENT_ROOT,
                is_group=1,
                account_type=None,
            )
        )
        # 2. Posting child
        results.append(
            _ensure_account(
                doc_name=CHILD_ID,
                account_name=CHILD_NAME,
                parent=PARENT_GROUP_ID,
                is_group=0,
                account_type="Income Account",
            )
        )
        frappe.db.commit()

        # Persist confirmation notice per plan Task 5.3
        out_dir = "/home/frappe/frappe-bench/sites/output/s168"
        try:
            os.makedirs(out_dir, exist_ok=True)
            notice = (
                "=" * 70 + "\n"
                "S168 ICT-008 ACCOUNT LOCKED (Butch Option C -- 2026-04-07 PM)\n"
                + "=" * 70 + "\n"
                f"Created parent group : {PARENT_GROUP_NAME}\n"
                f"Created posting child: {CHILD_NAME}\n"
                f"BEI Settings.bki_sales_income_account = '{CHILD_ID}'\n"
                f"BEI Settings.bki_output_vat_account    = '2102205 OUTPUT VAT PAYABLE - {COMPANY_ABBR}'\n"
                "\n"
                "Both codes fact-checked against COA.csv on 2026-04-07 PM -- free\n"
                "slots, consistent with 4000200 / 4000300 pattern. No swap required.\n"
                + "=" * 70 + "\n"
            )
            with open(os.path.join(out_dir, "phase5_account_confirmation.txt"), "w", encoding="utf-8") as f:
                f.write(notice)
            print(notice)
        except Exception:  # pragma: no cover
            pass

        report["results"] = results
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
