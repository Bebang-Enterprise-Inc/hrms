#!/usr/bin/env python3
"""S231: probe what chart Standard returns and find 6020602."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import get_chart

# Walk the Standard chart and find the offender
def find_account(chart, target_num, path=""):
    found = []
    if isinstance(chart, dict):
        for key, value in chart.items():
            current_path = f"{path} > {key}" if path else key
            if target_num in key:
                node_info = {
                    "path": current_path,
                    "key": key,
                    "is_group": value.get("is_group") if isinstance(value, dict) else None,
                    "account_number": value.get("account_number") if isinstance(value, dict) else None,
                    "has_children": isinstance(value, dict) and any(isinstance(v, dict) for v in value.values()),
                    "children_count": sum(1 for v in value.values() if isinstance(v, dict)) if isinstance(value, dict) else 0,
                }
                found.append(node_info)
            if isinstance(value, dict):
                found.extend(find_account(value, target_num, current_path))
    return found

# Try Standard chart
try:
    chart = get_chart("Standard")
    result["standard_chart_top_keys"] = list(chart.keys())[:20]
    result["standard_6020602"] = find_account(chart, "6020602")
except Exception as e:
    result["standard_error"] = str(e)

# Try Standard with Numbers
try:
    chart = get_chart("Standard with Numbers")
    result["std_with_numbers_top_keys"] = list(chart.keys())[:20]
    result["std_with_numbers_6020602"] = find_account(chart, "6020602")
except Exception as e:
    result["std_with_numbers_error"] = str(e)

# Try get_chart with the hint that's used when chart_of_accounts is None
try:
    chart = get_chart(None)
    result["default_chart_returned_anything"] = chart is not None
except Exception as e:
    result["default_error"] = str(e)

# Pull raw chart JSON paths from ERPNext app
import os
COA_BASE = "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/account/chart_of_accounts"
for sub in ["verified", "submitted"]:
    d = os.path.join(COA_BASE, sub)
    if os.path.exists(d):
        result.setdefault("chart_files", {})[sub] = sorted(os.listdir(d))[:30]

# Search for 6020602 in any chart file
hits = []
for sub in ["verified", "submitted"]:
    d = os.path.join(COA_BASE, sub)
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        path = os.path.join(d, f)
        try:
            content = open(path).read()
            if "6020602" in content or "ACCOUNTING FEES" in content:
                hits.append({"file": path, "has_6020602": "6020602" in content, "has_accounting_fees": "ACCOUNTING FEES" in content})
        except Exception:
            pass
result["files_with_6020602_or_ACCOUNTING_FEES"] = hits

# Also search the whole apps tree for "6020602 - ACCOUNTING FEES"
import subprocess
try:
    grep_result = subprocess.run(
        ["grep", "-rln", "6020602", "/home/frappe/frappe-bench/apps/"],
        capture_output=True, text=True, timeout=30
    )
    result["grep_6020602_files"] = grep_result.stdout.strip().split("\\n")[:20]
except Exception as e:
    result["grep_error"] = str(e)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/standard_chart_probe.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str)[:4000])
	return 0


if __name__ == "__main__":
	sys.exit(main())
