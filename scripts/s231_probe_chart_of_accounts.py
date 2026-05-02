#!/usr/bin/env python3
"""S231: probe chart_of_accounts values used by working parent Companies."""

from __future__ import annotations
import json, pathlib, sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

OUT = REPO_ROOT / "output" / "s231" / "verification" / "chart_of_accounts_probe.json"

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Probe a sample of working Companies
for cname in [
    "Bebang Enterprise Inc.",
    "BEBANG FRANCHISE CORP.",
    "BEBANG KITCHEN INC.",
    "BEBANG MEGA INC.",
]:
    if frappe.db.exists("Company", cname):
        result[cname] = frappe.db.get_value(
            "Company", cname,
            ["abbr", "chart_of_accounts", "country", "default_currency", "parent_company", "tax_id", "is_group"],
            as_dict=True,
        )

# Also list the chart files Frappe knows about for Philippines
import os
COA_DIRS = [
    "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/account/chart_of_accounts/verified/",
    "/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/account/chart_of_accounts/submitted/",
]
ph_charts = []
for d in COA_DIRS:
    if os.path.exists(d):
        for f in os.listdir(d):
            if "ph" in f.lower() or "philip" in f.lower():
                ph_charts.append(os.path.join(d, f))
result["philippine_charts_available"] = ph_charts

# Look at the actual chart Frappe will pick when chart_of_accounts is empty (Standard)
try:
    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import get_charts_for_country
    result["charts_for_philippines"] = get_charts_for_country("Philippines")
except Exception as e:
    result["get_charts_for_country_error"] = str(e)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	OUT.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str)[:3000])
	return 0


if __name__ == "__main__":
	sys.exit(main())
