#!/usr/bin/env python3
"""S231 L3 — teardown: delete the S231-L3-TEST-NEW-STORE test Company.

Reads output/l3/s231/seeded_test_store.json to find what was created,
then deletes the Company via direct SQL (bypasses cancel-and-delete
ORM since the test Company is unsubmitted with no transactions).

Idempotent: passes silently if the test Company doesn't exist.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

TEST_COMPANY = "S231-L3-TEST-NEW-STORE - BEBANG FT INC."

PROBE = (
	PAYLOAD_PREAMBLE
	+ f"""
import traceback
result = {{"test_company": {TEST_COMPANY!r}}}

before = bool(frappe.db.exists("Company", {TEST_COMPANY!r}))
result["existed_before_teardown"] = before

if before:
    try:
        # frappe.delete_doc honors NestedSet on Company so the doctype
        # cleans up cleanly. force=True allows deletion despite the
        # operational_status field.
        frappe.delete_doc(
            "Company", {TEST_COMPANY!r},
            force=True, ignore_permissions=True, ignore_on_trash=True,
        )
        frappe.db.commit()
        result["deleted"] = True
    except Exception as e:
        result["deleted"] = False
        result["delete_error"] = str(e)[:500]
        result["delete_tb"] = traceback.format_exc()[:2500]
        # SQL fallback for stubborn rows
        try:
            frappe.db.sql(
                "DELETE FROM `tabCompany` WHERE name = %s", ({TEST_COMPANY!r},)
            )
            frappe.db.commit()
            result["sql_delete_applied"] = True
        except Exception as e2:
            result["sql_delete_error"] = str(e2)[:300]

result["exists_after_teardown"] = bool(frappe.db.exists("Company", {TEST_COMPANY!r}))
result["teardown_at"] = frappe.utils.now()

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/l3/s231/teardown_test_store.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0 if not data.get("exists_after_teardown") else 1


if __name__ == "__main__":
	sys.exit(main())
