#!/usr/bin/env python3
"""S231: find the Department docname for Vista Mall."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
result["vista_departments"] = frappe.db.sql(
    "SELECT name, department_name, company FROM `tabDepartment` WHERE name LIKE '%vista%' OR department_name LIKE '%vista%' OR name LIKE '%VISTA%'",
    as_dict=True,
)
# Also any Company with vista in the name
result["vista_companies"] = frappe.db.sql(
    "SELECT name, abbr FROM `tabCompany` WHERE name LIKE '%VISTA%' OR name LIKE '%vista%'",
    as_dict=True,
)
result["all_departments_first_50"] = frappe.db.sql(
    "SELECT name FROM `tabDepartment` ORDER BY name LIMIT 50",
    as_list=True,
)
_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	print(json.dumps(data, indent=2, default=str)[:3000])
	return 0


if __name__ == "__main__":
	sys.exit(main())
