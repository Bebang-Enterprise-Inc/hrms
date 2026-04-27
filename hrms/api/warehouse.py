# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Warehouse Supervisor APIs
Handles PO receiving, Material Request approval, and stock transfers for Ian.

Author: Claude Code
Date: 2026-02-02
"""

import json
from contextlib import contextmanager
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from hrms.utils.bei_config import get_company
from hrms.utils.scm_roles import (
	SCM_APPROVAL_ROLES,
	SCM_DISPATCH_ROLES,
	SCM_RECEIVING_ROLES,
	check_scm_permission,
)
from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.standard_buying_bridge import apply_standard_buying_context
from hrms.utils.supply_chain_contracts import (
	CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
	FINANCE_TREATMENT_INTERCOMPANY,
	FINANCE_TREATMENT_SAME_COMPANY,
	REQUEST_SOURCE_COMMISSARY_FG_TRANSFER,
	REQUEST_SOURCE_STORE_ORDER,
	TEST_COMMISSARY_OPERATION_WAREHOUSE,
	get_preferred_commissary_warehouses,
	get_request_source_label,
	infer_finance_treatment,
	resolve_material_request_contract,
	resolve_warehouse_company,
	stamp_stock_entry_contract,
	strip_company_suffix,
)

# ============================================================
# 1. SUPPLIER RECEIVING
# ============================================================


def _resolve_warehouse_name(name: str) -> str:
	"""Resolve a partial/short warehouse name to the full Frappe Warehouse name.

	Frappe Link fields require exact name matches.  Users (and frontends) sometimes
	pass short names like "3MD Warehouse" instead of "3MD Logistics - Camangyanan -
	Bebang Enterprise Inc."  This mirrors the proven pattern from store.resolve_warehouse
	without throwing -- on failure it returns the original so the Stock Entry itself emits
	a clear LinkValidationError.
	"""
	if not name or frappe.db.exists("Warehouse", name):
		return name
	for suffix in (" - BEI", " - BKI"):
		if frappe.db.exists("Warehouse", f"{name}{suffix}"):
			return f"{name}{suffix}"
	match = frappe.db.get_value("Warehouse", {"warehouse_name": name}, "name")
	if match:
		return match
	prefix = name.split()[0] if " " in name else name
	like_match = frappe.db.get_value("Warehouse", {"name": ["like", f"{prefix}%"], "is_group": 0}, "name")
	if like_match:
		return like_match
	return name


def _row_value(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


def _ensure_warehouse_receiving_doctype():
	if not frappe.db.exists("DocType", "BEI Warehouse Receiving"):
		frappe.throw(_("BEI Warehouse Receiving DocType is not installed"))


def _notify_warehouse_handoff(
	receiving_name: str, source_warehouse: str | None = None, target_warehouse: str | None = None
) -> None:
	"""S093 (UX-011): Notify warehouse team of incoming commissary handoff via GChat + in-app."""
	try:
		from hrms.api.google_chat import send_message_to_space
		from hrms.utils.bei_config import SPACE_OPS, get_chat_space

		# get_chat_space returns a resource path like "spaces/XXXX" compatible with send_message_to_space
		space_name = get_chat_space(SPACE_OPS)
		if space_name:
			send_message_to_space(
				space_name,
				f"\U0001f4e6 New commissary handoff: *{receiving_name}*\n"
				f"From: {source_warehouse or 'Commissary'} \u2192 To: {target_warehouse or 'Warehouse'}\n"
				f"Check warehouse receiving queue: https://my.bebang.ph/dashboard/warehouse/receiving",
			)
	except Exception as e:
		frappe.log_error(f"Warehouse handoff notification failed for {receiving_name}: {e}", "Warehouse API")


def _get_store_crew_recipients(target_warehouse: str) -> list[str]:
	"""S198 (P3-T1): Resolve store crew email recipients for dispatch notification.

	Returns list of emails (capped at 20) by querying:
	  1. Warehouse.custom_area_supervisor (custom field on Warehouse doctype)
	  2. Employee WHERE branch = target_warehouse (standard HR link)
	"""
	recipients: list[str] = []
	if not target_warehouse:
		return recipients

	try:
		# 1. Area supervisor from Warehouse custom field
		area_sup = frappe.db.get_value("Warehouse", target_warehouse, "custom_area_supervisor")
		if area_sup:
			# custom_area_supervisor stores a User ID (email)
			recipients.append(area_sup)

		# 2. Employees assigned to this branch/store
		employees = frappe.get_all(
			"Employee",
			filters={"branch": target_warehouse, "status": "Active"},
			fields=["user_id"],
			limit_page_length=20,
		)
		for emp in employees:
			uid = emp.get("user_id")
			if uid and uid not in recipients:
				recipients.append(uid)
	except Exception as e:
		frappe.log_error(
			f"S198: Failed to resolve store crew recipients for {target_warehouse}: {e}",
			"Warehouse API",
		)

	return recipients[:20]


def _warehouse_receiving_item_rows(receiving_doc):
	rows = []
	for item in receiving_doc.items:
		rows.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"batch_no": getattr(item, "batch_no", None),
				"uom": getattr(item, "uom", None),
				"expected_qty": flt(item.expected_qty or 0),
				"received_qty": flt(item.received_qty or 0),
				"rejected_qty": flt(item.rejected_qty or 0),
				"accepted_qty": flt(item.accepted_qty or 0),
				"has_issue": cint(getattr(item, "has_issue", 0)),
				"issue_notes": getattr(item, "issue_notes", None),
			}
		)
	return rows


def _enable_role_gated_write(doc: Any):
	"""Use explicit SCM role checks as the write gate for workflow-owned mutations."""
	if getattr(doc, "flags", None) is None:
		doc.flags = type("_WarehouseDocFlags", (), {})()
	doc.flags.ignore_permissions = True
	doc.flags.ignore_user_permissions = True
	return doc


@contextmanager
def _run_as_system_user(user: str = "Administrator"):
	"""Temporarily elevate the session user for internal stock movements."""
	session = getattr(frappe, "session", None)
	if session is None:
		session = getattr(getattr(frappe, "local", None), "session", None)
	original_user = getattr(session, "user", None)
	try:
		if session and user:
			session.user = user
		yield
	finally:
		if session and original_user:
			session.user = original_user


def _resolve_valid_item_uom(item_doc: Any, requested_uom: str | None = None) -> str:
	"""Prefer the requested UOM only when it exists in the UOM master.

	Stock movements must use a valid UOM master record. Some operational feeds still
	send packaging labels such as "TRAY" that are not configured as ERP UOMs. When
	that happens, fall back to the item's real stock UOM instead of letting the stock
	transaction fail later with a LinkValidationError.
	"""
	candidates: list[str] = []
	for raw_value in [requested_uom, getattr(item_doc, "stock_uom", None)]:
		value = str(raw_value or "").strip()
		if value and value not in candidates:
			candidates.append(value)

	for row in getattr(item_doc, "uoms", None) or []:
		value = str(_row_value(row, "uom", "") or "").strip()
		if value and value not in candidates:
			candidates.append(value)

	for candidate in candidates:
		if frappe.db.exists("UOM", candidate):
			return candidate

	frappe.throw(
		_("No valid UOM master record found for item {0}. Checked: {1}").format(
			item_doc.name,
			", ".join(candidates) or _("none"),
		)
	)


def _clear_legacy_serial_batch_fields_after_auto_bundle(stock_entry: Any) -> None:
	"""Avoid duplicate auto-bundle validation on submit.

	ERPNext v15 can auto-create `serial_and_batch_bundle` rows when a draft stock
	transaction is inserted with old-style `batch_no` / `serial_no` values. When the
	same document is then submitted, ERPNext rejects rows that still carry both the
	auto-bundle reference and the legacy fields. Clear those legacy fields once the
	bundle exists so submit reuses the created bundle instead of trying to recreate it.
	"""
	for item in getattr(stock_entry, "items", None) or []:
		if not getattr(item, "serial_and_batch_bundle", None):
			continue
		if getattr(item, "batch_no", None):
			item.batch_no = None
		if getattr(item, "serial_no", None):
			item.serial_no = None


def _resolve_stock_entry_item_valuation(item_code: str, warehouse: str | None):
	"""Return a stable valuation context for outbound stock rows.

	Material Issue movements can fail at submit time when the source stock has no
	valuation rate yet. When that happens, explicitly mark the row as an allowed
	zero-valuation movement so dispatch does not die on a generic 417/validation error.
	"""
	bin_rate = flt(
		frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate") or 0
	)
	if bin_rate > 0:
		return bin_rate, False

	item_rates = frappe.db.get_value(
		"Item",
		item_code,
		["valuation_rate", "standard_rate", "last_purchase_rate"],
		as_dict=True,
	) or {"valuation_rate": 0, "standard_rate": 0, "last_purchase_rate": 0}
	resolved_rate = flt(
		item_rates.get("valuation_rate")
		or item_rates.get("standard_rate")
		or item_rates.get("last_purchase_rate")
		or 0
	)
	return resolved_rate, resolved_rate <= 0


@frappe.whitelist()
def get_pending_purchase_orders(item_code=None, warehouse=None):
	"""
	Get POs pending receipt at warehouse.
	Returns POs with status='To Receive and Bill' or 'To Receive'.
	P0-12 fix: Batch items fetch into single query (was N+1).
	"""
	item_code_filter = (item_code or "").strip()
	warehouse_filter = (warehouse or "").strip()

	pos = frappe.get_all(
		"Purchase Order",
		filters={"status": ["in", ["To Receive and Bill", "To Receive"]], "docstatus": 1},
		fields=[
			"name",
			"supplier",
			"supplier_name",
			"transaction_date",
			"grand_total",
			"status",
			"per_received",
		],
		order_by="transaction_date desc",
		limit=50,
	)

	if not pos:
		return {"success": True, "data": []}

	# P0-12: Batch-fetch all items for all POs in a single query
	po_names = [_row_value(po, "name") for po in pos]
	all_items = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": ["in", po_names]},
		fields=["parent", "item_code", "item_name", "qty", "received_qty", "uom", "warehouse"],
	)

	# Group items by PO
	items_by_po = {}
	for item in all_items:
		items_by_po.setdefault(_row_value(item, "parent"), []).append(item)

	filtered_pos = []
	for po in pos:
		po_name = _row_value(po, "name")
		items = items_by_po.get(po_name, [])

		has_item_match = (
			True
			if not item_code_filter
			else any(_row_value(i, "item_code") == item_code_filter for i in items)
		)
		has_warehouse_match = (
			True
			if not warehouse_filter
			else any(_row_value(i, "warehouse") == warehouse_filter for i in items)
		)
		if not (has_item_match and has_warehouse_match):
			continue

		visible_items = items
		if item_code_filter:
			visible_items = [i for i in visible_items if _row_value(i, "item_code") == item_code_filter]
		if warehouse_filter:
			visible_items = [i for i in visible_items if _row_value(i, "warehouse") == warehouse_filter]

		po["has_item_match"] = has_item_match
		po["has_warehouse_match"] = has_warehouse_match
		po["items"] = visible_items
		po["items_count"] = len(visible_items)
		po["pending_items"] = sum(
			1 for i in visible_items if flt(_row_value(i, "qty")) > flt(_row_value(i, "received_qty"))
		)
		filtered_pos.append(po)

	return {"success": True, "data": filtered_pos}


@frappe.whitelist()
def get_purchase_order_items(po_name):
	"""
	Get detailed items for a specific PO with receiving status.
	"""
	if not frappe.db.exists("Purchase Order", po_name):
		frappe.throw(_("Purchase Order not found"))

	po = frappe.get_doc("Purchase Order", po_name)

	items = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": po_name},
		fields=[
			"name",
			"item_code",
			"item_name",
			"description",
			"qty",
			"received_qty",
			"uom",
			"rate",
			"amount",
			"warehouse",
		],
	)

	# Calculate pending qty for each item
	for item in items:
		item["pending_qty"] = item["qty"] - item["received_qty"]

	return {
		"success": True,
		"data": {
			"po_name": po.name,
			"supplier": po.supplier,
			"supplier_name": po.supplier_name,
			"transaction_date": po.transaction_date,
			"grand_total": po.grand_total,
			"items": items,
		},
	}


@frappe.whitelist()
def create_purchase_receipt(
	po_name: str, items: str | list[dict[str, Any]], remarks: str | None = None
) -> dict[str, Any]:
	"""
	Create Purchase Receipt from PO.

	Args:
	    po_name: Purchase Order name
	    items: JSON array of {item_code, received_qty, rejected_qty, warehouse}
	    remarks: Optional notes

	Returns:
	    Purchase Receipt name
	"""
	if isinstance(items, str):
		items = json.loads(items)

	set_backend_observability_context(
		module="warehouse",
		action="create_purchase_receipt",
		mutation_type="create",
	)
	check_scm_permission(SCM_RECEIVING_ROLES, "receive supplier purchase orders")

	if not frappe.db.exists("Purchase Order", po_name):
		frappe.throw(_("Purchase Order not found"))

	po = frappe.get_doc("Purchase Order", po_name)

	# Create Purchase Receipt
	pr = frappe.new_doc("Purchase Receipt")
	pr.supplier = po.supplier
	pr.supplier_name = po.supplier_name
	pr.company = po.company
	pr.currency = getattr(po, "currency", None) or "PHP"
	pr.buying_price_list = getattr(po, "buying_price_list", None) or "Standard Buying"
	pr.price_list_currency = getattr(po, "price_list_currency", None) or pr.currency
	pr.plc_conversion_rate = flt(getattr(po, "plc_conversion_rate", None) or 1)
	pr.conversion_rate = flt(getattr(po, "conversion_rate", None) or 1)
	pr.set_warehouse = getattr(po, "set_warehouse", None)
	pr.posting_date = frappe.utils.today()
	pr.posting_time = frappe.utils.nowtime()
	pr.remarks = remarks or f"Received against {po_name}"
	apply_standard_buying_context(pr, store_label=pr.set_warehouse or "Stores - BEI", legal_entity=po.company)

	# Add items
	for item_data in items:
		# Find matching PO item
		po_item = next((i for i in po.items if i.item_code == item_data["item_code"]), None)
		if not po_item:
			continue

		received_qty = item_data.get("received_qty", 0)
		if received_qty <= 0:
			continue

		item_doc = frappe.get_doc("Item", item_data["item_code"])
		valid_uom = _resolve_valid_item_uom(item_doc, getattr(po_item, "uom", None))

		pr.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": po_item.item_name,
				"description": po_item.description,
				"qty": received_qty,
				"rejected_qty": item_data.get("rejected_qty", 0),
				"uom": valid_uom,
				"stock_uom": valid_uom,
				"conversion_factor": po_item.conversion_factor or 1,
				"rate": po_item.rate,
				"warehouse": item_data.get("warehouse") or po_item.warehouse,
				"purchase_order": po_name,
				"purchase_order_item": po_item.name,
			},
		)

	if not pr.items:
		frappe.throw(_("No items to receive"))

	_enable_role_gated_write(pr)
	pr.insert(ignore_permissions=True)
	with _run_as_system_user("Administrator"):
		pr.submit()

	return {
		"success": True,
		"data": {"name": pr.name, "grand_total": pr.grand_total, "items_count": len(pr.items)},
		"message": f"Purchase Receipt {pr.name} created successfully",
	}


_3PL_PATTERNS_DEFAULT = ("3MD", "Pinnacle", "Royal Cold", "RCS")
_ALLOWED_TARGET_COMPANIES_DEFAULT = {"Bebang Kitchen Inc.", "Bebang Enterprise Inc."}
_COMMISSARY_COMPANY_DEFAULT = "Bebang Kitchen Inc."


def _get_commissary_company() -> str:
	"""Get commissary company from BEI Settings, falling back to hardcoded default."""
	try:
		val = frappe.db.get_single_value("BEI Settings", "commissary_company")
		if val:
			return val
	except Exception:
		pass
	return _COMMISSARY_COMPANY_DEFAULT


def _get_allowed_target_companies() -> set[str]:
	"""Get allowed target companies.

	S204: Auto-derive from the live `Company` master (every non-group,
	non-disabled Company is a legitimate dispatch target) and union with the
	`BEI Settings.allowed_target_companies` CSV so Finance can still
	explicitly allow or add entries. This stops the allowlist drifting every
	time S199 adds a store-first rename or a new entity is onboarded — the
	source of truth is the Company master, not a manually-maintained string.
	"""
	companies: set[str] = set()

	# Primary source: all active, non-group Company records
	try:
		rows = frappe.db.sql(
			"""
			SELECT name FROM `tabCompany`
			WHERE COALESCE(is_group, 0) = 0
			""",
			as_dict=True,
		)
		companies.update(row["name"] for row in rows if row.get("name"))
	except Exception:
		pass

	# Override / extension: BEI Settings CSV (kept for Finance-level overrides)
	try:
		val = frappe.db.get_single_value("BEI Settings", "allowed_target_companies")
		if val:
			companies.update(c.strip() for c in val.split(",") if c.strip())
	except Exception:
		pass

	# Fallback if both above failed (fresh install, DB error, etc.)
	if not companies:
		companies.update(_ALLOWED_TARGET_COMPANIES_DEFAULT)
	return companies


def _get_3pl_patterns() -> tuple[str, ...]:
	"""Get 3PL warehouse patterns from BEI Settings, falling back to hardcoded defaults."""
	try:
		patterns_str = frappe.db.get_single_value("BEI Settings", "three_pl_warehouse_patterns")
		if patterns_str:
			return tuple(p.strip() for p in patterns_str.split(",") if p.strip())
	except Exception:
		pass
	return _3PL_PATTERNS_DEFAULT


def _is_3pl_warehouse(warehouse_name: str) -> bool:
	"""Check if a warehouse name matches a known 3PL partner pattern."""
	upper = (warehouse_name or "").upper()
	return any(p.upper() in upper for p in _get_3pl_patterns())


@frappe.whitelist()
def get_internal_receiving_warehouses():
	"""List warehouses that can receive commissary finished goods, grouped by type.

	Returns 3PL warehouses (3MD, Pinnacle, RCS) as the primary group and
	BEI store warehouses as a secondary group for direct commissary-to-store dispatch.
	"""
	commissary_source_warehouse = None
	try:
		from hrms.api.commissary import get_commissary_warehouse

		commissary_source_warehouse = get_commissary_warehouse()
	except Exception:
		commissary_source_warehouse = None

	excluded_warehouses = set(get_preferred_commissary_warehouses(include_legacy=True))
	excluded_warehouses.update(
		name
		for name in (
			CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
			TEST_COMMISSARY_OPERATION_WAREHOUSE,
			commissary_source_warehouse,
		)
		if name
	)

	allowed_companies = _get_allowed_target_companies()

	warehouses = frappe.get_all(
		"Warehouse",
		filters={"is_group": 0},
		fields=["name", "warehouse_name", "company"],
		order_by="warehouse_name asc",
	)

	items_3pl = []
	items_store = []
	for warehouse in warehouses:
		company = warehouse.get("company") or resolve_warehouse_company(warehouse.get("name"))
		name = warehouse.get("name") or ""
		if company not in allowed_companies:
			continue
		if name in excluded_warehouses:
			continue
		entry = {
			"name": name,
			"label": warehouse.get("warehouse_name") or strip_company_suffix(name),
			"company": company,
		}
		if _is_3pl_warehouse(name):
			entry["group"] = "3pl"
			items_3pl.append(entry)
		else:
			entry["group"] = "store"
			items_store.append(entry)

	return {"success": True, "data": items_3pl + items_store}


@frappe.whitelist()
def create_warehouse_receiving(
	source_warehouse: str,
	target_warehouse: str,
	items: list | str,
	linked_quality_inspection: str | None = None,
	linked_production_entry: str | None = None,
	remarks: str | None = None,
) -> dict:
	"""Create a pending warehouse inbound record for commissary finished goods."""
	set_backend_observability_context(
		module="warehouse", action="create_warehouse_receiving", mutation_type="create"
	)
	_ensure_warehouse_receiving_doctype()

	if isinstance(items, str):
		items = json.loads(items)

	if not source_warehouse or not target_warehouse:
		frappe.throw(_("source_warehouse and target_warehouse are required"))
	if not items:
		frappe.throw(_("No items to hand off"))

	source_company = resolve_warehouse_company(source_warehouse)
	target_company = resolve_warehouse_company(target_warehouse)
	commissary_co = _get_commissary_company()
	if source_company != commissary_co:
		frappe.throw(_("Source warehouse must belong to {0}").format(commissary_co))
	allowed_target_companies = _get_allowed_target_companies()
	if target_company not in allowed_target_companies:
		frappe.throw(
			_("Target warehouse must belong to one of: {0}").format(", ".join(allowed_target_companies))
		)

	doc = frappe.new_doc("BEI Warehouse Receiving")
	doc.naming_series = "BEI-WHR-.YYYY.-.#####"
	doc.source_type = "Commissary Finished Goods"
	doc.source_warehouse = source_warehouse
	doc.target_warehouse = target_warehouse
	doc.dispatch_date = now_datetime()
	doc.linked_quality_inspection = linked_quality_inspection
	doc.linked_production_entry = linked_production_entry
	doc.created_by_user = frappe.session.user
	doc.remarks = remarks or f"FG handoff from {source_warehouse} to {target_warehouse}"

	for item_data in items:
		qty = flt(item_data.get("qty") or item_data.get("expected_qty"))
		if qty <= 0:
			continue
		item_doc = frappe.get_doc("Item", item_data["item_code"])
		valid_uom = _resolve_valid_item_uom(item_doc, item_data.get("uom"))

		# UX-010: Shelf life gate at warehouse receiving
		check_expiry_val = 0
		shelf_life_warning = None
		batch_no = item_data.get("batch_no")
		if batch_no:
			from frappe.utils import today as _today

			from hrms.api.commissary_dashboard import _validate_shelf_life_gate

			gate = _validate_shelf_life_gate(item_data["item_code"], batch_no, _today(), "receive")
			if not gate["valid"]:
				shelf_life_warning = gate["error"]
				check_expiry_val = 1

		doc.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": item_doc.item_name,
				"batch_no": batch_no,
				"uom": valid_uom,
				"expected_qty": qty,
				"received_qty": 0,
				"rejected_qty": 0,
				"accepted_qty": 0,
				"has_issue": 1 if shelf_life_warning else 0,
				"issue_notes": shelf_life_warning or item_data.get("issue_notes"),
				"check_expiry": check_expiry_val,
			},
		)

	if not doc.items:
		frappe.throw(_("No valid finished goods items to hand off"))

	doc.insert(ignore_permissions=True)

	# S093 (UX-011): Notify warehouse team of incoming handoff
	_notify_warehouse_handoff(doc.name, doc.source_warehouse, doc.target_warehouse)

	return {
		"success": True,
		"data": {
			"name": doc.name,
			"source_warehouse": doc.source_warehouse,
			"target_warehouse": doc.target_warehouse,
			"items_count": len(doc.items),
			"total_qty": sum(flt(item.expected_qty) for item in doc.items),
		},
		"message": f"Warehouse handoff {doc.name} created successfully",
	}


@frappe.whitelist()
def get_pending_warehouse_receivings(target_warehouse=None):
	"""Return pending commissary FG handoffs for warehouse receiving."""
	_ensure_warehouse_receiving_doctype()

	filters = {"status": "Pending Warehouse Receive"}
	if target_warehouse:
		filters["target_warehouse"] = target_warehouse

	docs = frappe.get_all(
		"BEI Warehouse Receiving",
		filters=filters,
		fields=[
			"name",
			"source_type",
			"source_warehouse",
			"target_warehouse",
			"dispatch_date",
			"status",
			"linked_quality_inspection",
			"linked_production_entry",
		],
		order_by="dispatch_date desc",
	)

	for row in docs:
		row["items_count"] = frappe.db.count("BEI Warehouse Receiving Item", {"parent": row["name"]})
		row["total_qty"] = sum(
			flt(item.expected_qty)
			for item in frappe.get_all(
				"BEI Warehouse Receiving Item",
				filters={"parent": row["name"]},
				fields=["expected_qty"],
			)
		)
		row["source_label"] = strip_company_suffix(row["source_warehouse"])
		row["target_label"] = strip_company_suffix(row["target_warehouse"])

	return {"success": True, "data": docs}


@frappe.whitelist()
def get_warehouse_receiving_detail(receiving_name):
	"""Return one pending or completed warehouse receiving record."""
	_ensure_warehouse_receiving_doctype()
	if not frappe.db.exists("BEI Warehouse Receiving", receiving_name):
		frappe.throw(_("Warehouse receiving record not found"))

	doc = frappe.get_doc("BEI Warehouse Receiving", receiving_name)
	return {
		"success": True,
		"data": {
			"name": doc.name,
			"source_type": doc.source_type,
			"source_warehouse": doc.source_warehouse,
			"target_warehouse": doc.target_warehouse,
			"dispatch_date": doc.dispatch_date,
			"receiving_date": doc.receiving_date,
			"status": doc.status,
			"linked_quality_inspection": doc.linked_quality_inspection,
			"linked_production_entry": doc.linked_production_entry,
			"stock_entry": doc.stock_entry,
			"remarks": doc.remarks,
			"items": _warehouse_receiving_item_rows(doc),
		},
	}


@frappe.whitelist()
def complete_warehouse_receiving(
	receiving_name: str, items: str | list[dict[str, Any]], remarks: str | None = None
) -> dict[str, Any]:
	"""Complete warehouse receipt for a commissary FG handoff by creating the stock transfer."""
	set_backend_observability_context(
		module="warehouse", action="complete_warehouse_receiving", mutation_type="update"
	)
	_ensure_warehouse_receiving_doctype()

	if isinstance(items, str):
		items = json.loads(items)

	check_scm_permission(SCM_RECEIVING_ROLES, "complete warehouse receiving")

	if not frappe.db.exists("BEI Warehouse Receiving", receiving_name):
		frappe.throw(_("Warehouse receiving record not found"))

	receiving = frappe.get_doc("BEI Warehouse Receiving", receiving_name)
	if receiving.status == "Completed" and receiving.stock_entry:
		return {
			"success": True,
			"data": {"name": receiving.stock_entry, "receiving_name": receiving.name},
			"message": f"Warehouse receiving {receiving.name} already completed",
		}

	# S203: capture the ORIGINAL dispatch SE before the block below overwrites
	# receiving.stock_entry with the new Material Transfer/Issue SE. The
	# dispatch SE carries the `custom_sales_invoice_draft` link we need to
	# submit on store acceptance.
	dispatch_se_name = receiving.stock_entry

	item_map = {item.item_code: item for item in receiving.items}
	accepted_items = []
	has_issues = False

	for item_data in items:
		item_code = item_data.get("item_code")
		row = item_map.get(item_code)
		if not row:
			continue
		received_qty = flt(item_data.get("received_qty", row.expected_qty))
		rejected_qty = flt(item_data.get("rejected_qty", 0))
		if rejected_qty > received_qty:
			frappe.throw(_("Rejected quantity cannot exceed received quantity for {0}").format(item_code))

		# B2: Over-receipt prevention — received_qty must not exceed expected_qty
		expected = flt(row.expected_qty)
		if expected > 0 and received_qty > expected:
			frappe.throw(
				_("Received quantity ({0}) exceeds expected quantity ({1}) for item {2}").format(
					received_qty, expected, item_code
				),
				title=_("Over-Receipt Not Allowed"),
			)
		row.received_qty = received_qty
		row.rejected_qty = rejected_qty
		row.accepted_qty = max(received_qty - rejected_qty, 0)
		row.issue_notes = item_data.get("issue_notes") or row.issue_notes
		row.has_issue = 1 if row.rejected_qty > 0 or row.issue_notes else 0
		has_issues = has_issues or bool(row.has_issue)
		if row.accepted_qty > 0:
			accepted_items.append(
				{
					"item_code": row.item_code,
					"qty": row.accepted_qty,
					"uom": row.uom,
					"batch_no": row.batch_no,
				}
			)

	if not accepted_items:
		if any(flt(item_data.get("rejected_qty", 0)) > 0 for item_data in items):
			# Full rejection — no stock entry needed, just update status
			receiving.receiving_date = now_datetime()
			receiving.received_by_user = frappe.session.user
			receiving.remarks = remarks or receiving.remarks
			receiving.status = "With Issues"
			receiving.save(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit — full rejection saves receiving doc outside normal stock entry flow
			return {
				"success": True,
				"data": {"receiving_name": receiving.name, "status": "fully_rejected"},
				"message": f"All items rejected for {receiving.name}",
			}
		frappe.throw(_("No accepted quantity to receive into warehouse"))

	source_co = resolve_warehouse_company(receiving.source_warehouse)
	target_co = resolve_warehouse_company(receiving.target_warehouse)
	finance_treatment = infer_finance_treatment(source_co, target_co)
	is_intercompany = finance_treatment == FINANCE_TREATMENT_INTERCOMPANY
	movement_type = "Material Issue" if is_intercompany else "Material Transfer"

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = movement_type
	stock_entry.company = source_co or target_co or get_company()
	stock_entry.posting_date = frappe.utils.today()
	stock_entry.posting_time = frappe.utils.nowtime()
	stock_entry.from_warehouse = receiving.source_warehouse
	if not is_intercompany:
		stock_entry.to_warehouse = receiving.target_warehouse
	stock_entry.remarks = remarks or f"Warehouse receiving {receiving.name}"
	stamp_stock_entry_contract(
		stock_entry,
		request_source=REQUEST_SOURCE_COMMISSARY_FG_TRANSFER,
		cargo_lane="FG",
		destination_warehouse=receiving.target_warehouse,
		source_company=source_co,
		target_company=target_co,
		finance_treatment=finance_treatment,
	)

	for item_data in accepted_items:
		item_doc = frappe.get_doc("Item", item_data["item_code"])
		valid_uom = _resolve_valid_item_uom(item_doc, item_data.get("uom"))

		row = {
			"item_code": item_data["item_code"],
			"item_name": item_doc.item_name,
			"description": item_doc.description,
			"qty": item_data["qty"],
			"uom": valid_uom,
			"stock_uom": valid_uom,
			"conversion_factor": 1,
			"s_warehouse": receiving.source_warehouse,
		}

		if is_intercompany:
			# Material Issue: explicit valuation, no target warehouse, no batch
			valuation_rate, allow_zero = _resolve_stock_entry_item_valuation(
				item_data["item_code"], receiving.source_warehouse
			)
			row["valuation_rate"] = valuation_rate
			if allow_zero:
				row["allow_zero_valuation_rate"] = 1
		else:
			# Material Transfer: set target warehouse only.
			# Do NOT set batch_no — ERPNext v15 handles batch via Serial and
			# Batch Bundle.  Setting the legacy field causes orphaned bundles
			# on retry ("… has already created" error).
			row["t_warehouse"] = receiving.target_warehouse

		stock_entry.append("items", row)

	_enable_role_gated_write(stock_entry)
	stock_entry.insert(ignore_permissions=True)
	stock_entry = frappe.get_doc("Stock Entry", stock_entry.name)
	_enable_role_gated_write(stock_entry)
	_clear_legacy_serial_batch_fields_after_auto_bundle(stock_entry)
	with _run_as_system_user("Administrator"):
		stock_entry.submit()

	receiving.stock_entry = stock_entry.name
	receiving.receiving_date = now_datetime()
	receiving.received_by_user = frappe.session.user
	receiving.remarks = remarks or receiving.remarks
	receiving.status = "With Issues" if has_issues else "Completed"
	receiving.save(ignore_permissions=True)

	# S203: submit the Draft SI created at dispatch time. This closes the gap
	# surfaced by the S198/S192 L3 runs — previously the WR path stamped stock
	# without ever submitting the SI, leaving BKI→store deliveries without
	# revenue recognition. The stock transfer above has already succeeded, so
	# any failure here MUST NOT roll back stock; we log and continue (mirrors
	# store.complete_receiving's outer guard).
	si_name = None
	try:
		si_name = _submit_dispatch_draft_si(dispatch_se_name, receiving.name)
	except Exception:
		frappe.log_error(
			f"S203: Outer guard tripped submitting Draft SI for receiving {receiving.name}: {frappe.get_traceback()}",
			"S203 Submit SI Guard",
		)

	result_data: dict[str, Any] = {
		"name": stock_entry.name,
		"receiving_name": receiving.name,
		"items_count": len(stock_entry.items),
		"total_qty": sum(flt(item.qty) for item in stock_entry.items),
	}
	if si_name:
		result_data["sales_invoice"] = si_name

	return {
		"success": True,
		"data": result_data,
		"message": f"Warehouse receiving {receiving.name} completed successfully",
	}


def _reconcile_si_qty_from_wr(si_doc, receiving_name: str) -> int:
	"""S212 DEFECT-2: reduce each SI item's qty to the accepted qty on the WR.

	The Draft Sales Invoice is created at DISPATCH time, billed against the
	dispatched qty on the Stock Entry. If the store accepts less than the
	dispatched qty (short-receive), the SI should bill only what was
	accepted — rejected items are a commissary write-off, not a store
	billable. This helper mutates si_doc.items in place before submit.

	Args:
	    si_doc: Sales Invoice document in docstatus=0, mutable.
	    receiving_name: BEI Warehouse Receiving docname whose accepted qtys
	        drive the reconciliation.

	Returns:
	    Number of SI lines adjusted (0 if full-receive or WR not found).
	"""
	if not receiving_name or not frappe.db.exists("BEI Warehouse Receiving", receiving_name):
		return 0
	wr_doc = frappe.get_doc("BEI Warehouse Receiving", receiving_name)
	accepted_by_item: dict[str, float] = {}
	for wr_row in wr_doc.items or []:
		code = wr_row.item_code
		if not code:
			continue
		accepted_by_item[code] = accepted_by_item.get(code, 0.0) + flt(wr_row.accepted_qty or 0)

	total_adjust = 0
	for si_row in si_doc.items or []:
		accepted = flt(accepted_by_item.get(si_row.item_code, si_row.qty))
		dispatched = flt(si_row.qty)
		if accepted < dispatched:
			si_row.qty = accepted
			si_row.amount = flt(si_row.qty) * flt(si_row.rate)
			total_adjust += 1
	if total_adjust:
		si_doc.run_method("calculate_taxes_and_totals")
		frappe.logger().info(
			f"S212 DEFECT-2: reconciled {total_adjust} SI lines for WR {wr_doc.name} "
			f"(SI {si_doc.name})"
		)
	return total_adjust


def _submit_dispatch_draft_si(dispatch_se_name: str | None, receiving_name: str) -> str | None:
	"""S203: Submit the Draft Sales Invoice that was created at dispatch time
	(by ``create_stock_transfer``'s Draft SI hook, itself introduced in S203
	to mirror the S168 pattern used by ``commissary.fulfill_store_order``).

	Looks up the Draft SI via ``Stock Entry.custom_sales_invoice_draft``
	on the dispatch SE, then submits it if still in Draft state.

	Returns the submitted SI name, or None if no Draft SI exists (e.g.,
	billing hold at fulfillment, same-company transfer, non-BKI source).
	Wrapped in a savepoint — SI failures never roll back stock posting.
	"""
	if not dispatch_se_name:
		return None
	if not frappe.db.exists("Stock Entry", dispatch_se_name):
		return None
	if not frappe.get_meta("Stock Entry").has_field("custom_sales_invoice_draft"):
		return None

	draft_si_name = frappe.db.get_value(
		"Stock Entry", dispatch_se_name, "custom_sales_invoice_draft"
	)
	if not draft_si_name or not frappe.db.exists("Sales Invoice", draft_si_name):
		return None

	si_doc = frappe.get_doc("Sales Invoice", draft_si_name)
	if si_doc.docstatus != 0:
		# Already submitted (idempotent re-run) or cancelled — return as-is.
		return si_doc.name if si_doc.docstatus == 1 else None

	# S204 BLOCK-1 fix: accept-delivery is triggered by store crew (Store
	# Supervisor / Warehouse User) who lack Sales Invoice write permission
	# under BEI's Custom DocPerm (only Accounts User/Manager have it). The
	# Draft SI was already created and validated at dispatch time by a
	# different session — this is a system completion step that promotes
	# docstatus 0 → 1. Switch to Administrator just for the submit, restore
	# session user afterwards.
	original_user = frappe.session.user
	try:
		frappe.db.savepoint("s203_submit_si")
		frappe.set_user("Administrator")
		# S212 DEFECT-2: reconcile SI item qty against WR accepted_qty BEFORE
		# submit. On short-receive (accepted < dispatched), drop each SI line
		# to the accepted qty and recompute taxes/totals. On full-receive
		# (accepted == dispatched), this is a no-op. Guards against billing
		# the store for items they rejected (surfaced by S209 V1 variance).
		_reconcile_si_qty_from_wr(si_doc, receiving_name)
		si_doc.submit()
		frappe.db.release_savepoint("s203_submit_si")
		return si_doc.name
	except Exception:
		try:
			frappe.db.rollback(save_point="s203_submit_si")
		except Exception:
			pass
		frappe.log_error(
			f"S203: Draft SI {draft_si_name} submit failed for receiving {receiving_name}: {frappe.get_traceback()}",
			"S203 Submit SI Error",
		)
		return None
	finally:
		frappe.set_user(original_user)


# ============================================================
# 2. MATERIAL REQUEST APPROVAL
# ============================================================


@frappe.whitelist()
def get_pending_material_requests():
	"""
	Get Material Requests pending approval/fulfillment.
	"""
	set_backend_observability_context(
		module="warehouse",
		action="get_pending_material_requests",
		mutation_type="read",
	)
	# S225 follow-up (Phase 6 Sentry): "Ordered" MRs (auto-promoted at creation
	# by the BEI on_submit hook for store-orders) were dropping out of this
	# warehouse-approval queue, leaving SCM with no way to confirm/dispatch via
	# the UI. Same root pattern as S226's order-approval queue fix. Include
	# "Ordered" so already-promoted MRs remain visible until they are dispatched
	# (i.e., until a Stock Entry consumes them and the status moves to
	# "Transferred"). The S224 Pattern B idempotency fix in approve_material_request
	# means a re-click on an Ordered MR is a no-op and won't throw.
	mrs = frappe.get_all(
		"Material Request",
		filters={
			"status": ["in", ["Pending", "Partially Ordered", "Ordered"]],
			"docstatus": 1,
			"material_request_type": ["in", ["Material Transfer", "Material Issue"]],
		},
		fields=[
			"name",
			"transaction_date",
			"schedule_date",
			"status",
			"set_warehouse",  # destination warehouse (store)
		],
		order_by="schedule_date asc",
		limit=50,
	)

	commissary_warehouse = None
	try:
		from hrms.api.commissary import get_commissary_warehouse

		commissary_warehouse = get_commissary_warehouse()
	except Exception:
		commissary_warehouse = None

	for mr in mrs:
		mr_doc = frappe.get_doc("Material Request", mr["name"])
		contract = resolve_material_request_contract(mr_doc, commissary_warehouse=commissary_warehouse)
		mr.update(contract)
		mr["store_name"] = contract["destination_label"] or strip_company_suffix(mr.set_warehouse)
		mr["request_source_label"] = get_request_source_label(contract["request_source"])

		# Get items summary
		items = frappe.get_all(
			"Material Request Item",
			filters={"parent": mr.name},
			fields=["item_code", "item_name", "qty", "ordered_qty", "uom"],
		)
		mr["items"] = items
		mr["items_count"] = len(items)
		mr["pending_items"] = sum(1 for i in items if i.qty > (i.ordered_qty or 0))

	return {"success": True, "data": mrs}


@frappe.whitelist()
def get_material_request_items(mr_name: str):
	"""
	Get detailed items for a Material Request with stock availability.
	"""
	if not frappe.db.exists("Material Request", mr_name):
		frappe.throw(_("Material Request not found"))

	mr = frappe.get_doc("Material Request", mr_name)
	commissary_warehouse = None
	try:
		from hrms.api.commissary import get_commissary_warehouse

		commissary_warehouse = get_commissary_warehouse()
	except Exception:
		commissary_warehouse = None
	contract = resolve_material_request_contract(mr, commissary_warehouse=commissary_warehouse)

	items = frappe.get_all(
		"Material Request Item",
		filters={"parent": mr_name},
		fields=["name", "item_code", "item_name", "description", "qty", "ordered_qty", "uom", "warehouse"],
	)

	for item in items:
		item["pending_qty"] = item["qty"] - (item["ordered_qty"] or 0)
		from_warehouse = (
			frappe.db.get_value("Material Request Item", item["name"], "from_warehouse")
			or contract["source_warehouse"]
		)
		# FIX-5 (S092): Resolve blank from_warehouse via commissary warehouse fallback
		if not from_warehouse:
			from_warehouse = commissary_warehouse
		item["from_warehouse"] = from_warehouse
		bin_qty = 0
		if from_warehouse:
			bin_qty = (
				frappe.db.get_value(
					"Bin", {"item_code": item["item_code"], "warehouse": from_warehouse}, "actual_qty"
				)
				or 0
			)
		else:
			# No warehouse resolved — sum across all warehouses as last resort
			result = frappe.db.sql(
				"SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s",
				item["item_code"],
			)
			bin_qty = flt(result[0][0]) if result and result[0][0] else 0
		item["available_qty"] = bin_qty
		item["source_warehouse_missing"] = not bool(from_warehouse)

	return {
		"success": True,
		"data": {
			"mr_name": mr.name,
			"store": contract["destination_warehouse"] or mr.set_warehouse,
			"store_name": contract["destination_label"],
			"transaction_date": mr.transaction_date,
			"schedule_date": mr.schedule_date,
			"request_source": contract["request_source"],
			"request_source_label": contract["request_source_label"],
			"cargo_lane": contract["cargo_lane"],
			"source_warehouse": contract["source_warehouse"],
			"finance_treatment": contract["finance_treatment"],
			"items": items,
		},
	}


@frappe.whitelist()
def approve_material_request(mr_name=None, approved_items=None):
	"""
	Approve Material Request with optional quantity adjustments.

	Args:
	    mr_name: Material Request name
	    approved_items: JSON array of {item_code, approved_qty}
	"""
	set_backend_observability_context(
		module="warehouse",
		action="approve_material_request",
		mutation_type="update",
		extras={"mr_name": mr_name},
	)
	check_scm_permission(SCM_APPROVAL_ROLES, "approve material requests")

	if not mr_name or not approved_items:
		frappe.throw(_("Missing required parameters: mr_name, approved_items"), frappe.ValidationError)
	if isinstance(approved_items, str):
		approved_items = json.loads(approved_items)

	if not frappe.db.exists("Material Request", mr_name):
		frappe.throw(_("Material Request not found"))

	# G-102: Row lock to prevent double-approval race condition.
	# S224 idempotency fix: if MR is already "Ordered" it was either auto-promoted at
	# creation time (BEI on_submit hook for store-order MRs) or approved in a parallel
	# request — either way, the caller's intent ("approve this MR") is already
	# satisfied. Return success-with-noop instead of throwing so the SCM UI does not
	# show a confusing error for an MR that is in the desired state.
	# Sentry evidence: during the S223 L3 sweep window, 5 of the 14 failed stores hit
	# this exact "already been approved" path because the MR auto-promotes at
	# _create_mr_for_store_order time. Throwing here was a Pattern B root cause.
	current_status = frappe.db.sql(
		"SELECT status FROM `tabMaterial Request` WHERE name = %s FOR UPDATE", mr_name
	)[0][0]
	if current_status == "Ordered":
		return {
			"success": True,
			"message": f"Material Request {mr_name} already approved (status=Ordered) — no-op",
			"already_approved": True,
		}

	# Store approval info as comment
	approval_summary = []
	for item in approved_items:
		approval_summary.append(f"{item['item_code']}: {item.get('approved_qty', 0)}")

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Material Request",
			"reference_name": mr_name,
			"content": f"Approved by {frappe.session.user}. Quantities: " + ", ".join(approval_summary),
		}
	).insert(ignore_permissions=True)

	# P0-3 fix: Actually update MR status (previously only added comment)
	frappe.db.set_value("Material Request", mr_name, {"status": "Ordered", "per_ordered": 100})

	return {"success": True, "message": f"Material Request {mr_name} approved"}


@frappe.whitelist()
def reject_material_request(mr_name=None, reason=None):
	"""
	Reject/cancel a Material Request.
	"""
	check_scm_permission(SCM_APPROVAL_ROLES, "reject material requests")

	if not mr_name or not reason:
		frappe.throw(_("Missing required parameters: mr_name, reason"), frappe.ValidationError)
	if not frappe.db.exists("Material Request", mr_name):
		frappe.throw(_("Material Request not found"))

	mr = frappe.get_doc("Material Request", mr_name)

	# Add rejection comment
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Material Request",
			"reference_name": mr_name,
			"content": f"Rejected by {frappe.session.user}. Reason: {reason}",
		}
	).insert(ignore_permissions=True)

	# Cancel the MR
	mr.cancel()

	return {"success": True, "message": f"Material Request {mr_name} rejected"}


# ============================================================
# 3. DISPATCH / STOCK TRANSFER
# ============================================================


@frappe.whitelist()
def get_ready_for_dispatch():
	"""
	Get approved Material Requests ready for dispatch.
	Groups by destination store for trip planning.
	"""
	set_backend_observability_context(
		module="warehouse",
		action="get_ready_for_dispatch",
		route_action="get_ready_for_dispatch",
		mutation_type="load",
		endpoint_or_job="hrms.api.warehouse.get_ready_for_dispatch",
		phase="load",
	)
	mrs = frappe.get_all(
		"Material Request",
		filters={
			"status": ["in", ["Ordered", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": ["in", ["Material Transfer", "Material Issue"]],
		},
		fields=["name", "transaction_date", "schedule_date", "status", "set_warehouse"],
		order_by="schedule_date asc",
	)

	commissary_warehouse = None
	try:
		from hrms.api.commissary import get_commissary_warehouse

		commissary_warehouse = get_commissary_warehouse()
	except Exception:
		commissary_warehouse = None

	# Group by destination warehouse
	by_store = {}
	for mr in mrs:
		mr_doc = frappe.get_doc("Material Request", mr["name"])
		contract = resolve_material_request_contract(mr_doc, commissary_warehouse=commissary_warehouse)
		store = contract["destination_warehouse"] or mr.set_warehouse or "Unknown"
		if store not in by_store:
			by_store[store] = {
				"store": store,
				"store_name": contract["destination_label"] or strip_company_suffix(store),
				"requests": [],
				"total_items": 0,
			}

		items = frappe.get_all(
			"Material Request Item",
			filters={"parent": mr.name},
			fields=["item_code", "item_name", "qty", "uom", "from_warehouse"],
		)
		mr["items"] = items
		mr["items_count"] = len(items)
		mr.update(contract)
		mr["store_name"] = contract["destination_label"] or strip_company_suffix(store)

		by_store[store]["requests"].append(mr)
		by_store[store]["total_items"] += len(items)

	return {"success": True, "data": list(by_store.values())}


def _create_warehouse_receiving_for_se(se, contract: dict) -> str | None:
	"""S198: auto-create BEI Warehouse Receiving after SE submit on BKI dispatch.

	This is a fire-and-forget helper that MUST NOT raise. If WR creation fails,
	the SE is already submitted; throwing here would be a half-state.

	Args:
		se: The just-submitted Stock Entry doc
		contract: The material request contract dict (contains destination_warehouse, etc.)

	Returns:
		The WR docname if created/found, or None on failure/skip.
	"""
	try:
		# D-1: BKI scope guard — only auto-create WR for BKI-source dispatches
		source_company = resolve_warehouse_company(se.from_warehouse)
		if source_company != _get_commissary_company():
			return None

		destination_warehouse = contract.get("destination_warehouse") or getattr(se, "to_warehouse", None)
		if not destination_warehouse:
			return None

		# P1-T4: Idempotency safeguard — if a WR already exists for this SE, return it
		existing = frappe.db.get_value(
			"BEI Warehouse Receiving",
			{"stock_entry": se.name, "status": ("!=", "Cancelled")},
			"name",
		)
		if existing:
			return existing

		# Build items payload from SE items
		items_payload = []
		for item in se.items:
			items_payload.append({
				"item_code": item.item_code,
				"qty": item.qty,
				"uom": getattr(item, "uom", None) or getattr(item, "stock_uom", "Nos"),
			})

		if not items_payload:
			return None

		# Call create_warehouse_receiving (the existing @frappe.whitelist endpoint)
		result = create_warehouse_receiving(
			source_warehouse=se.from_warehouse,
			target_warehouse=destination_warehouse,
			items=json.dumps(items_payload),
			remarks=f"Auto-created from Stock Entry {se.name}",
		)

		wr_name = result.get("data", {}).get("name") if isinstance(result, dict) else None
		if not wr_name:
			return None

		# D-11: Stamp stock_entry on the WR using frappe.db.set_value (read_only field)
		frappe.db.set_value("BEI Warehouse Receiving", wr_name, "stock_entry", se.name)

		# P3-T2: Dispatch notification via GChat (reuse existing pattern)
		try:
			_notify_warehouse_handoff(wr_name, se.from_warehouse, destination_warehouse)
		except Exception:
			pass  # notification failure must not affect WR creation

		return wr_name

	except Exception as e:
		# MUST NOT raise — log and return None so SE submission is preserved
		frappe.log_error(
			f"S198: Auto-create WR failed for SE {getattr(se, 'name', '?')}: {e}",
			"Warehouse API",
		)
		return None


@frappe.whitelist()
def create_stock_transfer(
	source_warehouse: str,
	target_warehouse: str,
	items: str | list[dict[str, Any]],
	mr_name: str | None = None,
	remarks: str | None = None,
):
	"""
	Create Stock Entry (Material Transfer) for dispatch.

	Args:
	    source_warehouse: From warehouse (e.g., "Shaw BLVD - BKI")
	    target_warehouse: To warehouse (e.g., "SM-CALOOCAN - BEI")
	    items: JSON array of {item_code, qty, uom, batch_no (optional), mr_item_name (optional)}
	    mr_name: Optional Material Request reference
	    remarks: Optional notes

	Returns:
	    Stock Entry name
	"""
	if isinstance(items, str):
		items = json.loads(items)

	set_backend_observability_context(
		module="warehouse",
		action="create_stock_transfer",
		route_action="create_stock_transfer",
		mutation_type="create",
		endpoint_or_job="hrms.api.warehouse.create_stock_transfer",
		phase="mutation",
		extras={
			"source_warehouse": source_warehouse,
			"target_warehouse": target_warehouse,
			"mr_name": mr_name,
			"item_count": len(items) if isinstance(items, list) else None,
		},
	)
	check_scm_permission(SCM_DISPATCH_ROLES, "dispatch warehouse stock transfers")

	if not source_warehouse:
		frappe.throw(
			_(
				"Cannot create stock transfer: source warehouse is not set. "
				"Please specify a source warehouse or ensure the Material Request has one assigned."
			),
			title=_("Source Warehouse Required"),
		)

	# Resolve partial/short warehouse names to full Frappe names (e.g. "3MD Warehouse" →
	# "3MD Logistics - Camangyanan - Bebang Enterprise Inc.").  Frappe Link fields require
	# exact name matches; short names cause LinkValidationError.
	source_warehouse = _resolve_warehouse_name(source_warehouse)
	target_warehouse = _resolve_warehouse_name(target_warehouse)

	default_source_company = resolve_warehouse_company(source_warehouse) or get_company()
	default_target_company = resolve_warehouse_company(target_warehouse) or default_source_company

	# AUDIT CONTROL: Require approved Material Request before dispatch
	if not mr_name:
		frappe.throw(
			_(
				"Cannot create stock transfer without an approved Material Request. "
				"Please provide mr_name parameter."
			),
			title=_("Material Request Required"),
		)

	# Load and validate MR
	mr_items_map = {}
	contract = {
		"request_source": REQUEST_SOURCE_STORE_ORDER,
		"cargo_lane": None,
		"source_company": default_source_company,
		"target_company": default_target_company,
		"finance_treatment": infer_finance_treatment(default_source_company, default_target_company),
	}
	try:
		mr = frappe.get_doc("Material Request", mr_name)
		# Only allow dispatch for MRs that have been approved/ordered
		if mr.status not in ("Ordered", "Partially Ordered", "Transferred"):
			frappe.throw(
				_("Material Request {0} has status '{1}'. Only approved MRs can be dispatched.").format(
					mr_name, mr.status
				),
				title=_("Invalid Material Request Status"),
			)
		contract.update(resolve_material_request_contract(mr))
		for mr_item in mr.items:
			mr_items_map[mr_item.item_code] = mr_item.name
	except frappe.DoesNotExistError:
		frappe.throw(
			_("Material Request {0} not found.").format(mr_name), title=_("Material Request Not Found")
		)

	# Create Stock Entry
	actual_target_warehouse = contract.get("destination_warehouse") or target_warehouse
	actual_target_company = (
		contract.get("target_company")
		or resolve_warehouse_company(actual_target_warehouse)
		or default_target_company
	)
	finance_treatment = contract.get("finance_treatment") or infer_finance_treatment(
		contract.get("source_company") or default_source_company,
		actual_target_company,
	)
	is_intercompany = finance_treatment == FINANCE_TREATMENT_INTERCOMPANY
	movement_type = "Material Issue" if is_intercompany else "Material Transfer"

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = movement_type
	se.company = contract.get("source_company") or default_source_company
	se.posting_date = frappe.utils.today()
	se.posting_time = frappe.utils.nowtime()
	se.from_warehouse = source_warehouse
	if not is_intercompany:
		se.to_warehouse = actual_target_warehouse
	se.remarks = remarks or (f"{movement_type} for {strip_company_suffix(actual_target_warehouse)}")
	stamp_stock_entry_contract(
		se,
		request_source=contract["request_source"],
		cargo_lane=contract.get("cargo_lane"),
		destination_warehouse=actual_target_warehouse,
		source_company=contract.get("source_company") or default_source_company,
		target_company=actual_target_company,
		finance_treatment=finance_treatment,
	)

	# Add items
	normalized_items = []
	for item_data in items:
		qty_value = item_data.get("qty", item_data.get("quantity"))
		if qty_value is None:
			frappe.throw(_("Missing quantity for item {0}").format(item_data.get("item_code", "unknown")))
		item_data["qty"] = flt(qty_value)
		normalized_items.append(item_data)

	# S225: serialize concurrent batch decrements per item+warehouse pair.
	# Sentry confirmed Pattern A is a race condition where parallel
	# create_stock_transfer calls read Bin.actual_qty, both decide there's stock,
	# and both submit -- pushing the batch briefly negative.
	# FOR UPDATE locks the rows for the duration of this transaction; released
	# on COMMIT/ROLLBACK by Frappe's auto-transactional handler. Sorted item_codes
	# ensure deterministic lock acquisition order across concurrent transactions
	# (prevents deadlocks where T1 locks ItemA->ItemB and T2 locks ItemB->ItemA).
	_lock_item_codes = sorted({i.get("item_code") for i in normalized_items if i.get("item_code")})
	if _lock_item_codes:
		import time as _time
		_lock_t0 = _time.time()
		frappe.db.sql(
			"""SELECT name FROM `tabBin`
			   WHERE warehouse = %s AND item_code IN %s
			   FOR UPDATE""",
			(source_warehouse, tuple(_lock_item_codes)),
		)

		# AUDIT W-1: for batch-tracked items, also lock the Batch rows.
		# The Bin lock alone doesn't cover the Serial and Batch Bundle (SABB)
		# allocation path that runs inside se.submit(). Two parallel dispatches
		# could pass the Bin check (Bin lock works) but still race on batch-level
		# allocation.
		_batch_tracked_items = [
			ic for ic in _lock_item_codes
			if frappe.db.get_value("Item", ic, "has_batch_no") == 1
		]
		if _batch_tracked_items:
			# Lock all batches that have non-zero stock at this warehouse for these
			# items. Held until COMMIT, serializing batch allocation across concurrent
			# create_stock_transfer calls.
			frappe.db.sql(
				"""SELECT b.name FROM `tabBatch` b
				   JOIN `tabStock Ledger Entry` sle ON sle.batch_no = b.name
				   WHERE sle.warehouse = %s
				     AND sle.item_code IN %s
				     AND sle.is_cancelled = 0
				   GROUP BY b.name
				   FOR UPDATE""",
				(source_warehouse, tuple(_batch_tracked_items)),
			)

		# Lock-wait telemetry: surface contention into Sentry breadcrumbs when the
		# acquisition takes >2s. frappe.log_error feeds Sentry via the BEI
		# monkey-patch (DM-7). This is best-effort instrumentation, not
		# functional logic.
		_lock_wait_ms = int((_time.time() - _lock_t0) * 1000)
		if _lock_wait_ms > 2000:
			try:
				frappe.log_error(
					f"S225 lock wait {_lock_wait_ms}ms for {source_warehouse}/{_lock_item_codes}",
					"S225 Lock Contention",
				)
			except (RuntimeError, Exception):
				# frappe.log_error can throw "object is not bound" when called from a
				# non-request context (e.g., worker thread, scheduled job). The
				# lock-wait info is best-effort — drop silently rather than break the
				# dispatch.
				pass

	for item_data in normalized_items:
		# Get item details
		item = frappe.get_doc("Item", item_data["item_code"])
		valid_uom = _resolve_valid_item_uom(item, item_data.get("uom"))
		valuation_rate, allow_zero_valuation_rate = _resolve_stock_entry_item_valuation(
			item_data["item_code"], source_warehouse
		)

		# ERPNext v15 uses Serial and Batch Bundle for all batch tracking.
		# Passing legacy `batch_no` on the item row causes ERPNext to auto-create
		# a bundle during insert.  If the transaction then fails (validation,
		# timeout, retry) the orphaned bundle blocks all subsequent attempts with
		# "Serial and Batch Bundle … has already created".
		# Fix: never set batch_no — let ERPNext handle batch selection via its
		# own bundle mechanism during insert/submit.
		batch_no = None

		# Bug fix B9-001: Set material_request and material_request_item properly
		mr_item_ref = item_data.get("mr_item_name")
		if not mr_item_ref and mr_name:
			mr_item_ref = mr_items_map.get(item_data["item_code"])

		row = {
			"item_code": item_data["item_code"],
			"item_name": item.item_name,
			"description": item.description,
			"qty": item_data["qty"],
			"uom": valid_uom,
			"stock_uom": valid_uom,
			"conversion_factor": 1,
			"s_warehouse": source_warehouse,
			"material_request": mr_name if mr_item_ref else None,
			"material_request_item": mr_item_ref,
		}
		if is_intercompany:
			row["valuation_rate"] = valuation_rate
			if allow_zero_valuation_rate:
				row["allow_zero_valuation_rate"] = 1
		if batch_no:
			row["batch_no"] = batch_no
		if not is_intercompany:
			row["t_warehouse"] = actual_target_warehouse
		se.append("items", row)

	if not se.items:
		frappe.throw(_("No items to transfer"))

	_enable_role_gated_write(se)
	wr_name = None  # S198: will hold auto-created WR docname
	try:
		se.insert(ignore_permissions=True)
		se = frappe.get_doc("Stock Entry", se.name)
		_enable_role_gated_write(se)
		_clear_legacy_serial_batch_fields_after_auto_bundle(se)
		with _run_as_system_user("Administrator"):
			se.submit()

		# S198: auto-create BEI Warehouse Receiving so the destination store's
		# crew has an acknowledgment doc the moment dispatch packs the truck.
		# S204: wrap in Administrator context — the SCM dispatcher who
		# triggers `create_stock_transfer` typically lacks BEI Warehouse
		# Receiving write permission, so the inner `frappe.new_doc`+insert
		# (via `create_warehouse_receiving`) would silently fail and leave
		# the destination store with no receiving acknowledgment.
		with _run_as_system_user("Administrator"):
			wr_name = _create_warehouse_receiving_for_se(se, contract)

		# S203: create a Draft Sales Invoice at dispatch time for every BKI
		# intercompany transfer (mirrors the S168 pattern from
		# commissary.fulfill_store_order). The SI stays Draft until
		# complete_warehouse_receiving submits it on store acceptance.
		# Failure here is logged but never raised — billing errors must not
		# block stock dispatch.
		if mr_name and finance_treatment == FINANCE_TREATMENT_INTERCOMPANY:
			try:
				frappe.db.savepoint("s203_draft_si_create")
				from hrms.api.commissary import build_bki_store_sale_invoice

				store_order_name = frappe.db.get_value(
					"Material Request", mr_name, "custom_store_order"
				)
				draft_si_name = build_bki_store_sale_invoice(
					stock_entry=se,
					store_order_name=store_order_name,
				)
				if draft_si_name and frappe.get_meta("Stock Entry").has_field(
					"custom_sales_invoice_draft"
				):
					frappe.db.set_value(
						"Stock Entry",
						se.name,
						"custom_sales_invoice_draft",
						draft_si_name,
					)
				frappe.db.release_savepoint("s203_draft_si_create")
			except Exception:
				try:
					frappe.db.rollback(save_point="s203_draft_si_create")
				except Exception:
					pass
				frappe.log_error(
					f"S203: Draft SI creation failed for SE {se.name}: {frappe.get_traceback()}",
					"S203 Draft SI Error",
				)
				# DO NOT raise — dispatch must not block on billing errors.
	except frappe.ValidationError as e:
		import re

		raw_msg = str(e)
		# Strip HTML from Frappe validation messages for clean API response
		plain_msg = re.sub(r"<[^>]+>", "", raw_msg).strip()
		plain_msg = re.sub(r"\s+", " ", plain_msg)
		# Detect insufficient stock pattern
		stock_match = re.search(
			r"(\d+(?:\.\d+)?)\s*units?\s+of\s+(?:Item\s+\w+:\s*)?(.+?)\s+needed\s+in\s+(?:Warehouse\s+)?(.+?)\s+to\s+complete",
			plain_msg,
			re.IGNORECASE,
		)
		if stock_match:
			qty, item_name, wh = stock_match.group(1), stock_match.group(2).strip(), stock_match.group(3).strip()
			short_wh = re.sub(r"\s*-\s*(Bebang Enterprise Inc\.|BKI)\s*$", "", wh).strip()
			frappe.throw(
				_(
					"Not enough stock: {0} needs {1} units in {2}, but there isn't enough. "
					"Please check stock levels or do a stock receipt first."
				).format(item_name, qty, short_wh),
				title=_("Insufficient Stock"),
			)
		# Re-raise with HTML stripped
		frappe.throw(_(plain_msg), title=_("Transfer Failed"))

	return {
		"success": True,
		"data": {
			"name": se.name,
			"total_qty": sum(i.qty for i in se.items),
			"items_count": len(se.items),
			"movement_type": movement_type,
			"source_warehouse": source_warehouse,
			"target_warehouse": actual_target_warehouse,
			"request_source": contract["request_source"],
			"request_source_label": get_request_source_label(contract["request_source"]),
			"cargo_lane": contract.get("cargo_lane"),
			"finance_treatment": finance_treatment,
			"warehouse_receiving": wr_name,  # S198: auto-created WR docname (or None)
		},
		"message": f"{movement_type} {se.name} created successfully",
	}


@frappe.whitelist()
def get_dispatch_trips_today():
	"""
	Get today's dispatch trips for tracking.
	"""
	today = frappe.utils.today()

	# Check if BEI Distribution Trip DocType exists
	if not frappe.db.exists("DocType", "BEI Distribution Trip"):
		return {"success": True, "data": [], "message": "Trip tracking not configured"}

	trips = frappe.get_all(
		"BEI Distribution Trip",
		filters={"trip_date": today},
		fields=[
			"name",
			"trip_date",
			"route_name",
			"driver",
			"vehicle",
			"vehicle_plate",
			"departure_time",
			"status",
		],
		order_by="creation desc",
	)

	for trip in trips:
		# Get stops summary if child table exists
		if frappe.db.exists("DocType", "BEI Trip Stop"):
			stops = frappe.get_all(
				"BEI Trip Stop",
				filters={"parent": trip.name},
				fields=["store", "stop_order", "items_count", "status"],
			)
			trip["stops"] = stops
			trip["stops_count"] = len(stops)
			trip["completed_stops"] = sum(1 for s in stops if s.get("status") == "Delivered")
		else:
			trip["stops"] = []
			trip["stops_count"] = 0
			trip["completed_stops"] = 0

	return {"success": True, "data": trips}


# ============================================================
# 4. DASHBOARD / SUMMARY
# ============================================================


@frappe.whitelist()
def get_warehouse_dashboard():
	"""
	Get warehouse supervisor dashboard summary.
	"""
	today = frappe.utils.today()

	# Pending Purchase Receipts
	pending_pos = frappe.db.count(
		"Purchase Order", filters={"status": ["in", ["To Receive and Bill", "To Receive"]], "docstatus": 1}
	)

	# Pending Material Requests
	pending_mrs = frappe.db.count(
		"Material Request",
		filters={
			"status": ["in", ["Pending", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": ["in", ["Material Transfer", "Material Issue"]],
		},
	)

	# Today's trips (if DocType exists)
	todays_trips = 0
	if frappe.db.exists("DocType", "BEI Distribution Trip"):
		todays_trips = frappe.db.count("BEI Distribution Trip", filters={"trip_date": today})

	# Recent activity - Purchase Receipts
	recent_receipts = frappe.get_all(
		"Purchase Receipt",
		filters={"posting_date": [">=", frappe.utils.add_days(today, -7)]},
		fields=["name", "posting_date", "supplier_name", "grand_total"],
		order_by="posting_date desc",
		limit=5,
	)

	# Recent activity - Stock Transfers
	recent_transfers = frappe.get_all(
		"Stock Entry",
		filters={
			"posting_date": [">=", frappe.utils.add_days(today, -7)],
			"stock_entry_type": "Material Transfer",
		},
		fields=["name", "posting_date", "to_warehouse", "total_outgoing_value"],
		order_by="posting_date desc",
		limit=5,
	)

	return {
		"success": True,
		"data": {
			"pending_pos": pending_pos,
			"pending_mrs": pending_mrs,
			"todays_trips": todays_trips,
			"recent_receipts": recent_receipts,
			"recent_transfers": recent_transfers,
		},
	}
