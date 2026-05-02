#!/usr/bin/env python3
"""S231: figure out where 6020602 ACCOUNTING FEES at root level comes from."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Approach 1: simulate what `get_chart('Standard', existing_company=None)` actually returns
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import get_chart
chart = get_chart("Standard", existing_company=None)
def find_problem_keys(node, path=""):
    if isinstance(node, dict):
        problems = []
        for key, value in node.items():
            current_path = f"{path}>{key}" if path else key
            # A root-level entry that's missing is_group AND has no children is a problem
            if isinstance(value, dict):
                children = [k for k, v in value.items() if isinstance(v, dict) and k not in ("root_type", "account_number", "account_type", "is_group", "tax_rate")]
                is_group = value.get("is_group")
                problems_found = find_problem_keys(value, current_path)
                problems.extend(problems_found)
            else:
                problems.append({"path": current_path, "value": str(value)[:100]})
        return problems
    return []
result["standard_problem_keys_count"] = len(find_problem_keys(chart))
result["standard_top_keys"] = list(chart.keys())

# Approach 2: simulate get_chart with existing_company="Bebang Enterprise Inc."
chart2 = get_chart("Standard", existing_company="Bebang Enterprise Inc.")
result["with_existing_BEI_top_keys"] = list(chart2.keys())[:20] if chart2 else None
# Find 6020602 in this chart
def find_in_chart(node, target, path=""):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            current_path = f"{path}>{key}" if path else key
            if target in str(key):
                found.append({"path": current_path, "is_group": (value.get("is_group") if isinstance(value, dict) else None), "has_children": isinstance(value, dict) and len(value) > 0})
            if isinstance(value, dict):
                found.extend(find_in_chart(value, target, current_path))
    return found
result["6020602_in_BEI_clone"] = find_in_chart(chart2, "6020602") if chart2 else None
result["ACCOUNTING_FEES_in_BEI_clone"] = find_in_chart(chart2, "ACCOUNTING FEES") if chart2 else None

# Approach 3: check what the Company doc default for existing_company is
import frappe
meta = frappe.get_meta("Company")
existing_co_field = meta.get_field("existing_company")
result["existing_company_field_default"] = existing_co_field.default if existing_co_field else "FIELD MISSING"
result["existing_company_field_options"] = existing_co_field.options if existing_co_field else None

# Approach 4: actually try create with EXPLICITLY existing_company=None and see what happens
# But don't actually insert — just simulate get_chart that would be used
test_co = frappe.new_doc("Company")
test_co.company_name = "S231-TEST-CHART-PROBE"
test_co.abbr = "STCP"
test_co.country = "Philippines"
test_co.default_currency = "PHP"
test_co.chart_of_accounts = "Standard"
result["test_company_existing_company_default"] = test_co.existing_company

# Don't insert; just inspect

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/chart_root_cause_probe.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str)[:6000])
	return 0


if __name__ == "__main__":
	sys.exit(main())
