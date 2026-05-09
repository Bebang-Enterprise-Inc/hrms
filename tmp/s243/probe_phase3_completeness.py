#!/usr/bin/env python3
"""S243 Phase 3-T3 — verify CoA completeness across all 49 per-store Companies.

Replicates S238's _find_parent_group_for pattern. Each store must resolve
non-NULL parent for {Stock Assets, Accounts Payable, Current Assets}.

Output: coa_complete_count.json
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


def _find_parent_group_for(company: str, name_pattern: str) -> str | None:
    """Replicates S238's lookup pattern.

    Path 1: leaf account whose name starts with pattern -> return parent_account.
    Path 2: group account whose account_name == pattern (BARE) -> return its name.
    """
    # Path 1: existing leaf under target group
    rows = frappe.db.sql(
        """
        SELECT name, parent_account FROM `tabAccount`
        WHERE company=%s AND is_group=0 AND account_name LIKE %s
        LIMIT 1
        """,
        (company, name_pattern + "%"),
    )
    if rows and rows[0][1]:
        return rows[0][1]

    # Path 2: group account exactly named pattern (BARE)
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company=%s AND is_group=1 AND account_name=%s
        LIMIT 1
        """,
        (company, name_pattern),
    )
    if rows:
        return rows[0][0]

    return None


def main() -> None:
    payload: dict = {
        "sprint": "S243",
        "phase": "3-T3",
        "task": "CoA completeness verify across all 49 stores",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # All non-group, non-disabled per-store Companies (49)
        companies = frappe.db.sql(
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

        per_store: dict = {}
        complete_count = 0
        incomplete: list = []
        for co in companies:
            company = co["name"]
            sa = _find_parent_group_for(company, "Stock Assets")
            ap = _find_parent_group_for(company, "Accounts Payable")
            ca = _find_parent_group_for(company, "Current Assets")
            per_store[company] = {
                "abbr": co["abbr"],
                "stock_assets_parent": sa,
                "ap_parent": ap,
                "current_assets_parent": ca,
            }
            if sa and ap and ca:
                complete_count += 1
            else:
                incomplete.append({
                    "company": company,
                    "missing": [
                        k for k, v in (
                            ("stock_assets_parent", sa),
                            ("ap_parent", ap),
                            ("current_assets_parent", ca),
                        ) if not v
                    ],
                })

        payload["checked_stores"] = len(companies)
        payload["complete_stores"] = complete_count
        payload["incomplete_stores"] = incomplete
        payload["per_store_resolution"] = per_store
        payload["status"] = "OK"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s243_phase3_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    sys.stdout.write(
        f"S243_PHASE3_OK status={payload.get('status')} "
        f"complete={payload.get('complete_stores')}/{payload.get('checked_stores')} "
        f"incomplete={len(payload.get('incomplete_stores', []))} path={out_path}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
