#!/usr/bin/env python3
"""S231 fix: mark BEBANG FT INC. as is_group=1 so child stores can roll up.

ERPNext requires parent_company to be is_group=1. The Phase A
creation didn't set this flag (oversight). Setting now.
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
result["before"] = frappe.db.get_value("Company", "BEBANG FT INC.", ["is_group", "parent_company", "abbr"], as_dict=True)
# Direct SQL — avoid re-triggering on_update hooks that have the
# CoA structural bug.
frappe.db.sql("UPDATE `tabCompany` SET is_group = 1 WHERE name = 'BEBANG FT INC.'")
frappe.db.commit()
# Frappe NestedSet may need rebuilt for the parent change to apply
try:
    from frappe.utils.nestedset import rebuild_tree
    rebuild_tree("Company", "parent_company")
    frappe.db.commit()
    result["nestedset_rebuilt"] = True
except Exception as e:
    result["nestedset_error"] = str(e)[:300]

result["after"] = frappe.db.get_value("Company", "BEBANG FT INC.", ["is_group", "parent_company", "abbr"], as_dict=True)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/bfi2_is_group_fix.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0


if __name__ == "__main__":
	sys.exit(main())
