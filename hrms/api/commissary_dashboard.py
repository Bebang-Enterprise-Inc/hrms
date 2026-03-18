# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Dashboard & Production Tracking APIs.
Split from commissary.py (P0-11) for maintainability.
"""

import time
from contextlib import contextmanager
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from hrms.api.commissary import get_commissary_company, get_commissary_warehouse
from hrms.utils.scm_roles import SCM_COMMISSARY_ROLES, check_scm_permission


def _enable_role_gated_write(doc: Any):
	if getattr(doc, "flags", None) is None:
		doc.flags = type("_CommissaryDashboardDocFlags", (), {})()
	doc.flags.ignore_permissions = True
	doc.flags.ignore_user_permissions = True
	return doc


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


def _rollback_savepoint(savepoint_name: str):
	rollback = getattr(getattr(frappe, "db", None), "rollback", None)
	if not callable(rollback):
		return
	try:
		rollback(save_point=savepoint_name)
	except TypeError:
		rollback()


def _release_savepoint(savepoint_name: str):
	release = getattr(getattr(frappe, "db", None), "release_savepoint", None)
	if callable(release):
		release(savepoint_name)


def _is_retryable_stock_entry_submit_error(exc: Exception) -> bool:
	message = str(exc).lower()
	return (
		"lock wait timeout exceeded" in message
		or "deadlock found" in message
		or "try restarting transaction" in message
	)

# ============================================================
# DASHBOARD / SUMMARY
# ============================================================


@frappe.whitelist()
def get_commissary_dashboard() -> dict[str, Any]:
	"""
	Get commissary supervisor dashboard summary.
	"""
	commissary_warehouse = get_commissary_warehouse()
	today_date = today()

	# Today's production (Stock Entries with type=Manufacture)
	todays_production = frappe.db.count(
		"Stock Entry",
		filters={
			"stock_entry_type": "Manufacture",
			"posting_date": today_date,
			"to_warehouse": commissary_warehouse,
		},
	)

	# Low stock alerts (items below product-specific reorder level)
	low_stock_count = (
		frappe.db.sql(
			"""
        SELECT COUNT(DISTINCT b.item_code)
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND (
            b.actual_qty <= 0
            OR (i.item_code LIKE 'FG%%' AND b.actual_qty < 7)
            OR (i.item_code NOT LIKE 'FG%%' AND b.actual_qty < IFNULL(i.safety_stock, 10))
        )
        AND i.is_stock_item = 1
    """,
			commissary_warehouse,
		)[0][0]
		or 0
	)

	# Pending store orders
	pending_orders = frappe.db.count(
		"Material Request",
		filters={
			"status": ["in", ["Pending", "Partially Ordered"]],
			"docstatus": 1,
			"material_request_type": "Material Transfer",
		},
	)

	# Today's dispatches
	todays_dispatches = frappe.db.count(
		"Stock Entry",
		filters={
			"stock_entry_type": "Material Transfer",
			"posting_date": today_date,
			"from_warehouse": commissary_warehouse,
		},
	)

	# FQI issues (last 7 days)
	fqi_issues = frappe.db.count(
		"BEI FQI Report",
		{"status": ["in", ["Open", "Under Review"]], "creation": [">=", add_days(today_date, -7)]},
	)

	# Recent production activity
	recent_production = frappe.get_all(
		"Stock Entry",
		filters={
			"stock_entry_type": "Manufacture",
			"posting_date": [">=", add_days(today_date, -3)],
			"to_warehouse": commissary_warehouse,
			"docstatus": 1,
		},
		fields=["name", "posting_date", "total_outgoing_value", "remarks"],
		order_by="posting_date desc",
		limit=5,
	)

	production_summary = frappe.db.sql(
		"""
        SELECT
            sed.item_code,
            sed.item_name,
            SUM(sed.qty) AS qty_produced,
            COALESCE(NULLIF(sed.uom, ''), i.stock_uom) AS uom
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        LEFT JOIN `tabItem` i ON i.name = sed.item_code
        WHERE se.stock_entry_type = 'Manufacture'
          AND se.posting_date = %s
          AND sed.t_warehouse = %s
          AND se.docstatus = 1
        GROUP BY sed.item_code, sed.item_name, COALESCE(NULLIF(sed.uom, ''), i.stock_uom)
        ORDER BY qty_produced DESC, sed.item_name ASC
        LIMIT 5
    """,
		(today_date, commissary_warehouse),
		as_dict=True,
	)

	# Current stock summary
	stock_summary = frappe.db.sql(
		"""
        SELECT
            COUNT(DISTINCT b.item_code) as total_items,
            SUM(b.actual_qty) as total_qty,
            SUM(b.actual_qty * IFNULL(i.valuation_rate, 0)) as total_value
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
        AND b.actual_qty > 0
    """,
		commissary_warehouse,
		as_dict=True,
	)[0]

	return {
		"success": True,
		"data": {
			"commissary_warehouse": commissary_warehouse,
			"todays_production": todays_production,
			"low_stock_count": low_stock_count,
			"low_stock_items": low_stock_count,
			"pending_orders": pending_orders,
			"todays_dispatches": todays_dispatches,
			"dispatches_today": todays_dispatches,
			"fqi_issues": fqi_issues,
			"recent_production": recent_production,
			"production_summary": production_summary,
			"stock_summary": {
				"total_items": stock_summary.get("total_items") or 0,
				"total_qty": flt(stock_summary.get("total_qty") or 0),
				"total_value": flt(stock_summary.get("total_value") or 0),
			},
		},
	}


# ============================================================
# PRODUCTION TRACKING
# ============================================================


@frappe.whitelist()
def get_production_items() -> dict[str, Any]:
	"""
	Get finished goods that commissary produces.
	Returns items with current stock levels.
	"""
	commissary_warehouse = get_commissary_warehouse()

	# P0-12: Batch query — get items + stock in one query (was N+1)
	items = frappe.db.sql(
		"""
        SELECT DISTINCT
            i.name as item_code,
            i.item_name,
            i.description,
            i.stock_uom,
            i.valuation_rate as standard_rate,
            i.item_group,
            IFNULL(b.actual_qty, 0) as current_stock
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = %s
        WHERE i.disabled = 0
        AND i.is_stock_item = 1
        AND (i.item_group = 'Finished Goods' OR b.actual_qty > 0)
        ORDER BY i.item_name
    """,
		commissary_warehouse,
		as_dict=True,
	)

	# P0-12: Batch query — get today's production for ALL items in one query (was N+1)
	today_production = frappe.db.sql(
		"""
        SELECT sed.item_code, SUM(sed.qty) as total_produced
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.stock_entry_type = 'Manufacture'
        AND se.posting_date = %s
        AND sed.t_warehouse = %s
        AND se.docstatus = 1
        GROUP BY sed.item_code
    """,
		(today(), commissary_warehouse),
		as_dict=True,
	)
	production_map = {r.item_code: flt(r.total_produced) for r in today_production}

	for item in items:
		item["current_stock"] = flt(item["current_stock"])
		item["today_produced"] = production_map.get(item["item_code"], 0.0)

	return {"success": True, "data": items}


@frappe.whitelist()
def get_runtime_deduction_proof(
	item_code: str, qty: float | int | str, warehouse: str | None = None
) -> dict[str, Any]:
	"""
	Dashboard proxy for BOM runtime deduction proof.

	Kept in dashboard API surface so UI and evidence tooling can call a stable path.
	"""
	from hrms.api.commissary_bom import get_bom_runtime_deduction_proof

	return get_bom_runtime_deduction_proof(item_code=item_code, produced_qty=qty, warehouse=warehouse)


def get_or_create_batch(batch_id: str | None, item_code: str) -> str | None:
	"""
	Get existing batch or create a new one.
	Frappe requires Batch documents to exist before referencing in Stock Entry.
	"""
	batch_id = batch_id.strip()
	if not batch_id:
		return None

	# Check if batch already exists
	if frappe.db.exists("Batch", batch_id):
		return batch_id

	# Check if item has batch tracking enabled
	has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")
	if not has_batch_no:
		return None

	# Create new batch
	batch = frappe.new_doc("Batch")
	batch.batch_id = batch_id
	batch.item = item_code
	batch.manufacturing_date = today()
	batch.insert(ignore_permissions=True)

	return batch.name


def _build_production_remarks(batch_no: str | None = None, remarks: str | None = None) -> str:
	"""Stamp production output rows with a stable prefix for downstream QA lookup."""
	base = f"Production output | Batch: {(batch_no or 'No batch').strip() if batch_no else 'No batch'}"
	if remarks and str(remarks).strip():
		return f"{base} | Notes: {str(remarks).strip()}"
	return base


@frappe.whitelist()
def submit_production_output(
	items: str | list[dict[str, Any]],
	batch_no: str | None = None,
	remarks: str | None = None,
) -> dict[str, Any]:
	"""
	Record production batch output.
	Creates Stock Entry with type=Manufacture.

	Args:
	    items: JSON array of {item_code, qty, uom}
	    batch_no: Optional batch reference (will auto-create if doesn't exist)
	    remarks: Optional production notes
	"""
	check_scm_permission(SCM_COMMISSARY_ROLES, "record commissary production output")

	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to record"))

	commissary_warehouse = get_commissary_warehouse()
	first_item_code = items[0]["item_code"] if items else None
	bom = None
	if first_item_code:
		bom = frappe.db.get_value(
			"BOM",
			{"item": first_item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
			["name", "quantity"],
			as_dict=True,
		)

	se = None
	for attempt in range(3):
		savepoint_name = f"commissary_production_{attempt}"
		savepoint = getattr(getattr(frappe, "db", None), "savepoint", None)
		if callable(savepoint):
			savepoint(savepoint_name)

		try:
			se = frappe.new_doc("Stock Entry")
			se.company = get_commissary_company()
			se.posting_date = today()
			se.posting_time = frappe.utils.nowtime()
			se.to_warehouse = commissary_warehouse
			se.remarks = _build_production_remarks(batch_no=batch_no, remarks=remarks)

			if bom:
				# Use Manufacture type - auto-deducts RM from BOM
				se.stock_entry_type = "Manufacture"
				se.from_bom = 1
				se.bom_no = bom.name
				se.fg_completed_qty = sum(flt(i["qty"]) for i in items)
				se.from_warehouse = commissary_warehouse  # RM source
				se.get_items()

				# Only add FG if not already present from BOM
				fg_already_present = any(
					item.item_code == first_item_code and item.is_finished_item for item in se.items
				)
				item = frappe.get_doc("Item", first_item_code)
				if not fg_already_present:
					fg_row = se.append(
						"items",
						{
							"item_code": first_item_code,
							"item_name": item.item_name,
							"description": item.description,
							"qty": se.fg_completed_qty,
							"uom": item.stock_uom,
							"stock_uom": item.stock_uom,
							"conversion_factor": 1,
							"t_warehouse": commissary_warehouse,
							"is_finished_item": 1,
							"is_scrap_item": 0,
						},
					)
				else:
					# Get reference to the existing FG row for batch assignment below
					fg_row = next(
						i for i in se.items if i.item_code == first_item_code and i.is_finished_item
					)

				# Override batch on FG if provided
				if batch_no and batch_no.strip():
					valid_batch = get_or_create_batch(batch_no, first_item_code)
					if valid_batch:
						fg_row.batch_no = valid_batch
			else:
				# Fallback: Material Receipt (no RM deduction)
				se.stock_entry_type = "Material Receipt"

				for item_data in items:
					item = frappe.get_doc("Item", item_data["item_code"])

					item_row = {
						"item_code": item_data["item_code"],
						"item_name": item.item_name,
						"description": item.description,
						"qty": flt(item_data["qty"]),
						"uom": item_data.get("uom") or item.stock_uom,
						"stock_uom": item.stock_uom,
						"conversion_factor": 1,
						"t_warehouse": commissary_warehouse,
					}
					if batch_no and batch_no.strip():
						valid_batch = get_or_create_batch(batch_no, item_data["item_code"])
						if valid_batch:
							item_row["batch_no"] = valid_batch
					se.append("items", item_row)

			_enable_role_gated_write(se)
			with _run_as_system_user():
				se.insert(ignore_permissions=True)
				se = frappe.get_doc("Stock Entry", se.name)
				_enable_role_gated_write(se)
				se.submit()

			_release_savepoint(savepoint_name)
			break
		except Exception as exc:
			_rollback_savepoint(savepoint_name)
			if attempt == 2 or not _is_retryable_stock_entry_submit_error(exc):
				raise
			time.sleep(0.2 * (attempt + 1))

	# G-051: FEFO warnings — check if older batches were skipped
	fefo_warnings = _check_fefo_warnings(se, commissary_warehouse)

	result = {
		"success": True,
		"data": {"name": se.name, "total_qty": sum(i.qty for i in se.items), "items_count": len(se.items)},
		"message": f"Production recorded: {se.name}",
	}
	if fefo_warnings:
		result["fefo_warnings"] = fefo_warnings
	return result


def _check_fefo_warnings(stock_entry: Any, warehouse: str | None) -> list[dict[str, str]]:
	"""G-051: Check if any items in the Stock Entry used a newer batch when older ones exist."""
	warnings = []
	for item in stock_entry.items:
		if not item.batch_no or not item.s_warehouse:
			continue
		# Find oldest available batch for this item
		oldest = frappe.db.sql(
			"""
            SELECT b.name, b.expiry_date
            FROM `tabBatch` b
            JOIN `tabStock Ledger Entry` sle ON sle.batch_no = b.name
            WHERE sle.item_code = %s AND sle.warehouse = %s
            AND b.expiry_date IS NOT NULL AND b.expiry_date > CURDATE()
            GROUP BY b.name HAVING SUM(sle.actual_qty) > 0
            ORDER BY b.expiry_date ASC LIMIT 1
        """,
			(item.item_code, item.s_warehouse),
			as_dict=True,
		)

		if oldest and oldest[0].name != item.batch_no:
			used_expiry = frappe.db.get_value("Batch", item.batch_no, "expiry_date")
			if used_expiry and oldest[0].expiry_date and used_expiry > oldest[0].expiry_date:
				warnings.append(
					{
						"item_code": item.item_code,
						"used_batch": item.batch_no,
						"used_expiry": str(used_expiry),
						"older_batch": oldest[0].name,
						"older_expiry": str(oldest[0].expiry_date),
					}
				)
	return warnings


@frappe.whitelist()
def get_production_history(
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
) -> dict[str, Any]:
	"""
	Get production history.
	"""
	commissary_warehouse = get_commissary_warehouse()

	filters = {
		"stock_entry_type": ["in", ["Manufacture", "Material Receipt"]],
		"to_warehouse": commissary_warehouse,
		"docstatus": 1,
	}

	if date_from and date_to:
		filters["posting_date"] = ["between", [date_from, date_to]]
	elif date_from:
		filters["posting_date"] = [">=", date_from]
	elif date_to:
		filters["posting_date"] = ["<=", date_to]

	entries = frappe.get_all(
		"Stock Entry",
		filters=filters,
		fields=["name", "posting_date", "remarks", "owner"],
		order_by="posting_date desc",
		limit=int(limit),
	)

	# Add item details for each entry
	for entry in entries:
		items = frappe.get_all(
			"Stock Entry Detail",
			filters={"parent": entry["name"]},
			fields=["item_code", "item_name", "qty", "uom"],
		)
		entry["items"] = items
		entry["total_qty"] = sum(i.get("qty", 0) for i in items)
		entry["items_count"] = len(items)

	return {"success": True, "data": entries}


@frappe.whitelist()
def get_production_cost_per_batch(limit: int | str = 20, item_code: str | None = None) -> dict[str, Any]:
	"""
	Return production cost per batch from submitted Manufacture entries.

	Current costing model:
	- material_cost: Stock Entry total_outgoing_value
	- labor_cost: 0 (placeholder for future payroll integration)
	- overhead_cost: 0 (placeholder for future allocation model)
	"""
	try:
		limit_value = max(1, int(limit))
	except (TypeError, ValueError):
		limit_value = 20

	params = []
	item_filter_sql = ""
	if item_code:
		item_filter_sql = "AND sed.item_code = %s"
		params.append(item_code)

	params.append(limit_value)

	rows = frappe.db.sql(
		f"""
        SELECT
            se.name as batch_id,
            se.posting_date,
            IFNULL(MAX(CASE WHEN sed.is_finished_item = 1 THEN sed.item_code END), "") as item_code,
            IFNULL(MAX(CASE WHEN sed.is_finished_item = 1 THEN sed.item_name END), "") as item_name,
            ABS(IFNULL(se.total_outgoing_value, 0)) as material_cost,
            0 as labor_cost,
            0 as overhead_cost
        FROM `tabStock Entry` se
        LEFT JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
          AND se.stock_entry_type = 'Manufacture'
          {item_filter_sql}
        GROUP BY se.name, se.posting_date, se.total_outgoing_value
        ORDER BY se.posting_date DESC, se.creation DESC
        LIMIT %s
        """,
		tuple(params),
		as_dict=True,
	)

	data = []
	for row in rows:
		material_cost = flt(row.get("material_cost") or 0)
		labor_cost = flt(row.get("labor_cost") or 0)
		overhead_cost = flt(row.get("overhead_cost") or 0)
		total_cost = material_cost + labor_cost + overhead_cost

		data.append(
			{
				"batch_id": row.get("batch_id"),
				"posting_date": row.get("posting_date"),
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"material_cost": material_cost,
				"labor_cost": labor_cost,
				"overhead_cost": overhead_cost,
				"total_cost": total_cost,
			}
		)

	return {
		"success": True,
		"data": data,
		"summary": {
			"batches": len(data),
			"total_material_cost": sum(d["material_cost"] for d in data),
			"total_cost": sum(d["total_cost"] for d in data),
		},
	}


@frappe.whitelist()
def get_logistics_architecture_mode(route_name: str | None = None) -> dict[str, Any]:
	"""
	Return current logistics architecture mode (`hub` or `direct`).

	If route_name is provided and exists, mode is resolved from that BEI Route.
	Fallback mode is `hub`.
	"""
	mode = "hub"
	route_hint = "Hub-and-spoke mode: transfers route through designated hubs."

	if route_name and frappe.db.exists("BEI Route", route_name):
		route = frappe.get_doc("BEI Route", route_name)
		if hasattr(route, "resolve_architecture_mode"):
			mode = route.resolve_architecture_mode()
		else:
			notes = (getattr(route, "notes", "") or "").lower()
			mode = "direct" if "mode:direct" in notes else "hub"
		if hasattr(route, "architecture_hint"):
			route_hint = route.architecture_hint()
		elif mode == "direct":
			route_hint = "Direct store dispatch mode: transfers bypass external hubs."

	return {
		"success": True,
		"data": {
			"architecture_mode": mode,
			"available_modes": ["hub", "direct"],
			"hint": route_hint,
			"route_name": route_name,
		},
	}
