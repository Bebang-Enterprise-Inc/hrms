# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
BEI Store Ordering API
Handles store order submission, approval, and delivery receipt generation for my.bebang.ph
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import get_time, getdate, now, now_datetime, nowdate, today

# P0-10: Import centralized RBAC role sets
from hrms.utils.scm_roles import ORDERING_APPROVAL_ROLES, ORDERING_STORE_ROLES, ORDERING_WAREHOUSE_ROLES
from hrms.utils.scm_roles import check_scm_permission as _check_ordering_permission
from hrms.utils.sentry import set_backend_observability_context


def _normalize_submit_items(items: Any) -> list[dict[str, Any]]:
	"""S019 compatibility: accept reason_for_edit alias and recommended_qty payloads."""
	if isinstance(items, str):
		items = frappe.parse_json(items)
	normalized = []
	for row in items or []:
		normalized.append(
			{
				"item_code": row.get("item_code"),
				"qty_requested": row.get("qty_requested", 0),
				"recommended_qty": row.get("recommended_qty", row.get("suggested_qty", 0)),
				"suggested_qty": row.get("suggested_qty", row.get("recommended_qty", 0)),
				"deviation_reason": row.get("deviation_reason") or row.get("reason_for_edit") or "",
				"reason_for_edit": row.get("reason_for_edit") or row.get("deviation_reason") or "",
				"available_to_promise": row.get("available_to_promise", 0),
				"forecast_demand": row.get("forecast_demand", 0),
				"safety_buffer": row.get("safety_buffer", 0),
				"risk_rank": row.get("risk_rank", 4),
				"lane": row.get("lane"),
			}
		)
	return normalized


def _get_suggested_qty(store: str, item_code: str) -> float:
	"""
	Compute suggested qty: AVG(qty_requested) from last 3 BEI Store Orders
	for this store+item, multiplied by 1.2 safety factor.
	Returns 0 if no history exists.
	"""
	result = frappe.db.sql(
		"""
        SELECT AVG(soi.qty_requested) as avg_qty
        FROM `tabBEI Store Order Item` soi
        INNER JOIN `tabBEI Store Order` so ON soi.parent = so.name
        WHERE so.store = %s
          AND soi.item_code = %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Cancelled')
        ORDER BY so.order_date DESC
        LIMIT 3
    """,
		(store, item_code),
		as_dict=True,
	)

	if result and result[0].avg_qty:
		return round(result[0].avg_qty * 1.2, 3)
	return 0.0


def _get_last_order_qty(store: str, item_code: str) -> float:
	"""Get qty_requested from the most recent order for this store+item."""
	result = frappe.db.sql(
		"""
        SELECT soi.qty_requested
        FROM `tabBEI Store Order Item` soi
        INNER JOIN `tabBEI Store Order` so ON soi.parent = so.name
        WHERE so.store = %s
          AND soi.item_code = %s
          AND so.docstatus = 1
        ORDER BY so.order_date DESC
        LIMIT 1
    """,
		(store, item_code),
		as_dict=True,
	)

	return result[0].qty_requested if result else 0.0


@frappe.whitelist()
def get_orderable_items(store: str, date: str | None = None) -> dict[str, Any]:
	"""DEPRECATED: Use hrms.api.store.get_orderable_items instead."""
	frappe.logger("ordering").warning(
		"ordering.get_orderable_items is deprecated. Use store.get_orderable_items."
	)
	from hrms.api.store import get_orderable_items as canonical_get_orderable_items

	return canonical_get_orderable_items(store=store, date=date)


@frappe.whitelist()
def validate_order_schedule(store: str, date: str | None = None) -> dict[str, Any]:
	"""DEPRECATED: Use hrms.api.store.validate_order_schedule instead."""
	frappe.logger("ordering").warning(
		"ordering.validate_order_schedule is deprecated. Use store.validate_order_schedule."
	)
	from hrms.api.store import validate_order_schedule as canonical_validate

	return canonical_validate(store=store, date=date)


@frappe.whitelist()
def submit_order(
	store: str,
	items: Any,
	cargo_category: str | None = None,
	delivery_date: str | None = None,
	is_emergency: int = 0,
	notes: str = "",
) -> dict[str, Any]:
	"""DEPRECATED: Use hrms.api.store.submit_order instead."""
	frappe.logger("ordering").warning("ordering.submit_order is deprecated. Use store.submit_order.")
	from hrms.api.store import submit_order as canonical_submit

	normalized_items = _normalize_submit_items(items)
	return canonical_submit(
		store=store,
		items=normalized_items,
		cargo_category=cargo_category,
		delivery_date=delivery_date,
		is_emergency=is_emergency,
		notes=notes,
	)


def _generate_dr_internal(order_name: str, order: Any = None) -> dict[str, Any]:
	"""
	Internal DR generation without permission check.
	Called from approve_order() which already verified permissions.
	"""
	if not order:
		order = frappe.get_doc("BEI Store Order", order_name)

	# Generate DR number: DR + 7-digit auto-increment
	# S093: Generate DR number from BEI Store Order (BEI Delivery Receipt DocType doesn't exist)
	try:
		result = frappe.db.sql(
			"SELECT MAX(CAST(SUBSTRING(dr_number, 3) AS UNSIGNED)) "
			"FROM `tabBEI Store Order` WHERE dr_number IS NOT NULL AND dr_number != ''"
		)
		last_num = result[0][0] if result and result[0][0] else 0
	except Exception:
		last_num = 0

	dr_number = f"DR{last_num + 1:07d}"

	# S093: Store DR linkage on the order itself
	trip_stop_name = getattr(order, "trip_stop", None) or ""
	frappe.db.set_value(
		"BEI Store Order",
		order_name,
		{
			"dr_number": dr_number,
			"trip_stop": trip_stop_name,
		},
	)

	# Log the DR generation as a comment on the order
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "BEI Store Order",
			"reference_name": order_name,
			"content": _("Delivery Receipt generated: {0}").format(dr_number),
		}
	).insert(ignore_permissions=True)

	# Send GChat notification to store (pattern from dispatch.py)
	try:
		_send_order_notification(
			store=order.store,
			message=_(
				"Delivery Receipt {0} has been generated for your order {1}. Delivery scheduled for {2}."
			).format(dr_number, order_name, order.delivery_date or "TBD"),
		)
	except Exception as e:
		frappe.log_error(f"GChat notification failed for DR {dr_number}: {e}", "Ordering API")

	return {
		"dr_number": dr_number,
		"items_count": len(order.items),
		"trip_stop": trip_stop_name,
	}


@frappe.whitelist()
def generate_dr(order_name: str) -> dict[str, Any]:
	"""
	Generate a Delivery Receipt for an approved order.

	Args:
	    order_name (str): BEI Store Order name

	Returns:
	    dict: {"dr_number": str, "items_count": int}
	"""
	_check_ordering_permission(ORDERING_WAREHOUSE_ROLES, "generate delivery receipt")

	order = frappe.get_doc("BEI Store Order", order_name)

	if order.status != "Approved":
		frappe.throw(
			_("Cannot generate DR for order {0} — status is '{1}', must be 'Approved'").format(
				order_name, order.status
			)
		)

	return _generate_dr_internal(order_name, order)


@frappe.whitelist()
def get_order_review_queue(date: str | None = None, status: str | None = None) -> dict[str, Any]:
	"""
	Get all BEI Store Orders for review, optionally filtered by date and status.

	Args:
	    date (str, optional): Filter by order_date. Empty string or None => no date filter
	        (show all dates). S223 DEFECT-11 fix: previously defaulted to today which
	        narrowed the queue and hid orders submitted with delivery dates ≠ today.
	    status (str, optional): Filter by status

	Returns:
	    dict: {"orders": [...], "total": int}
	"""
	set_backend_observability_context(
		module="ordering",
		action="get_order_review_queue",
		mutation_type="read",
	)
	_check_ordering_permission(ORDERING_WAREHOUSE_ROLES, "view order review queue")

	# S223 DEFECT-11: empty/None date means "no date filter" — see SQL clause below.
	# Treat empty string as None so the SQL `(%(date)s IS NULL OR ...)` short-circuits.
	filter_date = (date or "").strip() or None
	current_user = frappe.session.user
	current_roles = set(frappe.get_roles(current_user))
	from hrms.api.store import _get_order_approval_fallback_user

	fallback_approver = _get_order_approval_fallback_user()
	params = {
		"date": filter_date,
		"current_user": current_user,
		"fallback_user": fallback_approver or "",
		"status": status or None,
	}

	admin_viewer_roles = {"System Manager", "Administrator", "Supply Chain Manager", "Warehouse Manager"}
	is_fallback_viewer = bool(fallback_approver and current_user == fallback_approver)
	is_admin_viewer = bool(current_roles.intersection(admin_viewer_roles)) or is_fallback_viewer
	params["is_admin_viewer"] = 1 if is_admin_viewer else 0

	orders = frappe.db.sql(
		"""
		SELECT
			so.name,
			so.store,
			so.order_date,
			so.delivery_date,
			so.cargo_category,
			so.status,
			so.is_bulk_order,
			so.is_emergency,
			so.submitted_by,
			pending_queue.queue_name AS approval_queue_name,
			pending_queue.assigned_approver AS current_approver,
			pending_queue.pending_since AS pending_since,
			CASE
				WHEN %(fallback_user)s != ''
					AND pending_queue.assigned_approver = %(fallback_user)s
					THEN 'Fallback Approval Review'
				ELSE 'Area Supervisor Review'
			END AS approval_stage,
			COUNT(soi.name) as items_count,
			SUM(soi.amount) as total_amount,
			SUM(CASE WHEN COALESCE(soi.is_edited, 0) = 1 OR COALESCE(soi.deviation_pct, 0) != 0 THEN 1 ELSE 0 END) as deviation_count
		FROM `tabBEI Store Order` so
		LEFT JOIN (
			SELECT
				q.reference_name,
				SUBSTRING_INDEX(GROUP_CONCAT(q.name ORDER BY q.creation ASC), ',', 1) AS queue_name,
				SUBSTRING_INDEX(GROUP_CONCAT(q.assigned_approver ORDER BY q.creation ASC), ',', 1) AS assigned_approver,
				MIN(q.submitted_at) AS pending_since
			FROM `tabBEI Approval Queue` q
			WHERE q.reference_doctype = 'BEI Store Order'
			  AND q.status = 'Pending'
			GROUP BY q.reference_name
		) pending_queue ON pending_queue.reference_name = so.name
		LEFT JOIN `tabWarehouse` wh ON wh.name = so.store
		LEFT JOIN `tabWarehouse` wh_parent ON wh_parent.name = wh.parent_warehouse
		LEFT JOIN `tabBEI Store Order Item` soi ON soi.parent = so.name
		WHERE (%(date)s IS NULL OR so.order_date = %(date)s)
		  AND so.docstatus < 2
		  AND (%(status)s IS NULL OR so.status = %(status)s)
		  AND (
			%(is_admin_viewer)s = 1
			OR so.status != 'Pending Approval'
			OR pending_queue.assigned_approver = %(current_user)s
		  )
		GROUP BY so.name
		ORDER BY
			CASE so.status WHEN 'Pending Approval' THEN 0 ELSE 1 END,
			COALESCE(pending_queue.pending_since, so.creation) ASC,
			so.store ASC
		""",
		params,
		as_dict=True,
	)

	return {
		"orders": orders,
		"total": len(orders),
	}


@frappe.whitelist()
def approve_order(order_name: str, adjustments: Any = None) -> dict[str, Any]:
	"""DEPRECATED: Use hrms.api.store.approve_order instead."""
	frappe.logger("ordering").warning("ordering.approve_order is deprecated. Use store.approve_order.")
	from hrms.api.store import approve_order as canonical_approve

	return canonical_approve(order_name=order_name, approved_quantities=adjustments)


@frappe.whitelist()
def reject_order(order_name: str, reason: str) -> dict[str, str]:
	"""
	Reject a pending store order.

	Args:
	    order_name (str): BEI Store Order name
	    reason (str): Rejection reason

	Returns:
	    dict: {"status": "Cancelled"}
	"""
	_check_ordering_permission(ORDERING_APPROVAL_ROLES, "reject orders")

	if not reason:
		frappe.throw(_("A rejection reason is required"))

	order = frappe.get_doc("BEI Store Order", order_name)

	if order.status != "Pending Approval":
		frappe.throw(
			_("Cannot reject order {0} — status is '{1}', must be 'Pending Approval'").format(
				order_name, order.status
			)
		)

	order.status = "Cancelled"
	order.save(ignore_permissions=True)

	pending_queue_rows = frappe.get_all(
		"BEI Approval Queue",
		filters={
			"reference_doctype": "BEI Store Order",
			"reference_name": order_name,
			"status": "Pending",
		},
		fields=["name", "assigned_approver"],
	)
	for row in pending_queue_rows:
		queue_doc = frappe.get_doc("BEI Approval Queue", row.name)
		queue_doc.status = "Rejected"
		queue_doc.approved_by = frappe.session.user
		queue_doc.approved_at = now_datetime()
		queue_doc.rejection_reason = reason
		queue_doc.save(ignore_permissions=True)

	try:
		todo_rows = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": "BEI Store Order",
				"reference_name": order_name,
				"status": "Open",
			},
			fields=["name"],
		)
		for row in todo_rows:
			todo_doc = frappe.get_doc("ToDo", row.name)
			todo_doc.status = "Closed"
			todo_doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			f"Failed to close ToDo assignments for cancelled order {order_name}",
			"Store Ordering Reject ToDo Close Error",
		)

	# Add comment with rejection reason
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "BEI Store Order",
			"reference_name": order_name,
			"content": _("Order rejected by {0}. Reason: {1}").format(frappe.session.user, reason),
		}
	).insert(ignore_permissions=True)

	# Send GChat notification to store
	try:
		store_name = order.store
		_send_order_notification(
			store=store_name, message=_("Your order {0} was rejected: {1}").format(order_name, reason)
		)
	except Exception as e:
		frappe.log_error(f"GChat notification failed for rejected order {order_name}: {e}", "Ordering API")

	return {"status": "Cancelled"}


def _send_order_notification(store: str, message: str) -> None:
	"""
	Send a GChat notification to the store.
	Pattern follows dispatch.py _send_delivery_notification.
	Silently fails if Google Chat integration is not configured.
	"""
	try:
		from hrms.api.google_chat import resolve_store_chat_space, send_message_to_space

		# Look up store's notification space from Warehouse custom fields or config
		space_id = resolve_store_chat_space(store)
		if space_id:
			send_message_to_space(space_id, message)
	except ImportError:
		# Google Chat module not available — log and skip
		frappe.log_error(f"GChat not configured. Skipped notification for store {store}", "Ordering API")
	except Exception as e:
		frappe.log_error(str(e), "Order Notification Error")
