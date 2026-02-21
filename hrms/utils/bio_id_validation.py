import re

import frappe


def validate_employee_bio_id(doc, method=None):
	"""Validate Bio ID format on Employee save. Must be 9xxxxxx (7 digits starting with 9)."""
	for field in ("attendance_device_id", "new_attendance_device_id"):
		val = getattr(doc, field, None)
		if val:
			bio_id = str(val).strip()
			if not re.match(r"^9\d{6}$", bio_id):
				frappe.throw(
					f"Bio ID '{bio_id}' is invalid. Must match format 9xxxxxx "
					f"(7 digits starting with 9). Example: 9001234",
					frappe.ValidationError,
				)
