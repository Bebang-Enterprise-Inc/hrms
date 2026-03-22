"""S043: Daily missing punch report.

Queries Frappe Attendance + Employee Checkin to find employees who:
1. Had a Shift Assignment but no Attendance record (absent/no punch)
2. Had an Attendance record but are missing a punch-out (Employee Checkin with IN but no OUT)

Sends report to:
- Store supervisor via Google Chat (per-store notification space)
- Area Supervisor via Google Chat
- hr@bebang.ph via email

Scheduled at 00:00 PHT (16:00 UTC) via hooks.py — runs after all retail
shifts end (latest S-2P at 23:00) and after auto-attendance has processed.
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, nowdate, get_datetime, getdate, format_date


def run_daily_missing_punch_report():
    """Entry point called by scheduler. Reports on yesterday's shifts."""
    report_date = add_days(today(), -1)

    # Skip company holidays
    if _is_company_holiday(report_date):
        frappe.logger().info(
            f"S043 Missing Punch Report: Skipping {report_date} — company holiday"
        )
        return

    missing = _get_missing_punches(report_date)
    absent = _get_absent_employees(report_date)

    if not missing and not absent:
        frappe.logger().info(
            f"S043 Missing Punch Report: No issues for {report_date}"
        )
        return

    # Group by store for per-store notifications
    by_store = {}
    for record in missing + absent:
        store = record.get("store", "Unknown")
        by_store.setdefault(store, []).append(record)

    # Send per-store Chat notifications
    for store, records in by_store.items():
        _send_store_chat_notification(store, records, report_date)

    # Send summary email to HR
    _send_hr_email_summary(by_store, report_date)

    frappe.logger().info(
        f"S043 Missing Punch Report: {len(missing)} missing punches, "
        f"{len(absent)} absents across {len(by_store)} stores for {report_date}"
    )


def _is_company_holiday(date_str):
    """Check if date is a company holiday for BEI."""
    return frappe.db.exists(
        "Holiday",
        {
            "holiday_date": date_str,
            "parent": ["like", "%Bebang%"],
        },
    )


def _get_missing_punches(report_date):
    """Employees with Shift Assignment + punch-in but no punch-out."""
    results = frappe.db.sql(
        """
        SELECT
            sa.employee,
            sa.employee_name,
            sa.shift_type,
            e.custom_store AS store,
            MAX(CASE WHEN ec.log_type = 'IN' THEN ec.time END) AS last_in,
            MAX(CASE WHEN ec.log_type = 'OUT' THEN ec.time END) AS last_out
        FROM `tabShift Assignment` sa
        JOIN `tabEmployee` e ON e.name = sa.employee
        LEFT JOIN `tabEmployee Checkin` ec
            ON ec.employee = sa.employee
            AND DATE(ec.time) = %(report_date)s
        WHERE sa.start_date = %(report_date)s
            AND sa.status = 'Active'
            AND sa.docstatus = 1
        GROUP BY sa.employee, sa.employee_name, sa.shift_type, e.custom_store
        HAVING last_in IS NOT NULL AND last_out IS NULL
        """,
        {"report_date": report_date},
        as_dict=True,
    )

    for r in results:
        r["issue_type"] = "Missing OUT Punch"
        r["report_date"] = report_date

    return results


def _get_absent_employees(report_date):
    """Employees with Shift Assignment but no Attendance record at all."""
    results = frappe.db.sql(
        """
        SELECT
            sa.employee,
            sa.employee_name,
            sa.shift_type,
            e.custom_store AS store
        FROM `tabShift Assignment` sa
        JOIN `tabEmployee` e ON e.name = sa.employee
        LEFT JOIN `tabAttendance` att
            ON att.employee = sa.employee
            AND att.attendance_date = %(report_date)s
            AND att.docstatus = 1
        WHERE sa.start_date = %(report_date)s
            AND sa.status = 'Active'
            AND sa.docstatus = 1
            AND att.name IS NULL
        """,
        {"report_date": report_date},
        as_dict=True,
    )

    for r in results:
        r["issue_type"] = "No Attendance Record (Absent/No Punch)"
        r["report_date"] = report_date
        r["last_in"] = None
        r["last_out"] = None

    return results


def _send_store_chat_notification(store, records, report_date):
    """Send missing punch notification to store's Google Chat space."""
    try:
        from hrms.api.google_chat import send_notification

        lines = [f"*Missing Punch Report — {format_date(report_date)}*", f"Store: {store}", ""]
        for r in records:
            punch_info = ""
            if r.get("last_in"):
                punch_info = f" (IN: {get_datetime(r['last_in']).strftime('%I:%M %p')})"
            lines.append(
                f"• {r['employee_name']} — {r['issue_type']}{punch_info} — Shift: {r.get('shift_type', 'N/A')}"
            )

        text = "\n".join(lines)

        # Try store-specific space first, fall back to global ops
        space_name = frappe.db.get_value(
            "Branch", store, "custom_gchat_space"
        )
        if not space_name:
            space_name = frappe.db.get_single_value(
                "BEI Settings", "ops_notification_space"
            ) or None

        if space_name:
            send_notification(space_name=space_name, text=text)
    except Exception:
        frappe.log_error(
            f"S043: Failed to send Chat notification for store {store}",
            "Missing Punch Report",
        )


def _send_hr_email_summary(by_store, report_date):
    """Send summary email to HR."""
    try:
        total_issues = sum(len(records) for records in by_store.values())

        html_parts = [
            f"<h2>Daily Missing Punch Report — {format_date(report_date)}</h2>",
            f"<p><strong>{total_issues} issues</strong> across {len(by_store)} stores</p>",
        ]

        for store, records in sorted(by_store.items()):
            html_parts.append(f"<h3>{store} ({len(records)} issues)</h3>")
            html_parts.append("<table border='1' cellpadding='5' style='border-collapse:collapse'>")
            html_parts.append(
                "<tr><th>Employee</th><th>Issue</th><th>Shift</th><th>Last IN</th></tr>"
            )
            for r in records:
                last_in = ""
                if r.get("last_in"):
                    last_in = get_datetime(r["last_in"]).strftime("%I:%M %p")
                html_parts.append(
                    f"<tr><td>{r['employee_name']}</td><td>{r['issue_type']}</td>"
                    f"<td>{r.get('shift_type', 'N/A')}</td><td>{last_in}</td></tr>"
                )
            html_parts.append("</table>")

        frappe.sendmail(
            recipients=["hr@bebang.ph"],
            subject=f"Missing Punch Report — {format_date(report_date)} ({total_issues} issues)",
            message="".join(html_parts),
            now=True,
        )
    except Exception:
        frappe.log_error(
            "S043: Failed to send HR email for missing punch report",
            "Missing Punch Report",
        )
