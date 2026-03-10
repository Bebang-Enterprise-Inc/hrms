"""
ERP Sync API - Frappe endpoints for Sheets Receiver.

These endpoints receive data from the Sheets Receiver service
and sync it to ERPNext DocTypes.
"""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from hrms.utils import store_inventory_shadow_sync as store_inventory_shadow_sync_builder
from hrms.utils import store_order_demand_snapshot as store_demand_snapshot_builder
from hrms.utils.standard_buying_bridge import apply_standard_buying_context

_FIELD_CACHE: dict[tuple, bool] = {}
ROOT_TYPES = {"Asset", "Liability", "Equity", "Income", "Expense"}
AP_OPENING_ITEM_CODE = "ERP-SYNC-AP-OPENING"
SYNC_ALLOWED_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"HR Manager",
}
STORE_DEMAND_SNAPSHOT_SHEET_NAME = "Store Demand Snapshot"
STORE_DEMAND_SNAPSHOT_AUTO_PREFIX = "scheduled_store_demand_snapshot"
STORE_INVENTORY_SHADOW_SYNC_SHEET_NAME = "Store Inventory Shadow Sync"
STORE_INVENTORY_SHADOW_SYNC_AUTO_PREFIX = "scheduled_store_inventory_shadow_sync"
STORE_INVENTORY_SHADOW_BATCH_PREFIX = "SHADOW"


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


def _ap_opening_store_label(row: dict[str, Any]) -> str | None:
	return _first_non_empty(row, "bei_store_label", "store_label", "warehouse", "store", "branch")


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

	warehouse_name_match = frappe.db.get_value("Warehouse", {"warehouse_name": value}, "name")
	if warehouse_name_match:
		return warehouse_name_match

	return None


def _coerce_metadata_dict(value: Any) -> dict[str, Any]:
	if isinstance(value, dict):
		return dict(value)
	if isinstance(value, str) and value.strip():
		try:
			parsed = json.loads(value)
		except Exception:
			return {}
		return parsed if isinstance(parsed, dict) else {}
	return {}


def _store_demand_output_root() -> Path:
	get_site_path = getattr(frappe, "get_site_path", None)
	if callable(get_site_path):
		try:
			return Path(get_site_path("private", "files", "store_order_demand_snapshot_runs"))
		except Exception:
			pass
	return Path(store_demand_snapshot_builder.DEFAULT_OUTPUT_ROOT)


def _store_demand_output_dir(snapshot_date: str) -> Path:
	return _store_demand_output_root() / f"{snapshot_date}_store_order_demand_snapshot_auto"


def _log_sync_run_summary(title: str, payload: dict[str, Any]) -> None:
	"""Log a compact sync summary without risking oversized Error Log titles."""
	try:
		message = json.dumps(payload, sort_keys=True, default=str)
	except Exception:
		message = str(payload)

	try:
		frappe.log_error(message=message, title=title[:140])
	except TypeError:
		frappe.log_error(message, title[:140])


def _is_store_inventory_shadow_sync(sheet_name: str) -> bool:
	return sheet_name.startswith(STORE_INVENTORY_SHADOW_SYNC_SHEET_NAME)


def _normalize_batch_token(value: str) -> str:
	token = "".join(ch if ch.isalnum() else "-" for ch in str(value or "").strip().upper())
	token = token.strip("-")
	while "--" in token:
		token = token.replace("--", "-")
	return token or "UNKNOWN"


def _build_shadow_batch_id(store_key: str, item_code: str) -> str:
	store_token = _normalize_batch_token(store_key)
	item_token = _normalize_batch_token(item_code)
	return f"{STORE_INVENTORY_SHADOW_BATCH_PREFIX}-{store_token}-{item_token}"[:140]


def _ensure_batch_exists(batch_id: str, item_code: str) -> str:
	batch_id = str(batch_id or "").strip()
	if not batch_id:
		frappe.throw(_("Batch ID is required for batch-tracked items"))

	if frappe.db.exists("Batch", batch_id):
		return batch_id

	if not cint(frappe.db.get_value("Item", item_code, "has_batch_no") or 0):
		frappe.throw(_("Item {0} is not batch-tracked").format(item_code))

	batch = frappe.new_doc("Batch")
	batch.batch_id = batch_id
	batch.item = item_code
	batch.manufacturing_date = nowdate()
	batch.description = _("Synthetic shadow batch for pre-cutover store inventory mirror")
	batch.insert(ignore_permissions=True)
	return batch.name


def _persist_store_demand_outputs(
	output_dir: Path, outputs: dict[str, Any], lookback_days: int, snapshot_date: str
) -> None:
	output_dir.mkdir(parents=True, exist_ok=True)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_product_daily_demand.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"fg_name",
			"component_recipe_key",
			"target_type",
			"target_key",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"mapping_note",
		],
		outputs["product_daily_rows"],
	)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_item_daily_demand.csv",
		[
			"business_date",
			"store_name",
			"channel",
			"item_code",
			"item_name",
			"demand_qty",
			"source_targets",
		],
		outputs["item_daily_rows"],
	)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_demand_snapshot.csv",
		[
			"snapshot_date",
			"warehouse",
			"item_code",
			"avg_daily_demand",
			"projected_sales",
			"bom_consumption",
			"lookback_days",
			"signal_source",
			"channel_mix",
			"source_reference",
		],
		outputs["snapshot_rows"],
	)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_product_mapping_audit.csv",
		[
			"product_name",
			"product_code",
			"resolution_status",
			"target_type",
			"target_key",
			"mapping_method",
			"mapping_note",
			"row_count",
			"qty_sold_total",
			"net_sales_amount_total",
			"channel_mix",
			"store_count",
		],
		outputs["mapping_audit_rows"],
	)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_demand_excluded_products.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"exclusion_reason",
			"mapping_note",
		],
		outputs["excluded_rows"],
	)
	store_demand_snapshot_builder.write_csv(
		output_dir / "store_demand_unmapped_products.csv",
		[
			"business_date",
			"channel",
			"store_name",
			"store_code",
			"product_name",
			"product_code",
			"qty_sold",
			"net_sales_amount",
			"mapping_method",
			"mapping_note",
		],
		outputs["unmapped_rows"],
	)

	summary = {
		"snapshot_date": snapshot_date,
		"lookback_days": lookback_days,
		"start_date": outputs["start_date"],
		"end_date": outputs["end_date"],
		"product_daily_rows": len(outputs["product_daily_rows"]),
		"item_daily_rows": len(outputs["item_daily_rows"]),
		"snapshot_rows": len(outputs["snapshot_rows"]),
		"mapping_audit_rows": len(outputs["mapping_audit_rows"]),
		"excluded_products": len(outputs["excluded_rows"]),
		"unmapped_products": len(outputs["unmapped_rows"]),
		"output_dir": str(output_dir),
	}
	(output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


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


def _sync_inventory_rows(
	sheet_name: str,
	data: list[dict],
	checksum: str,
	*,
	require_auth: bool,
) -> dict:
	"""Internal sync helper shared by API calls and scheduled jobs."""
	if require_auth:
		_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))

	items_by_warehouse: dict[str, dict[str, dict[str, Any]]] = {}
	is_shadow_sync = _is_store_inventory_shadow_sync(sheet_name)

	for row in rows:
		try:
			item_code = str(_first_non_empty(row, "item_code", "sku") or "").strip()
			warehouse = _resolve_warehouse(_first_non_empty(row, "warehouse", "location", "store"))
			qty = flt(_first_non_empty(row, "qty", "quantity", "stock") or 0)
			store_code = str(_first_non_empty(row, "store_code") or "").strip()
			batch_no = str(_first_non_empty(row, "batch_no") or "").strip()
			serial_no = str(_first_non_empty(row, "serial_no") or "").strip()

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

			has_batch_no = cint(frappe.db.get_value("Item", item_code, "has_batch_no") or 0)
			has_serial_no = cint(frappe.db.get_value("Item", item_code, "has_serial_no") or 0)
			use_serial_batch_fields = 0

			if has_serial_no and not serial_no:
				results["rows_failed"] += 1
				results["errors"].append(
					f"Serial-tracked item requires serial detail and cannot be mirrored from aggregate stock: {item_code}"
				)
				continue

			if has_batch_no:
				use_serial_batch_fields = 1
				if not batch_no:
					if not is_shadow_sync:
						results["rows_failed"] += 1
						results["errors"].append(f"Batch-tracked item requires batch_no: {item_code}")
						continue
					batch_no = _build_shadow_batch_id(store_code or warehouse, item_code)

				batch_no = _ensure_batch_exists(batch_no, item_code)

			if warehouse not in items_by_warehouse:
				items_by_warehouse[warehouse] = {}

			# Last row wins for repeated item+warehouse rows in same payload.
			items_by_warehouse[warehouse][item_code] = {
				"item_code": item_code,
				"warehouse": warehouse,
				"qty": qty,
				"batch_no": batch_no,
				"serial_no": serial_no,
				"use_serial_batch_fields": use_serial_batch_fields,
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
				row_payload = {
					"item_code": item["item_code"],
					"warehouse": warehouse,
					"qty": item["qty"],
				}
				if item.get("use_serial_batch_fields"):
					row_payload["use_serial_batch_fields"] = 1
				if item.get("batch_no"):
					row_payload["batch_no"] = item["batch_no"]
				if item.get("serial_no"):
					row_payload["serial_no"] = item["serial_no"]
				sr.append("items", row_payload)

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
def sync_inventory(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync Inventory data from Google Sheets.

	Updates stock levels via Stock Reconciliation.
	"""
	return _sync_inventory_rows(sheet_name, data, checksum, require_auth=True)


def _sync_store_demand_snapshot_rows(
	sheet_name: str,
	data: list[dict],
	checksum: str,
	*,
	require_auth: bool,
) -> dict:
	"""Internal upsert helper shared by API calls and scheduled jobs."""
	if require_auth:
		_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))

	latest_rows: dict[tuple[str, str, str], dict[str, Any]] = {}

	for row in rows:
		try:
			item_code = str(_first_non_empty(row, "item_code", "sku") or "").strip()
			warehouse = _resolve_warehouse(_first_non_empty(row, "warehouse", "store", "location"))
			snapshot_date = (
				_safe_date(_first_non_empty(row, "snapshot_date", "as_of_date", "date")) or nowdate()
			)

			if not item_code:
				results["rows_failed"] += 1
				results["errors"].append("Missing item_code in demand snapshot row")
				continue

			if not frappe.db.exists("Item", item_code):
				results["rows_failed"] += 1
				results["errors"].append(f"Item not found: {item_code}")
				continue

			if not warehouse:
				results["rows_failed"] += 1
				results["errors"].append(f"Warehouse not found for item {item_code}")
				continue

			row_key = (snapshot_date, warehouse, item_code)
			latest_rows[row_key] = {
				"snapshot_date": snapshot_date,
				"warehouse": warehouse,
				"item_code": item_code,
				"available_qty": flt(_first_non_empty(row, "available_qty", "available_stock") or 0),
				"avg_daily_demand": flt(
					_first_non_empty(row, "avg_daily_demand", "daily_demand", "bom_consumption") or 0
				),
				"inbound_qty": flt(_first_non_empty(row, "inbound_qty") or 0),
				"pending_po_count": cint(_first_non_empty(row, "pending_po_count") or 0),
				"delayed_po_count": cint(_first_non_empty(row, "delayed_po_count") or 0),
				"in_transit_qty": flt(_first_non_empty(row, "in_transit_qty") or 0),
				"next_eta": _first_non_empty(row, "next_eta"),
				"days_to_stockout": flt(_first_non_empty(row, "days_to_stockout") or 0),
				"projected_stockout_at": _first_non_empty(row, "projected_stockout_at"),
				"supplier_on_time_rate": flt(_first_non_empty(row, "supplier_on_time_rate") or 0),
				"risk_score": flt(_first_non_empty(row, "risk_score") or 0),
				"risk_level": _first_non_empty(row, "risk_level"),
				"value_at_risk": flt(_first_non_empty(row, "value_at_risk") or 0),
				"margin_at_risk": flt(_first_non_empty(row, "margin_at_risk") or 0),
				"source_reference": _coerce_metadata_dict(_first_non_empty(row, "source_reference")),
				"projected_sales": flt(_first_non_empty(row, "projected_sales") or 0),
				"bom_consumption": flt(_first_non_empty(row, "bom_consumption") or 0),
				"coverage_window_days": flt(_first_non_empty(row, "coverage_window_days") or 0),
				"lookback_days": cint(_first_non_empty(row, "lookback_days") or 0),
				"signal_source": _first_non_empty(row, "signal_source") or "sales_demand_snapshot",
				"channel_mix": _first_non_empty(row, "channel_mix"),
			}
		except Exception as e:
			results["errors"].append(str(e))
			results["rows_failed"] += 1

	for snapshot_key, snapshot in latest_rows.items():
		snapshot_date, warehouse, item_code = snapshot_key
		sync_ref = _sync_ref("DSNAP", sheet_name, checksum, f"{snapshot_date}|{warehouse}|{item_code}")
		savepoint = _make_savepoint("sync_dsnap", f"{sheet_name}|{checksum}|{warehouse}|{item_code}")
		frappe.db.savepoint(savepoint)
		try:
			source_reference = dict(snapshot["source_reference"])
			source_reference.update(
				{
					"sync_ref": sync_ref,
					"source_sheet": sheet_name,
					"checksum": checksum,
					"signal_source": snapshot["signal_source"],
					"lookback_days": snapshot["lookback_days"],
					"projected_sales": snapshot["projected_sales"],
					"bom_consumption": snapshot["bom_consumption"],
					"coverage_window_days": snapshot["coverage_window_days"],
				}
			)
			if snapshot["channel_mix"] not in (None, ""):
				source_reference["channel_mix"] = snapshot["channel_mix"]
			source_reference_json = json.dumps(source_reference, sort_keys=True)

			values = {
				"snapshot_date": snapshot_date,
				"warehouse": warehouse,
				"item_code": item_code,
				"available_qty": snapshot["available_qty"],
				"avg_daily_demand": snapshot["avg_daily_demand"],
				"inbound_qty": snapshot["inbound_qty"],
				"pending_po_count": snapshot["pending_po_count"],
				"delayed_po_count": snapshot["delayed_po_count"],
				"in_transit_qty": snapshot["in_transit_qty"],
				"next_eta": snapshot["next_eta"],
				"days_to_stockout": snapshot["days_to_stockout"],
				"projected_stockout_at": snapshot["projected_stockout_at"],
				"supplier_on_time_rate": snapshot["supplier_on_time_rate"],
				"risk_score": snapshot["risk_score"],
				"risk_level": snapshot["risk_level"],
				"value_at_risk": snapshot["value_at_risk"],
				"margin_at_risk": snapshot["margin_at_risk"],
				"source_reference": source_reference_json,
			}
			values = {
				fieldname: value
				for fieldname, value in values.items()
				if fieldname in {"snapshot_date", "warehouse", "item_code"}
				or _doctype_has_field("BEI Inventory Risk Snapshot", fieldname)
			}

			existing = frappe.db.get_value(
				"BEI Inventory Risk Snapshot",
				{
					"snapshot_date": snapshot_date,
					"warehouse": warehouse,
					"item_code": item_code,
				},
				"name",
			)

			if existing:
				frappe.db.set_value("BEI Inventory Risk Snapshot", existing, values, update_modified=False)
				results["rows_updated"] += 1
				_release_savepoint(savepoint)
				continue

			doc = frappe.new_doc("BEI Inventory Risk Snapshot")
			for fieldname, value in values.items():
				setattr(doc, fieldname, value)
			doc.insert(ignore_permissions=True)
			results["rows_created"] += 1
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["errors"].append(f"{warehouse}/{item_code}: {exc!s}")
			results["rows_failed"] += 1

	return results


@frappe.whitelist()
def sync_store_demand_snapshot(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""
	Sync store-item demand snapshots into BEI Inventory Risk Snapshot.

	Rows are upserted by (snapshot_date, warehouse, item_code). Additional
	demand metadata is stored as JSON in source_reference.
	"""
	return _sync_store_demand_snapshot_rows(
		sheet_name=sheet_name,
		data=data,
		checksum=checksum,
		require_auth=True,
	)


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
			invoice_no = _first_non_empty(row, "invoice_no", "invoice_no.", "reference", "bill_no")
			if not supplier_input or not invoice_no:
				results["rows_failed"] += 1
				results["errors"].append("Missing supplier or invoice_no in AP opening row")
				continue

			amount = _safe_float(
				_first_non_empty(row, "outstanding_balance", "balance", "outstanding", "amount")
			)
			company = _normalize_company(_first_non_empty(row, "company", "billed_to"))
			dedupe_key = f"{company}|{supplier_input}|{invoice_no}"
			if supplier_input and invoice_no and dedupe_key in seen_supplier_invoice_keys:
				results["rows_updated"] += 1
				continue
			if supplier_input and invoice_no:
				seen_supplier_invoice_keys.add(dedupe_key)

			if amount <= 0:
				results["rows_updated"] += 1
				continue

			savepoint = _make_savepoint("sync_ap", f"{sheet_name}|{checksum}|{dedupe_key}")
			frappe.db.savepoint(savepoint)

			posting_date = (
				_safe_date(_first_non_empty(row, "posting_date", "invoice_date", "date", "date_entry"))
				or nowdate()
			)
			due_date = _safe_date(_first_non_empty(row, "due_date")) or posting_date

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
				if _doctype_has_field("Purchase Invoice", "bei_legal_entity"):
					updates["bei_legal_entity"] = company
				if _doctype_has_field("Purchase Invoice", "bei_store_label"):
					updates["bei_store_label"] = _ap_opening_store_label(row) or "Stores - BEI"
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
			apply_standard_buying_context(
				pi,
				store_label=_ap_opening_store_label(row),
				legal_entity=company,
			)

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


def enqueue_scheduled_store_inventory_shadow_sync(
	run_date: str | None = None, force: bool = False
) -> dict[str, Any]:
	"""Queue the daily store inventory workbook shadow sync."""
	run_date_value = _safe_date(run_date) or nowdate()
	force_flag = bool(cint(force))
	job_id = f"{STORE_INVENTORY_SHADOW_SYNC_AUTO_PREFIX}:{run_date_value}"
	frappe.enqueue(
		"hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync",
		queue="long",
		job_id=job_id,
		enqueue_after_commit=True,
		run_date=run_date_value,
		force=force_flag,
	)
	return {
		"queued": True,
		"job_id": job_id,
		"run_date": run_date_value,
		"force": force_flag,
	}


def run_scheduled_store_inventory_shadow_sync(
	run_date: str | None = None, force: bool = False
) -> dict[str, Any]:
	"""Mirror store inventory sheets into Frappe using the tracked workbook bridge."""
	run_date_value = _safe_date(run_date) or nowdate()
	result = store_inventory_shadow_sync_builder.run_store_inventory_shadow_sync(
		run_date=run_date_value,
		force=bool(cint(force)),
	)
	_log_sync_run_summary(
		"Scheduled Store Inventory Shadow Sync",
		{
			"run_date": result.get("run_date"),
			"enabled_stores": result.get("enabled_stores"),
			"imported_stores": result.get("imported_stores"),
			"skipped_unchanged": result.get("skipped_unchanged"),
			"skipped_non_shadow": result.get("skipped_non_shadow"),
			"skipped_disabled": result.get("skipped_disabled"),
			"payload_rows": result.get("payload_rows"),
			"exception_rows": result.get("exception_rows"),
			"rows_created": result.get("rows_created"),
			"rows_updated": result.get("rows_updated"),
			"rows_failed": result.get("rows_failed"),
			"failed_store_count": len(result.get("failed_stores") or []),
			"output_dir": result.get("output_dir"),
		},
	)
	return result


def enqueue_scheduled_store_demand_snapshot_sync(
	snapshot_date: str | None = None, lookback_days: int = 28
) -> dict[str, Any]:
	"""Queue the daily sales-to-BOM demand snapshot sync for store ordering."""
	snapshot_date_value = _safe_date(snapshot_date) or nowdate()
	lookback_days = cint(lookback_days) or 28
	job_id = f"{STORE_DEMAND_SNAPSHOT_AUTO_PREFIX}:{snapshot_date_value}"
	frappe.enqueue(
		"hrms.api.erp_sync.run_scheduled_store_demand_snapshot_sync",
		queue="long",
		job_id=job_id,
		enqueue_after_commit=True,
		snapshot_date=snapshot_date_value,
		lookback_days=lookback_days,
	)
	return {
		"queued": True,
		"job_id": job_id,
		"snapshot_date": snapshot_date_value,
		"lookback_days": lookback_days,
	}


def run_scheduled_store_demand_snapshot_sync(
	snapshot_date: str | None = None, lookback_days: int = 28
) -> dict[str, Any]:
	"""Build and sync the mapped store demand snapshot into Frappe."""
	snapshot_date_value = _safe_date(snapshot_date) or nowdate()
	lookback_days = cint(lookback_days) or 28
	outputs = store_demand_snapshot_builder.build_outputs(
		snapshot_date=getdate(snapshot_date_value),
		lookback_days=lookback_days,
	)

	if outputs["unmapped_rows"]:
		raise RuntimeError(
			f"Aborting scheduled store demand sync: {len(outputs['unmapped_rows'])} unmapped product rows remain."
		)

	output_dir = _store_demand_output_dir(snapshot_date_value)
	_persist_store_demand_outputs(
		output_dir=output_dir,
		outputs=outputs,
		lookback_days=lookback_days,
		snapshot_date=snapshot_date_value,
	)

	checksum = hashlib.sha1(
		json.dumps(outputs["snapshot_rows"], sort_keys=True, default=str).encode()
	).hexdigest()
	sync_result = _sync_store_demand_snapshot_rows(
		sheet_name=STORE_DEMAND_SNAPSHOT_SHEET_NAME,
		data=outputs["snapshot_rows"],
		checksum=checksum,
		require_auth=False,
	)
	result = {
		"snapshot_date": snapshot_date_value,
		"lookback_days": lookback_days,
		"start_date": outputs["start_date"],
		"end_date": outputs["end_date"],
		"product_daily_rows": len(outputs["product_daily_rows"]),
		"item_daily_rows": len(outputs["item_daily_rows"]),
		"snapshot_rows": len(outputs["snapshot_rows"]),
		"mapping_audit_rows": len(outputs["mapping_audit_rows"]),
		"excluded_products": len(outputs["excluded_rows"]),
		"unmapped_products": len(outputs["unmapped_rows"]),
		"checksum": checksum,
		"output_dir": str(output_dir),
		"sync_result": sync_result,
	}
	_log_sync_run_summary(
		"Scheduled Store Demand Snapshot Sync",
		{
			"snapshot_date": result.get("snapshot_date"),
			"lookback_days": result.get("lookback_days"),
			"product_daily_rows": result.get("product_daily_rows"),
			"item_daily_rows": result.get("item_daily_rows"),
			"snapshot_rows": result.get("snapshot_rows"),
			"mapping_audit_rows": result.get("mapping_audit_rows"),
			"excluded_products": result.get("excluded_products"),
			"unmapped_products": result.get("unmapped_products"),
			"checksum": result.get("checksum"),
			"output_dir": result.get("output_dir"),
			"sync_rows_created": (result.get("sync_result") or {}).get("rows_created"),
			"sync_rows_updated": (result.get("sync_result") or {}).get("rows_updated"),
			"sync_rows_failed": (result.get("sync_result") or {}).get("rows_failed"),
		},
	)
	return result


_PROCUREMENT_APPROVED_VALUES = {"approved", "approve", "ok", "yes"}
_PROCUREMENT_REJECTED_VALUES = {
	"rejected",
	"reject",
	"disapproved",
	"declined",
	"no",
	"cancelled",
	"canceled",
}
_PROCUREMENT_NULL_TOKENS = {"na", "n/a", "none", "null", "nan"}


def _normalize_sheet_text(value: Any) -> str | None:
	if value is None:
		return None
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return None
		if text.lower() in _PROCUREMENT_NULL_TOKENS:
			return None
		return text

	text = str(value).strip()
	if not text or text.lower() in _PROCUREMENT_NULL_TOKENS:
		return None
	return text


def _truncate_text(value: Any, max_length: int = 140) -> str | None:
	text = _normalize_sheet_text(value)
	if text is None or len(text) <= max_length:
		return text
	if max_length <= 3:
		return text[:max_length]
	return f"{text[: max_length - 3].rstrip()}..."


def _normalize_file_url(value: Any) -> str | None:
	text = _normalize_sheet_text(value)
	if text is None:
		return None

	normalized = text.replace("\\", "/").strip()
	if normalized.startswith(("/files/", "/private/files/")) or "://" in normalized:
		return normalized

	filename = normalized.rsplit("/", 1)[-1].strip()
	if not filename:
		return None
	return f"/files/{filename}"


def _ensure_doc_flags(doc: Any) -> Any:
	flags = getattr(doc, "flags", None)
	if flags is None:
		flags = SimpleNamespace()
		doc.flags = flags
	return flags


def _safe_float(value: Any) -> float:
	text = _normalize_sheet_text(value)
	if text is None:
		return 0.0
	try:
		return flt(str(text).replace(",", ""))
	except Exception:
		return 0.0


def _sheet_flag(value: Any) -> int:
	text = (_normalize_sheet_text(value) or "").lower()
	return 1 if text in {"1", "true", "yes", "y"} else 0


def _normalize_approval_state(value: Any) -> str:
	text = (_normalize_sheet_text(value) or "").lower()
	if text in _PROCUREMENT_APPROVED_VALUES:
		return "Approved"
	if text in _PROCUREMENT_REJECTED_VALUES:
		return "Rejected"
	return "Pending"


def _parse_related_data(value: Any) -> dict[str, list[dict[str, Any]]]:
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except Exception:
			return {}

	if not isinstance(value, dict):
		return {}

	parsed: dict[str, list[dict[str, Any]]] = {}
	for key, rows in value.items():
		parsed[key] = _parse_rows(rows)
	return parsed


def _resolve_user_identity(name_or_email: Any = None, email: Any = None) -> str:
	email_value = _normalize_sheet_text(email)
	if email_value and frappe.db.exists("User", email_value):
		return email_value

	name_value = _normalize_sheet_text(name_or_email)
	if name_value:
		if frappe.db.exists("User", name_value):
			return name_value
		existing = frappe.db.get_value("User", {"full_name": name_value}, "name")
		if existing:
			return existing

	return "Administrator"


def _resolve_payment_terms_template(value: Any) -> str | None:
	text = _normalize_sheet_text(value)
	if not text:
		return None
	if frappe.db.exists("Payment Terms Template", text):
		return text
	return frappe.db.get_value("Payment Terms Template", {"template_name": text}, "name")


def _find_doc_by_business_key(doctype: str, fieldname: str, value: Any) -> str | None:
	text = _normalize_sheet_text(value)
	if not text:
		return None
	if frappe.db.exists(doctype, text):
		return text
	return frappe.db.get_value(doctype, {fieldname: text}, "name")


def _replace_child_rows(doc: Any, table_field: str, rows: list[dict[str, Any]]) -> None:
	if hasattr(doc, "set"):
		doc.set(table_field, [])
	else:
		setattr(doc, table_field, [])
	for row in rows:
		doc.append(table_field, row)


def _persist_doc(
	doc: Any, existing_name: str | None, business_field: str | None = None, business_value: Any = None
) -> str:
	if existing_name:
		doc.save(ignore_permissions=True)
		return "updated"

	doc.insert(ignore_permissions=True)
	if business_field and business_value and getattr(doc, business_field, None) != business_value:
		if hasattr(doc, "db_set"):
			doc.db_set(business_field, business_value, update_modified=False)
		else:
			frappe.db.set_value(doc.doctype, doc.name, business_field, business_value, update_modified=False)
		setattr(doc, business_field, business_value)
	return "created"


def _resolve_procurement_supplier(supplier_code: Any, supplier_name: Any) -> str:
	code = _normalize_sheet_text(supplier_code)
	name = _normalize_sheet_text(supplier_name)

	if code and frappe.db.exists("BEI Supplier", code):
		return code

	if name:
		existing = frappe.db.get_value("BEI Supplier", {"supplier_name": name}, "name")
		if existing:
			return existing

	if not code:
		frappe.throw(_("Supplier code is required to create missing BEI Supplier records"))

	doc = frappe.get_doc(
		{
			"doctype": "BEI Supplier",
			"supplier_code": code,
			"supplier_name": name or code,
			"status": "Pending Verification",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _resolve_item_code(item_code: Any, item_name: Any = None) -> str | None:
	code = _normalize_sheet_text(item_code)
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return code
	name = _normalize_sheet_text(item_name)
	if name:
		matched = frappe.db.get_value("Item", {"item_name": name}, "name")
		if matched:
			return matched
	return code


def _resolve_uom(value: Any) -> str | None:
	text = _normalize_sheet_text(value)
	if not text:
		return None
	if frappe.db.exists("UOM", text):
		return text
	return None


def _build_pr_status(row: dict[str, Any], items: list[dict[str, Any]]) -> str:
	if any(_normalize_sheet_text(item.get("po_reference")) for item in items):
		return "Converted to PO"
	approval_state = _normalize_approval_state(_first_non_empty(row, "approval"))
	if approval_state == "Approved":
		return "Approved"
	if approval_state == "Rejected":
		return "Rejected"
	if _normalize_sheet_text(_first_non_empty(row, "send_for_approval_timestamp")):
		return "Pending Approval"
	return "Draft"


def _build_po_status(row: dict[str, Any], requires_dual_approval: bool) -> str:
	mae_state = _normalize_approval_state(_first_non_empty(row, "approval"))
	butch_state = _normalize_approval_state(_first_non_empty(row, "2nd_approval"))
	if mae_state == "Rejected" or butch_state == "Rejected":
		return "Cancelled"
	if _normalize_sheet_text(_first_non_empty(row, "send_po_to_supplier_timestamp")):
		return "Sent to Supplier"
	if mae_state == "Approved":
		if requires_dual_approval and butch_state != "Approved":
			return "Pending Butch Approval"
		return "Approved"
	if _normalize_sheet_text(_first_non_empty(row, "send_for_approval_timestamp", "reviewer_timestamp")):
		return "Pending Mae Approval"
	return "Draft"


def _build_gr_status(row: dict[str, Any]) -> str:
	if _normalize_sheet_text(_first_non_empty(row, "approved_by", "approval_timestamp", "invoice")):
		return "Accepted"
	return "Draft"


@frappe.whitelist()
def sync_procurement_suppliers(sheet_name: str, data: list[dict], checksum: str, **kwargs) -> dict:
	"""Sync AppSheet supplier master rows into BEI Supplier."""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	results = _init_results(len(rows))
	seen_supplier_codes: set[str] = set()

	for row in rows:
		supplier_code = _normalize_sheet_text(_first_non_empty(row, "supplier_code"))
		supplier_name = _normalize_sheet_text(_first_non_empty(row, "supplier_name"))
		if not supplier_code and not supplier_name:
			continue

		dedupe_key = supplier_code or supplier_name or "unknown"
		if dedupe_key in seen_supplier_codes:
			results["rows_updated"] += 1
			continue
		seen_supplier_codes.add(dedupe_key)

		savepoint = _make_savepoint("sync_proc_supplier", f"{sheet_name}|{checksum}|{dedupe_key}")
		frappe.db.savepoint(savepoint)
		try:
			if not supplier_code:
				raise ValueError(f"Missing supplier_code for supplier '{supplier_name or 'unknown'}'")

			existing_name = _find_doc_by_business_key("BEI Supplier", "supplier_code", supplier_code)
			if not existing_name and supplier_name:
				existing_name = frappe.db.get_value("BEI Supplier", {"supplier_name": supplier_name}, "name")

			doc = (
				frappe.get_doc("BEI Supplier", existing_name)
				if existing_name
				else frappe.get_doc({"doctype": "BEI Supplier"})
			)
			doc.supplier_code = supplier_code
			doc.supplier_name = supplier_name or supplier_code
			doc.contact_number = _normalize_sheet_text(_first_non_empty(row, "contact_no", "contact_number"))
			doc.contact_person = _normalize_sheet_text(_first_non_empty(row, "contact_person"))
			doc.email = _normalize_sheet_text(_first_non_empty(row, "email_id", "email"))
			doc.address = _normalize_sheet_text(_first_non_empty(row, "address"))
			doc.bank_name = _normalize_sheet_text(_first_non_empty(row, "bank_name"))
			doc.bank_account_name = _normalize_sheet_text(_first_non_empty(row, "bank_account_name"))
			doc.bank_account_number = _normalize_sheet_text(
				_first_non_empty(row, "bank_account_no", "bank_account_number")
			)
			if not existing_name and not _normalize_sheet_text(getattr(doc, "status", None)):
				doc.status = "Pending Verification"

			action = _persist_doc(
				doc, existing_name, business_field="supplier_code", business_value=supplier_code
			)
			results[f"rows_{action}"] += 1
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["rows_failed"] += 1
			results["errors"].append(f"{dedupe_key}: {exc!s}")

	return results


@frappe.whitelist()
def sync_procurement_requisitions(
	sheet_name: str,
	data: list[dict],
	checksum: str,
	related_data: Any = None,
	**kwargs,
) -> dict:
	"""Sync AppSheet PR headers with PR item rows into BEI Purchase Requisition."""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	related = _parse_related_data(related_data)
	results = _init_results(len(rows))
	seen_pr_numbers: set[str] = set()
	supports_pr_item_po_reference = _doctype_has_field("BEI PR Item", "po_reference")

	items_by_pr: dict[str, list[dict[str, Any]]] = {}
	for item_row in related.get("procurement_pr_items", []):
		pr_no = _normalize_sheet_text(_first_non_empty(item_row, "pr_no"))
		item_code = _normalize_sheet_text(_first_non_empty(item_row, "item_code"))
		description = _normalize_sheet_text(_first_non_empty(item_row, "description"))
		qty = _safe_float(_first_non_empty(item_row, "total_order", "qty"))
		if not pr_no or not item_code or qty <= 0:
			continue

		items_by_pr.setdefault(pr_no, []).append(
			{
				"item_code": item_code,
				"item_name": _normalize_sheet_text(_first_non_empty(item_row, "item_name"))
				or description
				or item_code,
				"description": description,
				"qty": qty,
				"uom": _normalize_sheet_text(_first_non_empty(item_row, "unit_of_issue", "uom")) or "Pcs",
				"po_reference": _truncate_text(_first_non_empty(item_row, "po_reference")),
				"added_by": _normalize_sheet_text(_first_non_empty(item_row, "added_by")),
			}
		)

	for row in rows:
		pr_no = _normalize_sheet_text(_first_non_empty(row, "pr_no"))
		if not pr_no:
			continue
		if pr_no in seen_pr_numbers:
			results["rows_updated"] += 1
			continue
		seen_pr_numbers.add(pr_no)

		savepoint = _make_savepoint("sync_proc_pr", f"{sheet_name}|{checksum}|{pr_no}")
		frappe.db.savepoint(savepoint)
		try:
			items = items_by_pr.get(pr_no, [])
			if not items:
				raise ValueError("No PR items found for requisition")

			existing_name = _find_doc_by_business_key("BEI Purchase Requisition", "pr_no", pr_no)
			doc = (
				frappe.get_doc("BEI Purchase Requisition", existing_name)
				if existing_name
				else frappe.get_doc({"doctype": "BEI Purchase Requisition"})
			)

			doc.request_date = _safe_date(_first_non_empty(row, "timestamp")) or nowdate()
			doc.requested_by = _resolve_user_identity(
				_first_non_empty(row, "requested_by"),
				_first_non_empty(row, "requested_by_email"),
			)
			doc.delivery_to = _resolve_warehouse(_first_non_empty(row, "delivery_to"))
			doc.date_required = _safe_date(_first_non_empty(row, "date_required")) or doc.request_date
			doc.purpose = _normalize_sheet_text(_first_non_empty(row, "purpose")) or "Legacy AppSheet import"
			doc.recurring = _sheet_flag(_first_non_empty(row, "recurring"))
			doc.status = _build_pr_status(row, items)
			doc.approved_by = (
				_resolve_user_identity(
					_first_non_empty(row, "approved_by"), _first_non_empty(row, "approved_by_email")
				)
				if doc.status in {"Approved", "Rejected", "Converted to PO"}
				else None
			)
			doc.approval_date = _safe_date(_first_non_empty(row, "approval_timestamp"))
			doc.rejection_reason = (
				_normalize_sheet_text(_first_non_empty(row, "comment")) if doc.status == "Rejected" else None
			)
			child_rows = (
				items
				if supports_pr_item_po_reference
				else [{k: v for k, v in item.items() if k != "po_reference"} for item in items]
			)
			_replace_child_rows(doc, "items", child_rows)

			action = _persist_doc(doc, existing_name, business_field="pr_no", business_value=pr_no)
			results[f"rows_{action}"] += 1
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["rows_failed"] += 1
			results["errors"].append(f"{pr_no}: {exc!s}")

	return results


@frappe.whitelist()
def sync_procurement_purchase_orders(
	sheet_name: str,
	data: list[dict],
	checksum: str,
	related_data: Any = None,
	**kwargs,
) -> dict:
	"""Sync AppSheet PO headers with child items into BEI Purchase Order."""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	related = _parse_related_data(related_data)
	results = _init_results(len(rows))
	seen_po_numbers: set[str] = set()

	items_by_po: dict[str, list[dict[str, Any]]] = {}
	for item_row in related.get("procurement_po_items", []):
		po_no = _normalize_sheet_text(_first_non_empty(item_row, "po_no"))
		item_code = _normalize_sheet_text(_first_non_empty(item_row, "item_code"))
		qty = _safe_float(_first_non_empty(item_row, "qty"))
		unit_cost = _safe_float(_first_non_empty(item_row, "unit_cost"))
		if not po_no or not item_code or qty <= 0:
			continue

		vat_per_unit = _safe_float(_first_non_empty(item_row, "vat"))
		vat_rate = round((vat_per_unit / unit_cost) * 100, 4) if unit_cost > 0 and vat_per_unit > 0 else 12.0
		items_by_po.setdefault(po_no, []).append(
			{
				"item_code": item_code,
				"item_name": _normalize_sheet_text(_first_non_empty(item_row, "item_name")) or item_code,
				"description": _normalize_sheet_text(_first_non_empty(item_row, "item_name")) or item_code,
				"packaging_size": _normalize_sheet_text(_first_non_empty(item_row, "packaging_size")),
				"qty": qty,
				"uom": _normalize_sheet_text(_first_non_empty(item_row, "uom")) or "Pcs",
				"unit_cost": unit_cost,
				"vat_rate": vat_rate,
				"delivery_schedule": _safe_date(_first_non_empty(item_row, "delivery_schedule")),
				"price_variance_override": "Legacy AppSheet sync baseline import",
			}
		)

	for row in rows:
		po_no = _normalize_sheet_text(_first_non_empty(row, "po_no"))
		if not po_no:
			continue
		if po_no in seen_po_numbers:
			results["rows_updated"] += 1
			continue
		seen_po_numbers.add(po_no)

		savepoint = _make_savepoint("sync_proc_po", f"{sheet_name}|{checksum}|{po_no}")
		frappe.db.savepoint(savepoint)
		try:
			items = items_by_po.get(po_no, [])
			if not items:
				raise ValueError("No PO items found for purchase order")

			existing_name = _find_doc_by_business_key("BEI Purchase Order", "po_no", po_no)
			doc = (
				frappe.get_doc("BEI Purchase Order", existing_name)
				if existing_name
				else frappe.get_doc({"doctype": "BEI Purchase Order"})
			)

			doc.po_date = _safe_date(_first_non_empty(row, "po_date", "timestamp")) or nowdate()
			doc.pr_reference = _find_doc_by_business_key(
				"BEI Purchase Requisition", "pr_no", _first_non_empty(row, "pr_no")
			)
			doc.supplier = _resolve_procurement_supplier(
				_first_non_empty(row, "supplier_code"),
				_first_non_empty(row, "supplier_name"),
			)
			doc.delivery_date = _safe_date(_first_non_empty(row, "delivery_date")) or doc.po_date
			doc.ship_to = _resolve_warehouse(_first_non_empty(row, "ship_to"))
			doc.payment_terms = _resolve_payment_terms_template(_first_non_empty(row, "terms_of_payment"))
			doc.discount_amount = _safe_float(_first_non_empty(row, "total_discount"))
			doc.delivery_fee = _safe_float(_first_non_empty(row, "delivery_fee"))
			doc.mae_approval = _normalize_approval_state(_first_non_empty(row, "approval"))
			doc.mae_comment = _normalize_sheet_text(_first_non_empty(row, "comment", "reviewer_comment"))
			doc.mae_approval_date = _safe_date(_first_non_empty(row, "approval_timestamp"))
			doc.butch_approval = _normalize_approval_state(_first_non_empty(row, "2nd_approval"))
			doc.butch_comment = _normalize_sheet_text(_first_non_empty(row, "2nd_comment"))
			doc.butch_approval_date = _safe_date(_first_non_empty(row, "2nd_approval_timestamp"))
			doc.sent_to_supplier_date = _safe_date(_first_non_empty(row, "send_po_to_supplier_timestamp"))
			doc.sent_by = (
				_resolve_user_identity(_first_non_empty(row, "sent_by"))
				if _normalize_sheet_text(_first_non_empty(row, "sent_by"))
				else None
			)
			_replace_child_rows(doc, "items", items)
			estimated_grand_total = sum(
				_safe_float(item.get("qty"))
				* _safe_float(item.get("unit_cost"))
				* (1 + (_safe_float(item.get("vat_rate")) / 100))
				for item in items
			)
			estimated_grand_total = (
				estimated_grand_total
				- _safe_float(_first_non_empty(row, "total_discount"))
				+ _safe_float(_first_non_empty(row, "delivery_fee"))
			)
			doc.status = _build_po_status(row, requires_dual_approval=estimated_grand_total > 500000)

			action = _persist_doc(doc, existing_name, business_field="po_no", business_value=po_no)
			results[f"rows_{action}"] += 1
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["rows_failed"] += 1
			results["errors"].append(f"{po_no}: {exc!s}")

	return results


@frappe.whitelist()
def sync_procurement_goods_receipts(
	sheet_name: str,
	data: list[dict],
	checksum: str,
	related_data: Any = None,
	**kwargs,
) -> dict:
	"""Sync AppSheet GR headers and items into BEI Goods Receipt, then reconcile PO receipts."""
	_assert_sync_authorized()
	rows = _parse_rows(data)
	related = _parse_related_data(related_data)
	results = _init_results(len(rows))
	seen_gr_numbers: set[str] = set()
	po_doc_cache: dict[str, Any] = {}
	po_name_cache: dict[str, str] = {}
	received_qty_by_po: dict[str, dict[str, float]] = {}

	def get_po_doc(po_no: str) -> Any:
		if po_no in po_doc_cache:
			return po_doc_cache[po_no]

		po_name = _find_doc_by_business_key("BEI Purchase Order", "po_no", po_no)
		if not po_name:
			raise ValueError(f"Linked purchase order not found: {po_no}")

		po_name_cache[po_no] = po_name
		po_doc_cache[po_no] = frappe.get_doc("BEI Purchase Order", po_name)
		return po_doc_cache[po_no]

	items_by_gr: dict[str, list[dict[str, Any]]] = {}
	for item_row in related.get("procurement_gr_items", []):
		gr_no = _normalize_sheet_text(_first_non_empty(item_row, "gr_no"))
		po_no = _normalize_sheet_text(_first_non_empty(item_row, "po_no"))
		item_code = _normalize_sheet_text(_first_non_empty(item_row, "item_code"))
		received_qty = _safe_float(_first_non_empty(item_row, "issued_qty", "received_qty"))
		if not gr_no or not po_no or not item_code or received_qty <= 0:
			continue

		po_doc = get_po_doc(po_no)
		po_item_lookup = {po_item.item_code: po_item for po_item in getattr(po_doc, "items", [])}
		po_item = po_item_lookup.get(item_code)
		resolved_item_code = _resolve_item_code(item_code, _first_non_empty(item_row, "item_name"))
		items_by_gr.setdefault(gr_no, []).append(
			{
				"item_code": resolved_item_code,
				"item_name": _normalize_sheet_text(_first_non_empty(item_row, "item_name")) or item_code,
				"description": _normalize_sheet_text(_first_non_empty(item_row, "item_name")) or item_code,
				"ordered_qty": flt(getattr(po_item, "qty", received_qty), 2) if po_item else received_qty,
				"received_qty": received_qty,
				"uom": _resolve_uom(_first_non_empty(item_row, "uom")),
				"rejected_qty": 0,
				"unit_cost": flt(getattr(po_item, "unit_cost", 0), 2) if po_item else 0,
			}
		)
		received_qty_by_po.setdefault(po_no, {})
		received_qty_by_po[po_no][item_code] = received_qty_by_po[po_no].get(item_code, 0) + received_qty

	for row in rows:
		gr_no = _normalize_sheet_text(_first_non_empty(row, "gr_no"))
		po_no = _normalize_sheet_text(_first_non_empty(row, "po_no"))
		if not gr_no:
			continue
		if gr_no in seen_gr_numbers:
			results["rows_updated"] += 1
			continue
		seen_gr_numbers.add(gr_no)

		savepoint = _make_savepoint("sync_proc_gr", f"{sheet_name}|{checksum}|{gr_no}")
		frappe.db.savepoint(savepoint)
		try:
			if not po_no:
				raise ValueError("Missing linked purchase order reference")

			po_doc = get_po_doc(po_no)
			items = items_by_gr.get(gr_no, [])
			if not items:
				raise ValueError("No GR items found for goods receipt")

			existing_name = _find_doc_by_business_key("BEI Goods Receipt", "gr_no", gr_no)
			doc = (
				frappe.get_doc("BEI Goods Receipt", existing_name)
				if existing_name
				else frappe.get_doc({"doctype": "BEI Goods Receipt"})
			)

			doc.purchase_order = po_doc.name
			doc.receipt_date = _safe_date(_first_non_empty(row, "date", "timestamp")) or nowdate()
			doc.delivery_date = _safe_date(_first_non_empty(row, "date")) or doc.receipt_date
			doc.delivery_note_no = _normalize_sheet_text(_first_non_empty(row, "invoice_no")) or gr_no
			doc.warehouse = _resolve_warehouse(_first_non_empty(row, "issue_to"))
			if _doctype_has_field("BEI Goods Receipt", "supplier_invoice_photo"):
				doc.supplier_invoice_photo = _normalize_file_url(_first_non_empty(row, "invoice"))
			_ensure_doc_flags(doc).ignore_mandatory = True
			doc.inspection_required = 0
			doc.status = _build_gr_status(row)
			_replace_child_rows(doc, "items", items)

			action = _persist_doc(doc, existing_name, business_field="gr_no", business_value=gr_no)
			results[f"rows_{action}"] += 1
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["rows_failed"] += 1
			results["errors"].append(f"{gr_no}: {exc!s}")

	for po_no, item_totals in received_qty_by_po.items():
		savepoint = _make_savepoint("sync_proc_gr_po", f"{sheet_name}|{checksum}|{po_no}")
		frappe.db.savepoint(savepoint)
		try:
			po_doc = get_po_doc(po_no)
			changed = False
			for po_item in getattr(po_doc, "items", []):
				new_qty = flt(item_totals.get(po_item.item_code, 0), 2)
				if flt(getattr(po_item, "received_qty", 0), 2) != new_qty:
					po_item.received_qty = new_qty
					if getattr(po_item, "name", None):
						frappe.db.set_value(
							"BEI PO Item", po_item.name, "received_qty", new_qty, update_modified=False
						)
					changed = True

			fully_received = bool(getattr(po_doc, "items", [])) and all(
				flt(getattr(item, "received_qty", 0), 2) >= flt(getattr(item, "qty", 0), 2)
				for item in po_doc.items
			)
			partially_received = any(
				flt(getattr(item, "received_qty", 0), 2) > 0 for item in getattr(po_doc, "items", [])
			)
			new_status = po_doc.status
			if fully_received:
				new_status = "Fully Received"
			elif partially_received:
				new_status = "Partially Received"

			if new_status != po_doc.status:
				po_doc.status = new_status
				changed = True

			if changed:
				po_doc.save(ignore_permissions=True)
			_release_savepoint(savepoint)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			results["errors"].append(f"{po_no}: failed to reconcile PO received qty - {exc!s}")

	return results


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
