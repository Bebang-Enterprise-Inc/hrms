#!/usr/bin/env python3
"""S247 Phase 6 v2 — Second-pass cleanup for 560 SIs linked to legacy Stock Entries.

These legacy SEs were created pre-S247 (no `bki_si_reference`) but are linked
to the BKI SI via the SE's `sales_invoice_no` or `bill_no` field. Frappe's link
protection blocks SI delete until the linked SE is cancelled.

Strategy:
  1. Generators already disabled by Phase 6 v1 (re-enabled at end of that run);
     we re-disable to be safe.
  2. For each failed SI from Phase 6 v1:
     - Find the linked Stock Entry via tabDynamic Link or known link fields
     - Cancel the SE (reverses its SLE + JE — these are TEST data per CEO)
     - Delete the SE
     - Retry cancel+delete on the SI
  3. Re-enable generators.
"""
from __future__ import annotations
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json, sys, re, traceback
from datetime import datetime

import frappe  # type: ignore

BKI_COMPANY = "BEBANG KITCHEN INC."


def _toggle_generators(state):
    settings = frappe.get_single("BEI Settings")
    settings.enable_bki_store_pi_generator = state
    settings.enable_bki_store_stock_entry_generator = state
    settings.save(ignore_permissions=True)
    frappe.db.commit()


def _find_linked_ses(si_name):
    """Find all Stock Entries linked to this SI via various link fields."""
    ses = set()
    # Check tabStock Entry for any field referencing this SI
    for field in ("sales_invoice_no", "bill_no", "reference_doctype"):
        try:
            rows = frappe.db.sql(
                f"""SELECT name FROM `tabStock Entry`
                    WHERE `{field}` = %s""",
                si_name, as_dict=True,
            )
            for r in rows:
                ses.add(r["name"])
        except Exception:
            pass
    # Also check tabDynamic Link
    try:
        rows = frappe.db.sql(
            """SELECT parent FROM `tabDynamic Link`
               WHERE link_doctype = 'Sales Invoice' AND link_name = %s
                 AND parenttype = 'Stock Entry'""",
            si_name, as_dict=True,
        )
        for r in rows:
            ses.add(r["parent"])
    except Exception:
        pass
    return list(ses)


def _force_clean_si_with_links(si_name):
    """Clean SI by first cancelling+deleting any linked legacy SE."""
    out = {"si": si_name, "steps": []}
    try:
        linked_ses = _find_linked_ses(si_name)
        out["linked_legacy_ses"] = linked_ses

        for se_name in linked_ses:
            try:
                se = frappe.get_doc("Stock Entry", se_name)
                if se.docstatus == 1:
                    se.cancel()
                    out["steps"].append(f"cancelled legacy SE {se_name}")
                frappe.delete_doc("Stock Entry", se_name, force=True, ignore_permissions=True)
                out["steps"].append(f"deleted legacy SE {se_name}")
            except Exception as e:
                out["steps"].append(f"SE {se_name} cleanup err: {str(e)[:200]}")

        # Now SI
        si = frappe.get_doc("Sales Invoice", si_name)
        if si.docstatus == 1:
            si.cancel()
            out["steps"].append(f"cancelled SI {si_name}")
        frappe.delete_doc("Sales Invoice", si_name, force=True, ignore_permissions=True)
        out["steps"].append(f"deleted SI {si_name}")
        out["status"] = "OK"
        frappe.db.commit()
    except Exception as e:
        out["status"] = "STILL_FAILED"
        out["error"] = str(e)[:400]
    return out


def main() -> None:
    payload = {
        "sprint": "S247", "phase": "6v2",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "outcomes": [],
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # Disable generators
        _toggle_generators(0)
        payload["generators_disabled"] = True

        # Get remaining BKI SIs
        remaining = frappe.db.sql(
            """SELECT name FROM `tabSales Invoice` WHERE company = %s""",
            BKI_COMPANY, as_dict=True,
        )
        payload["remaining_before"] = len(remaining)

        for r in remaining:
            outcome = _force_clean_si_with_links(r["name"])
            payload["outcomes"].append(outcome)

        # Post-verify
        post = frappe.db.sql(
            """SELECT COUNT(*) AS cnt FROM `tabSales Invoice` WHERE company = %s""",
            BKI_COMPANY, as_dict=True,
        )
        payload["remaining_after"] = post[0]["cnt"] if post else None

        ok = sum(1 for o in payload["outcomes"] if o.get("status") == "OK")
        failed = sum(1 for o in payload["outcomes"] if o.get("status") != "OK")
        payload["summary"] = {
            "attempted": len(payload["outcomes"]),
            "ok": ok,
            "failed": failed,
            "remaining_after": payload["remaining_after"],
        }
        payload["status"] = "OK" if failed == 0 else "PARTIAL"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["error"] = str(e)
        payload["traceback"] = traceback.format_exc()
    finally:
        try:
            _toggle_generators(1)
            payload["generators_reenabled"] = True
        except Exception:
            payload["generators_reenable_failed"] = True

    out_path = "/tmp/s247_p6v2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S247_P6V2_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
