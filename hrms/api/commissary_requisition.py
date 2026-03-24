"""Commissary Requisition & Production Planning APIs. Split from commissary.py (P0-11) for maintainability."""

import json
from contextlib import contextmanager
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from hrms.api.commissary import get_commissary_company, get_commissary_warehouse
from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supply_chain_contracts import (
	FINANCE_TREATMENT_INTERCOMPANY,
	REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL,
	get_request_source_label,
	infer_finance_treatment,
	resolve_material_request_contract,
	resolve_warehouse_company,
	stamp_material_request_contract,
)


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


COMMISSARY_COMPANY = "Bebang Kitchen Inc."


def _get_commissary_raw_material_items(commissary_warehouse: str) -> list[dict[str, Any]]:
	"""
	Return the canonical commissary raw-material universe.

	Only ingredients used by active default BOMs for finished goods are included,
	and the item itself must still be tagged as Raw Materials. This keeps the
	commissary monitor centered on true production inputs instead of every stock
	item that happens to share an RM code prefix.
	"""
	return frappe.db.sql(
		"""
        SELECT DISTINCT
            i.name as item_code,
            i.item_name,
            i.item_group,
            i.stock_uom as uom,
            IFNULL(b.actual_qty, 0) as current_qty
        FROM `tabItem` i
        JOIN `tabBOM Item` bi ON bi.item_code = i.name
        JOIN `tabBOM` bom
            ON bom.name = bi.parent
            AND bom.is_active = 1
            AND bom.is_default = 1
            AND bom.docstatus = 1
        JOIN `tabItem` fg
            ON fg.name = bom.item
            AND fg.item_group = 'Finished Goods'
            AND fg.disabled = 0
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
          AND i.item_group = 'Raw Materials'
        ORDER BY i.item_name
    """,
		commissary_warehouse,
		as_dict=True,
	)


# ---------------------------------------------------------------------------
# RAW MATERIAL REORDER ALERTS
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_rm_reorder_alerts():
	"""
	Get raw materials that are below reorder level in Commissary.
	Uses reorder_level field on Item if set, otherwise estimates based on
	7-day consumption average x 3 (lead time buffer).
	"""
	set_backend_observability_context(
		module="commissary", action="get_rm_reorder_alerts", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()
	today_date = today()
	date_7_days_ago = add_days(today_date, -7)

	rm_items = _get_commissary_raw_material_items(commissary_warehouse)

	alerts = []
	for item in rm_items:
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

		avg_daily = flt(consumption / 7, 2)

		reorder_meta = (
			frappe.db.get_value(
				"Item Reorder",
				{"parent": item["item_code"], "warehouse": commissary_warehouse},
				["warehouse_reorder_level", "warehouse_reorder_qty"],
				as_dict=True,
			)
			or {}
		)

		if reorder_meta.get("warehouse_reorder_level") and reorder_meta["warehouse_reorder_level"] > 0:
			reorder_level = flt(reorder_meta["warehouse_reorder_level"])
		else:
			reorder_level = flt(avg_daily * 3, 2)

		if reorder_meta.get("warehouse_reorder_qty") and reorder_meta["warehouse_reorder_qty"] > 0:
			safety_stock = flt(reorder_meta["warehouse_reorder_qty"])
		else:
			safety_stock = flt(avg_daily, 2)

		current_qty = flt(item["current_qty"])

		if current_qty <= 0:
			alert_level = "critical"
			status = "Out of Stock"
		elif current_qty < safety_stock:
			alert_level = "critical"
			status = "Below Safety Stock"
		elif current_qty < reorder_level:
			alert_level = "warning"
			status = "Reorder Needed"
		else:
			continue

		target_qty = flt(avg_daily * 7, 2)
		suggested_qty = max(target_qty - current_qty, reorder_level)

		alerts.append(
			{
				"item_code": item["item_code"],
				"item_name": item["item_name"],
				"item_group": item["item_group"],
				"uom": item["uom"],
				"current_qty": current_qty,
				"reorder_level": reorder_level,
				"safety_stock": safety_stock,
				"avg_daily_consumption": avg_daily,
				"suggested_order_qty": flt(suggested_qty, 2),
				"alert_level": alert_level,
				"status": status,
			}
		)

	alert_order = {"critical": 0, "warning": 1}
	alerts.sort(key=lambda x: (alert_order.get(x["alert_level"], 99), x["item_name"]))

	return {
		"success": True,
		"data": alerts,
		"summary": {
			"total_alerts": len(alerts),
			"critical": sum(1 for a in alerts if a["alert_level"] == "critical"),
			"warning": sum(1 for a in alerts if a["alert_level"] == "warning"),
		},
	}


# ---------------------------------------------------------------------------
# RAW MATERIAL REQUISITION
# ---------------------------------------------------------------------------


@frappe.whitelist()
def create_rm_requisition(
	items: str | list[dict[str, Any]] | None = None,
	required_by_date: str | None = None,
	remarks: str | None = None,
	source_warehouse: str | None = None,
):
	"""
	Create Material Request for raw materials from Commissary.

	Args:
	    items: JSON array of {item_code, qty, uom (optional)}
	    required_by_date: When materials are needed (defaults to 3 days from now)
	    remarks: Optional notes

	Returns:
	    Material Request name and details
	"""
	set_backend_observability_context(
		module="commissary", action="create_rm_requisition", mutation_type="create"
	)
	if not items:
		frappe.throw(_("Missing required parameter: items"), frappe.ValidationError)
	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to request"))

	commissary_warehouse = get_commissary_warehouse()

	# G-100: Idempotency — prevent duplicate Draft requisitions by same user on same day
	existing_draft = frappe.db.exists(
		"Material Request",
		{
			"material_request_type": "Material Transfer",
			"set_warehouse": commissary_warehouse,
			"transaction_date": today(),
			"owner": frappe.session.user,
			"docstatus": 0,
		},
	)
	if existing_draft:
		frappe.throw(
			_(
				"You already have a Draft requisition today ({0}). "
				"Please edit the existing one or submit it before creating another."
			).format(existing_draft)
		)

	# Default required_by_date to 3 days from now (standard lead time)
	if not required_by_date:
		required_by_date = add_days(today(), 3)

	# Create Material Request
	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Material Transfer"
	target_company = resolve_warehouse_company(commissary_warehouse) or COMMISSARY_COMPANY
	source_company = resolve_warehouse_company(source_warehouse) or target_company
	finance_treatment = infer_finance_treatment(source_company, target_company)
	is_intercompany = finance_treatment == FINANCE_TREATMENT_INTERCOMPANY
	mr.company = target_company
	mr.transaction_date = today()
	mr.schedule_date = required_by_date
	mr.set_warehouse = commissary_warehouse
	mr.remarks = remarks or "Warehouse raw material request from Commissary"
	stamp_material_request_contract(
		mr,
		request_source=REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL,
		cargo_lane="RM",
		source_warehouse=source_warehouse,
		source_company=source_company,
		target_company=target_company,
		finance_treatment=finance_treatment,
	)

	for item_data in items:
		item = frappe.get_doc("Item", item_data["item_code"])

		row = {
			"item_code": item_data["item_code"],
			"item_name": item.item_name,
			"description": item.description,
			"qty": flt(item_data["qty"]),
			"uom": item_data.get("uom") or item.stock_uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": 1,
			"warehouse": commissary_warehouse,
			"schedule_date": required_by_date,
		}
		# For inter-company requests (e.g., BKI commissary requesting from BEI 3PL),
		# omit from_warehouse to avoid ERPNext's validate_warehouse_company rejection.
		# The MR is a request document — the actual stock transfer is handled by
		# warehouse receiving which already supports inter-company via Material Issue.
		if source_warehouse and not is_intercompany:
			row["from_warehouse"] = source_warehouse
		mr.append("items", row)

	mr.insert(ignore_permissions=True)
	with _run_as_system_user("Administrator"):
		mr.submit()
	return {
		"success": True,
		"data": {
			"name": mr.name,
			"items_count": len(mr.items),
			"total_qty": sum(i.qty for i in mr.items),
			"required_by_date": str(required_by_date),
			"status": mr.status,
			"request_source": REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL,
			"request_source_label": get_request_source_label(REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL),
		},
		"message": f"Material Request {mr.name} submitted to the warehouse queue",
	}


@frappe.whitelist()
def approve_requisition(mr_name):
	"""
	Approve (submit) a Draft Material Request.
	Only SCM Manager / Warehouse Manager can approve.
	"""
	set_backend_observability_context(
		module="commissary", action="approve_requisition", mutation_type="update"
	)
	from hrms.utils.scm_roles import SCM_APPROVAL_ROLES, check_scm_permission

	check_scm_permission(SCM_APPROVAL_ROLES, "approve requisitions")

	mr = frappe.get_doc("Material Request", mr_name)
	if mr.docstatus != 0:
		frappe.throw(
			_("Only Draft requisitions can be approved. Current status: {0}").format(
				"Submitted" if mr.docstatus == 1 else "Cancelled"
			)
		)

	with _run_as_system_user("Administrator"):
		mr.submit()

	return {
		"success": True,
		"data": {"name": mr.name, "status": mr.status},
		"message": f"Material Request {mr.name} approved and submitted",
	}


@frappe.whitelist()
def get_my_requisitions(status=None, limit=50):
	"""
	Get Material Requests created from Commissary.

	Args:
	    status: Optional filter by status (Pending, Ordered, Received, etc.)
	    limit: Max results (default 50)

	Returns list of requisitions with item details.
	"""
	set_backend_observability_context(module="commissary", action="get_my_requisitions", mutation_type="read")
	commissary_warehouse = get_commissary_warehouse()

	filters = {
		"material_request_type": "Material Transfer",
		"set_warehouse": commissary_warehouse,
		"docstatus": ["in", [0, 1]],  # Draft or Submitted
	}

	if status:
		filters["status"] = status

	mrs = frappe.get_all(
		"Material Request",
		filters=filters,
		fields=["name", "transaction_date", "schedule_date", "status", "owner", "docstatus"],
		order_by="transaction_date desc",
		limit=int(limit),
	)

	filtered_mrs = []
	for mr in mrs:
		mr_doc = frappe.get_doc("Material Request", mr["name"])
		contract = resolve_material_request_contract(mr_doc, commissary_warehouse=commissary_warehouse)
		if contract["request_source"] != REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL:
			continue

		# Get items
		items = frappe.get_all(
			"Material Request Item",
			filters={"parent": mr["name"]},
			fields=["item_code", "item_name", "qty", "ordered_qty", "received_qty", "uom"],
		)
		mr["items"] = items
		mr["items_count"] = len(items)
		mr["total_qty"] = sum(i.get("qty", 0) for i in items)
		mr["total_ordered"] = sum(i.get("ordered_qty", 0) for i in items)
		mr["total_received"] = sum(i.get("received_qty", 0) for i in items)
		mr.update(contract)

		# Calculate fulfillment percentage
		if mr["total_qty"] > 0:
			mr["fulfillment_pct"] = flt((mr["total_received"] / mr["total_qty"]) * 100, 1)
		else:
			mr["fulfillment_pct"] = 0
		filtered_mrs.append(mr)

	return {
		"success": True,
		"data": filtered_mrs,
		"summary": {
			"total": len(filtered_mrs),
			"pending": sum(1 for m in filtered_mrs if m["status"] in ["Pending", "Draft"]),
			"ordered": sum(1 for m in filtered_mrs if m["status"] == "Ordered"),
			"partially_received": sum(1 for m in filtered_mrs if m["status"] == "Partially Received"),
			"received": sum(1 for m in filtered_mrs if m["status"] == "Received"),
		},
	}


@frappe.whitelist()
def get_rm_for_requisition():
	"""
	Get raw materials available for requisition with current stock and alerts.
	Combines inventory levels with reorder recommendations.
	"""
	set_backend_observability_context(
		module="commissary", action="get_rm_for_requisition", mutation_type="read"
	)
	# Get reorder alerts first
	alerts_data = get_rm_reorder_alerts()
	alerts = {a["item_code"]: a for a in alerts_data["data"]}

	commissary_warehouse = get_commissary_warehouse()
	rm_items = _get_commissary_raw_material_items(commissary_warehouse)

	result = []
	for item in rm_items:
		item_data = {
			"item_code": item["item_code"],
			"item_name": item["item_name"],
			"item_group": item["item_group"],
			"uom": item["uom"],
			"current_qty": flt(item["current_qty"]),
			"needs_reorder": item["item_code"] in alerts,
			"suggested_qty": 0,
			"alert_level": None,
		}

		# Add alert data if available
		if item["item_code"] in alerts:
			alert = alerts[item["item_code"]]
			item_data["suggested_qty"] = alert["suggested_order_qty"]
			item_data["alert_level"] = alert["alert_level"]
			item_data["reorder_level"] = alert["reorder_level"]

		result.append(item_data)

	# Sort: items needing reorder first
	result.sort(key=lambda x: (0 if x["needs_reorder"] else 1, x["item_name"]))

	return {"success": True, "data": result, "alerts_count": len(alerts)}


# ---------------------------------------------------------------------------
# PRODUCTION PLANNING
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_production_suggestions():
	"""
	Get production suggestions based on stock levels and demand.
	Suggests FG items that are below safety stock or have pending orders.
	"""
	set_backend_observability_context(
		module="commissary", action="get_production_suggestions", mutation_type="read"
	)
	commissary_warehouse = get_commissary_warehouse()

	# Get FG items with current stock and pending demand
	suggestions = frappe.db.sql(
		"""
        SELECT
            i.item_code,
            i.item_name,
            i.stock_uom,
            COALESCE(bin.actual_qty, 0) as current_stock,
            COALESCE(bin.reserved_qty, 0) as reserved_qty,
            COALESCE(
                (SELECT SUM(mri.qty - mri.ordered_qty)
                 FROM `tabMaterial Request Item` mri
                 JOIN `tabMaterial Request` mr ON mr.name = mri.parent
                 WHERE mri.item_code = i.item_code
                 AND mr.docstatus = 1
                 AND mr.status NOT IN ('Stopped', 'Cancelled')
                ), 0
            ) as pending_demand,
            b.name as bom_name
        FROM `tabItem` i
        LEFT JOIN `tabBin` bin ON bin.item_code = i.name AND bin.warehouse = %s
        LEFT JOIN `tabBOM` b ON b.item = i.name AND b.is_active = 1 AND b.is_default = 1
        WHERE i.item_group = 'Finished Goods'
        AND i.disabled = 0
        ORDER BY pending_demand DESC, current_stock ASC
    """,
		commissary_warehouse,
		as_dict=True,
	)

	result = []
	for item in suggestions:
		# Calculate suggested production qty
		target_stock = 100  # Default safety stock
		gap = target_stock - item.current_stock + item.pending_demand

		if gap > 0 and item.bom_name:
			result.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"uom": item.stock_uom,
					"current_stock": flt(item.current_stock),
					"pending_demand": flt(item.pending_demand),
					"suggested_qty": flt(gap, 0),
					"bom_name": item.bom_name,
					"priority": "high" if item.pending_demand > 0 else "normal",
				}
			)

	return {"success": True, "data": result, "total": len(result)}


@frappe.whitelist()
def create_work_order(item_code, qty, planned_start_date=None, remarks=None):
	"""
	Create a Work Order for a Finished Good item.

	Args:
	    item_code: FG item to produce
	    qty: Quantity to produce
	    planned_start_date: When to start (defaults to today)
	    remarks: Optional notes
	"""
	set_backend_observability_context(module="commissary", action="create_work_order", mutation_type="create")
	commissary_warehouse = get_commissary_warehouse()

	# Get the default BOM for this item
	bom = frappe.db.get_value(
		"BOM", {"item": item_code, "is_active": 1, "is_default": 1}, ["name", "quantity"], as_dict=True
	)

	if not bom:
		return {"success": False, "error": f"No active BOM found for item {item_code}"}

	# Check material availability against BOM
	shortages = []
	bom_items = frappe.get_all(
		"BOM Item", filters={"parent": bom.name}, fields=["item_code", "item_name", "qty"]
	)
	for bi in bom_items:
		required_qty = flt(bi.qty) * flt(qty) / flt(bom.quantity or 1)
		available = flt(
			frappe.db.get_value(
				"Bin", {"item_code": bi.item_code, "warehouse": commissary_warehouse}, "actual_qty"
			)
		)
		if available < required_qty:
			shortages.append(
				{
					"item_code": bi.item_code,
					"item_name": bi.item_name,
					"required": required_qty,
					"available": available,
					"short": required_qty - available,
				}
			)

	if shortages:
		return {"success": False, "error": "Insufficient materials for production", "shortages": shortages}

	# Create Work Order
	wo = frappe.new_doc("Work Order")
	wo.production_item = item_code
	wo.bom_no = bom.name
	wo.qty = flt(qty)
	wo.fg_warehouse = commissary_warehouse
	wo.wip_warehouse = commissary_warehouse  # Same warehouse for simplicity
	wo.company = get_commissary_company()
	wo.planned_start_date = planned_start_date or today()
	wo.expected_delivery_date = planned_start_date or today()

	if remarks:
		wo.remarks = remarks

	wo.insert()

	return {
		"success": True,
		"message": f"Work Order {wo.name} created",
		"data": {
			"name": wo.name,
			"item_code": wo.production_item,
			"qty": wo.qty,
			"bom_no": wo.bom_no,
			"status": wo.status,
		},
	}


@frappe.whitelist()
def get_work_orders(status=None, days=7):
	"""
	Get Work Orders for commissary production.

	Args:
	    status: Filter by status (optional)
	    days: Days to look back (default 7)
	"""
	set_backend_observability_context(module="commissary", action="get_work_orders", mutation_type="read")
	filters = {"fg_warehouse": ["like", "%Commissary%"], "creation": [">=", add_days(today(), -int(days))]}

	if status:
		filters["status"] = status

	work_orders = frappe.get_all(
		"Work Order",
		filters=filters,
		fields=[
			"name",
			"production_item",
			"item_name",
			"qty",
			"produced_qty",
			"status",
			"planned_start_date",
			"expected_delivery_date",
			"bom_no",
		],
		order_by="creation desc",
		limit=50,
	)

	# Calculate completion percentage
	for wo in work_orders:
		wo["completion_pct"] = round(wo.produced_qty / wo.qty * 100, 1) if wo.qty > 0 else 0

	# Summary by status
	summary = {}
	for wo in work_orders:
		status = wo.status
		if status not in summary:
			summary[status] = {"count": 0, "qty": 0}
		summary[status]["count"] += 1
		summary[status]["qty"] += wo.qty

	return {"success": True, "data": work_orders, "summary": summary}


@frappe.whitelist()
def start_work_order(work_order_name):
	"""Start a work order (submit if draft, begin manufacturing)."""
	set_backend_observability_context(module="commissary", action="start_work_order", mutation_type="create")
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	commissary_warehouse = get_commissary_warehouse()
	wo = frappe.get_doc("Work Order", work_order_name)

	if wo.docstatus == 0:
		# Ensure WO has source_warehouse before submitting (needed for material transfer)
		if not wo.source_warehouse:
			wo.source_warehouse = commissary_warehouse or "Stores - BEI"
			wo.save()
		with _run_as_system_user("Administrator"):
			wo.submit()
		wo.reload()

	if wo.status in ("Submitted", "Not Started"):
		# Use ERPNext's native make_stock_entry for proper WO linking and tracking
		se_dict = make_stock_entry(work_order_name, "Material Transfer for Manufacture", wo.qty)
		se = frappe.get_doc(se_dict)
		se.stock_entry_type = "Material Transfer for Manufacture"

		# Ensure all items have source and target warehouses (BOM items may not specify)
		default_source = wo.source_warehouse or commissary_warehouse or "Stores - BEI"
		default_wip = wo.wip_warehouse or commissary_warehouse
		for item in se.items:
			if not item.s_warehouse:
				item.s_warehouse = default_source
			if not item.t_warehouse:
				item.t_warehouse = default_wip

		se.insert()
		_clear_legacy_serial_batch_fields_after_auto_bundle(se)
		with _run_as_system_user("Administrator"):
			se.submit()

		return {
			"success": True,
			"message": f"Work Order {wo.name} started. Material transferred.",
			"data": {"work_order": wo.name, "stock_entry": se.name},
		}

	return {"success": False, "error": f"Work Order is in status {wo.status}, cannot start"}


@frappe.whitelist()
def complete_work_order(work_order_name, qty_produced=None):
	"""Complete a work order by creating manufacture stock entry."""
	set_backend_observability_context(
		module="commissary", action="complete_work_order", mutation_type="create"
	)
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

	commissary_warehouse = get_commissary_warehouse()
	wo = frappe.get_doc("Work Order", work_order_name)

	if wo.status not in ["Submitted", "Not Started", "In Process"]:
		return {"success": False, "error": f"Work Order is in status {wo.status}, cannot complete"}

	qty = flt(qty_produced) or wo.qty - wo.produced_qty

	# Use ERPNext's native make_stock_entry for proper WO linking, FG item, and tracking
	se_dict = make_stock_entry(work_order_name, "Manufacture", qty)
	se = frappe.get_doc(se_dict)
	se.stock_entry_type = "Manufacture"

	# Ensure raw materials have source warehouse
	default_source = wo.wip_warehouse or commissary_warehouse or "Stores - BEI"
	for item in se.items:
		if not item.s_warehouse and not item.is_finished_item:
			item.s_warehouse = default_source

	se.insert()
	_clear_legacy_serial_batch_fields_after_auto_bundle(se)
	with _run_as_system_user("Administrator"):
		se.submit()

	# Refresh work order status
	wo.reload()

	return {
		"success": True,
		"message": f"Manufactured {qty} units of {wo.production_item}",
		"data": {
			"work_order": wo.name,
			"stock_entry": se.name,
			"produced_qty": wo.produced_qty,
			"status": wo.status,
		},
	}


# ---------------------------------------------------------------------------
# COMPATIBILITY WRAPPERS FOR CANONICAL CONTRACT MODULE
# ---------------------------------------------------------------------------


@frappe.whitelist()
def submit_production_output(items, batch_no=None, remarks=None):
	"""Bridge requisition route mapping to dashboard production submit API."""
	set_backend_observability_context(
		module="commissary", action="submit_production_output", mutation_type="create"
	)
	from hrms.api.commissary_dashboard import submit_production_output as dashboard_submit

	return dashboard_submit(items=items, batch_no=batch_no, remarks=remarks)


@frappe.whitelist()
def create_dispatch_transfer(target_warehouse, items, mr_name=None, remarks=None):
	"""Legacy wrapper kept for Sprint 18 route compatibility."""
	set_backend_observability_context(
		module="commissary", action="create_dispatch_transfer", mutation_type="create"
	)
	from hrms.api.commissary import create_dispatch_transfer as legacy_create_dispatch_transfer

	return legacy_create_dispatch_transfer(
		target_warehouse=target_warehouse,
		items=items,
		mr_name=mr_name,
		remarks=remarks,
	)


@frappe.whitelist()
def create_hub_transfer(destination_hub, items, remarks=None):
	"""Legacy wrapper kept for Sprint 18 route compatibility."""
	set_backend_observability_context(
		module="commissary", action="create_hub_transfer", mutation_type="create"
	)
	from hrms.api.commissary import create_hub_transfer as legacy_create_hub_transfer

	return legacy_create_hub_transfer(
		destination_hub=destination_hub,
		items=items,
		remarks=remarks,
	)


@frappe.whitelist()
def fulfill_store_order(mr_name, items):
	"""Legacy wrapper kept for Sprint 18 route compatibility."""
	set_backend_observability_context(
		module="commissary", action="fulfill_store_order", mutation_type="create"
	)
	from hrms.api.commissary import fulfill_store_order as legacy_fulfill_store_order

	return legacy_fulfill_store_order(mr_name=mr_name, items=items)


@frappe.whitelist()
def update_hub_inventory(hub_code, item_code, qty, uom=None):
	"""Legacy wrapper kept for Sprint 18 route compatibility."""
	set_backend_observability_context(
		module="commissary", action="update_hub_inventory", mutation_type="update"
	)
	from hrms.api.commissary import update_hub_inventory as legacy_update_hub_inventory

	return legacy_update_hub_inventory(
		hub_code=hub_code,
		item_code=item_code,
		qty=qty,
		uom=uom,
	)


@frappe.whitelist()
def check_production_feasibility(item_code, qty):
	"""Expose production feasibility on canonical requisition module path."""
	set_backend_observability_context(
		module="commissary", action="check_production_feasibility", mutation_type="read"
	)
	from hrms.api.commissary_bom import check_production_feasibility as bom_feasibility

	return bom_feasibility(item_code=item_code, qty=qty)
