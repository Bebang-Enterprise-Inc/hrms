#!/usr/bin/env python3
"""S231 emergency: recreate BEBANG FRANCHISE CORP. that the dedup nuked.

The previous BFC dedup with frappe.rename_doc(merge=True) collapsed both
the canonical and duplicate records due to case-insensitive collation
treating them as the same key. This script recreates BFC using the same
ignore_chart_of_accounts pattern as BFI2 creation.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Pre-state
result["before"] = frappe.db.sql(
    "SELECT name, abbr FROM `tabCompany` WHERE abbr='BFC' OR name LIKE '%FRANCHISE CORP%' OR name LIKE '%franchise corp%'",
    as_dict=True,
)

# Recreate with bypassed chart of accounts
already = bool(frappe.db.exists("Company", "BEBANG FRANCHISE CORP."))
result["already_existed"] = already

if not already:
    frappe.local.flags.ignore_chart_of_accounts = True
    frappe.flags.in_install = True
    try:
        co = frappe.new_doc("Company")
        co.company_name = "BEBANG FRANCHISE CORP."
        co.abbr = "BFC"
        co.country = "Philippines"
        co.default_currency = "PHP"
        co.tax_id = "672-618-804-00000"
        co.flags.ignore_permissions = True
        try:
            co.insert()
            frappe.db.commit()
            result["bfc_recreated"] = True
        except Exception as ex:
            import traceback as _tb
            result["bfc_insert_failed"] = True
            result["bfc_insert_error"] = str(ex)[:1000]
            result["bfc_insert_traceback"] = _tb.format_exc()[:5000]
            try:
                frappe.db.rollback()
            except Exception:
                pass
    finally:
        frappe.local.flags.ignore_chart_of_accounts = False
        frappe.flags.in_install = False

# Post-state
result["after"] = frappe.db.sql(
    "SELECT name, abbr, tax_id FROM `tabCompany` WHERE abbr='BFC' OR name LIKE '%FRANCHISE CORP%'",
    as_dict=True,
)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=180)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/bfc_recreate_log.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0


if __name__ == "__main__":
	sys.exit(main())
