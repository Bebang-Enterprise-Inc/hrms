#!/usr/bin/env python3
"""
S168 Phase 5.1 -- seed BKI Customer records for the 35 active buyer corporations.

Reads the S037 store/buyer/entity register and the ENTITY_TIN_RDO file (both
must be staged into the container by the SSM runner at /tmp/*).

For each unique `buyer_entity_name` with status in
  ('confirmed_legal_entity', 'entity_confirmed_store_type_pending')
creates a Customer with:
  - customer_name       = buyer_entity_name (exact)
  - customer_type       = Company
  - customer_group      = BKI Store (precreated by s168_seed_customer_group.py)
  - territory           = Philippines or All Territories
  - is_internal_customer= 0 (external per ICT-001)
  - tax_id              = TIN from ENTITY_TIN_RDO_2026-02-27.csv (required)
  - custom_vat_status   = VAT Status from TIN/RDO (set only if field exists)
  - custom_bir_rdo_code = RDO Code from TIN/RDO (set only if field exists)

Known exception: 'Everyday Delight Food Ventures Inc.' has a blank TIN in the
TIN/RDO file (store not yet operating) -- skip with a WARNING, not a FAIL.

Idempotent via frappe.db.exists("Customer", name) (no company filter per R1
Amendment 14: Customer is NOT scoped to company in ERPNext).

Writes audit JSON to sites/output/s168/seed_customers_evidence.json (inside
container), and prints the same JSON between S168_SSM_REPORT_BEGIN / _END.

Env overrides:
  S168_REGISTER_CSV  (default /tmp/s168_store_register.csv)
  S168_TIN_RDO_CSV   (default /tmp/s168_entity_tin_rdo.csv)
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

REGISTER_CSV = os.environ.get("S168_REGISTER_CSV", "/tmp/s168_store_register.csv")
TIN_RDO_CSV = os.environ.get("S168_TIN_RDO_CSV", "/tmp/s168_entity_tin_rdo.csv")

# Wiring note: the SI income account bki_sales_income_account = 4000101
# SALES - BKI TO STORES - BKI is set in s168_configure_bei_settings.py (ICT-008).
CUSTOMER_GROUP = "BKI Store"
ACTIVE_STATUSES = {"confirmed_legal_entity", "entity_confirmed_store_type_pending"}
KNOWN_BLANK_TIN_ENTITY = "Everyday Delight Food Ventures Inc."
TERRITORY_CANDIDATES = ["Philippines", "All Territories"]
EVIDENCE_OUT = "/home/frappe/frappe-bench/sites/output/s168/seed_customers_evidence.json"


def _load_tin_rdo_lookup(path: str) -> dict:
    if not os.path.exists(path):
        raise ValueError(f"TIN/RDO file not found at {path}")
    lookup: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Entity Name") or "").strip()
            if not name or name.startswith("TOTAL"):
                continue
            # Keep the FIRST non-blank TIN we see (head office row usually first)
            existing = lookup.get(name)
            tin = (row.get("TIN") or "").strip()
            if existing and existing.get("tax_id"):
                continue
            lookup[name] = {
                "tax_id": tin,
                "rdo_code": (row.get("RDO Code") or "").strip(),
                "vat_status": (row.get("VAT Status") or "").strip(),
            }
    return lookup


def _resolve_territory() -> str:
    for t in TERRITORY_CANDIDATES:
        if frappe.db.exists("Territory", t):
            return t
    raise ValueError("No default Territory found; Finance must create one first.")


def _has_custom_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})) or bool(
        fieldname in (frappe.get_meta(doctype).get_field_names() if hasattr(frappe.get_meta(doctype), "get_field_names") else [])
    )


def _safe_has_field(doctype: str, fieldname: str) -> bool:
    try:
        meta = frappe.get_meta(doctype)
        return bool(meta.get_field(fieldname))
    except Exception:
        return False


def main() -> None:
    report: dict = {
        "sprint": "S168",
        "phase": "5.1-customers",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "customer_group": CUSTOMER_GROUP,
    }
    created: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        if not frappe.db.exists("Customer Group", CUSTOMER_GROUP):
            raise ValueError(
                f"Customer Group '{CUSTOMER_GROUP}' missing. "
                "Run s168_seed_customer_group.py first."
            )
        territory = _resolve_territory()

        if not os.path.exists(REGISTER_CSV):
            raise ValueError(f"Register CSV not found at {REGISTER_CSV}")

        tin_lookup = _load_tin_rdo_lookup(TIN_RDO_CSV)
        report["tin_lookup_count"] = len(tin_lookup)

        has_vat_status = _safe_has_field("Customer", "custom_vat_status")
        has_rdo_code = _safe_has_field("Customer", "custom_bir_rdo_code")
        report["has_custom_vat_status_field"] = has_vat_status
        report["has_custom_bir_rdo_code_field"] = has_rdo_code

        with open(REGISTER_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Dedup by buyer_entity_name, active only
        unique: dict[str, dict] = {}
        for row in rows:
            name = (row.get("buyer_entity_name") or "").strip()
            status = (row.get("buyer_entity_status") or "").strip()
            if not name or status not in ACTIVE_STATUSES:
                continue
            unique.setdefault(name, row)
        report["unique_active_corps"] = len(unique)

        for name, row in sorted(unique.items()):
            try:
                # Known blank TIN exception
                tin_info = tin_lookup.get(name)
                if name == KNOWN_BLANK_TIN_ENTITY or (tin_info and not tin_info.get("tax_id")):
                    warnings.append(f"{name}: blank TIN in TIN/RDO file -- skipped (store not operating)")
                    skipped.append({"customer_name": name, "reason": "blank_tin_not_operating"})
                    continue
                if not tin_info:
                    errors.append(f"{name}: not found in ENTITY_TIN_RDO file")
                    continue

                if frappe.db.exists("Customer", name):
                    skipped.append({"customer_name": name, "reason": "already_exists"})
                    continue

                doc = frappe.new_doc("Customer")
                doc.customer_name = name
                doc.customer_type = "Company"
                doc.customer_group = CUSTOMER_GROUP
                doc.territory = territory
                doc.is_internal_customer = 0
                doc.tax_id = tin_info["tax_id"]
                if has_vat_status and tin_info.get("vat_status"):
                    doc.custom_vat_status = tin_info["vat_status"]
                if has_rdo_code and tin_info.get("rdo_code"):
                    doc.custom_bir_rdo_code = tin_info["rdo_code"]
                doc.insert(ignore_permissions=True)
                created.append({"customer_name": name, "tax_id": tin_info["tax_id"]})
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")

        frappe.db.commit()

        report.update(
            {
                "created_count": len(created),
                "created": created,
                "skipped_count": len(skipped),
                "skipped": skipped,
                "warnings": warnings,
                "errors": errors,
                "ok": not errors,
            }
        )

        # Persist audit JSON inside container
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
