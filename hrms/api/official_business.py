"""Official Business API endpoints"""

import frappe
from frappe import _
from frappe.utils import now_datetime
from hrms.utils.aws_location import AWSLocationService


def validate_image_upload(base64_data: str, max_size_mb: int = 5) -> bool:
    """Validate image upload for security

    Args:
        base64_data: Base64-encoded image data
        max_size_mb: Maximum allowed file size in MB (default: 5)

    Returns:
        bool: True if valid

    Raises:
        frappe.ValidationError: If validation fails
    """
    import base64
    import imghdr

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

    # Validate image format using imghdr
    image_type = imghdr.what(None, h=image_data)
    if image_type not in ['jpeg', 'png', 'webp', 'gif']:
        frappe.throw(_("Invalid image format. Only JPEG, PNG, WebP, GIF allowed"))

    return True

@frappe.whitelist()
def checkout(
    destination: str,
    purpose: str,
    latitude: float,
    longitude: float,
    accuracy: float,
    selfie_base64: str,
    expected_return: str = None
):
    """Create OB checkout record

    Args:
        destination: Where employee is going
        purpose: Reason for OB
        latitude: GPS latitude
        longitude: GPS longitude
        accuracy: GPS accuracy in meters
        selfie_base64: Base64-encoded selfie image
        expected_return: Optional expected return time

    Returns:
        Dict with OB record name and status
    """
    # Get current employee
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        frappe.throw(_("No employee record found for current user"))

    # Check if employee already has active OB
    active_ob = frappe.db.exists("BEI Official Business", {
        "employee": employee,
        "status": "Out"
    })

    if active_ob:
        frappe.throw(_("You already have an active OB. Please check in first."))

    # Reverse geocode address
    aws_location = AWSLocationService()
    address = aws_location.reverse_geocode(float(latitude), float(longitude))

    # Find nearest OB location
    nearest = aws_location.find_nearest_ob_location(float(latitude), float(longitude))

    # Create OB record
    ob_doc = frappe.get_doc({
        "doctype": "BEI Official Business",
        "employee": employee,
        "destination": destination,
        "purpose": purpose,
        "checkout_datetime": now_datetime(),
        "checkout_latitude": float(latitude),
        "checkout_longitude": float(longitude),
        "checkout_accuracy": float(accuracy),
        "checkout_address": address or f"{latitude}, {longitude}",
        "expected_return": expected_return,
        "status": "Out"
    })

    # Save selfie
    if selfie_base64:
        # Validate image first (security check)
        validate_image_upload(selfie_base64)

        import base64
        import io
        from PIL import Image

        # Decode base64
        img_data = base64.b64decode(selfie_base64.split(',')[1] if ',' in selfie_base64 else selfie_base64)
        img = Image.open(io.BytesIO(img_data))

        # Save as file
        file_doc = frappe.get_doc({
            "doctype": "File",
            "attached_to_doctype": "BEI Official Business",
            "file_name": f"checkout_selfie_{employee}_{frappe.utils.now()}.jpg",
            "is_private": 1,
            "content": img_data
        })
        file_doc.save(ignore_permissions=True)

        ob_doc.checkout_selfie = file_doc.file_url

    # Add nearest location info
    if nearest:
        ob_doc.matched_ob_location = nearest['location_id']
        ob_doc.distance_from_matched = nearest['distance_meters']
        ob_doc.checkout_within_geofence = nearest['within_geofence']

    ob_doc.insert(ignore_permissions=True)

    return {
        "name": ob_doc.name,
        "status": "success",
        "message": _("Check-out successful"),
        "checkout_address": ob_doc.checkout_address,
        "within_geofence": ob_doc.checkout_within_geofence
    }


@frappe.whitelist()
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
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if ob_doc.employee != employee:
        frappe.throw(_("You can only check in to your own OB records"))

    if ob_doc.status != "Out":
        frappe.throw(_("This OB is not in 'Out' status"))

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
        # Validate image first (security check)
        validate_image_upload(selfie_base64)

        import base64
        import io
        from PIL import Image

        img_data = base64.b64decode(selfie_base64.split(',')[1] if ',' in selfie_base64 else selfie_base64)
        img = Image.open(io.BytesIO(img_data))

        file_doc = frappe.get_doc({
            "doctype": "File",
            "attached_to_doctype": "BEI Official Business",
            "attached_to_name": ob_name,
            "file_name": f"checkin_selfie_{employee}_{frappe.utils.now()}.jpg",
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
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        return []

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
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        return None

    active = frappe.db.get_value(
        "BEI Official Business",
        filters={"employee": employee, "status": "Out"},
        fieldname=["name", "destination", "checkout_datetime", "expected_return"],
        as_dict=True
    )

    return active


@frappe.whitelist()
def get_pending_review():
    """Get OB records pending supervisor review

    Returns:
        List of records awaiting review
    """
    # Get employees reporting to current user
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee:
        return []

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
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
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
def cancel_ob(ob_name: str):
    """Cancel an OB record (before check-in)

    Args:
        ob_name: OB record name

    Returns:
        Success status
    """
    ob_doc = frappe.get_doc("BEI Official Business", ob_name)

    # Verify ownership
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
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
