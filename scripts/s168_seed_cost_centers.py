#!/usr/bin/env python3
"""
S168 Phase 12 -- seed per-store Cost Centers in Bebang Kitchen Inc. for P&L
allocation on BKI -> store Sales Invoices.

Hierarchy (created on demand, idempotent):
  Bebang Kitchen Inc. (root)
  |-- Stores - BKI (group)
      |-- JV - BKI (group)
      |   |-- {store_name} - BKI   (leaf)
      |-- Managed Franchise - BKI (group)
      |   |-- {store_name} - BKI   (leaf)
      |-- Full Franchise - BKI (group)
          |-- {store_name} - BKI   (leaf)

Reads the S037 store register from /tmp/s168_store_register.csv (override via
env S168_REGISTER_CSV). Creates a leaf cost center for every row whose
`active_fulfillment_status` starts with 'active' and `store_type` is non-blank.
Stores with blank `store_type` (pending_finance_classification) are parked
under a 'Stores - BKI' catch-all group.

Idempotent. Emits JSON report between S168_SSM_REPORT_BEGIN / _END and writes
sites/output/s168/seed_cost_centers_evidence.json.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from datetime import datetime

for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

COMPANY = "Bebang Kitchen Inc."
COMPANY_ABBR = "BKI"
REGISTER_CSV = os.environ.get("S168_REGISTER_CSV", "/tmp/s168_store_register.csv")
EVIDENCE_OUT = "/home/frappe/frappe-bench/sites/output/s168/seed_cost_centers_evidence.json"

KNOWN_GROUPS = ["Stores", "JV", "Managed Franchise", "Full Franchise"]


def _cc_id(name: str) -> str:
    return f"{name} - {COMPANY_ABBR}"


def _get_company_root_cc() -> str:
    root = frappe.db.get_value(
        "Cost Center",
        {"company": COMPANY, "is_group": 1, "parent_cost_center": ["in", ["", None]]},
        "name",
    )
    if root:
        return root
    root = frappe.db.get_value("Company", COMPANY, "cost_center")
    if not root:
        raise ValueError(f"No root cost center for {COMPANY}")
    return root


def _ensure_cc(cc_name: str, parent: str, is_group: int) -> dict:
    full_id = _cc_id(cc_name)
    if frappe.db.exists("Cost Center", full_id):
        return {"name": full_id, "action": "skipped"}
    if not frappe.db.exists("Cost Center", parent):
        raise ValueError(f"Parent cost center '{parent}' missing")
    doc = frappe.new_doc("Cost Center")
    doc.cost_center_name = cc_name
    doc.parent_cost_center = parent
    doc.company = COMPANY
    doc.is_group = is_group
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "action": "created"}


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "12-cost-centers",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "company": COMPANY,
    }
    results: list[dict] = []
    errors: list[str] = []
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        if not os.path.exists(REGISTER_CSV):
            raise ValueError(f"Register CSV not found at {REGISTER_CSV}")

        root_cc = _get_company_root_cc()
        report["root_cost_center"] = root_cc

        # Ensure top groups
        stores_cc = _cc_id("Stores")
        results.append(_ensure_cc("Stores", root_cc, 1))
        for group_label in ["JV", "Managed Franchise", "Full Franchise"]:
            results.append(_ensure_cc(group_label, stores_cc, 1))

        with open(REGISTER_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        leaf_count = 0
        for row in rows:
            store_name = (row.get("store_name") or "").strip()
            store_type = (row.get("store_type") or "").strip()
            fulfill = (row.get("active_fulfillment_status") or "").strip()
            if not store_name:
                continue
            if not fulfill.startswith("active"):
                continue
            if store_type in KNOWN_GROUPS[1:]:  # JV / MF / FF
                parent = _cc_id(store_type)
            else:
                # Pending classification -> park under Stores
                parent = stores_cc
            try:
                results.append(_ensure_cc(store_name, parent, 0))
                leaf_count += 1
            except Exception as e:
                errors.append(f"{store_name}: {type(e).__name__}: {e}")

        frappe.db.commit()

        report.update(
            {
                "leaf_stores_processed": leaf_count,
                "actions": results,
                "created_count": sum(1 for r in results if r.get("action") == "created"),
                "skipped_count": sum(1 for r in results if r.get("action") == "skipped"),
                "errors": errors,
                "ok": not errors,
            }
        )

        try:
            os.makedirs(os.path.dirname(EVIDENCE_OUT), exist_ok=True)
            with open(EVIDENCE_OUT, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
        except Exception:
            pass
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
