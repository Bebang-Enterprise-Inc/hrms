"""Payroll API endpoints for my.bebang.ph.

Custom aggregation and dashboard endpoints for payroll processing.
Stock REST API handles CRUD operations on Salary Slip and Payroll Entry.

All endpoints require HR permission check.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from hrms.payroll.ph_statutory import (
	get_pagibig_contribution,
	get_philhealth_contribution,
	get_sss_contribution,
)
from hrms.utils.api_helpers import _check_hr_permission, _paginate, _validate_date_range


@frappe.whitelist()
def get_payroll_summary(
	from_date: str,
	to_date: str,
	department: str | None = None,
	store: str | None = None,
) -> dict:
	"""Get payroll summary for a cutoff period.

	Returns total gross, total deductions, total net grouped by department/store if specified.

	Args:
	    from_date: Start date (string)
	    to_date: End date (string)
	    department: Optional department filter (string)
	    store: Optional store/branch filter (string)

	Returns:
	    dict: Summary with totals and breakdown
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	filters = {"docstatus": 1, "start_date": [">=", from_date], "end_date": ["<=", to_date]}

	if department:
		filters["department"] = department
	if store:
		filters["branch"] = store

	# Get summary totals
	params = {"from_date": from_date, "to_date": to_date}
	summary_query = """
        SELECT
            COUNT(DISTINCT ss.name) as total_employees,
            SUM(ss.gross_pay) as total_gross,
            SUM(ss.total_deduction) as total_deductions,
            SUM(ss.net_pay) as total_net
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(from_date)s
          AND ss.end_date <= %(to_date)s
    """
	if department:
		summary_query += "\n          AND ss.department = %(department)s"
		params["department"] = department
	if store:
		summary_query += "\n          AND ss.branch = %(store)s"
		params["store"] = store

	result = frappe.db.sql(summary_query, params, as_dict=True)

	summary = result[0] if result else {}

	# Get breakdown by department if no department filter
	breakdown = []
	if not department:
		breakdown_query = """
            SELECT
                ss.department,
                COUNT(DISTINCT ss.name) as employee_count,
                SUM(ss.gross_pay) as gross_pay,
                SUM(ss.total_deduction) as deductions,
                SUM(ss.net_pay) as net_pay
            FROM `tabSalary Slip` ss
            WHERE ss.docstatus = 1
              AND ss.start_date >= %(from_date)s
              AND ss.end_date <= %(to_date)s
        """
		breakdown_params = {"from_date": from_date, "to_date": to_date}
		if store:
			breakdown_query += "\n              AND ss.branch = %(store)s"
			breakdown_params["store"] = store

		breakdown_query += "\n            GROUP BY ss.department\n            ORDER BY ss.department"
		breakdown = frappe.db.sql(breakdown_query, breakdown_params, as_dict=True)

	return {
		"from_date": from_date,
		"to_date": to_date,
		"department": department,
		"store": store,
		"summary": {
			"total_employees": summary.get("total_employees", 0),
			"total_gross": flt(summary.get("total_gross", 0), 2),
			"total_deductions": flt(summary.get("total_deductions", 0), 2),
			"total_net": flt(summary.get("total_net", 0), 2),
		},
		"breakdown": breakdown,
	}


@frappe.whitelist()
def get_payroll_processing_status(payroll_entry: str | None = None) -> dict:
	"""Get status of payroll processing.

	Shows counts of total employees, processed, pending for a Payroll Entry.
	Used for real-time polling (refetchInterval: 3000).

	Args:
	    payroll_entry: Optional Payroll Entry name. If None, uses latest.

	Returns:
	    dict: Processing status with counts
	"""
	_check_hr_permission()

	# Get latest payroll entry if not specified
	if not payroll_entry:
		payroll_entry = frappe.db.get_value(
			"Payroll Entry", filters={}, fieldname="name", order_by="creation desc"
		)

	if not payroll_entry:
		return {
			"payroll_entry": None,
			"status": "No payroll entry found",
			"total_employees": 0,
			"processed": 0,
			"pending": 0,
			"failed": 0,
		}

	# Get payroll entry details
	pe = frappe.get_doc("Payroll Entry", payroll_entry)

	# Count salary slips by status
	processed = frappe.db.count("Salary Slip", filters={"payroll_entry": payroll_entry, "docstatus": 1})

	draft = frappe.db.count("Salary Slip", filters={"payroll_entry": payroll_entry, "docstatus": 0})

	# Failed = employees in payroll entry but no salary slip created
	total_in_entry = len(pe.employees) if hasattr(pe, "employees") else 0
	created_slips = processed + draft
	failed = max(0, total_in_entry - created_slips)

	return {
		"payroll_entry": payroll_entry,
		"status": pe.docstatus,
		"start_date": pe.start_date,
		"end_date": pe.end_date,
		"payroll_frequency": pe.payroll_frequency,
		"total_employees": total_in_entry,
		"processed": processed,
		"pending": draft,
		"failed": failed,
	}


@frappe.whitelist()
def get_attendance_summary(from_date: str, to_date: str, employee: str | None = None) -> list[dict]:
	"""Get attendance summary per employee.

	Returns present days, absent days, leave days, tardiness, undertime, OT hours.

	Args:
	    from_date: Start date (string)
	    to_date: End date (string)
	    employee: Optional employee filter (string)

	Returns:
	    list of dict: Per-employee attendance summary
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	# Query attendance with custom fields
	attendance_query = """
        SELECT
            a.employee,
            e.employee_name,
            e.department,
            e.branch,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN a.status = 'On Leave' THEN 1 ELSE 0 END) as leave_days,
            SUM(CASE WHEN a.late_entry = 1 THEN 1 ELSE 0 END) as late_days,
            SUM(CASE WHEN a.early_exit = 1 THEN 1 ELSE 0 END) as early_exit_days,
            SUM(GREATEST(COALESCE(a.working_hours, 0) - 8, 0)) as ot_hours
        FROM `tabAttendance` a
        LEFT JOIN `tabEmployee` e ON e.name = a.employee
        WHERE a.docstatus = 1
          AND a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY a.employee, e.employee_name, e.department, e.branch
        ORDER BY e.employee_name
    """
	attendance_params = {"from_date": from_date, "to_date": to_date}
	if employee:
		attendance_query += "\n          AND a.employee = %(employee)s"
		attendance_params["employee"] = employee

	results = frappe.db.sql(attendance_query, attendance_params, as_dict=True)

	return results


@frappe.whitelist()
def get_government_remittance(month: int | str, year: int | str, remittance_type: str) -> dict:
	"""Get government remittance report for a month.

	Returns per-employee contributions for SSS, PhilHealth, or Pag-IBIG.

	Args:
	    month: Month number (1-12)
	    year: Year (e.g., 2025)
	    remittance_type: "sss", "philhealth", "pagibig"

	Returns:
	    list of dict: Per-employee remittance details
	"""
	_check_hr_permission()

	# Validate inputs
	try:
		month = int(month)
		year = int(year)
	except (ValueError, TypeError):
		frappe.throw(_("Invalid month or year"))

	if month < 1 or month > 12:
		frappe.throw(_("Month must be between 1 and 12"))

	remittance_type = remittance_type.lower() if remittance_type else ""
	if remittance_type not in ["sss", "philhealth", "pagibig"]:
		frappe.throw(_("Invalid remittance type. Must be 'sss', 'philhealth', or 'pagibig'"))

	# Calculate date range
	from_date = getdate(f"{year}-{month:02d}-01")
	to_date = get_last_day(from_date)

	# Map remittance type to deduction component name
	# Adjust these names based on actual BEI Salary Component setup
	component_map = {
		"sss": "SSS Contribution",
		"philhealth": "PhilHealth Contribution",
		"pagibig": "Pag-IBIG Contribution",
	}

	component_name = component_map[remittance_type]

	# Query salary slip deductions
	results = frappe.db.sql(
		"""
        SELECT
            ss.employee,
            ss.employee_name,
            ss.department,
            ss.branch,
            SUM(sd.amount) as employee_contribution
        FROM `tabSalary Slip` ss
        LEFT JOIN `tabSalary Detail` sd ON sd.parent = ss.name
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(from_date)s
          AND ss.end_date <= %(to_date)s
          AND sd.parentfield = 'deductions'
          AND sd.salary_component = %(component_name)s
        GROUP BY ss.employee, ss.employee_name, ss.department, ss.branch
        ORDER BY ss.employee_name
    """,
		{"from_date": from_date, "to_date": to_date, "component_name": component_name},
		as_dict=True,
	)

	# Calculate employer share using statutory functions
	for row in results:
		# Get base salary for this employee (need this for calculation)
		base_salary = frappe.db.sql(
			"""
            SELECT SUM(sd.amount) as base_salary
            FROM `tabSalary Slip` ss
            LEFT JOIN `tabSalary Detail` sd ON sd.parent = ss.name
            WHERE ss.docstatus = 1
              AND ss.employee = %(employee)s
              AND ss.start_date >= %(from_date)s
              AND ss.end_date <= %(to_date)s
              AND sd.parentfield = 'earnings'
              AND sd.salary_component = 'Basic'
        """,
			{"employee": row.employee, "from_date": from_date, "to_date": to_date},
			as_dict=True,
		)

		base = flt(base_salary[0].base_salary) if base_salary and base_salary[0].base_salary else 0

		# Calculate employer share
		if remittance_type == "sss":
			_ee_share, employer_share, ec = get_sss_contribution(base)
			row["employer_contribution"] = flt(employer_share, 2)
			row["ec_contribution"] = flt(ec, 2)
			row["total_remittance"] = flt(row.employee_contribution + employer_share + ec, 2)
		elif remittance_type == "philhealth":
			_ee_share, employer_share = get_philhealth_contribution(base)
			row["employer_contribution"] = flt(employer_share, 2)
			row["total_remittance"] = flt(row.employee_contribution + employer_share, 2)
		elif remittance_type == "pagibig":
			_ee_share, employer_share = get_pagibig_contribution(base)
			row["employer_contribution"] = flt(employer_share, 2)
			row["total_remittance"] = flt(row.employee_contribution + employer_share, 2)

	return {
		"month": month,
		"year": year,
		"remittance_type": remittance_type,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"employees": results,
		"grand_total": {
			"employee_contribution": sum(flt(r.get("employee_contribution", 0)) for r in results),
			"employer_contribution": sum(flt(r.get("employer_contribution", 0)) for r in results),
			"total_remittance": sum(flt(r.get("total_remittance", 0)) for r in results),
		},
	}


@frappe.whitelist()
@rate_limit(limit=5, seconds=60)
def generate_bank_file(payroll_entry: str) -> dict:
	"""Generate BPI bank transfer file for payroll disbursement.

	Args:
	    payroll_entry: Payroll Entry name (string)

	Returns:
	    dict: File URL for download
	"""
	_check_hr_permission()

	if not payroll_entry:
		frappe.throw(_("Payroll Entry is required"))

	# Get all submitted salary slips for this payroll entry
	slips = frappe.db.sql(
		"""
        SELECT
            ss.employee,
            ss.employee_name,
            ss.net_pay,
            ss.bank_name,
            ss.bank_account_no
        FROM `tabSalary Slip` ss
        WHERE ss.payroll_entry = %(payroll_entry)s
          AND ss.docstatus = 1
          AND ss.net_pay > 0
        ORDER BY ss.employee
    """,
		{"payroll_entry": payroll_entry},
		as_dict=True,
	)

	if not slips:
		frappe.throw(_("No submitted salary slips found for this payroll entry"))

	# Generate BPI format file (adjust format based on BEI's actual bank requirements)
	# BPI format typically: Account Number, Amount, Employee Name (tab-delimited)
	file_lines = []
	total_amount = 0

	for slip in slips:
		if not slip.bank_account_no:
			frappe.msgprint(
				_("Employee {0} does not have bank account number. Skipped.").format(slip.employee_name)
			)
			continue

		line = f"{slip.bank_account_no}\t{slip.net_pay:.2f}\t{slip.employee_name}"
		file_lines.append(line)
		total_amount += slip.net_pay

	# Add header and footer
	header = f"BEI PAYROLL\t{payroll_entry}\t{frappe.utils.now()}\n"
	footer = f"\nTOTAL\t{total_amount:.2f}\t{len(file_lines)} employees"

	file_content = header + "\n".join(file_lines) + footer

	# Save as File doc
	from frappe.utils.file_manager import save_file

	file_doc = save_file(
		fname=f"BPI_Payroll_{payroll_entry}.txt",
		content=file_content,
		dt="Payroll Entry",
		dn=payroll_entry,
		is_private=1,
	)

	return {
		"file_url": file_doc.file_url,
		"file_name": file_doc.file_name,
		"total_amount": flt(total_amount, 2),
		"employee_count": len(file_lines),
	}


@frappe.whitelist()
def get_payroll_comparison(from_date: str, to_date: str, apex_results: list | str | None = None) -> dict:
	"""Compare Frappe payroll vs APEX payroll results.

	Args:
	    from_date: Start date (string)
	    to_date: End date (string)
	    apex_results: Optional list/JSON payload for APEX payroll rows

	Returns:
	    dict: Per-employee comparison and summary variance
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	# Get Frappe salary slips
	frappe_slips = frappe.db.sql(
		"""
        SELECT
            ss.employee,
            ss.employee_name,
            ss.gross_pay as frappe_gross,
            ss.total_deduction as frappe_deductions,
            ss.net_pay as frappe_net
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(from_date)s
          AND ss.end_date <= %(to_date)s
        ORDER BY ss.employee
    """,
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	apex_rows = _parse_apex_rows(apex_results)
	frappe_rows = [dict(row) for row in frappe_slips]

	if not apex_rows:
		comparison = []
		for row in frappe_rows:
			row["apex_gross"] = None
			row["apex_deductions"] = None
			row["apex_net"] = None
			row["variance_net"] = None
			comparison.append(row)

		return {
			"from_date": from_date,
			"to_date": to_date,
			"mode": "frappe_only",
			"comparison": comparison,
			"summary": {
				"frappe_count": len(frappe_rows),
				"apex_count": 0,
				"matched_count": 0,
				"variance_net_total": 0.0,
			},
			"note": "APEX dataset not supplied for this request.",
		}

	frappe_map = {row.get("employee"): row for row in frappe_rows if row.get("employee")}
	apex_map = {}
	for row in apex_rows:
		employee = row["employee"]
		if employee not in apex_map:
			apex_map[employee] = {
				"employee": employee,
				"employee_name": row.get("employee_name"),
				"apex_gross": 0.0,
				"apex_deductions": 0.0,
				"apex_net": 0.0,
			}
		apex_map[employee]["apex_gross"] += flt(row.get("apex_gross"))
		apex_map[employee]["apex_deductions"] += flt(row.get("apex_deductions"))
		apex_map[employee]["apex_net"] += flt(row.get("apex_net"))
		if row.get("employee_name") and not apex_map[employee].get("employee_name"):
			apex_map[employee]["employee_name"] = row["employee_name"]

	comparison = []
	matched_count = 0
	variance_net_total = 0.0
	all_employees = sorted(set(frappe_map.keys()) | set(apex_map.keys()))
	for employee in all_employees:
		frappe_row = frappe_map.get(employee)
		apex_row = apex_map.get(employee)
		frappe_net = flt(frappe_row.get("frappe_net")) if frappe_row else None
		apex_net = flt(apex_row.get("apex_net")) if apex_row else None
		variance = None
		if frappe_net is not None and apex_net is not None:
			variance = flt(frappe_net - apex_net, 2)
			matched_count += 1
			variance_net_total += variance

		comparison.append(
			{
				"employee": employee,
				"employee_name": (
					frappe_row.get("employee_name") if frappe_row else apex_row.get("employee_name")
				),
				"frappe_gross": flt(frappe_row.get("frappe_gross")) if frappe_row else None,
				"frappe_deductions": flt(frappe_row.get("frappe_deductions")) if frappe_row else None,
				"frappe_net": frappe_net,
				"apex_gross": flt(apex_row.get("apex_gross")) if apex_row else None,
				"apex_deductions": flt(apex_row.get("apex_deductions")) if apex_row else None,
				"apex_net": apex_net,
				"variance_net": variance,
			}
		)

	return {
		"from_date": from_date,
		"to_date": to_date,
		"mode": "with_apex",
		"comparison": comparison,
		"summary": {
			"frappe_count": len(frappe_rows),
			"apex_count": len(apex_map),
			"matched_count": matched_count,
			"variance_net_total": flt(variance_net_total, 2),
		},
	}


def _parse_apex_rows(apex_results: list | str | None) -> list[dict]:
	if not apex_results:
		return []
	if isinstance(apex_results, str):
		apex_results = frappe.parse_json(apex_results)

	if not isinstance(apex_results, list):
		frappe.throw(_("apex_results must be a list of payroll rows"))

	parsed_rows = []
	for idx, raw in enumerate(apex_results):
		if not isinstance(raw, dict):
			frappe.throw(_("Invalid apex_results row at index {0}: expected object").format(idx))

		employee = (
			raw.get("employee") or raw.get("employee_id") or raw.get("employee_code") or raw.get("name")
		)
		if not employee:
			continue
		employee = str(employee).strip()
		if not employee:
			continue

		parsed_rows.append(
			{
				"employee": employee,
				"employee_name": raw.get("employee_name"),
				"apex_gross": flt(raw.get("apex_gross", raw.get("gross_pay"))),
				"apex_deductions": flt(raw.get("apex_deductions", raw.get("deductions"))),
				"apex_net": flt(raw.get("apex_net", raw.get("net_pay"))),
			}
		)

	return parsed_rows


@frappe.whitelist()
def get_salary_slip_list(
	from_date: str,
	to_date: str,
	department: str | None = None,
	page: int | str = 1,
	page_size: int | str = 20,
) -> dict:
	"""Get paginated salary slip list.

	Args:
	    from_date: Start date (string)
	    to_date: End date (string)
	    department: Optional department filter (string)
	    page: Page number (int, default 1)
	    page_size: Results per page (int, default 20)

	Returns:
	    dict: Paginated salary slip data
	"""
	_check_hr_permission()
	_validate_date_range(from_date, to_date)

	page = int(page)
	page_size = int(page_size)

	filters = {"docstatus": 1, "start_date": [">=", from_date], "end_date": ["<=", to_date]}

	if department:
		filters["department"] = department

	# Get salary slips
	slips = frappe.get_all(
		"Salary Slip",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"branch",
			"posting_date",
			"start_date",
			"end_date",
			"gross_pay",
			"total_deduction",
			"net_pay",
			"payroll_entry",
		],
		order_by="posting_date desc, employee",
	)

	return _paginate(slips, page, page_size)


@frappe.whitelist()
def get_my_payslips(limit: int | str = 12) -> dict:
	"""Get current employee's own salary slips (self-service).

	No HR permission check needed — returns only the logged-in user's payslips.

	Args:
	    limit: Max number of slips to return (default 12 = 1 year)

	Returns:
	    dict: {success, payslips} or {success, error}
	"""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"success": False, "error": "No employee record found for your account"}

	slips = frappe.get_all(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=[
			"name",
			"posting_date",
			"start_date",
			"end_date",
			"gross_pay",
			"total_deduction",
			"net_pay",
			"status",
		],
		order_by="posting_date desc",
		limit=int(limit),
	)
	return {"success": True, "payslips": slips}


@frappe.whitelist()
def get_my_attendance(from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Get current employee's own attendance records (self-service).

	No HR permission check — returns only the logged-in user's attendance.

	Args:
	    from_date: Start date (defaults to 30 days ago)
	    to_date: End date (defaults to today)

	Returns:
	    dict: {success, attendance} or {success, error}
	"""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"success": False, "error": "No employee record found for your account"}

	if not to_date:
		to_date = nowdate()
	if not from_date:
		from_date = str(add_months(getdate(to_date), -1))

	records = frappe.get_all(
		"Attendance",
		filters={"employee": employee, "docstatus": 1, "attendance_date": ["between", [from_date, to_date]]},
		fields=[
			"name",
			"attendance_date",
			"status",
			"shift",
			"working_hours",
			"late_entry",
			"early_exit",
			"leave_type",
		],
		order_by="attendance_date desc",
	)

	# Summary counts
	present = sum(1 for r in records if r.get("status") == "Present")
	absent = sum(1 for r in records if r.get("status") == "Absent")
	on_leave = sum(1 for r in records if r.get("status") == "On Leave")
	late = sum(1 for r in records if r.get("late_entry"))

	return {
		"success": True,
		"attendance": records,
		"summary": {
			"total_days": len(records),
			"present": present,
			"absent": absent,
			"on_leave": on_leave,
			"late": late,
		},
	}


@frappe.whitelist()
def submit_leave_application(
	leave_type: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	reason: str | None = None,
	half_day: int | str = 0,
) -> dict:
	"""Submit a leave application for the current employee (self-service).

	Creates a Leave Application document for the logged-in user.

	Args:
	    leave_type: Type of leave (e.g., "Casual Leave", "Sick Leave")
	    from_date: Leave start date
	    to_date: Leave end date
	    reason: Optional reason for the leave
	    half_day: 1 for half-day leave, 0 for full day (default 0)

	Returns:
	    dict: {success, name, status} or {success, error}
	"""
	if not leave_type or not from_date or not to_date:
		frappe.throw(_("Leave type, from date, and to date are required"))

	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user},
		["name", "employee_name", "company", "leave_approver"],
		as_dict=True,
	)
	if not employee:
		return {"success": False, "error": "No employee record found for your account"}

	try:
		doc = frappe.new_doc("Leave Application")
		doc.employee = employee.name
		doc.leave_type = leave_type
		doc.from_date = from_date
		doc.to_date = to_date
		doc.description = reason or ""
		doc.half_day = int(half_day)
		doc.company = employee.company
		if employee.leave_approver:
			doc.leave_approver = employee.leave_approver
		doc.status = "Open"
		doc.insert(ignore_permissions=True)

		# Create approval queue entry so leave appears in supervisor's pending approvals
		if employee.leave_approver:
			try:
				store = None
				branch = frappe.db.get_value("Employee", employee.name, "branch")
				if branch:
					from hrms.api.store import resolve_warehouse

					try:
						store = resolve_warehouse(branch)
					except Exception:
						store = None
				if store:
					queue_entry = frappe.new_doc("BEI Approval Queue")
					queue_entry.reference_doctype = "Leave Application"
					queue_entry.reference_name = doc.name
					queue_entry.assigned_approver = employee.leave_approver
					queue_entry.status = "Pending"
					queue_entry.store = store
					queue_entry.submitted_by = frappe.session.user
					queue_entry.submitted_at = frappe.utils.now()
					queue_entry.insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(
					f"Failed to create approval queue for leave {doc.name}", "Approval Queue Error"
				)

		return {"success": True, "name": doc.name, "status": doc.status}

	except frappe.exceptions.ValidationError as e:
		return {"success": False, "error": str(e)}
	except Exception as e:
		frappe.log_error(
			message=f"Leave application failed for {employee.name}: {str(e)[:500]}",
			title="Leave Application Error",
		)
		return {"success": False, "error": "Failed to submit leave application. Please try again."}


@frappe.whitelist()
def get_my_schedule(from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Get current employee's shift schedule (self-service).

	No HR permission check — returns only the logged-in user's schedule.

	Args:
	    from_date: Start date (defaults to today)
	    to_date: End date (defaults to 14 days from now)

	Returns:
	    dict: {success, schedule} or {success, error}
	"""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {"success": False, "error": "No employee record found for your account"}

	if not from_date:
		from_date = nowdate()
	if not to_date:
		to_date = str(getdate(from_date) + __import__("datetime").timedelta(days=14))

	# Get shift assignments
	shifts = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"start_date": ["<=", to_date],
		},
		fields=["name", "shift_type", "start_date", "end_date", "status"],
		order_by="start_date asc",
	)

	# Filter to date range (end_date can be null = ongoing)
	schedule = []
	for s in shifts:
		if s.get("end_date") and str(s["end_date"]) < from_date:
			continue
		schedule.append(s)

	return {"success": True, "schedule": schedule}


@frappe.whitelist()
def get_payroll_readiness_check() -> dict:
	"""Pre-flight readiness check for payroll processing.

	Checks S076 day-zero blockers:
	- Company default_payroll_payable_account
	- Income tax slab assignment on SSAs
	- Active employees without Salary Structure Assignment
	- Bank details coverage

	Returns:
	    dict: Categorized blockers with owner and remediation
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="payroll",
		action="get_payroll_readiness_check",
		mutation_type="read",
	)
	_check_hr_permission()

	blockers = []
	warnings = []

	# 1. Check default_payroll_payable_account
	company = frappe.db.get_value(
		"Company",
		frappe.defaults.get_user_default("Company") or "Bebang Enterprise Inc.",
		["name", "default_payroll_payable_account"],
		as_dict=True,
	)
	if not company or not company.default_payroll_payable_account:
		blockers.append({
			"category": "gl_account",
			"title": "Payroll Payable Account Not Set",
			"description": "Company does not have a default payroll payable account. Payroll Entry cannot post journal entries without this.",
			"owner": "Finance Team",
			"remediation": f"Go to Company > {company.name if company else 'Bebang Enterprise Inc.'} > Accounts Settings > set Default Payroll Payable Account",
			"severity": "critical",
		})

	# 2. Check income tax slab on SSAs
	total_ssa = frappe.db.count("Salary Structure Assignment", {"docstatus": 1})
	ssa_without_tax = frappe.db.count(
		"Salary Structure Assignment",
		{"docstatus": 1, "income_tax_slab": ["in", ["", None]]},
	)
	if ssa_without_tax > 0:
		blockers.append({
			"category": "tax_slab",
			"title": f"{ssa_without_tax} of {total_ssa} Salary Structure Assignments Missing Tax Slab",
			"description": "BIR withholding tax will compute as zero for these employees.",
			"owner": "HR Team",
			"remediation": "Assign 'TRAIN Law 2025 - Philippines' income tax slab to all SSAs",
			"severity": "critical",
			"count": ssa_without_tax,
			"total": total_ssa,
		})

	# 3. Check active employees without SSA
	active_count = frappe.db.count("Employee", {"status": "Active"})
	employees_with_ssa = frappe.db.sql("""
		SELECT COUNT(DISTINCT ssa.employee)
		FROM `tabSalary Structure Assignment` ssa
		INNER JOIN `tabEmployee` e ON e.name = ssa.employee
		WHERE ssa.docstatus = 1 AND e.status = 'Active'
	""")[0][0]
	missing_ssa = active_count - employees_with_ssa
	if missing_ssa > 0:
		blockers.append({
			"category": "missing_ssa",
			"title": f"{missing_ssa} Active Employees Without Salary Structure",
			"description": "These employees cannot be included in payroll until they have a submitted Salary Structure Assignment.",
			"owner": "HR Team",
			"remediation": "Create and submit Salary Structure Assignments for these employees",
			"severity": "critical",
			"count": missing_ssa,
			"total": active_count,
		})

	# 4. Check Payroll Period exists
	current_year = frappe.utils.now_datetime().year
	payroll_period = frappe.db.exists(
		"Payroll Period",
		{
			"company": company.name if company else "Bebang Enterprise Inc.",
			"start_date": ["<=", frappe.utils.nowdate()],
			"end_date": [">=", frappe.utils.nowdate()],
		},
	)
	if not payroll_period:
		blockers.append({
			"category": "payroll_period",
			"title": "No Active Payroll Period",
			"description": f"No Payroll Period covers the current date ({frappe.utils.nowdate()}). Tax calculations require an active period.",
			"owner": "HR Team",
			"remediation": f"Create a Payroll Period for {current_year} with start and end dates covering the full year",
			"severity": "critical",
		})

	# 5. Bank details coverage (warning, not blocker)
	employees_with_bank = frappe.db.sql("""
		SELECT COUNT(*) FROM `tabEmployee`
		WHERE status = 'Active'
		  AND bank_ac_no IS NOT NULL AND bank_ac_no != ''
	""")[0][0]
	missing_bank = active_count - employees_with_bank
	if missing_bank > 0:
		warnings.append({
			"category": "bank_details",
			"title": f"{missing_bank} of {active_count} Active Employees Missing Bank Details",
			"description": "These employees will be excluded from bank file generation. Payroll can still proceed.",
			"owner": "HR Team (enrichment in progress)",
			"severity": "warning",
			"count": missing_bank,
			"total": active_count,
		})

	is_ready = len(blockers) == 0

	return {
		"is_ready": is_ready,
		"blockers": blockers,
		"warnings": warnings,
		"summary": {
			"active_employees": active_count,
			"employees_with_ssa": employees_with_ssa,
			"employees_with_bank": employees_with_bank,
			"total_ssa": total_ssa,
			"ssa_with_tax_slab": total_ssa - ssa_without_tax,
			"has_payable_account": bool(company and company.default_payroll_payable_account),
			"has_payroll_period": bool(payroll_period),
		},
	}


@frappe.whitelist()
def get_processing_blockers(from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Get employee-level processing blockers.

	Returns list of employees who cannot be processed and why.

	Args:
	    from_date: Payroll period start
	    to_date: Payroll period end

	Returns:
	    dict: Employee-level blocker details
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="payroll",
		action="get_processing_blockers",
		mutation_type="read",
	)
	_check_hr_permission()

	if not from_date:
		from_date = get_first_day(nowdate())
	if not to_date:
		to_date = get_last_day(from_date)

	# Get active employees
	employees = frappe.db.sql("""
		SELECT
			e.name as employee,
			e.employee_name,
			e.department,
			e.branch,
			e.bank_ac_no,
			e.bank_name
		FROM `tabEmployee` e
		WHERE e.status = 'Active'
		ORDER BY e.employee_name
	""", as_dict=True)

	# Get employees with submitted SSA
	ssa_map = {}
	ssas = frappe.db.sql("""
		SELECT employee, salary_structure, income_tax_slab
		FROM `tabSalary Structure Assignment`
		WHERE docstatus = 1
		ORDER BY from_date DESC
	""", as_dict=True)
	for ssa in ssas:
		if ssa.employee not in ssa_map:
			ssa_map[ssa.employee] = ssa

	blocked = []
	ready = []

	for emp in employees:
		issues = []
		ssa = ssa_map.get(emp.employee)

		if not ssa:
			issues.append({
				"type": "no_ssa",
				"message": "No Salary Structure Assignment",
				"severity": "critical",
			})
		else:
			if not ssa.income_tax_slab:
				issues.append({
					"type": "no_tax_slab",
					"message": "No income tax slab assigned",
					"severity": "critical",
				})

		if not emp.bank_ac_no:
			issues.append({
				"type": "no_bank",
				"message": "No bank account number",
				"severity": "warning",
			})

		emp_entry = {
			"employee": emp.employee,
			"employee_name": emp.employee_name,
			"department": emp.department,
			"branch": emp.branch,
			"has_ssa": bool(ssa),
			"has_tax_slab": bool(ssa and ssa.income_tax_slab),
			"has_bank": bool(emp.bank_ac_no),
			"issues": issues,
		}

		if any(i["severity"] == "critical" for i in issues):
			blocked.append(emp_entry)
		else:
			ready.append(emp_entry)

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"total_employees": len(employees),
		"ready_count": len(ready),
		"blocked_count": len(blocked),
		"blocked_employees": blocked,
		"ready_employees": ready,
	}


@frappe.whitelist()
def start_payroll_processing(
	from_date: str,
	to_date: str,
	payroll_frequency: str = "Monthly",
	department: str | None = None,
	branch: str | None = None,
) -> dict:
	"""Initiate payroll entry creation with validation gate.

	Runs readiness check first. If blockers exist, returns them without creating.

	Args:
	    from_date: Payroll period start
	    to_date: Payroll period end
	    payroll_frequency: Monthly, Bimonthly, etc.
	    department: Optional department filter
	    branch: Optional branch filter

	Returns:
	    dict: Created Payroll Entry details or blocker list
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="payroll",
		action="start_payroll_processing",
		mutation_type="create",
	)
	_check_hr_permission()

	if not from_date or not to_date:
		frappe.throw(_("Both from_date and to_date are required"))

	_validate_date_range(from_date, to_date)

	# Run readiness check first
	readiness = get_payroll_readiness_check()
	if not readiness["is_ready"]:
		return {
			"success": False,
			"stage": "readiness_check_failed",
			"blockers": readiness["blockers"],
			"message": "Cannot start payroll processing. Resolve all blockers first.",
		}

	# Get company
	company = frappe.defaults.get_user_default("Company") or "Bebang Enterprise Inc."

	try:
		# Create Payroll Entry
		pe = frappe.new_doc("Payroll Entry")
		pe.company = company
		pe.start_date = from_date
		pe.end_date = to_date
		pe.payroll_frequency = payroll_frequency
		pe.cost_center = frappe.db.get_value("Company", company, "cost_center")
		pe.payment_account = frappe.db.get_value("Company", company, "default_payroll_payable_account")

		if department:
			pe.department = department
		if branch:
			pe.branch = branch

		pe.insert(ignore_permissions=True)

		# Get employees for this payroll entry
		pe.fill_employee_details()
		pe.save()

		return {
			"success": True,
			"stage": "payroll_entry_created",
			"payroll_entry": pe.name,
			"employee_count": len(pe.employees) if hasattr(pe, "employees") else 0,
			"message": f"Payroll Entry {pe.name} created with {len(pe.employees) if hasattr(pe, 'employees') else 0} employees.",
		}

	except Exception as e:
		frappe.log_error(
			message=f"Payroll processing failed: {str(e)[:500]}",
			title="Payroll Processing Error",
		)
		return {
			"success": False,
			"stage": "creation_failed",
			"error": str(e),
			"message": "Failed to create Payroll Entry. Check error log for details.",
		}


@frappe.whitelist()
def get_remittance_summary(year: int | str | None = None) -> dict:
	"""Get aggregated remittance totals by type and period.

	Returns monthly totals for SSS, PhilHealth, Pag-IBIG, and BIR
	for the specified year.

	Args:
	    year: Year to summarize (defaults to current year)

	Returns:
	    dict: Monthly totals per remittance type
	"""
	from hrms.utils.sentry import set_backend_observability_context

	set_backend_observability_context(
		module="payroll",
		action="get_remittance_summary",
		mutation_type="read",
	)
	_check_hr_permission()

	if not year:
		year = frappe.utils.now_datetime().year
	year = int(year)

	# Component mapping
	component_map = {
		"sss": "SSS Contribution",
		"philhealth": "PhilHealth Contribution",
		"pagibig": "Pag-IBIG Contribution",
		"bir": "Income Tax",
	}

	results = {}
	for rtype, component in component_map.items():
		monthly = []
		for month in range(1, 13):
			from_date = getdate(f"{year}-{month:02d}-01")
			to_date = get_last_day(from_date)

			totals = frappe.db.sql("""
				SELECT
					COUNT(DISTINCT ss.employee) as employee_count,
					SUM(sd.amount) as total_amount
				FROM `tabSalary Slip` ss
				INNER JOIN `tabSalary Detail` sd ON sd.parent = ss.name
				WHERE ss.docstatus = 1
				  AND ss.start_date >= %(from_date)s
				  AND ss.end_date <= %(to_date)s
				  AND sd.parentfield = 'deductions'
				  AND sd.salary_component = %(component)s
			""", {
				"from_date": from_date,
				"to_date": to_date,
				"component": component,
			}, as_dict=True)

			row = totals[0] if totals else {}
			monthly.append({
				"month": month,
				"employee_count": row.get("employee_count", 0) or 0,
				"total_amount": flt(row.get("total_amount", 0), 2),
			})

		year_total = sum(m["total_amount"] for m in monthly)
		year_employees = max((m["employee_count"] for m in monthly), default=0)

		results[rtype] = {
			"component_name": component,
			"monthly": monthly,
			"year_total": flt(year_total, 2),
			"max_monthly_employees": year_employees,
		}

	return {
		"year": year,
		"remittance_types": results,
		"has_data": any(
			results[rt]["year_total"] > 0 for rt in results
		),
	}


@frappe.whitelist()
def get_payroll_dashboard(from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Get combined payroll dashboard data.

	Combines processing status + summary + recent entries for dashboard view.

	Args:
	    from_date: Optional start date (defaults to current month start)
	    to_date: Optional end date (defaults to today)

	Returns:
	    dict: Combined dashboard data
	"""
	_check_hr_permission()

	# Default to current month if dates not provided
	# Cast to str because get_first_day returns datetime.date but downstream
	# functions have str type annotations that Frappe validates at runtime.
	if not from_date:
		from_date = str(get_first_day(nowdate()))
	if not to_date:
		to_date = str(nowdate())

	# Get processing status (latest payroll entry)
	processing_status = get_payroll_processing_status()

	# Get payroll summary for period
	summary = get_payroll_summary(from_date, to_date)

	# Get recent payroll entries
	recent_entries = frappe.get_all(
		"Payroll Entry",
		fields=["name", "start_date", "end_date", "payroll_frequency", "docstatus", "creation"],
		order_by="creation desc",
		limit=5,
	)

	return {
		"from_date": from_date,
		"to_date": to_date,
		"processing_status": processing_status,
		"summary": summary,
		"recent_entries": recent_entries,
	}
