# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Backfill billing_type='Monthly Fees' on all existing BEI Billing Schedule records."""
	frappe.db.sql("""
		UPDATE `tabBEI Billing Schedule`
		SET billing_type = 'Monthly Fees',
			naming_series = 'BILL-MF-.YYYY.-.#####'
		WHERE billing_type IS NULL OR billing_type = ''
	""")
	frappe.db.commit()
