"""
ERP Sync API - Frappe endpoints for Sheets Receiver.

These endpoints receive data from the Sheets Receiver service
and sync it to ERPNext DocTypes.
"""

import hashlib
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

_FIELD_CACHE: dict[tuple, bool] = {}
ROOT_TYPES = {"Asset", "Liability", "Equity", "Income", "Expense"}
AP_OPENING_ITEM_CODE = "ERP-SYNC-AP-OPENING"
SYNC_ALLOWED_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"HR Manager",
}


def _parse_rows(data: Any) -> list[dict[str, Any]]:
	if isinstance(data, str):
		parsed = json.loads(data)
		return parsed if isinstance(parsed, list) else []
	if isinstance(data, list):
		return data
	return []


def _init_results(rows_processed: int) -> dict[str, Any]:
	return {
		"rows_processed": rows_processed,
		"rows_created": 0,
		"rows_updated": 0,
		"rows_failed": 0,
		"errors": [],
	}


def _first_non_empty(row: dict[str, Any], *keys: str) -> Any | None:
	for key in keys:
		value = row.get(key)
		if value is None:
			continue
		if isinstance(value, str) and not value.strip():
			continue
		return value
	return None


def _safe_date(value: Any) -> str | None:
	if value in (None, ""):
		return None
	try:
		return str(getdate(value))
	except Exception:
		return None


def _is_duplicate_error(exc: Exception) -> bool:
	duplicate_cls = getattr(frappe, "DuplicateEntryError", None)
	if duplicate_cls and isinstance(exc, duplicate_cls):
		return True
	message = str(exc).lower()
	return "duplicate" in message and "entry" in message


def _sync_ref(prefix: str, sheet_name: str, checksum: str, row_key: str) -> str:
	digest = hashlib.sha1(f"{sheet_name}|{checksum}|{row_key}".encode()).hexdigest()[:16]
	return f"{prefix}:{digest}"


def _make_savepoint(prefix: str, row_key: str) -> str:
	digest = hashlib.sha1(f"{prefix}|{row_key}".encode()).hexdigest()[:12]
	return f"{prefix}_{digest}"


def _release_savepoint(name: str) -> None:
	try:
		frappe.db.release_savepoint(name)
	except Exception:
		# Savepoint release availability differs by backend/version; rollback still works.
		pass


def _assert_sync_authorized() -> None:
	user = frappe.session.user or "Guest"
	if user == "Guest":
		frappe.throw(_("Authentication is required for ERP sync endpoints"), frappe.PermissionError)

	if user == "Administrator":
		return

	user_roles = set(frappe.get_roles(user))
	if user_roles.intersection(SYNC_ALLOWED_ROLES):
		return

	frappe.throw(_("You are not allowed to execute ERP sync endpoints"), frappe.PermissionError)


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
	cache_key = (doctype, fieldname)
	if cache_key in _FIELD_CACHE:
		return _FIELD_CACHE[cache_key]

	has_field = False
	try:
		has_field = bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		has_field = False

	_FIELD_CACHE[cache_key] = has_field
	return has_field


def _first_available_field(doctype: str, candidates: list[str]) -> str | None:
	for fieldname in candidates:
		if _doctype_has_field(doctype, fieldname):
			return fieldname
	return None


def _normalize_company(company: str | None = None) -> str:
	if company and frappe.db.exists("Company", company):
		return company

	default_company = None
	try:
		default_company = frappe.defaults.get_global_default("company")
	except Exception:
		default_company = None

	if default_company and frappe.db.exists("Company", default_company):
		return default_company

	try:
		companies = frappe.get_all("Company", pluck="name", limit=1)
	except Exception:
		companies = []

	if companies:
		return companies[0]

	frappe.throw(_("Default company is required for ERP sync writes"))


def _resolve_warehouse(raw_value: str | None) -> str | None:
	value = (raw_value or "").strip()
	if not value:
		if frappe.db.exists("Warehouse", "Stores - BEI"):
			return "Stores - BEI"
		return frappe.db.get_value("Warehouse", {"is_group": 0}, "name")

	if frappe.db.exists("Warehouse", value):
		return value

	if not value.endswith(" - BEI"):
		candidate = f"{value} - BEI"
		if frappe.db.exists("Warehouse", candidate):
			return candidate

	return None


def _resolve_root_type(account_type: str | None, gl_code: str | None, row: dict[str, Any]) -> str:
	explicit = _first_non_empty(row, "root_type")
	if explicit in ROOT_TYPES:
		return explicit

	normalized = (account_type or "").strip().lower()
	if any(token in normalized for token in ("asset", "receivable", "bank", "cash")):
		return "Asset"
	if any(token in normalized for token in ("liability", "payable")):
		return "Liability"
	if "equity" in normalized:
		return "Equity"
	if any(token in normalized for token in ("income", "revenue", "sale")):
		return "Income"
	if any(token in normalized for token in ("expense", "cost", "cogs")):
		return "Expense"

	leading = str(gl_code or "")[:1]
	if leading == "1":
		return "Asset"
	if leading == "2":
		return "Liability"
	if leading == "3":
		return "Equity"
	if leading == "4":
		return "Income"
	if leading in {"5", "6", "7", "8", "9"}:
		return "Expense"
	return "Asset"


def _resolve_parent_account(row: dict[str, Any], company: str, root_type: str) -> str | None:
	parent_name = _first_non_empty(row, "parent_account", "parent")
	if parent_name and frappe.db.exists("Account", parent_name):
		return parent_name

	parent_code = _first_non_empty(row, "parent_gl_code", "parent_account_code")
	if parent_code:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "account_number": parent_code},
			"name",
		)
		if parent:
			return parent

	return frappe.db.get_value(
		"Account",
		{"company": company, "root_type": root_type, "is_group": 1},
		"name",
	)


def _report_type_for(root_type: str) -> str:
	if root_type in {"Income", "Expense"}:
		return "Profit and Loss"
	return "Balance Sheet"


def _ensure_bank(bank_name: str | None) -> str | None:
	if not bank_name:
		return None

	normalized = str(bank_name).strip()
	if not normalized:
		return None

	if frappe.db.exists("Bank", normalized):
		return normalized

	existing = frappe.db.get_value("Bank", {"bank_name": normalized}, "name")
	if existing:
		return existing

	bank = frappe.get_doc({"doctype": "Bank", "bank_name": normalized})
	try:
		bank.insert(ignore_permissions=True)
		return bank.name
	except Exception as exc:
		if _is_duplicate_error(exc):
			return frappe.db.get_value("Bank", {"bank_name": normalized}, "name")
		raise


def _ensure_supplier(supplier_name: str) -> str:
	if frappe.db.exists("Supplier", supplier_name):
		return supplier_name

	existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
	if existing:
		return existing

	supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}
	)
	try:
		supplier.insert(ignore_permissions=True)
		return supplier.name
	except Exception as exc:
		if _is_duplicate_error(exc):
			return frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
		raise


def _default_expense_account(company: str) -> str | None:
	return frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Expense", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	)


def _default_payable_account(company: str) -> str | None:
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Payable", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Liability", "is_group": 0},
		"name",
	)


def _default_cost_center(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "cost_center") or frappe.db.get_value(
		"Cost Center", {"company": company, "is_group": 0}, "name"
	)


def _ensure_ap_opening_item() -> str:
	if frappe.db.exists("Item", AP_OPENING_ITEM_CODE):
		# Keep legacy item definitions safe for AP opening inserts.
		updates: dict[str, Any] = {}
		if _doctype_has_field("Item", "is_stock_item"):
			is_stock_item = cint(frappe.db.get_value("Item", AP_OPENING_ITEM_CODE, "is_stock_item") or 0)
			if is_stock_item:
				updates["is_stock_item"] = 0
		if _doctype_has_field("Item", "is_purchase_item"):
			is_purchase_item = cint(
				frappe.db.get_value("Item", AP_OPENING_ITEM_CODE, "is_purchase_item") or 0
			)
			if not is_purchase_item:
				updates["is_purchase_item"] = 1
		if _doctype_has_field("Item", "is_sales_item"):
			is_sales_item = cint(frappe.db.get_value("Item", AP_OPENING_ITEM_CODE, "is_sales_item") or 0)
			if is_sales_item:
				updates["is_sales_item"] = 0
		if _doctype_has_field("Item", "stock_uom"):
			stock_uom = frappe.db.get_value("Item", AP_OPENING_ITEM_CODE, "stock_uom")
			if not stock_uom:
				updates["stock_uom"] = "Nos"
		if updates:
			frappe.db.set_value("Item", AP_OPENING_ITEM_CODE, updates, update_modified=False)
		return AP_OPENING_ITEM_CODE

	item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": AP_OPENING_ITEM_CODE,
			"item_name": "AP Opening Balance Sync Item",
			"item_group": item_group,
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_purchase_item": 1,
			"is_sales_item": 0,
		}
	)
	try:
		item.insert(ignore_permissions=True)
		return item.name
	except Exception as exc:
		if _is_duplicate_error(exc):
			return AP_OPENING_ITEM_CODE
		raise


@frappe.whitelist()
def sync_ar_aging(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync AR Aging data from Google Sheets.

	Creates/updates Sales Invoice outstanding amounts.
	"""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))
	seen_invoice_keys: set[str] = set()

	outstanding_field = _first_available_field(
		"Sales Invoice",
		[
			"outstanding_amount",
			"custom_external_outstanding",
			"custom_ar_outstanding",
			"custom_sheet_outstanding",
		],
	)
	base_outstanding_field = _first_available_field(
		"Sales Invoice",
		[
			"base_outstanding_amount",
			"custom_base_external_outstanding",
		],
	)
	days_overdue_field = _first_available_field(
		"Sales Invoice",
		[
			"custom_days_overdue",
			"custom_ar_days_overdue",
		],
	)

	for row in rows:
		invoice_no = str(_first_non_empty(row, "invoice_no", "invoice_number", "name") or "").strip()
		if invoice_no and invoice_no in seen_invoice_keys:
			results["rows_updated"] += 1
			continue
		if invoice_no:
			seen_invoice_keys.add(invoice_no)

		savepoint = _make_savepoint("sync_ar", f"{sheet_name}|{checksum}|{invoice_no or 'unknown'}")
		frappe.db.savepoint(savepoint)
		try:
			outstanding = flt(_first_non_empty(row, "outstanding", "balance", "outstanding_amount") or 0)
			due_date = _safe_date(_first_non_empty(row, "due_date"))
			days_overdue = cint(_first_non_empty(row, "days_overdue", "overdue_days") or 0)

			if not invoice_no:
				results["rows_failed"] += 1
				results["errors"].append("Missing invoice_no in AR row")
				_release_savepoint(savepoint)
				continue

			invoice_name = frappe.db.exists("Sales Invoice", invoice_no)
			if not invoice_name:
				invoice_name = frappe.db.get_value("Sales Invoice", {"name": invoice_no}, "name")

			if not invoice_name:
				results["rows_failed"] += 1
				results["errors"].append(f"Invoice not found: {invoice_no}")
				_release_savepoint(savepoint)
				continue

			updates: dict[str, Any] = {}
			if outstanding_field:
				updates[outstanding_field] = outstanding

			if base_outstanding_field:
				conversion_rate = flt(
					frappe.db.get_value("Sales Invoice", invoice_name, "conversion_rate") or 1
				)
				updates[base_outstanding_field] = outstanding * conversion_rate

			if due_date and _doctype_has_field("Sales Invoice", "due_date"):
				updates["due_date"] = due_date

			if days_overdue_field:
				updates[days_overdue_field] = days_overdue

			sync_token_field = _first_available_field(
				"Sales Invoice",
				["custom_ar_sync_ref", "custom_last_sync_checksum"],
			)
			if sync_token_field:
				sync_ref = _sync_ref("AR", sheet_name, checksum, str(invoice_no))
				existing_sync_ref = frappe.db.get_value("Sales Invoice", invoice_name, sync_token_field)
				if existing_sync_ref == sync_ref:
					results["rows_updated"] += 1
					_release_savepoint(savepoint)
					continue
				updates[sync_token_field] = sync_ref

			if updates:
				frappe.db.set_value("Sales Invoice", invoice_name, updates, update_modified=False)

			results["rows_updated"] += 1
			_release_savepoint(savepoint)

		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			results["errors"].append(f"{row.get('invoice_no', 'unknown')}: {e!s}")
			results["rows_failed"] += 1

	frappe.logger().info(f"AR Aging sync complete: {results}")
	return results


@frappe.whitelist()
def sync_inventory(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync Inventory data from Google Sheets.

	Updates stock levels via Stock Reconciliation.
	"""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))

	items_by_warehouse: dict[str, dict[str, dict[str, Any]]] = {}

	for row in rows:
		try:
			item_code = _first_non_empty(row, "item_code", "sku")
			warehouse = _resolve_warehouse(_first_non_empty(row, "warehouse", "location", "store"))
			qty = flt(_first_non_empty(row, "qty", "quantity", "stock") or 0)

			if not item_code:
				results["rows_failed"] += 1
				results["errors"].append("Missing item_code in inventory row")
				continue

			if not frappe.db.exists("Item", item_code):
				results["rows_failed"] += 1
				results["errors"].append(f"Item not found: {item_code}")
				continue

			if not warehouse:
				results["rows_failed"] += 1
				results["errors"].append(f"Warehouse not found for item {item_code}")
				continue

			if warehouse not in items_by_warehouse:
				items_by_warehouse[warehouse] = {}

			# Last row wins for repeated item+warehouse rows in same payload.
			items_by_warehouse[warehouse][item_code] = {
				"item_code": item_code,
				"warehouse": warehouse,
				"qty": qty,
			}

		except Exception as e:
			results["errors"].append(str(e))
			results["rows_failed"] += 1

	for warehouse, items_map in items_by_warehouse.items():
		items = list(items_map.values())
		sync_ref = _sync_ref("INV", sheet_name, checksum, warehouse)
		savepoint = _make_savepoint("sync_inv", f"{sheet_name}|{checksum}|{warehouse}")
		frappe.db.savepoint(savepoint)
		try:
			has_remarks = _doctype_has_field("Stock Reconciliation", "remarks")
			token_field = _first_available_field(
				"Stock Reconciliation",
				["custom_sync_ref", "custom_last_sync_checksum"],
			)
			lookup_filters: dict[str, Any] = {"docstatus": ["<", 2]}
			if has_remarks:
				lookup_filters["remarks"] = ["like", f"%{sync_ref}%"]
			elif token_field:
				lookup_filters[token_field] = sync_ref
			else:
				lookup_filters = {}

			existing = None
			if lookup_filters:
				existing = frappe.db.get_value("Stock Reconciliation", lookup_filters, "name")

			if existing:
				results["rows_updated"] += len(items)
				_release_savepoint(savepoint)
				continue

			sr = frappe.new_doc("Stock Reconciliation")
			sr.purpose = "Stock Reconciliation"
			sr.posting_date = nowdate()
			sr.posting_time = now_datetime().strftime("%H:%M:%S")
			sr.company = _normalize_company()
			if has_remarks:
				sr.remarks = (
					f"ERP Inventory Sync ({sync_ref}) "
					f"sheet={sheet_name} warehouse={warehouse} rows={len(items)}"
				)
			elif token_field:
				setattr(sr, token_field, sync_ref)

			for item in items:
				sr.append(
					"items",
					{
						"item_code": item["item_code"],
						"warehouse": warehouse,
						"qty": item["qty"],
					},
				)

			sr.insert(ignore_permissions=True)
			sr.submit()
			results["rows_created"] += len(items)
			_release_savepoint(savepoint)

		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			if _is_duplicate_error(exc):
				existing = None
				if lookup_filters:
					existing = frappe.db.get_value("Stock Reconciliation", lookup_filters, "name")
				if existing:
					results["rows_updated"] += len(items)
					continue
			results["errors"].append(f"{warehouse}: {exc!s}")
			results["rows_failed"] += len(items)

	return results


@frappe.whitelist()
def sync_coa(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync Chart of Accounts from Google Sheets.

	Creates/updates Account DocType.
	"""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))
	seen_account_keys: set[str] = set()

	for row in rows:
		savepoint: str | None = None
		try:
			gl_code = _first_non_empty(row, "gl_code", "account_code")
			account_name = _first_non_empty(row, "gl_description", "account_name")
			account_type = _first_non_empty(row, "accounttype", "account_type")
			company = _normalize_company(_first_non_empty(row, "company"))
			dedupe_key = f"{company}|{gl_code}"
			if gl_code and dedupe_key in seen_account_keys:
				results["rows_updated"] += 1
				continue
			if gl_code:
				seen_account_keys.add(dedupe_key)

			savepoint = _make_savepoint("sync_coa", f"{sheet_name}|{checksum}|{dedupe_key}")
			frappe.db.savepoint(savepoint)

			root_type = _resolve_root_type(str(account_type or ""), str(gl_code or ""), row)
			parent_account = _resolve_parent_account(row, company, root_type)
			report_type = _report_type_for(root_type)
			is_group = cint(_first_non_empty(row, "is_group", "group") or 0)

			if not gl_code or not account_name:
				results["rows_failed"] += 1
				results["errors"].append("Missing gl_code or account_name in COA row")
				_release_savepoint(savepoint)
				continue

			existing = frappe.db.get_value(
				"Account",
				{"company": company, "account_number": gl_code},
				"name",
			)

			if existing:
				sync_token_field = _first_available_field(
					"Account", ["custom_sync_ref", "custom_last_sync_checksum"]
				)
				sync_ref = _sync_ref("COA", sheet_name, checksum, str(gl_code))
				if sync_token_field:
					existing_sync_ref = frappe.db.get_value("Account", existing, sync_token_field)
					if existing_sync_ref == sync_ref:
						results["rows_updated"] += 1
						_release_savepoint(savepoint)
						continue

				updates: dict[str, Any] = {
					"account_name": account_name,
					"root_type": root_type,
					"report_type": report_type,
					"is_group": is_group,
				}
				if account_type and _doctype_has_field("Account", "account_type"):
					updates["account_type"] = account_type
				if parent_account and parent_account != existing:
					updates["parent_account"] = parent_account
				if sync_token_field:
					updates[sync_token_field] = sync_ref
				try:
					frappe.db.set_value("Account", existing, updates, update_modified=False)
				except Exception as exc:
					if "descendants" in str(exc).lower() and "parent_account" in updates:
						updates.pop("parent_account", None)
						frappe.db.set_value("Account", existing, updates, update_modified=False)
					else:
						raise
				results["rows_updated"] += 1
				_release_savepoint(savepoint)
			else:
				if not parent_account:
					raise ValueError(f"Unable to resolve parent account for {gl_code}")

				account = frappe.new_doc("Account")
				account.account_name = account_name
				account.account_number = gl_code
				account.company = company
				account.parent_account = parent_account
				account.root_type = root_type
				account.report_type = report_type
				account.is_group = is_group
				if account_type and _doctype_has_field("Account", "account_type"):
					account.account_type = account_type
				sync_token_field = _first_available_field(
					"Account", ["custom_sync_ref", "custom_last_sync_checksum"]
				)
				if sync_token_field:
					setattr(account, sync_token_field, _sync_ref("COA", sheet_name, checksum, str(gl_code)))

				try:
					account.insert(ignore_permissions=True)
					results["rows_created"] += 1
					_release_savepoint(savepoint)
				except Exception as exc:
					if _is_duplicate_error(exc):
						results["rows_updated"] += 1
						_release_savepoint(savepoint)
					elif "descendants" in str(exc).lower():
						fallback_parent = frappe.db.get_value(
							"Account",
							{"company": company, "root_type": root_type, "is_group": 1},
							"name",
						)
						if not fallback_parent:
							raise
						account.parent_account = fallback_parent
						account.insert(ignore_permissions=True)
						results["rows_created"] += 1
						_release_savepoint(savepoint)
					else:
						raise

		except Exception as e:
			if savepoint:
				frappe.db.rollback(save_point=savepoint)
			results["errors"].append(f"{row.get('gl_code', 'unknown')}: {e!s}")
			results["rows_failed"] += 1

	return results


@frappe.whitelist()
def sync_bank_accounts(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync Bank Directory from Google Sheets.

	Creates/updates Bank Account DocType.
	"""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))
	seen_account_numbers: set[str] = set()

	for row in rows:
		savepoint: str | None = None
		try:
			account_number = _first_non_empty(row, "account_number", "account_no", "bank_account_no")
			account_name = _first_non_empty(row, "account_name", "account_holder")
			bank_name = _first_non_empty(row, "bank_name", "bank")
			branch = _first_non_empty(row, "branch_name", "branch")
			company = _normalize_company(_first_non_empty(row, "company"))
			gl_code = _first_non_empty(row, "gl_code", "account_code", "coa_code")
			linked_account = None

			if not account_number:
				results["rows_failed"] += 1
				results["errors"].append("Missing account_number in bank directory row")
				continue

			account_number = str(account_number).strip()
			if account_number in seen_account_numbers:
				results["rows_updated"] += 1
				continue
			seen_account_numbers.add(account_number)

			savepoint = _make_savepoint("sync_bank", f"{sheet_name}|{checksum}|{account_number}")
			frappe.db.savepoint(savepoint)

			if gl_code:
				linked_account = frappe.db.get_value(
					"Account",
					{"company": company, "account_number": gl_code},
					"name",
				) or (gl_code if frappe.db.exists("Account", gl_code) else None)

			bank = _ensure_bank(str(bank_name)) if bank_name else None

			existing = frappe.db.get_value(
				"Bank Account",
				{"bank_account_no": account_number},
				"name",
			)

			if existing:
				updates: dict[str, Any] = {}
				sync_token_field = _first_available_field(
					"Bank Account",
					["custom_sync_ref", "custom_last_sync_checksum"],
				)
				sync_ref = _sync_ref("BANK", sheet_name, checksum, account_number)
				if sync_token_field:
					existing_sync_ref = frappe.db.get_value("Bank Account", existing, sync_token_field)
					if existing_sync_ref == sync_ref:
						results["rows_updated"] += 1
						_release_savepoint(savepoint)
						continue
				if account_name:
					updates["account_name"] = account_name
				if bank:
					updates["bank"] = bank
				if branch:
					if _doctype_has_field("Bank Account", "branch"):
						updates["branch"] = branch
					elif _doctype_has_field("Bank Account", "branch_code"):
						updates["branch_code"] = branch
				if linked_account and _doctype_has_field("Bank Account", "account"):
					updates["account"] = linked_account
				if _doctype_has_field("Bank Account", "is_company_account"):
					updates["is_company_account"] = 1
				if _doctype_has_field("Bank Account", "party_type"):
					updates["party_type"] = "Company"
				if _doctype_has_field("Bank Account", "party"):
					updates["party"] = company
				if _doctype_has_field("Bank Account", "company"):
					updates["company"] = company
				if sync_token_field:
					updates[sync_token_field] = sync_ref
				if updates:
					frappe.db.set_value("Bank Account", existing, updates, update_modified=False)
				results["rows_updated"] += 1
				_release_savepoint(savepoint)
			else:
				bank_account = frappe.new_doc("Bank Account")
				bank_account.bank_account_no = account_number
				bank_account.account_name = str(account_name or account_number)
				if bank:
					bank_account.bank = bank
				if branch:
					if _doctype_has_field("Bank Account", "branch"):
						bank_account.branch = branch
					elif _doctype_has_field("Bank Account", "branch_code"):
						bank_account.branch_code = branch
				if _doctype_has_field("Bank Account", "is_company_account"):
					bank_account.is_company_account = 1
				if _doctype_has_field("Bank Account", "party_type"):
					bank_account.party_type = "Company"
				if _doctype_has_field("Bank Account", "party"):
					bank_account.party = company
				if _doctype_has_field("Bank Account", "company"):
					bank_account.company = company
				if linked_account and _doctype_has_field("Bank Account", "account"):
					bank_account.account = linked_account
				sync_token_field = _first_available_field(
					"Bank Account",
					["custom_sync_ref", "custom_last_sync_checksum"],
				)
				if sync_token_field:
					setattr(
						bank_account,
						sync_token_field,
						_sync_ref("BANK", sheet_name, checksum, account_number),
					)

				try:
					bank_account.insert(ignore_permissions=True)
					results["rows_created"] += 1
					_release_savepoint(savepoint)
				except Exception as exc:
					if _is_duplicate_error(exc):
						results["rows_updated"] += 1
						_release_savepoint(savepoint)
					else:
						raise

		except Exception as e:
			if savepoint:
				frappe.db.rollback(save_point=savepoint)
			results["errors"].append(f"{row.get('account_number', 'unknown')}: {e!s}")
			results["rows_failed"] += 1

	return results


@frappe.whitelist()
def sync_ap_opening(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync AP Opening Balance (Supplier SOA) from Google Sheets.

	Creates/updates Purchase Invoice entries for opening balances.
	"""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))
	opening_item = _ensure_ap_opening_item()
	seen_supplier_invoice_keys: set[str] = set()

	for row in rows:
		savepoint: str | None = None
		try:
			supplier_input = _first_non_empty(row, "supplier", "supplier_name")
			invoice_no = _first_non_empty(row, "invoice_no", "reference", "bill_no")
			amount = flt(_first_non_empty(row, "amount", "balance", "outstanding") or 0)
			company = _normalize_company(_first_non_empty(row, "company"))
			dedupe_key = f"{company}|{supplier_input}|{invoice_no}"
			if supplier_input and invoice_no and dedupe_key in seen_supplier_invoice_keys:
				results["rows_updated"] += 1
				continue
			if supplier_input and invoice_no:
				seen_supplier_invoice_keys.add(dedupe_key)

			savepoint = _make_savepoint("sync_ap", f"{sheet_name}|{checksum}|{dedupe_key}")
			frappe.db.savepoint(savepoint)

			posting_date = (
				_safe_date(_first_non_empty(row, "posting_date", "invoice_date", "date")) or nowdate()
			)
			due_date = _safe_date(_first_non_empty(row, "due_date")) or posting_date

			if not supplier_input or not invoice_no:
				results["rows_failed"] += 1
				results["errors"].append("Missing supplier or invoice_no in AP opening row")
				_release_savepoint(savepoint)
				continue

			supplier = _ensure_supplier(str(supplier_input))
			existing = frappe.db.get_value(
				"Purchase Invoice",
				{
					"supplier": supplier,
					"bill_no": invoice_no,
					"company": company,
					"docstatus": ["<", 2],
				},
				"name",
			)

			if existing:
				updates: dict[str, Any] = {}
				if _doctype_has_field("Purchase Invoice", "due_date"):
					updates["due_date"] = due_date
				if _doctype_has_field("Purchase Invoice", "bill_date"):
					updates["bill_date"] = posting_date
				sync_ref = _sync_ref("AP", sheet_name, checksum, f"{supplier}|{invoice_no}")
				if _doctype_has_field("Purchase Invoice", "remarks"):
					current_remarks = frappe.db.get_value("Purchase Invoice", existing, "remarks") or ""
					if sync_ref not in current_remarks:
						sync_note = f"[{sync_ref}] amount={amount}"
						updates["remarks"] = f"{current_remarks}\n{sync_note}".strip()
				if updates:
					frappe.db.set_value("Purchase Invoice", existing, updates, update_modified=False)
				results["rows_updated"] += 1
				_release_savepoint(savepoint)
				continue

			expense_account = _first_non_empty(row, "expense_account") or _default_expense_account(company)
			payable_account = _first_non_empty(
				row, "credit_to", "payable_account"
			) or _default_payable_account(company)
			cost_center = _first_non_empty(row, "cost_center") or _default_cost_center(company)

			if not expense_account:
				raise ValueError(f"No expense account available for company {company}")
			if not payable_account:
				raise ValueError(f"No payable account available for company {company}")

			sync_ref = _sync_ref("AP", sheet_name, checksum, f"{supplier}|{invoice_no}")
			pi = frappe.new_doc("Purchase Invoice")
			pi.company = company
			pi.supplier = supplier
			pi.bill_no = invoice_no
			pi.bill_date = posting_date
			pi.posting_date = posting_date
			pi.due_date = due_date
			pi.set_posting_time = 1
			if _doctype_has_field("Purchase Invoice", "is_opening"):
				pi.is_opening = "Yes"
			if _doctype_has_field("Purchase Invoice", "credit_to"):
				pi.credit_to = payable_account
			if _doctype_has_field("Purchase Invoice", "remarks"):
				pi.remarks = f"ERP AP Opening Sync [{sync_ref}]"

			item_row = {
				"item_code": opening_item,
				"qty": 1,
				"rate": amount,
				"expense_account": expense_account,
				"description": f"Opening balance sync for {invoice_no}",
			}
			if cost_center:
				item_row["cost_center"] = cost_center
			pi.append("items", item_row)

			try:
				pi.insert(ignore_permissions=True)
				try:
					pi.submit()
				except Exception:
					frappe.log_error(
						message=f"AP opening sync created draft PI {pi.name}; submit failed: {frappe.get_traceback()}",
						title="AP Opening Sync Submit Warning",
					)
				results["rows_created"] += 1
				_release_savepoint(savepoint)
			except Exception as exc:
				if _is_duplicate_error(exc):
					results["rows_updated"] += 1
					_release_savepoint(savepoint)
				else:
					raise

		except Exception as e:
			if savepoint:
				frappe.db.rollback(save_point=savepoint)
			results["errors"].append(str(e))
			results["rows_failed"] += 1

	return results


@frappe.whitelist()
def sync_supplier_soa(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Backward-compatible alias for supplier_soa route.

	Source config still points to this method name.
	"""
	return sync_ap_opening(sheet_name=sheet_name, data=data, checksum=checksum, **kwargs)


# nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
	"""
	Proxy webhook endpoint for Sheets Receiver.

	This allows the webhook to come through Frappe's URL
	and be forwarded to the Sheets Receiver service.

	Google sends webhooks to:
	https://hq.bebang.ph/api/method/hrms.api.sheets_receiver.webhook

	We forward to:
	http://sheets-receiver:8765/webhook/sheets
	"""
	import requests

	headers = {
		"X-Goog-Channel-ID": frappe.request.headers.get("X-Goog-Channel-ID"),
		"X-Goog-Resource-ID": frappe.request.headers.get("X-Goog-Resource-ID"),
		"X-Goog-Resource-State": frappe.request.headers.get("X-Goog-Resource-State"),
		"X-Goog-Changed": frappe.request.headers.get("X-Goog-Changed"),
		"X-Goog-Message-Number": frappe.request.headers.get("X-Goog-Message-Number"),
		"Content-Type": "application/json",
	}

	try:
		response = requests.post(
			"http://sheets-receiver:8765/webhook/sheets",
			headers=headers,
			data=frappe.request.data,
			timeout=5,
		)
		return response.json()
	except Exception as e:
		frappe.log_error(f"Failed to forward webhook: {e}", "Sheets Webhook Error")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_sync_status():
	"""Get sync status from Sheets Receiver service."""
	_assert_sync_authorized()
	import requests

	try:
		response = requests.get("http://sheets-receiver:8765/api/status", timeout=10)
		return response.json()
	except Exception as e:
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def trigger_sync(sheet_key: str | None = None, force: bool = False):
	"""Trigger manual sync via Sheets Receiver service."""
	_assert_sync_authorized()
	import requests

	try:
		if sheet_key:
			url = f"http://sheets-receiver:8765/api/sync/{sheet_key}?force={force}"
		else:
			url = f"http://sheets-receiver:8765/api/sync-all?force={force}"

		response = requests.post(url, timeout=10)
		return response.json()
	except Exception as e:
		return {"status": "error", "message": str(e)}
