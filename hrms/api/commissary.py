# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Supervisor APIs — Core Module
Inventory monitoring, store order fulfillment, dispatch, shifts, productivity, and hub management.

Dashboard/production, quality/QC, requisitions/work orders, and BOM functions have been
split into dedicated modules (P0-11). This file re-exports them for backwards compatibility.

Modules:
    commissary_dashboard.py — Dashboard summary + production tracking
    commissary_quality.py   — Quality inspection, QC forms, wastage, FEFO/batch
    commissary_requisition.py — RM reorder/requisitions, production planning/work orders
    commissary_bom.py       — BOM CRUD + production feasibility
"""

import json
from contextlib import contextmanager
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from hrms.api.store import _get_store_customer
from hrms.utils.bei_config import get_company
from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supply_chain_contracts import (
	CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
	buyer_entity_requires_billing_hold,
	get_preferred_commissary_warehouses,
	load_store_buyer_entity_register,
	resolve_store_buyer_entity,
	resolve_warehouse_company,
)

# ============================================================
# SHARED UTILITY (must be defined BEFORE sub-module re-exports
# to avoid circular import — sub-modules import this function)
# ============================================================


@contextmanager
def _run_as_system_user(user: str = "Administrator"):
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


def _clear_legacy_serial_batch_fields_after_auto_bundle(stock_entry):
	for item in getattr(stock_entry, "items", None) or []:
		if not getattr(item, "serial_and_batch_bundle", None):
			continue
		if getattr(item, "batch_no", None):
			item.batch_no = None
		if getattr(item, "serial_no", None):
			item.serial_no = None


def get_commissary_warehouse():
	"""Resolve the operational commissary warehouse, preferring the BKI custody model."""

	def _stocked_candidate(include_legacy: bool) -> str | None:
		for warehouse_name in get_preferred_commissary_warehouses(include_legacy=include_legacy):
			if not frappe.db.exists("Warehouse", warehouse_name):
				continue
			stocked = frappe.db.sql(
				"""
				SELECT COUNT(*)
				FROM `tabBin`
				WHERE warehouse = %s
				  AND actual_qty > 0
				""",
				warehouse_name,
			)[0][0]
			if stocked:
				return warehouse_name
		return None

	def _existing_candidate(include_legacy: bool) -> str | None:
		for warehouse_name in get_preferred_commissary_warehouses(include_legacy=include_legacy):
			if frappe.db.exists("Warehouse", warehouse_name):
				return warehouse_name
		return None

	return (
		_stocked_candidate(include_legacy=False)
		or _existing_candidate(include_legacy=False)
		or _stocked_candidate(include_legacy=True)
		or _existing_candidate(include_legacy=True)
		or CANONICAL_COMMISSARY_OPERATION_WAREHOUSE
	)


def get_commissary_company() -> str:
	"""Resolve the legal entity that owns the active commissary warehouse."""
	return resolve_warehouse_company(get_commissary_warehouse()) or get_company()


def _raise_direct_fulfillment_retired() -> None:
	frappe.throw(
		_(
			"Commissary direct store fulfillment is retired. "
			"Use the warehouse-centered flow: raw materials -> production -> QA -> warehouse handoff."
		)
	)


@frappe.whitelist()
def get_production_cost_per_batch(limit=20, item_code=None):
	"""
	Compatibility wrapper for dashboard production costing endpoint.
	"""
	set_backend_observability_context(
		module="commissary", action="get_production_cost_per_batch", mutation_type="read"
	)
	from hrms.api.commissary_dashboard import get_production_cost_per_batch as _dashboard_costing

	return _dashboard_costing(limit=limit, item_code=item_code)


@frappe.whitelist()
def get_logistics_architecture_mode(route_name=None):
	"""
	Compatibility wrapper for logistics architecture mode endpoint.
	"""
	set_backend_observability_context(
		module="commissary", action="get_logistics_architecture_mode", mutation_type="read"
	)
	from hrms.api.commissary_dashboard import (
		get_logistics_architecture_mode as _dashboard_logistics_architecture_mode,
	)

	return _dashboard_logistics_architecture_mode(route_name=route_name)


OUTSOURCED_CODE_PREFIXES = ("OUT-", "OS-", "3P-", "OUTSOURCED")


def resolve_outsourced_item_flag(item_code=None, item_name=None, item_meta=None):
	"""
	Classify if a production item is outsourced.

	Deterministic order:
	1) Explicit metadata flags
	2) Supplier metadata
	3) Item code/name conventions
	"""
	item_meta = item_meta or {}

	explicit_flag = item_meta.get("is_outsourced_item")
	if explicit_flag in (1, "1", True, "true", "True", "YES", "yes"):
		return {"is_outsourced_item": True, "reason": "meta:is_outsourced_item"}

	supplier = item_meta.get("outsourced_supplier") or item_meta.get("default_supplier")
	if supplier:
		return {"is_outsourced_item": True, "reason": f"meta:supplier:{supplier}"}

	code_name = f"{item_code or ''} {item_name or ''}".upper().strip()
	for prefix in OUTSOURCED_CODE_PREFIXES:
		if code_name.startswith(prefix):
			return {"is_outsourced_item": True, "reason": f"prefix:{prefix.rstrip('-')}"}

	return {"is_outsourced_item": False, "reason": "none"}


@frappe.whitelist()
def get_outsourced_item_flag(item_code, item_name=None):
	"""
	Public API for UI/audit checks.
	"""
	set_backend_observability_context(
		module="commissary", action="get_outsourced_item_flag", mutation_type="read"
	)
	return {"success": True, "data": resolve_outsourced_item_flag(item_code=item_code, item_name=item_name)}


# ============================================================
# P0-11: Re-exports for backwards compatibility
# Frontend calls hrms.api.commissary.<fn> — these imports ensure
# existing API paths continue to work after the split.
# ============================================================

# Dashboard & Production (commissary_dashboard.py)
# BOM & Feasibility (commissary_bom.py)
from hrms.api.commissary_bom import (
	check_production_feasibility,
	create_bom,
	get_bom_detail,
	update_bom,
)
from hrms.api.commissary_dashboard import (
	get_commissary_dashboard,
	get_or_create_batch,
	get_production_history,
	get_production_items,
	submit_production_batch,
	submit_production_output,
)

# Quality, Wastage, FEFO, QC Forms (commissary_quality.py)
from hrms.api.commissary_quality import (
	create_quality_inspection,
	enable_batch_tracking_for_fg,
	get_expiring_batches,
	get_fefo_picking_list,
	get_inspection_details,
	get_inspection_history,
	get_pending_inspections,
	get_qc_form_detail,
	get_qc_form_templates,
	get_qc_forms,
	get_wastage_history,
	get_wastage_reasons,
	get_wastage_trends,
	log_wastage,
	submit_qc_form,
)

# RM Requisitions & Production Planning (commissary_requisition.py)
from hrms.api.commissary_requisition import (
	approve_requisition,
	complete_work_order,
	create_rm_requisition,
	create_work_order,
	get_my_requisitions,
	get_production_suggestions,
	get_rm_for_requisition,
	get_rm_reorder_alerts,
	get_work_orders,
	start_work_order,
)

# ============================================================
# 3. INVENTORY MONITORING
# ============================================================


@frappe.whitelist()
def get_inventory_levels(item_group=None, show_low_stock_only=False):
	"""
	Get current inventory levels at commissary.
	Uses per-product thresholds instead of hardcoded values.
	"""
	set_backend_observability_context(
		module="commissary", action="get_inventory_levels", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	conditions = "WHERE b.warehouse = %s AND i.disabled = 0 AND i.is_stock_item = 1"
	params = [commissary_warehouse]

	if item_group:
		conditions += " AND i.item_group = %s"
		params.append(item_group)

	# Get all items first, then apply product-specific thresholds
	items = frappe.db.sql(
		f"""
        SELECT  -- nosemgrep: frappe-sql-format-injection
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty,
            i.valuation_rate
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        {conditions}
        ORDER BY i.item_name
    """,
		params,
		as_dict=True,
	)

	result = []
	for item in items:
		# Get product-specific thresholds
		threshold = get_product_threshold(item["item_code"])
		# Use target_di as a proxy for reorder level (days of stock = quantity threshold for now)
		# For a proper calculation, we'd need avg daily consumption
		safety_stock = threshold["target_di"] // 2  # Half of target DI
		reorder_level = threshold["target_di"]

		# Determine stock status
		qty = flt(item["current_qty"])
		if qty <= 0:
			stock_status = "Out of Stock"
		elif qty < safety_stock:
			stock_status = "Low Stock"
		elif qty < reorder_level:
			stock_status = "Reorder"
		else:
			stock_status = "OK"

		# Skip if filtering for low stock only
		if (show_low_stock_only == "1" or show_low_stock_only is True) and stock_status == "OK":
			continue

		item["safety_stock"] = safety_stock
		item["reorder_level"] = reorder_level
		item["stock_status"] = stock_status
		item["value"] = qty * flt(item["valuation_rate"] or 0)
		item["shelf_life"] = threshold["shelf_life"]
		item["storage_temp"] = threshold["storage_temp"]

		# UX-008: Add batch info for items with batch tracking
		item["batches"] = frappe.db.get_all(
			"Batch",
			filters={"item": item["item_code"], "disabled": 0},
			fields=["name", "batch_id", "manufacturing_date", "expiry_date"],
			order_by="expiry_date asc",
			limit_page_length=10,
		)

		result.append(item)

	# Sort by status priority
	status_order = {"Out of Stock": 0, "Low Stock": 1, "Reorder": 2, "OK": 3}
	result.sort(key=lambda x: (status_order.get(x["stock_status"], 99), x["item_name"]))

	return {"success": True, "data": result}


@frappe.whitelist()
def get_transfer_ready_inventory():
	"""
	Fast finished-goods inventory feed for the commissary -> warehouse handoff page.

	This intentionally avoids the threshold enrichment loop used by the broader
	commissary inventory dashboard because the transfer page only needs current FG
	stock with positive quantity in the active commissary warehouse.
	"""
	set_backend_observability_context(
		module="commissary", action="get_transfer_ready_inventory", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	items = frappe.db.sql(
		"""
		SELECT
			b.item_code,
			i.item_name,
			i.item_group,
			b.actual_qty,
			0 as reserved_qty,
			b.actual_qty as available_qty,
			i.stock_uom,
			b.warehouse
		FROM `tabBin` b
		JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.warehouse = %s
		  AND b.actual_qty > 0
		  AND i.disabled = 0
		  AND i.is_stock_item = 1
		  AND (
			i.name LIKE 'FG%%'
			OR i.item_group = 'Finished Goods'
		  )
		ORDER BY i.item_name
		""",
		commissary_warehouse,
		as_dict=True,
	)

	return {"success": True, "data": items}


@frappe.whitelist()
def get_low_stock_alerts():
	"""
	Get items below safety stock or reorder level.
	Uses per-product thresholds instead of hardcoded values.
	"""
	set_backend_observability_context(
		module="commissary", action="get_low_stock_alerts", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	# Get all items with stock
	items = frappe.db.sql(
		"""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_qty
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND i.disabled = 0
        AND i.is_stock_item = 1
        ORDER BY i.item_name
    """,
		commissary_warehouse,
		as_dict=True,
	)

	alerts = []
	for item in items:
		# Get product-specific thresholds
		threshold = get_product_threshold(item["item_code"])
		safety_stock = threshold["target_di"] // 2
		reorder_level = threshold["target_di"]

		qty = flt(item["current_qty"])

		# Determine alert level based on product-specific thresholds
		if qty <= 0:
			alert_level = "critical"
		elif qty < safety_stock:
			alert_level = "warning"
		elif qty < reorder_level:
			alert_level = "info"
		else:
			continue  # No alert needed

		alerts.append(
			{
				"item_code": item["item_code"],
				"item_name": item["item_name"],
				"item_group": item["item_group"],
				"uom": item["uom"],
				"current_qty": qty,
				"safety_stock": safety_stock,
				"reorder_level": reorder_level,
				"alert_level": alert_level,
				"shelf_life": threshold["shelf_life"],
				"storage_temp": threshold["storage_temp"],
			}
		)

	# Sort by alert level priority
	alert_order = {"critical": 0, "warning": 1, "info": 2}
	alerts.sort(key=lambda x: (alert_order.get(x["alert_level"], 99), x["item_name"]))

	return {
		"success": True,
		"data": alerts,
		"summary": {
			"critical": sum(1 for a in alerts if a["alert_level"] == "critical"),
			"warning": sum(1 for a in alerts if a["alert_level"] == "warning"),
			"info": sum(1 for a in alerts if a["alert_level"] == "info"),
		},
	}


@frappe.whitelist()
def get_item_groups():
	"""
	Get item groups for filtering.
	"""
	set_backend_observability_context(module="commissary", action="get_item_groups", mutation_type="read")
	groups = frappe.get_all(
		"Item Group", filters={"is_group": 0}, fields=["name", "parent_item_group"], order_by="name"
	)
	return {"success": True, "data": groups}


# ============================================================
# 4. STORE ORDER FULFILLMENT
# ============================================================


@frappe.whitelist()
def get_pending_store_orders():
	"""
	Get pending Material Requests from stores, grouped by priority.
	"""
	set_backend_observability_context(
		module="commissary", action="get_pending_store_orders", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	mrs = frappe.get_all(
		"Material Request",
		filters={
			"status": ["in", ["Pending", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": "Material Transfer",
		},
		fields=["name", "transaction_date", "schedule_date", "status", "set_warehouse"],
		order_by="schedule_date asc",
	)

	# Enrich with store info and items
	from datetime import date, datetime

	for mr in mrs:
		# Store name
		mr["store_name"] = mr["set_warehouse"].replace(" - BEI", "") if mr["set_warehouse"] else "Unknown"

		# Calculate urgency (days until due)
		if mr["schedule_date"]:
			schedule = mr["schedule_date"]
			if isinstance(schedule, str):
				schedule = datetime.strptime(schedule, "%Y-%m-%d").date()
			days_until = (schedule - date.today()).days
			mr["days_until_due"] = days_until
			if days_until < 0:
				mr["urgency"] = "overdue"
			elif days_until == 0:
				mr["urgency"] = "today"
			elif days_until <= 1:
				mr["urgency"] = "urgent"
			else:
				mr["urgency"] = "normal"
		else:
			mr["days_until_due"] = None
			mr["urgency"] = "normal"

		# Get items with availability
		items = frappe.db.sql(
			"""
            SELECT
                mri.item_code,
                mri.item_name,
                mri.qty as requested_qty,
                IFNULL(mri.ordered_qty, 0) as ordered_qty,
                mri.qty - IFNULL(mri.ordered_qty, 0) as pending_qty,
                mri.uom,
                IFNULL(b.actual_qty, 0) as available_qty
            FROM `tabMaterial Request Item` mri
            LEFT JOIN `tabBin` b ON b.item_code = mri.item_code AND b.warehouse = %s
            WHERE mri.parent = %s
        """,
			(commissary_warehouse, mr["name"]),
			as_dict=True,
		)

		mr["items"] = items
		mr["items_count"] = len(items)
		mr["can_fulfill"] = all(i["available_qty"] >= i["pending_qty"] for i in items) if items else False
		mr["partial_fulfill"] = any(i["available_qty"] > 0 for i in items) and not mr["can_fulfill"]

	# Sort by urgency
	urgency_order = {"overdue": 0, "today": 1, "urgent": 2, "normal": 3}
	mrs.sort(key=lambda x: (urgency_order.get(x["urgency"], 99), x.get("schedule_date") or "9999-99-99"))

	return {"success": True, "data": mrs}


@frappe.whitelist()
def get_order_summary():
	"""
	Get summary of pending orders by store.
	"""
	set_backend_observability_context(module="commissary", action="get_order_summary", mutation_type="read")
	summary = frappe.db.sql(
		"""
        SELECT
            mr.set_warehouse as store,
            COUNT(mr.name) as order_count,
            SUM(
                (SELECT COUNT(*) FROM `tabMaterial Request Item` mri WHERE mri.parent = mr.name)
            ) as total_items
        FROM `tabMaterial Request` mr
        WHERE mr.status IN ('Pending', 'Partially Ordered')
        AND mr.docstatus = 1
        AND mr.material_request_type = 'Material Transfer'
        GROUP BY mr.set_warehouse
        ORDER BY order_count DESC
    """,
		as_dict=True,
	)

	for s in summary:
		s["store_name"] = s["store"].replace(" - BEI", "") if s["store"] else "Unknown"

	return {"success": True, "data": summary}


# ============================================================
# 5. QUALITY TRACKING
# ============================================================


@frappe.whitelist()
def get_fqi_summary(days=7):
	"""
	Get FQI (Food Quality Inspection) summary from stores.
	Aggregates BEI FQI Reports by issue_type, status, and store.
	"""
	set_backend_observability_context(module="commissary", action="get_fqi_summary", mutation_type="read")
	days = int(days)
	reports = frappe.get_all(
		"BEI FQI Report",
		filters={"creation": [">=", add_days(today(), -days)]},
		fields=["name", "issue_type", "status", "store", "item_code", "creation"],
		order_by="creation desc",
	)

	# Aggregate by status
	by_status = {}
	by_issue_type = {}
	for r in reports:
		by_status[r.status] = by_status.get(r.status, 0) + 1
		if r.issue_type:
			by_issue_type[r.issue_type] = by_issue_type.get(r.issue_type, 0) + 1

	return {
		"success": True,
		"data": reports,
		"summary": {
			"total": len(reports),
			"by_status": by_status,
			"by_issue_type": by_issue_type,
			"open_count": by_status.get("Open", 0) + by_status.get("Under Review", 0),
		},
	}


@frappe.whitelist()
def get_returns_pending(store=None):
	"""
	DEPRECATED: Delegates to store.get_returns_pending() which uses
	proper has_issue=1 + NOT EXISTS anti-join (G-002 Task 2C).
	"""
	set_backend_observability_context(module="commissary", action="get_returns_pending", mutation_type="read")
	from hrms.api.store import get_returns_pending as _store_returns

	return _store_returns(store=store)


# ============================================================
# 6. STOCK TRANSFER (Create dispatch from commissary)
# ============================================================


@frappe.whitelist()
def create_dispatch_transfer(
	target_warehouse: str,
	items: str | list[dict[str, Any]],
	mr_name: str | None = None,
	remarks: str | None = None,
):
	"""
	DEPRECATED: Use fulfill_store_order() instead.
	Kept for backward compatibility with existing frontend calls.

	Create Stock Entry (Material Transfer) for dispatch from commissary.

	Args:
	    target_warehouse: Destination warehouse (store)
	    items: JSON array of {item_code, qty, uom}
	    mr_name: Optional Material Request reference
	    remarks: Optional notes
	"""
	set_backend_observability_context(
		module="commissary", action="create_dispatch_transfer", mutation_type="create"
	)
	_raise_direct_fulfillment_retired()

	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to transfer"))

	commissary_warehouse = get_commissary_warehouse()

	# Create Stock Entry
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.company = get_commissary_company()
	se.posting_date = today()
	se.posting_time = frappe.utils.nowtime()
	se.from_warehouse = commissary_warehouse
	se.to_warehouse = target_warehouse
	se.remarks = remarks or f"Dispatch to {target_warehouse}"

	for item_data in items:
		item = frappe.get_doc("Item", item_data["item_code"])

		se.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": item.item_name,
				"description": item.description,
				"qty": flt(item_data["qty"]),
				"uom": item_data.get("uom") or item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": commissary_warehouse,
				"t_warehouse": target_warehouse,
				"material_request": mr_name,
			},
		)

	if not se.items:
		frappe.throw(_("No items to transfer"))

	se.insert()
	_clear_legacy_serial_batch_fields_after_auto_bundle(se)
	with _run_as_system_user("Administrator"):
		se.submit()

	# G-051: FEFO warnings
	from hrms.api.commissary_dashboard import _check_fefo_warnings

	fefo_warnings = _check_fefo_warnings(se, commissary_warehouse)

	result = {
		"success": True,
		"data": {"name": se.name, "total_qty": sum(i.qty for i in se.items), "items_count": len(se.items)},
		"message": f"Dispatch {se.name} created successfully",
	}
	if fefo_warnings:
		result["fefo_warnings"] = fefo_warnings
	return result


# ============================================================
# 7. ORDER DETAIL & FULFILLMENT
# ============================================================


@frappe.whitelist()
def get_order_detail(mr_name):
	"""
	Get detailed information about a Material Request for fulfillment.

	Args:
	    mr_name: Material Request name (e.g., 'MAT-MR-2026-00002')
	"""
	set_backend_observability_context(module="commissary", action="get_order_detail", mutation_type="read")
	if not mr_name:
		frappe.throw(_("Material Request name is required"))

	mr = frappe.get_doc("Material Request", mr_name)
	commissary_warehouse = get_commissary_warehouse()

	items = []
	for item in mr.items:
		# Get current stock in commissary
		stock = (
			frappe.db.get_value(
				"Bin", {"item_code": item.item_code, "warehouse": commissary_warehouse}, "actual_qty"
			)
			or 0
		)

		items.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,  # Alias for frontend compatibility
				"qty_requested": item.qty,
				"qty_ordered": item.ordered_qty or 0,
				"qty_received": item.received_qty or 0,
				"qty_pending": item.qty - (item.received_qty or 0),
				"uom": item.uom,
				"current_stock": flt(stock),
				"can_fulfill": flt(stock) >= (item.qty - (item.received_qty or 0)),
			}
		)

	return {
		"success": True,
		"data": {
			"name": mr.name,
			"mr_name": mr.name,  # Alias for frontend compatibility
			"set_warehouse": mr.set_warehouse or "",
			"transaction_date": str(mr.transaction_date) if mr.transaction_date else "",
			"schedule_date": str(mr.schedule_date) if mr.schedule_date else "",
			"status": mr.status,
			"owner": mr.owner,
			"items": items,
		},
	}


@frappe.whitelist()
def fulfill_store_order(mr_name: str, items: str | list[dict[str, Any]]):
	"""
	Fulfill a Material Request by creating a Stock Entry (Material Transfer).

	Args:
	    mr_name: Material Request name
	    items: JSON array of {item_code, qty_to_fulfill, uom}
	"""
	set_backend_observability_context(
		module="commissary", action="fulfill_store_order", mutation_type="create"
	)
	_raise_direct_fulfillment_retired()

	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to fulfill"))

	mr = frappe.get_doc("Material Request", mr_name)
	commissary_warehouse = get_commissary_warehouse()

	# Get target warehouse from header or first item
	target_warehouse = mr.set_warehouse
	if not target_warehouse and mr.items:
		target_warehouse = mr.items[0].warehouse

	if not target_warehouse:
		frappe.throw(_("Material Request has no target warehouse set"))

	# Build item_code to MR item name mapping
	mr_item_map = {item.item_code: item.name for item in mr.items}

	# Create Stock Entry
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.company = get_commissary_company()
	se.posting_date = today()
	se.posting_time = frappe.utils.nowtime()
	se.from_warehouse = commissary_warehouse
	se.to_warehouse = target_warehouse
	se.remarks = f"Fulfillment for {mr_name}"

	for item_data in items:
		qty = flt(item_data.get("qty_to_fulfill") or item_data.get("fulfilled_qty") or item_data.get("qty"))
		if qty <= 0:
			continue

		item_code = item_data["item_code"]
		item = frappe.get_doc("Item", item_code)

		# Get the MR item reference (required by ERPNext validation)
		mr_item_name = item_data.get("material_request_item") or mr_item_map.get(item_code)

		se.append(
			"items",
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"description": item.description,
				"qty": qty,
				"uom": item_data.get("uom") or item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": commissary_warehouse,
				"t_warehouse": target_warehouse,
				"material_request": mr_name,
				"material_request_item": mr_item_name,
			},
		)

	if not se.items:
		frappe.throw(_("No valid items to fulfill"))

	se.insert()
	_clear_legacy_serial_batch_fields_after_auto_bundle(se)
	with _run_as_system_user("Administrator"):
		se.submit()

	# S168: Create Draft Sales Invoice synchronously so failures surface with the SE.
	# The SI stays Draft until the store signs the DR at complete_receiving time.
	# Per ICT-001/004/007: BKI→store is an EXTERNAL sale (12% VAT, no intercompany
	# auto-mirror, revenue recognized on store DR acceptance).
	try:
		frappe.db.savepoint("s168_draft_si_create")
		store_order_name = frappe.db.get_value("Material Request", mr_name, "custom_store_order")
		si_name = build_bki_store_sale_invoice(
			stock_entry=se,
			store_order_name=store_order_name,
		)
		if si_name:
			frappe.db.set_value("Stock Entry", se.name, "custom_sales_invoice_draft", si_name)
		frappe.db.release_savepoint("s168_draft_si_create")
	except Exception:
		frappe.db.sql("ROLLBACK TO SAVEPOINT s168_draft_si_create")
		frappe.log_error(
			f"S168: Draft SI creation failed for SE {se.name}: {frappe.get_traceback()}",
			"S168 Draft SI Error",
		)
		# DO NOT raise -- fulfillment must not block on billing errors.

	# Update linked BEI Store Order status based on fulfillment completeness
	_update_store_order_status_after_fulfillment(mr_name, items)

	return {
		"success": True,
		"data": {
			"name": se.name,
			"mr_name": mr_name,
			"total_qty": sum(i.qty for i in se.items),
			"items_count": len(se.items),
		},
		"message": f"Order fulfilled: {se.name}",
	}


def _update_store_order_status_after_fulfillment(mr_name, fulfilled_items):
	"""
	After commissary fulfills a Material Request, update the linked BEI Store Order status.
	- All items fulfilled → "Ready for Dispatch"
	- Partial fulfillment → "Partially Fulfilled"
	"""
	try:
		# Find the BEI Store Order linked to this Material Request.
		# Check via custom_store_order field first, then fall back to warehouse + date match.
		store_order_name = frappe.db.get_value("Material Request", mr_name, "custom_store_order")
		if not store_order_name:
			# Fallback: find approved store order for the same target warehouse
			mr_warehouse = frappe.db.get_value("Material Request", mr_name, "set_warehouse")
			if mr_warehouse:
				store_order_name = frappe.db.get_value(
					"BEI Store Order",
					{"store": mr_warehouse, "status": "Approved"},
					"name",
					order_by="order_date desc",
				)
		if not store_order_name:
			return

		store_order = frappe.get_doc("BEI Store Order", store_order_name)

		# Build map of fulfilled quantities from input
		fulfilled_map = {}
		if isinstance(fulfilled_items, str):
			import json as _json

			fulfilled_items = _json.loads(fulfilled_items)
		for item in fulfilled_items:
			qty = flt(item.get("qty_to_fulfill") or item.get("fulfilled_qty") or item.get("qty") or 0)
			if qty > 0:
				fulfilled_map[item.get("item_code")] = fulfilled_map.get(item.get("item_code"), 0) + qty

		# Check if all items are fully fulfilled
		all_fulfilled = True
		any_fulfilled = False
		for order_item in store_order.items:
			fulfilled_qty = fulfilled_map.get(order_item.item_code, 0)
			if fulfilled_qty > 0:
				any_fulfilled = True
			if fulfilled_qty < flt(order_item.qty):
				all_fulfilled = False

		if all_fulfilled and any_fulfilled:
			store_order.status = "Ready for Dispatch"
		elif any_fulfilled:
			store_order.status = "Partially Fulfilled"

		if any_fulfilled:
			store_order.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(
			title="Store Order Status Update Failed",
			message=f"Failed to update store order status for MR {mr_name}: {e!s}",
		)


# ============================================================
# S168: BKI -> Store External Sale (Draft SI at Fulfillment)
# ============================================================
#
# Replaces the legacy G-046 intercompany auto-mirror. Stores are SEPARATE
# BIR-registered corporations (ICT-005), not BKI internal customers.
# SI is created DRAFT on fulfillment and submitted at store DR acceptance
# (ICT-007 destination terms). No Purchase Invoice auto-mirror (ICT-003):
# stores file their own AP/input VAT independently.


def build_bki_store_sale_invoice(
	stock_entry,
	store_order_name: str | None = None,
) -> str | None:
	"""S168: Create a Draft Sales Invoice for a BKI -> store fulfillment.

	The SI is inserted as DRAFT (docstatus=0) and held there until the
	store signs the Delivery Receipt via complete_receiving. At that
	point the SI is submitted with the receiving acceptance date as
	posting_date (ICT-007 destination terms / revenue on DR acceptance).

	Per ICT-001: 12% Output VAT applied via BEI Settings.bki_sales_vat_template.
	Per ICT-002: markup 2.75% JV / 8% Managed & Full Franchise.
	Per ICT-003: no auto Purchase Invoice -- stores file their own AP.
	Per ICT-004: no EWT (not Top 20,000).
	Per ICT-005: BKI is a separate Frappe Company.

	R1 Phase 3.1 amendment: one SI row per Stock Entry Detail row (row-level
	aggregation, not per-item_code) to avoid double-billing when S163 grouped
	orders produce multiple rows for the same item_code.

	Returns the SI name, or None if the buyer entity is on billing hold
	(provisional / missing register row). Callers MUST NOT raise when
	None is returned -- fulfillment continues, Finance is notified via
	the log_error breadcrumb.
	"""
	set_backend_observability_context(
		module="commissary",
		action="create_draft_store_sale_invoices",
		mutation_type="create",
	)

	# S192 fix: accept either a SE docname (string) or a Stock Entry doc
	if isinstance(stock_entry, str):
		stock_entry = frappe.get_doc("Stock Entry", stock_entry)

	# S192 fix: Material Issue intercompany SEs have no header.to_warehouse;
	# fall back to item-level t_warehouse (dispatch destination).
	target_warehouse = stock_entry.to_warehouse
	# S192 fix: intercompany Material Issue SEs put the destination on
	# custom_destination_warehouse, not header.to_warehouse.
	if not target_warehouse:
		target_warehouse = getattr(stock_entry, "custom_destination_warehouse", None)
	if not target_warehouse:
		for se_item in stock_entry.items:
			t_wh = getattr(se_item, "t_warehouse", None)
			s_wh = getattr(se_item, "s_warehouse", None)
			if t_wh and t_wh != s_wh:
				target_warehouse = t_wh
				break
	if not target_warehouse:
		frappe.log_error(
			f"S168: Stock Entry {stock_entry.name} has no to_warehouse; cannot create SI",
			"S168 Draft SI Error",
		)
		return None

	# S190: Company-first buyer entity resolution with CSV fallback
	entity_row = resolve_store_buyer_entity(warehouse_docname=target_warehouse) or {}

	if buyer_entity_requires_billing_hold(entity_row):
		frappe.log_error(
			(
				f"S190: Billing hold for warehouse={target_warehouse} "
				f"(status={entity_row.get('buyer_entity_status') or 'unknown'}); "
				"Draft SI NOT created. Finance must release the hold or amend the register."
			),
			"S190 Billing Hold",
		)
		return None

	buyer_entity_name = (entity_row.get("buyer_entity_name") or "").strip()
	store_type = (entity_row.get("store_type") or "").strip()
	if not buyer_entity_name:
		frappe.throw(
			_(
				"Store {0} has no buyer entity (checked Company Master and S037 register); "
				"cannot create SI"
			).format(target_warehouse)
		)

	bki_company = "Bebang Kitchen Inc."
	if not frappe.db.exists("Company", bki_company):
		frappe.throw(_("BKI company does not exist in Frappe (ICT-005)"))

	# Customer lookup: exact customer_name match, no company filter (R1 Amendment 14)
	customer = frappe.db.get_value(
		"Customer", {"customer_name": buyer_entity_name}, "name"
	)
	if not customer:
		frappe.throw(
			_(
				"No Customer '{0}' found in Frappe (store: {1}). "
				"Run scripts/s168_seed_customers.py to create missing Customers."
			).format(buyer_entity_name, target_warehouse)
		)

	# Markup + VAT template + income account from BEI Settings
	settings = frappe.get_single("BEI Settings")
	markup_by_type = {
		"JV": flt(getattr(settings, "bki_markup_jv_percent", 0) or 0) / 100,
		"Managed Franchise": flt(
			getattr(settings, "bki_markup_managed_franchise_percent", 0) or 0
		)
		/ 100,
		"Full Franchise": flt(
			getattr(settings, "bki_markup_full_franchise_percent", 0) or 0
		)
		/ 100,
	}
	markup_rate = markup_by_type.get(store_type)
	if markup_rate is None:
		frappe.throw(
			_(
				"Unknown store_type '{0}' for {1}. Configure markup in BEI Settings "
				"or fix the S037 register row."
			).format(store_type, target_warehouse)
		)

	vat_template = (getattr(settings, "bki_sales_vat_template", "") or "").strip()
	if not vat_template:
		frappe.throw(
			_(
				"BEI Settings.bki_sales_vat_template is not set. Cannot create SI "
				"without 12% VAT template (ICT-001)."
			)
		)

	income_account = (getattr(settings, "bki_sales_income_account", "") or "").strip()
	if not income_account:
		frappe.throw(_("BEI Settings.bki_sales_income_account is not set. Cannot create SI."))

	debit_to = (getattr(settings, "bki_sales_debit_to_account", "") or "").strip()

	# S168 Phase 12: BIR-aware naming series. Finance sets bki_sales_naming_series
	# in BEI Settings to match the authorized BIR ATP/PTU prefix before the first
	# production SI is issued. Until set, Frappe uses the SI default naming.
	bki_sales_naming_series = (
		getattr(settings, "bki_sales_naming_series", "") or ""
	).strip()

	# S168 Phase 13: EWT toggle (defaults OFF per ICT-004 — BEI is not Top 20,000).
	# When Finance flips bki_ewt_on_store_sales_enabled, the SI emits an EWT line
	# using the existing default_ewt_rate / ewt_payable_account from BEI Settings
	# (R1 Amendment 9 — reuse existing EWT fields, do not duplicate).
	ewt_enabled = bool(getattr(settings, "bki_ewt_on_store_sales_enabled", 0) or 0)
	default_ewt_rate = flt(getattr(settings, "default_ewt_rate", 0) or 0)
	ewt_payable_account = (
		getattr(settings, "ewt_payable_account", "") or ""
	).strip()

	# Build the Draft SI
	si = frappe.new_doc("Sales Invoice")
	si.company = bki_company
	si.customer = customer
	si.is_internal_customer = 0  # EXTERNAL sale per ICT-001
	si.posting_date = stock_entry.posting_date
	si.set_posting_time = 1
	si.currency = frappe.db.get_value("Company", bki_company, "default_currency") or "PHP"
	if bki_sales_naming_series:
		si.naming_series = bki_sales_naming_series
	si.taxes_and_charges = vat_template
	if debit_to:
		si.debit_to = debit_to
	# S192: bei_legal_entity + bei_store_label are mandatory custom fields on
	# Sales Invoice for ERP-sync attribution. Set them from the resolved
	# Company-first chain (S190).
	if frappe.get_meta("Sales Invoice").has_field("bei_legal_entity"):
		si.bei_legal_entity = buyer_entity_name
	if frappe.get_meta("Sales Invoice").has_field("bei_store_label"):
		si.bei_store_label = target_warehouse
	# Linkage (custom fields added by Phase 1 fixtures)
	si.custom_stock_entry = stock_entry.name
	if store_order_name:
		si.custom_bei_store_order = store_order_name
	si.remarks = (
		f"S168: Draft BKI->{buyer_entity_name} sale. Store: {target_warehouse} "
		f"({store_type}). Stock Entry: {stock_entry.name}. Markup: {markup_rate*100:.2f}%. "
		"Will be submitted on store DR acceptance (ICT-007)."
	)

	# S168 Phase 12 fix: resolve per-store cost center so BKI->store P&L rolls
	# up per store, not into the BKI company default. Falls back to company
	# default only if no per-store / group CC is seeded.
	resolved_cc = _resolve_store_cost_center(target_warehouse, entity_row)
	cost_center = resolved_cc or frappe.db.get_value(
		"Company", bki_company, "cost_center"
	)

	# Row-level aggregation: one SI row per Stock Entry Detail row (R1 Phase 3.1)
	# Prevents double-billing when grouped orders (S163) produce duplicate
	# item_code rows.
	has_rows = False
	for se_item in stock_entry.items:
		qty = flt(se_item.qty)
		if qty <= 0:
			continue
		base_price = flt(se_item.basic_rate)
		if not base_price:
			base_price = flt(
				frappe.db.get_value("Item", se_item.item_code, "valuation_rate")
			)
		if base_price <= 0:
			frappe.throw(
				_(
					"Item {0} has no basic_rate or valuation_rate; cannot price Draft SI "
					"for Stock Entry {1}"
				).format(se_item.item_code, stock_entry.name)
			)
		selling_price = flt(base_price * (1 + markup_rate), 4)
		row = {
			"item_code": se_item.item_code,
			"qty": qty,
			"uom": getattr(se_item, "uom", None) or getattr(se_item, "stock_uom", None),
			"rate": selling_price,
			"income_account": income_account,
			"warehouse": stock_entry.to_warehouse,
			"cost_center": cost_center,
			# Traceability: which SE Detail row this SI row came from
			"custom_stock_entry_detail": se_item.name,
		}
		si.append("items", row)
		has_rows = True

	if not has_rows:
		frappe.log_error(
			f"S168: Stock Entry {stock_entry.name} has no billable items; Draft SI not created",
			"S168 Draft SI Error",
		)
		return None

	# Pull taxes from the configured template (12% VAT per ICT-001)
	try:
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		taxes = get_taxes_and_charges("Sales Taxes and Charges Template", vat_template) or []
		for tax in taxes:
			si.append("taxes", tax)
	except Exception:
		frappe.log_error(
			f"S168: Failed to load taxes from template {vat_template}: {frappe.get_traceback()}",
			"S168 Draft SI Error",
		)
		raise

	# S168 Phase 13: append EWT row only if Finance flipped the toggle.
	# default_ewt_rate is the % to withhold; ewt_payable_account is the GL credit.
	# Per ICT-004, this branch is dormant — toggle stays off until BEI is tagged
	# Top 20,000 by BIR. Code path is in place so Finance can flip without a deploy.
	if ewt_enabled and default_ewt_rate > 0 and ewt_payable_account:
		si.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": ewt_payable_account,
				"description": f"EWT {default_ewt_rate}% (S168 Phase 13)",
				"rate": -abs(default_ewt_rate),  # negative = deduction
				"add_deduct_tax": "Deduct",
			},
		)

	si.insert(ignore_permissions=True)
	# DO NOT submit. SI stays Draft until complete_receiving submits it on
	# store DR acceptance (ICT-007). docstatus=0 is intentional.
	return si.name


def _resolve_store_cost_center(store_warehouse: str, entity_row: dict) -> str | None:
	"""S168 Phase 12: resolve the per-store Cost Center for a BKI->store sale.

	Cost center hierarchy (seeded by scripts/s168_seed_cost_centers.py):
		Stores - BKI
		  JV - BKI
		    {store} - BKI
		  Managed Franchise - BKI
		    {store} - BKI
		  Full Franchise - BKI
		    {store} - BKI

	Resolution order:
	  1. Per-store cost center derived from entity_row.buyer_entity_name
	     (exact seed-script pattern "{buyer_entity_name} - BKI").
	  2. Per-store cost center derived from the warehouse name.
	  3. Store-type parent group ("JV - BKI" / "Managed Franchise - BKI" /
	     "Full Franchise - BKI").
	  4. "Stores - BKI" umbrella group.
	  5. None (caller falls back to Company default).
	"""
	try:
		if not frappe.db.exists("DocType", "Cost Center"):
			return None
	except Exception:
		return None

	bki_company = "Bebang Kitchen Inc."
	candidates: list[str] = []

	entity_row = entity_row or {}
	buyer_name = (entity_row.get("buyer_entity_name") or "").strip()
	if buyer_name:
		candidates.append(f"{buyer_name} - BKI")

	if store_warehouse:
		# Warehouse names already look like "Store X - BKI"; try verbatim
		# and also try re-appending " - BKI" to the stripped form.
		candidates.append(store_warehouse)
		bare = store_warehouse
		if bare.endswith(" - BKI"):
			bare = bare[: -len(" - BKI")]
			candidates.append(f"{bare} - BKI")

	store_type = (entity_row.get("store_type") or "").strip()
	if store_type:
		candidates.append(f"{store_type} - BKI")

	candidates.append("Stores - BKI")

	seen: set[str] = set()
	for cc_name in candidates:
		if not cc_name or cc_name in seen:
			continue
		seen.add(cc_name)
		try:
			if frappe.db.exists(
				"Cost Center", {"name": cc_name, "company": bki_company}
			):
				return cc_name
		except Exception:
			continue
	return None


def _delete_orphan_draft_si_on_se_cancel(doc, method=None):
	"""S168: If a Stock Entry is cancelled and has a linked Draft SI, delete
	the orphan Draft SI so it does not linger in the billing holds dashboard.

	Registered on Stock Entry on_cancel via hooks.py (wired by schema agent).
	Safe to call even if the field or doc does not exist.
	"""
	try:
		si_name = getattr(doc, "custom_sales_invoice_draft", None)
		if not si_name:
			return
		if not frappe.db.exists("Sales Invoice", si_name):
			return
		docstatus = frappe.db.get_value("Sales Invoice", si_name, "docstatus")
		if docstatus != 0:
			# Only delete DRAFT invoices; never touch submitted/cancelled SIs.
			frappe.log_error(
				(
					f"S168: Stock Entry {doc.name} cancelled but linked SI {si_name} "
					f"is docstatus={docstatus}; not deleting. Manual review required."
				),
				"S168 Draft SI Cancel",
			)
			return
		frappe.delete_doc(
			"Sales Invoice",
			si_name,
			force=True,
			ignore_permissions=True,
			delete_permanently=True,
		)
		frappe.db.set_value("Stock Entry", doc.name, "custom_sales_invoice_draft", None)
	except Exception:
		frappe.log_error(
			f"S168: Failed to clean up orphan Draft SI on SE cancel {doc.name}: {frappe.get_traceback()}",
			"S168 Draft SI Cancel",
		)


@frappe.whitelist()
def clear_buyer_entity_cache():
	"""S168 Amendment 10: System Manager endpoint to reload the S037 register.

	`load_store_buyer_entity_register` is decorated with @lru_cache(maxsize=1)
	for performance. After updating the register CSV, call this endpoint to
	reload it without a bench restart.
	"""
	set_backend_observability_context(
		module="commissary",
		action="clear_buyer_entity_cache",
		mutation_type="update",
	)
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Only System Manager can reload the buyer entity register"))
	cache_clear = getattr(load_store_buyer_entity_register, "cache_clear", None)
	if callable(cache_clear):
		cache_clear()
	return {"success": True, "message": "Buyer entity register cache cleared"}


@frappe.whitelist()
def get_ready_for_pickup():
	"""
	Get Stock Entries that are ready for pickup/dispatch.
	These are submitted Material Transfer entries from commissary.
	"""
	set_backend_observability_context(
		module="commissary", action="get_ready_for_pickup", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	# Get recent Material Transfer stock entries from commissary
	entries = frappe.get_all(
		"Stock Entry",
		filters={
			"stock_entry_type": "Material Transfer",
			"from_warehouse": commissary_warehouse,
			"docstatus": 1,
			"posting_date": [">=", frappe.utils.add_days(today(), -7)],  # Last 7 days
		},
		fields=["name", "posting_date", "to_warehouse", "remarks", "owner"],
		order_by="posting_date desc",
		limit=50,
	)

	result = []
	for entry in entries:
		# Get items for this entry
		items = frappe.get_all(
			"Stock Entry Detail",
			filters={"parent": entry.name},
			fields=["item_code", "item_name", "qty", "uom"],
		)

		result.append(
			{
				"name": entry.name,
				"posting_date": str(entry.posting_date) if entry.posting_date else "",
				"target_warehouse": entry.to_warehouse,
				"remarks": entry.remarks,
				"owner": entry.owner,
				"items_count": len(items),
				"total_qty": sum(i.qty for i in items),
				"items": items[:5],  # First 5 items for preview
			}
		)

	return {"success": True, "data": result}


# ============================================================
# 8. DAYS INVENTORY & SHIFT TRACKING (Phase 1 Enhancements)
# ============================================================

# Product-specific thresholds based on MANCOM data and questionnaire responses
PRODUCT_THRESHOLDS = {
	# Frozen products (60 days shelf life)
	"FG020": {"shelf_life": 60, "target_di": 14, "yellow_alert": 16, "red_alert": 21, "storage_temp": "-18C"},
	# Short shelf life products (14-15 days)
	"FG001": {
		"shelf_life": 15,
		"target_di": 7,
		"yellow_alert": 10,
		"red_alert": 12,
		"storage_temp": "0-4C",
	},  # Leche Flan
	"FG004": {
		"shelf_life": 15,
		"target_di": 7,
		"yellow_alert": 10,
		"red_alert": 12,
		"storage_temp": "0-4C",
	},  # Buko Pandan Jelly
	"FG005": {
		"shelf_life": 15,
		"target_di": 7,
		"yellow_alert": 10,
		"red_alert": 12,
		"storage_temp": "0-4C",
	},  # Vanilla White Jelly
	"FG006": {
		"shelf_life": 14,
		"target_di": 7,
		"yellow_alert": 10,
		"red_alert": 12,
		"storage_temp": "-18C",
	},  # Coconut Jelly
	"FG007": {
		"shelf_life": 14,
		"target_di": 7,
		"yellow_alert": 10,
		"red_alert": 12,
		"storage_temp": "0-4C",
	},  # Coconut Syrup
	"FG009": {
		"shelf_life": 21,
		"target_di": 10,
		"yellow_alert": 14,
		"red_alert": 18,
		"storage_temp": "0-4C",
	},  # Sago
	"FG012": {
		"shelf_life": 21,
		"target_di": 10,
		"yellow_alert": 14,
		"red_alert": 18,
		"storage_temp": "0-4C",
	},  # Melted Ube
	# FG015 BP Sauce - DISCONTINUED (no longer produced in commissary as of Feb 2026)
	# Long shelf life products
	"FG003": {
		"shelf_life": 180,
		"target_di": 30,
		"yellow_alert": 45,
		"red_alert": 60,
		"storage_temp": "20-25C",
	},  # Rice Crispies
	"FG014": {
		"shelf_life": 60,
		"target_di": 14,
		"yellow_alert": 21,
		"red_alert": 30,
		"storage_temp": "20-25C",
	},  # Pistachio Mix
}

# Default thresholds for items not in the lookup
DEFAULT_THRESHOLD = {
	"shelf_life": 30,
	"target_di": 14,
	"yellow_alert": 21,
	"red_alert": 30,
	"storage_temp": "ambient",
}


def get_product_threshold(item_code):
	"""
	Get product-specific thresholds, checking custom fields first then fallback to lookup.
	"""
	# First check if item has custom fields set
	custom_fields = frappe.db.get_value(
		"Item",
		item_code,
		[
			"custom_shelf_life_days",
			"custom_reorder_days",
			"custom_storage_temp_min",
			"custom_storage_temp_max",
		],
		as_dict=True,
	)

	if custom_fields and custom_fields.get("custom_shelf_life_days"):
		shelf_life = custom_fields["custom_shelf_life_days"]
		target_di = custom_fields.get("custom_reorder_days") or max(7, shelf_life // 4)
		return {
			"shelf_life": shelf_life,
			"target_di": target_di,
			"yellow_alert": int(target_di * 1.5),
			"red_alert": int(target_di * 2),
			"storage_temp": f"{custom_fields.get('custom_storage_temp_min', 0)}-{custom_fields.get('custom_storage_temp_max', 25)}C",
		}

	# Check for FG code prefix match
	for code_prefix, threshold in PRODUCT_THRESHOLDS.items():
		if item_code.startswith(code_prefix):
			return threshold

	return DEFAULT_THRESHOLD


@frappe.whitelist()
def get_days_inventory():
	"""
	Calculate Days Inventory (DI) for each finished goods product.

	Formula: DI = Current Stock / Average Daily Consumption (7-day rolling)
	Target: 14 days (MANCOM standard for most products)

	Returns:
	    - item_code, item_name
	    - current_stock: Current quantity in commissary
	    - avg_daily_consumption: 7-day rolling average of outgoing qty
	    - days_inventory: Calculated DI (current_stock / avg_daily_consumption)
	    - target_di: Target days inventory for this product
	    - status: 'ok', 'yellow', 'red', 'overstocked'
	    - shelf_life: Product shelf life in days
	"""
	set_backend_observability_context(module="commissary", action="get_days_inventory", mutation_type="read")
	commissary_warehouse = get_commissary_warehouse()
	today_date = today()
	date_7_days_ago = add_days(today_date, -7)

	# Get all FG items with current stock
	items = frappe.db.sql(
		"""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            b.actual_qty as current_stock
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND i.disabled = 0
        AND i.is_stock_item = 1
        AND (i.item_group = 'Finished Goods' OR i.item_code LIKE 'FG%%')
        ORDER BY i.item_name
    """,
		commissary_warehouse,
		as_dict=True,
	)

	result = []
	for item in items:
		# Calculate 7-day consumption (outgoing stock from commissary)
		consumption = (
			frappe.db.sql(
				"""
            SELECT IFNULL(SUM(ABS(sed.qty)), 0) as total_out
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1
            AND se.posting_date BETWEEN %s AND %s
            AND sed.s_warehouse = %s
            AND sed.item_code = %s
        """,
				(date_7_days_ago, today_date, commissary_warehouse, item["item_code"]),
			)[0][0]
			or 0
		)

		# Calculate average daily consumption
		avg_daily = flt(consumption / 7, 2)

		# Get product-specific thresholds
		threshold = get_product_threshold(item["item_code"])

		# Calculate days inventory
		if avg_daily > 0:
			days_inv = flt(item["current_stock"] / avg_daily, 1)
		else:
			# No consumption = infinite DI (overstocked or no demand)
			days_inv = 999 if item["current_stock"] > 0 else 0

		# Determine status based on thresholds
		target_di = threshold["target_di"]
		if days_inv == 0:
			status = "out_of_stock"
		elif days_inv < target_di * 0.5:
			status = "critical"
		elif days_inv < target_di:
			status = "low"
		elif days_inv <= threshold["yellow_alert"]:
			status = "ok"
		elif days_inv <= threshold["red_alert"]:
			status = "overstocked_warning"
		else:
			status = "overstocked"

		result.append(
			{
				"item_code": item["item_code"],
				"item_name": item["item_name"],
				"item_group": item["item_group"],
				"uom": item["uom"],
				"current_stock": flt(item["current_stock"]),
				"avg_daily_consumption": avg_daily,
				"total_7day_consumption": flt(consumption),
				"days_inventory": days_inv if days_inv < 999 else None,
				"target_di": target_di,
				"yellow_alert": threshold["yellow_alert"],
				"red_alert": threshold["red_alert"],
				"shelf_life": threshold["shelf_life"],
				"storage_temp": threshold["storage_temp"],
				"status": status,
			}
		)

	# Sort by status priority (critical first)
	status_order = {
		"out_of_stock": 0,
		"critical": 1,
		"low": 2,
		"ok": 3,
		"overstocked_warning": 4,
		"overstocked": 5,
	}
	result.sort(key=lambda x: (status_order.get(x["status"], 99), x["item_name"]))

	# Summary stats
	summary = {
		"total_items": len(result),
		"out_of_stock": sum(1 for r in result if r["status"] == "out_of_stock"),
		"critical": sum(1 for r in result if r["status"] == "critical"),
		"low": sum(1 for r in result if r["status"] == "low"),
		"ok": sum(1 for r in result if r["status"] == "ok"),
		"overstocked": sum(1 for r in result if r["status"] in ["overstocked_warning", "overstocked"]),
	}

	return {
		"success": True,
		"data": result,
		"summary": summary,
		"target_di_standard": 14,
		"calculation_period": f"{date_7_days_ago} to {today_date}",
	}


@frappe.whitelist()
def get_current_shift():
	"""
	Get the current production shift based on time of day.

	Shifts (from Bryan's questionnaire):
	- AM Shift: 5:00 AM - 2:00 PM
	- PM Shift: 4:00 PM - 1:00 AM
	- Dispatch: 4:00 AM

	Returns current shift info and next shift details.
	"""
	set_backend_observability_context(module="commissary", action="get_current_shift", mutation_type="read")
	from datetime import datetime

	now = datetime.now()
	current_hour = now.hour

	# Define shifts
	shifts = {
		"dispatch": {"start": 4, "end": 5, "label": "Dispatch", "break_time": None},
		"am": {"start": 5, "end": 14, "label": "AM Shift", "break_time": "9:00 AM"},
		"pm": {"start": 16, "end": 25, "label": "PM Shift", "break_time": "8:00 PM"},  # 25 = 1 AM next day
		"gap_am_pm": {"start": 14, "end": 16, "label": "Between Shifts", "break_time": None},
		"night": {"start": 1, "end": 4, "label": "Night (Post-PM)", "break_time": None},
	}

	# Determine current shift
	# Handle PM shift that crosses midnight
	if current_hour >= 16 or current_hour < 1:
		current_shift = "pm"
		shift_info = shifts["pm"]
	elif 1 <= current_hour < 4:
		current_shift = "night"
		shift_info = shifts["night"]
	elif 4 <= current_hour < 5:
		current_shift = "dispatch"
		shift_info = shifts["dispatch"]
	elif 5 <= current_hour < 14:
		current_shift = "am"
		shift_info = shifts["am"]
	else:  # 14 <= current_hour < 16
		current_shift = "gap_am_pm"
		shift_info = shifts["gap_am_pm"]

	# Calculate time remaining in shift
	shift_end = shift_info["end"]
	if shift_end > 24:
		shift_end -= 24
	if current_hour < shift_info["start"] and shift_info["end"] > 24:
		# We're in the post-midnight part of PM shift
		hours_remaining = shift_end - current_hour
	else:
		hours_remaining = (shift_end - current_hour) % 24

	# Determine next shift
	if current_shift == "dispatch":
		next_shift = "AM Shift starts at 5:00 AM"
	elif current_shift == "am":
		next_shift = "PM Shift starts at 4:00 PM"
	elif current_shift == "pm" or current_shift == "night":
		next_shift = "Dispatch at 4:00 AM"
	else:
		next_shift = "PM Shift starts at 4:00 PM"

	return {
		"success": True,
		"data": {
			"current_shift": shift_info["label"],
			"shift_code": current_shift,
			"current_time": now.strftime("%I:%M %p"),
			"hours_remaining": round(hours_remaining, 1),
			"break_time": shift_info["break_time"],
			"next_shift": next_shift,
			"staffing": {"am": 11, "pm": 8, "supervisor_ratio": "1:20"},
		},
	}


# ============================================================
# 9. PRODUCTIVITY & WEEKLY METRICS (Phase 2 Enhancements)
# ============================================================


@frappe.whitelist()
def get_productivity_metrics(date_from=None, date_to=None):
	"""
	Calculate productivity metrics (kg/manhour) for commissary operations.

	Returns:
	    - total_output_kg: Sum of production output in kg
	    - total_manhours: From BEI Weekly Labor Plan or estimated
	    - productivity: total_output_kg / total_manhours
	    - breakdown_by_product: Output breakdown by FG product
	    - breakdown_by_activity: Manhours by activity (Common Packing, Frozen Milk, Cooking)

	Target productivity: ~50 kg/manhour
	"""
	set_backend_observability_context(
		module="commissary", action="get_productivity_metrics", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	if not date_from:
		date_from = add_days(today(), -7)
	if not date_to:
		date_to = today()

	# Get production output (Material Receipt to commissary = production)
	output_data = frappe.db.sql(
		"""
        SELECT
            sed.item_code,
            i.item_name,
            SUM(sed.qty) as total_qty,
            i.stock_uom as uom
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        JOIN `tabItem` i ON i.name = sed.item_code
        WHERE se.docstatus = 1
        AND se.stock_entry_type IN ('Material Receipt', 'Manufacture')
        AND se.posting_date BETWEEN %s AND %s
        AND sed.t_warehouse = %s
        GROUP BY sed.item_code
        ORDER BY total_qty DESC
    """,
		(date_from, date_to, commissary_warehouse),
		as_dict=True,
	)

	# Calculate total output in KG
	total_output_kg = 0
	breakdown_by_product = []
	for row in output_data:
		# Convert to KG based on UOM
		qty_kg = row["total_qty"]
		if row["uom"] in ["Gram", "g"]:
			qty_kg = row["total_qty"] / 1000
		elif row["uom"] in ["Barrel", "barrel"]:
			qty_kg = row["total_qty"] * 2.5  # ~2.5kg per barrel

		total_output_kg += qty_kg
		breakdown_by_product.append(
			{
				"item_code": row["item_code"],
				"item_name": row["item_name"],
				"qty": flt(row["total_qty"]),
				"qty_kg": flt(qty_kg, 2),
				"uom": row["uom"],
				"percentage": 0,  # Will calculate after total
			}
		)

	# Calculate percentages
	for item in breakdown_by_product:
		if total_output_kg > 0:
			item["percentage"] = flt((item["qty_kg"] / total_output_kg) * 100, 1)

	# Estimate manhours based on MANCOM ratios
	# From MANCOM: WW5 had 669 manhours for 26.3K kg output
	# Breakdown: Common Packing 38.3%, Frozen Milk 34.2%, Cooking 27.5%
	# Try to get from BEI Weekly Labor Plan if available
	manhours = None
	try:
		if frappe.db.exists("DocType", "BEI Weekly Labor Plan"):
			labor_data = frappe.db.sql(
				"""
                SELECT SUM(total_hours) as total_manhours
                FROM `tabBEI Weekly Labor Plan`
                WHERE start_date <= %s AND end_date >= %s
            """,
				(date_to, date_from),
			)
			if labor_data and labor_data[0][0]:
				manhours = flt(labor_data[0][0])
	except Exception:
		pass

	# If no labor plan data, estimate based on MANCOM ratio (~39.3 kg/manhour)
	if not manhours:
		# Estimate: ~25 manhours per 1000 kg (from 669 hours / 26.3K kg)
		manhours = flt(total_output_kg / 1000 * 25.4, 1)
		manhours_source = "estimated"
	else:
		manhours_source = "labor_plan"

	# Calculate productivity
	productivity = flt(total_output_kg / manhours, 2) if manhours > 0 else 0

	# Estimate activity breakdown based on MANCOM ratios
	breakdown_by_activity = [
		{"activity": "Common Packing", "manhours": flt(manhours * 0.383, 1), "percentage": 38.3},
		{"activity": "Frozen Milk", "manhours": flt(manhours * 0.342, 1), "percentage": 34.2},
		{"activity": "Cooking", "manhours": flt(manhours * 0.275, 1), "percentage": 27.5},
	]

	return {
		"success": True,
		"data": {
			"date_from": date_from,
			"date_to": date_to,
			"total_output_kg": flt(total_output_kg, 2),
			"total_manhours": flt(manhours, 1),
			"manhours_source": manhours_source,
			"productivity_kg_per_hour": productivity,
			"target_productivity": 50,
			"productivity_status": "above_target" if productivity >= 50 else "below_target",
			"breakdown_by_product": breakdown_by_product,
			"breakdown_by_activity": breakdown_by_activity,
		},
	}


@frappe.whitelist()
def get_weekly_summary(work_week=None):
	"""
	Get MANCOM-format weekly summary for a specific work week.

	Work week format: "WW5" or "2026-W05" or ISO week number
	If not provided, returns current week.

	Returns KPIs in MANCOM slide format:
	    - output_by_product
	    - manhours_by_activity
	    - productivity_kg_per_hour
	    - days_inventory
	    - wastage
	    - week_on_week_comparison
	"""
	set_backend_observability_context(module="commissary", action="get_weekly_summary", mutation_type="read")
	from datetime import datetime, timedelta

	# Parse work week and get date range
	if not work_week:
		# Current week
		today_dt = datetime.strptime(today(), "%Y-%m-%d")
		week_start = today_dt - timedelta(days=today_dt.weekday())
		week_end = week_start + timedelta(days=6)
		week_number = today_dt.isocalendar()[1]
	else:
		# Parse work week (handle WW5, 2026-W05, or just 5)
		if work_week.upper().startswith("WW"):
			week_number = int(work_week[2:])
		elif "-W" in work_week:
			week_number = int(work_week.split("-W")[1])
		else:
			week_number = int(work_week)

		# Get the Monday of that week (assume current year)
		year = datetime.now().year
		week_start = datetime.strptime(f"{year}-W{week_number:02d}-1", "%Y-W%W-%w")
		week_end = week_start + timedelta(days=6)

	date_from = week_start.strftime("%Y-%m-%d")
	date_to = week_end.strftime("%Y-%m-%d")

	# Get productivity metrics for this week
	productivity = get_productivity_metrics(date_from, date_to)["data"]

	# Get days inventory
	di_data = get_days_inventory()["data"]

	# Get previous week for comparison
	prev_week_start = week_start - timedelta(days=7)
	prev_week_end = prev_week_start + timedelta(days=6)
	prev_productivity = get_productivity_metrics(
		prev_week_start.strftime("%Y-%m-%d"), prev_week_end.strftime("%Y-%m-%d")
	)["data"]

	# Calculate week-on-week changes
	output_change = 0
	productivity_change = 0
	if prev_productivity["total_output_kg"] > 0:
		output_change = flt(
			(
				(productivity["total_output_kg"] - prev_productivity["total_output_kg"])
				/ prev_productivity["total_output_kg"]
			)
			* 100,
			1,
		)
	if prev_productivity["productivity_kg_per_hour"] > 0:
		productivity_change = flt(
			(
				(productivity["productivity_kg_per_hour"] - prev_productivity["productivity_kg_per_hour"])
				/ prev_productivity["productivity_kg_per_hour"]
			)
			* 100,
			1,
		)

	# Get wastage (Stock Entry with purpose containing "waste" or "spoilage")
	wastage = (
		frappe.db.sql(
			"""
        SELECT IFNULL(SUM(sed.qty), 0) as wastage_qty
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
        AND se.posting_date BETWEEN %s AND %s
        AND (se.remarks LIKE '%%waste%%' OR se.remarks LIKE '%%spoil%%' OR se.stock_entry_type = 'Material Issue')
    """,
			(date_from, date_to),
		)[0][0]
		or 0
	)

	return {
		"success": True,
		"data": {
			"work_week": f"WW{week_number}",
			"date_range": f"{date_from} to {date_to}",
			"output": {
				"total_kg": productivity["total_output_kg"],
				"by_product": productivity["breakdown_by_product"],
				"change_from_last_week": output_change,
			},
			"manhours": {
				"total": productivity["total_manhours"],
				"source": productivity["manhours_source"],
				"by_activity": productivity["breakdown_by_activity"],
			},
			"productivity": {
				"kg_per_hour": productivity["productivity_kg_per_hour"],
				"target": 50,
				"status": productivity["productivity_status"],
				"change_from_last_week": productivity_change,
			},
			"days_inventory": {
				"items": di_data[:10],  # Top 10 items
				"summary": {
					"total_items": len(di_data),
					"below_target": sum(1 for d in di_data if d["status"] in ["critical", "low"]),
					"at_target": sum(1 for d in di_data if d["status"] == "ok"),
					"overstocked": sum(
						1 for d in di_data if d["status"] in ["overstocked_warning", "overstocked"]
					),
				},
			},
			"wastage": {"total_kg": flt(wastage, 2), "target": 0},
		},
	}


@frappe.whitelist()
def get_delivery_routes():
	"""
	Get delivery routes with store assignments.

	Routes from Bryan's questionnaire:
	- North: 7 routes
	- South: 8 routes
	- Total: 15 routes serving 50+ stores
	"""
	set_backend_observability_context(module="commissary", action="get_delivery_routes", mutation_type="read")
	# Hard-coded route data from Bryan's questionnaire response
	routes = {
		"north": [
			{"route": "North-1", "truck": 1, "stores": ["Clark", "Pulilan", "Marilao"]},
			{"route": "North-2", "truck": 2, "stores": ["Fairview Terraces", "SM Caloocan", "SJDM"]},
			{"route": "North-3", "truck": 3, "stores": ["Ever Commonwealth", "Uptown Center", "SM North"]},
			{"route": "North-4", "truck": 4, "stores": ["Valenzuela", "Sangandaan", "Grand Central"]},
			{"route": "North-5", "truck": 5, "stores": ["Lucky Chinatown", "SM Manila", "Megamall"]},
			{"route": "North-6", "truck": 6, "stores": ["CTT Morato", "Araneta Gateway", "Marikina"]},
			{
				"route": "North-7",
				"truck": 7,
				"stores": ["East Ortigas", "Robinson Antipolo", "Taytay", "St. Lucia"],
			},
		],
		"south": [
			{"route": "South-1", "truck": 1, "stores": ["Paseo Makati", "Grid Rockwell", "Uptown BGC"]},
			{
				"route": "South-2",
				"truck": 2,
				"stores": ["Market Market", "Venice Grand Canal", "Vista Taguig"],
			},
			{"route": "South-3", "truck": 3, "stores": ["MOA", "PITX", "NAIA T3"]},
			{"route": "South-4", "truck": 4, "stores": ["Bicutan", "BF Homes", "Southmall"]},
			{"route": "South-5", "truck": 5, "stores": ["Sta Rosa", "Solenad", "D'Verde Calamba"]},
			{"route": "South-6", "truck": 6, "stores": ["Evo City Kawit", "Robinson Gen Trias", "SM Tanza"]},
			{
				"route": "South-7",
				"truck": 7,
				"stores": ["Festival Alabang", "Terminal Alabang", "Galleria South"],
			},
			{"route": "South-8", "truck": 8, "stores": ["Robinson Imus", "Ayala Vermosa"]},
		],
	}

	# Try to get today's dispatch trips if BEI Distribution Trip exists
	todays_trips = []
	try:
		if frappe.db.exists("DocType", "BEI Distribution Trip"):
			trips = frappe.get_all(
				"BEI Distribution Trip",
				filters={"trip_date": today()},
				fields=["name", "route_name", "driver", "vehicle", "status", "total_stops"],
			)
			todays_trips = trips
	except Exception:
		pass

	# Calculate summary
	total_stores = sum(len(r["stores"]) for r in routes["north"]) + sum(
		len(r["stores"]) for r in routes["south"]
	)

	return {
		"success": True,
		"data": {
			"routes": routes,
			"summary": {
				"north_routes": len(routes["north"]),
				"south_routes": len(routes["south"]),
				"total_routes": len(routes["north"]) + len(routes["south"]),
				"total_stores": total_stores,
				"dispatch_time": "4:00 AM",
				"order_deadline": "12:00 PM (previous day)",
				"lead_time": "1 day",
			},
			"todays_trips": todays_trips,
			"external_hubs": [
				{"name": "3MD", "type": "Wet & Dry", "location": "Bulacan", "contact": "Vlad Ferrer"},
				{"name": "JENTEC", "type": "Dry", "location": "Pasig", "contact": "Beverly Que"},
				{"name": "RCS", "type": "Frozen", "location": "Taytay", "contact": "Joey Ancheta"},
				{"name": "PINNACLE", "type": "Wet & Dry", "location": "Laguna", "contact": "Daryl Alano"},
			],
		},
	}


# ============================================================
# 10. EXTERNAL HUB TRACKING (Phase 3)
# ============================================================


@frappe.whitelist()
def get_hub_inventory(hub_code=None):
	"""
	Get inventory levels at external hubs.

	Args:
	    hub_code: Optional specific hub code (3MD, JENTEC, RCS, PINNACLE)
	              If not provided, returns all hubs.

	Returns hub information with current inventory items.
	"""
	set_backend_observability_context(module="commissary", action="get_hub_inventory", mutation_type="read")
	# Check if BEI External Hub DocType exists
	if not frappe.db.exists("DocType", "BEI External Hub"):
		# Return hardcoded data if DocType not yet created
		default_hubs = [
			{
				"hub_code": "3MD",
				"hub_name": "3MD Logistics",
				"hub_type": "Wet & Dry",
				"location": "Bulacan",
				"contact_person": "Vlad Ferrer",
				"items": [],
			},
			{
				"hub_code": "JENTEC",
				"hub_name": "JENTEC Warehouse",
				"hub_type": "Dry",
				"location": "Pasig",
				"contact_person": "Beverly Que",
				"items": [],
			},
			{
				"hub_code": "RCS",
				"hub_name": "RCS Cold Storage",
				"hub_type": "Frozen",
				"location": "Taytay",
				"contact_person": "Joey Ancheta",
				"items": [],
			},
			{
				"hub_code": "PINNACLE",
				"hub_name": "Pinnacle Logistics",
				"hub_type": "Wet & Dry",
				"location": "Laguna",
				"contact_person": "Daryl Alano",
				"items": [],
			},
		]
		if hub_code:
			hubs = [h for h in default_hubs if h["hub_code"] == hub_code.upper()]
		else:
			hubs = default_hubs

		return {
			"success": True,
			"data": hubs,
			"source": "default",
			"message": "BEI External Hub DocType not yet created. Showing default data.",
		}

	# Get from DocType
	filters = {"is_active": 1}
	if hub_code:
		filters["hub_code"] = hub_code.upper()

	hubs = frappe.get_all(
		"BEI External Hub",
		filters=filters,
		fields=[
			"hub_code",
			"hub_name",
			"hub_type",
			"location",
			"contact_person",
			"contact_phone",
			"contact_email",
			"lead_time_days",
			"notes",
		],
	)

	# Get items for each hub
	for hub in hubs:
		items = frappe.get_all(
			"BEI Hub Item",
			filters={"parent": hub["hub_code"], "parenttype": "BEI External Hub"},
			fields=["item_code", "item_name", "current_qty", "uom", "last_updated"],
		)
		hub["items"] = items
		hub["total_items"] = len(items)
		hub["total_qty"] = sum(i.get("current_qty", 0) for i in items)

	return {"success": True, "data": hubs, "source": "doctype"}


@frappe.whitelist()
def update_hub_inventory(hub_code, item_code, qty, uom=None):
	"""
	Update inventory level for an item at an external hub.

	Args:
	    hub_code: Hub code (3MD, JENTEC, RCS, PINNACLE)
	    item_code: Item code
	    qty: New quantity
	    uom: Unit of measure (optional, defaults to stock UOM)
	"""
	set_backend_observability_context(
		module="commissary", action="update_hub_inventory", mutation_type="update"
	)
	if not frappe.db.exists("DocType", "BEI External Hub"):
		frappe.throw("BEI External Hub DocType not yet created. Please run bench migrate.")

	hub_code = hub_code.upper()
	if not frappe.db.exists("BEI External Hub", hub_code):
		frappe.throw(f"Hub {hub_code} not found")

	if not frappe.db.exists("Item", item_code):
		frappe.throw(f"Item {item_code} not found")

	hub = frappe.get_doc("BEI External Hub", hub_code)

	# Find existing item or add new
	item_found = False
	for item in hub.items:
		if item.item_code == item_code:
			item.current_qty = flt(qty)
			item.last_updated = frappe.utils.now()
			if uom:
				item.uom = uom
			item_found = True
			break

	if not item_found:
		# Add new item
		item_doc = frappe.get_doc("Item", item_code)
		hub.append(
			"items",
			{
				"item_code": item_code,
				"item_name": item_doc.item_name,
				"current_qty": flt(qty),
				"uom": uom or item_doc.stock_uom,
				"last_updated": frappe.utils.now(),
			},
		)

	hub.save()

	return {
		"success": True,
		"message": f"Updated {item_code} at {hub_code}: {qty}",
		"data": {"hub_code": hub_code, "item_code": item_code, "new_qty": flt(qty)},
	}


# ============================================================
# 11. HUB TRANSFER (NEW - Task #3)
# ============================================================

# Distribution hub warehouse mapping
DISTRIBUTION_HUBS = {
	"3MD": "3MD Logistics - Camangyanan - BEI",
	"JENTEC": "Jentec Storage Inc. - BEI",
	"RCS": "Royal Cold Storage - Taytay - BEI",
	"PINNACLE": "Pinnacle Cold Storage - BEI",
}


@frappe.whitelist()
def get_distribution_hubs():
	"""
	Get list of available distribution hubs for transfer.
	"""
	set_backend_observability_context(
		module="commissary", action="get_distribution_hubs", mutation_type="read"
	)
	hubs = []
	for code, warehouse in DISTRIBUTION_HUBS.items():
		# Check if warehouse exists
		exists = frappe.db.exists("Warehouse", warehouse)
		hub_info = {
			"hub_code": code,
			"warehouse": warehouse,
			"exists": exists,
			"hub_type": "Cold + Dry"
			if code in ["3MD", "PINNACLE"]
			else ("Frozen" if code == "RCS" else "Dry"),
		}

		# Get current stock count if warehouse exists
		if exists:
			stock_count = frappe.db.sql(
				"""
                SELECT COUNT(DISTINCT item_code) as items, SUM(actual_qty) as total_qty
                FROM `tabBin` WHERE warehouse = %s AND actual_qty > 0
            """,
				warehouse,
				as_dict=True,
			)[0]
			hub_info["items_count"] = stock_count.get("items") or 0
			hub_info["total_qty"] = flt(stock_count.get("total_qty") or 0)

		hubs.append(hub_info)

	return {"success": True, "data": hubs}


@frappe.whitelist()
def create_hub_transfer(
	destination_hub: str,
	items: str | list[dict[str, Any]],
	remarks: str | None = None,
):
	"""
	Create Stock Entry (Material Transfer) from Commissary to Distribution Hub.

	Args:
	    destination_hub: Hub code (3MD, JENTEC, RCS, PINNACLE)
	    items: JSON array of {item_code, qty, batch_no (optional)}
	    remarks: Optional notes

	Returns:
	    Stock Entry name and details
	"""
	set_backend_observability_context(
		module="commissary", action="create_hub_transfer", mutation_type="create"
	)
	_raise_direct_fulfillment_retired()

	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to transfer"))

	destination_hub = destination_hub.upper()
	if destination_hub not in DISTRIBUTION_HUBS:
		frappe.throw(
			_(f"Invalid hub code: {destination_hub}. Valid codes: {', '.join(DISTRIBUTION_HUBS.keys())}")
		)

	target_warehouse = DISTRIBUTION_HUBS[destination_hub]

	# G-100: Idempotency — prevent duplicate hub transfers within 5 minutes
	recent_transfer = frappe.db.exists(
		"Stock Entry",
		{
			"stock_entry_type": "Material Transfer",
			"to_warehouse": target_warehouse,
			"posting_date": today(),
			"owner": frappe.session.user,
			"creation": [">=", add_days(today(), 0)],  # same day
			"docstatus": ["<", 2],
		},
	)
	if recent_transfer:
		frappe.throw(
			_(
				"A hub transfer to {0} already exists today ({1}). "
				"If you need another transfer, please wait or cancel the existing one."
			).format(destination_hub, recent_transfer)
		)

	# Verify warehouse exists
	if not frappe.db.exists("Warehouse", target_warehouse):
		frappe.throw(_(f"Warehouse {target_warehouse} does not exist. Please create it first."))

	commissary_warehouse = get_commissary_warehouse()

	# Create Stock Entry
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.company = get_commissary_company()
	se.posting_date = today()
	se.posting_time = frappe.utils.nowtime()
	se.from_warehouse = commissary_warehouse
	se.to_warehouse = target_warehouse
	se.remarks = remarks or f"Hub Transfer to {destination_hub}"

	for item_data in items:
		item = frappe.get_doc("Item", item_data["item_code"])

		# Validate sufficient stock
		current_stock = (
			frappe.db.get_value(
				"Bin", {"item_code": item_data["item_code"], "warehouse": commissary_warehouse}, "actual_qty"
			)
			or 0
		)

		qty = flt(item_data["qty"])
		if qty > current_stock:
			frappe.throw(
				_(f"Insufficient stock for {item.item_name}. Available: {current_stock}, Requested: {qty}")
			)

		item_row = {
			"item_code": item_data["item_code"],
			"item_name": item.item_name,
			"description": item.description,
			"qty": qty,
			"uom": item_data.get("uom") or item.stock_uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": 1,
			"s_warehouse": commissary_warehouse,
			"t_warehouse": target_warehouse,
		}

		# Handle batch if provided
		if item_data.get("batch_no"):
			valid_batch = get_or_create_batch(item_data["batch_no"], item_data["item_code"])
			if valid_batch:
				item_row["batch_no"] = valid_batch

		se.append("items", item_row)

	se.insert()
	_clear_legacy_serial_batch_fields_after_auto_bundle(se)
	with _run_as_system_user("Administrator"):
		se.submit()

	return {
		"success": True,
		"data": {
			"name": se.name,
			"destination_hub": destination_hub,
			"target_warehouse": target_warehouse,
			"total_qty": sum(i.qty for i in se.items),
			"items_count": len(se.items),
		},
		"message": f"Transfer {se.name} to {destination_hub} created successfully",
	}


@frappe.whitelist()
def get_transfer_history(destination_hub=None, date_from=None, date_to=None, limit=50):
	"""
	Get history of transfers from Commissary to Distribution Hubs.

	Args:
	    destination_hub: Optional filter by hub code
	    date_from: Optional start date
	    date_to: Optional end date
	    limit: Max results (default 50)
	"""
	set_backend_observability_context(
		module="commissary", action="get_transfer_history", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	# Build warehouse filter
	if destination_hub:
		destination_hub = destination_hub.upper()
		if destination_hub not in DISTRIBUTION_HUBS:
			frappe.throw(_(f"Invalid hub code: {destination_hub}"))
		target_warehouses = [DISTRIBUTION_HUBS[destination_hub]]
	else:
		target_warehouses = list(DISTRIBUTION_HUBS.values())

	# Build date filter
	date_filter = ""
	params = [commissary_warehouse]

	if date_from and date_to:
		date_filter = "AND se.posting_date BETWEEN %s AND %s"
		params.extend([date_from, date_to])
	elif date_from:
		date_filter = "AND se.posting_date >= %s"
		params.append(date_from)
	elif date_to:
		date_filter = "AND se.posting_date <= %s"
		params.append(date_to)

	# Query transfers
	warehouse_placeholders = ", ".join(["%s"] * len(target_warehouses))
	params.extend(target_warehouses)
	params.append(int(limit))

	# conditions (date_filter, warehouse_placeholders) are string constants, not user input
	transfers = frappe.db.sql(
		"SELECT se.name, se.posting_date, se.to_warehouse, se.remarks, se.owner, se.docstatus,"
		" COUNT(sed.item_code) as items_count, SUM(sed.qty) as total_qty"
		" FROM `tabStock Entry` se"
		" JOIN `tabStock Entry Detail` sed ON sed.parent = se.name"
		" WHERE se.stock_entry_type = 'Material Transfer'"
		" AND se.from_warehouse = %s"
		" AND se.to_warehouse IN (" + warehouse_placeholders + ")"
		" AND se.docstatus = 1"
		" " + date_filter + " GROUP BY se.name"
		" ORDER BY se.posting_date DESC, se.creation DESC"
		" LIMIT %s",
		params,
		as_dict=True,
	)

	# Add hub code to each transfer
	warehouse_to_hub = {v: k for k, v in DISTRIBUTION_HUBS.items()}
	for t in transfers:
		t["hub_code"] = warehouse_to_hub.get(t["to_warehouse"], "UNKNOWN")
		t["total_qty"] = flt(t["total_qty"])

	return {
		"success": True,
		"data": transfers,
		"summary": {"total_transfers": len(transfers), "total_qty": sum(t["total_qty"] for t in transfers)},
	}
