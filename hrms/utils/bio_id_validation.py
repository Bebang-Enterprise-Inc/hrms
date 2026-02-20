import re

import frappe


def validate_employee_bio_id(doc, method=None):
	"""Validate Bio ID format on Employee save. Must be 9xxxxxx (7 digits starting with 9)."""
	if doc.attendance_device_id:
		bio_id = str(doc.attendance_device_id).strip()
		if not re.match(r"^9\d{6}$", bio_id):
			frappe.throw(
				f"Bio ID '{bio_id}' is invalid. Must match format 9xxxxxx "
				f"(7 digits starting with 9). Example: 9001234",
				frappe.ValidationError,
			)
