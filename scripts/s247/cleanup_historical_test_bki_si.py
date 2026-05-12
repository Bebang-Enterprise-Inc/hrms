#!/usr/bin/env python3
"""S247 Phase 6 — Historical BKI test SI cleanup with generator-toggle dance.

Per CEO directive 2026-05-10: "All transactions in Frappe today are test —
delete them before go-live." Targets all Sales Invoices on company=BKI.

Safety dance (audit Blocker 9):
  1. Disable both generators via BEI Settings toggles (prevents recursive
     cascade on every SI cancel).
  2. For each BKI SI: cancel paired PI + SE if they exist (Draft -> delete,
     Submitted -> cancel + delete). Then cancel SI. Then force-delete SI.
  3. Re-enable both generators.

Idempotent. Tracks per-SI outcome. Writes detailed log.
"""
from __future__ import annotations
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json, sys, traceback
from datetime import datetime

import frappe  # type: ignore

BKI_COMPANY = "BEBANG KITCHEN INC."


def _toggle_generators(state):
    """Set both generator toggles to `state` (0 or 1) and commit."""
    settings = frappe.get_single("BEI Settings")
    settings.enable_bki_store_pi_generator = state
    settings.enable_bki_store_stock_entry_generator = state
    settings.save(ignore_permissions=True)
    frappe.db.commit()


def _force_clean_one_si(si_name):
    """Cancel + delete one BKI SI with its paired PI/SE. Returns outcome dict."""
    out = {"si": si_name, "steps": []}
    try:
        # Find paired docs first
        pi_name = frappe.db.get_value("Purchase Invoice", {"bki_si_reference": si_name}, "name")
        se_name = None
        if frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
            se_name = frappe.db.get_value("Stock Entry", {"bki_si_reference": si_name}, "name")
        out["paired_pi"] = pi_name
        out["paired_se"] = se_name

        # Clean SE first (reverse-creation order)
        if se_name:
            try:
                se = frappe.get_doc("Stock Entry", se_name)
                if se.docstatus == 1:
                    se.cancel()
                    out["steps"].append(f"cancelled SE {se_name}")
                frappe.delete_doc("Stock Entry", se_name, force=True, ignore_permissions=True)
                out["steps"].append(f"deleted SE {se_name}")
            except Exception as e:
                out["steps"].append(f"SE cleanup failed {se_name}: {str(e)[:200]}")

        # Then PI
        if pi_name:
            try:
                pi = frappe.get_doc("Purchase Invoice", pi_name)
                if pi.docstatus == 1:
                    pi.cancel()
                    out["steps"].append(f"cancelled PI {pi_name}")
                frappe.delete_doc("Purchase Invoice", pi_name, force=True, ignore_permissions=True)
                out["steps"].append(f"deleted PI {pi_name}")
            except Exception as e:
                out["steps"].append(f"PI cleanup failed {pi_name}: {str(e)[:200]}")

        # Then SI
        try:
            si = frappe.get_doc("Sales Invoice", si_name)
            if si.docstatus == 1:
                si.cancel()
                out["steps"].append(f"cancelled SI {si_name}")
            frappe.delete_doc("Sales Invoice", si_name, force=True, ignore_permissions=True)
            out["steps"].append(f"deleted SI {si_name}")
            out["status"] = "OK"
        except Exception as e:
            out["steps"].append(f"SI delete failed {si_name}: {str(e)[:300]}")
            out["status"] = "SI_DELETE_FAILED"

        frappe.db.commit()
    except Exception as e:
        out["status"] = "OUTER_ERROR"
        out["error"] = str(e)[:300]
    return out


def main() -> None:
    payload = {
        "sprint": "S247", "phase": "6",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "outcomes": [],
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # P6.1 — snapshot
        before = frappe.db.sql(
            """SELECT name, docstatus, customer, custom_bei_store_order, grand_total, creation
               FROM `tabSales Invoice` WHERE company = %s""",
            BKI_COMPANY, as_dict=True,
        )
        payload["pre_cleanup_count"] = len(before)
        payload["pre_breakdown"] = {}
        for r in before:
            ds = r["docstatus"]
            payload["pre_breakdown"][ds] = payload["pre_breakdown"].get(ds, 0) + 1

        # P6.0 — disable both generators
        _toggle_generators(0)
        payload["generators_disabled_at"] = datetime.utcnow().isoformat() + "Z"

        # P6.2-P6.4 — clean each SI
        for r in before:
            outcome = _force_clean_one_si(r["name"])
            payload["outcomes"].append(outcome)

        # P6.5 — post-verify
        after = frappe.db.sql(
            """SELECT COUNT(*) AS cnt FROM `tabSales Invoice` WHERE company = %s""",
            BKI_COMPANY, as_dict=True,
        )
        payload["post_cleanup_count"] = after[0]["cnt"] if after else None

        paired_pi_remaining = frappe.db.sql(
            """SELECT COUNT(*) AS cnt FROM `tabPurchase Invoice`
               WHERE bki_si_reference IS NOT NULL AND bki_si_reference != ''""",
            as_dict=True,
        )
        payload["paired_pi_remaining"] = paired_pi_remaining[0]["cnt"] if paired_pi_remaining else None

        paired_se_remaining = 0
        if frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
            paired_se_remaining = frappe.db.sql(
                """SELECT COUNT(*) AS cnt FROM `tabStock Entry`
                   WHERE bki_si_reference IS NOT NULL AND bki_si_reference != ''""",
                as_dict=True,
            )[0]["cnt"]
        payload["paired_se_remaining"] = paired_se_remaining

        # P6.6 — re-enable generators
        _toggle_generators(1)
        payload["generators_reenabled_at"] = datetime.utcnow().isoformat() + "Z"

        # Tallies
        ok = sum(1 for o in payload["outcomes"] if o.get("status") == "OK")
        failed = sum(1 for o in payload["outcomes"] if o.get("status") != "OK")
        payload["summary"] = {
            "total_attempted": len(payload["outcomes"]),
            "ok": ok,
            "failed": failed,
            "pre_cleanup_count": payload["pre_cleanup_count"],
            "post_cleanup_count": payload["post_cleanup_count"],
            "paired_pi_remaining": payload["paired_pi_remaining"],
            "paired_se_remaining": payload["paired_se_remaining"],
        }
        payload["status"] = "OK" if failed == 0 else "PARTIAL"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()
        # Always try to re-enable generators on error
        try:
            _toggle_generators(1)
            payload["generators_reenabled_on_error"] = True
        except Exception:
            payload["generators_reenable_failed"] = True

    out_path = "/tmp/s247_p6_cleanup.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S247_P6_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
