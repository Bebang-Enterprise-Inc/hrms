#!/usr/bin/env python3
"""S231 Phase A-3: create `BEBANG FT INC.` parent legal-entity Company.

Production probe (`output/plan-audit/.../dep_production_state.json`) confirmed
this Company does NOT exist, but multiple per-store Companies (notably
`AYALA FAIRVIEW TERRACES - BEBANG FT INC.`) reference it as their
`parent_company`. Without it, those stores' default_* fields point at
ghost `- BFI2` Accounts that never get created via S181 templates.

This script creates the Company. The `on_update` hook then fires
`auto_provision_company` (now wrapped by S231-C1 atomicity) which runs
S181 balance-sheet + sales templates and creates the `- BFI2` Accounts.

IDEMPOTENT — exits cleanly if BEBANG FT INC. already exists.

Run:
    python scripts/s231_create_bebang_ft_inc_parent.py
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	PAYLOAD_PREAMBLE,
	decode_output,
	run_in_container,
)

OUT = REPO_ROOT / "output" / "s231" / "verification" / "bebang_ft_inc_creation_log.json"

CREATE_SCRIPT = (
	PAYLOAD_PREAMBLE
	+ """
already_exists = bool(frappe.db.exists("Company", "BEBANG FT INC."))
log = {
    "company": "BEBANG FT INC.",
    "abbr": "BFI2",
    "tax_id": "663-440-106-00000",
    "country": "Philippines",
    "default_currency": "PHP",
    "parent_company": "Bebang Enterprise Inc.",
    "already_existed": already_exists,
}

if not already_exists:
    # Skip auto_provision_company on first insert because S181's
    # _s181_apply_balance_sheet_template hits a chart-of-accounts
    # structural error on fresh BFI2 ("6020602 - ACCOUNTING FEES - BFI2
    # must be a group"). The C-1 atomicity wrapper rolls back the
    # savepoint cleanly when this happens, but the doc.insert call
    # still propagates the error. We use the in_install flag (which
    # auto_provision_company at company.py:742 honors as a skip
    # condition) to bypass the hook on first save, create the
    # Company shell, then call retry_provision_company manually
    # AFTER. If S181 still fails, the wrapper rolls back its own
    # savepoint but the Company shell is preserved.
    # ERPNext's Company.on_update calls self.create_default_accounts()
    # unless either frappe.flags.in_install_app is True OR self.flags.
    # country_change is True. We use country_change because it scopes
    # to this single doc and doesn't require setting global flags.
    # BEI's auto_provision_company is also skipped because we set
    # frappe.flags.in_install too (it checks in_install/in_migrate/
    # in_import at line 742).
    # ERPNext's Company.on_update calls create_default_accounts UNLESS
    # `frappe.local.flags.ignore_chart_of_accounts` is True (verified by
    # reading the ERPNext source on the live container). The chart
    # import path fails because BEI's existing Companies have malformed
    # root-level non-group accounts (e.g. "6020602 - ACCOUNTING FEES")
    # that get cloned into BFI2 and trip Account.validate_root_details.
    # We set ignore_chart_of_accounts=True to skip ERPNext's CoA
    # seeding entirely, create the Company shell, then run BEI's S181
    # templates manually via retry_provision_company AFTER.
    #
    # frappe.flags.in_install also skips BEI's auto_provision_company
    # (it short-circuits at company.py:742 when in_install is set).
    frappe.local.flags.ignore_chart_of_accounts = True
    frappe.flags.in_install = True
    try:
        co = frappe.new_doc("Company")
        co.company_name = "BEBANG FT INC."
        co.abbr = "BFI2"
        co.country = "Philippines"
        co.default_currency = "PHP"
        co.tax_id = "663-440-106-00000"
        if frappe.db.exists("Company", "Bebang Enterprise Inc."):
            co.parent_company = "Bebang Enterprise Inc."
        co.flags.ignore_permissions = True
        try:
            co.insert()
            frappe.db.commit()
            log["shell_created"] = True
        except Exception as ex:
            import traceback as _tb
            log["insert_failed"] = True
            log["insert_error"] = str(ex)[:1000]
            log["insert_traceback"] = _tb.format_exc()[:5000]
            try:
                frappe.db.rollback()
            except Exception:
                pass
    finally:
        frappe.local.flags.ignore_chart_of_accounts = False
        frappe.flags.in_install = False

    # Now attempt full provisioning. retry_provision_company resets
    # first_provision_done to 0 and re-fires auto_provision_company.
    # If it raises, the C-1 wrapper rolls back its own savepoint —
    # but the Company shell, which was committed BEFORE the retry,
    # survives. We catch + log + continue.
    try:
        from hrms.overrides.company import retry_provision_company
        retry_provision_company(company_name="BEBANG FT INC.")
        log["retry_provision_attempted"] = True
        log["retry_provision_succeeded"] = True
    except Exception as e:
        log["retry_provision_attempted"] = True
        log["retry_provision_succeeded"] = False
        log["retry_provision_error"] = str(e)[:500]
        try:
            frappe.db.rollback()
        except Exception:
            pass
    log["created"] = True
else:
    log["created"] = False

# Verify post-insert state
log["exists_after"] = bool(frappe.db.exists("Company", "BEBANG FT INC."))
log["first_provision_done"] = frappe.db.get_value(
    "Company", "BEBANG FT INC.", "first_provision_done"
)

# Verify key accounts created by the S181 templates via auto_provision_company
required_accounts = [
    f"{n} - BFI2" for n in [
        "Stock In Hand", "Payroll Payable", "Employee Advances",
        "Cash on Hand", "Debtors", "Creditors", "Cost of Goods Sold",
        "Round Off",
    ]
]
log["required_accounts"] = required_accounts
log["missing_accounts"] = [a for a in required_accounts if not frappe.db.exists("Account", a)]

# Capture every Account that does exist with `- BFI2` suffix for closeout audit
existing_bfi2_accounts = frappe.db.sql(
    "SELECT name FROM `tabAccount` WHERE name LIKE '%- BFI2'",
    as_dict=True,
)
log["existing_bfi2_accounts_count"] = len(existing_bfi2_accounts)
log["existing_bfi2_accounts_sample"] = [r["name"] for r in existing_bfi2_accounts[:20]]

_s231_emit(log)

frappe.destroy()
"""
)


def main() -> int:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	stdout = run_in_container(CREATE_SCRIPT, timeout=300)
	log = decode_output(stdout)
	OUT.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}")
	print(f"BEBANG FT INC. created={log['created']} exists_after={log['exists_after']}")
	print(f"first_provision_done={log['first_provision_done']}")
	print(f"existing_bfi2_accounts_count={log['existing_bfi2_accounts_count']}")
	if log["missing_accounts"]:
		print(f"WARN missing accounts: {log['missing_accounts']}")
		return 2
	return 0


if __name__ == "__main__":
	sys.exit(main())
