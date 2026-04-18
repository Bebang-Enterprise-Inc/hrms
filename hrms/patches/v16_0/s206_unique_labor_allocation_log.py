# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Add unique index on (year, month, employee) for BEI Labor Allocation Log.

	S206 idempotency is enforced in validate() on the DocType controller, but
	that check happens in Python — concurrent inserts can race past it. The
	DB-level unique index closes the race.

	Idempotent: if index already exists, skip silently.
	"""
	table = "tabBEI Labor Allocation Log"

	# Skip if the DocType table hasn't been created yet (e.g., first-install).
	exists = frappe.db.sql(
		"""
		SELECT COUNT(*) AS c FROM information_schema.tables
		WHERE table_schema = DATABASE() AND table_name = %s
		""",
		(table,),
		as_dict=True,
	)
	if not exists or exists[0]["c"] == 0:
		return

	indexes = frappe.db.sql(
		f"SHOW INDEX FROM `{table}` WHERE Key_name = 'idx_year_month_employee'",
		as_dict=True,
	)
	if indexes:
		return

	try:
		frappe.db.sql(
			f"""
			CREATE UNIQUE INDEX `idx_year_month_employee`
			ON `{table}` (`year`, `month`, `employee`)
			"""
		)
		frappe.db.commit()
	except Exception as exc:
		# If duplicates already exist, the CREATE will fail. Log and continue —
		# the Python validate() catches new duplicates going forward. A manual
		# cleanup of dupes is required before this patch can succeed.
		frappe.log_error(
			title="S206 unique index create failed (dupes or privilege issue)",
			message=str(exc),
		)
		frappe.db.rollback()
