#!/usr/bin/env python3
"""S243 Phase 0-T4 probe — pre-state for 4 BEBANG ENTERPRISE INC. stores.

v1.1-B5 fix: replaces dependency on tmp/s238/* (gitignored, not in worktree)
by regenerating the same evidence inline.

For each of:
  - ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.  (ROA)
  - SM MANILA           - BEBANG ENTERPRISE INC.  (SMM)
  - SM MEGAMALL         - BEBANG ENTERPRISE INC.  (SMMM)
  - SM SOUTHMALL        - BEBANG ENTERPRISE INC.  (SMS)

write to before_state.json:
  - total_accounts, group_accounts, leaf_accounts counts
  - all_group_accounts (full row)
  - all_leaf_accounts (full row)
  - parent_company, abbr from tabCompany
  - billing_customer_exists, billing_customer name
  - warehouse_list
  - BKI SI counts grouped by docstatus + total grand_total
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime

# v1.1-B5: SSM boilerplate inlined — log dirs MUST exist before import frappe
for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

TARGET_COMPANIES = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]


def probe_store(company: str) -> dict:
    """Probe one target store's pre-state."""
    out: dict = {"company": company}

    # Company meta
    co_row = frappe.db.sql(
        """
        SELECT abbr, parent_company, entity_category, default_currency
        FROM `tabCompany`
        WHERE name = %s
        """,
        company,
        as_dict=True,
    )
    if not co_row:
        out["error"] = "Company not found"
        return out
    out["abbr"] = co_row[0]["abbr"]
    out["parent_company"] = co_row[0]["parent_company"]
    out["entity_category"] = co_row[0]["entity_category"]
    out["default_currency"] = co_row[0]["default_currency"]

    # Account counts
    out["total_accounts"] = frappe.db.count("Account", {"company": company})
    out["group_accounts_count"] = frappe.db.count(
        "Account", {"company": company, "is_group": 1}
    )
    out["leaf_accounts_count"] = frappe.db.count(
        "Account", {"company": company, "is_group": 0}
    )

    # All group accounts
    out["all_group_accounts"] = frappe.db.sql(
        """
        SELECT name, account_name, account_number, parent_account, root_type, account_type
        FROM `tabAccount`
        WHERE company = %s AND is_group = 1
        ORDER BY root_type, account_number, account_name
        """,
        company,
        as_dict=True,
    )

    # All leaf accounts (small set since these stores are skeleton — capture them all)
    out["all_leaf_accounts"] = frappe.db.sql(
        """
        SELECT name, account_name, account_number, parent_account, root_type, account_type
        FROM `tabAccount`
        WHERE company = %s AND is_group = 0
        ORDER BY root_type, account_number, account_name
        """,
        company,
        as_dict=True,
    )

    # Billing Customer (canonical: same docname as Company)
    out["billing_customer_exists"] = bool(frappe.db.exists("Customer", company))
    out["billing_customer"] = company if out["billing_customer_exists"] else None

    # Warehouses
    out["warehouse_list"] = frappe.db.sql(
        """
        SELECT name, warehouse_name, is_group, disabled
        FROM `tabWarehouse`
        WHERE company = %s
        ORDER BY name
        """,
        company,
        as_dict=True,
    )

    # BKI SI counts — grouped by docstatus
    si_rows = frappe.db.sql(
        """
        SELECT docstatus, COUNT(*) AS cnt, SUM(grand_total) AS total
        FROM `tabSales Invoice`
        WHERE company = 'BEBANG KITCHEN INC.' AND customer = %s
        GROUP BY docstatus
        """,
        company,
        as_dict=True,
    )
    out["BKI_si_counts"] = {
        int(r["docstatus"]): {
            "count": r["cnt"],
            "total": float(r["total"] or 0),
        }
        for r in si_rows
    }
    out["BKI_si_total_count"] = sum(r["cnt"] for r in si_rows)

    return out


def main() -> None:
    payload: dict = {
        "sprint": "S243",
        "phase": "0-T4",
        "task": "pre-state probe (regenerated; replaces tmp/s238 dependency per v1.1-B5)",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stores": {},
    }

    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        for company in TARGET_COMPANIES:
            payload["stores"][company] = probe_store(company)

        payload["status"] = "OK"
    except Exception as e:
        payload["status"] = "ERROR"
        payload["error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    sys.stdout.write("S243_PHASE0_BEGIN\n")
    sys.stdout.write(json.dumps(payload, indent=2, default=str))
    sys.stdout.write("\nS243_PHASE0_END\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
