"""DOLE compliance API endpoints used by my.bebang.ph."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _

ALLOWED_ROLES = ["HR Manager", "System Manager", "HR User", "Area Supervisor"]


def _require_access() -> None:
	"""Enforce role-based access for compliance endpoints."""
	frappe.only_for(ALLOWED_ROLES)


def _coerce_year(year: Any) -> int:
	try:
		value = int(year)
	except (TypeError, ValueError):
		frappe.throw(_("Invalid year parameter."), exc=frappe.ValidationError)
	if value < 2000 or value > 2100:
		frappe.throw(_("Year must be between 2000 and 2100."), exc=frappe.ValidationError)
	return value


def _coerce_month(month: Any) -> int:
	try:
		value = int(month)
	except (TypeError, ValueError):
		frappe.throw(_("Invalid month parameter."), exc=frappe.ValidationError)
	if value < 1 or value > 12:
		frappe.throw(_("Month must be between 1 and 12."), exc=frappe.ValidationError)
	return value


@frappe.whitelist(allow_guest=False)
def get_compliance_dashboard() -> dict[str, Any]:
	"""Return high-level compliance summary cards."""
	_require_access()

	now = datetime.utcnow()
	summary = {
		"generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
		"employees_for_review": 0,
		"open_separations": 0,
		"pending_clearance_items": 0,
	}

	try:
		open_separations = frappe.db.sql(
			"""
			SELECT COUNT(name)
			FROM `tabEmployee Separation`
			WHERE boarding_status != 'Completed'
			""",
		)
		pending_items = frappe.db.sql(
			"""
			SELECT COUNT(name)
			FROM `tabBEI DOLE Compliance Checklist`
			WHERE status = 'Pending'
			""",
		)
		summary["open_separations"] = int(open_separations[0][0]) if open_separations else 0
		summary["pending_clearance_items"] = int(pending_items[0][0]) if pending_items else 0
	except Exception:
		# Keep endpoint resilient for dashboard fallback rendering.
		pass

	return {"success": True, "data": summary}


@frappe.whitelist(allow_guest=False)
def calculate_13th_month_pay(year: int | str) -> dict[str, Any]:
	"""Return 13th month compliance aggregate for a given year."""
	_require_access()
	normalized_year = _coerce_year(year)

	rows = frappe.db.sql(
		"""
		SELECT employee, employee_name, IFNULL(SUM(base_gross_pay), 0) AS total_basic
		FROM `tabSalary Slip`
		WHERE docstatus = 1 AND YEAR(start_date) = %s
		GROUP BY employee, employee_name
		ORDER BY employee_name
		""",
		(normalized_year,),
		as_dict=True,
	)

	total_basic = sum(float(row.get("total_basic", 0) or 0) for row in rows)
	total_13th = round(total_basic / 12, 2)

	return {
		"success": True,
		"data": {
			"year": normalized_year,
			"employee_count": len(rows),
			"total_basic": round(total_basic, 2),
			"estimated_13th_month": total_13th,
			"rows": rows,
		},
	}


@frappe.whitelist(allow_guest=False)
def calculate_sil_balance(employee: str) -> dict[str, Any]:
	"""Return SIL balance details for one employee."""
	_require_access()
	if not employee:
		frappe.throw(_("Employee is required."), exc=frappe.ValidationError)

	allocation = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(total_leaves_allocated), 0) AS allocated
		FROM `tabLeave Allocation`
		WHERE employee = %s AND docstatus = 1 AND leave_type = 'Sick Leave'
		""",
		(employee,),
		as_dict=True,
	)
	consumed = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(total_leave_days), 0) AS consumed
		FROM `tabLeave Application`
		WHERE employee = %s AND docstatus = 1 AND status = 'Approved' AND leave_type = 'Sick Leave'
		""",
		(employee,),
		as_dict=True,
	)

	allocated = float((allocation[0] or {}).get("allocated", 0) if allocation else 0)
	used = float((consumed[0] or {}).get("consumed", 0) if consumed else 0)

	return {
		"success": True,
		"data": {
			"employee": employee,
			"allocated": allocated,
			"used": used,
			"remaining": round(max(allocated - used, 0), 2),
		},
	}


@frappe.whitelist(allow_guest=False)
def get_holiday_pay_compliance(month: int | str, year: int | str) -> dict[str, Any]:
	"""Return a month-level holiday pay compliance placeholder."""
	_require_access()
	normalized_month = _coerce_month(month)
	normalized_year = _coerce_year(year)

	return {
		"success": True,
		"data": {
			"month": normalized_month,
			"year": normalized_year,
			"rows": [],
			"notes": "Holiday pay compliance report scaffold.",
		},
	}


@frappe.whitelist(allow_guest=False)
def generate_13th_month_report(year: int | str) -> dict[str, Any]:
	"""Generate a lightweight report payload for export flow."""
	_require_access()
	normalized_year = _coerce_year(year)
	calc = calculate_13th_month_pay(normalized_year)
	data = calc.get("data", {})
	return {
		"success": True,
		"data": {
			"report_name": f"13th-month-{normalized_year}",
			"generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
			"summary": {
				"year": normalized_year,
				"employee_count": data.get("employee_count", 0),
				"estimated_13th_month": data.get("estimated_13th_month", 0),
			},
		},
		"message": _("13th month report generated."),
	}
