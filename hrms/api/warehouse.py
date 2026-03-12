# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Warehouse Supervisor APIs
Handles PO receiving, Material Request approval, and stock transfers for Ian.

Author: Claude Code
Date: 2026-02-02
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from hrms.utils.bei_config import get_company
from hrms.utils.scm_roles import SCM_APPROVAL_ROLES, check_scm_permission
from hrms.utils.supply_chain_contracts import (
	CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
	FINANCE_TREATMENT_SAME_COMPANY,
	REQUEST_SOURCE_COMMISSARY_FG_TRANSFER,
	REQUEST_SOURCE_STORE_ORDER,
	TEST_COMMISSARY_OPERATION_WAREHOUSE,
	get_request_source_label,
	get_preferred_commissary_warehouses,
	infer_finance_treatment,
	resolve_material_request_contract,
	resolve_warehouse_company,
	stamp_stock_entry_contract,
	strip_company_suffix,
)

# ============================================================
# 1. SUPPLIER RECEIVING
# ============================================================


def _row_value(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


def _ensure_warehouse_receiving_doctype():
	if not frappe.db.exists("DocType", "BEI Warehouse Receiving"):
		frappe.throw(_("BEI Warehouse Receiving DocType is not installed"))


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
def create_purchase_receipt(po_name, items, remarks=None):
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

	if not frappe.db.exists("Purchase Order", po_name):
		frappe.throw(_("Purchase Order not found"))

	po = frappe.get_doc("Purchase Order", po_name)

	# Create Purchase Receipt
	pr = frappe.new_doc("Purchase Receipt")
	pr.supplier = po.supplier
	pr.supplier_name = po.supplier_name
	pr.company = po.company
	pr.posting_date = frappe.utils.today()
	pr.posting_time = frappe.utils.nowtime()
	pr.remarks = remarks or f"Received against {po_name}"

	# Add items
	for item_data in items:
		# Find matching PO item
		po_item = next((i for i in po.items if i.item_code == item_data["item_code"]), None)
		if not po_item:
			continue

		received_qty = item_data.get("received_qty", 0)
		if received_qty <= 0:
			continue

		pr.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": po_item.item_name,
				"description": po_item.description,
				"qty": received_qty,
				"rejected_qty": item_data.get("rejected_qty", 0),
				"uom": po_item.uom,
				"stock_uom": po_item.stock_uom,
				"conversion_factor": po_item.conversion_factor or 1,
				"rate": po_item.rate,
				"warehouse": item_data.get("warehouse") or po_item.warehouse,
				"purchase_order": po_name,
				"purchase_order_item": po_item.name,
			},
		)

	if not pr.items:
		frappe.throw(_("No items to receive"))

	pr.insert()
	pr.submit()

	return {
		"success": True,
		"data": {"name": pr.name, "grand_total": pr.grand_total, "items_count": len(pr.items)},
		"message": f"Purchase Receipt {pr.name} created successfully",
	}


@frappe.whitelist()
def get_internal_receiving_warehouses():
	"""List active BKI warehouses that can receive commissary finished goods."""
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

	warehouses = frappe.get_all(
		"Warehouse",
		filters={"is_group": 0},
		fields=["name", "warehouse_name", "company"],
		order_by="warehouse_name asc",
	)

	filtered = []
	for warehouse in warehouses:
		company = warehouse.get("company") or resolve_warehouse_company(warehouse.get("name"))
		name = warehouse.get("name") or ""
		if company != "Bebang Kitchen Inc.":
			continue
		if name in excluded_warehouses:
			continue
		filtered.append(
			{
				"name": name,
				"label": warehouse.get("warehouse_name") or strip_company_suffix(name),
				"company": company,
			}
		)

	return {"success": True, "data": filtered}


@frappe.whitelist()
def create_warehouse_receiving(
	source_warehouse,
	target_warehouse,
	items,
	linked_quality_inspection=None,
	linked_production_entry=None,
	remarks=None,
):
	"""Create a pending warehouse inbound record for commissary finished goods."""
	_ensure_warehouse_receiving_doctype()

	if isinstance(items, str):
		items = json.loads(items)

	if not source_warehouse or not target_warehouse:
		frappe.throw(_("source_warehouse and target_warehouse are required"))
	if not items:
		frappe.throw(_("No items to hand off"))

	source_company = resolve_warehouse_company(source_warehouse)
	target_company = resolve_warehouse_company(target_warehouse)
	if source_company != "Bebang Kitchen Inc." or target_company != "Bebang Kitchen Inc.":
		frappe.throw(_("Commissary warehouse handoff must stay within Bebang Kitchen Inc. warehouses"))

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
		doc.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": item_doc.item_name,
				"batch_no": item_data.get("batch_no"),
				"uom": item_data.get("uom") or item_doc.stock_uom,
				"expected_qty": qty,
				"received_qty": 0,
				"rejected_qty": 0,
				"accepted_qty": 0,
				"issue_notes": item_data.get("issue_notes"),
			},
		)

	if not doc.items:
		frappe.throw(_("No valid finished goods items to hand off"))

	doc.insert(ignore_permissions=True)

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
def complete_warehouse_receiving(receiving_name, items, remarks=None):
	"""Complete warehouse receipt for a commissary FG handoff by creating the stock transfer."""
	_ensure_warehouse_receiving_doctype()

	if isinstance(items, str):
		items = json.loads(items)

	if not frappe.db.exists("BEI Warehouse Receiving", receiving_name):
		frappe.throw(_("Warehouse receiving record not found"))

	receiving = frappe.get_doc("BEI Warehouse Receiving", receiving_name)
	if receiving.status == "Completed" and receiving.stock_entry:
		return {
			"success": True,
			"data": {"name": receiving.stock_entry, "receiving_name": receiving.name},
			"message": f"Warehouse receiving {receiving.name} already completed",
		}

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
		frappe.throw(_("No accepted quantity to receive into warehouse"))

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = "Material Transfer"
	stock_entry.company = resolve_warehouse_company(receiving.source_warehouse) or get_company()
	stock_entry.posting_date = frappe.utils.today()
	stock_entry.posting_time = frappe.utils.nowtime()
	stock_entry.from_warehouse = receiving.source_warehouse
	stock_entry.to_warehouse = receiving.target_warehouse
	stock_entry.remarks = remarks or f"Warehouse receiving {receiving.name}"
	stamp_stock_entry_contract(
		stock_entry,
		request_source=REQUEST_SOURCE_COMMISSARY_FG_TRANSFER,
		cargo_lane="FG",
		source_company=resolve_warehouse_company(receiving.source_warehouse),
		target_company=resolve_warehouse_company(receiving.target_warehouse),
		finance_treatment=FINANCE_TREATMENT_SAME_COMPANY,
	)

	for item_data in accepted_items:
		item_doc = frappe.get_doc("Item", item_data["item_code"])
		stock_entry.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": item_doc.item_name,
				"description": item_doc.description,
				"qty": item_data["qty"],
				"uom": item_data.get("uom") or item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": receiving.source_warehouse,
				"t_warehouse": receiving.target_warehouse,
				"batch_no": item_data.get("batch_no"),
			},
		)

	stock_entry.insert(ignore_permissions=True)
	stock_entry.submit()

	receiving.stock_entry = stock_entry.name
	receiving.receiving_date = now_datetime()
	receiving.received_by_user = frappe.session.user
	receiving.remarks = remarks or receiving.remarks
	receiving.status = "With Issues" if has_issues else "Completed"
	receiving.save(ignore_permissions=True)

	return {
		"success": True,
		"data": {
			"name": stock_entry.name,
			"receiving_name": receiving.name,
			"items_count": len(stock_entry.items),
			"total_qty": sum(flt(item.qty) for item in stock_entry.items),
		},
		"message": f"Warehouse receiving {receiving.name} completed successfully",
	}


# ============================================================
# 2. MATERIAL REQUEST APPROVAL
# ============================================================


@frappe.whitelist()
def get_pending_material_requests():
	"""
	Get Material Requests pending approval/fulfillment.
	"""
	mrs = frappe.get_all(
		"Material Request",
		filters={
			"status": ["in", ["Pending", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": "Material Transfer",
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
def get_material_request_items(mr_name):
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
		item["from_warehouse"] = from_warehouse
		bin_qty = 0
		if from_warehouse:
			bin_qty = (
				frappe.db.get_value(
					"Bin", {"item_code": item["item_code"], "warehouse": from_warehouse}, "actual_qty"
				)
				or 0
			)
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
	check_scm_permission(SCM_APPROVAL_ROLES, "approve material requests")

	if not mr_name or not approved_items:
		frappe.throw(_("Missing required parameters: mr_name, approved_items"), frappe.ValidationError)
	if isinstance(approved_items, str):
		approved_items = json.loads(approved_items)

	if not frappe.db.exists("Material Request", mr_name):
		frappe.throw(_("Material Request not found"))

	# G-102: Row lock to prevent double-approval race condition
	current_status = frappe.db.sql(
		"SELECT status FROM `tabMaterial Request` WHERE name = %s FOR UPDATE", mr_name
	)[0][0]
	if current_status == "Ordered":
		frappe.throw(_("Material Request {0} has already been approved").format(mr_name))

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
	mrs = frappe.get_all(
		"Material Request",
		filters={
			"status": ["in", ["Ordered", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": "Material Transfer",
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


@frappe.whitelist()
def create_stock_transfer(source_warehouse, target_warehouse, items, mr_name=None, remarks=None):
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
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.company = contract.get("source_company") or default_source_company
	se.posting_date = frappe.utils.today()
	se.posting_time = frappe.utils.nowtime()
	se.from_warehouse = source_warehouse
	se.to_warehouse = target_warehouse
	se.remarks = remarks or f"Transfer to {target_warehouse}"
	stamp_stock_entry_contract(
		se,
		request_source=contract["request_source"],
		cargo_lane=contract.get("cargo_lane"),
		source_company=contract.get("source_company") or default_source_company,
		target_company=contract.get("target_company") or default_target_company,
		finance_treatment=contract.get("finance_treatment"),
	)

	# Add items
	normalized_items = []
	for item_data in items:
		qty_value = item_data.get("qty", item_data.get("quantity"))
		if qty_value is None:
			frappe.throw(_("Missing quantity for item {0}").format(item_data.get("item_code", "unknown")))
		item_data["qty"] = flt(qty_value)
		normalized_items.append(item_data)

	for item_data in normalized_items:
		# Get item details
		item = frappe.get_doc("Item", item_data["item_code"])

		# Bug fix B9-002: Handle batch_no for batch-tracked items
		batch_no = item_data.get("batch_no")
		if item.has_batch_no and not batch_no:
			# Auto-select oldest batch with sufficient stock
			oldest_batch = frappe.db.get_value(
				"Batch",
				{"item": item_data["item_code"], "batch_qty": [">", 0]},
				"name",
				order_by="creation asc",
			)
			batch_no = oldest_batch

		# Bug fix B9-001: Set material_request and material_request_item properly
		mr_item_ref = item_data.get("mr_item_name")
		if not mr_item_ref and mr_name:
			mr_item_ref = mr_items_map.get(item_data["item_code"])

		se.append(
			"items",
			{
				"item_code": item_data["item_code"],
				"item_name": item.item_name,
				"description": item.description,
				"qty": item_data["qty"],
				"uom": item_data.get("uom") or item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": source_warehouse,
				"t_warehouse": target_warehouse,
				"batch_no": batch_no,
				"material_request": mr_name if mr_item_ref else None,
				"material_request_item": mr_item_ref,
			},
		)

	if not se.items:
		frappe.throw(_("No items to transfer"))

	se.insert()
	se.submit()

	return {
		"success": True,
		"data": {
			"name": se.name,
			"total_qty": sum(i.qty for i in se.items),
			"items_count": len(se.items),
			"movement_type": "Material Transfer",
			"source_warehouse": source_warehouse,
			"target_warehouse": target_warehouse,
			"request_source": contract["request_source"],
			"request_source_label": get_request_source_label(contract["request_source"]),
			"cargo_lane": contract.get("cargo_lane"),
			"finance_treatment": contract.get("finance_treatment"),
		},
		"message": f"Stock Transfer {se.name} created successfully",
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
			"material_request_type": "Material Transfer",
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
