"""HR Personnel Action API.

Dedicated HR-only workflow for promotion, inter-department transfer,
designation updates, and compensation changes.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt, getdate, now_datetime

DOCTYPE_PERSONNEL_ACTION = "BEI HR Personnel Action"
DOCTYPE_COMPENSATION_ROW = "BEI HR Personnel Action Compensation"
HR_PERSONNEL_ACTION_ROLES = {"HR User", "HR Manager", "System Manager"}


def _has_hr_personnel_action_role(user: str | None = None) -> bool:
	active_user = user or frappe.session.user
	if active_user == "Administrator":
		return True
	return bool(set(frappe.get_roles(active_user)).intersection(HR_PERSONNEL_ACTION_ROLES))


def _require_hr_personnel_action_role():
	if not _has_hr_personnel_action_role():
		frappe.throw(
			_("Only HR users can create or approve personnel actions"),
			frappe.PermissionError,
		)


def _parse_compensation_rows(compensation_rows: Any) -> list[dict[str, Any]]:
	if not compensation_rows:
		return []

	rows_payload = compensation_rows
	if isinstance(compensation_rows, str):
		try:
			rows_payload = json.loads(compensation_rows)
		except Exception:
			frappe.throw(_("Compensation rows must be valid JSON"))

	if not isinstance(rows_payload, list):
		frappe.throw(_("Compensation rows must be a list"))

	rows: list[dict[str, Any]] = []
	for raw in rows_payload:
		if not isinstance(raw, dict):
			continue

		component = (raw.get("component") or "").strip()
		if not component:
			continue

		row = {
			"doctype": DOCTYPE_COMPENSATION_ROW,
			"component": component,
			"from_amount": flt(raw.get("from_amount") or 0),
			"to_amount": flt(raw.get("to_amount") or 0),
			"include_in_total": cint(raw.get("include_in_total") if raw.get("include_in_total") is not None else 1),
			"notes": (raw.get("notes") or "").strip(),
		}
		rows.append(row)
	return rows


def _build_employee_snapshot(employee_id: str) -> dict[str, Any]:
	employee = frappe.get_doc("Employee", employee_id)
	return {
		"employee_name": employee.employee_name,
		"from_branch": employee.branch,
		"from_department": employee.department,
		"from_designation": employee.designation,
		"from_reports_to": employee.reports_to,
	}


def _apply_employee_master_change(doc):
	employee = frappe.get_doc("Employee", doc.employee)
	updated = False

	updates = {
		"branch": doc.to_branch,
		"department": doc.to_department,
		"designation": doc.to_designation,
		"reports_to": doc.to_reports_to,
	}

	for fieldname, value in updates.items():
		if value and getattr(employee, fieldname, None) != value:
			setattr(employee, fieldname, value)
			updated = True

	if updated:
		employee.save(ignore_permissions=True)

	return {"updated": updated, "employee": employee.name}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def create_personnel_action(
	employee,
	effective_date,
	reason,
	action_type="Promotion",
	to_branch=None,
	to_department=None,
	to_designation=None,
	to_reports_to=None,
	salary_old=None,
	salary_new=None,
	compensation_rows=None,
):
	_require_hr_personnel_action_role()

	if not employee:
		frappe.throw(_("Employee is required"))
	if not effective_date:
		frappe.throw(_("Effective date is required"))
	if not reason:
		frappe.throw(_("Reason is required"))
	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee not found"), frappe.DoesNotExistError)

	snapshot = _build_employee_snapshot(employee)
	rows = _parse_compensation_rows(compensation_rows)
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE_PERSONNEL_ACTION,
			"employee": employee,
			"employee_name": snapshot["employee_name"],
			"requested_by": frappe.session.user,
			"requested_on": now_datetime(),
			"effective_date": getdate(effective_date),
			"action_type": action_type or "Promotion",
			"reason": reason,
			"from_branch": snapshot["from_branch"],
			"from_department": snapshot["from_department"],
			"from_designation": snapshot["from_designation"],
			"from_reports_to": snapshot["from_reports_to"],
			"to_branch": to_branch,
			"to_department": to_department,
			"to_designation": to_designation,
			"to_reports_to": to_reports_to,
			"salary_old": flt(salary_old or 0),
			"salary_new": flt(salary_new or 0),
			"status": "Pending HR Approval",
			"compensation_changes": rows,
		}
	).insert(ignore_permissions=True)

	doc.add_comment("Comment", _("Personnel action submitted by {0}").format(frappe.session.user))
	return {"success": True, "name": doc.name, "status": doc.status}


@frappe.whitelist()
def list_personnel_actions(status=None, employee=None, page=1, page_size=20):
	_require_hr_personnel_action_role()

	page = max(1, cint(page) or 1)
	page_size = min(100, max(1, cint(page_size) or 20))
	filters: dict[str, Any] = {}
	if status:
		filters["status"] = status
	if employee:
		filters["employee"] = employee

	total = frappe.db.count(DOCTYPE_PERSONNEL_ACTION, filters=filters)
	data = frappe.get_all(
		DOCTYPE_PERSONNEL_ACTION,
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"action_type",
			"effective_date",
			"requested_by",
			"requested_on",
			"status",
			"to_branch",
			"to_department",
			"to_designation",
			"to_reports_to",
			"salary_old",
			"salary_new",
		],
		order_by="creation desc",
		start=(page - 1) * page_size,
		page_length=page_size,
	)

	return {"data": data, "total": total, "page": page, "page_size": page_size}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def approve_personnel_action(personnel_action_name, remarks=None):
	_require_hr_personnel_action_role()

	if not frappe.db.exists(DOCTYPE_PERSONNEL_ACTION, personnel_action_name):
		frappe.throw(_("Personnel action not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_PERSONNEL_ACTION, personnel_action_name)
	if doc.status == "Approved":
		frappe.throw(_("Personnel action is already approved"))
	if doc.status == "Rejected":
		frappe.throw(_("Personnel action is already rejected"))

	change_result = _apply_employee_master_change(doc)
	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.save(ignore_permissions=True)

	comment = _("Personnel action approved by {0}").format(frappe.session.user)
	if remarks:
		comment += _(". Notes: {0}").format(remarks)
	doc.add_comment("Comment", comment)

	return {
		"success": True,
		"name": doc.name,
		"status": doc.status,
		"employee_change": change_result,
	}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def reject_personnel_action(personnel_action_name, reason):
	_require_hr_personnel_action_role()
	if not reason:
		frappe.throw(_("Rejection reason is required"))

	if not frappe.db.exists(DOCTYPE_PERSONNEL_ACTION, personnel_action_name):
		frappe.throw(_("Personnel action not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_PERSONNEL_ACTION, personnel_action_name)
	if doc.status == "Approved":
		frappe.throw(_("Cannot reject an already approved personnel action"))

	doc.status = "Rejected"
	doc.rejected_by = frappe.session.user
	doc.rejected_on = now_datetime()
	doc.rejection_reason = reason
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("Personnel action rejected by {0}. Reason: {1}").format(frappe.session.user, reason))

	return {"success": True, "name": doc.name, "status": doc.status}
