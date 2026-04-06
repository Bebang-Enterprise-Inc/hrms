"""Shared BEI employee ID generator.

Extracted from hrms/api/onboarding.py in S164 Phase 1 to provide a single
source of truth for the BEI-EMP-YYYY-NNNNN sequence so the existing
onboarding flow and the new create_employee_direct endpoint share the
same FOR UPDATE-locked sequence generator.
"""

from __future__ import annotations

import frappe


def generate_bei_employee_id() -> str:
	"""Generate the next sequential BEI-EMP-YYYY-NNNNN employee ID.

	Uses a SELECT ... FOR UPDATE lock to prevent concurrent collision.
	Must be called inside a transaction (Frappe's default request context
	provides one).
	"""
	year = frappe.utils.nowdate()[:4]
	last_emp = frappe.db.sql(
		"""
        SELECT name FROM tabEmployee
        WHERE name LIKE %s
        ORDER BY name DESC LIMIT 1 FOR UPDATE
    """,
		(f"BEI-EMP-{year}-%",),
		as_dict=True,
	)

	if last_emp:
		last_num = int(last_emp[0]["name"].split("-")[-1])
		new_num = last_num + 1
	else:
		new_num = 1

	return f"BEI-EMP-{year}-{new_num:05d}"
