#!/usr/bin/env python3
"""
S168 Phase 5.4 + Phase 13 -- configure BEI Settings for BKI -> store sales billing.

Phase 5.4 -- Set BKI billing defaults on BEI Settings single doc:
  - bki_markup_jv_percent                 = 2.75
  - bki_markup_managed_franchise_percent  = 8.0
  - bki_markup_full_franchise_percent     = 8.0
  - bki_sales_vat_template                = 'BKI Output VAT 12% Sales'
  - bki_sales_income_account              = '4000101 SALES - BKI TO STORES - BKI'  (ICT-008 Option C)
  - bki_output_vat_account                = '2102205 OUTPUT VAT PAYABLE - BKI'     (ICT-009)
  - bki_default_incoterm                  = 'Destination'                          (ICT-007)

Phase 13 -- EWT toggle framework (NO-OP REUSE):
  ICT-004 confirmed: BEI is NOT a Top 20,000 taxpayer, so EWT is OFF by
  default. Phase 13 MUST reuse the existing BEI Settings fields:
    - default_ewt_rate      (pre-existing Float, default 0)
    - ewt_payable_account   (pre-existing Link -> Account)
    - default_vat_rate      (pre-existing Float)
  S168 adds exactly ONE new toggle, `bki_ewt_on_store_sales_enabled` (Check,
  default 0), in the BEI Settings JSON (owned by agent-schema). This script
  does NOT create new EWT rate/account fields. When Finance eventually flips
  the toggle ON, the existing default_ewt_rate + ewt_payable_account become
  active on BKI -> store SIs. No code change required at that time.

  Direction caveat (from finance audit W3): Top 20k EWT obligation runs on
  the PAYER (the store), not BKI. In that future scenario BKI would RECEIVE
  a 2307 from the store rather than withhold on its own SI. Revisit at
  toggle-flip time.

This script is idempotent: it only updates fields whose current value differs
from the target. Emits JSON report between S168_SSM_REPORT_BEGIN / _END markers.
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
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

TARGETS: dict = {
    "bki_markup_jv_percent": 2.75,
    "bki_markup_managed_franchise_percent": 8.0,
    "bki_markup_full_franchise_percent": 8.0,
    "bki_sales_vat_template": "BKI Output VAT 12% Sales",
    "bki_sales_income_account": "4000101 SALES - BKI TO STORES - BKI",
    "bki_output_vat_account": "2102205 OUTPUT VAT PAYABLE - BKI",
    "bki_default_incoterm": "Destination",
}

# Phase 13 fields we expect to ALREADY EXIST (do not create)
PHASE13_EXISTING_FIELDS = ["default_ewt_rate", "ewt_payable_account", "default_vat_rate"]
PHASE13_NEW_TOGGLE = "bki_ewt_on_store_sales_enabled"  # owned by agent-schema JSON


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "5.4+13-bei-settings",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    changes: list[dict] = []
    warnings: list[str] = []
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        doc = frappe.get_single("BEI Settings")
        meta = frappe.get_meta("BEI Settings")

        # Phase 5.4: apply targets (skip missing fields with a warning so the
        # script is safe to run before the DocType JSON patch lands).
        for field, target in TARGETS.items():
            if not meta.get_field(field):
                warnings.append(f"field_missing:{field}")
                continue
            # Guard link fields against non-existent documents
            if field == "bki_sales_vat_template":
                if not frappe.db.exists("Sales Taxes and Charges Template", target):
                    warnings.append(f"vat_template_missing:{target} -- run s168_seed_vat_template.py first")
                    continue
            if field == "bki_sales_income_account":
                if not frappe.db.exists("Account", target):
                    warnings.append(f"income_account_missing:{target} -- run s168_seed_gl_accounts.py first")
                    continue
            if field == "bki_output_vat_account":
                if not frappe.db.exists("Account", target):
                    warnings.append(f"output_vat_account_missing:{target}")
                    continue
            current = doc.get(field)
            if current == target:
                continue
            doc.set(field, target)
            changes.append({"field": field, "old": current, "new": target})

        # Phase 13: verify reuse fields exist (they should, from prior sprints).
        phase13_status: dict = {}
        for field in PHASE13_EXISTING_FIELDS:
            exists = bool(meta.get_field(field))
            phase13_status[field] = "present" if exists else "MISSING"
            if not exists:
                warnings.append(f"phase13_reuse_field_missing:{field}")

        toggle_field = meta.get_field(PHASE13_NEW_TOGGLE)
        phase13_status[PHASE13_NEW_TOGGLE] = "present" if toggle_field else "not_yet_added_by_schema_agent"

        if changes:
            doc.save(ignore_permissions=True)
            frappe.db.commit()

        report.update(
            {
                "changes": changes,
                "changed_count": len(changes),
                "phase13_fields": phase13_status,
                "warnings": warnings,
                "ok": True,
            }
        )
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
