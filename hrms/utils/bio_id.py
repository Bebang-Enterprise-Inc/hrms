"""Shared BEI Bio ID (attendance_device_id) generator.

Created in S164 Phase 1 to eliminate HR's manual "next available Bio ID"
tracking and prevent duplicate assignments. Ground truth is the
`Employee.attendance_device_id` column.
"""

from __future__ import annotations

import re

import frappe

BIO_ID_RE = re.compile(r"^9\d{6}$")


def generate_next_bio_id() -> str:
	"""Return next sequential Bio ID in 9XXXXXX format.

	Uses SELECT MAX(...) FOR UPDATE to prevent concurrent collision.
	Starts at 9000003 if no valid Bio IDs exist yet.
	"""
	result = frappe.db.sql(
		"""
        SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) AS max_bio
        FROM `tabEmployee`
        WHERE attendance_device_id REGEXP '^9[0-9]{6}$'
        FOR UPDATE
    """,
		as_dict=True,
	)
	current_max = (result[0].get("max_bio") if result else None) or 9000002
	next_id = str(int(current_max) + 1)
	if not BIO_ID_RE.match(next_id):
		frappe.throw(f"Bio ID generator overflow: computed {next_id}")
	# Paranoia: FOR UPDATE should already prevent this
	if frappe.db.exists("Employee", {"attendance_device_id": next_id}):
		frappe.throw(f"Generated Bio ID {next_id} already exists")
	return next_id
