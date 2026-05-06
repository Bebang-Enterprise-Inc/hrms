import re

import frappe

# S237 (2026-05-05): Bio ID ranges
#   9xxxxxx (3000001..9999999 with leading 9) → real BEI employees (Master CSV authoritative)
#   3xxxxxx (3000001..3999999) → test employees (L3, browser, automation fixtures)
# Both ranges accepted at validate to allow Desk-side edits on legitimate test rows
# without re-introducing the test/real Bio ID collision that S237 cleaned up.
# See `.claude/skills/l3-v2-bei-erp/SKILL.md` and `.claude/skills/audit-plan-bei-erp/SKILL.md`
# for the full rule set.
_BIO_ID_PATTERN = re.compile(r"^[39]\d{6}$")


def validate_employee_bio_id(doc, method=None):
	"""Validate Bio ID format on Employee save.

	Accepts:
	  - 9xxxxxx (real BEI employees, Master CSV range)
	  - 3xxxxxx (test employees, L3/automation range — S237 reservation)
	"""
	for field in ("attendance_device_id", "new_attendance_device_id"):
		val = getattr(doc, field, None)
		if val:
			bio_id = str(val).strip()
			if not _BIO_ID_PATTERN.match(bio_id):
				frappe.throw(
					f"Bio ID '{bio_id}' is invalid. Must match either 9xxxxxx "
					f"(real employees) or 3xxxxxx (test fixtures, S237 reservation). "
					f"Examples: 9001234 (real), 3000005 (test).",
					frappe.ValidationError,
				)
