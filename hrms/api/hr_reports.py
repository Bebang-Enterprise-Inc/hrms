"""HR Reports API endpoints for employee masterlist, headcount, attrition, attendance, and OT"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate, today

from hrms.api import leave_dashboard as leave_dashboard_api
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
	search: str | None = None,
	reports_to: str | None = None,
	page: int = 1,
	page_size: int = 50,
):
	"""Employee masterlist with operational people-data fields.

	Args:
	    status: Filter by status (Active/Inactive/Left)
	    department: Filter by department
	    store: Filter by branch/store
	    employment_type: Filter by employment type
	    search: Search employee id, name, email, designation, or branch
	    reports_to: Filter by manager employee id
	    page: Page number (1-based)
	    page_size: Results per page

	Returns:
	    dict: Paginated employee list with summary + filter metadata
	"""
	_check_hr_permission()

	page = max(int(page or 1), 1)
	page_size = min(max(int(page_size or 50), 1), 200)

	filters = {}
	if status:
		filters["status"] = status
	if department:
		filters["department"] = department
	if store:
		filters["branch"] = store
	if employment_type:
		filters["employment_type"] = employment_type
	if reports_to:
		filters["reports_to"] = reports_to

	results = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"name as employee_id",
			"employee_name",
			"department",
			"designation",
			"branch",
			"status",
			"date_of_joining",
			"employment_type",
			"company",
			"user_id",
			"company_email",
			"personal_email",
			"cell_number",
			"reports_to",
			"custom_enrichment_status",
			"custom_enrichment_submitted_date",
			"custom_enrichment_complete_date",
			"gender",
			"date_of_birth",
		],
		order_by="employee_name asc",
	)

	if search:
		search_lower = search.strip().lower()
		if search_lower:
			results = [
				row
				for row in results
				if search_lower in str(row.get("name") or "").lower()
				or search_lower in str(row.get("employee_name") or "").lower()
				or search_lower in str(row.get("user_id") or "").lower()
				or search_lower in str(row.get("designation") or "").lower()
				or search_lower in str(row.get("branch") or "").lower()
				or search_lower in str(row.get("department") or "").lower()
			]

	manager_ids = sorted({row.get("reports_to") for row in results if row.get("reports_to")})
	manager_name_map = {}
	if manager_ids:
		manager_rows = frappe.get_all(
			"Employee",
			filters={"name": ("in", manager_ids)},
			fields=["name", "employee_name"],
		)
		manager_name_map = {row["name"]: row["employee_name"] for row in manager_rows}

	open_enrichment_employees = set(
		frappe.get_all(
			"BEI Onboarding Request",
			filters={
				"request_type": "update_existing",
				"status": ("in", ["Pending", "Escalated", "Revision Requested"]),
			},
			pluck="employee",
		)
	)

	for row in results:
		if not row.get("custom_enrichment_status"):
			row["custom_enrichment_status"] = "Not Started"
		row["reports_to_name"] = manager_name_map.get(row.get("reports_to"), "")
		row["has_pending_enrichment"] = row.get("name") in open_enrichment_employees

	summary = {
		"total_employees": len(results),
		"active": sum(1 for row in results if row.get("status") == "Active"),
		"inactive": sum(1 for row in results if row.get("status") != "Active"),
		"missing_manager": sum(1 for row in results if not row.get("reports_to")),
		"missing_company_email": sum(1 for row in results if not row.get("company_email")),
		"pending_enrichment": sum(1 for row in results if row.get("has_pending_enrichment")),
		"in_progress_enrichment": sum(
			1 for row in results if row.get("custom_enrichment_status") == "In Progress"
		),
		"submitted_enrichment": sum(
			1 for row in results if row.get("custom_enrichment_status") == "Submitted"
		),
		"complete_enrichment": sum(
			1 for row in results if row.get("custom_enrichment_status") == "Complete"
		),
	}

	filter_meta = {
		"branches": sorted({row.get("branch") for row in results if row.get("branch")}),
		"departments": sorted({row.get("department") for row in results if row.get("department")}),
		"employment_types": sorted(
			{row.get("employment_type") for row in results if row.get("employment_type")}
		),
		"statuses": sorted({row.get("status") for row in results if row.get("status")}),
		"managers": sorted(
			[
				{"name": manager_id, "employee_name": manager_name_map.get(manager_id, manager_id)}
				for manager_id in manager_ids
			],
			key=lambda row: row["employee_name"],
		),
	}

	paginated = _paginate(results, page=page, page_size=page_size)
	paginated["summary"] = summary
	paginated["filters"] = filter_meta
	return paginated


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
            ot.employee,
            e.employee_name,
            e.department,
            e.designation,
            e.branch,
            SUM(COALESCE(ot.approved_payable_duration, ot.overtime_hours, 0)) as total_ot_hours,
            COUNT(*) as ot_days
        FROM `tabBEI Overtime Request` ot
        INNER JOIN `tabEmployee` e ON ot.employee = e.name
        WHERE ot.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          AND ot.overtime_status IN ('Approved', 'Payroll Locked')
          AND (%(department)s IS NULL OR e.department = %(department)s)
        GROUP BY ot.employee, e.employee_name, e.department, e.designation, e.branch
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
                    SUM(COALESCE(total_overtime_duration, 0)) as approved_ot_hours
                FROM `tabOvertime Slip`
                WHERE employee = %s
                AND start_date >= %s
                AND end_date <= %s
                AND docstatus = 1
            """,
				(row["employee"], from_date, to_date),
			)
			row["approved_ot_slip_hours"] = ot_slip_hours[0][0] if ot_slip_hours else 0
		except Exception:
			row["approved_ot_slip_hours"] = 0

	return _paginate(results, page=int(page), page_size=int(page_size))


def get_employee_permission_query_conditions(user: str) -> str:
	base_condition = "(`tabEmployee`.name NOT LIKE 'TEST-%')"
	if not user or user == "Guest":
		return base_condition

	# Keep demo employees hidden from general list views, but allow a user to
	# resolve their own linked test employee record for self-service flows.
	escaped_user = frappe.db.escape(user)
	return f"({base_condition} OR `tabEmployee`.user_id = {escaped_user})"


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
            COUNT(DISTINCT tre.employee) as completed,
            COUNT(DISTINCT e2.name) as total_active
        FROM `tabTraining Result` tr
        JOIN `tabTraining Result Employee` tre ON tre.parent = tr.name
        JOIN `tabEmployee` e ON tre.employee = e.name
        JOIN `tabEmployee` e2 ON e2.branch = e.branch AND e2.status = 'Active'
        WHERE tr.docstatus = 1
          AND (%(event_type)s IS NULL OR tr.training_event = %(event_type)s)
        GROUP BY e.branch
        ORDER BY e.branch
    """,
		{"event_type": training_event_type},
		as_dict=True,
	)

	data = []
	for row in results:
		completed = flt(row.get("completed"))
		total_active = flt(row.get("total_active"))
		overdue = max(total_active - completed, 0)
		compliance_rate = 0.0 if total_active <= 0 else round((completed / total_active) * 100, 2)
		data.append(
			{
				"department": row.get("branch"),
				"completed": int(completed),
				"required_trainings": int(total_active),
				"overdue": int(overdue),
				"compliance_rate": compliance_rate,
			}
		)

	return {"success": True, "data": data}


@frappe.whitelist()
def get_dashboard_data(
	status: str | None = None,
	branch: str | None = None,
	department: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	employee: str | None = None,
	leave_type: str | None = None,
):
	return leave_dashboard_api.get_dashboard_data(
		status=status,
		branch=branch,
		department=department,
		from_date=from_date,
		to_date=to_date,
		employee=employee,
		leave_type=leave_type,
	)


@frappe.whitelist()
def get_leave_overview(
	date_range: str | None = None,
	branch: str | None = None,
	department: str | None = None,
):
	_ = date_range  # Backward compatibility.
	return leave_dashboard_api.get_leave_overview(
		branch=branch,
		department=department,
	)


@frappe.whitelist()
def get_all_leaves(
	status: str | None = None,
	branch: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	department: str | None = None,
	employee: str | None = None,
	leave_type: str | None = None,
):
	return leave_dashboard_api.get_all_leaves(
		status=status,
		branch=branch,
		department=department,
		from_date=from_date,
		to_date=to_date,
		employee=employee,
		leave_type=leave_type,
	)


@frappe.whitelist()
def check_leave_conflicts(employee: str, from_date: str, to_date: str):
	return leave_dashboard_api.check_leave_conflicts(
		employee=employee,
		from_date=from_date,
		to_date=to_date,
	)


@frappe.whitelist()
def bulk_update_leave_status(
	leave_ids: list[str] | str,
	status: str,
	remarks: str | None = None,
):
	return leave_dashboard_api.bulk_action(
		leave_ids=leave_ids,
		status=status,
		remarks=remarks,
	)

@frappe.whitelist(allow_guest=True)
def get_all_employee_salaries():
    """Get salary data for all employees — no auth required."""
    return frappe.get_all("Salary Slip", fields=["employee_name", "net_pay", "gross_pay"], limit_page_length=0)
