#!/usr/bin/env python3
"""S231: probe BFC's chart structure to see if 6020602 ACCOUNTING FEES is leaf at root."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}

# Look at BFC's existing_company field
result["bfc_company"] = frappe.db.get_value(
    "Company", "BEBANG FRANCHISE CORP.",
    ["existing_company", "chart_of_accounts"],
    as_dict=True,
)
result["bei_company"] = frappe.db.get_value(
    "Company", "Bebang Enterprise Inc.",
    ["existing_company", "chart_of_accounts"],
    as_dict=True,
)

# Find any account named ACCOUNTING FEES across companies
acct = frappe.db.sql(
    '''SELECT name, account_number, company, parent_account, is_group, root_type
       FROM `tabAccount`
       WHERE account_number = '6020602' OR account_name LIKE '%ACCOUNTING FEES%'
       LIMIT 20''',
    as_dict=True,
)
result["accounting_fees_accounts"] = acct

# Check BFC's chart of accounts root structure
bfc_root_accounts = frappe.db.sql(
    '''SELECT name, account_number, is_group, parent_account, root_type
       FROM `tabAccount`
       WHERE company = 'BEBANG FRANCHISE CORP.'
       AND (parent_account IS NULL OR parent_account = '')
       ORDER BY name''',
    as_dict=True,
)
result["bfc_root_accounts"] = bfc_root_accounts

# Maybe the problem is how `existing_company` is being inferred. Check if there's a hook
# or logic that picks an existing_company when None is set.

# In ERPNext create_default_accounts, existing_company defaults to self.existing_company.
# If that's None, chart_of_accounts kicks in. Look at create_charts logic.
import inspect
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts
result["create_charts_signature"] = str(inspect.signature(create_charts))

# Check if BFC has 6020602 specifically
bfc_6020602 = frappe.db.sql(
    '''SELECT name, is_group, parent_account FROM `tabAccount`
       WHERE company = 'BEBANG FRANCHISE CORP.' AND account_number = '6020602' LIMIT 5''',
    as_dict=True,
)
result["bfc_6020602"] = bfc_6020602

# Check Company chart_of_accounts hooks that might modify behavior
from frappe.utils.deprecations import deprecation_warning
import importlib
result["hooks_for_account"] = {}
try:
    hooks_mod = importlib.import_module("hrms.hooks")
    result["hooks_for_account"] = {
        "doc_events_Account": hooks_mod.doc_events.get("Account"),
    }
except Exception as e:
    result["hooks_error"] = str(e)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/existing_company_chart_probe.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str)[:6000])
	return 0


if __name__ == "__main__":
	sys.exit(main())
