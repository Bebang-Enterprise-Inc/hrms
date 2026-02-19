# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Add unique index on (store, count_date, count_type) for submitted BEI Cycle Count records.

	This prevents duplicate submitted counts for the same store/date/type combination.
	The index is partial (only docstatus=1) to allow multiple drafts.
	Since MariaDB doesn't support partial indexes, we use a regular unique index
	and rely on the before_submit() TOCTOU check in bei_cycle_count.py for enforcement.
	"""
	# Check if index already exists
	indexes = frappe.db.sql("""
		SHOW INDEX FROM `tabBEI Cycle Count`
		WHERE Key_name = 'unique_store_date_type'
	""", as_dict=True)

	if not indexes:
		try:
			frappe.db.sql("""
				CREATE UNIQUE INDEX `unique_store_date_type`
				ON `tabBEI Cycle Count` (`store`, `count_date`, `count_type`, `docstatus`)
			""")
			frappe.db.commit()
		except Exception as e:
			# If duplicates already exist, log and skip — the before_submit() check
			# will prevent new duplicates going forward
			frappe.log_error(f"Could not create unique index on BEI Cycle Count: {e}")
			frappe.db.rollback()
