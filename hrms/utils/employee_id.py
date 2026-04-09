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

	S172 Defect #8 fix: query the `employee` field, not `name`. When Employee
	records are inserted via the ORM (`create_employee_direct`), Frappe's
	autoname generates `name` as HR-EMP-NNNNN per the naming_series rule,
	not as BEI-EMP-YYYY-NNNNN. The previous `SELECT name WHERE name LIKE
	'BEI-EMP-YYYY-%'` therefore returned the same stale maximum forever
	(cached at BEI-EMP-2026-00004 in prod), causing every call to return
	the same employee_id. Querying the `employee` field tracks the BEI
	sequence independently of however Frappe chooses to name the record.
	"""
	year = frappe.utils.nowdate()[:4]
	last_emp = frappe.db.sql(
		"""
        SELECT employee FROM tabEmployee
        WHERE employee LIKE %s
        ORDER BY employee DESC LIMIT 1 FOR UPDATE
    """,
		(f"BEI-EMP-{year}-%",),
		as_dict=True,
	)

	if last_emp:
		last_num = int(last_emp[0]["employee"].split("-")[-1])
		new_num = last_num + 1
	else:
		new_num = 1

	return f"BEI-EMP-{year}-{new_num:05d}"
