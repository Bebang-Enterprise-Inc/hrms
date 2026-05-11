#!/usr/bin/env python3
"""After-sweep probe — read full S238 error logs + verify no leftover test artifacts."""
from __future__ import annotations

import os
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import json
import sys
from datetime import datetime

import frappe  # type: ignore


def main() -> None:
    payload = {"timestamp_utc": datetime.utcnow().isoformat() + "Z"}
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # Last 60 minutes of S238 errors with FULL text
        errs = frappe.db.sql(
            """SELECT name, error, creation FROM `tabError Log`
               WHERE error LIKE 'S238: PI generation failed%'
               AND creation >= NOW() - INTERVAL 60 MINUTE
               ORDER BY creation DESC""",
            as_dict=True,
        )
        payload["error_log_count"] = len(errs)
        # Sample unique error stacktraces (dedupe by last 200 chars)
        seen = set()
        samples = []
        for e in errs:
            tail = e["error"][-300:] if len(e["error"]) > 300 else e["error"]
            key = tail.split("\n")[-2] if "\n" in tail else tail
            if key not in seen:
                seen.add(key)
                samples.append({
                    "name": e["name"],
                    "creation": str(e["creation"]),
                    "full_error": e["error"][:4000],  # capped to keep payload manageable
                })
            if len(samples) >= 8:
                break
        payload["unique_error_samples"] = samples

        # Check for any leftover test SIs (any BKI-SI-2026-009XX-N or 010XX-N created in last hour)
        leftover_si = frappe.db.sql(
            """SELECT name, custom_bei_store_order, customer, docstatus, creation
               FROM `tabSales Invoice`
               WHERE company = 'BEBANG KITCHEN INC.'
                 AND creation >= NOW() - INTERVAL 60 MINUTE
               ORDER BY creation DESC""",
            as_dict=True,
        )
        payload["leftover_si_count"] = len(leftover_si)
        payload["leftover_si"] = [
            {"name": r["name"], "order": r["custom_bei_store_order"],
             "customer": r["customer"], "docstatus": r["docstatus"],
             "creation": str(r["creation"])}
            for r in leftover_si
        ]

        # Check for any leftover test PIs (PIs with bki_si_reference set, created in last hour)
        leftover_pi = frappe.db.sql(
            """SELECT name, bki_si_reference, supplier, company, docstatus, creation
               FROM `tabPurchase Invoice`
               WHERE bki_si_reference IS NOT NULL AND bki_si_reference != ''
                 AND creation >= NOW() - INTERVAL 60 MINUTE
               ORDER BY creation DESC""",
            as_dict=True,
        )
        payload["leftover_pi_count"] = len(leftover_pi)
        payload["leftover_pi"] = [
            {"name": r["name"], "si_ref": r["bki_si_reference"],
             "supplier": r["supplier"], "company": r["company"],
             "docstatus": r["docstatus"], "creation": str(r["creation"])}
            for r in leftover_pi
        ]

        # Also check totals to detect any orphan PIs from previous sessions
        any_orphans = frappe.db.sql(
            """SELECT pi.name, pi.bki_si_reference, pi.company, pi.docstatus, pi.creation
               FROM `tabPurchase Invoice` pi
               LEFT JOIN `tabSales Invoice` si ON si.name = pi.bki_si_reference
               WHERE pi.bki_si_reference IS NOT NULL AND pi.bki_si_reference != ''
                 AND si.name IS NULL
               LIMIT 10""",
            as_dict=True,
        )
        payload["orphan_pi_count"] = len(any_orphans)
        payload["orphan_pi_sample"] = [
            {"name": r["name"], "si_ref": r["bki_si_reference"],
             "company": r["company"], "docstatus": r["docstatus"],
             "creation": str(r["creation"])}
            for r in any_orphans
        ]

        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s244_aftermath.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_AFTERMATH_OK status={payload.get('status')} "
                     f"errors={payload.get('error_log_count')} "
                     f"leftover_si={payload.get('leftover_si_count')} "
                     f"leftover_pi={payload.get('leftover_pi_count')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
