#!/usr/bin/env python3
"""S238 Phase 1 — seed 3 leaf accounts per per-store Company (49 × 3 = 147).

Per v2 audit B4, account_numbers are deterministic for exact-match resolver:
  1104210 Inventory-from-Commissary  -> parent: 'Stock Assets - <ABBR>',     account_type=Stock,   root_type=Asset
  1106210 Input VAT - BKI Inter-Co   -> parent: 'Current Assets - <ABBR>',  account_type=Tax,     root_type=Asset
  2103210 AP-Trade-BKI               -> parent: 'Accounts Payable - <ABBR>', account_type=Payable, root_type=Liability

v2-B5: parent groups discovered via _find_parent_group pattern from
hrms/on_demand/s206_seed_intercompany_accounts.py. All 49 stores must
have the 3 BARE-NAME parent groups (S243 closed the gap on 4 stores;
the other 45 already had them).

v2-B1 (savepoint API): frappe.db.savepoint(name) for entry, raw SQL
'ROLLBACK TO SAVEPOINT name' for rollback. NEVER frappe.db.rollback_to_savepoint
(that API doesn't exist in this Frappe build).

Idempotent (skip if account_number already exists per Company).
Modes: --dry-run (default), --apply.
"""
from __future__ import annotations

import os
for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import json
import re
import sys
import traceback
from datetime import datetime

import frappe  # type: ignore

LEAF_SPEC = [
    # (account_number, account_name, parent_group_pattern, account_type, root_type)
    ("1104210", "Inventory-from-Commissary", "Stock Assets",     "Stock",   "Asset"),
    ("1106210", "Input VAT - BKI Inter-Co",  "Current Assets",   "Tax",     "Asset"),
    ("2103210", "AP-Trade-BKI",              "Accounts Payable", "Payable", "Liability"),
]


def _safe_savepoint_name(company: str) -> str:
    """Sanitize Company name for use in savepoint identifier."""
    safe = re.sub(r"[^A-Za-z0-9_]", "_", company)[:40]
    return f"s238_seed_{safe}"


def _find_parent_group(company: str, name_pattern: str) -> str | None:
    """Lookup canonical pattern from s206_seed_intercompany_accounts.py:82.

    Path 1: existing leaf account whose name starts with pattern -> return parent_account.
    Path 2: group account exactly named pattern (BARE) -> return its docname.
    """
    rows = frappe.db.sql(
        """
        SELECT name, parent_account
        FROM `tabAccount`
        WHERE company=%s AND is_group=0 AND account_name LIKE %s
        LIMIT 1
        """,
        (company, name_pattern + "%"),
    )
    if rows and rows[0][1]:
        return rows[0][1]
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabAccount`
        WHERE company=%s AND is_group=1 AND account_name=%s
        LIMIT 1
        """,
        (company, name_pattern),
    )
    return rows[0][0] if rows else None


def _ensure_leaf_account(
    company: str,
    account_number: str,
    account_name: str,
    parent_account: str,
    account_type: str,
    root_type: str,
) -> tuple[str, str]:
    """Idempotent INSERT for a leaf account. Returns (docname, status).

    status in {created, existed}. Raises on insert failure.
    """
    abbr = frappe.db.get_value("Company", company, "abbr")
    if not abbr:
        raise ValueError(f"Company {company!r} has no abbr")
    expected_docname = f"{account_number} - {account_name} - {abbr}"

    # Idempotency: check by docname OR by account_number+company
    if frappe.db.exists("Account", expected_docname):
        return expected_docname, "existed"
    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": account_number},
        "name",
    )
    if existing:
        return existing, "existed"

    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": f"{account_number} - {account_name}",  # s206 pattern: "<num> - <name>"
        "account_number": account_number,
        "parent_account": parent_account,
        "company": company,
        "is_group": 0,
        "account_type": account_type,
        "root_type": root_type,
        "report_type": "Balance Sheet",
    })
    doc.insert(ignore_permissions=True)
    return doc.name, "created"


def _per_store_companies() -> list[str]:
    """The 49 per-store Companies (excludes BKI parent + holding companies)."""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT c.name
        FROM `tabCompany` c
        WHERE c.name != 'BEBANG KITCHEN INC.'
          AND IFNULL(c.is_group, 0) = 0
          AND EXISTS (
              SELECT 1 FROM `tabWarehouse` w
              WHERE w.company = c.name AND IFNULL(w.disabled, 0) = 0
          )
        ORDER BY c.name
        """,
    )
    return [r[0] for r in rows]


def execute(dry_run: bool = True) -> dict:
    """Loop 49 Companies × 3 leaf specs = 147 inserts. Per-Company savepoint."""
    frappe.set_user("Administrator")

    ledger: dict = {
        "mode": "dry-run" if dry_run else "apply",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stores": {},
        "errors": [],
        "total_created": 0,
        "total_existed": 0,
        "total_errors": 0,
    }

    # v1.1-B2 from S243: also flag for child Companies
    original_root_flag = getattr(frappe.local.flags, "ignore_root_company_validation", False)
    frappe.local.flags.ignore_root_company_validation = True

    try:
        for company in _per_store_companies():
            sp = _safe_savepoint_name(company)
            store_ledger: dict = {"company": company, "result": []}
            try:
                frappe.db.savepoint(sp)
                for acct_num, acct_name, parent_pat, acct_type, root_type in LEAF_SPEC:
                    parent = _find_parent_group(company, parent_pat)
                    if not parent:
                        # All 49 stores should have these post-S243; this is HARD STOP territory
                        store_ledger["result"].append({
                            "account_number": acct_num,
                            "account_name": acct_name,
                            "status": "error",
                            "error": f"parent group {parent_pat!r} not found on {company} (Phase 0-T4 invariant violated)",
                        })
                        ledger["errors"].append({
                            "company": company,
                            "account_number": acct_num,
                            "error": f"parent {parent_pat!r} missing",
                        })
                        ledger["total_errors"] += 1
                        continue
                    docname, status = _ensure_leaf_account(
                        company=company,
                        account_number=acct_num,
                        account_name=acct_name,
                        parent_account=parent,
                        account_type=acct_type,
                        root_type=root_type,
                    )
                    store_ledger["result"].append({
                        "account_number": acct_num,
                        "name": docname,
                        "parent_account": parent,
                        "status": status,
                    })
                    if status == "created":
                        ledger["total_created"] += 1
                    else:
                        ledger["total_existed"] += 1

                if dry_run:
                    # v2-B1: raw SQL ROLLBACK TO SAVEPOINT (frappe.db.rollback_to_savepoint doesn't exist)
                    frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{sp}`")
                else:
                    frappe.db.release_savepoint(sp)
            except Exception as exc:
                try:
                    frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{sp}`")
                except Exception:
                    pass
                frappe.log_error(
                    title=f"S238 Phase 1 seed failed for {company}",
                    message=traceback.format_exc()[:1500],
                )
                store_ledger["result"].append({
                    "status": "error",
                    "error": str(exc)[:300],
                })
                ledger["errors"].append({"company": company, "error": str(exc)[:300]})
                ledger["total_errors"] += 1

            ledger["stores"][company] = store_ledger

        if not dry_run:
            frappe.db.commit()
            ledger["committed"] = True
        else:
            ledger["committed"] = False

    finally:
        frappe.local.flags.ignore_root_company_validation = original_root_flag

    return ledger


def main() -> None:
    dry_run = "--apply" not in sys.argv  # default = dry-run

    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()

    result = execute(dry_run=dry_run)

    out_path = "/tmp/s238_seed_accounts_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    sys.stdout.write(
        f"S238_PHASE1_OK mode={result['mode']} created={result['total_created']} "
        f"existed={result['total_existed']} errors={result['total_errors']} "
        f"path={out_path}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
