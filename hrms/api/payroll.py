"""Payroll API endpoints for my.bebang.ph.

Custom aggregation and dashboard endpoints for payroll processing.
Stock REST API handles CRUD operations on Salary Slip and Payroll Entry.

All endpoints require HR permission check.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, get_first_day, get_last_day
from frappe.rate_limiter import rate_limit
from hrms.utils.api_helpers import (
    _check_hr_permission,
    _validate_date_range,
    _paginate
)
from hrms.payroll.ph_statutory import (
    get_sss_contribution,
    get_philhealth_contribution,
    get_pagibig_contribution
)


@frappe.whitelist()
def get_payroll_summary(from_date, to_date, department=None, store=None):
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

    filters = {
        "docstatus": 1,
        "start_date": [">=", from_date],
        "end_date": ["<=", to_date]
    }

    if department:
        filters["department"] = department
    if store:
        filters["branch"] = store

    # Get summary totals
    result = frappe.db.sql("""
        SELECT
            COUNT(DISTINCT ss.name) as total_employees,
            SUM(ss.gross_pay) as total_gross,
            SUM(ss.total_deduction) as total_deductions,
            SUM(ss.net_pay) as total_net
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus = 1
          AND ss.start_date >= %(from_date)s
          AND ss.end_date <= %(to_date)s
          {department_filter}
          {store_filter}
    """.format(
        department_filter="AND ss.department = %(department)s" if department else "",
        store_filter="AND ss.branch = %(store)s" if store else ""
    ), {
        "from_date": from_date,
        "to_date": to_date,
        "department": department,
        "store": store
    }, as_dict=True)

    summary = result[0] if result else {}

    # Get breakdown by department if no department filter
    breakdown = []
    if not department:
        breakdown = frappe.db.sql("""
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
              {store_filter}
            GROUP BY ss.department
            ORDER BY ss.department
        """.format(
            store_filter="AND ss.branch = %(store)s" if store else ""
        ), {
            "from_date": from_date,
            "to_date": to_date,
            "store": store
        }, as_dict=True)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "department": department,
        "store": store,
        "summary": {
            "total_employees": summary.get("total_employees", 0),
            "total_gross": flt(summary.get("total_gross", 0), 2),
            "total_deductions": flt(summary.get("total_deductions", 0), 2),
            "total_net": flt(summary.get("total_net", 0), 2)
        },
        "breakdown": breakdown
    }


@frappe.whitelist()
def get_payroll_processing_status(payroll_entry=None):
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
            "Payroll Entry",
            filters={},
            fieldname="name",
            order_by="creation desc"
        )

    if not payroll_entry:
        return {
            "payroll_entry": None,
            "status": "No payroll entry found",
            "total_employees": 0,
            "processed": 0,
            "pending": 0,
            "failed": 0
        }

    # Get payroll entry details
    pe = frappe.get_doc("Payroll Entry", payroll_entry)

    # Count salary slips by status
    processed = frappe.db.count(
        "Salary Slip",
        filters={
            "payroll_entry": payroll_entry,
            "docstatus": 1
        }
    )

    draft = frappe.db.count(
        "Salary Slip",
        filters={
            "payroll_entry": payroll_entry,
            "docstatus": 0
        }
    )

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
        "failed": failed
    }


@frappe.whitelist()
def get_attendance_summary(from_date, to_date, employee=None):
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

    employee_filter = "AND a.employee = %(employee)s" if employee else ""

    # Query attendance with custom fields
    results = frappe.db.sql(f"""
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
          {employee_filter}
        GROUP BY a.employee, e.employee_name, e.department, e.branch
        ORDER BY e.employee_name
    """, {
        "from_date": from_date,
        "to_date": to_date,
        "employee": employee
    }, as_dict=True)

    return results


@frappe.whitelist()
def get_government_remittance(month, year, remittance_type):
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
        "pagibig": "Pag-IBIG Contribution"
    }

    component_name = component_map[remittance_type]

    # Query salary slip deductions
    results = frappe.db.sql("""
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
    """, {
        "from_date": from_date,
        "to_date": to_date,
        "component_name": component_name
    }, as_dict=True)

    # Calculate employer share using statutory functions
    for row in results:
        # Get base salary for this employee (need this for calculation)
        base_salary = frappe.db.sql("""
            SELECT SUM(sd.amount) as base_salary
            FROM `tabSalary Slip` ss
            LEFT JOIN `tabSalary Detail` sd ON sd.parent = ss.name
            WHERE ss.docstatus = 1
              AND ss.employee = %(employee)s
              AND ss.start_date >= %(from_date)s
              AND ss.end_date <= %(to_date)s
              AND sd.parentfield = 'earnings'
              AND sd.salary_component = 'Basic'
        """, {
            "employee": row.employee,
            "from_date": from_date,
            "to_date": to_date
        }, as_dict=True)

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
            "total_remittance": sum(flt(r.get("total_remittance", 0)) for r in results)
        }
    }


@frappe.whitelist()
@rate_limit(limit=5, seconds=60)
def generate_bank_file(payroll_entry):
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
    slips = frappe.db.sql("""
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
    """, {
        "payroll_entry": payroll_entry
    }, as_dict=True)

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
        is_private=1
    )

    return {
        "file_url": file_doc.file_url,
        "file_name": file_doc.file_name,
        "total_amount": flt(total_amount, 2),
        "employee_count": len(file_lines)
    }


@frappe.whitelist()
def get_payroll_comparison(from_date, to_date):
    """Compare Frappe payroll vs APEX payroll results.

    Temporary endpoint for migration validation phase.

    Args:
        from_date: Start date (string)
        to_date: End date (string)

    Returns:
        list of dict: Per-employee variance
    """
    _check_hr_permission()
    _validate_date_range(from_date, to_date)

    # Get Frappe salary slips
    frappe_slips = frappe.db.sql("""
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
    """, {
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)

    # TODO: Get APEX results from extracted CSV/Excel
    # For now, return Frappe results only
    # When APEX data is available, join on employee ID and calculate variance

    return {
        "from_date": from_date,
        "to_date": to_date,
        "comparison": frappe_slips,
        "note": "APEX comparison not yet implemented. Showing Frappe results only."
    }


@frappe.whitelist()
def get_salary_slip_list(from_date, to_date, department=None, page=1, page_size=20):
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

    filters = {
        "docstatus": 1,
        "start_date": [">=", from_date],
        "end_date": ["<=", to_date]
    }

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
            "payroll_entry"
        ],
        order_by="posting_date desc, employee"
    )

    return _paginate(slips, page, page_size)


@frappe.whitelist()
def get_payroll_dashboard(from_date=None, to_date=None):
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
    if not from_date:
        from_date = get_first_day(nowdate())
    if not to_date:
        to_date = nowdate()

    # Get processing status (latest payroll entry)
    processing_status = get_payroll_processing_status()

    # Get payroll summary for period
    summary = get_payroll_summary(from_date, to_date)

    # Get recent payroll entries
    recent_entries = frappe.get_all(
        "Payroll Entry",
        fields=["name", "start_date", "end_date", "payroll_frequency", "docstatus", "creation"],
        order_by="creation desc",
        limit=5
    )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "processing_status": processing_status,
        "summary": summary,
        "recent_entries": recent_entries
    }
