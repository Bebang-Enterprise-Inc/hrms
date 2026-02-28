import json
from typing import Any

import frappe
from frappe.utils import add_days, today


ALLOWED_ROLES = ["HR Manager", "System Manager", "HR User", "Area Supervisor"]


def _enforce_access() -> None:
    frappe.only_for(ALLOWED_ROLES)


def _build_employee_conditions(branch: str | None = None, department: str | None = None) -> tuple[list[str], dict[str, Any]]:
    conditions = ["e.status = 'Active'"]
    values: dict[str, Any] = {}

    if branch:
        conditions.append("e.branch = %(branch)s")
        values["branch"] = branch

    if department:
        conditions.append("e.department = %(department)s")
        values["department"] = department

    return conditions, values


def _build_leave_conditions(
    status: str | None = None,
    branch: str | None = None,
    department: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    employee: str | None = None,
    leave_type: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    conditions = ["1=1"]
    values: dict[str, Any] = {}

    if status:
        conditions.append("la.status = %(status)s")
        values["status"] = status

    if branch:
        conditions.append("e.branch = %(branch)s")
        values["branch"] = branch

    if department:
        conditions.append("e.department = %(department)s")
        values["department"] = department

    if from_date:
        conditions.append("la.to_date >= %(from_date)s")
        values["from_date"] = from_date

    if to_date:
        conditions.append("la.from_date <= %(to_date)s")
        values["to_date"] = to_date

    if employee:
        conditions.append(
            "(la.employee = %(employee_exact)s OR la.employee LIKE %(employee_like)s OR la.employee_name LIKE %(employee_like)s)"
        )
        values["employee_exact"] = employee
        values["employee_like"] = f"%{employee}%"

    if leave_type:
        conditions.append("la.leave_type = %(leave_type)s")
        values["leave_type"] = leave_type

    return conditions, values


@frappe.whitelist()
def get_leave_overview(branch: str | None = None, department: str | None = None) -> dict[str, int]:
    _enforce_access()

    current_date = today()
    seven_days_from_now = add_days(current_date, 7)
    employee_conditions, employee_values = _build_employee_conditions(branch, department)
    employee_where = " AND ".join(employee_conditions)

    total_employees = frappe.db.sql(
        f"""
        SELECT count(name)
        FROM `tabEmployee` e
        WHERE {employee_where}
        """,
        employee_values,
    )[0][0]

    values_today = {"today": current_date, **employee_values}
    on_leave_today = frappe.db.sql(
        f"""
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
          AND la.docstatus = 1
          AND %(today)s BETWEEN la.from_date AND la.to_date
          AND {employee_where}
        """,
        values_today,
    )[0][0]

    pending_count = frappe.db.sql(
        f"""
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Open'
          AND la.docstatus = 0
          AND {employee_where}
        """,
        employee_values,
    )[0][0]

    values_upcoming = {"today": current_date, "next_7": seven_days_from_now, **employee_values}
    upcoming_count = frappe.db.sql(
        f"""
        SELECT count(la.name)
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
          AND la.docstatus = 1
          AND la.from_date > %(today)s
          AND la.from_date <= %(next_7)s
          AND {employee_where}
        """,
        values_upcoming,
    )[0][0]

    return {
        "on_leave_today": int(on_leave_today or 0),
        "pending_count": int(pending_count or 0),
        "upcoming_count": int(upcoming_count or 0),
        "total_employees": int(total_employees or 0),
    }


@frappe.whitelist()
def get_all_leaves(
    status: str | None = None,
    branch: str | None = None,
    department: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    employee: str | None = None,
    leave_type: str | None = None,
) -> list[dict[str, Any]]:
    _enforce_access()

    leave_conditions, values = _build_leave_conditions(
        status=status,
        branch=branch,
        department=department,
        from_date=from_date,
        to_date=to_date,
        employee=employee,
        leave_type=leave_type,
    )
    leave_where = " AND ".join(leave_conditions)

    query = f"""
        SELECT
            la.name,
            la.employee,
            la.employee_name,
            la.leave_type,
            la.from_date,
            la.to_date,
            la.total_leave_days,
            la.status,
            la.description,
            e.branch,
            e.department,
            e.image AS employee_image,
            e.designation
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE {leave_where}
        ORDER BY la.from_date DESC, la.modified DESC
    """

    return frappe.db.sql(query, values, as_dict=True)


def _to_calendar_events(leaves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for leave in leaves:
        start = leave.get("from_date")
        end = leave.get("to_date")
        if not start or not end:
            continue

        events.append(
            {
                "id": leave.get("name"),
                "title": f"{leave.get('employee_name', leave.get('employee', 'Employee'))} - {leave.get('leave_type', 'Leave')}",
                "start_date": str(start),
                "end_date": str(end),
                "status": leave.get("status"),
                "branch": leave.get("branch"),
                "department": leave.get("department"),
                "leave_type": leave.get("leave_type"),
            }
        )
    return events


@frappe.whitelist()
def get_dashboard_data(
    status: str | None = None,
    branch: str | None = None,
    department: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    employee: str | None = None,
    leave_type: str | None = None,
) -> dict[str, Any]:
    _enforce_access()

    kpis = get_leave_overview(branch=branch, department=department)
    pending_requests = get_all_leaves(
        status="Open",
        branch=branch,
        department=department,
        from_date=from_date,
        to_date=to_date,
        employee=employee,
        leave_type=leave_type,
    )

    history_status = status if status and status != "Open" else None
    historical_requests = get_all_leaves(
        status=history_status,
        branch=branch,
        department=department,
        from_date=from_date,
        to_date=to_date,
        employee=employee,
        leave_type=leave_type,
    )
    historical_requests = [item for item in historical_requests if item.get("status") != "Open"]

    calendar_events = _to_calendar_events(historical_requests if historical_requests else pending_requests)

    return {
        "kpis": kpis,
        "pending_requests": pending_requests,
        "historical_requests": historical_requests,
        "calendar_events": calendar_events,
    }


@frappe.whitelist()
def check_leave_conflicts(employee: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
    _enforce_access()

    employee_details = frappe.db.get_value("Employee", employee, ["branch", "department"], as_dict=True)
    if not employee_details:
        return []

    branch = employee_details.get("branch")
    department = employee_details.get("department")
    if not branch or not department:
        return []

    query = """
        SELECT
            la.name AS leave_id,
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

    return frappe.db.sql(
        query,
        {
            "employee": employee,
            "branch": branch,
            "department": department,
            "from_date": from_date,
            "to_date": to_date,
        },
        as_dict=True,
    )


def _parse_leave_ids(leave_ids: Any) -> list[str]:
    if isinstance(leave_ids, list):
        return [str(value) for value in leave_ids if value]

    if isinstance(leave_ids, str):
        try:
            parsed = json.loads(leave_ids)
            if isinstance(parsed, list):
                return [str(value) for value in parsed if value]
        except json.JSONDecodeError:
            return [value.strip() for value in leave_ids.split(",") if value.strip()]

    return []


@frappe.whitelist()
def bulk_action(leave_ids: list[str] | str, status: str, remarks: str | None = None) -> dict[str, Any]:
    _enforce_access()

    normalized_leave_ids = _parse_leave_ids(leave_ids)
    if not normalized_leave_ids:
        frappe.throw("At least one leave ID is required.")

    if status not in {"Approved", "Rejected"}:
        frappe.throw("Status must be Approved or Rejected")

    results: dict[str, Any] = {"success": [], "failed": []}

    for leave_id in normalized_leave_ids:
        try:
            doc = frappe.get_doc("Leave Application", leave_id)
            if doc.status != "Open":
                results["failed"].append({"id": leave_id, "error": f"Leave is already {doc.status}"})
                continue

            if status == "Approved":
                if doc.docstatus == 0:
                    doc.flags.ignore_permissions = True
                    doc.submit()
                else:
                    doc.db_set("status", "Approved")
            else:
                doc.db_set("status", "Rejected")

            if remarks and hasattr(doc, "add_comment"):
                doc.add_comment("Comment", f"Bulk leave action: {status}. Remarks: {remarks}")

            results["success"].append(leave_id)
        except Exception as exc:  # pragma: no cover - pass-through path
            results["failed"].append({"id": leave_id, "error": str(exc)})

    return results
