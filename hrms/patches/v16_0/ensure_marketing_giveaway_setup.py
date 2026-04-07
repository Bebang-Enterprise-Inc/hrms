from __future__ import annotations

import frappe

ROLE_NAMES = ("Marketing User", "Marketing Manager")
SOURCE_ACCOUNT_NUMBER = "6005000"
TARGET_ACCOUNT_NUMBER = "6005001"
TARGET_ACCOUNT_NAME = "MARKETING GIVEAWAYS"
# Marketing is a centralized BEI head office function — the giveaway GL account
# belongs ONLY to BEI, not to BKI / JV / any subsidiary. Looping over all
# companies previously blocked every migrate when the JV company's source
# account 6005000 was parented under a ledger account (CEO directive 2026-04-07).
MARKETING_COMPANY = "Bebang Enterprise Inc."


def _ensure_role(role_name: str) -> None:
	if frappe.db.exists("Role", role_name):
		return
	doc = frappe.new_doc("Role")
	doc.role_name = role_name
	doc.desk_access = 0
	doc.insert(ignore_permissions=True)


def _ensure_roles() -> None:
	for role_name in ROLE_NAMES:
		_ensure_role(role_name)


def _ensure_account_for_company(company: str) -> None:
	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_number": TARGET_ACCOUNT_NUMBER},
		"name",
	)
	if existing:
		return

	source_account_name = frappe.db.get_value(
		"Account",
		{"company": company, "account_number": SOURCE_ACCOUNT_NUMBER},
		"name",
	)
	if not source_account_name:
		return

	source_account = frappe.get_doc("Account", source_account_name)

	# DEFENSIVE: validate parent is a group before inserting. A single
	# misconfigured source account must never block the entire migrate
	# pipeline. Log-and-skip is the correct behavior here; Finance can
	# fix the underlying COA data out-of-band.
	parent_account_name = source_account.parent_account
	if not parent_account_name:
		frappe.log_error(
			f"ensure_marketing_giveaway_setup: source account {source_account_name} "
			f"on {company} has no parent_account; skipping {TARGET_ACCOUNT_NUMBER} creation.",
			"Marketing Giveaway Patch Skip",
		)
		return

	parent_is_group = frappe.db.get_value("Account", parent_account_name, "is_group")
	if not parent_is_group:
		frappe.log_error(
			f"ensure_marketing_giveaway_setup: parent {parent_account_name} "
			f"(on {company}, derived from source {source_account_name}) is a ledger "
			f"account, not a group. Cannot create child {TARGET_ACCOUNT_NUMBER}. "
			f"Fix COA: either convert {parent_account_name} to a group (if empty) or "
			f"move {source_account_name} under the correct expense group.",
			"Marketing Giveaway Patch Skip",
		)
		return

	account = frappe.new_doc("Account")
	account.company = company
	account.account_name = TARGET_ACCOUNT_NAME
	account.account_number = TARGET_ACCOUNT_NUMBER
	account.parent_account = parent_account_name
	account.root_type = source_account.root_type
	account.report_type = source_account.report_type
	account.is_group = 0
	if hasattr(source_account, "account_type"):
		account.account_type = source_account.account_type
	account.insert(ignore_permissions=True)


def _ensure_accounts() -> None:
	# Marketing giveaway GL belongs to BEI head office ONLY. Do NOT create on
	# BKI / JV / any other subsidiary — marketing is a centralized BEI function
	# (CEO directive 2026-04-07). Looping over all companies previously blocked
	# every migrate when one subsidiary's source account was misconfigured.
	if frappe.db.exists("Company", MARKETING_COMPANY):
		_ensure_account_for_company(MARKETING_COMPANY)
	else:
		frappe.log_error(
			f"ensure_marketing_giveaway_setup: Company '{MARKETING_COMPANY}' not found; "
			"marketing giveaway GL not created. If BEI head office company was renamed, "
			"update MARKETING_COMPANY in this patch.",
			"Marketing Giveaway Patch Skip",
		)


def execute():
	_ensure_roles()
	_ensure_accounts()
	frappe.clear_cache()
