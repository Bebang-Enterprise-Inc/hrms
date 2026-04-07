from __future__ import annotations

import sys

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

# Frappe Error Log "Title" field is capped at 140 chars. Keep all titles short.
_LOG_TITLE = "Marketing Giveaway Skip"


def _safe_log(message: str) -> None:
	"""Log a skip/warn without ever raising.

	frappe.log_error signature in Frappe v15 is log_error(title, message) with
	title first. The Title field is capped at 140 chars. If anything in this
	logging path raises, we fall back to stderr — the patch must NEVER block
	migrate just because it couldn't write an error log row.
	"""
	try:
		frappe.log_error(title=_LOG_TITLE, message=message)
	except Exception:
		try:
			sys.stderr.write(f"[{_LOG_TITLE}] {message}\n")
		except Exception:
			pass


def _ensure_role(role_name: str) -> None:
	if frappe.db.exists("Role", role_name):
		return
	doc = frappe.new_doc("Role")
	doc.role_name = role_name
	doc.desk_access = 0
	doc.insert(ignore_permissions=True)


def _ensure_roles() -> None:
	for role_name in ROLE_NAMES:
		try:
			_ensure_role(role_name)
		except Exception as exc:
			_safe_log(f"role {role_name} failed: {exc}")


def _ensure_account_for_company(company: str) -> None:
	"""Create 6005001 MARKETING GIVEAWAYS for `company` if safe.

	Swallows all exceptions — this is a one-time idempotent data setup patch
	that must never block migrate. On any failure, logs a short skip entry
	and returns.
	"""
	try:
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
			_safe_log(f"no {SOURCE_ACCOUNT_NUMBER} on {company}; skipping.")
			return

		source_account = frappe.get_doc("Account", source_account_name)

		# DEFENSIVE: parent must exist and be a group. Otherwise skip.
		parent_account_name = source_account.parent_account
		if not parent_account_name:
			_safe_log(
				f"{source_account_name} on {company} has no parent; skipping {TARGET_ACCOUNT_NUMBER}."
			)
			return

		parent_is_group = frappe.db.get_value("Account", parent_account_name, "is_group")
		if not parent_is_group:
			_safe_log(
				f"parent {parent_account_name} on {company} is a ledger not group; skipping."
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
	except Exception as exc:
		_safe_log(f"{company} insert failed: {str(exc)[:80]}")


def _ensure_accounts() -> None:
	# Marketing giveaway GL belongs to BEI head office ONLY. Do NOT create on
	# BKI / JV / any other subsidiary — marketing is a centralized BEI function
	# (CEO directive 2026-04-07). Looping over all companies previously blocked
	# every migrate when one subsidiary's source account was misconfigured.
	try:
		if frappe.db.exists("Company", MARKETING_COMPANY):
			_ensure_account_for_company(MARKETING_COMPANY)
		else:
			_safe_log(f"Company {MARKETING_COMPANY} not found; skipping.")
	except Exception as exc:
		_safe_log(f"_ensure_accounts top-level: {str(exc)[:80]}")


def execute():
	try:
		_ensure_roles()
	except Exception as exc:
		_safe_log(f"_ensure_roles failed: {str(exc)[:80]}")
	try:
		_ensure_accounts()
	except Exception as exc:
		_safe_log(f"_ensure_accounts failed: {str(exc)[:80]}")
	try:
		frappe.clear_cache()
	except Exception:
		pass
