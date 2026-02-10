"""Official Business API endpoints"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.rate_limiter import rate_limit
from frappe.query_builder import DocType
from hrms.utils.aws_location import AWSLocationService
from hrms.utils.geo import calculate_haversine_distance


NO_EMPLOYEE_MSG = "Your account is not linked to an employee record. Please contact HR to set up your employee profile."


def _get_employee_or_throw():
    """Get Employee ID for current user, or throw a user-friendly error."""
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not employee:
        frappe.throw(_(NO_EMPLOYEE_MSG), title=_("Employee Record Not Found"))
    return employee


def validate_image_upload(base64_data: str, max_size_mb: int = 5) -> bytes:
    """Validate image upload for security and return decoded data

    Args:
        base64_data: Base64-encoded image data
        max_size_mb: Maximum allowed file size in MB (default: 5)

    Returns:
        bytes: Decoded image data if valid

    Raises:
        frappe.ValidationError: If validation fails
    """
    import base64
    import io
    from PIL import Image

    if not base64_data or not isinstance(base64_data, str):
        frappe.throw(_("Invalid image data"))

    try:
        # Remove data URL prefix if present
        image_data = base64.b64decode(
            base64_data.split(',')[1] if ',' in base64_data else base64_data
        )
    except Exception:
        frappe.throw(_("Invalid base64 image format"))

    # Check size
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        frappe.throw(_(f"Image too large ({size_mb:.1f}MB). Maximum {max_size_mb}MB allowed"))

    # Validate image format using Pillow (imghdr removed in Python 3.13)
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        image_format = img.format.lower() if img.format else None
        if image_format not in ('jpeg', 'png', 'webp', 'gif'):
            frappe.throw(_("Invalid image format. Only JPEG, PNG, WebP, GIF allowed"))
    except Exception:
        frappe.throw(_("Invalid or corrupted image file"))

    return image_data

@frappe.whitelist()
@rate_limit(limit=10, seconds=60)  # 10 requests per minute (AWS geocoding costs)
def checkout(
    destination: str,
    purpose: str,
    latitude: float,
    longitude: float,
    accuracy: float,
    selfie_base64: str,
    expected_return: str = None,
    gps_latitude: float = None,
    gps_longitude: float = None
):
    """Create OB checkout record

    Args:
        destination: Where employee is going
        purpose: Reason for OB
        latitude: Submitted latitude (adjusted pin position, or raw GPS if no map)
        longitude: Submitted longitude (adjusted pin position, or raw GPS if no map)
        accuracy: GPS accuracy in meters
        selfie_base64: Base64-encoded selfie image
        expected_return: Optional expected return time
        gps_latitude: Raw GPS latitude from device (optional, for audit trail)
        gps_longitude: Raw GPS longitude from device (optional, for audit trail)

    Returns:
        Dict with OB record name and status
    """
    # Get current employee
    employee = _get_employee_or_throw()

    # Raw GPS coordinates: use provided values or fall back to submitted coords
    raw_gps_lat = float(gps_latitude) if gps_latitude is not None else float(latitude)
    raw_gps_lng = float(gps_longitude) if gps_longitude is not None else float(longitude)

    # Enforce selfie requirement
    if not selfie_base64:
        frappe.throw(_("Selfie is required for check-out"))

    # Reject poor GPS signal
    if float(accuracy) > 100:
        frappe.throw(_("GPS accuracy too low ({0}m). Please move to an open area with clear sky view for better signal.".format(int(float(accuracy)))))

    # Validate adjusted position is within 300m of raw GPS (anti-spoofing)
    # 305m server tolerance for floating-point diff between frontend/backend Haversine
    adjustment_distance = calculate_haversine_distance(
        raw_gps_lat, raw_gps_lng, float(latitude), float(longitude)
    )
    if adjustment_distance > 305:
        frappe.throw(
            _("Adjusted location is {0}m from GPS position. Maximum 300m allowed.").format(
                int(adjustment_distance)
            )
        )

    # Check if employee already has active OB (with row-level lock to prevent race condition)
    BEIOfficialBusiness = DocType("BEI Official Business")
    active_ob = (
        frappe.qb.from_(BEIOfficialBusiness)
        .select(BEIOfficialBusiness.name)
        .where(BEIOfficialBusiness.employee == employee)
        .where(BEIOfficialBusiness.status == "Out")
        .for_update()  # Row-level lock prevents duplicate checkout race condition
        .run()
    )

    if active_ob:
        frappe.throw(_("You already have an active OB. Please check in first."))

    # Reverse geocode address
    aws_location = AWSLocationService()
    address = aws_location.reverse_geocode(float(latitude), float(longitude))

    # Find nearest OB location
    nearest = aws_location.find_nearest_ob_location(float(latitude), float(longitude))

    # Create OB record (stores both raw GPS and adjusted pin position)
    ob_doc = frappe.get_doc({
        "doctype": "BEI Official Business",
        "employee": employee,
        "destination": destination,
        "purpose": purpose,
        "checkout_datetime": now_datetime(),
        "checkout_latitude": float(latitude),
        "checkout_longitude": float(longitude),
        "checkout_accuracy": float(accuracy),
        "checkout_gps_latitude": raw_gps_lat,
        "checkout_gps_longitude": raw_gps_lng,
        "checkout_adjustment_distance": round(adjustment_distance, 1),
        "checkout_address": address or f"{latitude}, {longitude}",
        "expected_return": expected_return,
        "status": "Out"
    })

    # Validate selfie before insert (security check)
    img_data = None
    if selfie_base64:
        img_data = validate_image_upload(selfie_base64)

    # Add nearest location info
    if nearest:
        ob_doc.matched_ob_location = nearest['location_id']
        ob_doc.distance_from_matched = nearest['distance_meters']
        ob_doc.checkout_within_geofence = nearest['within_geofence']

    ob_doc.insert(ignore_permissions=True)

    # Save selfie AFTER insert so ob_doc.name is available for attached_to_name
    if img_data:
        file_doc = frappe.get_doc({
            "doctype": "File",
            "attached_to_doctype": "BEI Official Business",
            "attached_to_name": ob_doc.name,
            "file_name": f"checkout_selfie_{employee}_{now_datetime().strftime('%Y%m%d_%H%M%S')}_{frappe.generate_hash(length=6)}.jpg",
            "is_private": 1,
            "content": img_data
        })
        file_doc.save(ignore_permissions=True)

        # Use set_value to avoid TimestampMismatchError — File save hooks
        # may update ob_doc.modified between insert and this save
        frappe.db.set_value("BEI Official Business", ob_doc.name,
                           "checkout_selfie", file_doc.file_url)

    return {
        "name": ob_doc.name,
        "status": "success",
        "message": _("Check-out successful"),
        "checkout_address": ob_doc.checkout_address,
        "within_geofence": ob_doc.checkout_within_geofence
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)  # 10 requests per minute (AWS geocoding costs)
def checkin(
    ob_name: str,
    latitude: float,
    longitude: float,
    accuracy: float,
    selfie_base64: str
):
    """Update OB record with check-in data

    Args:
        ob_name: OB record name
        latitude: GPS latitude
        longitude: GPS longitude
        accuracy: GPS accuracy in meters
        selfie_base64: Base64-encoded selfie image

    Returns:
        Dict with status and total hours
    """
    ob_doc = frappe.get_doc("BEI Official Business", ob_name)

    # Verify ownership
    employee = _get_employee_or_throw()
    if ob_doc.employee != employee:
        frappe.throw(_("You can only check in to your own OB records"))

    if ob_doc.status != "Out":
        frappe.throw(_("This OB is not in 'Out' status"))

    # Reject poor GPS signal
    if float(accuracy) > 100:
        frappe.throw(_("GPS accuracy too low ({0}m). Please move to an open area with clear sky view for better signal.".format(int(float(accuracy)))))

    # Reverse geocode address
    aws_location = AWSLocationService()
    address = aws_location.reverse_geocode(float(latitude), float(longitude))

    # Update check-in fields
    ob_doc.checkin_datetime = now_datetime()
    ob_doc.checkin_latitude = float(latitude)
    ob_doc.checkin_longitude = float(longitude)
    ob_doc.checkin_accuracy = float(accuracy)
    ob_doc.checkin_address = address or f"{latitude}, {longitude}"
    ob_doc.status = "Returned"

    # Save selfie
    if selfie_base64:
        # Validate and decode image (security check + decode in one step)
        img_data = validate_image_upload(selfie_base64)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "attached_to_doctype": "BEI Official Business",
            "attached_to_name": ob_name,
            "file_name": f"checkin_selfie_{employee}_{now_datetime().strftime('%Y%m%d_%H%M%S')}_{frappe.generate_hash(length=6)}.jpg",
            "is_private": 1,
            "content": img_data
        })
        file_doc.save(ignore_permissions=True)

        ob_doc.checkin_selfie = file_doc.file_url

    ob_doc.save(ignore_permissions=True)

    return {
        "name": ob_doc.name,
        "status": "success",
        "message": _("Check-in successful"),
        "total_hours": ob_doc.total_hours_out,
        "checkin_address": ob_doc.checkin_address
    }


@frappe.whitelist()
def get_my_ob_records(limit: int = 20):
    """Get current employee's OB records

    Args:
        limit: Number of records to return (default: 20)

    Returns:
        List of OB records
    """
    employee = _get_employee_or_throw()

    records = frappe.get_all(
        "BEI Official Business",
        filters={"employee": employee},
        fields=[
            "name", "destination", "purpose", "checkout_datetime", "checkin_datetime",
            "status", "total_hours_out", "checkout_address", "checkin_address",
            "supervisor_action", "checkout_within_geofence"
        ],
        order_by="checkout_datetime desc",
        limit=limit
    )

    return records


@frappe.whitelist()
def get_active_ob():
    """Get current employee's active OB record

    Returns:
        Active OB record or None
    """
    employee = _get_employee_or_throw()

    active = frappe.db.get_value(
        "BEI Official Business",
        filters={"employee": employee, "status": "Out"},
        fieldname=["name", "destination", "purpose", "checkout_datetime", "checkout_address", "expected_return"],
        as_dict=True
    )

    return active


@frappe.whitelist()
@rate_limit(limit=30, seconds=60)  # 30/min for read-only operations
def get_pending_review():
    """Get OB records pending supervisor review

    Returns:
        List of records awaiting review
    """
    # Get employees reporting to current user
    employee = _get_employee_or_throw()

    records = frappe.get_all(
        "BEI Official Business",
        filters={
            "supervisor": employee,
            "status": "Returned",
            "supervisor_action": "Pending"
        },
        fields=[
            "name", "employee", "employee_name", "destination", "purpose",
            "checkout_datetime", "checkout_address", "checkout_selfie",
            "checkin_datetime", "checkin_address", "checkin_selfie",
            "total_hours_out", "checkout_within_geofence", "velocity_flag",
            "flag_reason"
        ],
        order_by="checkin_datetime desc"
    )

    return records


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)  # 20/min for supervisor actions
def review_ob(
    ob_name: str,
    action: str,
    notes: str = None
):
    """Supervisor reviews OB record

    Args:
        ob_name: OB record name
        action: "Approved" or "Rejected"
        notes: Optional supervisor notes

    Returns:
        Success status
    """
    if action not in ["Approved", "Rejected"]:
        frappe.throw(_("Invalid action. Must be 'Approved' or 'Rejected'"))

    ob_doc = frappe.get_doc("BEI Official Business", ob_name)

    # Verify supervisor
    employee = _get_employee_or_throw()
    if ob_doc.supervisor != employee:
        frappe.throw(_("You are not the supervisor for this employee"))

    ob_doc.supervisor_action = action
    ob_doc.supervisor_notes = notes or ""
    ob_doc.reviewed_datetime = now_datetime()
    ob_doc.status = "Verified" if action == "Approved" else "Flagged"

    ob_doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "message": _(f"OB {action.lower()} successfully")
    }


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)  # 10/min for write operations
def cancel_ob(ob_name: str):
    """Cancel an OB record (before check-in)

    Args:
        ob_name: OB record name

    Returns:
        Success status
    """
    ob_doc = frappe.get_doc("BEI Official Business", ob_name)

    # Verify ownership
    employee = _get_employee_or_throw()
    if ob_doc.employee != employee:
        frappe.throw(_("You can only cancel your own OB records"))

    if ob_doc.status not in ["Draft", "Out"]:
        frappe.throw(_("Can only cancel OB before check-in"))

    ob_doc.status = "Cancelled"
    ob_doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "message": _("OB cancelled successfully")
    }
