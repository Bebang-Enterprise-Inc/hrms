"""BEI Disciplinary Management API endpoints.

Handles the complete IR→NTE→NOD→Appeal disciplinary cycle
per Philippine DOLE requirements.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, add_days, today
from hrms.utils.api_helpers import (
    _get_employee_or_throw,
    _get_employee_details,
    _check_hr_permission,
    _check_manager_permission,
    _paginate,
)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_incident_report(data):
    """File new incident report.

    Args:
        data: JSON string with fields: employee, incident_date, incident_category,
              description, store, recommended_action, witnesses

    Returns:
        Created incident report name

    Access: Supervisor
    """
    import json

    if isinstance(data, str):
        data = json.loads(data)

    # Validate required fields
    required_fields = ["employee", "incident_date", "incident_category", "description"]
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_(f"Missing required field: {field}"))

    # Permission check - must be supervisor of employee or HR
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    if not is_hr:
        _check_manager_permission(data["employee"])

    # Create incident report
    ir = frappe.get_doc({
        "doctype": "BEI Incident Report",
        "employee": data["employee"],
        "reported_by": current_employee,
        "store": data.get("store"),
        "incident_date": getdate(data["incident_date"]),
        "incident_category": data["incident_category"],
        "description": data["description"],
        "recommended_action": data.get("recommended_action"),
        "witnesses": data.get("witnesses"),
        "status": "Submitted",
    })

    ir.insert(ignore_permissions=True)
    frappe.db.commit()

    # Notify HR
    _notify_hr_of_incident(ir)

    return {
        "message": _("Incident report created successfully"),
        "name": ir.name,
    }


def _notify_hr_of_incident(ir):
    """Notify HR team of new incident report."""
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles:
            hr_emails.append(user.email)

    if hr_emails:
        frappe.sendmail(
            recipients=hr_emails,
            subject=_("New Incident Report: {0}").format(ir.employee_name),
            message=_("""
            A new incident report has been filed:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee})<br>
            <strong>Reported By:</strong> {reported_by_name}<br>
            <strong>Category:</strong> {category}<br>
            <strong>Date:</strong> {incident_date}<br>
            <strong>Recommended Action:</strong> {recommended_action}<br><br>
            <strong>Report ID:</strong> {report_id}
            """).format(
                employee_name=ir.employee_name,
                employee=ir.employee,
                reported_by_name=ir.reported_by_name,
                category=ir.incident_category,
                incident_date=frappe.format_date(ir.incident_date),
                recommended_action=ir.recommended_action or "Not specified",
                report_id=ir.name,
            ),
            reference_doctype="BEI Incident Report",
            reference_name=ir.name,
        )


@frappe.whitelist()
def get_incident_reports(status=None, employee=None, page=1):
    """List incident reports.

    Args:
        status: Filter by status (optional)
        employee: Filter by employee (optional)
        page: Page number

    Returns:
        Paginated list of incident reports

    Access: Supervisor (own team), HR (all)
    """
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    page = int(page) if page else 1

    # Build filters
    filters = {}
    if status:
        filters["status"] = status
    if employee:
        filters["employee"] = employee

    # If not HR, only show reports for own team
    if not is_hr:
        team_members = frappe.get_all(
            "Employee",
            filters={"reports_to": current_employee, "status": "Active"},
            pluck="name",
        )
        filters["employee"] = ["in", team_members]

    # Get incident reports
    reports = frappe.get_all(
        "BEI Incident Report",
        filters=filters,
        fields=[
            "name",
            "employee",
            "employee_name",
            "reported_by_name",
            "incident_date",
            "incident_category",
            "status",
            "recommended_action",
            "creation",
        ],
        order_by="incident_date desc",
    )

    return _paginate(reports, page=page, page_size=20)


@frappe.whitelist()
def get_incident_detail(ir_name):
    """Get full incident report details including linked NTE/NOD.

    Args:
        ir_name: Incident report name

    Returns:
        Full incident report with linked documents

    Access: Supervisor, HR
    """
    if not frappe.db.exists("BEI Incident Report", ir_name):
        frappe.throw(_("Incident report not found"), frappe.DoesNotExistError)

    ir = frappe.get_doc("BEI Incident Report", ir_name)

    # Permission check
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    if not is_hr:
        _check_manager_permission(ir.employee)

    # Get linked documents
    linked_nte = None
    if ir.linked_nte:
        linked_nte = frappe.db.get_value(
            "BEI Notice to Explain",
            ir.linked_nte,
            ["name", "status", "issue_date", "response_deadline"],
            as_dict=True,
        )

    linked_nod = None
    if linked_nte:
        linked_nod = frappe.db.get_value(
            "BEI Notice of Decision",
            {"notice_to_explain": ir.linked_nte},
            ["name", "status", "decision_date", "penalty"],
            as_dict=True,
        )

    return {
        "name": ir.name,
        "employee": ir.employee,
        "employee_name": ir.employee_name,
        "reported_by": ir.reported_by,
        "reported_by_name": ir.reported_by_name,
        "store": ir.store,
        "incident_date": ir.incident_date,
        "incident_category": ir.incident_category,
        "description": ir.description,
        "recommended_action": ir.recommended_action,
        "witnesses": ir.witnesses,
        "evidence_photos": ir.evidence_photos,
        "evidence_documents": ir.evidence_documents,
        "hr_notes": ir.hr_notes,
        "status": ir.status,
        "linked_nte": linked_nte,
        "linked_nod": linked_nod,
        "creation": ir.creation,
        "modified": ir.modified,
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_nte(ir_name, charges, response_deadline=None):
    """Issue Notice to Explain from incident report.

    Args:
        ir_name: Incident report name
        charges: Text of charges (HTML)
        response_deadline: Date by which employee must respond (default: +5 days)

    Returns:
        Created NTE name

    Access: HR only
    """
    _check_hr_permission()

    if not frappe.db.exists("BEI Incident Report", ir_name):
        frappe.throw(_("Incident report not found"), frappe.DoesNotExistError)

    ir = frappe.get_doc("BEI Incident Report", ir_name)

    # Validate charges
    if not charges:
        frappe.throw(_("Charges text is required"))

    # Calculate response deadline (DOLE standard: 5 days)
    if not response_deadline:
        response_deadline = add_days(today(), 5)
    else:
        response_deadline = getdate(response_deadline)

    current_employee = _get_employee_or_throw()

    # Create NTE
    nte = frappe.get_doc({
        "doctype": "BEI Notice to Explain",
        "employee": ir.employee,
        "issued_by": current_employee,
        "incident_report": ir_name,
        "issue_date": getdate(today()),
        "response_deadline": response_deadline,
        "charges": charges,
        "status": "Issued",
    })

    nte.insert(ignore_permissions=True)
    frappe.db.commit()

    # Update IR status
    ir.db_set("status", "NTE Issued")
    ir.db_set("linked_nte", nte.name)

    # Notify employee
    _notify_employee_of_nte(nte, ir)

    return {
        "message": _("Notice to Explain issued successfully"),
        "name": nte.name,
    }


def _notify_employee_of_nte(nte, ir):
    """Notify employee of NTE issuance."""
    employee_email = frappe.db.get_value("Employee", nte.employee, "user_id")
    if not employee_email:
        return

    frappe.sendmail(
        recipients=[employee_email],
        subject=_("Notice to Explain - Action Required"),
        message=_("""
        Dear {employee_name},<br><br>
        You have received a Notice to Explain regarding an incident on {incident_date}.<br><br>
        <strong>Category:</strong> {category}<br>
        <strong>Response Deadline:</strong> {deadline}<br><br>
        <strong>Charges:</strong><br>
        {charges}<br><br>
        You are required to submit your written explanation by {deadline}.
        Please respond via my.bebang.ph.
        """).format(
            employee_name=nte.employee_name,
            incident_date=frappe.format_date(ir.incident_date),
            category=ir.incident_category,
            deadline=frappe.format_date(nte.response_deadline),
            charges=nte.charges,
        ),
        reference_doctype="BEI Notice to Explain",
        reference_name=nte.name,
    )


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def submit_nte_response(nte_name, response, attachments=None):
    """Employee submits response to NTE.

    Args:
        nte_name: NTE document name
        response: Employee's written explanation (HTML)
        attachments: File attachments (optional)

    Returns:
        Success message

    Access: Employee (own NTE only)
    """
    if not frappe.db.exists("BEI Notice to Explain", nte_name):
        frappe.throw(_("Notice to Explain not found"), frappe.DoesNotExistError)

    nte = frappe.get_doc("BEI Notice to Explain", nte_name)

    # Permission check - must be the employee
    current_employee = _get_employee_or_throw()
    if nte.employee != current_employee:
        frappe.throw(_("Permission denied. This is not your NTE."), frappe.PermissionError)

    # Validate response
    if not response:
        frappe.throw(_("Response text is required"))

    # Update NTE
    nte.employee_response = response
    nte.response_date = getdate(today())
    nte.status = "Response Received"
    nte.save(ignore_permissions=True)
    frappe.db.commit()

    # Notify HR
    _notify_hr_of_nte_response(nte)

    return {
        "message": _("Response submitted successfully"),
    }


def _notify_hr_of_nte_response(nte):
    """Notify HR of NTE response."""
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles:
            hr_emails.append(user.email)

    if hr_emails:
        frappe.sendmail(
            recipients=hr_emails,
            subject=_("NTE Response Received: {0}").format(nte.employee_name),
            message=_("""
            Employee has submitted response to Notice to Explain:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee})<br>
            <strong>NTE:</strong> {nte_name}<br>
            <strong>Response Date:</strong> {response_date}<br><br>
            Please review and determine next steps.
            """).format(
                employee_name=nte.employee_name,
                employee=nte.employee,
                nte_name=nte.name,
                response_date=frappe.format_date(nte.response_date),
            ),
            reference_doctype="BEI Notice to Explain",
            reference_name=nte.name,
        )


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_nod(nte_name, penalty, findings, rationale, suspension_days=None):
    """Issue Notice of Decision.

    Args:
        nte_name: NTE document name
        penalty: Penalty type (Verbal Warning/Written Warning/etc.)
        findings: Findings text (HTML)
        rationale: Decision rationale (HTML)
        suspension_days: Number of days (if penalty is Suspension)

    Returns:
        Created NOD name

    Access: HR only
    """
    _check_hr_permission()

    if not frappe.db.exists("BEI Notice to Explain", nte_name):
        frappe.throw(_("Notice to Explain not found"), frappe.DoesNotExistError)

    nte = frappe.get_doc("BEI Notice to Explain", nte_name)

    # Validate required fields
    if not penalty or not findings or not rationale:
        frappe.throw(_("Penalty, findings, and rationale are required"))

    if penalty == "Suspension" and not suspension_days:
        frappe.throw(_("Suspension days required for suspension penalty"))

    current_employee = _get_employee_or_throw()

    # Create NOD
    nod = frappe.get_doc({
        "doctype": "BEI Notice of Decision",
        "employee": nte.employee,
        "decided_by": current_employee,
        "notice_to_explain": nte_name,
        "decision_date": getdate(today()),
        "penalty": penalty,
        "suspension_days": suspension_days,
        "findings": findings,
        "decision_rationale": rationale,
        "status": "Issued",
    })

    nod.insert(ignore_permissions=True)
    frappe.db.commit()

    # Update NTE status
    nte.db_set("status", "Decision Made")
    nte.db_set("linked_nod", nod.name)

    # Notify employee
    _notify_employee_of_nod(nod, nte)

    return {
        "message": _("Notice of Decision issued successfully"),
        "name": nod.name,
    }


def _notify_employee_of_nod(nod, nte):
    """Notify employee of NOD."""
    employee_email = frappe.db.get_value("Employee", nod.employee, "user_id")
    if not employee_email:
        return

    frappe.sendmail(
        recipients=[employee_email],
        subject=_("Notice of Decision - {0}").format(nod.penalty),
        message=_("""
        Dear {employee_name},<br><br>
        A decision has been made regarding your Notice to Explain.<br><br>
        <strong>Decision Date:</strong> {decision_date}<br>
        <strong>Penalty:</strong> {penalty}<br>
        {suspension_info}
        <br>
        <strong>Findings:</strong><br>
        {findings}<br><br>
        <strong>Rationale:</strong><br>
        {rationale}<br><br>
        You have the right to appeal this decision within 5 days via my.bebang.ph.
        """).format(
            employee_name=nod.employee_name,
            decision_date=frappe.format_date(nod.decision_date),
            penalty=nod.penalty,
            suspension_info=(f"<strong>Suspension Days:</strong> {nod.suspension_days}<br>"
                           if nod.penalty == "Suspension" else ""),
            findings=nod.findings,
            rationale=nod.decision_rationale,
        ),
        reference_doctype="BEI Notice of Decision",
        reference_name=nod.name,
    )


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def create_appeal(nod_name, grounds, evidence=None):
    """Create appeal for NOD.

    Args:
        nod_name: NOD document name
        grounds: Appeal grounds (HTML)
        evidence: File attachment (optional)

    Returns:
        Created appeal name

    Access: Employee (own NOD only)
    """
    if not frappe.db.exists("BEI Notice of Decision", nod_name):
        frappe.throw(_("Notice of Decision not found"), frappe.DoesNotExistError)

    nod = frappe.get_doc("BEI Notice of Decision", nod_name)

    # Permission check - must be the employee
    current_employee = _get_employee_or_throw()
    if nod.employee != current_employee:
        frappe.throw(_("Permission denied. This is not your NOD."), frappe.PermissionError)

    # Validate grounds
    if not grounds:
        frappe.throw(_("Appeal grounds are required"))

    # Create appeal
    appeal = frappe.get_doc({
        "doctype": "BEI Employee Appeal",
        "employee": nod.employee,
        "notice_of_decision": nod_name,
        "appeal_date": getdate(today()),
        "appeal_grounds": grounds,
        "appeal_evidence": evidence,
        "status": "Submitted",
    })

    appeal.insert(ignore_permissions=True)
    frappe.db.commit()

    # Update NOD status
    nod.db_set("status", "Appealed")

    # Notify HR
    _notify_hr_of_appeal(appeal, nod)

    return {
        "message": _("Appeal submitted successfully"),
        "name": appeal.name,
    }


def _notify_hr_of_appeal(appeal, nod):
    """Notify HR of employee appeal."""
    hr_users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["email"],
    )

    hr_emails = []
    for user in hr_users:
        roles = frappe.get_roles(user.email)
        if "HR Manager" in roles:
            hr_emails.append(user.email)

    if hr_emails:
        frappe.sendmail(
            recipients=hr_emails,
            subject=_("Appeal Filed: {0}").format(appeal.employee_name),
            message=_("""
            An employee has filed an appeal:<br><br>
            <strong>Employee:</strong> {employee_name} ({employee})<br>
            <strong>Original Penalty:</strong> {penalty}<br>
            <strong>Appeal Date:</strong> {appeal_date}<br>
            <strong>Appeal ID:</strong> {appeal_id}<br><br>
            Please review and schedule appeal hearing.
            """).format(
                employee_name=appeal.employee_name,
                employee=appeal.employee,
                penalty=nod.penalty,
                appeal_date=frappe.format_date(appeal.appeal_date),
                appeal_id=appeal.name,
            ),
            reference_doctype="BEI Employee Appeal",
            reference_name=appeal.name,
        )


@frappe.whitelist()
def get_disciplinary_history(employee, page=1):
    """Get full disciplinary record for employee.

    Args:
        employee: Employee ID
        page: Page number

    Returns:
        Paginated disciplinary history

    Access: HR, Supervisor (own team)
    """
    current_employee = _get_employee_or_throw()
    roles = frappe.get_roles(frappe.session.user)
    is_hr = any(r in roles for r in ["HR Manager", "HR User", "System Manager"])

    if not is_hr:
        _check_manager_permission(employee)

    page = int(page) if page else 1

    # Get all incident reports
    incidents = frappe.get_all(
        "BEI Incident Report",
        filters={"employee": employee},
        fields=[
            "name",
            "incident_date",
            "incident_category",
            "status",
            "recommended_action",
            "linked_nte",
        ],
        order_by="incident_date desc",
    )

    # Enrich with NTE and NOD data
    history = []
    for ir in incidents:
        record = {
            "incident_report": ir.name,
            "incident_date": ir.incident_date,
            "category": ir.incident_category,
            "status": ir.status,
            "nte": None,
            "nod": None,
            "appeal": None,
        }

        if ir.linked_nte:
            nte = frappe.db.get_value(
                "BEI Notice to Explain",
                ir.linked_nte,
                ["name", "status", "issue_date", "response_date", "linked_nod"],
                as_dict=True,
            )
            if nte:
                record["nte"] = {
                    "name": nte.name,
                    "status": nte.status,
                    "issue_date": nte.issue_date,
                    "response_date": nte.response_date,
                }

                if nte.linked_nod:
                    nod = frappe.db.get_value(
                        "BEI Notice of Decision",
                        nte.linked_nod,
                        ["name", "status", "penalty", "decision_date"],
                        as_dict=True,
                    )
                    if nod:
                        record["nod"] = {
                            "name": nod.name,
                            "status": nod.status,
                            "penalty": nod.penalty,
                            "decision_date": nod.decision_date,
                        }

                        # Check for appeal
                        appeal = frappe.db.get_value(
                            "BEI Employee Appeal",
                            {"notice_of_decision": nte.linked_nod},
                            ["name", "status", "review_decision"],
                            as_dict=True,
                        )
                        if appeal:
                            record["appeal"] = {
                                "name": appeal.name,
                                "status": appeal.status,
                                "review_decision": appeal.review_decision,
                            }

        history.append(record)

    return _paginate(history, page=page, page_size=20)


@frappe.whitelist()
def get_disciplinary_dashboard():
    """Get disciplinary dashboard statistics.

    Returns:
        Dashboard stats: IRs, NTEs, NODs, Appeals by status

    Access: HR only
    """
    _check_hr_permission()

    stats = {
        "incident_reports": {
            "draft": frappe.db.count("BEI Incident Report", {"status": "Draft"}),
            "submitted": frappe.db.count("BEI Incident Report", {"status": "Submitted"}),
            "under_review": frappe.db.count("BEI Incident Report", {"status": "Under Review"}),
            "nte_issued": frappe.db.count("BEI Incident Report", {"status": "NTE Issued"}),
        },
        "ntes": {
            "issued": frappe.db.count("BEI Notice to Explain", {"status": "Issued"}),
            "response_received": frappe.db.count("BEI Notice to Explain", {"status": "Response Received"}),
            "under_review": frappe.db.count("BEI Notice to Explain", {"status": "Under Review"}),
        },
        "nods": {
            "issued": frappe.db.count("BEI Notice of Decision", {"status": "Issued"}),
            "appealed": frappe.db.count("BEI Notice of Decision", {"status": "Appealed"}),
            "final": frappe.db.count("BEI Notice of Decision", {"status": "Final"}),
        },
        "appeals": {
            "submitted": frappe.db.count("BEI Employee Appeal", {"status": "Submitted"}),
            "under_review": frappe.db.count("BEI Employee Appeal", {"status": "Under Review"}),
            "decision_made": frappe.db.count("BEI Employee Appeal", {"status": "Decision Made"}),
        },
    }

    return stats
