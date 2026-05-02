#!/usr/bin/env python3
"""S231 deploy validation — comprehensive read-only check that PR #706 +
#707 actually landed correctly in production.

Verifies:
  1. tabBEI Fee Schedule + tabBEI Fee Carveout + tabBEI Billing Schedule
     tables exist (DocTypes migrated by `bench migrate`).
  2. All 11 new BEI Settings fields exist in DocType meta with correct
     defaults / fieldtypes.
  3. Live BEI Settings Single doc has bki_billing_cron_enabled=0 (the
     PR #706 kill-switch is intact).
  4. The live Company validate hook chain has null_out_dead_default_refs
     wired BEFORE validate_default_accounts (per S231-C2).
  5. _NON_STORE_ENTITIES + DEFAULT_FIELDS_TO_TRACK constants are
     importable from the deployed code.

Output: output/s231/verification/deploy_validation.json
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	PAYLOAD_PREAMBLE,
	decode_output,
	run_in_container,
)

OUT = REPO_ROOT / "output" / "s231" / "verification" / "deploy_validation.json"

VALIDATE_SCRIPT = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# 1. Tables migrated
for table in ("tabBEI Fee Schedule", "tabBEI Fee Carveout", "tabBEI Billing Schedule"):
    rows = frappe.db.sql(f"SHOW TABLES LIKE %s", (table,))
    result.setdefault("tables", {})[table] = bool(rows)

# 2. BEI Settings new fields
required_fields = [
    ("bki_markup_company_owned_percent", "Float", "2.75"),
    ("bki_billing_cron_enabled", "Check", "0"),
    ("bki_sales_debit_to_account", "Link", None),
    ("bki_sales_naming_series", "Data", None),
    ("bfc_revenue_company", "Link", "BEBANG FRANCHISE CORP."),
    ("bfc_sales_vat_template", "Link", None),
    ("bfc_sales_naming_series", "Data", None),
    ("bfc_or_active", "Check", "0"),
    ("bfc_vat_registration_active", "Check", "0"),
    ("jv_revenue_company", "Link", "Bebang Enterprise Inc."),
    ("jv_sales_vat_template", "Link", None),
]
meta = frappe.get_meta("BEI Settings")
fields_check = []
for fname, expected_type, expected_default in required_fields:
    if not meta.has_field(fname):
        fields_check.append({"field": fname, "exists": False})
        continue
    field = meta.get_field(fname)
    fields_check.append({
        "field": fname,
        "exists": True,
        "fieldtype": field.fieldtype,
        "default": field.default,
        "type_match": field.fieldtype == expected_type,
        "default_match": str(field.default or "") == str(expected_default or ""),
    })
result["bei_settings_fields"] = fields_check

# 3. Live values on the BEI Settings Single doc
live_values = {}
for f, _, _ in required_fields:
    try:
        live_values[f] = frappe.db.get_single_value("BEI Settings", f)
    except Exception as e:
        live_values[f] = f"ERROR: {e}"
result["live_bei_settings"] = live_values

# Critical check: cron gate intact
result["cron_gate_intact"] = live_values.get("bki_billing_cron_enabled") in (0, None)

# 4. Hooks chain ordering check — read live `Company` validate hooks
import hrms.hooks as hooks_mod
company_hooks = hooks_mod.doc_events.get("Company", {})
validate_chain = company_hooks.get("validate", [])
if isinstance(validate_chain, str):
    validate_chain = [validate_chain]
result["company_validate_chain"] = list(validate_chain)
# null_out_dead_default_refs must appear BEFORE validate_default_accounts
try:
    null_idx = validate_chain.index("hrms.overrides.company.null_out_dead_default_refs")
    valdef_idx = validate_chain.index("hrms.overrides.company.validate_default_accounts")
    result["null_out_before_validate_defaults"] = null_idx < valdef_idx
except ValueError:
    result["null_out_before_validate_defaults"] = False
# validate_store_ownership_type also wired
result["validate_store_ownership_type_wired"] = (
    "hrms.overrides.company.validate_store_ownership_type" in validate_chain
)

# 5. Constants importable
import importlib
try:
    company_mod = importlib.import_module("hrms.overrides.company")
    result["DEFAULT_FIELDS_TO_TRACK_count"] = len(getattr(company_mod, "DEFAULT_FIELDS_TO_TRACK", []))
    result["null_out_dead_default_refs_callable"] = callable(
        getattr(company_mod, "null_out_dead_default_refs", None)
    )
    result["validate_store_ownership_type_callable"] = callable(
        getattr(company_mod, "validate_store_ownership_type", None)
    )
except Exception as e:
    result["company_module_import_error"] = str(e)

try:
    billing_mod = importlib.import_module("hrms.api.billing")
    result["_resolve_fee_recipient_company_callable"] = callable(
        getattr(billing_mod, "_resolve_fee_recipient_company", None)
    )
    result["_assert_bfc_billing_ready_callable"] = callable(
        getattr(billing_mod, "_assert_bfc_billing_ready", None)
    )
    result["_create_monthly_fee_sales_invoice_callable"] = callable(
        getattr(billing_mod, "_create_monthly_fee_sales_invoice", None)
    )
except Exception as e:
    result["billing_module_import_error"] = str(e)

try:
    cm_mod = importlib.import_module("hrms.api.company_master")
    nse = getattr(cm_mod, "_NON_STORE_ENTITIES", None)
    result["_NON_STORE_ENTITIES_keys"] = list(nse.keys()) if nse else None
    result["_NON_STORE_ENTITIES_count"] = len(nse) if nse else 0
except Exception as e:
    result["company_master_module_import_error"] = str(e)

# 6. DocType-level check on the new ones
for dt in ("BEI Fee Schedule", "BEI Fee Carveout"):
    try:
        dt_meta = frappe.get_meta(dt)
        result.setdefault("new_doctypes", {})[dt] = {
            "exists": True,
            "field_count": len(dt_meta.fields),
            "issingle": dt_meta.issingle,
        }
    except Exception as e:
        result.setdefault("new_doctypes", {})[dt] = {"exists": False, "error": str(e)}

# 7. Existing rows count (should be 0 immediately after deploy; non-zero after seed)
for dt in ("BEI Fee Schedule", "BEI Fee Carveout"):
    try:
        result.setdefault("doctype_row_counts", {})[dt] = frappe.db.count(dt)
    except Exception as e:
        result.setdefault("doctype_row_counts", {})[dt] = f"ERROR: {e}"

# 8. Canonical Companies sanity (BEBANG FRANCHISE CORP. canonical exists?)
result["canonical_bfc_check"] = {
    "BEBANG FRANCHISE CORP._exists": bool(
        frappe.db.exists("Company", "BEBANG FRANCHISE CORP.")
    ),
    "Bebang Franchise Corp._exists": bool(
        frappe.db.exists("Company", "Bebang Franchise Corp.")
    ),
    "BEBANG FT INC._exists": bool(frappe.db.exists("Company", "BEBANG FT INC.")),
    "Bebang Enterprise Inc._exists": bool(
        frappe.db.exists("Company", "Bebang Enterprise Inc.")
    ),
}

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(VALIDATE_SCRIPT, timeout=180)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}")
	# Quick gate summary for Sam
	print("\n=== SUMMARY ===")
	tables = data.get("tables", {})
	for t, ok in tables.items():
		print(f"  {'OK' if ok else 'FAIL'}  table {t}")
	print(f"  cron_gate_intact: {data.get('cron_gate_intact')}")
	print(f"  null_out_before_validate_defaults: {data.get('null_out_before_validate_defaults')}")
	print(f"  validate_store_ownership_type_wired: {data.get('validate_store_ownership_type_wired')}")
	for f, info in data.get("new_doctypes", {}).items():
		print(f"  DocType {f}: {info}")
	print(f"  DEFAULT_FIELDS_TO_TRACK_count: {data.get('DEFAULT_FIELDS_TO_TRACK_count')}")
	print(f"  _NON_STORE_ENTITIES_count: {data.get('_NON_STORE_ENTITIES_count')}")
	missing_fields = [f["field"] for f in data.get("bei_settings_fields", []) if not f.get("exists")]
	print(f"  missing_bei_settings_fields: {missing_fields or 'NONE'}")
	canon = data.get("canonical_bfc_check", {})
	print(f"  BFC canonical exists: {canon.get('BEBANG FRANCHISE CORP._exists')}")
	print(f"  BFC duplicate exists: {canon.get('Bebang Franchise Corp._exists')}")
	print(f"  BFI2 (BEBANG FT INC.) exists: {canon.get('BEBANG FT INC._exists')}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
