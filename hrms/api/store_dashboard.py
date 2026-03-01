"""
Supervisor dashboard aggregation endpoints for my.bebang.ph.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate


SUPERVISOR_DASHBOARD_ROLES = {
    "Area Supervisor",
    "Store Supervisor",
    "HR Manager",
    "System Manager",
}


def _check_dashboard_access():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(SUPERVISOR_DASHBOARD_ROLES):
        frappe.throw(_("Only supervisor roles can access store dashboard endpoints."), frappe.PermissionError)


def _period_window(period):
    period = (period or "today").strip().lower()
    if period not in {"today", "week"}:
        frappe.throw(_("Invalid period. Allowed values: today, week."))

    today = getdate(nowdate())
    if period == "today":
        return period, today, today

    week_start = add_days(today, -today.weekday())
    return period, week_start, today


def _get_store_scope():
    try:
        from hrms.api import supervisor as supervisor_api

        stores = supervisor_api._get_area_supervisor_stores(frappe.session.user)
        store_names = [row.name for row in stores if row.get("name")]
        if store_names:
            return sorted(set(store_names))
    except Exception:
        pass

    branch = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user, "status": "Active"},
        "branch",
    )
    if not branch:
        return []

    exact_warehouse = frappe.db.get_value("Warehouse", branch, "name")
    if exact_warehouse:
        return [exact_warehouse]

    labeled_warehouse = frappe.db.get_value(
        "Warehouse",
        {"warehouse_name": branch, "is_group": 0},
        "name",
    )
    if labeled_warehouse:
        return [labeled_warehouse]

    return [branch]


def _safe_count(doctype, filters):
    try:
        return cint(frappe.db.count(doctype, filters=filters))
    except Exception:
        return 0


def _count_pending_overtime(store_names, start_date, end_date):
    if not store_names:
        return 0

    params = {
        "stores": tuple(store_names),
        "start_date": start_date,
        "end_date": end_date,
    }
    row = frappe.db.sql(
        """
        SELECT COUNT(ot.name) AS total
        FROM `tabBEI Overtime Request` ot
        LEFT JOIN `tabEmployee` emp ON emp.name = ot.employee
        WHERE ot.overtime_status = 'Pending Approval'
          AND emp.branch IN %(stores)s
          AND ot.attendance_date BETWEEN %(start_date)s AND %(end_date)s
        """,
        params,
        as_dict=True,
    )
    return cint(row[0].total if row else 0)


def _iter_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current = add_days(current, 1)


@frappe.whitelist()
def get_supervisor_dashboard_summary(period="today"):
    """Return KPI summary payload expected by portal supervisor dashboard."""
    _check_dashboard_access()
    _period, start_date, end_date = _period_window(period)
    store_names = _get_store_scope()

    expected_days = max(1, date_diff(end_date, start_date) + 1)
    expected_reports = len(store_names) * expected_days

    if not store_names:
        return {
            "stores": [],
            "store_count": 0,
            "kpis": {
                "opening_reports": 0,
                "closing_reports": 0,
                "pending_orders": 0,
                "pending_overtime": 0,
                "open_fqi": 0,
                "expected_reports": 0,
            },
        }

    opening_reports = _safe_count(
        "BEI Store Opening Report",
        {"store": ["in", store_names], "report_date": ["between", [start_date, end_date]]},
    )
    closing_reports = _safe_count(
        "BEI Store Closing Report",
        {"store": ["in", store_names], "report_date": ["between", [start_date, end_date]]},
    )
    pending_orders = _safe_count(
        "BEI Store Order",
        {"store": ["in", store_names], "status": "Pending Approval"},
    )
    pending_overtime = _count_pending_overtime(store_names, start_date, end_date)
    open_fqi = _safe_count(
        "BEI FQI Report",
        {"store": ["in", store_names], "status": "Open"},
    )

    return {
        "stores": store_names,
        "store_count": len(store_names),
        "kpis": {
            "opening_reports": opening_reports,
            "closing_reports": closing_reports,
            "pending_orders": pending_orders,
            "pending_overtime": pending_overtime,
            "open_fqi": open_fqi,
            "expected_reports": expected_reports,
        },
    }


@frappe.whitelist()
def get_pending_reports(period="today", status="Missing", sort="store"):
    """Return list of missing opening/closing reports for supervised stores."""
    _check_dashboard_access()
    _period, start_date, end_date = _period_window(period)
    store_names = _get_store_scope()

    if not store_names:
        return {"pending": []}

    try:
        opening_rows = frappe.get_all(
            "BEI Store Opening Report",
            filters={"store": ["in", store_names], "report_date": ["between", [start_date, end_date]]},
            fields=["store", "report_date"],
        )
    except Exception:
        opening_rows = []

    try:
        closing_rows = frappe.get_all(
            "BEI Store Closing Report",
            filters={"store": ["in", store_names], "report_date": ["between", [start_date, end_date]]},
            fields=["store", "report_date"],
        )
    except Exception:
        closing_rows = []

    opening_submitted = {(row.store, str(row.report_date)) for row in opening_rows}
    closing_submitted = {(row.store, str(row.report_date)) for row in closing_rows}

    pending = []
    for report_date in _iter_dates(start_date, end_date):
        day = str(report_date)
        for store in store_names:
            if (store, day) not in opening_submitted:
                pending.append(
                    {
                        "store": store,
                        "report_type": "Opening",
                        "expected_by": f"{day} 09:00",
                        "status": "Missing",
                    }
                )
            if (store, day) not in closing_submitted:
                pending.append(
                    {
                        "store": store,
                        "report_type": "Closing",
                        "expected_by": f"{day} 23:59",
                        "status": "Missing",
                    }
                )

    if status:
        pending = [item for item in pending if item.get("status") == status]

    if sort == "expected_by":
        pending.sort(key=lambda item: (item.get("expected_by", ""), item.get("store", ""), item.get("report_type", "")))
    elif sort == "report_type":
        pending.sort(key=lambda item: (item.get("report_type", ""), item.get("store", ""), item.get("expected_by", "")))
    else:
        pending.sort(key=lambda item: (item.get("store", ""), item.get("report_type", ""), item.get("expected_by", "")))

    return {"pending": pending}
