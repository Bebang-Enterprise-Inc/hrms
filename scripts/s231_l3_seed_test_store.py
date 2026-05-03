#!/usr/bin/env python3
"""S231 L3 — pre-flight seeder: create a TEST Company under BEBANG FT INC.

Pattern follows s209's `s209_grant_test_area_access.py` — a one-shot
production-mutation script that runs BEFORE the browser test, then
gets reversed by the matching teardown script after the test.

The test Company is intentionally namespaced with `S231-L3-TEST-` so
the teardown can find + delete it cleanly. parent_company is set to
BEBANG FT INC. (the new BFI2 entity created in S231 Phase A) — this
exercises the FULL canonical chain: child store rolling P&L up to a
new parent legal entity.

Output: output/l3/s231/seeded_test_store.json with the created
Company name + abbr + parent for the browser spec to read.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

TEST_COMPANY = "S231-L3-TEST-NEW-STORE - BEBANG FT INC."
TEST_ABBR = "S231NS"
TEST_PARENT = "BEBANG FT INC."
TEST_OWNERSHIP = "Managed Franchise"  # exercises full fee schedule

PROBE = (
	PAYLOAD_PREAMBLE
	+ f"""
import traceback

result = {{
    "test_company": {TEST_COMPANY!r},
    "test_abbr": {TEST_ABBR!r},
    "test_parent": {TEST_PARENT!r},
    "test_ownership": {TEST_OWNERSHIP!r},
}}

# Idempotent: if the test Company already exists, skip create (next
# run will reuse it; teardown will clean up regardless).
already = bool(frappe.db.exists("Company", {TEST_COMPANY!r}))
result["already_existed"] = already

if not already:
    # Pre-condition: parent must exist.
    if not frappe.db.exists("Company", {TEST_PARENT!r}):
        result["error"] = f"Parent Company {TEST_PARENT!r} does not exist"
        _s231_emit(result)
        frappe.destroy()
        raise SystemExit(0)

    # Use ignore_chart_of_accounts to skip ERPNext's CoA seeder which
    # has the structural bug (clones BEI flat-root accounts and fails
    # validate_root_details). Use in_install to skip BEI's
    # auto_provision_company too. The Company shell is enough for the
    # browser test — we're validating UI rendering, not CoA accounts.
    frappe.local.flags.ignore_chart_of_accounts = True
    frappe.flags.in_install = True
    try:
        co = frappe.new_doc("Company")
        co.company_name = {TEST_COMPANY!r}
        co.abbr = {TEST_ABBR!r}
        co.country = "Philippines"
        co.default_currency = "PHP"
        co.tax_id = "999-S231-L3-TEST-00000"
        co.parent_company = {TEST_PARENT!r}
        co.entity_category = "Store"
        co.store_ownership_type = {TEST_OWNERSHIP!r}
        co.operational_status = "Pre-Opening"
        co.flags.ignore_permissions = True
        try:
            co.insert()
            frappe.db.commit()
            result["created"] = True
        except Exception as ex:
            result["created"] = False
            result["insert_error"] = str(ex)[:500]
            result["insert_tb"] = traceback.format_exc()[:2500]
            try:
                frappe.db.rollback()
            except Exception:
                pass
    finally:
        frappe.local.flags.ignore_chart_of_accounts = False
        frappe.flags.in_install = False

# Verify post-state
result["exists_after"] = bool(frappe.db.exists("Company", {TEST_COMPANY!r}))
if result["exists_after"]:
    result["after"] = frappe.db.get_value(
        "Company", {TEST_COMPANY!r},
        ["abbr", "parent_company", "store_ownership_type",
         "entity_category", "operational_status", "tax_id",
         "first_provision_done"],
        as_dict=True,
    )

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/l3/s231/seeded_test_store.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0 if data.get("exists_after") else 1


if __name__ == "__main__":
	sys.exit(main())
