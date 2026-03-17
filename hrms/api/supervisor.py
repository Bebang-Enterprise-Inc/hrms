# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Supervisor Tools API
Handles approval queues, store visits, labor planning, and team management
"""

import json
import re
from collections import Counter
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_time, getdate, now_datetime, nowdate

from hrms.api.store import resolve_employee_store_context, resolve_warehouse
from hrms.utils.labor_plan_templates import apply_template_to_employees, get_template_metadata
from hrms.utils.store_shift_config import get_shift_options_for_store
from hrms.utils.supply_chain_contracts import get_preferred_commissary_warehouses

TRANSFER_REQUEST_DOCTYPE = "BEI Transfer Request"
SCHEDULE_SOURCE = "BEI_WEEKLY_LABOR_PLAN"
SCHEDULE_SURFACE_STORE = "store_schedule"
SCHEDULE_SURFACE_COMMISSARY = "commissary_schedule"
COMMISSARY_EMPLOYEE_BRANCH_ALIASES = {
	"SHAWBLVD": ("COMMISSARY SHAW",),
	"SHAWBLVDBKI": ("COMMISSARY SHAW",),
	"TESTCOMMISSARY": ("TEST-COMMISSARY", "TEST-COMMISSARY - BKI", "TEST-COMMISSARY - BEI"),
	"TESTCOMMISSARYBKI": ("TEST-COMMISSARY", "TEST-COMMISSARY - BKI", "TEST-COMMISSARY - BEI"),
	"TESTCOMMISSARYBEI": ("TEST-COMMISSARY", "TEST-COMMISSARY - BKI", "TEST-COMMISSARY - BEI"),
}


# ==============================================================================
# APPROVAL QUEUE
# ==============================================================================


@frappe.whitelist()
def get_pending_approvals(approver: str | None = None):
	"""Get pending items for an approver."""
	if not approver:
		approver = frappe.session.user

	approvals = frappe.get_all(
		"BEI Approval Queue",
		filters={"assigned_approver": approver, "status": "Pending"},
		fields=[
			"name",
			"reference_doctype",
			"reference_name",
			"store",
			"submitted_by",
			"submitted_at",
			"priority",
		],
		order_by="priority desc, submitted_at asc",
	)
	return {"approvals": approvals}


@frappe.whitelist()
def approve_item(queue_name: str, notes: str | None = None):
	"""Approve an item in the queue."""
	doc = frappe.get_doc("BEI Approval Queue", queue_name)
	if doc.reference_doctype == TRANSFER_REQUEST_DOCTYPE:
		frappe.throw(
			_("Transfer requests must be approved via transfer stage APIs, not generic queue mutators."),
			frappe.ValidationError,
		)

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = now_datetime()
	doc.save()

	# Also update the referenced document if it has status field
	try:
		ref_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)
		if hasattr(ref_doc, "status"):
			ref_doc.status = "Approved"
			if hasattr(ref_doc, "approved_by"):
				ref_doc.approved_by = frappe.session.user
			if hasattr(ref_doc, "approved_at"):
				ref_doc.approved_at = now_datetime()
			ref_doc.save()
	except Exception:
		pass  # Reference document may not exist

	return {"success": True, "message": f"Approved {queue_name}"}


@frappe.whitelist()
def reject_item(queue_name: str, reason: str):
	"""Reject an item in the queue."""
	if not reason:
		frappe.throw(_("Rejection reason is required"))

	doc = frappe.get_doc("BEI Approval Queue", queue_name)
	if doc.reference_doctype == TRANSFER_REQUEST_DOCTYPE:
		frappe.throw(
			_("Transfer requests must be rejected via transfer stage APIs, not generic queue mutators."),
			frappe.ValidationError,
		)

	doc.status = "Rejected"
	doc.approved_by = frappe.session.user
	doc.approved_at = now_datetime()
	doc.rejection_reason = reason
	doc.save()
	return {"success": True, "message": f"Rejected {queue_name}"}


@frappe.whitelist()
def escalate_item(queue_name: str, escalate_to: str):
	"""Escalate an item to another approver."""
	doc = frappe.get_doc("BEI Approval Queue", queue_name)
	doc.status = "Escalated"
	doc.assigned_approver = escalate_to
	doc.save()
	return {"success": True, "message": f"Escalated to {escalate_to}"}


# ==============================================================================
# STORE VISITS
# ==============================================================================

# Category mapping for store visit audit items
# Frontend may send short codes, but DocType requires full labels with prefix
CATEGORY_MAP = {
	# Short codes
	"A": "A. Funds",
	"B": "B. Stocks",
	"C": "C. Organization",
	"D": "D. Staffing",
	"E": "E. Coaching",
	# Short names (without prefix)
	"Funds": "A. Funds",
	"Stocks": "B. Stocks",
	"Organization": "C. Organization",
	"Staffing": "D. Staffing",
	"Coaching": "E. Coaching",
}


@frappe.whitelist()
def create_store_visit(
	store: str,
	visit_type: str,
	audit_items: str | list[dict[str, Any]],
	score_funds: int | str | None = None,
	score_stocks: int | str | None = None,
	score_organization: int | str | None = None,
	score_staffing: int | str | None = None,
	score_coaching: int | str | None = None,
	critical_findings: str | None = None,
	action_items: str | None = None,
	follow_up_date: str | None = None,
	photos: str | list[dict[str, Any]] | None = None,
	store_supervisor_present: bool | int | None = None,
):
	"""Create a store visit report with 100-point scoring."""
	if not store:
		frappe.throw(_("Store is required"))

	if isinstance(audit_items, str):
		audit_items = json.loads(audit_items)
	if isinstance(photos, str):
		photos = json.loads(photos)

	doc = frappe.new_doc("BEI Store Visit Report")
	doc.store = store
	doc.visit_date = nowdate()
	doc.visit_type = visit_type
	doc.visited_by = frappe.session.user
	doc.store_supervisor_present = store_supervisor_present
	doc.critical_findings = critical_findings
	doc.action_items = action_items
	doc.follow_up_date = follow_up_date

	# Scoring (each max 20, total 100)
	doc.score_funds = int(score_funds) if score_funds else 0
	doc.score_stocks = int(score_stocks) if score_stocks else 0
	doc.score_organization = int(score_organization) if score_organization else 0
	doc.score_staffing = int(score_staffing) if score_staffing else 0
	doc.score_coaching = int(score_coaching) if score_coaching else 0

	for item in audit_items:
		# Normalize category to full label with prefix
		if item.get("category") in CATEGORY_MAP:
			item["category"] = CATEGORY_MAP[item["category"]]
		doc.append("audit_items", item)

	if photos:
		for photo in photos:
			doc.append("photos", photo)

	doc.status = "Submitted"
	doc.insert()
	return {"success": True, "name": doc.name, "score": doc.overall_score, "grade": doc.overall_grade}


@frappe.whitelist()
def get_store_visits(
	store: str | None = None,
	visited_by: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
):
	"""Get store visit history."""
	filters = {}
	if store:
		filters["store"] = store
	if visited_by:
		filters["visited_by"] = visited_by
	if date_from:
		filters["visit_date"] = [">=", date_from]
	if date_to:
		if "visit_date" in filters:
			filters["visit_date"] = ["between", [date_from, date_to]]
		else:
			filters["visit_date"] = ["<=", date_to]

	visits = frappe.get_all(
		"BEI Store Visit Report",
		filters=filters,
		fields=["name", "store", "visit_date", "visit_type", "overall_score", "overall_grade", "status"],
		order_by="visit_date desc",
		limit=int(limit),
	)
	return {"visits": visits}


@frappe.whitelist()
def get_visit_detail(visit_name: str):
	"""Get full details of a store visit."""
	doc = frappe.get_doc("BEI Store Visit Report", visit_name)
	return {"visit": doc.as_dict()}


@frappe.whitelist()
def acknowledge_visit(visit_name: str):
	"""Acknowledge a store visit report."""
	doc = frappe.get_doc("BEI Store Visit Report", visit_name)
	doc.status = "Acknowledged"
	doc.save()
	return {"success": True}


# ==============================================================================
# WEEKLY LABOR PLANNING
# ==============================================================================


DAY_OFFSETS = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}


def _normalize_designation(designation: str | None):
	return (designation or "").strip().upper()


def _is_store_oic_designation(designation: str | None):
	normalized = _normalize_designation(designation)
	return (
		"OIC" in normalized
		or ("ASSISTANT" in normalized and "SUPERVISOR" in normalized)
		or ("ASST" in normalized and "SUPERVISOR" in normalized)
	)


def _resolve_labor_plan_store(store: str):
	warehouse = resolve_warehouse(store)
	warehouse_name = frappe.db.get_value("Warehouse", warehouse, "warehouse_name") or warehouse
	return {"warehouse": warehouse, "warehouse_name": warehouse_name}


def _normalize_schedule_surface(surface: str | None) -> str:
	value = re.sub(r"[^a-z_]", "", str(surface or "").strip().lower())
	if value == SCHEDULE_SURFACE_COMMISSARY:
		return SCHEDULE_SURFACE_COMMISSARY
	return SCHEDULE_SURFACE_STORE


def _normalize_schedule_location_key(value: str | None) -> str:
	return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _commissary_schedule_location_keys() -> set[str]:
	keys = {"COMMISSARY", "SHAWBLVD", "SHAWBLVDBKI"}
	for warehouse in get_preferred_commissary_warehouses(include_legacy=True):
		normalized = str(warehouse or "").upper().strip()
		if not normalized or normalized.startswith("TEST-"):
			continue
		keys.add(_normalize_schedule_location_key(normalized))
		keys.add(_normalize_schedule_location_key(normalized.replace(" - BEI", "").replace(" - BKI", "")))
	return {key for key in keys if key}


def _is_commissary_schedule_store(store: str):
	store_context = _resolve_labor_plan_store(store)
	keys = _commissary_schedule_location_keys()
	return (
		_normalize_schedule_location_key(store_context["warehouse"]) in keys
		or _normalize_schedule_location_key(store_context["warehouse_name"]) in keys
	)


def _get_current_employee():
	return frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user, "status": "Active"},
		["name", "employee_name", "branch", "designation", "reports_to", "company", "user_id"],
		as_dict=True,
	)


def _user_can_manage_store_schedule(store: str):
	user_roles = set(frappe.get_roles(frappe.session.user))
	if user_roles.intersection({"System Manager", "Administrator", "HR User", "HR Manager"}):
		return True

	store_context = _resolve_labor_plan_store(store)

	if "Area Supervisor" in user_roles:
		return bool(
			frappe.db.exists(
				"Warehouse",
				{"name": store_context["warehouse"], "custom_area_supervisor": frappe.session.user},
			)
		)

	employee = _get_current_employee()
	if not employee:
		return False

	resolved_store = resolve_employee_store_context(employee)
	if resolved_store.get("warehouse") != store_context["warehouse"]:
		return False

	if "Store Supervisor" in user_roles:
		return True

	return "Store Staff" in user_roles and _is_store_oic_designation(employee.get("designation"))


def _user_can_manage_commissary_schedule(store: str):
	user_roles = set(frappe.get_roles(frappe.session.user))
	if user_roles.intersection({"System Manager", "Administrator", "HR User", "HR Manager"}):
		return True

	if not _is_commissary_schedule_store(store):
		return False

	return bool(user_roles.intersection({"Commissary Supervisor", "Warehouse User", "Supply Chain Manager"}))


def _assert_schedule_access(store: str, surface: str | None = None):
	surface_key = _normalize_schedule_surface(surface)
	if surface_key == SCHEDULE_SURFACE_COMMISSARY:
		if not _user_can_manage_commissary_schedule(store):
			frappe.throw(
				_("You do not have permission to manage commissary schedules for {0}.").format(store),
				frappe.PermissionError,
			)
		return

	if not _user_can_manage_store_schedule(store):
		frappe.throw(
			_("You do not have permission to manage schedules for {0}.").format(store),
			frappe.PermissionError,
		)


def _coerce_shifts(shifts: str | list[dict[str, Any]] | None):
	if isinstance(shifts, str):
		shifts = json.loads(shifts)
	return shifts or []


def _calculate_shift_hours(shift_start: str | None, shift_end: str | None, is_off: bool | int = 0):
	if cint(is_off) or not shift_start or not shift_end:
		return 0

	start = get_time(shift_start)
	end = get_time(shift_end)
	hours = (end.hour * 60 + end.minute - start.hour * 60 - start.minute) / 60
	if hours < 0:
		hours += 24
	return hours


def _sort_labor_plan_employees(employees: list[dict[str, Any]]):
	def employee_sort_key(row: dict[str, Any]):
		designation = _normalize_designation(row.get("designation"))
		if "STORE SUPERVISOR" in designation and "ASSISTANT" not in designation:
			priority = 0
		elif _is_store_oic_designation(designation):
			priority = 1
		elif "CASHIER" in designation:
			priority = 3
		else:
			priority = 2
		return (priority, row.get("employee_name") or row.get("name") or "")

	return sorted(employees, key=employee_sort_key)


def _get_labor_plan_employees(store_context: dict[str, str]):
	branch_candidates = {
		store_context["warehouse"],
		store_context["warehouse_name"],
	}
	for key in (
		_normalize_schedule_location_key(store_context["warehouse"]),
		_normalize_schedule_location_key(store_context["warehouse_name"]),
	):
		branch_candidates.update(COMMISSARY_EMPLOYEE_BRANCH_ALIASES.get(key, ()))

	employees = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"branch": ["in", [value for value in branch_candidates if value]],
		},
		fields=["name", "employee_name", "designation", "branch", "company"],
		order_by="employee_name asc",
	)
	for employee in employees:
		rate_meta = _get_labor_plan_hour_rate(employee.get("name"))
		employee["hour_rate"] = rate_meta.get("hour_rate")
		employee["hour_rate_source"] = rate_meta.get("source")
		employee["base_salary"] = rate_meta.get("base_salary")
	return _sort_labor_plan_employees(employees)


def _annotate_commissary_rotation_groups(employees: list[dict[str, Any]]):
	rotation_labels = ("Team A", "Team B", "Team C", "Team D")
	for index, employee in enumerate(employees):
		employee["rotation_group"] = rotation_labels[index % len(rotation_labels)]
	return employees


def _get_labor_plan_hour_rate(employee: str | None, effective_on: str | None = None):
	if not employee:
		return {"hour_rate": None, "source": None, "base_salary": None}

	filters: dict[str, Any] = {"employee": employee, "docstatus": 1}
	if effective_on:
		filters["from_date"] = ["<=", effective_on]

	assignments = frappe.get_all(
		"Salary Structure Assignment",
		filters=filters,
		fields=["name", "salary_structure", "base", "from_date"],
		order_by="from_date desc",
		limit=1,
	)
	if not assignments:
		return {"hour_rate": None, "source": None, "base_salary": None}

	assignment = assignments[0]
	base_salary = flt(assignment.get("base"))
	structure_rate = flt(
		frappe.db.get_value("Salary Structure", assignment.get("salary_structure"), "hour_rate") or 0
	)
	if structure_rate > 0:
		return {"hour_rate": round(structure_rate, 2), "source": "salary_structure", "base_salary": base_salary}

	if base_salary > 0:
		# Fallback estimate: monthly base salary over a 26-day / 8-hour operating month.
		return {
			"hour_rate": round(base_salary / 208, 2),
			"source": "salary_base_estimate",
			"base_salary": base_salary,
		}

	return {"hour_rate": None, "source": None, "base_salary": base_salary or None}


def _calculate_plan_cost(shifts: list[dict[str, Any]] | list[Any], hourly_rates: dict[str, float | None]):
	total_cost = 0.0
	for row in shifts:
		employee = row.get("employee") if isinstance(row, dict) else getattr(row, "employee", None)
		if not employee:
			continue
		if cint(row.get("is_off") if isinstance(row, dict) else getattr(row, "is_off", 0)):
			continue
		hours = flt(row.get("hours") if isinstance(row, dict) else getattr(row, "hours", 0))
		if hours <= 0:
			shift_start = row.get("shift_start") if isinstance(row, dict) else getattr(row, "shift_start", None)
			shift_end = row.get("shift_end") if isinstance(row, dict) else getattr(row, "shift_end", None)
			hours = flt(_calculate_shift_hours(shift_start, shift_end, 0))
		rate = flt(hourly_rates.get(employee) or 0)
		if rate > 0 and hours > 0:
			total_cost += rate * hours
	return round(total_cost, 2)


def _get_shift_type_name(shift: dict[str, Any]):
	if cint(shift.get("is_off")):
		return "Off"
	return shift.get("shift_type_name") or shift.get("shift_type")


def _legacy_shift_type_value(shift_type_name: str | None):
	return shift_type_name if shift_type_name in {"Opening", "Mid", "Closing"} else None


def _apply_shifts(doc: Any, shifts: list[dict[str, Any]]):
	doc.shifts = []
	total_hours = 0

	for shift in shifts:
		row = doc.append("shifts", {})
		row.employee = shift.get("employee")
		row.employee_name = shift.get("employee_name")
		row.day_of_week = shift.get("day_of_week")
		row.shift_type_name = _get_shift_type_name(shift)
		row.is_off = cint(shift.get("is_off"))
		row.ends_next_day = cint(shift.get("ends_next_day"))
		row.notes = shift.get("notes")
		row.shift_type = _legacy_shift_type_value(row.shift_type_name)

		if not row.is_off:
			row.shift_start = shift.get("shift_start")
			row.shift_end = shift.get("shift_end")
		else:
			row.shift_start = None
			row.shift_end = None

		row.hours = _calculate_shift_hours(row.shift_start, row.shift_end, row.is_off)
		total_hours += row.hours or 0

	doc.total_hours = total_hours
	return total_hours


def _get_work_date(week_start_date: str, day_of_week: str):
	if day_of_week not in DAY_OFFSETS:
		frappe.throw(_("Unsupported day of week: {0}").format(day_of_week))
	return add_days(week_start_date, DAY_OFFSETS[day_of_week])


def _get_shift_assignment_conflicts(employee: str, work_date: str, row_key: str, plan_name: str):
	ShiftAssignment = frappe.qb.DocType("Shift Assignment")
	assignments = (
		frappe.qb.from_(ShiftAssignment)
		.select(
			ShiftAssignment.name,
			ShiftAssignment.shift_type,
			ShiftAssignment.start_date,
			ShiftAssignment.end_date,
			ShiftAssignment.custom_bei_schedule_source,
			ShiftAssignment.custom_bei_weekly_labor_plan,
			ShiftAssignment.custom_bei_weekly_plan_row_key,
		)
		.where(
			(ShiftAssignment.employee == employee)
			& (ShiftAssignment.docstatus == 1)
			& (ShiftAssignment.status == "Active")
			& (ShiftAssignment.start_date <= work_date)
			& ((ShiftAssignment.end_date >= work_date) | (ShiftAssignment.end_date.isnull()))
		)
	).run(as_dict=True)

	conflicts = []
	for assignment in assignments:
		if (
			assignment.custom_bei_schedule_source == SCHEDULE_SOURCE
			and assignment.custom_bei_weekly_labor_plan == plan_name
			and assignment.custom_bei_weekly_plan_row_key == row_key
		):
			continue
		conflicts.append(assignment)

	return conflicts


def _cancel_and_delete_shift_assignment(assignment_name: str):
	assignment = frappe.get_doc("Shift Assignment", assignment_name)
	assignment.flags.ignore_permissions = True
	assignment.flags.ignore_user_permissions = True
	if assignment.docstatus == 1:
		assignment.cancel()
	frappe.delete_doc("Shift Assignment", assignment_name, ignore_permissions=True)


def _normalized_shift_time(value: str | None):
	if not value:
		return None
	return get_time(value)


def _ensure_shift_type_for_plan_row(row: Any):
	shift_type_name = (row.shift_type_name or row.shift_type or "").strip()
	if not shift_type_name or shift_type_name == "Off":
		frappe.throw(_("Shift type is required for {0} on {1}.").format(row.employee, row.day_of_week))

	if frappe.db.exists("Shift Type", shift_type_name):
		return shift_type_name

	start_time = _normalized_shift_time(row.shift_start)
	end_time = _normalized_shift_time(row.shift_end)
	if not start_time or not end_time:
		frappe.throw(
			_("Shift Type {0} is missing start/end times and cannot be provisioned.").format(shift_type_name)
		)

	# S043: provision with ALL required fields for auto-attendance.
	# `process_attendance_after` is a Date field; `last_sync_of_checkin`
	# is a Datetime updated hourly by the scheduler when auto_update_last_sync=1.
	process_after = "2026-02-01"
	last_sync = frappe.utils.now_datetime()

	frappe.get_doc(
		{
			"doctype": "Shift Type",
			"name": shift_type_name,
			"start_time": start_time,
			"end_time": end_time,
			"enable_auto_attendance": 1,
			"process_attendance_after": process_after,
			"last_sync_of_checkin": last_sync,
			"late_entry_grace_period": 15,
			"early_exit_grace_period": 15,
			"working_hours_threshold_for_half_day": 4,
			"working_hours_threshold_for_absent": 1,
			"allow_check_out_after_shift_end_time": 60,
			"working_hours_calculation_based_on": "First Check-in and Last Check-out",
			"enable_late_entry_marking": 1,
			"enable_early_exit_marking": 1,
			"auto_update_last_sync": 1,
			"determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True)

	return shift_type_name


def _create_shift_assignment_from_plan(plan: Any, row: Any, work_date: str, publish_run_id: str):
	employee = frappe.db.get_value(
		"Employee",
		row.employee,
		["company", "branch"],
		as_dict=True,
	)
	if not employee or not employee.get("company"):
		frappe.throw(_("Employee {0} is missing company data.").format(row.employee))

	shift_type_name = _ensure_shift_type_for_plan_row(row)

	row_key = f"{row.employee}|{work_date}"
	assignment = frappe.get_doc(
		{
			"doctype": "Shift Assignment",
			"employee": row.employee,
			"company": employee.company,
			"shift_type": shift_type_name,
			"start_date": work_date,
			"end_date": work_date,
			"status": "Active",
			"custom_bei_schedule_source": SCHEDULE_SOURCE,
			"custom_bei_weekly_labor_plan": plan.name,
			"custom_bei_weekly_plan_row_key": row_key,
			"custom_bei_publish_run_id": publish_run_id,
		}
	)
	assignment.flags.ignore_permissions = True
	assignment.flags.ignore_user_permissions = True
	assignment.insert(ignore_permissions=True)
	assignment.submit()
	return assignment


def _get_shift_assignment_doc(assignment_name: str):
	assignment = frappe.get_doc("Shift Assignment", assignment_name)
	if assignment.docstatus != 1 or assignment.status != "Active":
		frappe.throw(_("Shift Assignment {0} is not active.").format(assignment_name))
	return assignment


def _assignment_covers_date(assignment: Any, work_date: str) -> bool:
	start_date = str(assignment.start_date)
	end_date = str(assignment.end_date or assignment.start_date)
	return start_date <= work_date <= end_date


def _get_shift_assignments_for_employees(employee_names: list[str], from_date: str, to_date: str):
	if not employee_names:
		return []
	placeholders = ", ".join(["%s"] * len(employee_names))
	params = [*employee_names, to_date, from_date]
	return frappe.db.sql(
		f"""
		SELECT
			name,
			employee,
			shift_type,
			start_date,
			end_date,
			status,
			custom_bei_schedule_source,
			custom_bei_weekly_labor_plan
		FROM `tabShift Assignment`
		WHERE employee IN ({placeholders})
			AND docstatus = 1
			AND status = 'Active'
			AND start_date <= %s
			AND (end_date IS NULL OR end_date = '' OR end_date >= %s)
		ORDER BY employee ASC, start_date ASC
		""",
		params,
		as_dict=True,
	)


def _expand_shift_assignment_rows(
	assignments: list[dict[str, Any]],
	from_date: str,
	to_date: str,
	employee_lookup: dict[str, dict[str, Any]],
):
	rows = []
	for assignment in assignments:
		current = str(max(getdate(assignment.start_date), getdate(from_date)))
		final = str(min(getdate(assignment.end_date or assignment.start_date), getdate(to_date)))
		while current <= final:
			employee = employee_lookup.get(assignment.employee, {})
			rows.append(
				{
					"assignment_name": assignment.name,
					"employee": assignment.employee,
					"employee_name": employee.get("employee_name") or assignment.employee,
					"user_id": employee.get("user_id"),
					"designation": employee.get("designation"),
					"branch": employee.get("branch"),
					"work_date": current,
					"shift_type": assignment.shift_type,
					"weekly_plan": assignment.custom_bei_weekly_labor_plan,
				}
			)
			current = str(add_days(current, 1))
	return rows


def _serialize_shift_swap_request(request: Any, *, surface: str | None = None):
	surface_key = surface or (
		SCHEDULE_SURFACE_COMMISSARY if _is_commissary_schedule_store(request.store) else SCHEDULE_SURFACE_STORE
	)
	user_roles = set(frappe.get_roles(frappe.session.user))
	can_manage = False
	if surface_key == SCHEDULE_SURFACE_COMMISSARY:
		can_manage = _user_can_manage_commissary_schedule(request.store)
	else:
		can_manage = _user_can_manage_store_schedule(request.store)
	can_approve = request.status == "Pending Approval" and (
		request.approver == frappe.session.user
		or can_manage
		or bool(user_roles.intersection({"HR User", "HR Manager", "System Manager", "Administrator"}))
	)
	return {
		"name": request.name,
		"store": request.store,
		"swap_date": str(request.swap_date),
		"requester_employee": request.requester_employee,
		"requester_name": request.requester_name,
		"requester_shift_assignment": request.requester_shift_assignment,
		"requester_shift_type": request.requester_shift_type,
		"target_employee": request.target_employee,
		"target_name": request.target_name,
		"target_shift_assignment": request.target_shift_assignment,
		"target_shift_type": request.target_shift_type,
		"approver": request.approver,
		"approver_name": frappe.db.get_value("User", request.approver, "full_name") or request.approver,
		"status": request.status,
		"notes": request.notes,
		"decision_note": request.decision_note,
		"approved_by": request.approved_by,
		"approved_at": str(request.approved_at) if request.approved_at else None,
		"can_approve": can_approve,
	}


def _resolve_shift_swap_approver(employee: dict[str, Any], store_context: dict[str, str]):
	if not employee:
		return None
	explicit_approver = frappe.db.get_value("Employee", employee.get("name"), "shift_request_approver")
	if explicit_approver:
		return explicit_approver
	if employee.get("reports_to"):
		manager_user = frappe.db.get_value("Employee", employee.get("reports_to"), "user_id")
		if manager_user:
			return manager_user
	area_supervisor = frappe.db.get_value("Warehouse", store_context["warehouse"], "custom_area_supervisor")
	if area_supervisor:
		return area_supervisor
	return None


def _notify_schedule_change(
	store: str,
	employee: str,
	employee_name: str,
	message: str,
	*,
	context: str,
):
	try:
		from hrms.api.google_chat import send_message_to_space, send_message_to_user_direct

		user_id = frappe.db.get_value("Employee", employee, "user_id")
		result = send_message_to_user_direct(user_id, message, context=context)
		if result.get("success"):
			return result
		store_space = frappe.db.get_value("Warehouse", store, "custom_gchat_space")
		if store_space:
			send_message_to_space(store_space, f"{employee_name}\n{message}")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Schedule Change Notification Failed")
	return {"success": False, "sent": False}


def _send_published_schedule_notifications(plan: Any, change_map: dict[str, list[dict[str, Any]]]):
	if not change_map:
		return

	for employee, changes in change_map.items():
		employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
		lines = [
			"*Schedule Update*",
			"",
			f"Location: {plan.store}",
			f"Week of {plan.week_start_date}",
			"",
			"*Changes*",
		]
		for change in changes:
			work_date = str(change.get("work_date") or "")
			change_type = str(change.get("type") or "updated")
			new_shift = str(change.get("new_shift") or "-")
			old_shift = str(change.get("old_shift") or "-")
			if change_type == "created":
				lines.append(f"• {work_date}: assigned to {new_shift}")
			elif change_type == "deleted":
				lines.append(f"• {work_date}: removed from {old_shift}")
			else:
				lines.append(f"• {work_date}: {old_shift} → {new_shift}")
		lines.extend(["", f"Open: https://my.bebang.ph/dashboard/hr/schedule"])
		_notify_schedule_change(
			plan.store,
			employee,
			employee_name,
			"\n".join(lines),
			context="hrms.api.supervisor.publish_weekly_plan",
		)


def _sync_shift_swap_plan_rows(doc: Any):
	requester_assignment = _get_shift_assignment_doc(doc.requester_shift_assignment)
	target_assignment = _get_shift_assignment_doc(doc.target_shift_assignment)
	requester_plan = requester_assignment.custom_bei_weekly_labor_plan
	target_plan = target_assignment.custom_bei_weekly_labor_plan
	if not requester_plan or requester_plan != target_plan:
		return

	plan = frappe.get_doc("BEI Weekly Labor Plan", requester_plan)
	day_name = None
	for label, offset in DAY_OFFSETS.items():
		if str(add_days(plan.week_start_date, offset)) == str(doc.swap_date):
			day_name = label
			break
	if not day_name:
		return

	requester_row = None
	target_row = None
	for row in plan.shifts:
		if row.day_of_week != day_name:
			continue
		if row.employee == doc.requester_employee and requester_row is None:
			requester_row = row
		elif row.employee == doc.target_employee and target_row is None:
			target_row = row

	if not requester_row or not target_row:
		return

	requester_row.employee, target_row.employee = target_row.employee, requester_row.employee
	requester_row.employee_name, target_row.employee_name = target_row.employee_name, requester_row.employee_name
	plan.save(ignore_permissions=True)


def _notify_shift_swap_decision(doc: Any):
	lines = [
		"*Shift Swap Update*",
		"",
		f"Location: {doc.store}",
		f"Date: {doc.swap_date}",
		f"{doc.requester_name}: {doc.requester_shift_type}",
		f"{doc.target_name}: {doc.target_shift_type}",
		"",
		f"Status: {doc.status}",
	]
	if doc.decision_note:
		lines.extend(["", f"Note: {doc.decision_note}"])
	message = "\n".join(lines)
	_notify_schedule_change(
		doc.store,
		doc.requester_employee,
		doc.requester_name or doc.requester_employee,
		message,
		context="hrms.api.supervisor.shift_swap_decision",
	)
	_notify_schedule_change(
		doc.store,
		doc.target_employee,
		doc.target_name or doc.target_employee,
		message,
		context="hrms.api.supervisor.shift_swap_decision",
	)


@frappe.whitelist()
def get_shift_swap_context(week_start: str | None = None):
	current_employee = _get_current_employee()
	if not current_employee:
		frappe.throw(_("No active employee record found for the current user."))

	store_context = resolve_employee_store_context(current_employee)
	if not store_context.get("warehouse"):
		return {
			"employee": current_employee,
			"store": None,
			"warehouse_name": None,
			"week_start": str(getdate(week_start)) if week_start else _default_week_start_value(),
			"week_end": str(add_days(str(getdate(week_start)) if week_start else _default_week_start_value(), 6)),
			"approver": {"user_id": None, "full_name": None},
			"assignments": [],
			"coworker_assignments": [],
			"requests": [],
		}

	start_date = str(getdate(week_start)) if week_start else _default_week_start_value()
	if start_date < nowdate():
		start_date = nowdate()
	end_date = str(add_days(start_date, 6))

	coworkers = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"branch": ["in", [store_context["warehouse"], store_context["warehouse_name"]]],
			"name": ["!=", current_employee["name"]],
		},
		fields=["name", "employee_name", "designation", "branch", "user_id"],
		order_by="employee_name asc",
	)
	employee_lookup = {
		current_employee["name"]: current_employee,
		**{row["name"]: row for row in coworkers},
	}

	assignments = _get_shift_assignments_for_employees(list(employee_lookup.keys()), start_date, end_date)
	expanded = _expand_shift_assignment_rows(assignments, start_date, end_date, employee_lookup)
	my_assignments = [row for row in expanded if row["employee"] == current_employee["name"]]
	coworker_assignments = [row for row in expanded if row["employee"] != current_employee["name"]]
	approver = _resolve_shift_swap_approver(current_employee, store_context)
	requests = frappe.get_all(
		"BEI Shift Swap Request",
		filters={
			"requester_employee": current_employee["name"],
			"swap_date": ["between", [start_date, end_date]],
		},
		fields=["name"],
		order_by="creation desc",
	)

	return {
		"employee": current_employee,
		"store": store_context["warehouse"],
		"warehouse_name": store_context["warehouse_name"],
		"week_start": start_date,
		"week_end": end_date,
		"approver": {
			"user_id": approver,
			"full_name": frappe.db.get_value("User", approver, "full_name") if approver else None,
		},
		"assignments": my_assignments,
		"coworker_assignments": coworker_assignments,
		"requests": [
			_serialize_shift_swap_request(frappe.get_doc("BEI Shift Swap Request", row.name))
			for row in requests
		],
	}


@frappe.whitelist()
def create_shift_swap_request(
	requester_shift_assignment: str,
	target_shift_assignment: str,
	work_date: str,
	notes: str | None = None,
):
	current_employee = _get_current_employee()
	if not current_employee:
		frappe.throw(_("No active employee record found for the current user."))

	swap_date = str(getdate(work_date))
	requester_assignment = _get_shift_assignment_doc(requester_shift_assignment)
	target_assignment = _get_shift_assignment_doc(target_shift_assignment)
	if requester_assignment.employee != current_employee["name"]:
		frappe.throw(_("You can only request swaps for your own shifts."), frappe.PermissionError)
	if not _assignment_covers_date(requester_assignment, swap_date):
		frappe.throw(_("Your selected shift does not cover {0}.").format(swap_date))
	if not _assignment_covers_date(target_assignment, swap_date):
		frappe.throw(_("The coworker's shift does not cover {0}.").format(swap_date))
	if requester_assignment.employee == target_assignment.employee:
		frappe.throw(_("Choose a coworker shift to swap with."))

	store_context = resolve_employee_store_context(current_employee)
	target_employee = frappe.db.get_value(
		"Employee",
		target_assignment.employee,
		["name", "employee_name", "branch", "company"],
		as_dict=True,
	)
	if not target_employee:
		frappe.throw(_("Target employee could not be found."))
	if target_employee.get("branch") not in {store_context["warehouse"], store_context["warehouse_name"]}:
		frappe.throw(_("Shift swaps are limited to coworkers in the same location."))

	if frappe.db.exists(
		"BEI Shift Swap Request",
		{
			"requester_employee": current_employee["name"],
			"swap_date": swap_date,
			"status": "Pending Approval",
		},
	):
		frappe.throw(_("You already have a pending swap request for {0}.").format(swap_date))

	approver = _resolve_shift_swap_approver(current_employee, store_context)
	if not approver:
		frappe.throw(_("No approver is configured for shift swaps at this location."))

	doc = frappe.get_doc(
		{
			"doctype": "BEI Shift Swap Request",
			"requester_employee": current_employee["name"],
			"store": store_context["warehouse"],
			"company": current_employee.get("company") or target_employee.get("company"),
			"swap_date": swap_date,
			"target_employee": target_employee["name"],
			"requester_shift_assignment": requester_assignment.name,
			"requester_shift_type": requester_assignment.shift_type,
			"target_shift_assignment": target_assignment.name,
			"target_shift_type": target_assignment.shift_type,
			"approver": approver,
			"status": "Pending Approval",
			"notes": notes,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)

	return {"success": True, "request": _serialize_shift_swap_request(doc)}


@frappe.whitelist()
def get_location_shift_swap_requests(store: str, week_start: str, surface: str | None = None):
	store_context = _resolve_labor_plan_store(store)
	surface_key = _normalize_schedule_surface(surface)
	_assert_schedule_access(store_context["warehouse"], surface_key)
	week_start_date = str(getdate(week_start))
	week_end_date = str(add_days(week_start_date, 6))
	requests = frappe.get_all(
		"BEI Shift Swap Request",
		filters={
			"store": store_context["warehouse"],
			"swap_date": ["between", [week_start_date, week_end_date]],
		},
		fields=["name"],
		order_by="swap_date asc, creation asc",
	)
	return {
		"requests": [
			_serialize_shift_swap_request(
				frappe.get_doc("BEI Shift Swap Request", row.name),
				surface=surface_key,
			)
			for row in requests
		]
	}


@frappe.whitelist()
def approve_shift_swap_request(request_name: str, decision_note: str | None = None):
	doc = frappe.get_doc("BEI Shift Swap Request", request_name)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only pending shift swap requests can be approved."))

	surface_key = (
		SCHEDULE_SURFACE_COMMISSARY if _is_commissary_schedule_store(doc.store) else SCHEDULE_SURFACE_STORE
	)
	_assert_schedule_access(doc.store, surface_key)
	from hrms.api.roster import swap_shift

	swap_shift(doc.requester_shift_assignment, str(doc.swap_date), doc.target_employee, str(doc.swap_date), doc.target_shift_assignment)
	_sync_shift_swap_plan_rows(doc)
	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_at = now_datetime()
	doc.decision_note = decision_note
	doc.save(ignore_permissions=True)
	_notify_shift_swap_decision(doc)
	return {"success": True, "request": _serialize_shift_swap_request(doc, surface=surface_key)}


@frappe.whitelist()
def reject_shift_swap_request(request_name: str, decision_note: str | None = None):
	doc = frappe.get_doc("BEI Shift Swap Request", request_name)
	if doc.status != "Pending Approval":
		frappe.throw(_("Only pending shift swap requests can be rejected."))

	surface_key = (
		SCHEDULE_SURFACE_COMMISSARY if _is_commissary_schedule_store(doc.store) else SCHEDULE_SURFACE_STORE
	)
	_assert_schedule_access(doc.store, surface_key)
	doc.status = "Rejected"
	doc.approved_by = frappe.session.user
	doc.approved_at = now_datetime()
	doc.decision_note = decision_note
	doc.save(ignore_permissions=True)
	_notify_shift_swap_decision(doc)
	return {"success": True, "request": _serialize_shift_swap_request(doc, surface=surface_key)}


@frappe.whitelist()
def get_labor_plan_bootstrap(store: str, surface: str | None = None):
	"""Return store roster and shift options for labor planning."""
	if not store:
		frappe.throw(_("Store is required"))

	surface_key = _normalize_schedule_surface(surface)
	_assert_schedule_access(store, surface_key)
	store_context = _resolve_labor_plan_store(store)
	employees = _get_labor_plan_employees(store_context)
	if surface_key == SCHEDULE_SURFACE_COMMISSARY:
		employees = _annotate_commissary_rotation_groups(employees)

	return {
		"store": store_context["warehouse"],
		"warehouse_name": store_context["warehouse_name"],
		"surface": surface_key,
		"employees": employees,
		"shift_options": get_shift_options_for_store(store_context["warehouse_name"]),
		"templates": get_template_metadata(surface_key),
	}


@frappe.whitelist()
def get_weekly_templates(store: str, surface: str | None = None):
	"""Return template metadata for the selected labor-plan surface."""
	if not store:
		frappe.throw(_("Store is required"))

	surface_key = _normalize_schedule_surface(surface)
	_assert_schedule_access(store, surface_key)
	return {"templates": get_template_metadata(surface_key)}


@frappe.whitelist()
def apply_weekly_template(
	store: str,
	template_key: str,
	week_start: str | None = None,
	surface: str | None = None,
):
	"""Apply a roster-aware weekly template to the selected location."""
	if not store:
		frappe.throw(_("Store is required"))
	if not template_key:
		frappe.throw(_("Template key is required"))

	surface_key = _normalize_schedule_surface(surface)
	_assert_schedule_access(store, surface_key)
	store_context = _resolve_labor_plan_store(store)
	employees = _get_labor_plan_employees(store_context)
	shift_options = get_shift_options_for_store(store_context["warehouse_name"])

	try:
		applied = apply_template_to_employees(
			template_key,
			surface_key,
			employees,
			shift_options,
			week_start=week_start,
		)
	except KeyError:
		frappe.throw(_("Template {0} is not available for this location.").format(template_key))

	return {
		"store": store_context["warehouse"],
		"warehouse_name": store_context["warehouse_name"],
		"surface": surface_key,
		"week_start": week_start,
		"template": applied["template"],
		"shifts": applied["shifts"],
		"warnings": applied["warnings"],
		"shift_count": len(applied["shifts"]),
	}


@frappe.whitelist()
def create_weekly_plan(
	store: str,
	week_start: str,
	shifts: str | list[dict[str, Any]],
	labor_budget: float | int | str | None = None,
	surface: str | None = None,
):
	"""Create a weekly labor plan."""
	if not store:
		frappe.throw(_("Store is required"))

	surface_key = _normalize_schedule_surface(surface)
	_assert_schedule_access(store, surface_key)
	shifts = _coerce_shifts(shifts)
	store_context = _resolve_labor_plan_store(store)

	doc = frappe.new_doc("BEI Weekly Labor Plan")
	doc.store = store_context["warehouse"]
	doc.week_start_date = week_start
	doc.week_end_date = add_days(week_start, 6)
	doc.planned_by = frappe.session.user
	doc.labor_budget = float(labor_budget) if labor_budget else 0

	total_hours = _apply_shifts(doc, shifts)
	doc.status = "Draft"
	doc.insert()
	return {"success": True, "name": doc.name, "total_hours": total_hours}


@frappe.whitelist()
def get_weekly_plan(store: str | None = None, week_start: str | None = None, surface: str | None = None):
	"""Get weekly labor plan for a store."""
	if not store or not week_start:
		return {"plan": None}

	store_context = _resolve_labor_plan_store(store)
	_assert_schedule_access(store_context["warehouse"], surface)

	plans = frappe.get_all(
		"BEI Weekly Labor Plan",
		filters={"store": store_context["warehouse"], "week_start_date": week_start},
		fields=["name", "status", "total_hours", "planned_by"],
	)

	if plans:
		doc = frappe.get_doc("BEI Weekly Labor Plan", plans[0].name)
		return {"plan": doc.as_dict()}
	return {"plan": None}


def _default_week_start_value():
	today = getdate(nowdate())
	return str(add_days(today, -today.weekday()))


@frappe.whitelist()
def get_area_schedule_overview(week_start: str | None = None):
	"""Return a cross-store weekly schedule overview for area supervisors and HR."""
	user_roles = set(frappe.get_roles(frappe.session.user))
	allowed_roles = {"Area Supervisor", "HR User", "HR Manager", "System Manager", "Administrator"}
	if not user_roles.intersection(allowed_roles):
		frappe.throw(_("You do not have permission to view the area labor overview."), frappe.PermissionError)

	normalized_week_start = str(getdate(week_start)) if week_start else _default_week_start_value()
	week_end = str(add_days(normalized_week_start, 6))

	current_employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user, "status": "Active"},
		["designation"],
		as_dict=True,
	)
	is_area_persona = "Area Supervisor" in user_roles or _designation_is_area_supervisor(
		(current_employee or {}).get("designation")
	)
	if is_area_persona:
		from hrms.api.store import _get_store_schedule_locations, get_user_store

		store_payload = get_user_store(surface=SCHEDULE_SURFACE_STORE) or {}
		stores = store_payload.get("stores") or []
		if not stores and user_roles.intersection({"HR User", "HR Manager", "System Manager", "Administrator"}):
			stores = _get_store_schedule_locations()
	else:
		from hrms.api.store import _get_store_schedule_locations

		stores = _get_store_schedule_locations()

	items = []
	status_counter: Counter[str] = Counter()
	total_hours = 0.0
	total_cost = 0.0
	total_locations = 0
	total_missing_locations = 0

	for store in stores:
		store_name = store.get("name") if isinstance(store, dict) else store.name
		warehouse_name = (
			store.get("warehouse_name") if isinstance(store, dict) else getattr(store, "warehouse_name", None)
		) or store_name
		if not store_name:
			continue

		total_locations += 1
		store_context = _resolve_labor_plan_store(store_name)
		employees = _get_labor_plan_employees(store_context)
		hourly_rates = {row.get("name"): row.get("hour_rate") for row in employees if row.get("name")}

		plan_rows = frappe.get_all(
			"BEI Weekly Labor Plan",
			filters={"store": store_context["warehouse"], "week_start_date": normalized_week_start},
			fields=["name", "status", "total_hours", "labor_budget", "planned_by"],
			order_by="creation desc",
			limit=1,
		)
		plan_meta = plan_rows[0] if plan_rows else None
		plan_doc = frappe.get_doc("BEI Weekly Labor Plan", plan_meta["name"]) if plan_meta else None
		plan_shifts = list(plan_doc.shifts) if plan_doc else []
		coverage_days = {
			row.day_of_week for row in plan_shifts if not cint(getattr(row, "is_off", 0)) and row.day_of_week
		}
		scheduled_employees = {
			row.employee for row in plan_shifts if not cint(getattr(row, "is_off", 0)) and row.employee
		}
		status = plan_meta.get("status") if plan_meta else "Missing"
		empty_days = [day for day in DAY_OFFSETS if day not in coverage_days]
		warning_count = 0
		if not plan_meta:
			warning_count += 1
		if empty_days:
			warning_count += len(empty_days)
		if plan_meta and flt(plan_meta.get("total_hours")) > flt(plan_meta.get("labor_budget") or 0):
			warning_count += 1

		location_cost = _calculate_plan_cost(plan_shifts, hourly_rates) if plan_meta else 0.0
		location_hours = flt(plan_meta.get("total_hours")) if plan_meta else 0.0
		status_counter[status] += 1
		total_hours += location_hours
		total_cost += location_cost
		if status == "Missing":
			total_missing_locations += 1

		items.append(
			{
				"store": store_context["warehouse"],
				"warehouse_name": warehouse_name,
				"status": status,
				"plan_name": plan_meta.get("name") if plan_meta else None,
				"planned_by": plan_meta.get("planned_by") if plan_meta else None,
				"roster_count": len(employees),
				"scheduled_employee_count": len(scheduled_employees),
				"unscheduled_employee_count": max(len(employees) - len(scheduled_employees), 0),
				"coverage_days": sorted(coverage_days, key=lambda day: DAY_OFFSETS.get(day, 99)),
				"empty_days": empty_days,
				"warning_count": warning_count,
				"total_hours": location_hours,
				"labor_budget": flt(plan_meta.get("labor_budget")) if plan_meta else 0.0,
				"total_cost": location_cost,
			}
		)

	items.sort(key=lambda item: (item["status"] == "Missing", item["warehouse_name"]))

	return {
		"week_start": normalized_week_start,
		"week_end": week_end,
		"items": items,
		"summary": {
			"locations": total_locations,
			"missing_locations": total_missing_locations,
			"draft_locations": status_counter.get("Draft", 0),
			"published_locations": status_counter.get("Published", 0),
			"total_hours": round(total_hours, 2),
			"total_cost": round(total_cost, 2),
		},
	}


@frappe.whitelist()
def create_team_attendance_request(
	employee: str,
	attendance_date: str,
	reason: str,
	explanation: str | None = None,
	shift: str | None = None,
):
	"""Create and submit a same-day office exception for a direct report."""
	if reason not in {"Work From Home", "On Duty"}:
		frappe.throw(_("Reason must be Work From Home or On Duty."))

	target_employee = frappe.db.get_value(
		"Employee",
		employee,
		["name", "employee_name", "reports_to", "status", "company"],
		as_dict=True,
	)
	if not target_employee or target_employee.get("status") != "Active":
		frappe.throw(_("Employee {0} is not active.").format(employee))

	current_roles = set(frappe.get_roles(frappe.session.user))
	current_employee = _get_current_employee()
	allowed = bool(current_roles.intersection({"HQ User", "HR User", "HR Manager", "System Manager", "Administrator"}))
	if current_employee and target_employee.get("reports_to") == current_employee.get("name"):
		allowed = True
	if not allowed:
		frappe.throw(
			_("You do not have permission to manage office schedule exceptions for {0}.").format(employee),
			frappe.PermissionError,
		)

	request_date = str(getdate(attendance_date))
	doc = frappe.get_doc(
		{
			"doctype": "Attendance Request",
			"employee": target_employee["name"],
			"from_date": request_date,
			"to_date": request_date,
			"reason": reason,
			"explanation": explanation
			or _("Created from Office Team Schedule by {0}.").format(frappe.session.user),
			"company": target_employee.get("company"),
			"shift": shift,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	doc.add_comment(
		"Info",
		text=_("{0} submitted this {1} request from the Office Team Schedule surface.").format(
			frappe.session.user, reason
		),
	)

	return {"success": True, "name": doc.name, "reason": doc.reason, "attendance_date": request_date}


@frappe.whitelist()
def copy_weekly_plan_from_previous_week(
	store: str,
	target_week_start: str,
	surface: str | None = None,
):
	"""Copy the most recent published weekly labor plan before the target week."""
	if not store or not target_week_start:
		frappe.throw(_("Store and target week start are required."))

	store_context = _resolve_labor_plan_store(store)
	_assert_schedule_access(store_context["warehouse"], surface)

	plans = frappe.get_all(
		"BEI Weekly Labor Plan",
		filters={
			"store": store_context["warehouse"],
			"status": "Published",
			"week_start_date": ["<", target_week_start],
		},
		fields=["name", "week_start_date"],
		order_by="week_start_date desc",
		limit=1,
	)
	if not plans:
		return {
			"success": False,
			"error": "no_previous_week",
			"message": _("No previous schedule found for this location."),
		}

	source_plan_meta = plans[0]
	source_plan_name = source_plan_meta.get("name") if isinstance(source_plan_meta, dict) else source_plan_meta.name
	source_week = (
		source_plan_meta.get("week_start_date")
		if isinstance(source_plan_meta, dict)
		else source_plan_meta.week_start_date
	)
	source_plan = frappe.get_doc("BEI Weekly Labor Plan", source_plan_name)
	active_roster = {
		row.get("name"): row
		for row in _get_labor_plan_employees(store_context)
		if row.get("name")
	}
	copied_shifts = []
	warnings = []
	source_employee_names = set()
	for row in source_plan.shifts:
		source_employee_names.add(row.employee)
		if row.employee not in active_roster:
			warnings.append(
				{
					"code": "transferred_out",
					"level": "warning",
					"message": _("Removed {0} because they are no longer on this roster.").format(
						row.employee_name or row.employee
					),
					"employee": row.employee,
				}
			)
			continue
		copied_shifts.append(
			{
				"employee": row.employee,
				"employee_name": row.employee_name,
				"day_of_week": row.day_of_week,
				"shift_type_name": row.shift_type_name or row.shift_type,
				"shift_start": row.shift_start,
				"shift_end": row.shift_end,
				"is_off": cint(row.is_off),
				"ends_next_day": cint(row.ends_next_day),
				"hours": row.hours
				or _calculate_shift_hours(row.shift_start, row.shift_end, row.is_off),
				"notes": row.notes,
			}
		)

	for employee_name, employee_row in active_roster.items():
		if employee_name in source_employee_names:
			continue
		warnings.append(
			{
				"code": "new_hire",
				"level": "info",
				"message": _("Added {0} as an empty row because they were not on the previous week.").format(
					employee_row.get("employee_name") or employee_name
				),
				"employee": employee_name,
			}
		)

	return {
		"success": True,
		"shifts": copied_shifts,
		"source_week": source_week,
		"source_plan": source_plan.name,
		"shift_count": len(copied_shifts),
		"warnings": warnings,
	}


@frappe.whitelist()
def update_weekly_plan(plan_name: str, shifts: str | list[dict[str, Any]], surface: str | None = None):
	"""Update shifts in a weekly plan."""
	shifts = _coerce_shifts(shifts)
	doc = frappe.get_doc("BEI Weekly Labor Plan", plan_name)
	_assert_schedule_access(doc.store, surface)
	doc.shifts = []

	total_hours = _apply_shifts(doc, shifts)
	doc.status = "Draft"
	doc.approved_by = None
	doc.rejection_reason = None
	doc.rejected_by = None
	doc.save(ignore_permissions=True)
	return {"success": True, "total_hours": total_hours}


@frappe.whitelist()
def publish_weekly_plan(plan_name: str, surface: str | None = None):
	"""Publish a weekly labor plan and sync tagged Shift Assignments."""
	plan = frappe.get_doc("BEI Weekly Labor Plan", plan_name)
	inferred_surface = surface or (
		SCHEDULE_SURFACE_COMMISSARY if _is_commissary_schedule_store(plan.store) else SCHEDULE_SURFACE_STORE
	)
	_assert_schedule_access(plan.store, inferred_surface)

	current_rows = []
	current_keys = set()
	ShiftAssignment = frappe.qb.DocType("Shift Assignment")
	existing_assignments = (
		frappe.qb.from_(ShiftAssignment)
		.select(
			ShiftAssignment.name,
			ShiftAssignment.employee,
			ShiftAssignment.shift_type,
			ShiftAssignment.start_date,
			ShiftAssignment.end_date,
			ShiftAssignment.docstatus,
			ShiftAssignment.custom_bei_weekly_plan_row_key,
		)
		.where(
			(ShiftAssignment.custom_bei_schedule_source == SCHEDULE_SOURCE)
			& (ShiftAssignment.custom_bei_weekly_labor_plan == plan.name)
		)
	).run(as_dict=True)
	existing_by_key = {
		assignment.custom_bei_weekly_plan_row_key: assignment
		for assignment in existing_assignments
		if assignment.custom_bei_weekly_plan_row_key
	}

	conflicts = []
	for row in plan.shifts:
		if cint(row.is_off):
			continue

		work_date = _get_work_date(plan.week_start_date, row.day_of_week)
		row_key = f"{row.employee}|{work_date}"
		if row_key in current_keys:
			conflicts.append(_("Duplicate schedule row for {0} on {1}.").format(row.employee, work_date))
			continue

		row_conflicts = _get_shift_assignment_conflicts(row.employee, work_date, row_key, plan.name)
		if row_conflicts:
			conflict_names = ", ".join(conflict.name for conflict in row_conflicts)
			conflicts.append(
				_("Employee {0} already has Shift Assignment(s) on {1}: {2}").format(
					row.employee, work_date, conflict_names
				)
			)
			continue

		current_keys.add(row_key)
		current_rows.append((row, work_date, row_key))

	if conflicts:
		frappe.throw("<br>".join(conflicts), title=_("Publish blocked by assignment conflicts"))

	publish_run_id = str(now_datetime())
	created = 0
	updated = 0
	unchanged = 0
	notifications: dict[str, list[dict[str, Any]]] = {}

	for row, work_date, row_key in current_rows:
		shift_type_name = row.shift_type_name or row.shift_type
		existing = existing_by_key.get(row_key)

		if (
			existing
			and existing.shift_type == shift_type_name
			and str(existing.start_date) == work_date
			and str(existing.end_date or existing.start_date) == work_date
		):
			unchanged += 1
			continue

		if existing:
			_cancel_and_delete_shift_assignment(existing.name)
			updated += 1
			notifications.setdefault(row.employee, []).append(
				{
					"type": "updated",
					"work_date": work_date,
					"old_shift": existing.shift_type,
					"new_shift": shift_type_name,
				}
			)
		else:
			created += 1
			notifications.setdefault(row.employee, []).append(
				{
					"type": "created",
					"work_date": work_date,
					"new_shift": shift_type_name,
				}
			)

		_create_shift_assignment_from_plan(plan, row, work_date, publish_run_id)

	deleted = 0
	for row_key, assignment in existing_by_key.items():
		if row_key in current_keys:
			continue
		_cancel_and_delete_shift_assignment(assignment.name)
		deleted += 1
		if assignment.employee:
			notifications.setdefault(assignment.employee, []).append(
				{
					"type": "deleted",
					"work_date": str(assignment.start_date),
					"old_shift": assignment.shift_type,
				}
			)

	plan.status = "Published"
	plan.approved_by = None
	plan.rejection_reason = None
	plan.rejected_by = None
	plan.save(ignore_permissions=True)
	_send_published_schedule_notifications(plan, notifications)

	return {
		"success": True,
		"created": created,
		"updated": updated,
		"deleted": deleted,
		"unchanged": unchanged,
		"status": plan.status,
	}


# ==============================================================================
# TEAM MANAGEMENT
# ==============================================================================


@frappe.whitelist()
def get_my_team():
	"""Get employees who report to current user."""
	user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not user_employee:
		return {"team": []}

	team = frappe.get_all(
		"Employee",
		filters={"reports_to": user_employee, "status": "Active"},
		fields=["name", "employee_name", "designation", "branch", "user_id", "image"],
	)
	return {"team": team}


@frappe.whitelist()
def get_team_attendance(date: str | None = None):
	"""Get attendance overview for team."""
	if not date:
		date = nowdate()

	user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not user_employee:
		return {"attendance": []}

	# Get team members
	team = frappe.get_all(
		"Employee",
		filters={"reports_to": user_employee, "status": "Active"},
		fields=["name", "employee_name"],
	)

	attendance = []
	for member in team:
		# Get latest checkin for the day
		checkins = frappe.get_all(
			"Employee Checkin",
			filters={"employee": member.name, "time": ["like", f"{date}%"]},
			fields=["time", "log_type"],
			order_by="time asc",
		)

		attendance.append(
			{
				"employee": member.name,
				"employee_name": member.employee_name,
				"checkins": checkins,
				"status": "Present" if checkins else "Absent",
			}
		)

	return {"date": date, "attendance": attendance}


# ==============================================================================
# UNIFIED APPROVAL QUEUE
# ==============================================================================


@frappe.whitelist()
def get_unified_approval_queue(approver: str | None = None, store: str | None = None):
	"""Get all pending items requiring approval from various sources."""
	if not approver:
		approver = frappe.session.user

	items = []

	# 1. Store Orders pending approval
	try:
		order_filters = {"status": "Pending Approval"}
		if store:
			order_filters["store"] = store

		orders = frappe.get_all(
			"BEI Store Order",
			filters=order_filters,
			fields=["name", "store", "order_date", "submitted_by", "creation", "total_amount"],
		)
		for order in orders:
			items.append(
				{
					"type": "store_order",
					"name": order.name,
					"store": order.store,
					"submitted_by": order.submitted_by,
					"submitted_at": str(order.creation) if order.creation else None,
					"title": f"Store Order: {order.name}",
					"description": f"Total: {order.total_amount or 0}",
					"order_date": str(order.order_date) if order.order_date else None,
				}
			)
	except Exception:
		pass  # DocType may not exist

	# 2. Leave Applications pending (supervisor's team)
	try:
		employee = frappe.db.get_value("Employee", {"user_id": approver}, "name")
		if employee:
			# Get direct reports
			direct_reports = frappe.get_all(
				"Employee", filters={"reports_to": employee, "status": "Active"}, pluck="name"
			)
			if direct_reports:
				leaves = frappe.get_all(
					"Leave Application",
					filters={"status": "Open", "employee": ["in", direct_reports]},
					fields=[
						"name",
						"employee",
						"employee_name",
						"leave_type",
						"from_date",
						"to_date",
						"creation",
						"total_leave_days",
					],
				)
				for leave in leaves:
					items.append(
						{
							"type": "leave_request",
							"name": leave.name,
							"employee": leave.employee,
							"employee_name": leave.employee_name,
							"leave_type": leave.leave_type,
							"dates": f"{leave.from_date} to {leave.to_date}",
							"total_days": leave.total_leave_days,
							"submitted_at": str(leave.creation) if leave.creation else None,
							"title": f"Leave: {leave.employee_name} - {leave.leave_type}",
							"description": f"{leave.total_leave_days} day(s)",
						}
					)
	except Exception:
		pass

	# 3. Coverage Requests pending
	try:
		coverage_filters = {"status": "Pending"}
		if store:
			coverage_filters["store"] = store

		coverage = frappe.get_all(
			"BEI Staff Coverage Request",
			filters=coverage_filters,
			fields=[
				"name",
				"store",
				"coverage_date",
				"shift",
				"requested_by",
				"creation",
				"absent_employee",
				"reason",
			],
		)
		for req in coverage:
			items.append(
				{
					"type": "coverage_request",
					"name": req.name,
					"store": req.store,
					"coverage_date": str(req.coverage_date) if req.coverage_date else None,
					"shift": req.shift,
					"absent_employee": req.absent_employee,
					"reason": req.reason,
					"submitted_at": str(req.creation) if req.creation else None,
					"title": f"Coverage: {req.store} - {req.shift}",
					"description": f"For {req.absent_employee}",
				}
			)
	except Exception:
		pass

	# 4. Onboarding requests pending
	try:
		onboarding = frappe.get_all(
			"BEI Onboarding Request",
			filters={"status": "Pending"},
			fields=["name", "employee", "employee_name", "store", "creation"],
		)
		for req in onboarding:
			items.append(
				{
					"type": "onboarding_request",
					"name": req.name,
					"employee": req.employee,
					"employee_name": req.employee_name,
					"store": req.store,
					"submitted_at": str(req.creation) if req.creation else None,
					"title": f"Onboarding: {req.employee_name}",
					"description": f"New employee at {req.store}",
				}
			)
	except Exception:
		pass

	# 5. Transfer Requests (stage-aware routing)
	try:
		import hrms.api.transfer_requests as transfer_api

		user_roles = set(frappe.get_roles(approver))
		stage_filters = []
		if user_roles.intersection(transfer_api.AREA_APPROVER_ROLES):
			stage_filters.append(transfer_api.STAGE_PENDING_AREA)
		if user_roles.intersection(transfer_api.HR_APPROVER_ROLES):
			stage_filters.extend(
				[
					transfer_api.STAGE_PENDING_HR,
					transfer_api.STAGE_WAITING_EFFECTIVE,
				]
			)
		if user_roles.intersection(transfer_api.IT_APPROVER_ROLES):
			stage_filters.append(transfer_api.STAGE_PENDING_IT)

		if stage_filters:
			filters = {"current_stage": ["in", list(dict.fromkeys(stage_filters))]}
			if store:
				filters["store_warehouse"] = store

			transfers = frappe.get_all(
				TRANSFER_REQUEST_DOCTYPE,
				filters=filters,
				fields=[
					"name",
					"employee",
					"employee_name",
					"requested_by",
					"requested_on",
					"effective_date",
					"current_stage",
					"to_branch",
					"store_warehouse",
				],
				order_by="requested_on desc",
			)
			for req in transfers:
				effective_label = str(req.effective_date) if req.effective_date else "N/A"
				items.append(
					{
						"type": "transfer_request",
						"name": req.name,
						"employee": req.employee,
						"employee_name": req.employee_name,
						"stage": req.current_stage,
						"store": req.store_warehouse,
						"store_warehouse": req.store_warehouse,
						"to_branch": req.to_branch,
						"effective_date": effective_label,
						"submitted_by": req.requested_by,
						"submitted_at": str(req.requested_on) if req.requested_on else None,
						"title": f"Transfer: {req.employee_name or req.employee}",
						"description": f"{req.current_stage} - Effective {effective_label}",
					}
				)
	except Exception:
		pass

	# 7. Opening/Closing Reports (for area supervisors)
	try:
		# Get stores under this area supervisor
		supervisor_stores = _get_area_supervisor_stores(approver)
		store_names = [s.name for s in supervisor_stores]

		if store_names:
			# Opening reports pending review
			opening_reports = frappe.get_all(
				"BEI Store Opening Report",
				filters={"store": ["in", store_names], "status": "Submitted"},
				fields=["name", "store", "report_date", "report_time", "submitted_by", "creation"],
			)
			for report in opening_reports:
				submitter_name = (
					frappe.db.get_value("User", report.submitted_by, "full_name") or report.submitted_by
				)
				items.append(
					{
						"type": "opening_report",
						"name": report.name,
						"store": report.store,
						"report_date": str(report.report_date) if report.report_date else None,
						"report_time": str(report.report_time) if report.report_time else None,
						"submitted_by": report.submitted_by,
						"submitted_by_name": submitter_name,
						"submitted_at": str(report.creation) if report.creation else None,
						"title": f"Opening Report: {report.store}",
						"description": f"Submitted at {report.report_time} by {submitter_name}",
					}
				)

			# Closing reports pending review
			closing_reports = frappe.get_all(
				"BEI Store Closing Report",
				filters={"store": ["in", store_names], "status": "Submitted"},
				fields=[
					"name",
					"store",
					"report_date",
					"report_time",
					"submitted_by",
					"creation",
					"cash_variance",
				],
			)
			for report in closing_reports:
				submitter_name = (
					frappe.db.get_value("User", report.submitted_by, "full_name") or report.submitted_by
				)
				variance_note = ""
				if report.cash_variance and abs(float(report.cash_variance)) > 100:
					variance_note = f" - Variance: PHP {report.cash_variance}"
				items.append(
					{
						"type": "closing_report",
						"name": report.name,
						"store": report.store,
						"report_date": str(report.report_date) if report.report_date else None,
						"report_time": str(report.report_time) if report.report_time else None,
						"submitted_by": report.submitted_by,
						"submitted_by_name": submitter_name,
						"cash_variance": float(report.cash_variance) if report.cash_variance else 0,
						"submitted_at": str(report.creation) if report.creation else None,
						"title": f"Closing Report: {report.store}",
						"description": f"Submitted at {report.report_time} by {submitter_name}{variance_note}",
					}
				)
	except Exception:
		pass

	# Sort by creation date (most recent first)
	items.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)

	return {"items": items, "count": len(items)}


# ==============================================================================
# AREA SUPERVISOR - STORE REPORTS
# ==============================================================================


def _get_area_supervisor_stores(user: str | None = None):
	"""Get stores (warehouses) assigned to the area supervisor."""
	if not user:
		user = frappe.session.user

	stores = frappe.get_all(
		"Warehouse",
		filters={"custom_area_supervisor": user, "is_group": 0},
		fields=["name", "warehouse_name"],
		order_by="warehouse_name",
	)
	return stores


@frappe.whitelist()
def get_my_stores(user: str | None = None):
	"""
	Get stores (warehouses) assigned to the area supervisor.
	Used by store dropdowns in Store Visit, Reports, and Action Plans forms.

	Args:
	    user: Optional user email to get stores for (defaults to current session user)

	Returns:
	    {"stores": [{"name": str, "warehouse_name": str, "custom_area_supervisor": str, "is_group": int}]}
	"""
	stores = _get_area_supervisor_stores(user)

	# Enrich with required fields for frontend
	result = []
	for store in stores:
		result.append(
			{
				"name": store.name,
				"warehouse_name": store.warehouse_name,
				"custom_area_supervisor": frappe.session.user,
				"is_group": 0,
			}
		)

	return {"stores": result}


@frappe.whitelist()
def get_area_dashboard():
	"""
	Get area supervisor dashboard data including stores list and statistics.
	Main endpoint for the supervisor dashboard page.

	Returns:
	    {
	        "stats": SupervisorDashboardStats,
	        "stores": [SupervisorStore]
	    }
	"""
	from frappe.utils import add_days, getdate

	user = frappe.session.user
	stores = _get_area_supervisor_stores(user)
	store_names = [s.name for s in stores]

	today = nowdate()
	week_start = add_days(today, -getdate(today).weekday())

	# Initialize stats with defaults
	stats = {
		"total_stores": len(stores),
		"pending_approvals": 0,
		"reports_today": {
			"opening": {"submitted": 0, "missing": 0, "reviewed": 0, "revision_requested": 0},
			"closing": {"submitted": 0, "missing": 0, "reviewed": 0, "revision_requested": 0},
		},
		"open_action_plans": 0,
		"overdue_action_plans": 0,
		"cash_variance_alerts": 0,
		"visits_this_week": 0,
		"avg_store_score": None,
	}

	# Enrich stores for response
	enriched_stores = []
	for store in stores:
		enriched_stores.append(
			{
				"name": store.name,
				"warehouse_name": store.warehouse_name,
				"custom_area_supervisor": user,
				"is_group": 0,
			}
		)

	if not store_names:
		return {"stats": stats, "stores": enriched_stores}

	# Count pending approvals
	try:
		queue_result = get_unified_approval_queue(approver=user)
		stats["pending_approvals"] = queue_result.get("count", 0)
	except Exception:
		pass

	# Count opening reports for today
	_count_reports_by_status(stats, "opening", "BEI Store Opening Report", store_names, today)

	# Count closing reports for today
	_count_reports_by_status(stats, "closing", "BEI Store Closing Report", store_names, today)

	# Count action plans
	try:
		stats["open_action_plans"] = frappe.db.count(
			"BEI Action Plan", {"store": ["in", store_names], "status": ["in", ["Open", "In Progress"]]}
		)
		stats["overdue_action_plans"] = frappe.db.count(
			"BEI Action Plan",
			{
				"store": ["in", store_names],
				"status": ["in", ["Open", "In Progress"]],
				"due_date": ["<", today],
			},
		)
	except Exception:
		pass

	# Count cash variance alerts (variance > 100 or < -100)
	try:
		stats["cash_variance_alerts"] = frappe.db.count(
			"BEI Store Closing Report",
			{"store": ["in", store_names], "report_date": today, "cash_variance": [">", 100]},
		) + frappe.db.count(
			"BEI Store Closing Report",
			{"store": ["in", store_names], "report_date": today, "cash_variance": ["<", -100]},
		)
	except Exception:
		pass

	# Count store visits this week
	try:
		stats["visits_this_week"] = frappe.db.count(
			"BEI Store Visit Report", {"store": ["in", store_names], "visit_date": [">=", week_start]}
		)

		# Average store score from recent visits
		recent_visits = frappe.get_all(
			"BEI Store Visit Report",
			filters={"store": ["in", store_names]},
			fields=["overall_score"],
			limit=20,
			order_by="visit_date desc",
		)
		if recent_visits:
			scores = [v.overall_score for v in recent_visits if v.overall_score]
			if scores:
				stats["avg_store_score"] = round(sum(scores) / len(scores), 1)
	except Exception:
		pass

	return {"stats": stats, "stores": enriched_stores}


def _count_reports_by_status(
	stats: dict[str, Any], report_key: str, doctype: str, store_names: list[str], today: str
):
	"""Helper to count reports by status for a given doctype."""
	total_stores = len(store_names)
	submitted = reviewed = flagged = 0

	try:
		for status in ["Submitted", "Reviewed", "Flagged"]:
			count = frappe.db.count(
				doctype, {"store": ["in", store_names], "report_date": today, "status": status}
			)
			if status == "Submitted":
				submitted = count
			elif status == "Reviewed":
				reviewed = count
			elif status == "Flagged":
				flagged = count
	except Exception:
		pass

	stats["reports_today"][report_key]["submitted"] = submitted
	stats["reports_today"][report_key]["reviewed"] = reviewed
	stats["reports_today"][report_key]["revision_requested"] = flagged
	stats["reports_today"][report_key]["missing"] = max(0, total_stores - submitted - reviewed - flagged)


@frappe.whitelist()
def get_area_store_reports(report_type: str, report_date: str | None = None, status: str | None = None):
	"""
	Get store reports for all stores under the area supervisor.
	Returns reports with photo URLs and a list of stores that haven't submitted.

	Args:
	    report_type: 'opening', 'closing', 'midshift', 'pos_upload', or 'bank_deposit'
	    report_date: Date to filter by (defaults to today)
	    status: Optional status filter ('Submitted', 'Reviewed', 'Flagged')

	Returns:
	    {reports: [...], stores: [...], stores_missing: [...], stats: {...}}
	"""
	if not report_date:
		report_date = nowdate()

	# Get stores under this area supervisor
	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {
			"reports": [],
			"stores": [],
			"stores_missing": [],
			"stats": {"total": 0, "submitted": 0, "missing": 0},
		}

	# Report type configuration
	report_config = {
		"opening": {
			"doctype": "BEI Store Opening Report",
			"date_field": "report_date",
			"time_field": "report_time",
			"submitter_field": "submitted_by",
			"photo_fields": [
				"photo_backup_area",
				"photo_frozen_milk",
				"photo_toppings_area",
				"photo_dispatch_area",
				"photo_cold_storage_temp",
			],
			"extra_fields": [],
		},
		"closing": {
			"doctype": "BEI Store Closing Report",
			"date_field": "report_date",
			"time_field": "report_time",
			"submitter_field": "submitted_by",
			"photo_fields": [
				"photo_xread_opening",
				"photo_xread_closing",
				"photo_zread",
				"photo_closing_reports",
				"photo_dashboard_report",
				"photo_logo_signage",
				"photo_hygrometer",
				"photo_water_meter",
				"photo_backup_area_clean",
				"photo_frozen_milk_clean",
				"photo_toppings_clean",
				"photo_dispatch_clean",
				"photo_cold_storage_close",
				"photo_cashier_clean",
				"photo_rollup_closed",
			],
			"extra_fields": [
				"pos_total_sales",
				"actual_cash_count",
				"card_payments",
				"gcash_total",
				"cash_variance",
				"variance_explanation",
			],
		},
		"midshift": {
			"doctype": "BEI Midshift Checklist",
			"date_field": "check_datetime",  # Datetime field - will extract date
			"time_field": "check_datetime",  # Will extract time
			"submitter_field": "submitted_by",
			"photo_fields": ["photo_evidence"],
			"extra_fields": ["shift", "cleanliness_status", "issues_found", "corrective_action"],
		},
		"pos_upload": {
			"doctype": "BEI POS Upload",
			"date_field": "pos_date",
			"time_field": None,  # No time field
			"submitter_field": "uploaded_by",
			"photo_fields": [],  # No photos, has z_reading_file attachment
			"extra_fields": [
				"pos_system",
				"gross_sales",
				"net_sales",
				"transaction_count",
				"void_count",
				"void_amount",
				"discount_amount",
				"z_reading_file",
			],
		},
		"bank_deposit": {
			"doctype": "BEI Bank Deposit",
			"date_field": "deposit_date",
			"time_field": None,  # No time field
			"submitter_field": "submitted_by",
			"photo_fields": [],  # Photos are in child table
			"extra_fields": ["bank", "total_amount"],
		},
	}

	config = report_config.get(report_type)
	if not config:
		frappe.throw(f"Invalid report type: {report_type}")

	doctype = config["doctype"]
	date_field = config["date_field"]
	time_field = config["time_field"]
	submitter_field = config["submitter_field"]
	photo_fields = config["photo_fields"]
	extra_fields = config["extra_fields"]

	# Build filters based on date field type
	if report_type == "midshift":
		# For datetime field, filter by date portion
		filters = {
			"store": ["in", store_names],
			date_field: ["between", [f"{report_date} 00:00:00", f"{report_date} 23:59:59"]],
		}
	else:
		filters = {"store": ["in", store_names], date_field: report_date}

	if status:
		filters["status"] = status

	# Get base fields
	base_fields = [
		"name",
		"store",
		date_field,
		"creation",
		"notes" if frappe.db.has_column(doctype, "notes") else None,
	]
	base_fields = [f for f in base_fields if f]  # Remove None

	if time_field and time_field != date_field:
		base_fields.append(time_field)

	if submitter_field:
		base_fields.append(submitter_field)

	if frappe.db.has_column(doctype, "status"):
		base_fields.append("status")

	# Fetch reports — validate fields exist on DocType to avoid "Unknown column" errors
	all_fields = list(set(base_fields + extra_fields + photo_fields))
	all_fields = [f for f in all_fields if frappe.db.has_column(doctype, f)]
	reports = frappe.get_all(doctype, filters=filters, fields=all_fields, order_by="store asc, creation desc")

	# Transform reports
	for report in reports:
		# Normalize date/time fields
		if report_type == "midshift" and report.get("check_datetime"):
			dt = report.get("check_datetime")
			report["report_date"] = str(dt.date()) if hasattr(dt, "date") else str(dt)[:10]
			report["report_time"] = str(dt.time()) if hasattr(dt, "time") else str(dt)[11:19]
		elif date_field != "report_date":
			report["report_date"] = report.pop(date_field, None)
		if time_field and time_field != "report_time" and time_field != date_field:
			report["report_time"] = report.pop(time_field, None)
		elif not time_field:
			creation = report.get("creation")
			if creation:
				report["report_time"] = (
					str(creation.time())[:8] if hasattr(creation, "time") else str(creation)[11:19]
				)
			else:
				report["report_time"] = ""

		# Normalize submitter field
		submitter = report.get(submitter_field) or report.get("submitted_by") or report.get("uploaded_by")
		report["submitted_by"] = submitter
		if submitter:
			report["submitted_by_name"] = frappe.db.get_value("User", submitter, "full_name") or submitter
		else:
			report["submitted_by_name"] = "Unknown"

		# Structure photos as array
		photos = []
		for field in photo_fields:
			if report.get(field):
				label = field.replace("photo_", "").replace("_", " ").title()
				photos.append({"field": field, "label": label, "url": report.get(field)})
			report.pop(field, None)

		# For bank_deposit, get photos from child table
		if report_type == "bank_deposit":
			deposit_photos = frappe.get_all(
				"BEI Bank Deposit Photo", filters={"parent": report["name"]}, fields=["photo", "photo_number"]
			)
			for idx, dp in enumerate(deposit_photos):
				if dp.get("photo"):
					photos.append(
						{
							"field": f"deposit_photo_{idx}",
							"label": f"Deposit Slip {dp.get('photo_number') or idx + 1}",
							"url": dp.get("photo"),
						}
					)

		report["photos"] = photos

		# Ensure status field exists
		if "status" not in report:
			report["status"] = "Submitted"

	# Find stores that submitted
	submitted_stores = set(r["store"] for r in reports)

	# Find missing stores
	stores_missing = [
		{"name": s.name, "warehouse_name": s.warehouse_name} for s in stores if s.name not in submitted_stores
	]

	return {
		"reports": reports,
		"stores": [{"name": s.name, "warehouse_name": s.warehouse_name} for s in stores],
		"stores_missing": stores_missing,
		"stats": {"total": len(stores), "submitted": len(submitted_stores), "missing": len(stores_missing)},
	}


@frappe.whitelist()
def get_reports_feed(report_date: str | None = None, limit: int | str = 50):
	"""
	Get a chronological feed of all store reports for today (or specified date).
	Returns opening, closing, midshift, POS upload, and bank deposit reports
	across all stores under the supervisor's area, sorted newest first.

	Args:
	    report_date: Date to filter (defaults to today)
	    limit: Max items to return (default 50)

	Returns:
	    {reports: [{type, name, store, submitted_by, submitted_at, status, ...}]}
	"""
	if not report_date:
		report_date = nowdate()

	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {"reports": []}

	feed = []

	# Opening reports
	opening = frappe.get_all(
		"BEI Store Opening Report",
		filters={"store": ["in", store_names], "report_date": report_date},
		fields=["name", "store", "submitted_by", "report_time", "status", "creation"],
		order_by="creation desc",
		limit=int(limit),
	)
	for r in opening:
		r["report_type"] = "opening"
		r["submitted_at"] = str(r.get("report_time") or r.get("creation") or "")
		feed.append(r)

	# Closing reports
	closing = frappe.get_all(
		"BEI Store Closing Report",
		filters={"store": ["in", store_names], "report_date": report_date},
		fields=[
			"name",
			"store",
			"submitted_by",
			"report_time",
			"status",
			"cash_variance",
			"stage_completed",
			"creation",
		],
		order_by="creation desc",
		limit=int(limit),
	)
	for r in closing:
		r["report_type"] = "closing"
		r["submitted_at"] = str(r.get("report_time") or r.get("creation") or "")
		feed.append(r)

	# Midshift checklists
	midshift = frappe.get_all(
		"BEI Midshift Checklist",
		filters={
			"store": ["in", store_names],
			"check_datetime": ["between", [f"{report_date} 00:00:00", f"{report_date} 23:59:59"]],
		},
		fields=[
			"name",
			"store",
			"submitted_by",
			"shift",
			"cleanliness_status",
			"check_datetime as submitted_at",
			"creation",
		],
		order_by="creation desc",
		limit=int(limit),
	)
	for r in midshift:
		r["report_type"] = "midshift"
		r["status"] = r.get("cleanliness_status", "")
		feed.append(r)

	# POS uploads
	pos = frappe.get_all(
		"BEI POS Upload",
		filters={"store": ["in", store_names], "pos_date": report_date},
		fields=[
			"name",
			"store",
			"uploaded_by as submitted_by",
			"pos_system",
			"gross_sales",
			"net_sales",
			"status",
			"creation",
		],
		order_by="creation desc",
		limit=int(limit),
	)
	for r in pos:
		r["report_type"] = "pos_upload"
		r["submitted_at"] = str(r.get("creation") or "")
		feed.append(r)

	# Bank deposits
	deposits = frappe.get_all(
		"BEI Bank Deposit",
		filters={"store": ["in", store_names], "deposit_date": report_date},
		fields=["name", "store", "submitted_by", "bank", "total_amount", "status", "creation"],
		order_by="creation desc",
		limit=int(limit),
	)
	for r in deposits:
		r["report_type"] = "bank_deposit"
		r["submitted_at"] = str(r.get("creation") or "")
		feed.append(r)

	# Sort combined feed by creation time (newest first)
	feed.sort(key=lambda x: str(x.get("creation", "")), reverse=True)

	return {"reports": feed[: int(limit)]}


@frappe.whitelist()
def request_report_revision(report_name: str, doctype: str, revision_notes: str):
	"""
	Flag a report for revision and notify the submitter via Google Chat.

	Args:
	    report_name: Document name (e.g., 'BEI-OPEN-2026-00001')
	    doctype: 'BEI Store Opening Report' or 'BEI Store Closing Report'
	    revision_notes: Reason for requesting revision
	"""
	if not revision_notes:
		frappe.throw(_("Revision notes are required"))

	doc = frappe.get_doc(doctype, report_name)
	doc.status = "Flagged"
	doc.add_comment("Comment", text=f"Revision requested: {revision_notes}")
	doc.save()

	# Try to notify via Google Chat
	try:
		from hrms.api.google_chat import send_notification

		reviewer_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

		message = f"""*Report Revision Requested*
Store: {doc.store}
Report: {report_name}
Requested by: {reviewer_name}

Notes: {revision_notes}

Please review and resubmit."""

		send_notification(doc.submitted_by, message)
	except Exception:
		pass  # Notification is optional

	return {"success": True, "message": f"Report {report_name} flagged for revision"}


@frappe.whitelist()
def mark_report_reviewed(report_name: str, doctype: str):
	"""
	Mark a report as reviewed by the supervisor.

	Args:
	    report_name: Document name
	    doctype: 'BEI Store Opening Report' or 'BEI Store Closing Report'
	"""
	doc = frappe.get_doc(doctype, report_name)
	doc.status = "Reviewed"
	doc.add_comment("Comment", text=f"Reviewed by {frappe.session.user}")
	doc.save()

	return {"success": True, "message": f"Report {report_name} marked as reviewed"}


@frappe.whitelist()
def get_stores_compliance_summary(report_date: str | None = None):
	"""
	Get compliance summary for all stores under the area supervisor.
	Shows which stores submitted opening/closing reports and which are missing.

	Args:
	    report_date: Date to check (defaults to today)

	Returns:
	    {date, stores, opening: {submitted: [...], missing: [...]}, closing: {...}, stats: {...}}
	"""
	if not report_date:
		report_date = nowdate()

	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {
			"date": report_date,
			"stores": [],
			"opening": {"submitted": [], "missing": []},
			"closing": {"submitted": [], "missing": []},
			"stats": {"total": 0, "opening_submitted": 0, "closing_submitted": 0},
		}

	# Get opening reports
	opening_reports = frappe.get_all(
		"BEI Store Opening Report",
		filters={"store": ["in", store_names], "report_date": report_date},
		fields=["name", "store", "status", "report_time", "submitted_by"],
	)
	opening_submitted = {r.store: r for r in opening_reports}

	# Get closing reports
	closing_reports = frappe.get_all(
		"BEI Store Closing Report",
		filters={"store": ["in", store_names], "report_date": report_date},
		fields=["name", "store", "status", "report_time", "submitted_by", "cash_variance"],
	)
	closing_submitted = {r.store: r for r in closing_reports}

	# Build result
	opening_missing = []
	closing_missing = []

	for store in stores:
		if store.name not in opening_submitted:
			opening_missing.append({"name": store.name, "warehouse_name": store.warehouse_name})
		if store.name not in closing_submitted:
			closing_missing.append({"name": store.name, "warehouse_name": store.warehouse_name})

	return {
		"date": report_date,
		"stores": [{"name": s.name, "warehouse_name": s.warehouse_name} for s in stores],
		"opening": {"submitted": list(opening_submitted.values()), "missing": opening_missing},
		"closing": {"submitted": list(closing_submitted.values()), "missing": closing_missing},
		"stats": {
			"total": len(stores),
			"opening_submitted": len(opening_submitted),
			"opening_missing": len(opening_missing),
			"closing_submitted": len(closing_submitted),
			"closing_missing": len(closing_missing),
		},
	}


# ==============================================================================
# AREA SUPERVISOR - VARIANCE & ACTION PLANS (P1)
# ==============================================================================


@frappe.whitelist()
def get_variance_flagged_reports(
	threshold: float | int | str = 100,
	date_from: str | None = None,
	date_to: str | None = None,
):
	"""
	Get closing reports with cash variance exceeding the threshold.

	Args:
	    threshold: Variance threshold in PHP (default 100)
	    date_from: Optional start date
	    date_to: Optional end date (defaults to today)

	Returns:
	    {reports: [...], stats: {...}}
	"""
	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {"reports": [], "stats": {"total": 0, "over_threshold": 0, "under_threshold": 0}}

	if not date_to:
		date_to = nowdate()

	filters = {"store": ["in", store_names]}

	if date_from:
		filters["report_date"] = ["between", [date_from, date_to]]
	else:
		filters["report_date"] = ["<=", date_to]

	reports = frappe.get_all(
		"BEI Store Closing Report",
		filters=filters,
		fields=[
			"name",
			"store",
			"report_date",
			"report_time",
			"status",
			"submitted_by",
			"cash_variance",
			"variance_explanation",
		],
		order_by="report_date desc",
	)

	# Filter by threshold
	threshold = float(threshold)
	flagged_reports = []
	over_count = 0
	under_count = 0

	for report in reports:
		variance = abs(float(report.cash_variance or 0))
		if variance > threshold:
			report["submitted_by_name"] = (
				frappe.db.get_value("User", report.submitted_by, "full_name") or report.submitted_by
			)
			report["variance_abs"] = variance
			flagged_reports.append(report)
			over_count += 1
		else:
			under_count += 1

	return {
		"reports": flagged_reports,
		"threshold": threshold,
		"stats": {"total": len(reports), "over_threshold": over_count, "under_threshold": under_count},
	}


@frappe.whitelist()
def get_action_plans(store: str | None = None, status: str | None = None, limit: int | str = 50):
	"""
	Get action plans for stores under the area supervisor.

	Args:
	    store: Optional filter by specific store
	    status: Optional status filter ('Open', 'In Progress', 'Completed', 'Overdue')
	    limit: Max number of results

	Returns:
	    {plans: [...], stats: {...}}
	"""
	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {"plans": [], "stats": {"total": 0, "open": 0, "completed": 0}}

	filters = {"store": ["in", store_names]}

	if store:
		filters["store"] = store
	if status:
		filters["status"] = status

	plans = frappe.get_all(
		"BEI Action Plan",
		filters=filters,
		fields=[
			"name",
			"store",
			"issue_description",
			"action_required",
			"status",
			"priority",
			"created_date",
			"due_date",
			"completed_date",
			"assigned_to",
			"created_by",
			"source_visit",
			"completion_notes",
		],
		order_by="due_date asc, priority desc",
		limit=int(limit),
	)

	# Get stats
	open_count = sum(1 for p in plans if p.status in ("Open", "In Progress", "Overdue"))
	completed_count = sum(1 for p in plans if p.status == "Completed")

	# Enrich with user names
	for plan in plans:
		if plan.assigned_to:
			plan["assigned_to_name"] = (
				frappe.db.get_value("User", plan.assigned_to, "full_name") or plan.assigned_to
			)
		if plan.created_by:
			plan["created_by_name"] = (
				frappe.db.get_value("User", plan.created_by, "full_name") or plan.created_by
			)

	return {"plans": plans, "stats": {"total": len(plans), "open": open_count, "completed": completed_count}}


@frappe.whitelist()
def create_action_plan(
	store: str,
	issue_description: str,
	action_required: str,
	due_date: str,
	priority: str = "Medium",
	source_visit: str | None = None,
	assigned_to: str | None = None,
):
	"""
	Create a new action plan from a store visit or observation.

	Args:
	    store: Store (warehouse) name
	    issue_description: Brief description of the issue
	    action_required: What needs to be done
	    due_date: When it should be completed
	    priority: Low/Medium/High/Critical (default Medium)
	    source_visit: Optional link to store visit report
	    assigned_to: Optional user to assign to
	"""
	if not store or not issue_description or not action_required or not due_date:
		frappe.throw(_("Store, issue description, action required, and due date are all required"))

	doc = frappe.new_doc("BEI Action Plan")
	doc.store = store
	doc.issue_description = issue_description
	doc.action_required = action_required
	doc.due_date = due_date
	doc.priority = priority
	doc.source_visit = source_visit
	doc.assigned_to = assigned_to
	doc.created_by = frappe.session.user
	doc.created_date = nowdate()
	doc.status = "Open"
	doc.insert()

	return {"success": True, "name": doc.name}


@frappe.whitelist()
def update_action_plan_status(plan_name: str, status: str, completion_notes: str | None = None):
	"""
	Update the status of an action plan.

	Args:
	    plan_name: Action plan name
	    status: New status ('Open', 'In Progress', 'Completed', 'Cancelled')
	    completion_notes: Optional notes when completing
	"""
	doc = frappe.get_doc("BEI Action Plan", plan_name)
	doc.status = status
	if completion_notes:
		doc.completion_notes = completion_notes
	if status == "Completed":
		doc.completed_date = nowdate()
		doc.completed_by = frappe.session.user
	doc.save()

	return {"success": True, "message": f"Action plan {plan_name} updated to {status}"}


@frappe.whitelist()
def get_store_visit_template():
	"""
	Get the 100-point audit template for store visits.

	Returns the 5 categories with their items and point values.
	"""
	template = {
		"categories": [
			{
				"code": "A",
				"name": "Funds",
				"max_points": 20,
				"items": [
					{
						"name": "Cash fund intact",
						"points": 10,
						"description": "Opening fund matches cash on hand",
					},
					{
						"name": "Proper documentation",
						"points": 10,
						"description": "Receipts, logs, and records complete",
					},
				],
			},
			{
				"code": "B",
				"name": "Stocks",
				"max_points": 20,
				"items": [
					{
						"name": "No expired items",
						"points": 10,
						"description": "All products within expiry date",
					},
					{
						"name": "FIFO rotation",
						"points": 5,
						"description": "First-in-first-out properly followed",
					},
					{
						"name": "Temperature logged",
						"points": 5,
						"description": "Temperature readings recorded and within range",
					},
				],
			},
			{
				"code": "C",
				"name": "Organization/Maintenance",
				"max_points": 20,
				"items": [
					{"name": "Cleanliness", "points": 5, "description": "All areas clean and sanitized"},
					{"name": "Equipment working", "points": 5, "description": "All equipment operational"},
					{
						"name": "Waste management",
						"points": 10,
						"description": "Proper waste disposal and segregation",
					},
				],
			},
			{
				"code": "D",
				"name": "Staffing",
				"max_points": 20,
				"items": [
					{
						"name": "Proper equipment",
						"points": 5,
						"description": "Staff have required tools and safety equipment",
					},
					{
						"name": "Uniform compliance",
						"points": 5,
						"description": "Complete and clean uniform worn",
					},
					{
						"name": "Service sequence",
						"points": 10,
						"description": "Correct service flow followed",
					},
				],
			},
			{
				"code": "E",
				"name": "Coaching",
				"max_points": 20,
				"items": [
					{
						"name": "Improvements identified",
						"points": 10,
						"description": "Areas for improvement noted and discussed",
					},
					{
						"name": "On-the-spot coaching",
						"points": 10,
						"description": "Coaching provided during visit",
					},
				],
			},
		],
		"total_points": 100,
		"grading": [
			{"min": 90, "max": 100, "grade": "EXCELLENT"},
			{"min": 70, "max": 89, "grade": "SATISFACTORY"},
			{"min": 0, "max": 69, "grade": "NEEDS IMPROVEMENT"},
		],
	}

	return template


@frappe.whitelist()
def get_coaching_history(store: str | None = None, employee: str | None = None, limit: int | str = 20):
	"""
	Get coaching history for a store or employee.

	Args:
	    store: Optional store filter
	    employee: Optional employee filter
	    limit: Max results

	Returns:
	    {logs: [...]}
	"""
	stores = _get_area_supervisor_stores()
	store_names = [s.name for s in stores]

	if not store_names:
		return {"logs": []}

	filters = {"store": ["in", store_names]}
	if store:
		filters["store"] = store
	if employee:
		filters["employee"] = employee

	logs = frappe.get_all(
		"BEI Coaching Log",
		filters=filters,
		fields=[
			"name",
			"store",
			"coaching_date",
			"coaching_type",
			"employee",
			"coached_by",
			"topic",
			"coaching_remarks",
			"follow_up_required",
			"follow_up_date",
			"follow_up_status",
			"source_visit",
		],
		order_by="coaching_date desc",
		limit=int(limit),
	)

	# Enrich with names
	for log in logs:
		if log.employee:
			log["employee_name"] = frappe.db.get_value("Employee", log.employee, "employee_name")
		if log.coached_by:
			log["coached_by_name"] = (
				frappe.db.get_value("User", log.coached_by, "full_name") or log.coached_by
			)

	return {"logs": logs}


@frappe.whitelist()
def create_coaching_log(
	store: str,
	topic: str,
	coaching_remarks: str,
	employee: str | None = None,
	coaching_type: str = "On-the-spot",
	observations: str | None = None,
	follow_up_required: bool | int = False,
	follow_up_date: str | None = None,
	source_visit: str | None = None,
	source_action_plan: str | None = None,
):
	"""
	Create a new coaching log entry.

	Args:
	    store: Store (warehouse) name
	    topic: Coaching topic
	    coaching_remarks: Notes from coaching session
	    employee: Optional specific employee coached
	    coaching_type: On-the-spot/Scheduled/Follow-up/Performance Review
	    observations: What was observed
	    follow_up_required: Whether follow-up is needed
	    follow_up_date: When to follow up
	    source_visit: Optional link to store visit
	    source_action_plan: Optional link to action plan
	"""
	doc = frappe.new_doc("BEI Coaching Log")
	doc.store = store
	doc.coaching_date = nowdate()
	doc.coaching_type = coaching_type
	doc.employee = employee
	doc.coached_by = frappe.session.user
	doc.topic = topic
	doc.observations = observations
	doc.coaching_remarks = coaching_remarks
	doc.follow_up_required = follow_up_required
	doc.follow_up_date = follow_up_date
	doc.source_visit = source_visit
	doc.source_action_plan = source_action_plan
	doc.insert()

	return {"success": True, "name": doc.name}


# ==============================================================================
# STORE REPORTS - COMMENTS (for Reports Feed)
# ==============================================================================


@frappe.whitelist()
def add_report_comment(report_name: str, doctype: str, comment: str):
	"""
	Add a supervisor comment to a store report.

	Args:
	    report_name: Document name (e.g., 'BEI-OPEN-2026-00001')
	    doctype: 'BEI Store Opening Report' or 'BEI Store Closing Report'
	    comment: Comment text

	Returns:
	    {success: True, message: "Comment added", comment_name: "..."}
	"""
	if not comment:
		frappe.throw(_("Comment is required"))

	if doctype not in ["BEI Store Opening Report", "BEI Store Closing Report"]:
		frappe.throw(_("Invalid doctype"))

	# Verify the document exists
	if not frappe.db.exists(doctype, report_name):
		frappe.throw(_("Report not found"))

	# Create comment
	comment_doc = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": doctype,
			"reference_name": report_name,
			"content": comment,
		}
	)
	comment_doc.insert(ignore_permissions=True)

	return {"success": True, "message": "Comment added", "comment_name": comment_doc.name}


@frappe.whitelist()
def get_report_comments(report_name: str, doctype: str):
	"""
	Get all comments for a store report.

	Args:
	    report_name: Document name
	    doctype: 'BEI Store Opening Report' or 'BEI Store Closing Report'

	Returns:
	    {comments: [{name, content, owner, creation, owner_name}]}
	"""
	if doctype not in ["BEI Store Opening Report", "BEI Store Closing Report"]:
		frappe.throw(_("Invalid doctype"))

	comments = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": report_name, "comment_type": "Comment"},
		fields=["name", "content", "owner", "creation"],
		order_by="creation desc",
	)

	# Add owner names
	for c in comments:
		c["owner_name"] = frappe.db.get_value("User", c["owner"], "full_name") or c["owner"]

	return {"comments": comments}
