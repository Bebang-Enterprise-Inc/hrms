from __future__ import annotations

import frappe

ROLE_NAMES = ("Marketing User", "Marketing Manager")
SOURCE_ACCOUNT_NUMBER = "6005000"
TARGET_ACCOUNT_NUMBER = "6005001"
TARGET_ACCOUNT_NAME = "MARKETING GIVEAWAYS"


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
	account = frappe.new_doc("Account")
	account.company = company
	account.account_name = TARGET_ACCOUNT_NAME
	account.account_number = TARGET_ACCOUNT_NUMBER
	account.parent_account = source_account.parent_account
	account.root_type = source_account.root_type
	account.report_type = source_account.report_type
	account.is_group = 0
	if hasattr(source_account, "account_type"):
		account.account_type = source_account.account_type
	account.insert(ignore_permissions=True)


def _ensure_accounts() -> None:
	companies = frappe.get_all("Company", fields=["name"], limit_page_length=200)
	for row in companies:
		name = str(row.get("name") or "").strip()
		if name:
			_ensure_account_for_company(name)


def execute():
	_ensure_roles()
	_ensure_accounts()
	frappe.clear_cache()
