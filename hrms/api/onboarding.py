# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
BEI Onboarding API

Server-side methods used by tasks.bebang.ph to support:
- QR-based self onboarding
- Kiosk onboarding (supervisor device)
- New hire onboarding (no Employee ID yet)

Important:
- These endpoints are intended to be called server-to-server (Next.js -> Frappe)
- Do NOT expose API tokens to the browser
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

import frappe
from frappe.utils import now_datetime
from frappe.utils.data import add_to_date


SESSION_DOCTYPE = "BEI Onboarding Session"
REQUEST_DOCTYPE = "BEI Onboarding Request"


def _new_token() -> str:
    # 24 chars URL-safe token (short enough for QR, long enough for security)
    return secrets.token_urlsafe(18)


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


@frappe.whitelist()
def create_session(
    branch: str,
    mode: str = "self",
    verifier_email: str | None = None,
    expires_in_minutes: int = 30,
) -> Dict[str, Any]:
    """
    Create an onboarding session.

    Intended to be called by an authenticated supervisor/manager flow.
    """
    if not branch:
        return {"success": False, "error": "Branch is required", "code": "MISSING_BRANCH"}

    mode = (mode or "self").strip().lower()
    if mode not in ("self", "kiosk", "new_hire"):
        return {"success": False, "error": "Invalid mode", "code": "INVALID_MODE"}

    token = _new_token()
    expires_at = add_to_date(now_datetime(), minutes=int(expires_in_minutes))

    doc = frappe.get_doc(
        {
            "doctype": SESSION_DOCTYPE,
            "token": token,
            "branch": branch,
            "mode": mode,
            "verifier_email": verifier_email or "",
            "created_by_user": frappe.session.user,
            "expires_at": expires_at,
            "status": "Active",
        }
    )

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "data": {
                "token": token,
                "expires_at": str(expires_at),
                "branch": branch,
                "mode": mode,
            },
        }
    except Exception as e:
        frappe.log_error(title="BEI Onboarding create_session failed", message=str(e))
        return {"success": False, "error": "Failed to create session", "code": "CREATE_FAILED"}


@frappe.whitelist()
def get_session(token: str) -> Dict[str, Any]:
    """Return minimal session metadata (no PII)."""
    if not token:
        return {"success": False, "error": "Token is required", "code": "MISSING_TOKEN"}

    name = frappe.db.get_value(SESSION_DOCTYPE, {"token": token}, "name")
    if not name:
        return {"success": False, "error": "Session not found", "code": "NOT_FOUND"}

    doc = frappe.get_doc(SESSION_DOCTYPE, name)
    if doc.status != "Active":
        return {"success": False, "error": "Session not active", "code": "NOT_ACTIVE"}

    if doc.expires_at and now_datetime() > doc.expires_at:
        # best-effort mark expired
        try:
            frappe.db.set_value(SESSION_DOCTYPE, name, "status", "Expired")
            frappe.db.commit()
        except Exception:
            pass
        return {"success": False, "error": "Session expired", "code": "EXPIRED"}

    return {
        "success": True,
        "data": {
            "token": token,
            "branch": doc.branch,
            "mode": doc.mode,
            "expires_at": str(doc.expires_at) if doc.expires_at else None,
            "verifier_email": doc.verifier_email or "",
        },
    }


@frappe.whitelist()
def lookup_employee(token: str, biometric_id: str | None = None, employee: str | None = None) -> Dict[str, Any]:
    """
    Lookup employee within a session context.
    Returns minimal confirmation fields only (no sensitive data).
    """
    session = get_session(token)
    if not session.get("success"):
        return session

    if not biometric_id and not employee:
        return {"success": False, "error": "Employee identifier required", "code": "MISSING_IDENTIFIER"}

    filters = {}
    if employee:
        filters["name"] = employee
    if biometric_id:
        filters["biometric_id"] = biometric_id

    # NOTE: Request all fields needed for prefilling the onboarding form
    fields = [
        "name",
        "employee_name",
        "first_name",
        "middle_name",
        "last_name",
        "gender",
        "date_of_birth",
        "branch",
        "department",
        "designation",
        "reports_to",
        "cell_number",
        "personal_email",
        "current_address",
        "permanent_address",
        "person_to_be_contacted",  # Emergency contact name
        "emergency_phone_number",   # Emergency phone
        "relation",                 # Emergency relationship
        "sss_number",               # Custom field
        "philhealth_number",        # Custom field
        "pagibig_number",           # Custom field
        "tin_number",               # Custom field
        "bank_name",                # If exists
        "bank_ac_no",               # Bank account number
        "image",                    # Profile photo
    ]
    rows = frappe.get_all("Employee", filters=filters, fields=fields, limit=2)

    if not rows:
        return {"success": False, "error": "Employee not found", "code": "EMP_NOT_FOUND"}
    if len(rows) > 1:
        return {"success": False, "error": "Multiple matches found", "code": "MULTIPLE_MATCHES"}

    row = rows[0]

    # Branch scoping: by default, only allow onboarding employees for session branch
    sess_branch = session["data"].get("branch")
    if sess_branch and row.get("branch") and row["branch"] != sess_branch:
        return {"success": False, "error": "Employee not in this branch", "code": "BRANCH_MISMATCH"}

    return {
        "success": True,
        "data": {
            "name": row.get("name"),
            "employee_name": row.get("employee_name"),
            "first_name": row.get("first_name"),
            "middle_name": row.get("middle_name"),
            "last_name": row.get("last_name"),
            "gender": row.get("gender"),
            "date_of_birth": row.get("date_of_birth"),
            "branch": row.get("branch"),
            "department": row.get("department"),
            "designation": row.get("designation"),
            "reports_to": row.get("reports_to"),
            "cell_number": row.get("cell_number"),
            "personal_email": row.get("personal_email"),
            "current_address": row.get("current_address"),
            "permanent_address": row.get("permanent_address"),
            "emergency_contact_name": row.get("person_to_be_contacted"),
            "emergency_phone": row.get("emergency_phone_number"),
            "emergency_relationship": row.get("relation"),
            "sss_number": row.get("sss_number"),
            "philhealth_number": row.get("philhealth_number"),
            "pagibig_number": row.get("pagibig_number"),
            "tin_number": row.get("tin_number"),
            "bank_name": row.get("bank_name"),
            "bank_ac_no": row.get("bank_ac_no"),
            "image": row.get("image"),
            "biometric_id": row.get("biometric_id"),
        },
    }


@frappe.whitelist()
def submit_request(
    token: str,
    employee: str | None = None,
    request_type: str = "update_existing",
    requested_changes: str | None = None,
    submitted_by_meta: str | None = None,
    selfie_file_url: str | None = None,
    verifier_email: str | None = None,
) -> Dict[str, Any]:
    """
    Create an onboarding request.

    - For updates, pass `employee`
    - For new hires, pass request_type='new_hire' and leave employee empty
    """
    session = get_session(token)
    if not session.get("success"):
        return session

    request_type = (request_type or "update_existing").strip().lower()
    if request_type not in ("update_existing", "new_hire"):
        return {"success": False, "error": "Invalid request_type", "code": "INVALID_REQUEST_TYPE"}

    if request_type == "update_existing" and not employee:
        return {"success": False, "error": "Employee is required", "code": "MISSING_EMPLOYEE"}

    changes = _as_dict(requested_changes)
    meta = _as_dict(submitted_by_meta)

    doc = frappe.get_doc(
        {
            "doctype": REQUEST_DOCTYPE,
            "session_token": token,
            "employee": employee or "",
            "request_type": request_type,
            "status": "Pending",
            "submitted_at": now_datetime(),
            "submitted_via": meta.get("submitted_via") or "",
            "submitted_by_meta": json.dumps(meta, ensure_ascii=False),
            "requested_changes": json.dumps(changes, ensure_ascii=False),
            "selfie_file_url": selfie_file_url or "",
            "approver_email": verifier_email or "",
        }
    )

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"request": doc.name, "status": doc.status}}
    except Exception as e:
        frappe.log_error(title="BEI Onboarding submit_request failed", message=str(e))
        return {"success": False, "error": "Failed to submit request", "code": "SUBMIT_FAILED"}


@frappe.whitelist()
def approve_and_apply(
    request_name: str,
    approver_email: str,
    decision: str = "approve",
    approver_notes: str | None = None,
) -> Dict[str, Any]:
    """
    Approve (or reject) and optionally apply an onboarding request.

    Notes:
    - Access control is enforced in tasks.bebang.ph (verifier routing + auth)
    - This method applies changes using the current session user (typically integration user)
    """
    if not request_name:
        return {"success": False, "error": "Request is required", "code": "MISSING_REQUEST"}

    decision = (decision or "approve").strip().lower()
    if decision not in ("approve", "reject", "escalate"):
        return {"success": False, "error": "Invalid decision", "code": "INVALID_DECISION"}

    if not frappe.db.exists(REQUEST_DOCTYPE, request_name):
        return {"success": False, "error": "Request not found", "code": "NOT_FOUND"}

    req = frappe.get_doc(REQUEST_DOCTYPE, request_name)

    if req.status not in ("Pending", "Escalated"):
        return {"success": False, "error": "Request not pending", "code": "NOT_PENDING"}

    req.approver_email = approver_email or ""
    req.approver_notes = approver_notes or ""
    req.approved_at = now_datetime()

    if decision == "reject":
        req.status = "Rejected"
        req.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"status": req.status}}

    if decision == "escalate":
        req.status = "Escalated"
        req.escalated_to_hr = 1
        req.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"status": req.status}}

    # approve
    req.status = "Approved"
    req.save(ignore_permissions=True)

    # Apply changes (only for update_existing)
    if req.request_type == "update_existing" and req.employee:
        try:
            changes = _as_dict(req.requested_changes)
            emp = frappe.get_doc("Employee", req.employee)

            # Apply ONLY whitelisted-safe fields. Keep restricted fields for HR-only flow.
            # These fieldnames are common in ERPNext; if your instance differs, update mapping.
            safe_map = {
                "personal_email": "personal_email",
                "cell_number": "cell_number",
                "current_address": "current_address",
                "emergency_contact_person": "emergency_contact_person",
                "emergency_contact_number": "emergency_phone_number",
                "selfie_file_url": None,  # stored on request; Employee photo handled separately
            }

            for input_key, emp_field in safe_map.items():
                if emp_field and input_key in changes and changes[input_key] is not None:
                    setattr(emp, emp_field, changes[input_key])

            emp.save(ignore_permissions=True)
            req.status = "Applied"
            req.applied_at = now_datetime()
            req.applied_by = frappe.session.user
            req.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(title="BEI Onboarding apply failed", message=str(e))
            return {"success": False, "error": "Approved but failed to apply changes", "code": "APPLY_FAILED"}

    frappe.db.commit()
    return {"success": True, "data": {"status": req.status}}





"""
BEI Onboarding API

Server-side methods used by tasks.bebang.ph to support:
- QR-based self onboarding
- Kiosk onboarding (supervisor device)
- New hire onboarding (no Employee ID yet)

Important:
- These endpoints are intended to be called server-to-server (Next.js -> Frappe)
- Do NOT expose API tokens to the browser
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

import frappe
from frappe.utils import now_datetime
from frappe.utils.data import add_to_date


SESSION_DOCTYPE = "BEI Onboarding Session"
REQUEST_DOCTYPE = "BEI Onboarding Request"


def _new_token() -> str:
    # 24 chars URL-safe token (short enough for QR, long enough for security)
    return secrets.token_urlsafe(18)


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


@frappe.whitelist()
def create_session(
    branch: str,
    mode: str = "self",
    verifier_email: str | None = None,
    expires_in_minutes: int = 30,
) -> Dict[str, Any]:
    """
    Create an onboarding session.

    Intended to be called by an authenticated supervisor/manager flow.
    """
    if not branch:
        return {"success": False, "error": "Branch is required", "code": "MISSING_BRANCH"}

    mode = (mode or "self").strip().lower()
    if mode not in ("self", "kiosk", "new_hire"):
        return {"success": False, "error": "Invalid mode", "code": "INVALID_MODE"}

    token = _new_token()
    expires_at = add_to_date(now_datetime(), minutes=int(expires_in_minutes))

    doc = frappe.get_doc(
        {
            "doctype": SESSION_DOCTYPE,
            "token": token,
            "branch": branch,
            "mode": mode,
            "verifier_email": verifier_email or "",
            "created_by_user": frappe.session.user,
            "expires_at": expires_at,
            "status": "Active",
        }
    )

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "data": {
                "token": token,
                "expires_at": str(expires_at),
                "branch": branch,
                "mode": mode,
            },
        }
    except Exception as e:
        frappe.log_error(title="BEI Onboarding create_session failed", message=str(e))
        return {"success": False, "error": "Failed to create session", "code": "CREATE_FAILED"}


@frappe.whitelist()
def get_session(token: str) -> Dict[str, Any]:
    """Return minimal session metadata (no PII)."""
    if not token:
        return {"success": False, "error": "Token is required", "code": "MISSING_TOKEN"}

    name = frappe.db.get_value(SESSION_DOCTYPE, {"token": token}, "name")
    if not name:
        return {"success": False, "error": "Session not found", "code": "NOT_FOUND"}

    doc = frappe.get_doc(SESSION_DOCTYPE, name)
    if doc.status != "Active":
        return {"success": False, "error": "Session not active", "code": "NOT_ACTIVE"}

    if doc.expires_at and now_datetime() > doc.expires_at:
        # best-effort mark expired
        try:
            frappe.db.set_value(SESSION_DOCTYPE, name, "status", "Expired")
            frappe.db.commit()
        except Exception:
            pass
        return {"success": False, "error": "Session expired", "code": "EXPIRED"}

    return {
        "success": True,
        "data": {
            "token": token,
            "branch": doc.branch,
            "mode": doc.mode,
            "expires_at": str(doc.expires_at) if doc.expires_at else None,
            "verifier_email": doc.verifier_email or "",
        },
    }


@frappe.whitelist()
def lookup_employee(token: str, biometric_id: str | None = None, employee: str | None = None) -> Dict[str, Any]:
    """
    Lookup employee within a session context.
    Returns minimal confirmation fields only (no sensitive data).
    """
    session = get_session(token)
    if not session.get("success"):
        return session

    if not biometric_id and not employee:
        return {"success": False, "error": "Employee identifier required", "code": "MISSING_IDENTIFIER"}

    filters = {}
    if employee:
        filters["name"] = employee
    if biometric_id:
        filters["biometric_id"] = biometric_id

    # NOTE: Request all fields needed for prefilling the onboarding form
    fields = [
        "name",
        "employee_name",
        "first_name",
        "middle_name",
        "last_name",
        "gender",
        "date_of_birth",
        "branch",
        "department",
        "designation",
        "reports_to",
        "cell_number",
        "personal_email",
        "current_address",
        "permanent_address",
        "person_to_be_contacted",  # Emergency contact name
        "emergency_phone_number",   # Emergency phone
        "relation",                 # Emergency relationship
        "sss_number",               # Custom field
        "philhealth_number",        # Custom field
        "pagibig_number",           # Custom field
        "tin_number",               # Custom field
        "bank_name",                # If exists
        "bank_ac_no",               # Bank account number
        "image",                    # Profile photo
    ]
    rows = frappe.get_all("Employee", filters=filters, fields=fields, limit=2)

    if not rows:
        return {"success": False, "error": "Employee not found", "code": "EMP_NOT_FOUND"}
    if len(rows) > 1:
        return {"success": False, "error": "Multiple matches found", "code": "MULTIPLE_MATCHES"}

    row = rows[0]

    # Branch scoping: by default, only allow onboarding employees for session branch
    sess_branch = session["data"].get("branch")
    if sess_branch and row.get("branch") and row["branch"] != sess_branch:
        return {"success": False, "error": "Employee not in this branch", "code": "BRANCH_MISMATCH"}

    return {
        "success": True,
        "data": {
            "name": row.get("name"),
            "employee_name": row.get("employee_name"),
            "first_name": row.get("first_name"),
            "middle_name": row.get("middle_name"),
            "last_name": row.get("last_name"),
            "gender": row.get("gender"),
            "date_of_birth": row.get("date_of_birth"),
            "branch": row.get("branch"),
            "department": row.get("department"),
            "designation": row.get("designation"),
            "reports_to": row.get("reports_to"),
            "cell_number": row.get("cell_number"),
            "personal_email": row.get("personal_email"),
            "current_address": row.get("current_address"),
            "permanent_address": row.get("permanent_address"),
            "emergency_contact_name": row.get("person_to_be_contacted"),
            "emergency_phone": row.get("emergency_phone_number"),
            "emergency_relationship": row.get("relation"),
            "sss_number": row.get("sss_number"),
            "philhealth_number": row.get("philhealth_number"),
            "pagibig_number": row.get("pagibig_number"),
            "tin_number": row.get("tin_number"),
            "bank_name": row.get("bank_name"),
            "bank_ac_no": row.get("bank_ac_no"),
            "image": row.get("image"),
            "biometric_id": row.get("biometric_id"),
        },
    }


@frappe.whitelist()
def submit_request(
    token: str,
    employee: str | None = None,
    request_type: str = "update_existing",
    requested_changes: str | None = None,
    submitted_by_meta: str | None = None,
    selfie_file_url: str | None = None,
    verifier_email: str | None = None,
) -> Dict[str, Any]:
    """
    Create an onboarding request.

    - For updates, pass `employee`
    - For new hires, pass request_type='new_hire' and leave employee empty
    """
    session = get_session(token)
    if not session.get("success"):
        return session

    request_type = (request_type or "update_existing").strip().lower()
    if request_type not in ("update_existing", "new_hire"):
        return {"success": False, "error": "Invalid request_type", "code": "INVALID_REQUEST_TYPE"}

    if request_type == "update_existing" and not employee:
        return {"success": False, "error": "Employee is required", "code": "MISSING_EMPLOYEE"}

    changes = _as_dict(requested_changes)
    meta = _as_dict(submitted_by_meta)

    doc = frappe.get_doc(
        {
            "doctype": REQUEST_DOCTYPE,
            "session_token": token,
            "employee": employee or "",
            "request_type": request_type,
            "status": "Pending",
            "submitted_at": now_datetime(),
            "submitted_via": meta.get("submitted_via") or "",
            "submitted_by_meta": json.dumps(meta, ensure_ascii=False),
            "requested_changes": json.dumps(changes, ensure_ascii=False),
            "selfie_file_url": selfie_file_url or "",
            "approver_email": verifier_email or "",
        }
    )

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"request": doc.name, "status": doc.status}}
    except Exception as e:
        frappe.log_error(title="BEI Onboarding submit_request failed", message=str(e))
        return {"success": False, "error": "Failed to submit request", "code": "SUBMIT_FAILED"}


@frappe.whitelist()
def approve_and_apply(
    request_name: str,
    approver_email: str,
    decision: str = "approve",
    approver_notes: str | None = None,
) -> Dict[str, Any]:
    """
    Approve (or reject) and optionally apply an onboarding request.

    Notes:
    - Access control is enforced in tasks.bebang.ph (verifier routing + auth)
    - This method applies changes using the current session user (typically integration user)
    """
    if not request_name:
        return {"success": False, "error": "Request is required", "code": "MISSING_REQUEST"}

    decision = (decision or "approve").strip().lower()
    if decision not in ("approve", "reject", "escalate"):
        return {"success": False, "error": "Invalid decision", "code": "INVALID_DECISION"}

    if not frappe.db.exists(REQUEST_DOCTYPE, request_name):
        return {"success": False, "error": "Request not found", "code": "NOT_FOUND"}

    req = frappe.get_doc(REQUEST_DOCTYPE, request_name)

    if req.status not in ("Pending", "Escalated"):
        return {"success": False, "error": "Request not pending", "code": "NOT_PENDING"}

    req.approver_email = approver_email or ""
    req.approver_notes = approver_notes or ""
    req.approved_at = now_datetime()

    if decision == "reject":
        req.status = "Rejected"
        req.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"status": req.status}}

    if decision == "escalate":
        req.status = "Escalated"
        req.escalated_to_hr = 1
        req.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "data": {"status": req.status}}

    # approve
    req.status = "Approved"
    req.save(ignore_permissions=True)

    # Apply changes (only for update_existing)
    if req.request_type == "update_existing" and req.employee:
        try:
            changes = _as_dict(req.requested_changes)
            emp = frappe.get_doc("Employee", req.employee)

            # Apply ONLY whitelisted-safe fields. Keep restricted fields for HR-only flow.
            # These fieldnames are common in ERPNext; if your instance differs, update mapping.
            safe_map = {
                "personal_email": "personal_email",
                "cell_number": "cell_number",
                "current_address": "current_address",
                "emergency_contact_person": "emergency_contact_person",
                "emergency_contact_number": "emergency_phone_number",
                "selfie_file_url": None,  # stored on request; Employee photo handled separately
            }

            for input_key, emp_field in safe_map.items():
                if emp_field and input_key in changes and changes[input_key] is not None:
                    setattr(emp, emp_field, changes[input_key])

            emp.save(ignore_permissions=True)
            req.status = "Applied"
            req.applied_at = now_datetime()
            req.applied_by = frappe.session.user
            req.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(title="BEI Onboarding apply failed", message=str(e))
            return {"success": False, "error": "Approved but failed to apply changes", "code": "APPLY_FAILED"}

    frappe.db.commit()
    return {"success": True, "data": {"status": req.status}}



