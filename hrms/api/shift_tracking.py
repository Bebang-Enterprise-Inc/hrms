"""Shift Tracking (Remote Punch) API endpoints

Provides 7 endpoints for the daily punch-in/out workflow used by 600+ store employees:
  1. punch_in     - GPS + selfie at shift start (row-level lock for race conditions)
  2. punch_out    - GPS only at shift end
  3. get_active_punch    - Current active punch for employee
  4. get_my_punch_history - Employee's paginated punch history
  5. get_team_punches    - Manager review queue with filters
  6. verify_punch        - Approve/flag individual punch
  7. bulk_verify_punches - Bulk approve/reject for efficiency
"""

import json

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, cint

from hrms.api.official_business import validate_image_upload
from hrms.utils.aws_location import AWSLocationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_employee() -> str:
    """Return the Employee ID linked to the current session user, or throw."""
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user, "status": "Active"},
        "name",
    )
    if not employee:
        frappe.throw(_("No active employee record found for current user"))
    return employee


def _has_supervisor_role() -> bool:
    """Check whether the current user holds a supervisor role."""
    roles = frappe.get_roles()
    return bool(
        set(roles) & {"Store Supervisor", "Area Supervisor", "HR User", "HR Manager", "System Manager"}
    )


def _get_subordinates(manager_employee_id: str) -> list[str]:
    """Return employee IDs that report to *manager_employee_id*."""
    return frappe.get_all(
        "Employee",
        filters={"reports_to": manager_employee_id, "status": "Active"},
        pluck="name",
    )


# ---------------------------------------------------------------------------
# 1. Punch In
# ---------------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def punch_in(latitude: float, longitude: float, accuracy: float, selfie_base64: str):
    """Punch in with GPS + selfie. Uses row-level lock to prevent duplicate punches.

    Args:
        latitude:  GPS latitude  (degrees)
        longitude: GPS longitude (degrees)
        accuracy:  GPS accuracy  (meters)
        selfie_base64: Base64-encoded selfie image (data URL or raw)

    Returns:
        dict with shift record name, address, status
    """
    employee = _get_current_employee()

    latitude = float(latitude)
    longitude = float(longitude)
    accuracy = float(accuracy)

    # Reject poor GPS signal
    if accuracy > 100:
        frappe.throw(_("GPS accuracy too low ({0}m). Please move to an open area.").format(
            int(accuracy)
        ))

    # ---- Row-level lock: prevent duplicate punch-in (race condition guard) ----
    active_shift = frappe.db.sql(
        """
        SELECT name
        FROM `tabBEI Shift Record`
        WHERE employee = %s
          AND punch_out_time IS NULL
          AND status = 'In Progress'
        FOR UPDATE
        """,
        (employee,),
        as_dict=True,
    )

    if active_shift:
        frappe.throw(_("Already punched in. Punch out first."))

    # Validate and decode selfie
    if not selfie_base64:
        frappe.throw(_("Selfie is required for punch-in"))
    img_data = validate_image_upload(selfie_base64)

    # Reverse geocode
    aws_location = AWSLocationService()
    address = aws_location.reverse_geocode(latitude, longitude)

    # Create shift record
    shift_doc = frappe.get_doc({
        "doctype": "BEI Shift Record",
        "employee": employee,
        "punch_in_time": now_datetime(),
        "punch_in_latitude": latitude,
        "punch_in_longitude": longitude,
        "punch_in_accuracy": accuracy,
        "punch_in_address": address or f"{latitude}, {longitude}",
        "status": "In Progress",
        "verification_status": "Pending",
    })

    # Save selfie as standalone private file first (no attachment link yet)
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": (
            f"punch_in_{employee}_{now_datetime().strftime('%Y%m%d_%H%M%S')}"
            f"_{frappe.generate_hash(length=6)}.jpg"
        ),
        "is_private": 1,
        "content": img_data,
    })
    file_doc.save(ignore_permissions=True)

    # Set photo URL on shift doc and insert (punch_in_photo is mandatory)
    shift_doc.punch_in_photo = file_doc.file_url
    shift_doc.insert(ignore_permissions=True)

    # Now link the file to the shift record (use set_value to avoid
    # TimestampMismatchError — Frappe File hooks update modified between saves)
    frappe.db.set_value("File", file_doc.name, {
        "attached_to_doctype": "BEI Shift Record",
        "attached_to_name": shift_doc.name,
    })

    return {
        "name": shift_doc.name,
        "status": "success",
        "message": _("Punch-in recorded"),
        "punch_in_address": shift_doc.punch_in_address,
        "punch_in_time": str(shift_doc.punch_in_time),
    }


# ---------------------------------------------------------------------------
# 2. Punch Out
# ---------------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def punch_out(latitude: float, longitude: float, accuracy: float, notes: str = None):
    """Punch out with GPS (no selfie required).

    Args:
        latitude:  GPS latitude  (degrees)
        longitude: GPS longitude (degrees)
        accuracy:  GPS accuracy  (meters)
        notes:     Optional shift notes

    Returns:
        dict with shift name, total hours, status
    """
    employee = _get_current_employee()

    latitude = float(latitude)
    longitude = float(longitude)
    accuracy = float(accuracy)

    # Reject poor GPS signal
    if accuracy > 100:
        frappe.throw(_("GPS accuracy too low ({0}m). Please move to an open area.").format(
            int(accuracy)
        ))

    # Find active punch (row-level lock to prevent double punch-out)
    active = frappe.db.sql(
        """
        SELECT name
        FROM `tabBEI Shift Record`
        WHERE employee = %s
          AND punch_out_time IS NULL
          AND status = 'In Progress'
        FOR UPDATE
        """,
        (employee,),
        as_dict=True,
    )

    if not active:
        frappe.throw(_("No active punch found. Please punch in first."))

    shift_doc = frappe.get_doc("BEI Shift Record", active[0].name)

    # Reverse geocode
    aws_location = AWSLocationService()
    address = aws_location.reverse_geocode(latitude, longitude)

    # Update punch-out fields
    shift_doc.punch_out_time = now_datetime()
    shift_doc.punch_out_latitude = latitude
    shift_doc.punch_out_longitude = longitude
    shift_doc.punch_out_accuracy = accuracy
    shift_doc.punch_out_address = address or f"{latitude}, {longitude}"
    shift_doc.status = "Completed"

    if notes:
        shift_doc.notes = notes

    # validate() in the controller will calculate total_hours, overtime_flag,
    # cross_day_flag, and velocity_flag automatically
    shift_doc.save(ignore_permissions=True)

    return {
        "name": shift_doc.name,
        "status": "success",
        "message": _("Punch-out recorded"),
        "punch_out_address": shift_doc.punch_out_address,
        "punch_out_time": str(shift_doc.punch_out_time),
        "total_hours": shift_doc.total_hours,
    }


# ---------------------------------------------------------------------------
# 3. Get Active Punch
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_active_punch():
    """Return the current employee's active (in-progress) punch, or None."""
    employee = _get_current_employee()

    active = frappe.db.get_value(
        "BEI Shift Record",
        filters={"employee": employee, "status": "In Progress", "punch_out_time": ("is", "not set")},
        fieldname=[
            "name", "punch_in_time", "punch_in_address",
            "punch_in_latitude", "punch_in_longitude", "punch_in_photo",
        ],
        as_dict=True,
    )

    return active


# ---------------------------------------------------------------------------
# 4. Get My Punch History
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_my_punch_history(limit: int = 20, offset: int = 0):
    """Return paginated punch history for the current employee.

    Args:
        limit:  Number of records per page (default 20, max 100)
        offset: Number of records to skip (default 0)

    Returns:
        list of shift record dicts
    """
    employee = _get_current_employee()

    limit = min(cint(limit) or 20, 100)
    offset = max(cint(offset) or 0, 0)

    records = frappe.get_all(
        "BEI Shift Record",
        filters={"employee": employee},
        fields=[
            "name", "punch_in_time", "punch_out_time",
            "punch_in_address", "punch_out_address",
            "total_hours", "status", "verification_status",
            "overtime_flag", "cross_day_flag", "velocity_flag",
            "auto_punched_out", "notes",
        ],
        order_by="punch_in_time desc",
        limit_page_length=limit,
        limit_start=offset,
    )

    return records


# ---------------------------------------------------------------------------
# 5. Get Team Punches (Manager Review Queue)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=30, seconds=60)
def get_team_punches(date=None, employee_filter=None, status_filter=None):
    """Return shift records for the manager's team with optional filters.

    Args:
        date:             Single date (YYYY-MM-DD) to filter on
        employee_filter:  Single employee ID or JSON list of IDs
        status_filter:    Verification status: Pending, Approved, or Flagged

    Returns:
        list of shift record dicts (max 200)
    """
    if not _has_supervisor_role():
        frappe.throw(_("Insufficient permissions to view team punches"))

    employee = _get_current_employee()
    subordinates = _get_subordinates(employee)

    if not subordinates:
        return []

    filters = {"employee": ["in", subordinates]}

    # Date filter
    if date:
        filters["punch_in_time"] = [">=", date]

    # Employee filter (single or list)
    if employee_filter:
        if isinstance(employee_filter, str):
            try:
                employee_filter = json.loads(employee_filter)
            except (json.JSONDecodeError, ValueError):
                pass

        if isinstance(employee_filter, list):
            # Intersect requested employees with actual subordinates
            valid = [e for e in employee_filter if e in subordinates]
            if valid:
                filters["employee"] = ["in", valid]
            else:
                return []
        else:
            if employee_filter in subordinates:
                filters["employee"] = employee_filter
            else:
                return []

    # Status filter
    if status_filter:
        if status_filter not in ("Pending", "Approved", "Flagged"):
            frappe.throw(_("Invalid status filter. Use Pending, Approved, or Flagged."))
        filters["verification_status"] = status_filter

    shifts = frappe.get_all(
        "BEI Shift Record",
        filters=filters,
        fields=[
            "name", "employee", "employee_name",
            "punch_in_time", "punch_out_time",
            "total_hours",
            "punch_in_latitude", "punch_in_longitude",
            "punch_in_address", "punch_in_photo",
            "punch_out_address",
            "status", "verification_status",
            "overtime_flag", "cross_day_flag", "velocity_flag",
            "auto_punched_out", "notes",
        ],
        order_by="punch_in_time desc",
        limit_page_length=200,
    )

    return shifts


# ---------------------------------------------------------------------------
# 6. Verify Punch (Individual)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def verify_punch(shift_id: str, verification_status: str, notes: str = None):
    """Approve or flag an individual punch record.

    Args:
        shift_id:            BEI Shift Record name
        verification_status: 'Approved' or 'Flagged'
        notes:               Optional reviewer notes

    Returns:
        dict with success status
    """
    if not _has_supervisor_role():
        frappe.throw(_("Insufficient permissions to verify punches"))

    if verification_status not in ("Approved", "Flagged"):
        frappe.throw(_("Invalid verification status. Use 'Approved' or 'Flagged'."))

    employee = _get_current_employee()
    subordinates = _get_subordinates(employee)

    shift = frappe.get_doc("BEI Shift Record", shift_id)

    # Ensure the punch belongs to a subordinate
    if shift.employee not in subordinates:
        frappe.throw(_("You can only verify punches for your team members"))

    shift.verification_status = verification_status
    shift.verified_by = frappe.session.user
    shift.verification_time = now_datetime()
    if notes:
        shift.verification_notes = notes

    shift.save(ignore_permissions=True)

    return {
        "status": "success",
        "message": _("Punch {0}").format(verification_status.lower()),
    }


# ---------------------------------------------------------------------------
# 7. Bulk Verify Punches
# ---------------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def bulk_verify_punches(shift_ids, verification_status: str, notes: str = None):
    """Approve or flag multiple punch records at once.

    Args:
        shift_ids:           List of BEI Shift Record names (or JSON string)
        verification_status: 'Approved' or 'Flagged'
        notes:               Optional reviewer notes applied to all

    Returns:
        dict with updated count
    """
    if not _has_supervisor_role():
        frappe.throw(_("Insufficient permissions to verify punches"))

    if verification_status not in ("Approved", "Flagged"):
        frappe.throw(_("Invalid verification status. Use 'Approved' or 'Flagged'."))

    # Parse shift_ids if passed as JSON string
    if isinstance(shift_ids, str):
        try:
            shift_ids = json.loads(shift_ids)
        except (json.JSONDecodeError, ValueError):
            frappe.throw(_("shift_ids must be a valid JSON list"))

    if not isinstance(shift_ids, list):
        frappe.throw(_("shift_ids must be a list"))

    if not shift_ids:
        frappe.throw(_("No shift IDs provided"))

    if len(shift_ids) > 100:
        frappe.throw(_("Maximum 100 punches can be verified at once"))

    employee = _get_current_employee()
    subordinates = _get_subordinates(employee)

    updated_count = 0

    for shift_id in shift_ids:
        shift = frappe.get_doc("BEI Shift Record", shift_id)

        # Skip if not a subordinate
        if shift.employee not in subordinates:
            continue

        shift.verification_status = verification_status
        shift.verified_by = frappe.session.user
        shift.verification_time = now_datetime()
        shift.verification_notes = notes or ""
        shift.save(ignore_permissions=True)
        updated_count += 1

    return {
        "status": "success",
        "updated_count": updated_count,
        "message": _("{0} punches {1}").format(updated_count, verification_status.lower()),
    }
