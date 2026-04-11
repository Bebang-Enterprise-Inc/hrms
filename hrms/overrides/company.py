# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import csv
import json
import os

import frappe
from frappe import _

from erpnext.accounts.doctype.account.account import get_account_currency


def make_company_fixtures(doc, method=None):
	if not frappe.flags.country_change:
		return

	run_regional_setup(doc.country)
	make_salary_components(doc.country)


def delete_company_fixtures():
	countries = frappe.get_all(
		"Company",
		distinct="True",
		pluck="country",
	)

	for country in countries:
		try:
			module_name = f"hrms.regional.{frappe.scrub(country)}.setup.uninstall"
			frappe.get_attr(module_name)()
		except (ImportError, AttributeError):
			# regional file or method does not exist
			pass
		except Exception as e:
			frappe.log_error("Unable to delete country fixtures for Frappe HR")
			msg = _("Failed to delete defaults for country {0}.").format(frappe.bold(country))
			msg += "<br><br>" + _("{0}: {1}").format(frappe.bold(_("Error")), get_error_message(e))
			frappe.throw(msg, title=_("Country Fixture Deletion Failed"))


def run_regional_setup(country):
	try:
		module_name = f"hrms.regional.{frappe.scrub(country)}.setup.setup"
		frappe.get_attr(module_name)()
	except ImportError:
		pass
	except Exception as e:
		frappe.log_error("Unable to setup country fixtures for Frappe HR")
		msg = _("Failed to setup defaults for country {0}.").format(frappe.bold(country))
		msg += "<br><br>" + _("{0}: {1}").format(frappe.bold(_("Error")), get_error_message(e))
		frappe.throw(msg, title=_("Country Setup failed"))


def get_error_message(error) -> str:
	try:
		message_log = frappe.message_log.pop() if frappe.message_log else str(error)
		if isinstance(message_log, str):
			error_message = json.loads(message_log).get("message")
		else:
			error_message = message_log.get("message")
	except Exception:
		error_message = message_log

	return error_message


def make_salary_components(country):
	docs = []

	file_name = "salary_components.json"

	# default components already added
	if not frappe.db.exists("Salary Component", "Basic"):
		file_path = frappe.get_app_path("hrms", "payroll", "data", file_name)
		docs.extend(json.loads(read_data_file(file_path)))

	file_path = frappe.get_app_path("hrms", "regional", frappe.scrub(country), "data", file_name)
	docs.extend(json.loads(read_data_file(file_path)))

	for d in docs:
		try:
			doc = frappe.get_doc(d)
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert(ignore_if_duplicate=True)
		except frappe.NameError:
			frappe.clear_messages()
		except frappe.DuplicateEntryError:
			frappe.clear_messages()


def read_data_file(file_path):
	try:
		with open(file_path) as f:
			return f.read()
	except OSError:
		return "{}"


def set_default_hr_accounts(doc, method=None):
	if frappe.local.flags.ignore_chart_of_accounts:
		return

	if not doc.default_payroll_payable_account:
		payroll_payable_account = frappe.db.get_value(
			"Account", {"account_name": _("Payroll Payable"), "company": doc.name, "is_group": 0}
		)

		doc.db_set("default_payroll_payable_account", payroll_payable_account)

	if not doc.default_employee_advance_account:
		employe_advance_account = frappe.db.get_value(
			"Account", {"account_name": _("Employee Advances"), "company": doc.name, "is_group": 0}
		)

		doc.db_set("default_employee_advance_account", employe_advance_account)


def validate_default_accounts(doc, method=None):
	if doc.default_payroll_payable_account:
		for_company = frappe.db.get_value("Account", doc.default_payroll_payable_account, "company")
		if for_company != doc.name:
			frappe.throw(
				_("Account {0} does not belong to company: {1}").format(
					doc.default_payroll_payable_account, doc.name
				)
			)

		if get_account_currency(doc.default_payroll_payable_account) != doc.default_currency:
			frappe.throw(
				_(
					"The currency of {0} should be same as the company's default currency. Please select another account."
				).format(frappe.bold(_("Default Payroll Payable Account")))
			)


def handle_linked_docs(doc, method=None):
	delete_docs_with_company_field(doc)
	clear_company_field_for_single_doctypes(doc)


def delete_docs_with_company_field(doc, method=None):
	"""
	Deletes records from linked doctypes where the 'company' field matches the company's name
	"""
	company_data_to_be_ignored = frappe.get_hooks("company_data_to_be_ignored") or []
	for doctype in company_data_to_be_ignored:
		records_to_delete = frappe.get_all(doctype, filters={"company": doc.name}, pluck="name")
		if records_to_delete:
			frappe.db.delete(doctype, {"name": ["in", records_to_delete]})


def clear_company_field_for_single_doctypes(doc):
	"""
	Clears the 'company' value in Single doctypes where applicable
	"""
	single_docs = get_single_doctypes_with_company_field()
	singles = frappe.qb.DocType("Singles")
	(
		frappe.qb.update(singles)
		.set(singles.value, "")
		.where(singles.doctype.isin(single_docs))
		.where(singles.field == "company")
		.where(singles.value == doc.name)
	).run()


def get_single_doctypes_with_company_field():
	DocType = frappe.qb.DocType("DocType")
	DocField = frappe.qb.DocType("DocField")

	return (
		frappe.qb.from_(DocField)
		.select(DocField.parent)
		.where(
			(DocField.fieldtype == "Link")
			& (DocField.options == "Company")
			& (
				DocField.parent.isin(
					frappe.qb.from_(DocType)
					.select(DocType.name)
					.where((DocType.issingle == 1) & (DocType.module.isin(["HR", "Payroll"])))
				)
			)
		)
	).run(pluck=True)


# ============================================================================
# S181 Company Master Extension: auto-provision on first Company save
# ----------------------------------------------------------------------------
# Registered via hooks.py doc_events:
#   "Company": {
#       "on_update": [
#           ...existing entries...,
#           "hrms.overrides.company.auto_provision_company",
#           "hrms.overrides.company.auto_enroll_adms_devices",
#       ]
#   }
#
# auto_provision_company is sentinel-gated by the `first_provision_done`
# Custom Field (added in Phase 1 Section 7), so it runs exactly once per
# Company, AFTER ERPNext's own create_default_accounts / create_default_
# warehouses / create_default_cost_center have populated the standard COA
# skeleton (Blocker 9 lifecycle fix).
#
# It is also guarded against bulk-import / migration (Blocker 13) to avoid
# triggering mass account creation during `bench migrate` or
# frappe.client.insert_many-style flows.
# ============================================================================


# The 27-account Sales template. Canonical from S175 — DO NOT modify without
# also updating scripts/s175_master_coa_template.py (HB-1 lock).
_MASTER_SALES_TEMPLATE = [
	# (number, name, parent_number, is_group, root_type, account_type)
	("4000000", "SALES", None, 1, "Income", None),
	("4000100", "STORE SALES", "4000000", 1, "Income", None),
	("4000110", "IN-STORE SALES", "4000100", 0, "Income", "Income Account"),
	("4000120", "ONLINE SALES", "4000100", 1, "Income", None),
	("4000121", "BEI WEBSITE", "4000120", 0, "Income", "Income Account"),
	("4000122", "FOOD PANDA", "4000120", 0, "Income", "Income Account"),
	("4000123", "GRAB", "4000120", 0, "Income", "Income Account"),
	("4000200", "BKI SALES", "4000000", 1, "Income", None),
	("4000210", "DELIVERIES", "4000200", 0, "Income", "Income Account"),
	("4000220", "LOGISTICS", "4000200", 1, "Income", None),
	("4000221", "DELIVERY INCOME", "4000220", 0, "Income", "Income Account"),
	("4000222", "LOGISTICS INCOME", "4000220", 0, "Income", "Income Account"),
	("4000230", "FEES", "4000000", 1, "Income", None),
	("4000231", "ROYALTY FEES", "4000230", 0, "Income", "Income Account"),
	("4000232", "MANAGEMENT FEES", "4000230", 0, "Income", "Income Account"),
	("4000233", "FRANCHISE FEES", "4000230", 0, "Income", "Income Account"),
	("4000234", "MARKETING FEES", "4000230", 0, "Income", "Income Account"),
	("4000235", "E-COMMERCE FEES", "4000230", 0, "Income", "Income Account"),
	("4000900", "DISCOUNTS AND PROMO", "4000000", 1, "Income", None),
	("4000901", "SALES DISCOUNT DUE TO FREE HALOHALO", "4000900", 0, "Income", "Income Account"),
	("4000902", "SALES DISCOUNT OF SENIOR CITIZENS", "4000900", 0, "Income", "Income Account"),
	("4000903", "SALES DISCOUNTS OF PWDS", "4000900", 0, "Income", "Income Account"),
	("4000904", "SALES DISCOUNTS OF STAFFS AND EMPLOYEES", "4000900", 0, "Income", "Income Account"),
	("4000905", "SALES DISCOUNTS FROM VAT OF PWD", "4000900", 0, "Income", "Income Account"),
	("4000906", "SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS", "4000900", 0, "Income", "Income Account"),
	("4000907", "SALES REFUNDS TO CUSTOMER", "4000900", 0, "Income", "Income Account"),
	("4000908", "SALES DISCOUNTS - EMPLOYEE DISC", "4000900", 0, "Income", "Income Account"),
]
assert len(_MASTER_SALES_TEMPLATE) == 27, "S181 HB-1: MASTER_SALES_TEMPLATE row count must be 27"


# Balance Sheet + Expense skeleton. Added in S181 per audit Blocker 5/9 fix —
# guarantees Debtors / Creditors / Cost of Goods Sold / Round Off / Cash exist
# on every newly provisioned Company, independent of whether ERPNext's Standard
# Template ran first. Idempotent: `_s181_ensure_account` re-uses existing rows
# by (company, account_number) match, so this will not duplicate accounts
# ERPNext may have already created.
_MASTER_BALANCE_SHEET_TEMPLATE = [
	# ----- ASSETS -----
	("1000000", "ASSETS", None, 1, "Asset", None),
	("1100000", "CURRENT ASSETS", "1000000", 1, "Asset", None),
	("1110000", "CASH AND EQUIVALENTS", "1100000", 1, "Asset", None),
	("1110100", "CASH ON HAND", "1110000", 0, "Asset", "Cash"),
	("1110200", "CASH IN BANK", "1110000", 0, "Asset", "Bank"),
	("1120000", "ACCOUNTS RECEIVABLE", "1100000", 1, "Asset", None),
	("1120100", "Debtors", "1120000", 0, "Asset", "Receivable"),
	("1130000", "INVENTORY", "1100000", 0, "Asset", "Stock"),
	# ----- LIABILITIES -----
	("2000000", "LIABILITIES", None, 1, "Liability", None),
	("2100000", "CURRENT LIABILITIES", "2000000", 1, "Liability", None),
	("2110000", "ACCOUNTS PAYABLE", "2100000", 1, "Liability", None),
	("2110100", "Creditors", "2110000", 0, "Liability", "Payable"),
	("2120000", "ROUND OFF", "2100000", 0, "Liability", "Round Off"),
	# ----- EQUITY -----
	("3000000", "EQUITY", None, 1, "Equity", None),
	("3100000", "Retained Earnings", "3000000", 0, "Equity", None),
	# ----- EXPENSES -----
	("5000000", "EXPENSES", None, 1, "Expense", None),
	("5100000", "COST OF GOODS SOLD (GROUP)", "5000000", 1, "Expense", None),
	("5100100", "Cost of Goods Sold", "5100000", 0, "Expense", "Cost of Goods Sold"),
	("5200000", "OPERATING EXPENSES", "5000000", 1, "Expense", None),
	("5200100", "Stock Adjustment", "5200000", 0, "Expense", "Stock Adjustment"),
]
assert len(_MASTER_BALANCE_SHEET_TEMPLATE) == 20, "S181: balance sheet template row count must be 20"


def _s181_ensure_account(company, number, name, parent_number, is_group, root_type, account_type):
	"""Idempotent account creation. Reuses the S175 ensure_account pattern.

	- If account exists by (company, account_number): verify is_group match,
	  fix root_type via UPDATE if it drifted, return existing name.
	- If account missing: resolve parent (by parent_number within the same
	  company, or the company's root group for root-level accounts) and
	  frappe.new_doc("Account") it.
	"""
	if parent_number is None:
		# Root-level account — find the company's root group for this root_type
		parent_name = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"root_type": root_type,
				"is_group": 1,
				"parent_account": ["in", ["", None]],
			},
			"name",
		)
		if not parent_name:
			# No existing root for this root_type on this company — create a
			# new root account with parent_account=None. ERPNext will accept
			# this because ignore_root_company_validation is already set by
			# the caller.
			root = frappe.new_doc("Account")
			root.account_name = name
			root.account_number = number
			root.company = company
			root.parent_account = ""
			root.is_group = 1
			root.root_type = root_type
			root.flags.ignore_permissions = True
			root.flags.ignore_mandatory = True
			root.insert()
			return root.name
	else:
		parent_name = frappe.db.get_value(
			"Account",
			{"company": company, "account_number": parent_number},
			"name",
		)
		if not parent_name:
			frappe.throw(
				f"S181: parent account {parent_number} not found for {company}"
			)

	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_number": number},
		["name", "is_group", "root_type"],
		as_dict=True,
	)

	if existing:
		if int(existing.is_group) != int(is_group):
			frappe.throw(
				f"S181: account {number} on {company} has is_group={existing.is_group}, "
				f"expected {is_group}"
			)
		if existing.root_type != root_type:
			frappe.db.sql(
				"UPDATE `tabAccount` SET root_type=%s WHERE name=%s",
				(root_type, existing.name),
			)
		return existing.name

	acc = frappe.new_doc("Account")
	acc.account_name = name
	acc.account_number = number
	acc.company = company
	acc.parent_account = parent_name
	acc.is_group = is_group
	acc.root_type = root_type
	if account_type:
		acc.account_type = account_type
	acc.flags.ignore_permissions = True
	acc.flags.ignore_mandatory = True
	acc.insert()
	return acc.name


def _s181_apply_sales_template(doc):
	"""Apply the locked 27-account Sales template to a newly provisioned Company."""
	for number, name, parent_number, is_group, root_type, account_type in _MASTER_SALES_TEMPLATE:
		_s181_ensure_account(doc.name, number, name, parent_number, is_group, root_type, account_type)


def _s181_apply_balance_sheet_template(doc):
	"""Apply the Asset/Liability/Equity/Expense skeleton.

	Guarantees that `_s181_set_default_accounts` can find its targets even
	if ERPNext's Standard Template hasn't populated them under the same
	account numbers yet.
	"""
	for number, name, parent_number, is_group, root_type, account_type in _MASTER_BALANCE_SHEET_TEMPLATE:
		_s181_ensure_account(doc.name, number, name, parent_number, is_group, root_type, account_type)


def _s181_ensure_warehouse(doc):
	"""Create the default S181 branch warehouse if it does not already exist."""
	wh_name = f"{doc.name} - {doc.abbr}"
	if frappe.db.exists("Warehouse", wh_name):
		return
	wh = frappe.new_doc("Warehouse")
	wh.warehouse_name = doc.name
	wh.company = doc.name
	wh.is_group = 0
	wh.flags.ignore_permissions = True
	wh.insert()


def _s181_ensure_cost_center(doc):
	"""Create the default S181 branch cost center if it does not already exist."""
	cc_name = f"{doc.name} - {doc.abbr}"
	if frappe.db.exists("Cost Center", cc_name):
		return
	cc = frappe.new_doc("Cost Center")
	cc.cost_center_name = doc.name
	cc.company = doc.name
	cc.is_group = 0
	cc.flags.ignore_permissions = True
	cc.insert()


def _s181_set_default_accounts(doc):
	"""Set default income / expense / receivable / payable / round-off / cash.

	Blocker 5 fix: this used to silently no-op because Debtors / Creditors /
	Cost of Goods Sold were assumed to come from ERPNext's Standard Template
	that had not run yet at `after_insert` time. With the lifecycle moved to
	`on_update` + sentinel AND `_s181_apply_balance_sheet_template` running
	earlier in `auto_provision_company`, the required accounts are guaranteed
	to exist by the time this helper runs.

	If any required default is still missing, this raises — triggering the
	savepoint rollback in the caller instead of a silently half-provisioned
	company.
	"""
	# Default income account = IN-STORE SALES (most common revenue posting)
	income_account = frappe.db.get_value(
		"Account", {"company": doc.name, "account_number": "4000110"}, "name"
	)
	if income_account:
		doc.db_set("default_income_account", income_account)

	# Tolerant lookup — try S181's numbered accounts first, fall back to
	# ERPNext Standard Template name-based matches for anything not in the
	# S181 balance-sheet template.
	default_map = [
		("default_receivable_account", ["1120100"], ["Debtors"]),
		("default_payable_account", ["2110100"], ["Creditors"]),
		("default_expense_account", ["5100100"], ["Cost of Goods Sold"]),
		("round_off_account", ["2120000"], ["Round Off"]),
		("default_cash_account", ["1110100"], ["Cash", "Cash On Hand"]),
	]
	missing = []
	for field, numbers, names in default_map:
		account = None
		for num in numbers:
			account = frappe.db.get_value(
				"Account",
				{"company": doc.name, "account_number": num, "is_group": 0},
				"name",
			)
			if account:
				break
		if not account:
			for nm in names:
				account = frappe.db.get_value(
					"Account",
					{"company": doc.name, "account_name": nm, "is_group": 0},
					"name",
				)
				if account:
					break
		if account:
			doc.db_set(field, account)
		else:
			missing.append(field)

	if missing:
		frappe.throw(
			f"S181 _s181_set_default_accounts: missing required default accounts "
			f"on {doc.name}: {missing}. Check that _s181_apply_balance_sheet_template "
			f"ran successfully."
		)


# --- S037 register paths used by _s181_ensure_bki_customer (Blocker 4 fix) ---
# Resolved relative to the hrms app so the helper works in Docker and on local
# benches without depending on CWD.
_S037_REGISTER_RELPATH = (
	"2026-03-12-s037-store-buyer-entity-register",
	"store_buyer_entity_register_2026-03-12.csv",
)
_ENTITY_TIN_RDO_RELPATH = (
	"batch_2026-02-28_cleanroom_v1",
	"raw_snapshot",
	"ENTITY_TIN_RDO_2026-02-27.csv",
)


def _s181_ensure_bki_customer(doc):
	"""Ensure a BKI Customer exists for this Company, matching S168 conventions.

	Blocker 4 fix: S168's `build_bki_store_sale_invoice` in
	`hrms/api/commissary.py:1027-1050` looks up the Customer via
	`frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, ...)`
	— where `buyer_entity_name` comes from the S037 register, NOT the Frappe
	Company docname. 48 stores map to only 38 unique buyer entities, so the
	Customer is shared across stores within the same buyer entity group.

	This helper:
	  1. Resolves the buyer_entity_name for `doc` via the S037 register
	     (matching by store_name OR warehouse_docname).
	  2. If not found, logs INFO and skips — non-store entities (head office,
	     commissary, holding, franchisor) do not need a BKI Customer.
	  3. If found, looks up tax details in the ENTITY_TIN_RDO register by
	     Entity Name = buyer_entity_name and copies tax_id / custom_bir_rdo_code
	     / custom_vat_status onto the Customer.
	  4. Creates the Customer with customer_name = buyer_entity_name (NOT
	     doc.name), customer_group = "BKI Store", territory = "Philippines".
	  5. De-dups: if a Customer with the same customer_name already exists,
	     does nothing (shared across stores in the same buyer entity group).
	"""
	app_path = frappe.get_app_path("hrms", "..", "data", "_CLEANROOM")
	s037_path = os.path.normpath(os.path.join(app_path, *_S037_REGISTER_RELPATH))
	tin_register_path = os.path.normpath(os.path.join(app_path, *_ENTITY_TIN_RDO_RELPATH))

	if not os.path.exists(s037_path):
		frappe.log_error(
			title="S181 _s181_ensure_bki_customer: S037 register missing",
			message=f"Cannot resolve BKI Customer for {doc.name} — register not found at {s037_path}",
		)
		return

	# Step 1: find this Company in S037 by store_name OR warehouse_docname
	buyer_row = None
	with open(s037_path, encoding="utf-8-sig") as f:
		for row in csv.DictReader(f):
			wh_docname = (row.get("warehouse_docname") or "").strip()
			store_name = (row.get("store_name") or "").strip()
			if wh_docname == doc.name or store_name == doc.name:
				buyer_row = row
				break

	if not buyer_row:
		# Non-store entities do not need a BKI Customer — skip gracefully
		frappe.logger().info(
			f"S181 _s181_ensure_bki_customer: {doc.name} not in S037 register — "
			f"skipping BKI Customer (expected for non-store entities)"
		)
		return

	buyer_entity_name = (buyer_row.get("buyer_entity_name") or "").strip()
	if not buyer_entity_name:
		frappe.log_error(
			title="S181 _s181_ensure_bki_customer: empty buyer_entity_name",
			message=f"Row for {doc.name} has no buyer_entity_name: {buyer_row}",
		)
		return

	# Step 2: idempotent — if Customer already exists, don't duplicate.
	# Shared across stores that map to the same buyer entity (by design).
	existing = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
	if existing:
		return

	# Step 3: look up tax details from ENTITY_TIN_RDO (optional — not every entity has them)
	tax_id = None
	rdo = None
	vat_status = None
	if os.path.exists(tin_register_path):
		with open(tin_register_path, encoding="utf-8-sig") as f:
			for row in csv.DictReader(f):
				entity_name = (row.get("Entity Name") or "").strip()
				if entity_name == buyer_entity_name:
					tax_id = (row.get("TIN") or "").strip() or None
					rdo = (row.get("RDO Code") or "").strip() or None
					vat_status = (row.get("VAT Status") or "").strip() or None
					break

	# Step 4: create Customer with the correct naming convention
	customer = frappe.new_doc("Customer")
	customer.customer_name = buyer_entity_name
	customer.customer_type = "Company"
	customer.customer_group = "BKI Store"
	customer.territory = "Philippines"
	customer.default_currency = "PHP"
	if tax_id:
		customer.tax_id = tax_id
	# Only set custom fields if they exist on the Customer DocType — S168
	# added `custom_vat_status` and `custom_bir_rdo_code` to Customer, but be
	# defensive in case of ordering / older environments.
	meta = frappe.get_meta("Customer")
	if rdo and meta.has_field("custom_bir_rdo_code"):
		customer.custom_bir_rdo_code = rdo
	if vat_status and meta.has_field("custom_vat_status"):
		customer.custom_vat_status = vat_status
	customer.flags.ignore_permissions = True
	customer.flags.ignore_mandatory = True
	customer.insert()


def auto_provision_company(doc, method=None):
	"""Auto-provision COA, Warehouse, Cost Center, default accounts, BKI Customer.

	Registered as a Company `on_update` doc_event in hrms/hooks.py. Fires
	exactly once per Company, gated by the `first_provision_done` Custom
	Field sentinel added in Phase 1 Section 7 (Blocker 9 fix).

	Guards:
	- Skipped during `frappe.flags.in_import / in_migrate / in_install`
	  (Blocker 13 — bulk imports would otherwise trigger 27 × N account
	  creations).
	- Skipped when `first_provision_done == 1` (idempotency sentinel).

	Atomicity:
	- Uses `frappe.db.savepoint()` so any failure leaves the Company record
	  saved but rolls back the S181 provisioning work. The operator can then
	  click "Retry Provisioning" (Desk button or bei-tasks pill, both wired
	  in Task 2.4) to re-run.

	Sentry:
	- Tagged via `set_backend_observability_context(module='company',
	  action='auto_provision_company', mutation_type='create', extras={...})`
	  per DM-7.
	"""
	# Blocker 13 guard: skip during bulk-import / migration / install
	if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_install:
		return

	# Blocker 9 sentinel: only run once per Company.
	# Use has_field guard so this is a no-op on environments where the Phase 1
	# fixture has not yet been migrated.
	company_meta = frappe.get_meta("Company")
	if not company_meta.has_field("first_provision_done"):
		return
	if frappe.db.get_value("Company", doc.name, "first_provision_done"):
		return

	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="company",
		action="auto_provision_company",
		mutation_type="create",
		extras={"company": doc.name, "abbr": doc.abbr},
	)

	try:
		frappe.db.savepoint("s181_auto_provision")

		# Bypass ERPNext group-company validator for this session — most new
		# companies have a parent_company and would otherwise hit
		# "Please add the account to root level Company".
		frappe.local.flags.ignore_root_company_validation = True

		# Step 0: best-effort call of ERPNext's own default-seeding methods.
		# When `on_update` fires, ERPNext has typically already run these,
		# but calling them defensively covers edge cases (e.g. bench-console
		# creation paths that bypass the Setup Wizard).
		try:
			if hasattr(doc, "create_default_accounts"):
				doc.create_default_accounts()
			if hasattr(doc, "create_default_warehouses"):
				doc.create_default_warehouses()
			if hasattr(doc, "create_default_cost_center"):
				doc.create_default_cost_center()
		except Exception as erpnext_err:
			# ERPNext defaults are best-effort; the S181 templates create the
			# critical accounts regardless. Log and continue.
			frappe.log_error(
				title=f"S181 ERPNext default seeding non-fatal for {doc.name}",
				message=str(erpnext_err),
			)

		# Step 1: S181 branch warehouse
		_s181_ensure_warehouse(doc)

		# Step 2: S181 branch cost center
		_s181_ensure_cost_center(doc)

		# Step 3: 27-account Sales template (all Income root_type)
		_s181_apply_sales_template(doc)

		# Step 4: Balance Sheet + Expense skeleton (Blocker 5 fix)
		_s181_apply_balance_sheet_template(doc)

		# Step 5: Default accounts (raises if any required default missing)
		_s181_set_default_accounts(doc)

		# Step 6: BKI Customer via S037 register (Blocker 4 fix)
		_s181_ensure_bki_customer(doc)

		# Step 7: flip the sentinel so this hook never re-runs for this company
		frappe.db.set_value(
			"Company", doc.name, "first_provision_done", 1, update_modified=False
		)

		frappe.db.release_savepoint("s181_auto_provision")
		frappe.msgprint(
			f"S181: auto-provisioned COA, Warehouse, Cost Center, default accounts "
			f"and BKI Customer for {doc.name}",
			indicator="green",
			alert=True,
		)
	except Exception:
		frappe.db.rollback_to_savepoint("s181_auto_provision")
		frappe.log_error(
			title=f"S181 auto-provision failed for {doc.name}",
			message=frappe.get_traceback(),
		)
		frappe.msgprint(
			f"S181: auto-provisioning failed for {doc.name}. The company was saved "
			f"but COA / Warehouse / Cost Center must be retried — click "
			f"'Retry Provisioning' on the Company form, or call "
			f"hrms.overrides.company.retry_provision_company via bench console. "
			f"Check Error Log for details.",
			indicator="red",
			alert=True,
		)


def auto_enroll_adms_devices(doc, method=None):
	"""Enqueue ADMS enrollment for any un-enrolled devices on this Company.

	Blocker 12 fix: the original draft made a synchronous HTTP call inside
	`on_update` AND called `doc.save(ignore_permissions=True)` at the end,
	which re-entered `on_update` on the same request — double-saving every
	Company edit and cascading through `make_company_fixtures` /
	`set_default_hr_accounts` / `auto_provision_company` twice. It also
	blocked the user's save on the ADMS receiver's availability.

	This rewrite:
	- Enqueues `_enroll_adms_devices_job` in Frappe's `short` queue.
	- Passes the pending device list by value (no doc reference in the job).
	- The job updates child rows via `frappe.db.set_value`, which does NOT
	  trigger `on_update`, so there is no recursion.
	- 10-second timeout per device to protect the worker.
	- Circuit breaker: failed enrollments are logged and left un-enrolled;
	  the hook re-scans on every Company save, so the retry is automatic on
	  the next edit.

	Blocker 13 guard: skipped during bulk-import / migration / install.
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="company",
		action="auto_enroll_adms_devices",
		mutation_type="update",
		extras={"company": doc.name},
	)

	if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_install:
		return

	# adms_devices is a Custom Field (Table) added in Phase 1. Defensive: if
	# the fixture hasn't been migrated yet, doc.get("adms_devices") returns None.
	devices = doc.get("adms_devices") or []
	if not devices:
		return

	pending = [
		{
			"row_name": device.name,
			"device_serial": device.device_serial,
			"bio_device_id": device.bio_device_id,
		}
		for device in devices
		if not device.adms_enrolled and device.device_serial
	]
	if not pending:
		return

	frappe.enqueue(
		"hrms.overrides.company._enroll_adms_devices_job",
		queue="short",
		timeout=120,
		job_name=f"s181_adms_enroll_{doc.name}",
		company_name=doc.name,
		pending=pending,
	)


def _enroll_adms_devices_job(company_name: str, pending: list):
	"""Background worker for ADMS device enrollment.

	Runs in Frappe's `short` queue. Circuit breaker: if the receiver is
	unreachable or returns non-2xx, log the error and leave the row
	un-enrolled. The row will be re-queued on the next Company save
	(`auto_enroll_adms_devices` re-scans for un-enrolled rows each time).
	"""
	import requests

	try:
		receiver_base_url = frappe.conf.get("adms_receiver_base_url") or frappe.db.get_single_value(
			"ADMS Settings", "receiver_base_url"
		)
	except Exception:
		receiver_base_url = None

	if not receiver_base_url:
		frappe.log_error(
			title=f"S181 ADMS enrollment: no receiver URL configured ({company_name})",
			message=f"Pending devices: {pending}",
		)
		return

	base = receiver_base_url.rstrip("/")
	for entry in pending:
		try:
			resp = requests.post(
				f"{base}/api/devices/enroll",
				json={
					"device_serial": entry["device_serial"],
					"bio_device_id": entry["bio_device_id"],
					"company": company_name,
				},
				timeout=10,
			)
			resp.raise_for_status()
			data = resp.json()
			if data.get("success"):
				# Child-row update via set_value does NOT trigger parent on_update
				frappe.db.set_value(
					"BEI Company ADMS Device",
					entry["row_name"],
					{
						"adms_enrolled": 1,
						"enrollment_date": frappe.utils.nowdate(),
					},
					update_modified=False,
				)
			else:
				frappe.log_error(
					title=f"S181 ADMS enrollment rejected for {entry['device_serial']}",
					message=f"Receiver response: {data}",
				)
		except Exception as e:
			frappe.log_error(
				title=f"S181 ADMS enrollment failed for {entry['device_serial']}",
				message=f"Company: {company_name}\nError: {e}",
			)

	frappe.db.commit()


@frappe.whitelist()
def retry_provision_company(company_name: str):
	"""Retry S181 auto-provisioning for a Company whose first-provision failed.

	Called from the Desk Company form button (registered via hrms/public/js/
	company.js) and from the bei-tasks "Retry Provisioning" pill on the
	Company Master detail dialog. Idempotent — safe to call repeatedly.

	Permission: the caller must have `write` permission on the specific
	Company. This is stricter than role-based checks because Company-level
	permissions are already managed in Frappe.

	Blocker 14 fix — this is the one-click recovery path for half-provisioned
	companies whose `auto_provision_company` hit a savepoint rollback.
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="company",
		action="retry_provision_company",
		mutation_type="update",
		extras={"company": company_name},
	)

	if not frappe.has_permission("Company", "write", doc=company_name):
		frappe.throw(_("Not permitted to retry provisioning for this company."))

	doc = frappe.get_doc("Company", company_name)
	# Clear the sentinel so auto_provision_company runs again
	frappe.db.set_value(
		"Company", company_name, "first_provision_done", 0, update_modified=False
	)
	# Call directly — the in_import / in_migrate guard and the sentinel still
	# apply, so passing a non-standard caller (bench console, REST) is safe.
	auto_provision_company(doc)
	return {"ok": True, "company": company_name}
