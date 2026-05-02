#!/usr/bin/env python3
"""S231: read ERPNext Company.on_update source to find the actual skip conditions."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
import inspect
from erpnext.setup.doctype.company.company import Company
src = inspect.getsource(Company.on_update)
result["on_update_source"] = src

src2 = inspect.getsource(Company.create_default_accounts)
result["create_default_accounts_source"] = src2

# Check if there's a way to suppress via flag
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import get_chart, create_charts
result["create_charts_source"] = inspect.getsource(create_charts)
result["get_chart_source"] = inspect.getsource(get_chart)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/erpnext_on_update_source.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print("=== on_update ===")
	print(data["on_update_source"][:2000])
	print("\n=== create_default_accounts ===")
	print(data["create_default_accounts_source"][:2500])
	print("\n=== get_chart ===")
	print(data["get_chart_source"][:2500])
	return 0


if __name__ == "__main__":
	sys.exit(main())
