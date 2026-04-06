"""HR Reports API endpoints for employee masterlist, headcount, attrition, attendance, and OT"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate, today

from hrms.api import leave_dashboard as leave_dashboard_api
from hrms.api.payroll_compensation import (
	compute_pagibig_employee,
	compute_philhealth_employee,
	compute_sss_employee,
	compute_monthly_tax,
)
from hrms.utils.api_helpers import (
	_check_hr_permission,
	_paginate,
	_validate_date_range,
)
from hrms.utils.sentry import set_backend_observability_context


@frappe.whitelist()
def get_employee_masterlist(
	status: str | None = None,
	department: str | None = None,
	store: str | None = None,
	employment_type: str | None = None,
	search: str | None = None,
	reports_to: str | None = None,
	exception: str | None = None,
	page: int = 1,
	page_size: int = 50,
	detail: str | None = None,
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
	    detail: If provided, return full detail for this single employee ID

	Returns:
	    dict: Paginated employee list with summary + filter metadata, or single employee detail
	"""
	_check_hr_permission()

	if detail:
		return _get_employee_detail(detail)

	page = max(int(page or 1), 1)
	page_size = min(max(int(page_size or 50), 1), 1000)

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
			"attendance_device_id",
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

	# Employees with an active (submitted) Salary Structure Assignment
	employees_with_salary = set(
		frappe.get_all(
			"Salary Structure Assignment",
			filters={"docstatus": 1},
			pluck="employee",
		)
	)

	# Profile completion fields — each filled field adds to the percentage
	_profile_fields = [
		"employee_name", "date_of_birth", "gender", "cell_number",
		"personal_email", "company_email", "department", "designation",
		"branch", "reports_to", "date_of_joining", "employment_type",
	]

	for row in results:
		if not row.get("custom_enrichment_status"):
			row["custom_enrichment_status"] = "Not Started"
		row["reports_to_name"] = manager_name_map.get(row.get("reports_to"), "")
		row["has_bio_id"] = bool(row.get("attendance_device_id"))
		row["has_pending_enrichment"] = row.get("name") in open_enrichment_employees
		row["has_salary_structure"] = row.get("name") in employees_with_salary
		# Compute profile completion %
		filled = sum(1 for f in _profile_fields if row.get(f))
		row["profile_completion"] = round(filled / len(_profile_fields) * 100)

	summary = {
		"total_employees": len(results),
		"active": sum(1 for row in results if row.get("status") == "Active"),
		"inactive": sum(1 for row in results if row.get("status") != "Active"),
		"missing_manager": sum(1 for row in results if not row.get("reports_to")),
		"missing_company_email": sum(1 for row in results if not row.get("company_email")),
		"missing_bio_id": sum(1 for row in results if not row.get("has_bio_id")),
		"missing_dob": sum(1 for row in results if not row.get("date_of_birth")),
		"missing_designation": sum(1 for row in results if not row.get("designation")),
		"missing_salary": sum(1 for row in results if not row.get("has_salary_structure")),
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

	# Apply exception filter AFTER summary so chip counts reflect full data
	if exception:
		_exception_filters = {
			"missing_manager": lambda r: not r.get("reports_to"),
			"missing_dob": lambda r: not r.get("date_of_birth"),
			"missing_designation": lambda r: not r.get("designation"),
			"missing_email": lambda r: not r.get("company_email"),
			"missing_salary": lambda r: not r.get("has_salary_structure"),
		}
		predicate = _exception_filters.get(exception)
		if predicate:
			results = [row for row in results if predicate(row)]

	paginated = _paginate(results, page=page, page_size=page_size)
	paginated["summary"] = summary
	paginated["filters"] = filter_meta
	return paginated


def _get_employee_detail(employee_id: str) -> dict:
	"""Return structured employee detail grouped by section for the EmployeeDetailDialog.

	Called when get_employee_masterlist(detail=employee_id) is used.
	"""
	set_backend_observability_context(
		module="hr",
		action="get_employee_detail",
		mutation_type="read",
	)

	if not frappe.db.exists("Employee", employee_id):
		frappe.throw(_("Employee {0} not found").format(employee_id), frappe.DoesNotExistError)

	# --- Personal, emergency, employment fields ---
	emp_fields = [
		"name", "employee_name", "first_name", "middle_name", "last_name",
		"date_of_birth", "gender", "marital_status", "blood_group",
		"cell_number", "personal_email", "current_address", "permanent_address",
		"custom_nickname", "custom_uniform_size",
		# Emergency
		"person_to_be_contacted", "emergency_phone_number", "relation",
		# Employment
		"department", "designation", "branch", "employment_type",
		"date_of_joining", "status", "company", "reports_to",
		"company_email", "custom_work_phone", "user_id",
		# Bank
		"salary_mode", "bank_name", "bank_account_name", "bank_ac_no",
		# Gov IDs
		"tin_number", "sss_number", "philhealth_number", "pagibig_number",
		# Enrichment
		"custom_enrichment_status", "custom_enrichment_submitted_date",
		"custom_enrichment_complete_date",
		"custom_tin_verified", "custom_sss_verified",
		"custom_philhealth_verified", "custom_pagibig_verified",
	]

	# Guard ALL fields — filter out any that don't exist on the DocType (S161 lesson)
	_meta = frappe.get_meta("Employee")
	_valid_fields = {f.fieldname for f in _meta.fields} | {"name"}
	emp_fields = [f for f in emp_fields if f in _valid_fields]

	# Check bei_* allowance columns exist
	allowance_fields = [
		"bei_comm_allow_monthly", "bei_deminimis_monthly", "bei_honorarium_monthly",
		"bei_meal_allow_monthly", "bei_gasoline_allow_monthly", "bei_other_fixed_monthly",
	]
	existing_cols = {
		r[0] for r in frappe.db.sql("SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'")
	}
	has_allowance_cols = all(f in existing_cols for f in allowance_fields)
	if has_allowance_cols:
		emp_fields.extend(allowance_fields)

	emp = frappe.db.get_value("Employee", employee_id, emp_fields, as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found").format(employee_id), frappe.DoesNotExistError)

	# Resolve reports_to name
	reports_to_name = ""
	if emp.get("reports_to"):
		reports_to_name = frappe.db.get_value("Employee", emp.reports_to, "employee_name") or ""

	# --- Personal section ---
	personal = {
		"employee_name": emp.employee_name,
		"first_name": emp.first_name,
		"middle_name": emp.middle_name,
		"last_name": emp.last_name,
		"date_of_birth": str(emp.date_of_birth) if emp.date_of_birth else None,
		"gender": emp.gender,
		"marital_status": emp.marital_status,
		"blood_group": emp.get("blood_group"),
		"cell_number": emp.cell_number,
		"personal_email": emp.personal_email,
		"current_address": emp.current_address,
		"permanent_address": emp.permanent_address,
		"custom_nickname": emp.get("custom_nickname"),
		"custom_uniform_size": emp.get("custom_uniform_size"),
	}

	# --- Emergency section ---
	emergency = {
		"person_to_be_contacted": emp.get("person_to_be_contacted"),
		"emergency_phone_number": emp.get("emergency_phone_number"),
		"relation": emp.get("relation"),
	}

	# --- Employment section ---
	employment = {
		"department": emp.department,
		"branch": emp.branch,
		"designation": emp.designation,
		"employment_type": emp.employment_type,
		"date_of_joining": str(emp.date_of_joining) if emp.date_of_joining else None,
		"reports_to": emp.reports_to,
		"reports_to_name": reports_to_name,
		"status": emp.status,
		"company": emp.company,
		"company_email": emp.company_email,
		"custom_work_phone": emp.get("custom_work_phone"),
		"user_id": emp.user_id,
	}

	# --- Compensation section (reuse payroll_compensation pattern) ---
	compensation = {}
	for f in allowance_fields:
		compensation[f] = float(emp.get(f) or 0) if has_allowance_cols else 0

	# Latest SSA
	ssa = frappe.db.sql(
		"""
		SELECT base, salary_structure, income_tax_slab, from_date
		FROM `tabSalary Structure Assignment`
		WHERE employee = %s AND docstatus = 1
		ORDER BY from_date DESC LIMIT 1
		""",
		employee_id,
		as_dict=True,
	)
	if ssa:
		compensation["base_salary"] = float(ssa[0].base or 0)
		compensation["salary_structure"] = ssa[0].salary_structure
		compensation["tax_slab"] = ssa[0].income_tax_slab
		compensation["ssa_from_date"] = str(ssa[0].from_date) if ssa[0].from_date else None
	else:
		compensation["base_salary"] = 0
		compensation["salary_structure"] = None
		compensation["tax_slab"] = None
		compensation["ssa_from_date"] = None

	# Projected deductions
	base = compensation["base_salary"]
	compensation["projected_sss"] = compute_sss_employee(base)
	compensation["projected_philhealth"] = compute_philhealth_employee(base)
	compensation["projected_pagibig"] = compute_pagibig_employee(base)
	compensation["projected_tax"] = compute_monthly_tax(base)

	# Bank info (masked)
	compensation["salary_mode"] = emp.salary_mode
	compensation["bank_name"] = emp.bank_name
	compensation["bank_account_name"] = emp.get("bank_account_name")
	bank_ac_no = emp.bank_ac_no or ""
	compensation["bank_ac_no"] = ("****" + bank_ac_no[-4:]) if len(bank_ac_no) > 4 else bank_ac_no

	# Pending compensation changes count
	compensation["pending_changes_count"] = 0
	if frappe.db.exists("DocType", "BEI Compensation Change"):
		compensation["pending_changes_count"] = frappe.db.count(
			"BEI Compensation Change",
			filters={
				"employee": employee_id,
				"status": ("in", ["Pending HR Manager", "Pending Accounts Manager"]),
			},
		)

	# --- Gov IDs (masked) ---
	def _mask(val):
		val = val or ""
		return ("****" + val[-4:]) if len(val) > 4 else val

	gov_ids = {
		"tin_number": _mask(emp.get("tin_number")),
		"sss_number": _mask(emp.get("sss_number")),
		"philhealth_number": _mask(emp.get("philhealth_number")),
		"pagibig_number": _mask(emp.get("pagibig_number")),
	}

	# --- Enrichment status ---
	# Check for pending enrichment (guard DocType existence)
	has_pending_enrichment = False
	if frappe.db.exists("DocType", "BEI Onboarding Request"):
		has_pending_enrichment = bool(
			frappe.db.exists(
				"BEI Onboarding Request",
				{
					"employee": employee_id,
					"request_type": "update_existing",
					"status": ("in", ["Pending", "Escalated", "Revision Requested"]),
				},
			)
		)
	enrichment = {
		"custom_enrichment_status": emp.get("custom_enrichment_status") or "Not Started",
		"custom_enrichment_submitted_date": str(emp.custom_enrichment_submitted_date) if emp.get("custom_enrichment_submitted_date") else None,
		"custom_enrichment_complete_date": str(emp.custom_enrichment_complete_date) if emp.get("custom_enrichment_complete_date") else None,
		"custom_tin_verified": emp.get("custom_tin_verified"),
		"custom_sss_verified": emp.get("custom_sss_verified"),
		"custom_philhealth_verified": emp.get("custom_philhealth_verified"),
		"custom_pagibig_verified": emp.get("custom_pagibig_verified"),
		"has_pending_enrichment": has_pending_enrichment,
	}

	# --- Recent changes (last 10 combined) ---
	comp_changes = []
	if frappe.db.exists("DocType", "BEI Compensation Change"):
		comp_changes = frappe.get_all(
			"BEI Compensation Change",
			filters={"employee": employee_id},
			fields=[
				"name", "'compensation' as source", "change_type",
				"salary_component", "employee_field_name",
				"old_value", "new_value", "status",
				"requested_by", "submission_date as change_date",
			],
			order_by="creation DESC",
			limit_page_length=10,
		)
	sensitive_changes = []
	if frappe.db.exists("DocType", "BEI Sensitive Change Request"):
		sensitive_changes = frappe.get_all(
			"BEI Sensitive Change Request",
			filters={"employee": employee_id},
			fields=[
				"name", "'sensitive' as source", "field_name as change_type",
				"'' as salary_component", "field_name as employee_field_name",
				"old_value", "new_value", "status",
				"initiated_by as requested_by", "submission_date as change_date",
			],
			order_by="creation DESC",
			limit_page_length=10,
		)
	all_changes = sorted(
		comp_changes + sensitive_changes,
		key=lambda r: str(r.get("change_date") or ""),
		reverse=True,
	)[:10]
	# Convert dates to strings for JSON
	for ch in all_changes:
		if ch.get("change_date"):
			ch["change_date"] = str(ch["change_date"])

	return {
		"employee": emp.name,
		"personal": personal,
		"emergency": emergency,
		"employment": employment,
		"compensation": compensation,
		"gov_ids": gov_ids,
		"enrichment": enrichment,
		"recent_changes": all_changes,
	}


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
