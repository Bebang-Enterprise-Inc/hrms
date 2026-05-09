#!/usr/bin/env python3
"""S238 Phase 2-T1 — create 'BEBANG KITCHEN INC. - Trade' Supplier (NOT internal).

Distinct from existing 'Bebang Kitchen Inc.' Internal Supplier (S206).
This Trade Supplier is what BKI's per-store PIs will reference.

- name = 'BEBANG KITCHEN INC. - Trade'
- supplier_name = 'BEBANG KITCHEN INC.' (display name on PI print)
- is_internal_supplier = 0
- represents_company = NULL
- tax_id = BKI's TIN (from BKI Customer or BKI Company)
- Add 49 entries to companies child table (Allowed To Transact With)

Idempotent. Modes: --dry-run (default), --apply.
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
import sys
import traceback
from datetime import datetime

import frappe  # type: ignore

SUPPLIER_NAME = "BEBANG KITCHEN INC. - Trade"
# Frappe Supplier autoname is "By Field" supplier_name, and MySQL primary key
# collation is case-insensitive — using "BEBANG KITCHEN INC." collides with
# existing "Bebang Kitchen Inc." (S206 internal Supplier). Use the full unique
# Trade name so Frappe's autoname produces docname="BEBANG KITCHEN INC. - Trade".
SUPPLIER_DISPLAY = "BEBANG KITCHEN INC. - Trade"
BKI_COMPANY = "BEBANG KITCHEN INC."
SAVEPOINT = "s238_seed_supplier"


def _resolve_bki_tax_id() -> str | None:
    tid = frappe.db.get_value("Company", BKI_COMPANY, "tax_id")
    if tid:
        return tid
    cust = frappe.db.get_value("Customer", {"customer_name": BKI_COMPANY}, "tax_id")
    return cust


def _per_store_companies() -> list[str]:
    rows = frappe.db.sql(
        """
        SELECT DISTINCT c.name FROM `tabCompany` c
        WHERE c.name != %s AND IFNULL(c.is_group, 0) = 0
          AND EXISTS (SELECT 1 FROM `tabWarehouse` w WHERE w.company = c.name AND IFNULL(w.disabled, 0) = 0)
        ORDER BY c.name
        """,
        BKI_COMPANY,
    )
    return [r[0] for r in rows]


def _default_supplier_group() -> str:
    grp = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
    return grp or "All Supplier Groups"


def execute(dry_run: bool = True) -> dict:
    frappe.set_user("Administrator")
    ledger: dict = {
        "mode": "dry-run" if dry_run else "apply",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "supplier": SUPPLIER_NAME,
        "errors": [],
    }
    frappe.db.savepoint(SAVEPOINT)
    try:
        if frappe.db.exists("Supplier", SUPPLIER_NAME):
            ledger["status"] = "existed"
        else:
            tax_id = _resolve_bki_tax_id()
            stores = _per_store_companies()
            doc = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": SUPPLIER_DISPLAY,
                "supplier_group": _default_supplier_group(),
                "country": "Philippines",
                "is_internal_supplier": 0,
                "tax_id": tax_id,
                "companies": [{"company": s} for s in stores],
            })
            doc.insert(ignore_permissions=True)
            if doc.name != SUPPLIER_NAME:
                raise ValueError(f"Expected docname {SUPPLIER_NAME!r}, got {doc.name!r}")
            ledger["status"] = "created"
            ledger["tax_id"] = tax_id
            ledger["companies_count"] = len(stores)

        if dry_run:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        else:
            frappe.db.release_savepoint(SAVEPOINT)
            frappe.db.commit()
    except Exception as exc:
        try:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        except Exception:
            pass
        frappe.log_error(title="S238 Supplier seed failed", message=traceback.format_exc()[:1500])
        ledger["status"] = "error"
        ledger["error"] = str(exc)[:300]
        ledger["errors"].append({"step": "create_supplier", "error": str(exc)[:300]})
    return ledger


def main() -> None:
    dry_run = "--apply" not in sys.argv
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    result = execute(dry_run=dry_run)
    out = "/tmp/s238_seed_supplier_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    sys.stdout.write(
        f"S238_SUPPLIER_OK mode={result['mode']} status={result['status']} path={out}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
