#!/usr/bin/env python3
"""S238 Phase 2-T2 — install Custom Field 'bki_si_reference' on Purchase Invoice.

Link to Sales Invoice (BKI's SI). read_only=1. Inserted after bill_no.
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

DT = "Purchase Invoice"
FIELDNAME = "bki_si_reference"
SAVEPOINT = "s238_install_si_ref_field"


def execute(dry_run: bool = True) -> dict:
    frappe.set_user("Administrator")
    ledger: dict = {
        "mode": "dry-run" if dry_run else "apply",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "doctype": DT,
        "fieldname": FIELDNAME,
    }
    frappe.db.savepoint(SAVEPOINT)
    try:
        existing = frappe.db.exists("Custom Field", {"dt": DT, "fieldname": FIELDNAME})
        if existing:
            ledger["status"] = "existed"
            ledger["name"] = existing
        else:
            cf = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": DT,
                "fieldname": FIELDNAME,
                "label": "BKI Sales Invoice Reference",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "read_only": 1,
                "insert_after": "bill_no",
            })
            cf.insert(ignore_permissions=True)
            ledger["status"] = "created"
            ledger["name"] = cf.name

        if dry_run:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        else:
            frappe.db.release_savepoint(SAVEPOINT)
            frappe.db.commit()
            # Clear custom field cache so subsequent reads see the new field
            frappe.clear_cache(doctype=DT)
    except Exception as exc:
        try:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        except Exception:
            pass
        frappe.log_error(
            title="S238 install bki_si_reference field failed",
            message=traceback.format_exc()[:1500],
        )
        ledger["status"] = "error"
        ledger["error"] = str(exc)[:300]
    return ledger


def main() -> None:
    dry_run = "--apply" not in sys.argv
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    result = execute(dry_run=dry_run)
    out = "/tmp/s238_install_si_ref_field_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    sys.stdout.write(
        f"S238_FIELD_OK mode={result['mode']} status={result['status']} path={out}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
