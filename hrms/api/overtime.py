"""
Overtime Approval API

DOLE compliance: shifts >8 hours require supervisor approval before payroll
inclusion. Unapproved OT hours are excluded from OT pay calculation.

Flow:
  1. Daily scheduled task scans Attendance for working_hours > 8
  2. Creates BEI Overtime Request records (Pending Approval)
  3. Supervisor calls approve_overtime() or reject_overtime()
  4. payroll/salary slip calculation checks overtime_status = 'Approved'
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime, getdate, add_days

from hrms.utils.api_helpers import _paginate


OT_THRESHOLD_HOURS = 8.0  # Hours beyond which overtime kicks in

# Roles allowed to approve/reject overtime
OT_APPROVER_ROLES = {"HR Manager", "Store Supervisor", "Area Supervisor", "System Manager"}


def _check_ot_approver_role():
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(OT_APPROVER_ROLES):
        frappe.throw(
            _("Only supervisors and HR managers can approve overtime"),
            frappe.PermissionError,
        )


# ================================
# DETECTION
# ================================

def detect_overtime_for_date(attendance_date=None):
    """Scan Attendance records for a given date and create BEI Overtime Request
    for any employee whose working_hours exceeds 8.

    Called by daily scheduled task. Safe to re-run — skips if request already exists.

    Args:
        attendance_date: Date string (YYYY-MM-DD). Defaults to yesterday.
    """
    if not attendance_date:
        attendance_date = str(add_days(getdate(nowdate()), -1))

    # Find attendance records with OT
    ot_records = frappe.db.sql("""
        SELECT
            a.name AS attendance_name,
            a.employee,
            a.attendance_date,
            a.working_hours,
            a.shift,
            e.reports_to AS supervisor
        FROM `tabAttendance` a
        LEFT JOIN `tabEmployee` e ON e.name = a.employee
        WHERE a.docstatus = 1
          AND a.attendance_date = %s
          AND a.working_hours > %s
    """, (attendance_date, OT_THRESHOLD_HOURS), as_dict=True)

    created = 0
    skipped = 0

    for rec in ot_records:
        # Idempotency: skip if BEI Overtime Request already exists for this attendance
        existing = frappe.db.exists("BEI Overtime Request", {
            "attendance": rec.attendance_name
        })
        if existing:
            skipped += 1
            continue

        ot_hours = flt(rec.working_hours) - OT_THRESHOLD_HOURS

        try:
            doc = frappe.new_doc("BEI Overtime Request")
            doc.employee = rec.employee
            doc.attendance = rec.attendance_name
            doc.attendance_date = rec.attendance_date
            doc.shift = rec.shift
            doc.total_hours = flt(rec.working_hours)
            doc.regular_hours = OT_THRESHOLD_HOURS
            doc.overtime_hours = round(ot_hours, 2)
            doc.overtime_status = "Pending Approval"
            doc.supervisor = rec.supervisor
            doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            frappe.log_error(
                f"Failed to create OT request for {rec.employee} on {rec.attendance_date}: {e}",
                "Overtime Detection"
            )

    frappe.logger("overtime").info(
        f"OT detection for {attendance_date}: {created} created, {skipped} skipped"
    )
    return {"date": attendance_date, "created": created, "skipped": skipped}


# ================================
# APPROVAL / REJECTION
# ================================

@frappe.whitelist()
def approve_overtime(overtime_request_name=None, notes=None, name=None, approval_notes=None):
    """Supervisor approves an overtime request.
    Status: Pending Approval → Approved

    Args:
        overtime_request_name: BEI Overtime Request name
        notes: Optional approval notes

    Returns:
        dict: {success, status, overtime_hours}
    """
    _check_ot_approver_role()

    overtime_request_name = overtime_request_name or name
    if not overtime_request_name:
        frappe.throw(_("Overtime request name is required"))

    notes = notes if notes is not None else approval_notes

    doc = frappe.get_doc("BEI Overtime Request", overtime_request_name)
    if doc.overtime_status != "Pending Approval":
        frappe.throw(_("Only 'Pending Approval' overtime requests can be approved"))

    doc.overtime_status = "Approved"
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()
    if notes:
        doc.approval_notes = notes
    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "name": doc.name,
        "status": doc.overtime_status,
        "overtime_hours": doc.overtime_hours,
        "employee": doc.employee,
    }


@frappe.whitelist()
def reject_overtime(overtime_request_name=None, reason=None, name=None, rejection_reason=None):
    """Supervisor rejects an overtime request.
    Status: Pending Approval → Rejected
    Effect: Employee paid for regular hours only (no OT pay in payroll).

    Args:
        overtime_request_name: BEI Overtime Request name
        reason: Required rejection reason

    Returns:
        dict: {success, status}
    """
    _check_ot_approver_role()

    overtime_request_name = overtime_request_name or name
    if not overtime_request_name:
        frappe.throw(_("Overtime request name is required"))

    reason = reason if reason is not None else rejection_reason
    if not reason:
        frappe.throw(_("Rejection reason is required"))

    doc = frappe.get_doc("BEI Overtime Request", overtime_request_name)
    if doc.overtime_status != "Pending Approval":
        frappe.throw(_("Only 'Pending Approval' overtime requests can be rejected"))

    doc.overtime_status = "Rejected"
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()
    doc.rejection_reason = reason
    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "name": doc.name,
        "status": doc.overtime_status,
        "employee": doc.employee,
    }


@frappe.whitelist()
def get_pending_overtime(store=None, employee=None, from_date=None, to_date=None):
    """Get overtime requests pending supervisor approval.

    Args:
        store: Optional store/branch filter
        employee: Optional employee filter
        from_date: Optional date range start
        to_date: Optional date range end

    Returns:
        list of dicts
    """
    _check_ot_approver_role()

    conditions = ["ot.overtime_status = 'Pending Approval'"]
    params = {}

    if employee:
        conditions.append("ot.employee = %(employee)s")
        params["employee"] = employee

    if from_date:
        conditions.append("ot.attendance_date >= %(from_date)s")
        params["from_date"] = from_date

    if to_date:
        conditions.append("ot.attendance_date <= %(to_date)s")
        params["to_date"] = to_date

    store_join = ""
    if store:
        store_join = "LEFT JOIN `tabEmployee` e ON e.name = ot.employee"
        conditions.append("e.branch = %(store)s")
        params["store"] = store

    where = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            ot.name,
            ot.employee,
            ot.attendance_date,
            ot.shift,
            ot.regular_hours,
            ot.overtime_hours,
            ot.total_hours,
            ot.supervisor,
            emp.employee_name,
            emp.branch
        FROM `tabBEI Overtime Request` ot
        LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
        {store_join}
        WHERE {where}
        ORDER BY ot.attendance_date DESC
    """, params, as_dict=True)


@frappe.whitelist()
def get_overtime_requests(
    status=None,
    store=None,
    employee=None,
    from_date=None,
    to_date=None,
    page=1,
    page_size=20,
):
    """Portal contract for overtime requests list with pagination."""
    _check_ot_approver_role()

    conditions = []
    params = {}

    if status:
        conditions.append("ot.overtime_status = %(status)s")
        params["status"] = status

    if employee:
        conditions.append("ot.employee = %(employee)s")
        params["employee"] = employee

    if from_date:
        conditions.append("ot.attendance_date >= %(from_date)s")
        params["from_date"] = from_date

    if to_date:
        conditions.append("ot.attendance_date <= %(to_date)s")
        params["to_date"] = to_date

    if store:
        conditions.append("emp.branch = %(store)s")
        params["store"] = store

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            ot.name,
            ot.employee,
            ot.attendance_date,
            ot.shift,
            ot.regular_hours,
            ot.overtime_hours,
            ot.total_hours,
            ot.overtime_status,
            ot.supervisor,
            ot.reviewed_by,
            ot.reviewed_at,
            ot.approval_notes,
            ot.rejection_reason,
            emp.employee_name,
            emp.branch
        FROM `tabBEI Overtime Request` ot
        LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
        {where_sql}
        ORDER BY ot.attendance_date DESC, ot.creation DESC
    """,
        params,
        as_dict=True,
    )

    return _paginate(rows, page=int(page or 1), page_size=int(page_size or 20))


@frappe.whitelist()
def get_overtime_summary(store=None, from_date=None, to_date=None):
    """Portal contract for overtime summary cards/tables."""
    _check_ot_approver_role()

    conditions = []
    params = {}

    if from_date:
        conditions.append("ot.attendance_date >= %(from_date)s")
        params["from_date"] = from_date

    if to_date:
        conditions.append("ot.attendance_date <= %(to_date)s")
        params["to_date"] = to_date

    if store:
        conditions.append("emp.branch = %(store)s")
        params["store"] = store

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    summary = frappe.db.sql(
        f"""
        SELECT
            COALESCE(emp.department, 'Unassigned') AS department,
            COALESCE(emp.branch, 'Unassigned') AS store,
            COUNT(*) AS total_requests,
            COALESCE(SUM(ot.overtime_hours), 0) AS total_hours,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Approved' THEN ot.overtime_hours ELSE 0 END), 0) AS approved_hours,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Pending Approval' THEN ot.overtime_hours ELSE 0 END), 0) AS pending_hours,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Rejected' THEN ot.overtime_hours ELSE 0 END), 0) AS rejected_hours,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Approved' THEN 1 ELSE 0 END), 0) AS approved_count,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Pending Approval' THEN 1 ELSE 0 END), 0) AS pending_count,
            COALESCE(SUM(CASE WHEN ot.overtime_status = 'Rejected' THEN 1 ELSE 0 END), 0) AS rejected_count
        FROM `tabBEI Overtime Request` ot
        LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
        {where_sql}
        GROUP BY COALESCE(emp.department, 'Unassigned'), COALESCE(emp.branch, 'Unassigned')
        ORDER BY store ASC, department ASC
    """,
        params,
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
        totals["total_requests"] += int(row.get("total_requests") or 0)
        totals["total_hours"] += flt(row.get("total_hours"))
        totals["approved_hours"] += flt(row.get("approved_hours"))
        totals["pending_hours"] += flt(row.get("pending_hours"))
        totals["rejected_hours"] += flt(row.get("rejected_hours"))

    return {"summary": summary, "totals": totals}


@frappe.whitelist()
def get_approved_overtime_hours(employee, from_date, to_date):
    """Get total approved overtime hours for an employee in a date range.

    Used by payroll processing to calculate OT pay — only approved hours included.

    Args:
        employee: Employee ID
        from_date: Period start
        to_date: Period end

    Returns:
        dict: {approved_hours, pending_hours, rejected_hours}
    """
    rows = frappe.db.sql("""
        SELECT overtime_status, COALESCE(SUM(overtime_hours), 0) as hours
        FROM `tabBEI Overtime Request`
        WHERE employee = %s
          AND attendance_date BETWEEN %s AND %s
        GROUP BY overtime_status
    """, (employee, from_date, to_date), as_dict=True)

    result = {"approved_hours": 0.0, "pending_hours": 0.0, "rejected_hours": 0.0}
    status_map = {
        "Approved": "approved_hours",
        "Pending Approval": "pending_hours",
        "Rejected": "rejected_hours",
    }
    for row in rows:
        key = status_map.get(row.overtime_status)
        if key:
            result[key] = flt(row.hours)

    return result


# ================================
# SCHEDULED TASK
# ================================

def scheduled_overtime_detection():
    """Daily scheduled task: detect OT for yesterday's attendance.

    Called by hooks.py cron (daily).
    """
    yesterday = str(add_days(getdate(nowdate()), -1))
    result = detect_overtime_for_date(attendance_date=yesterday)
    frappe.logger("overtime").info(
        f"Scheduled OT detection complete: {result}"
    )
