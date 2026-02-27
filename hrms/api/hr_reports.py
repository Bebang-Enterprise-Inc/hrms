"""HR Reports API endpoints for employee masterlist, headcount, attrition, attendance, and OT"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate, today

from hrms.utils.api_helpers import (
	_check_hr_permission,
	_paginate,
	_validate_date_range,
)


@frappe.whitelist()
def get_employee_masterlist(
	status: str | None = None,
	department: str | None = None,
	store: str | None = None,
	employment_type: str | None = None,
	page: int = 1,
	page_size: int = 50,
):
	"""Active/Inactive employee masterlist with filters.

	Args:
	    status: Filter by status (Active/Inactive/Left)
	    department: Filter by department
	    store: Filter by branch/store
	    employment_type: Filter by employment type
	    page: Page number (1-based)
	    page_size: Results per page

	Returns:
	    dict: Paginated employee list
	"""
	_check_hr_permission()

	filters = {}
	if status:
		filters["status"] = status
	if department:
		filters["department"] = department
	if store:
		filters["branch"] = store
	if employment_type:
		filters["employment_type"] = employment_type

	results = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"department",
			"designation",
			"branch",
			"status",
			"date_of_joining",
			"employment_type",
			"company",
			"user_id",
			"cell_number",
			"reports_to",
			"gender",
			"date_of_birth",
		],
		order_by="employee_name asc",
	)

	return _paginate(results, page=int(page), page_size=int(page_size))


@frappe.whitelist()
def get_headcount_report(group_by: str = "department", as_of_date: str | None = None):
	"""Headcount grouped by department, store, employment_type, or designation.

	Args:
	    group_by: Grouping field (department/branch/employment_type/designation)
	    as_of_date: Count as of specific date (default: today)

	Returns:
	    list: Headcount by group with percentages
	"""
	_check_hr_permission()

	if group_by not in ["department", "branch", "employment_type", "designation"]:
		frappe.throw(_("Invalid group_by field. Must be: department/branch/employment_type/designation"))

	if not as_of_date:
		as_of_date = today()

	# Get total active headcount
	total_count = frappe.db.count("Employee", filters={"status": "Active"})

	query_by_group = {
		"department": """
        SELECT department as group_name, COUNT(*) as count
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND date_of_joining <= %(as_of_date)s
          AND (relieving_date IS NULL OR relieving_date > %(as_of_date)s)
        GROUP BY department
        ORDER BY count DESC
    """,
		"branch": """
        SELECT branch as group_name, COUNT(*) as count
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND date_of_joining <= %(as_of_date)s
          AND (relieving_date IS NULL OR relieving_date > %(as_of_date)s)
        GROUP BY branch
        ORDER BY count DESC
    """,
		"employment_type": """
        SELECT employment_type as group_name, COUNT(*) as count
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND date_of_joining <= %(as_of_date)s
          AND (relieving_date IS NULL OR relieving_date > %(as_of_date)s)
        GROUP BY employment_type
        ORDER BY count DESC
    """,
		"designation": """
        SELECT designation as group_name, COUNT(*) as count
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND date_of_joining <= %(as_of_date)s
          AND (relieving_date IS NULL OR relieving_date > %(as_of_date)s)
        GROUP BY designation
        ORDER BY count DESC
    """,
	}

	results = frappe.db.sql(
		query_by_group[group_by],
		{"as_of_date": as_of_date},
		as_dict=True,
	)

	# Calculate percentages
	for row in results:
		row["percentage"] = round((row["count"] / total_count * 100), 2) if total_count > 0 else 0
		if not row["group_name"]:
			row["group_name"] = _("Unassigned")

	return {
		"group_by": group_by,
		"as_of_date": as_of_date,
		"total_count": total_count,
		"groups": results,
	}


@frappe.whitelist()
def get_attrition_report(from_date: str, to_date: str, group_by: str = "department"):
	"""Attrition rate calculation.

	Attrition rate = (Separations / Average Headcount) * 100

	Args:
	    from_date: Start date
	    to_date: End date
	    group_by: Grouping field (department/branch/employment_type)

	Returns:
	    dict: Overall attrition rate + per-group breakdown
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	if group_by not in ["department", "branch", "employment_type"]:
		frappe.throw(_("Invalid group_by field"))

	query_by_group = {
		"department": """
        SELECT department as group_name, COUNT(*) as separation_count
        FROM `tabEmployee`
        WHERE relieving_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY department
    """,
		"branch": """
        SELECT branch as group_name, COUNT(*) as separation_count
        FROM `tabEmployee`
        WHERE relieving_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY branch
    """,
		"employment_type": """
        SELECT employment_type as group_name, COUNT(*) as separation_count
        FROM `tabEmployee`
        WHERE relieving_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY employment_type
    """,
	}
	separations = frappe.db.sql(
		query_by_group[group_by],
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	# Get headcount at start and end
	start_headcount = frappe.db.count(
		"Employee",
		filters={
			"status": "Active",
			"date_of_joining": ["<=", from_date],
		},
	)
	end_headcount = frappe.db.count("Employee", filters={"status": "Active"})
	avg_headcount = (start_headcount + end_headcount) / 2

	# Calculate attrition by group
	for row in separations:
		# Get average headcount for this group
		group_start = frappe.db.count(
			"Employee",
			filters={
				group_by: row["group_name"],
				"date_of_joining": ["<=", from_date],
			},
		)
		group_end = frappe.db.count(
			"Employee",
			filters={"status": "Active", group_by: row["group_name"]},
		)
		group_avg = (group_start + group_end) / 2

		row["avg_headcount"] = group_avg
		row["attrition_rate"] = round((row["separation_count"] / group_avg * 100), 2) if group_avg > 0 else 0
		if not row["group_name"]:
			row["group_name"] = _("Unassigned")

	# Overall attrition
	total_separations = sum(r["separation_count"] for r in separations)
	overall_attrition = round((total_separations / avg_headcount * 100), 2) if avg_headcount > 0 else 0

	return {
		"period": {"from_date": from_date, "to_date": to_date},
		"overall": {
			"separations": total_separations,
			"avg_headcount": round(avg_headcount, 0),
			"attrition_rate": overall_attrition,
		},
		"by_group": separations,
		"group_by": group_by,
	}


@frappe.whitelist()
def get_new_hires_report(from_date: str, to_date: str, department: str | None = None):
	"""New hires in period (date_of_joining in range).

	Args:
	    from_date: Start date
	    to_date: End date
	    department: Optional department filter

	Returns:
	    list: New hire details
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	filters = {
		"date_of_joining": ["between", [from_date, to_date]],
	}
	if department:
		filters["department"] = department

	results = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"department",
			"designation",
			"branch",
			"date_of_joining",
			"employment_type",
			"company",
		],
		order_by="date_of_joining desc",
	)

	return {
		"period": {"from_date": from_date, "to_date": to_date},
		"department": department,
		"total_hires": len(results),
		"hires": results,
	}


@frappe.whitelist()
def get_separations_report(from_date: str, to_date: str, department: str | None = None):
	"""Separations in period (relieving_date in range).

	Args:
	    from_date: Start date
	    to_date: End date
	    department: Optional department filter

	Returns:
	    list: Separation details with reasons
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	filters = {
		"relieving_date": ["between", [from_date, to_date]],
	}
	if department:
		filters["department"] = department

	results = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"department",
			"designation",
			"branch",
			"date_of_joining",
			"relieving_date",
			"employment_type",
			"company",
			"status",
		],
		order_by="relieving_date desc",
	)

	# Get separation reasons from Employee Separation if available
	for row in results:
		separation = frappe.db.get_value(
			"Employee Separation",
			{"employee": row["name"]},
			["reason_for_leaving", "exit_interview_held"],
			as_dict=True,
		)
		if separation:
			row["reason"] = separation.get("reason_for_leaving")
			row["exit_interview_held"] = separation.get("exit_interview_held")
		else:
			row["reason"] = None
			row["exit_interview_held"] = None

		# Calculate tenure
		if row["date_of_joining"] and row["relieving_date"]:
			tenure_days = date_diff(row["relieving_date"], row["date_of_joining"])
			row["tenure_years"] = round(tenure_days / 365.25, 1)

	return {
		"period": {"from_date": from_date, "to_date": to_date},
		"department": department,
		"total_separations": len(results),
		"separations": results,
	}


@frappe.whitelist()
def get_recruitment_funnel(from_date: str | None = None, to_date: str | None = None):
	"""Recruitment pipeline funnel: MRFs → Openings → Applications → Offers → Hires.

	Args:
	    from_date: Start date (default: last 90 days)
	    to_date: End date (default: today)

	Returns:
	    dict: Stage counts and conversion rates
	"""
	_check_hr_permission()

	# Default to last 90 days
	if not from_date:
		from_date = add_days(today(), -90)
	if not to_date:
		to_date = today()

	_validate_date_range(from_date, to_date)

	# Count each stage
	mrfs = frappe.db.count(
		"BEI Manpower Request Form",
		filters={"creation": ["between", [from_date, to_date]]},
	)
	openings = frappe.db.count(
		"Job Opening",
		filters={"creation": ["between", [from_date, to_date]]},
	)
	applications = frappe.db.count(
		"Job Applicant",
		filters={"creation": ["between", [from_date, to_date]]},
	)
	offers = frappe.db.count(
		"Job Offer",
		filters={"offer_date": ["between", [from_date, to_date]]},
	)
	hires = frappe.db.count(
		"Employee",
		filters={"date_of_joining": ["between", [from_date, to_date]]},
	)

	# Calculate conversion rates
	mrf_to_opening = round((openings / mrfs * 100), 2) if mrfs > 0 else 0
	opening_to_application = round((applications / openings * 100), 2) if openings > 0 else 0
	application_to_offer = round((offers / applications * 100), 2) if applications > 0 else 0
	offer_to_hire = round((hires / offers * 100), 2) if offers > 0 else 0
	overall_conversion = round((hires / mrfs * 100), 2) if mrfs > 0 else 0

	return {
		"period": {"from_date": from_date, "to_date": to_date},
		"funnel": {
			"mrfs": mrfs,
			"openings": openings,
			"applications": applications,
			"offers": offers,
			"hires": hires,
		},
		"conversion_rates": {
			"mrf_to_opening": mrf_to_opening,
			"opening_to_application": opening_to_application,
			"application_to_offer": application_to_offer,
			"offer_to_hire": offer_to_hire,
			"overall": overall_conversion,
		},
	}


@frappe.whitelist()
def get_attendance_summary_report(
	from_date: str,
	to_date: str,
	employee: str | None = None,
	department: str | None = None,
	page: int = 1,
	page_size: int = 50,
):
	"""Per-employee attendance summary: present, absent, late, undertime days.

	Args:
	    from_date: Start date
	    to_date: End date
	    employee: Optional employee filter
	    department: Optional department filter
	    page: Page number
	    page_size: Results per page

	Returns:
	    dict: Paginated attendance summary
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	filters = {
		"from_date": from_date,
		"to_date": to_date,
		"employee": employee,
		"department": department,
	}

	results = frappe.db.sql(
		"""
        SELECT
            a.employee,
            e.employee_name,
            e.department,
            e.designation,
            e.branch,
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_days,
            COUNT(CASE WHEN a.status = 'Absent' THEN 1 END) as absent_days,
            COUNT(CASE WHEN a.status = 'On Leave' THEN 1 END) as on_leave_days,
            COUNT(CASE WHEN a.status = 'Half Day' THEN 1 END) as half_day_count,
            SUM(CASE WHEN a.late_entry = 1 THEN 1 ELSE 0 END) as late_days,
            SUM(CASE WHEN a.early_exit = 1 THEN 1 ELSE 0 END) as early_exit_days,
            SUM(COALESCE(a.working_hours, 0)) as total_working_hours,
            SUM(GREATEST(COALESCE(a.working_hours, 0) - 8, 0)) as total_ot_hours
        FROM `tabAttendance` a
        INNER JOIN `tabEmployee` e ON a.employee = e.name
        WHERE a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          AND (%(employee)s IS NULL OR a.employee = %(employee)s)
          AND (%(department)s IS NULL OR e.department = %(department)s)
        GROUP BY a.employee, e.employee_name, e.department, e.designation, e.branch
        ORDER BY e.employee_name
    """,
		filters,
		as_dict=True,
	)

	# Calculate attendance percentage
	total_days = date_diff(to_date, from_date) + 1
	for row in results:
		row["total_days"] = total_days
		row["attendance_percentage"] = (
			round((row["present_days"] / total_days * 100), 2) if total_days > 0 else 0
		)

	return _paginate(results, page=int(page), page_size=int(page_size))


@frappe.whitelist()
def get_overtime_report(
	from_date: str,
	to_date: str,
	department: str | None = None,
	page: int = 1,
	page_size: int = 50,
):
	"""OT hours by employee with type breakdown (regular/holiday/rest day).

	Args:
	    from_date: Start date
	    to_date: End date
	    department: Optional department filter
	    page: Page number
	    page_size: Results per page

	Returns:
	    dict: Paginated OT report
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	filters = {"from_date": from_date, "to_date": to_date, "department": department}

	results = frappe.db.sql(
		"""
        SELECT
            a.employee,
            e.employee_name,
            e.department,
            e.designation,
            e.branch,
            SUM(GREATEST(COALESCE(a.working_hours, 0) - 8, 0)) as total_ot_hours,
            COUNT(CASE WHEN a.working_hours > 8 THEN 1 END) as ot_days
        FROM `tabAttendance` a
        INNER JOIN `tabEmployee` e ON a.employee = e.name
        WHERE a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          AND (%(department)s IS NULL OR e.department = %(department)s)
        GROUP BY a.employee, e.employee_name, e.department, e.designation, e.branch
        HAVING total_ot_hours > 0
        ORDER BY total_ot_hours DESC
    """,
		filters,
		as_dict=True,
	)

	# Get approved OT Slip records for breakdown (if DocType exists)
	for row in results:
		try:
			ot_slip_hours = frappe.db.sql(
				"""
                SELECT
                    SUM(COALESCE(total_hours, 0)) as approved_ot_hours
                FROM `tabOvertime Slip`
                WHERE employee = %s
                AND from_date >= %s
                AND to_date <= %s
                AND docstatus = 1
            """,
				(row["employee"], from_date, to_date),
			)
			row["approved_ot_slip_hours"] = ot_slip_hours[0][0] if ot_slip_hours else 0
		except Exception:
			row["approved_ot_slip_hours"] = 0

	return _paginate(results, page=int(page), page_size=int(page_size))


def get_employee_permission_query_conditions(user: str) -> str:
	return "(`tabEmployee`.name NOT LIKE 'TEST-%')"


@frappe.whitelist()
def get_training_completion_by_store(training_event_type: str | None = None) -> dict:
	"""
	Return training completion % per store branch.
	Groups Training Result records by branch.
	"""
	# Query Training Result joined with Employee for branch
	results = frappe.db.sql(
		"""
        SELECT
            e.branch,
            COUNT(DISTINCT tr.employee) as completed,
            COUNT(DISTINCT e2.name) as total_active
        FROM `tabTraining Result` tr
        JOIN `tabEmployee` e ON tr.employee = e.name
        JOIN `tabEmployee` e2 ON e2.branch = e.branch AND e2.status = 'Active'
        WHERE tr.docstatus = 1
          AND (%(event_type)s IS NULL OR tr.training_event = %(event_type)s)
        GROUP BY e.branch
        ORDER BY e.branch
    """,
		{"event_type": training_event_type},
		as_dict=True,
	)

	return {"success": True, "data": results}


import frappe

ALLOWED_ROLES = ["HR Manager", "System Manager", "HR User", "Area Supervisor"]


@frappe.whitelist()
def get_leave_overview(
	date_range: str | None = None,
	branch: str | None = None,
	department: str | None = None,
):
	frappe.only_for(ALLOWED_ROLES)

	current_date = today()
	seven_days_from_now = add_days(current_date, 7)

	emp_values = {"branch": branch, "department": department}

	# Get total active employees matching criteria (for reference)
	total_employees = frappe.db.sql(
		"""
        SELECT count(name)
        FROM `tabEmployee` e
        WHERE e.status = 'Active'
          AND (%(branch)s IS NULL OR e.branch = %(branch)s)
          AND (%(department)s IS NULL OR e.department = %(department)s)
    """,
		emp_values,
	)[0][0]

	# Leaves today
	on_leave_today_query = """
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
        AND la.docstatus = 1
        AND %(today)s BETWEEN la.from_date AND la.to_date
        AND e.status = 'Active'
        AND (%(branch)s IS NULL OR e.branch = %(branch)s)
        AND (%(department)s IS NULL OR e.department = %(department)s)
    """
	values_today = {"today": current_date}
	values_today.update(emp_values)
	on_leave_today = frappe.db.sql(on_leave_today_query, values_today)[0][0]

	# Pending approvals
	pending_query = """
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Open'
        AND la.docstatus = 0
        AND e.status = 'Active'
        AND (%(branch)s IS NULL OR e.branch = %(branch)s)
        AND (%(department)s IS NULL OR e.department = %(department)s)
    """
	pending_count = frappe.db.sql(pending_query, emp_values)[0][0]

	# Upcoming (next 7 days)
	upcoming_query = """
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
        AND la.docstatus = 1
        AND la.from_date > %(today)s AND la.from_date <= %(next_7)s
        AND e.status = 'Active'
        AND (%(branch)s IS NULL OR e.branch = %(branch)s)
        AND (%(department)s IS NULL OR e.department = %(department)s)
    """
	values_upcoming = {"today": current_date, "next_7": seven_days_from_now}
	values_upcoming.update(emp_values)
	upcoming_count = frappe.db.sql(upcoming_query, values_upcoming)[0][0]

	return {
		"on_leave_today": on_leave_today,
		"pending_count": pending_count,
		"upcoming_count": upcoming_count,
		"total_employees": total_employees,
	}


@frappe.whitelist()
def get_all_leaves(
	status: str | None = None,
	branch: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
):
	frappe.only_for(ALLOWED_ROLES)

	values = {
		"status": status,
		"branch": branch,
		"from_date": from_date,
		"to_date": to_date,
	}

	query = """
        SELECT
            la.name, la.employee, la.employee_name, la.leave_type,
            la.from_date, la.to_date, la.total_leave_days, la.status, la.description,
            e.branch, e.department, e.image as employee_image, e.designation
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE (%(status)s IS NULL OR la.status = %(status)s)
          AND (%(branch)s IS NULL OR e.branch = %(branch)s)
          AND (%(from_date)s IS NULL OR la.to_date >= %(from_date)s)
          AND (%(to_date)s IS NULL OR la.from_date <= %(to_date)s)
        ORDER BY la.from_date DESC
    """

	leaves = frappe.db.sql(query, values, as_dict=True)
	return leaves


@frappe.whitelist()
def check_leave_conflicts(employee: str, from_date: str, to_date: str):
	"""
	Checks if there are overlapping approved leaves for the employee's branch/department.
	"""
	frappe.only_for(ALLOWED_ROLES)

	# Get employee details
	emp_details = frappe.db.get_value(
		"Employee", employee, ["branch", "department", "employee_name"], as_dict=True
	)
	if not emp_details:
		return []

	branch = emp_details.get("branch")
	department = emp_details.get("department")

	if not branch or not department:
		return []

	# Find overlapping leaves in the same branch/department (excluding this employee)
	query = """
        SELECT
            la.name as leave_id,
            la.employee_name,
            la.from_date,
            la.to_date,
            la.leave_type
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
        AND la.docstatus = 1
        AND la.employee != %(employee)s
        AND e.branch = %(branch)s
        AND e.department = %(department)s
        AND la.from_date <= %(to_date)s
        AND la.to_date >= %(from_date)s
    """

	values = {
		"employee": employee,
		"branch": branch,
		"department": department,
		"from_date": from_date,
		"to_date": to_date,
	}

	conflicts = frappe.db.sql(query, values, as_dict=True)
	return conflicts


@frappe.whitelist()
def bulk_update_leave_status(
	leave_ids: list[str] | str,
	status: str,
	remarks: str | None = None,
):
	frappe.only_for(ALLOWED_ROLES)

	import json

	if isinstance(leave_ids, str):
		leave_ids = json.loads(leave_ids)

	if status not in ["Approved", "Rejected"]:
		frappe.throw(_("Status must be Approved or Rejected"))

	results = {"success": [], "failed": []}

	for leave_id in leave_ids:
		try:
			doc = frappe.get_doc("Leave Application", leave_id)
			if doc.status == "Open":
				doc.status = status
				if remarks:
					# In Frappe, there's no native remarks field on Leave Application by default,
					# but maybe leave_approver_name or a custom field. We can add to workflow comments or just set status.
					# doc.leave_approver = frappe.session.user
					pass

				if status == "Approved":
					# Approve submits the document if it's draft
					if doc.docstatus == 0:
						doc.submit()
					else:
						doc.db_set("status", "Approved")
				elif status == "Rejected":
					_reject_leave_application(doc)

				results["success"].append(leave_id)
			else:
				results["failed"].append({"id": leave_id, "error": f"Leave is already {doc.status}"})
		except Exception as e:
			results["failed"].append({"id": leave_id, "error": str(e)})

	return results


def _reject_leave_application(doc: Any) -> None:
	"""Reject leave requests without forcing raw status writes on submitted docs.

	Submitted leave applications should be cancelled through document lifecycle,
	while draft applications can be marked rejected and saved.
	"""
	if getattr(doc, "docstatus", 0) == 1 and callable(getattr(doc, "cancel", None)):
		doc.cancel()
		return

	doc.status = "Rejected"

	save_method = getattr(doc, "save", None)
	if callable(save_method):
		try:
			save_method(ignore_permissions=True)
			return
		except TypeError:
			save_method()
			return

	# Fallback for lightweight test doubles without save()
	db_set = getattr(doc, "db_set", None)
	if callable(db_set):
		db_set("status", "Rejected")
