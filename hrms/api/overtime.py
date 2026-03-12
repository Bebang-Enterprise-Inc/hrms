from __future__ import annotations

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, get_time, getdate, now_datetime, nowdate

from hrms.api.store import resolve_employee_store_context
from hrms.utils.api_helpers import _paginate

OT_THRESHOLD_HOURS = 8.0
DEFAULT_FLEX_MINUTES = 30
FLEX_REASON = "Flex Exception"
FLEX_EARLY = "Early Start Validation"
FLEX_LATE = "Late Flex Exception"
OT_PENDING = "Pending Review"
OT_LEGACY_PENDING = "Pending Approval"
OT_NEEDS_INFO = "Needs Clarification"
OT_CLARIFIED = "Clarification Submitted"
OT_APPROVED = "Approved"
OT_REJECTED = "Rejected"
OT_ESCALATED = "Escalated"
OT_LOCKED = "Payroll Locked"
FLEX_PENDING = "Pending Review"
FLEX_NEEDS_INFO = "Needs Clarification"
FLEX_CLARIFIED = "Clarification Submitted"
FLEX_APPROVED = "Approved"
FLEX_REJECTED = "Rejected"
PAYROLL_NOT_READY = "Not Ready"
PAYROLL_PENDING = "Pending Bridge"
PAYROLL_BRIDGED = "Bridged"
PAYROLL_LOCKED = "Payroll Locked"
HR_OVERRIDE_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}
HEAD_OFFICE_KEYS = {"BRITTANY", "CAPITAL HOUSE", "BGC", "HEAD OFFICE", "HQ"}
COMMISSARY_KEYS = {"COMMISSARY", "R&D", "R AND D"}


def _txt(value: str | None) -> str:
	return str(value or "").strip()


def _upper(value: str | None) -> str:
	return _txt(value).upper()


def _normalize_ot_status(status: str | None) -> str:
	return OT_PENDING if status == OT_LEGACY_PENDING else _txt(status)


def _is_store_oic(designation: str | None) -> bool:
	label = _upper(designation)
	return (
		"OIC" in label
		or ("ASSISTANT" in label and "SUPERVISOR" in label)
		or ("ASST" in label and "SUPERVISOR" in label)
	)


def _is_store_supervisor(designation: str | None) -> bool:
	label = _upper(designation)
	return "STORE SUPERVISOR" in label and "ASSISTANT" not in label and "ASST" not in label


def _is_commissary(branch: str | None) -> bool:
	label = _upper(branch)
	return any(key in label for key in COMMISSARY_KEYS)


def _is_head_office(branch: str | None) -> bool:
	label = _upper(branch)
	return any(key in label for key in HEAD_OFFICE_KEYS)


def _is_head_office_shift(shift_name: str | None) -> bool:
	label = _upper(shift_name)
	return label.startswith("HO ") or "HEAD OFFICE" in label or "BGC" in label or "CAPITAL" in label


def _combine(date_value, time_value) -> datetime:
	base = getdate(date_value)
	tm = get_time(time_value)
	if isinstance(tm, timedelta):
		return datetime.combine(base, time.min) + tm
	return datetime.combine(base, tm)


def _hours(start_dt: datetime, end_dt: datetime) -> float:
	return max(0.0, (end_dt - start_dt).total_seconds() / 3600.0)


def _minutes(start_dt: datetime, end_dt: datetime) -> float:
	return max(0.0, (end_dt - start_dt).total_seconds() / 60.0)


def _roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def _is_hr_override(user: str | None = None) -> bool:
	return bool(_roles(user).intersection(HR_OVERRIDE_ROLES))


def _assert_hr_access() -> None:
	if not _is_hr_override():
		frappe.throw(_("Only HR or administrators can access this view."), frappe.PermissionError)


def _assert_review_access(doc, status_field: str) -> bool:
	user = frappe.session.user
	if _is_hr_override(user):
		return user not in {
			_txt(getattr(doc, "assigned_approver", None)),
			_txt(getattr(doc, "fallback_approver", None)),
			_txt(getattr(doc, "escalation_approver", None)),
		}
	allowed = {
		_txt(getattr(doc, "assigned_approver", None)),
		_txt(getattr(doc, "fallback_approver", None)),
		_txt(getattr(doc, "escalation_approver", None)),
	}
	if user not in allowed:
		raise frappe.PermissionError(_("You are not the assigned reviewer for {0}.").format(doc.name))
	return False


def _assert_employee_access(employee_name: str) -> None:
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	if employee != employee_name and not _is_hr_override():
		frappe.throw(_("You do not have permission to respond for this employee."), frappe.PermissionError)


def _employee(employee_name: str):
	row = frappe.db.get_value(
		"Employee",
		employee_name,
		["name", "employee_name", "user_id", "branch", "department", "designation", "reports_to", "company"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Employee {0} not found").format(employee_name))
	return frappe._dict(row)


def _employee_user(employee_name: str | None) -> str | None:
	return _txt(frappe.db.get_value("Employee", employee_name, "user_id")) if employee_name else None


def _default_hr_manager() -> str | None:
	for user in frappe.get_all("Has Role", filters={"role": "HR Manager"}, pluck="parent"):
		if user and frappe.db.get_value("User", user, "enabled"):
			return user
	return None


def _manager_user(employee_name: str | None) -> str | None:
	return _employee_user(employee_name)


def _manager_manager_user(employee_name: str | None) -> str | None:
	if not employee_name:
		return None
	manager = frappe.db.get_value("Employee", employee_name, "reports_to")
	return _employee_user(manager)


def _store_chain(employee_doc) -> dict[str, str | None]:
	ctx = resolve_employee_store_context(employee_doc)
	candidates = {
		value
		for value in {_txt(ctx.get("branch")), _txt(ctx.get("warehouse")), _txt(ctx.get("warehouse_name"))}
		if value
	}
	rows = (
		frappe.get_all(
			"Employee",
			filters={"status": "Active", "branch": ["in", list(candidates)]},
			fields=["name", "user_id", "designation"],
			limit_page_length=100,
		)
		if candidates
		else []
	)
	primary = None
	fallback = None
	requester_user = _txt(employee_doc.user_id)
	if _is_store_supervisor(employee_doc.designation):
		try:
			from hrms.api.store import _get_area_supervisor_for_store

			primary = _txt(_get_area_supervisor_for_store(ctx.get("warehouse")))
		except Exception:
			primary = None
	else:
		for row in rows:
			if row.user_id and row.user_id != requester_user and _is_store_supervisor(row.designation):
				primary = row.user_id
				break
	if not fallback:
		for row in rows:
			if (
				row.user_id
				and row.user_id not in {requester_user, primary}
				and _is_store_oic(row.designation)
			):
				fallback = row.user_id
				break
	try:
		from hrms.api.store import _get_area_supervisor_for_store

		escalation = _txt(_get_area_supervisor_for_store(ctx.get("warehouse")))
	except Exception:
		escalation = None
	primary = primary or escalation or _default_hr_manager()
	fallback = fallback or escalation or _default_hr_manager()
	escalation = escalation or _default_hr_manager()
	return {
		"team_type": "store",
		"assigned_approver": primary,
		"fallback_approver": fallback,
		"escalation_approver": escalation,
	}


def _approver_chain(employee_doc) -> dict[str, str | None]:
	if resolve_employee_store_context(employee_doc).get("warehouse"):
		return _store_chain(employee_doc)
	team_type = (
		"commissary"
		if _is_commissary(employee_doc.branch) and not _is_head_office(employee_doc.branch)
		else "office"
	)
	primary = _manager_user(employee_doc.reports_to)
	fallback = _manager_manager_user(employee_doc.reports_to)
	escalation = _default_hr_manager()
	return {
		"team_type": team_type,
		"assigned_approver": primary or escalation,
		"fallback_approver": fallback or escalation,
		"escalation_approver": escalation,
	}


def _shift_context(employee_doc, attendance_date, shift_name: str | None = None):
	shift_row = None
	if shift_name:
		shift_row = frappe.db.get_value(
			"Shift Type",
			shift_name,
			[
				"name",
				"start_time",
				"end_time",
				"begin_check_in_before_shift_start_time",
				"late_entry_grace_period",
				"allow_overtime",
				"overtime_type",
			],
			as_dict=True,
		)
	if not shift_row:
		assignment = frappe.db.get_value(
			"Shift Assignment",
			{
				"employee": employee_doc.name,
				"docstatus": 1,
				"status": "Active",
				"start_date": ("<=", attendance_date),
				"end_date": [">=", attendance_date],
			},
			["shift_type"],
			as_dict=True,
		)
		if not assignment:
			assignment = frappe.db.get_value(
				"Shift Assignment",
				{
					"employee": employee_doc.name,
					"docstatus": 1,
					"status": "Active",
					"start_date": ("<=", attendance_date),
					"end_date": ("is", "not set"),
				},
				["shift_type"],
				as_dict=True,
			)
		if assignment and assignment.get("shift_type"):
			shift_row = frappe.db.get_value(
				"Shift Type",
				assignment["shift_type"],
				[
					"name",
					"start_time",
					"end_time",
					"begin_check_in_before_shift_start_time",
					"late_entry_grace_period",
					"allow_overtime",
					"overtime_type",
				],
				as_dict=True,
			)
	if not shift_row:
		return frappe._dict(
			{
				"shift_name": shift_name,
				"scheduled_start": None,
				"scheduled_end": None,
				"flex_eligible": False,
				"allowed_early_minutes": 0,
				"late_flex_minutes": 0,
				"standard_working_hours": OT_THRESHOLD_HOURS,
				"overtime_type": None,
			}
		)
	start_dt = _combine(attendance_date, shift_row["start_time"])
	end_dt = _combine(attendance_date, shift_row["end_time"])
	if end_dt <= start_dt:
		end_dt += timedelta(days=1)
	flex_eligible = (
		not resolve_employee_store_context(employee_doc).get("warehouse")
		and not (_is_commissary(employee_doc.branch) and not _is_head_office(employee_doc.branch))
		and (
			_is_head_office_shift(shift_row["name"])
			or _is_head_office(employee_doc.branch)
			or (
				flt(shift_row.get("begin_check_in_before_shift_start_time")) > 0
				and flt(shift_row.get("late_entry_grace_period")) > 0
			)
		)
	)
	return frappe._dict(
		{
			"shift_name": shift_row["name"],
			"scheduled_start": start_dt,
			"scheduled_end": end_dt,
			"flex_eligible": flex_eligible,
			"allowed_early_minutes": int(
				min(flt(shift_row.get("begin_check_in_before_shift_start_time") or 0), DEFAULT_FLEX_MINUTES)
			)
			if flex_eligible
			else 0,
			"late_flex_minutes": int(
				min(flt(shift_row.get("late_entry_grace_period") or 0), DEFAULT_FLEX_MINUTES)
			)
			if flex_eligible
			else 0,
			"standard_working_hours": round(_hours(start_dt, end_dt), 2) or OT_THRESHOLD_HOURS,
			"overtime_type": shift_row.get("overtime_type"),
		}
	)


def _flex_doc(employee_name: str, attendance_date, flex_type: str):
	name = frappe.db.get_value(
		"Attendance Request",
		{
			"employee": employee_name,
			"from_date": attendance_date,
			"to_date": attendance_date,
			"reason": FLEX_REASON,
			"flex_exception_type": flex_type,
			"docstatus": ("!=", 2),
		},
		"name",
	)
	return frappe.get_doc("Attendance Request", name) if name else None


def _validated_minutes(doc) -> float:
	if not doc or _txt(getattr(doc, "review_status", None)) != FLEX_APPROVED:
		return 0.0
	return flt(doc.validated_minutes or doc.requested_minutes or 0)


def _evaluate(attendance_doc, employee_doc, shift_ctx):
	if (
		not attendance_doc.get("in_time")
		or not attendance_doc.get("out_time")
		or not shift_ctx.scheduled_start
		or not shift_ctx.scheduled_end
	):
		total = flt(attendance_doc.get("working_hours") or 0)
		return frappe._dict(
			{
				"total_hours": round(total, 2),
				"candidate_hours": round(max(0, total - OT_THRESHOLD_HOURS), 2),
				"eligible": total > OT_THRESHOLD_HOURS,
				"late_exception_minutes": 0,
				"early_exception_minutes": 0,
			}
		)
	actual_in = get_datetime(attendance_doc.in_time)
	actual_out = get_datetime(attendance_doc.out_time)
	late_doc = _flex_doc(employee_doc.name, attendance_doc.attendance_date, FLEX_LATE)
	early_doc = _flex_doc(employee_doc.name, attendance_doc.attendance_date, FLEX_EARLY)
	approved_late = _validated_minutes(late_doc)
	approved_early = _validated_minutes(early_doc)
	standard_allowed_in = shift_ctx.scheduled_start - timedelta(minutes=shift_ctx.allowed_early_minutes)
	late_minutes = _minutes(shift_ctx.scheduled_start, actual_in)
	extra_early = _minutes(actual_in, standard_allowed_in) if actual_in < standard_allowed_in else 0
	within_default_late = bool(
		shift_ctx.flex_eligible
		and shift_ctx.late_flex_minutes > 0
		and 0 < late_minutes < shift_ctx.late_flex_minutes
	)
	unresolved_late = bool(
		shift_ctx.flex_eligible and late_minutes >= shift_ctx.late_flex_minutes > 0 and approved_late <= 0
	)
	counted_start = max(
		actual_in,
		shift_ctx.scheduled_start - timedelta(minutes=shift_ctx.allowed_early_minutes + approved_early),
	)
	expected_end = shift_ctx.scheduled_end + timedelta(
		minutes=(late_minutes if within_default_late else min(approved_late, late_minutes))
	)
	effective_hours = _hours(counted_start, actual_out)
	candidate = max(0.0, _hours(expected_end, actual_out))
	return frappe._dict(
		{
			"total_hours": round(_hours(actual_in, actual_out), 2),
			"candidate_hours": round(candidate, 2),
			"eligible": candidate > 0 and effective_hours > OT_THRESHOLD_HOURS and not unresolved_late,
			"late_exception_minutes": round(late_minutes, 2) if unresolved_late else 0,
			"early_exception_minutes": round(extra_early, 2) if shift_ctx.flex_eligible else 0,
		}
	)


def _upsert_flex(
	employee_doc,
	attendance_doc,
	shift_ctx,
	flex_type: str,
	requested_minutes: float,
	shift_record: str | None = None,
):
	if requested_minutes <= 0:
		return None
	doc = _flex_doc(employee_doc.name, attendance_doc.attendance_date, flex_type)
	chain = _approver_chain(employee_doc)
	if not doc:
		doc = frappe.new_doc("Attendance Request")
		doc.employee = employee_doc.name
		doc.company = employee_doc.company
		doc.from_date = attendance_doc.attendance_date
		doc.to_date = attendance_doc.attendance_date
		doc.reason = FLEX_REASON
		doc.flex_exception_type = flex_type
		doc.review_status = FLEX_PENDING
		doc.cutoff_datetime = f"{getdate(attendance_doc.attendance_date)} 23:59:00"
		doc.explanation = "System-detected flex exception"
	doc.shift = shift_ctx.shift_name or attendance_doc.get("shift")
	doc.attendance = attendance_doc.name
	doc.shift_record = shift_record or getattr(doc, "shift_record", None)
	doc.requested_minutes = flt(requested_minutes)
	doc.assigned_approver = chain["assigned_approver"]
	doc.fallback_approver = chain["fallback_approver"]
	doc.escalation_approver = chain["escalation_approver"]
	doc.hr_notified = 1 if _default_hr_manager() else 0
	doc.hr_notified_at = now_datetime() if doc.hr_notified else getattr(doc, "hr_notified_at", None)
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc


def _ot_doc(attendance_name: str | None = None, shift_record_name: str | None = None):
	filters = {"attendance": attendance_name} if attendance_name else {"shift_record": shift_record_name}
	name = frappe.db.get_value("BEI Overtime Request", filters, "name") if any(filters.values()) else None
	return frappe.get_doc("BEI Overtime Request", name) if name else None


def _upsert_from_attendance_doc(
	attendance_doc, source_trigger: str = "attendance_close", shift_record_name: str | None = None
):
	employee_doc = _employee(attendance_doc.employee)
	shift_ctx = _shift_context(employee_doc, attendance_doc.attendance_date, attendance_doc.get("shift"))
	eval_result = _evaluate(attendance_doc, employee_doc, shift_ctx)
	if eval_result.early_exception_minutes and shift_ctx.flex_eligible:
		_upsert_flex(
			employee_doc,
			attendance_doc,
			shift_ctx,
			FLEX_EARLY,
			eval_result.early_exception_minutes,
			shift_record=shift_record_name,
		)
	if eval_result.late_exception_minutes and shift_ctx.flex_eligible:
		_upsert_flex(
			employee_doc,
			attendance_doc,
			shift_ctx,
			FLEX_LATE,
			eval_result.late_exception_minutes,
			shift_record=shift_record_name,
		)
	doc = _ot_doc(attendance_name=attendance_doc.name, shift_record_name=shift_record_name)
	if not eval_result.eligible and not doc:
		return None
	chain = _approver_chain(employee_doc)
	if not doc:
		doc = frappe.new_doc("BEI Overtime Request")
	doc.employee = employee_doc.name
	doc.attendance = attendance_doc.name
	doc.attendance_date = attendance_doc.attendance_date
	doc.shift = shift_ctx.shift_name or attendance_doc.get("shift")
	doc.shift_record = shift_record_name
	doc.total_hours = eval_result.total_hours
	doc.regular_hours = OT_THRESHOLD_HOURS
	doc.overtime_hours = eval_result.candidate_hours
	doc.supervisor = employee_doc.reports_to
	doc.request_source = "system_detected"
	doc.source_trigger = source_trigger
	doc.source_event_key = (
		attendance_doc.name
		if source_trigger != "shift_record_close"
		else f"{source_trigger}:{shift_record_name or attendance_doc.name}"
	)
	doc.reason_category = "Post Shift OT"
	doc.assigned_approver = chain["assigned_approver"]
	doc.fallback_approver = chain["fallback_approver"]
	doc.escalation_approver = chain["escalation_approver"]
	doc.candidate_overtime_type = shift_ctx.overtime_type or attendance_doc.get("overtime_type")
	doc.payroll_bridge_status = doc.payroll_bridge_status or PAYROLL_NOT_READY
	if _normalize_ot_status(getattr(doc, "overtime_status", None)) in {"", OT_LEGACY_PENDING}:
		doc.overtime_status = OT_PENDING
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc


def upsert_overtime_case_from_attendance(attendance_name: str, source_trigger: str = "attendance_close"):
	doc = _upsert_from_attendance_doc(
		frappe.get_doc("Attendance", attendance_name), source_trigger=source_trigger
	)
	return doc.as_dict() if doc else None


def upsert_overtime_case_from_shift_record(shift_record_name: str):
	shift_doc = frappe.get_doc("BEI Shift Record", shift_record_name)
	attendance_name = frappe.db.get_value(
		"Attendance",
		{"employee": shift_doc.employee, "attendance_date": getdate(shift_doc.punch_in_time), "docstatus": 1},
		"name",
	)
	if not attendance_name:
		return None
	return upsert_overtime_case_from_attendance(attendance_name, source_trigger="shift_record_close")


def detect_overtime_for_date(attendance_date: str | None = None):
	attendance_date = attendance_date or str(add_days(getdate(nowdate()), -1))
	rows = frappe.get_all(
		"Attendance",
		filters={"docstatus": 1, "attendance_date": attendance_date},
		fields=["name"],
		limit_page_length=5000,
	)
	created = 0
	updated = 0
	for row in rows:
		existing = _ot_doc(attendance_name=row.name)
		upsert_overtime_case_from_attendance(row.name, source_trigger="nightly_backfill")
		if existing:
			updated += 1
		else:
			created += 1
	return {"date": attendance_date, "created": created, "updated": updated}


@frappe.whitelist()
def get_operational_queue(status: str | None = None, include_resolved: int = 0):
	user = frappe.session.user
	ot_rows = frappe.db.sql(
		"""
		SELECT ot.name, ot.employee, emp.employee_name, emp.branch, emp.department, ot.attendance_date, ot.shift,
		       ot.overtime_hours, ot.total_hours, ot.overtime_status, ot.clarification_question, ot.clarification_response, ot.review_note
		FROM `tabBEI Overtime Request` ot
		LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
		WHERE ot.assigned_approver = %(user)s OR ot.fallback_approver = %(user)s OR ot.escalation_approver = %(user)s
		ORDER BY ot.attendance_date DESC, ot.creation DESC
		""",
		{"user": user},
		as_dict=True,
	)
	flex_rows = frappe.db.sql(
		"""
		SELECT ar.name, ar.employee, emp.employee_name, emp.branch, emp.department, ar.from_date AS attendance_date, ar.shift,
		       ar.review_status, ar.flex_exception_type, ar.requested_minutes, ar.validated_minutes,
		       ar.clarification_prompt, ar.clarification_response, ar.manager_decision_note
		FROM `tabAttendance Request` ar
		LEFT JOIN `tabEmployee` emp ON emp.name = ar.employee
		WHERE ar.reason = %(reason)s
		  AND (ar.assigned_approver = %(user)s OR ar.fallback_approver = %(user)s OR ar.escalation_approver = %(user)s)
		ORDER BY ar.from_date DESC, ar.creation DESC
		""",
		{"reason": FLEX_REASON, "user": user},
		as_dict=True,
	)
	items = []
	for row in ot_rows:
		ot_status = _normalize_ot_status(row.overtime_status)
		if status and ot_status != status:
			continue
		if not int(include_resolved or 0) and ot_status not in {
			OT_PENDING,
			OT_NEEDS_INFO,
			OT_CLARIFIED,
			OT_ESCALATED,
		}:
			continue
		items.append(
			{
				"id": row.name,
				"item_type": "overtime",
				"status": ot_status,
				"employee": row.employee,
				"employee_name": row.employee_name,
				"branch": row.branch,
				"department": row.department,
				"attendance_date": row.attendance_date,
				"shift": row.shift,
				"overtime_hours": row.overtime_hours,
				"total_hours": row.total_hours,
				"clarification_question": row.clarification_question,
				"clarification_response": row.clarification_response,
				"review_note": row.review_note,
			}
		)
	for row in flex_rows:
		if status and row.review_status != status:
			continue
		if not int(include_resolved or 0) and row.review_status not in {
			FLEX_PENDING,
			FLEX_NEEDS_INFO,
			FLEX_CLARIFIED,
		}:
			continue
		items.append(
			{
				"id": row.name,
				"item_type": "flex_exception",
				"status": row.review_status,
				"employee": row.employee,
				"employee_name": row.employee_name,
				"branch": row.branch,
				"department": row.department,
				"attendance_date": row.attendance_date,
				"shift": row.shift,
				"flex_exception_type": row.flex_exception_type,
				"requested_minutes": row.requested_minutes,
				"validated_minutes": row.validated_minutes,
				"clarification_question": row.clarification_prompt,
				"clarification_response": row.clarification_response,
				"review_note": row.manager_decision_note,
			}
		)
	return {"items": items, "count": len(items)}


@frappe.whitelist()
def get_employee_ot_cases():
	current_employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
	)
	if not current_employee:
		return {"items": [], "count": 0}
	ot_rows = frappe.get_all(
		"BEI Overtime Request",
		filters={"employee": current_employee},
		fields=[
			"name",
			"attendance_date",
			"shift",
			"overtime_hours",
			"total_hours",
			"overtime_status",
			"clarification_question",
			"clarification_response",
			"review_note",
			"rejection_reason",
			"approval_notes",
		],
		order_by="attendance_date desc",
	)
	flex_rows = frappe.get_all(
		"Attendance Request",
		filters={"employee": current_employee, "reason": FLEX_REASON},
		fields=[
			"name",
			"from_date",
			"shift",
			"review_status",
			"flex_exception_type",
			"requested_minutes",
			"validated_minutes",
			"clarification_prompt",
			"clarification_response",
			"manager_decision_note",
		],
		order_by="from_date desc",
	)
	items = [
		{
			"id": row.name,
			"item_type": "overtime",
			"status": _normalize_ot_status(row.overtime_status),
			"attendance_date": row.attendance_date,
			"shift": row.shift,
			"overtime_hours": row.overtime_hours,
			"total_hours": row.total_hours,
			"clarification_question": row.clarification_question,
			"clarification_response": row.clarification_response,
			"review_note": row.review_note or row.rejection_reason or row.approval_notes,
		}
		for row in ot_rows
	]
	items.extend(
		{
			"id": row.name,
			"item_type": "flex_exception",
			"status": row.review_status,
			"attendance_date": row.from_date,
			"shift": row.shift,
			"flex_exception_type": row.flex_exception_type,
			"requested_minutes": row.requested_minutes,
			"validated_minutes": row.validated_minutes,
			"clarification_question": row.clarification_prompt,
			"clarification_response": row.clarification_response,
			"review_note": row.manager_decision_note,
		}
		for row in flex_rows
	)
	return {"items": items, "count": len(items)}


def _save_ot_transition(
	doc,
	new_status: str,
	notes: str | None = None,
	approved_duration: float | None = None,
	approved_type: str | None = None,
):
	is_override = _assert_review_access(doc, "overtime_status")
	if is_override and not notes:
		frappe.throw(_("HR override actions require notes."))
	doc.overtime_status = new_status
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	if notes:
		doc.review_note = notes
	if is_override:
		doc.override_note = notes
	if new_status == OT_APPROVED:
		doc.approval_notes = notes or doc.approval_notes
		doc.approved_payable_duration = flt(
			approved_duration if approved_duration is not None else doc.overtime_hours
		)
		doc.approved_overtime_type = (
			approved_type or doc.candidate_overtime_type or doc.approved_overtime_type
		)
		doc.payroll_bridge_status = PAYROLL_PENDING
	if new_status == OT_REJECTED:
		doc.rejection_reason = notes or doc.rejection_reason
		doc.payroll_bridge_status = PAYROLL_NOT_READY
	doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist()
def approve_overtime(
	overtime_request_name: str | None = None,
	notes: str | None = None,
	name: str | None = None,
	approval_notes: str | None = None,
	approved_payable_duration: float | None = None,
	approved_overtime_type: str | None = None,
):
	doc = _save_ot_transition(
		frappe.get_doc("BEI Overtime Request", overtime_request_name or name),
		OT_APPROVED,
		notes if notes is not None else approval_notes,
		approved_payable_duration,
		approved_overtime_type,
	)
	return {"success": True, "name": doc.name, "status": doc.overtime_status}


@frappe.whitelist()
def reject_overtime(
	overtime_request_name: str | None = None,
	reason: str | None = None,
	name: str | None = None,
	rejection_reason: str | None = None,
):
	reason = reason if reason is not None else rejection_reason
	if not reason:
		frappe.throw(_("Rejection reason is required"))
	doc = _save_ot_transition(
		frappe.get_doc("BEI Overtime Request", overtime_request_name or name), OT_REJECTED, reason
	)
	return {"success": True, "name": doc.name, "status": doc.overtime_status}


@frappe.whitelist()
def request_overtime_clarification(name: str, question: str):
	if not question:
		frappe.throw(_("Clarification question is required"))
	doc = frappe.get_doc("BEI Overtime Request", name)
	_assert_review_access(doc, "overtime_status")
	doc.overtime_status = OT_NEEDS_INFO
	doc.clarification_question = question
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.overtime_status}


@frappe.whitelist()
def submit_overtime_clarification(name: str, response: str):
	if not response:
		frappe.throw(_("Clarification response is required"))
	doc = frappe.get_doc("BEI Overtime Request", name)
	_assert_employee_access(doc.employee)
	doc.clarification_response = response
	doc.employee_explanation = response
	doc.overtime_status = OT_CLARIFIED
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.overtime_status}


@frappe.whitelist()
def escalate_overtime(name: str, notes: str | None = None):
	doc = frappe.get_doc("BEI Overtime Request", name)
	_assert_review_access(doc, "overtime_status")
	target = _txt(doc.fallback_approver or doc.escalation_approver)
	if not target or target == _txt(frappe.session.user):
		target = _txt(doc.escalation_approver)
	if not target:
		frappe.throw(_("No escalation approver is configured."))
	doc.overtime_status = OT_ESCALATED
	doc.assigned_approver = target
	doc.review_note = notes or doc.review_note
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.overtime_status, "assigned_approver": target}


@frappe.whitelist()
def approve_flex_exception(name: str, notes: str | None = None, validated_minutes: float | None = None):
	doc = frappe.get_doc("Attendance Request", name)
	_assert_review_access(doc, "review_status")
	doc.review_status = FLEX_APPROVED
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.manager_decision_note = notes or doc.manager_decision_note
	doc.validated_minutes = flt(
		validated_minutes if validated_minutes is not None else doc.requested_minutes or 0
	)
	doc.save(ignore_permissions=True)
	if doc.attendance:
		ot_doc = _upsert_from_attendance_doc(
			frappe.get_doc("Attendance", doc.attendance),
			source_trigger="attendance_close",
			shift_record_name=doc.shift_record,
		)
		if ot_doc:
			doc.linked_ot_case = ot_doc.name
			doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.review_status}


@frappe.whitelist()
def reject_flex_exception(name: str, reason: str):
	if not reason:
		frappe.throw(_("Rejection reason is required"))
	doc = frappe.get_doc("Attendance Request", name)
	_assert_review_access(doc, "review_status")
	doc.review_status = FLEX_REJECTED
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.manager_decision_note = reason
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.review_status}


@frappe.whitelist()
def request_flex_clarification(name: str, question: str):
	if not question:
		frappe.throw(_("Clarification question is required"))
	doc = frappe.get_doc("Attendance Request", name)
	_assert_review_access(doc, "review_status")
	doc.review_status = FLEX_NEEDS_INFO
	doc.clarification_prompt = question
	doc.reviewed_by = frappe.session.user
	doc.reviewed_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.review_status}


@frappe.whitelist()
def submit_flex_clarification(name: str, response: str):
	if not response:
		frappe.throw(_("Clarification response is required"))
	doc = frappe.get_doc("Attendance Request", name)
	_assert_employee_access(doc.employee)
	doc.clarification_response = response
	doc.review_status = FLEX_CLARIFIED
	doc.save(ignore_permissions=True)
	return {"success": True, "name": doc.name, "status": doc.review_status}


@frappe.whitelist()
def get_overtime_requests(
	status: str | None = None,
	store: str | None = None,
	employee: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	page: int = 1,
	page_size: int = 20,
):
	_assert_hr_access()
	rows = frappe.db.sql(
		"""
		SELECT ot.name, ot.employee, emp.employee_name, emp.branch, emp.department, ot.attendance_date, ot.shift, ot.regular_hours,
		       ot.overtime_hours, ot.total_hours, ot.overtime_status, ot.assigned_approver, ot.fallback_approver, ot.escalation_approver,
		       ot.reviewed_by, ot.reviewed_at, ot.review_note, ot.approval_notes, ot.rejection_reason, ot.approved_payable_duration,
		       ot.approved_overtime_type, ot.payroll_bridge_status, ot.payroll_bridge_reference
		FROM `tabBEI Overtime Request` ot
		LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
		WHERE (%(status)s IS NULL OR ot.overtime_status = %(status)s)
		  AND (%(employee)s IS NULL OR ot.employee = %(employee)s)
		  AND (%(from_date)s IS NULL OR ot.attendance_date >= %(from_date)s)
		  AND (%(to_date)s IS NULL OR ot.attendance_date <= %(to_date)s)
		  AND (%(store)s IS NULL OR emp.branch = %(store)s)
		ORDER BY ot.attendance_date DESC, ot.creation DESC
		""",
		{"status": status, "employee": employee, "from_date": from_date, "to_date": to_date, "store": store},
		as_dict=True,
	)
	return _paginate(
		[{**dict(row), "overtime_status": _normalize_ot_status(row.overtime_status)} for row in rows],
		page=int(page or 1),
		page_size=int(page_size or 20),
	)


@frappe.whitelist()
def get_overtime_summary(store: str | None = None, from_date: str | None = None, to_date: str | None = None):
	_assert_hr_access()
	summary = frappe.db.sql(
		"""
		SELECT COALESCE(emp.department, 'Unassigned') AS department, COALESCE(emp.branch, 'Unassigned') AS store,
		       COUNT(*) AS total_requests, COALESCE(SUM(ot.overtime_hours), 0) AS total_hours,
		       COALESCE(SUM(CASE WHEN ot.overtime_status = 'Approved' THEN COALESCE(ot.approved_payable_duration, ot.overtime_hours) ELSE 0 END), 0) AS approved_hours,
		       COALESCE(SUM(CASE WHEN ot.overtime_status IN ('Pending Review', 'Needs Clarification', 'Clarification Submitted', 'Escalated', 'Pending Approval') THEN ot.overtime_hours ELSE 0 END), 0) AS pending_hours,
		       COALESCE(SUM(CASE WHEN ot.overtime_status = 'Rejected' THEN ot.overtime_hours ELSE 0 END), 0) AS rejected_hours
		FROM `tabBEI Overtime Request` ot
		LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
		WHERE (%(from_date)s IS NULL OR ot.attendance_date >= %(from_date)s)
		  AND (%(to_date)s IS NULL OR ot.attendance_date <= %(to_date)s)
		  AND (%(store)s IS NULL OR emp.branch = %(store)s)
		GROUP BY COALESCE(emp.department, 'Unassigned'), COALESCE(emp.branch, 'Unassigned')
		ORDER BY store ASC, department ASC
		""",
		{"from_date": from_date, "to_date": to_date, "store": store},
		as_dict=True,
	)
	totals = {
		"total_requests": 0,
		"total_hours": 0.0,
		"approved_hours": 0.0,
		"pending_hours": 0.0,
		"rejected_hours": 0.0,
	}
	for row in summary:
		totals["total_requests"] += int(row.total_requests or 0)
		totals["total_hours"] += flt(row.total_hours)
		totals["approved_hours"] += flt(row.approved_hours)
		totals["pending_hours"] += flt(row.pending_hours)
		totals["rejected_hours"] += flt(row.rejected_hours)
	return {"summary": summary, "totals": totals}


@frappe.whitelist()
def get_approved_overtime_hours(employee: str, from_date: str, to_date: str):
	rows = frappe.db.sql(
		"""
		SELECT overtime_status, COALESCE(SUM(COALESCE(approved_payable_duration, overtime_hours)), 0) AS hours
		FROM `tabBEI Overtime Request`
		WHERE employee = %(employee)s AND attendance_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY overtime_status
		""",
		{"employee": employee, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	result = {"approved_hours": 0.0, "pending_hours": 0.0, "rejected_hours": 0.0}
	for row in rows:
		status = _normalize_ot_status(row.overtime_status)
		if status in {OT_APPROVED, OT_LOCKED}:
			result["approved_hours"] += flt(row.hours)
		elif status == OT_REJECTED:
			result["rejected_hours"] += flt(row.hours)
		else:
			result["pending_hours"] += flt(row.hours)
	return result


def get_approved_ot_bridge_rows(employee: str, start_date, end_date):
	rows = frappe.db.sql(
		"""
		SELECT ot.name, ot.attendance AS reference_document, ot.attendance_date, COALESCE(ot.approved_overtime_type, ot.candidate_overtime_type) AS overtime_type,
		       COALESCE(ot.approved_payable_duration, ot.overtime_hours) AS overtime_duration,
		       COALESCE(a.standard_working_hours, %(standard_hours)s) AS standard_working_hours
		FROM `tabBEI Overtime Request` ot
		LEFT JOIN `tabAttendance` a ON a.name = ot.attendance
		WHERE ot.employee = %(employee)s
		  AND ot.attendance_date BETWEEN %(start_date)s AND %(end_date)s
		  AND ot.overtime_status IN ('Approved', 'Payroll Locked')
		  AND COALESCE(ot.approved_payable_duration, ot.overtime_hours) > 0
		ORDER BY ot.attendance_date ASC, ot.creation ASC
		""",
		{
			"employee": employee,
			"start_date": start_date,
			"end_date": end_date,
			"standard_hours": OT_THRESHOLD_HOURS,
		},
		as_dict=True,
	)
	return [frappe._dict(row) for row in rows if row.get("overtime_type")]


def mark_overtime_requests_bridged(
	ot_request_names: list[str], overtime_slip_name: str, locked: bool = False
):
	names = list(ot_request_names or [])
	if not names and overtime_slip_name:
		names = frappe.get_all(
			"BEI Overtime Request",
			filters={"payroll_bridge_reference": overtime_slip_name},
			pluck="name",
		)
	for name in names:
		doc = frappe.get_doc("BEI Overtime Request", name)
		doc.payroll_bridge_status = PAYROLL_LOCKED if locked else PAYROLL_BRIDGED
		doc.payroll_bridge_reference = overtime_slip_name
		if locked and doc.overtime_status == OT_APPROVED:
			doc.overtime_status = OT_LOCKED
		doc.save(ignore_permissions=True)


def scheduled_overtime_detection():
	yesterday = str(add_days(getdate(nowdate()), -1))
	result = detect_overtime_for_date(attendance_date=yesterday)
	frappe.logger("overtime").info(f"Scheduled OT detection complete: {result}")
