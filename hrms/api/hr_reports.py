"""HR Reports API endpoints for employee masterlist, headcount, attrition, attendance, and OT"""

import frappe
from frappe import _
from frappe.utils import getdate, date_diff, flt, today, add_days
from hrms.utils.api_helpers import (
    _check_hr_permission,
    _validate_date_range,
    _paginate,
)


@frappe.whitelist()
def get_employee_masterlist(
    status=None,
    department=None,
    store=None,
    employment_type=None,
    page=1,
    page_size=50,
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
def get_headcount_report(group_by="department", as_of_date=None):
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

    # Group by specified field
    results = frappe.db.sql(
        f"""
        SELECT
            {group_by} as group_name,
            COUNT(*) as count
        FROM `tabEmployee`
        WHERE status = 'Active'
        AND date_of_joining <= %s
        AND (relieving_date IS NULL OR relieving_date > %s)
        GROUP BY {group_by}
        ORDER BY count DESC
    """,
        (as_of_date, as_of_date),
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
def get_attrition_report(from_date, to_date, group_by="department"):
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

    # Get separations in period
    separations = frappe.db.sql(
        f"""
        SELECT
            {group_by} as group_name,
            COUNT(*) as separation_count
        FROM `tabEmployee`
        WHERE relieving_date BETWEEN %s AND %s
        GROUP BY {group_by}
    """,
        (from_date, to_date),
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
        row["attrition_rate"] = (
            round((row["separation_count"] / group_avg * 100), 2) if group_avg > 0 else 0
        )
        if not row["group_name"]:
            row["group_name"] = _("Unassigned")

    # Overall attrition
    total_separations = sum(r["separation_count"] for r in separations)
    overall_attrition = (
        round((total_separations / avg_headcount * 100), 2) if avg_headcount > 0 else 0
    )

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
def get_new_hires_report(from_date, to_date, department=None):
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
def get_separations_report(from_date, to_date, department=None):
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
def get_recruitment_funnel(from_date=None, to_date=None):
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
    from_date,
    to_date,
    employee=None,
    department=None,
    page=1,
    page_size=50,
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

    # Build WHERE clause
    where_conditions = ["a.attendance_date BETWEEN %(from_date)s AND %(to_date)s"]
    filters = {"from_date": from_date, "to_date": to_date}

    if employee:
        where_conditions.append("a.employee = %(employee)s")
        filters["employee"] = employee
    if department:
        where_conditions.append("e.department = %(department)s")
        filters["department"] = department

    where_clause = " AND ".join(where_conditions)

    # Query attendance summary
    results = frappe.db.sql(
        f"""
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
            SUM(COALESCE(a.overtime_hours, 0)) as total_ot_hours
        FROM `tabAttendance` a
        INNER JOIN `tabEmployee` e ON a.employee = e.name
        WHERE {where_clause}
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
def get_overtime_report(from_date, to_date, department=None, page=1, page_size=50):
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

    # Build WHERE clause
    where_conditions = ["a.attendance_date BETWEEN %(from_date)s AND %(to_date)s"]
    filters = {"from_date": from_date, "to_date": to_date}

    if department:
        where_conditions.append("e.department = %(department)s")
        filters["department"] = department

    where_clause = " AND ".join(where_conditions)

    # Query OT from Attendance records
    results = frappe.db.sql(
        f"""
        SELECT
            a.employee,
            e.employee_name,
            e.department,
            e.designation,
            e.branch,
            SUM(COALESCE(a.overtime_hours, 0)) as total_ot_hours,
            COUNT(CASE WHEN a.overtime_hours > 0 THEN 1 END) as ot_days
        FROM `tabAttendance` a
        INNER JOIN `tabEmployee` e ON a.employee = e.name
        WHERE {where_clause}
        GROUP BY a.employee, e.employee_name, e.department, e.designation, e.branch
        HAVING total_ot_hours > 0
        ORDER BY total_ot_hours DESC
    """,
        filters,
        as_dict=True,
    )

    # Get approved OT Slip records for breakdown
    for row in results:
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

    return _paginate(results, page=int(page), page_size=int(page_size))
