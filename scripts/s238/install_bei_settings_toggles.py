#!/usr/bin/env python3
"""S238 Phase 2-T3 — install Custom Field 'enable_bki_store_pi_generator' on BEI Settings.

Check field, default 1. Kill switch for the PI generator hook.
Idempotent. Modes: --dry-run (default), --apply.

Per audit B11: explicitly EXCLUDES auto_submit_store_pi (deferred to future
queued-job sprint).
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

DT = "BEI Settings"
FIELDNAME = "enable_bki_store_pi_generator"
SAVEPOINT = "s238_install_pi_toggle"


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
                "label": "Enable BKI Store PI Generator",
                "fieldtype": "Check",
                "default": "1",
                "description": "S238: when enabled, every submitted BKI->store SI auto-creates a Draft PI on the per-store Company's books. Kill switch.",
                "insert_after": "bki_default_incoterm",
            })
            cf.insert(ignore_permissions=True)
            ledger["status"] = "created"
            ledger["name"] = cf.name

        # Set the default value on the Single doc itself
        if not dry_run:
            settings = frappe.get_single(DT)
            cur = settings.get(FIELDNAME)
            if cur is None or int(cur or 0) == 0:
                settings.set(FIELDNAME, 1)
                settings.save(ignore_permissions=True)
                ledger["default_set"] = True
            else:
                ledger["default_set"] = False
                ledger["existing_value"] = int(cur)

        if dry_run:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        else:
            frappe.db.release_savepoint(SAVEPOINT)
            frappe.db.commit()
            frappe.clear_cache(doctype=DT)
    except Exception as exc:
        try:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT `{SAVEPOINT}`")
        except Exception:
            pass
        frappe.log_error(
            title="S238 install BEI Settings toggle failed",
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
    out = "/tmp/s238_install_toggle_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    sys.stdout.write(
        f"S238_TOGGLE_OK mode={result['mode']} status={result['status']} path={out}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
