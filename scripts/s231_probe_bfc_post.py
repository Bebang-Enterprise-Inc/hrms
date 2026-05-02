#!/usr/bin/env python3
"""S231: post-dedup probe of BFC state."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
# Direct SQL — bypass any caching
result["all_bfc_companies"] = frappe.db.sql(
    "SELECT name, abbr, parent_company FROM `tabCompany` WHERE name LIKE '%FRANCHISE%' OR abbr = 'BFC' ORDER BY name",
    as_dict=True,
)
result["case_sensitive_canonical"] = frappe.db.sql(
    "SELECT name, abbr FROM `tabCompany` WHERE name = 'BEBANG FRANCHISE CORP.' COLLATE utf8mb4_bin",
    as_dict=True,
)
result["case_insensitive"] = frappe.db.sql(
    "SELECT name, abbr FROM `tabCompany` WHERE name LIKE 'bebang franchise corp.' COLLATE utf8mb4_general_ci",
    as_dict=True,
)
result["any_BFC_count"] = frappe.db.sql("SELECT COUNT(*) FROM `tabCompany` WHERE abbr = 'BFC'")[0][0]

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/bfc_post_dedup_state.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0


if __name__ == "__main__":
	sys.exit(main())
