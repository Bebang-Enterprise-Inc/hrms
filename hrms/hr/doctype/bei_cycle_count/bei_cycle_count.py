# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEICycleCount(Document):
	def validate(self):
		"""Compute counted_qty from WHOLE + LOOSE, populate system_qty from Bin, compute variance."""
		for item in self.items:
			# Fetch conversion_factor from UOM Conversion Detail (defaults to 1.0 if not set)
			cf = frappe.db.get_value(
				"UOM Conversion Detail",
				{"parent": item.item_code, "uom": item.uom},
				"conversion_factor"
			)
			item.conversion_factor = cf if cf and cf > 0 else 1.0

			# Compute counted_qty from WHOLE + LOOSE
			# WHOLE = full packages in stock UOM, LOOSE = fractional amount
			# With default cf=1.0: counted_qty = whole + loose (both in same UOM)
			if item.counted_qty_whole is not None or item.counted_qty_loose is not None:
				whole = item.counted_qty_whole or 0
				loose = item.counted_qty_loose or 0.0
				item.counted_qty = whole + (loose / item.conversion_factor)

			# B-6: Populate system_qty and unit_cost from Bin in a single query
			bin_data = frappe.db.get_value(
				"Bin", {"item_code": item.item_code, "warehouse": self.store},
				["actual_qty", "valuation_rate"], as_dict=True
			) or {}
			item.system_qty = bin_data.get("actual_qty") or 0
			bin_rate = bin_data.get("valuation_rate")
			item.unit_cost = bin_rate if bin_rate else (
				frappe.db.get_value("Item", item.item_code, "valuation_rate") or 0.0
			)

			# Compute variance
			item.counted_qty = item.counted_qty or 0
			item.variance_qty = item.counted_qty - item.system_qty
			item.variance_value = item.variance_qty * item.unit_cost

	def before_insert(self):
		if not self.counted_by:
			self.counted_by = frappe.session.user

	def on_submit(self):
		"""Set custom status field to 'Submitted' when Frappe docstatus changes to 1."""
		self.db_set("status", "Submitted")

	def before_submit(self):
		"""AUDIT-8: Enforce unique constraint at submit time (TOCTOU race protection).
		Excludes Rejected and Resubmitted records — resubmissions must be allowed."""
		existing = frappe.db.sql("""
			SELECT name FROM `tabBEI Cycle Count`
			WHERE store = %s AND count_date = %s AND count_type = %s
			  AND docstatus = 1
			  AND status NOT IN ('Rejected', 'Resubmitted')
			  AND name != %s
			LIMIT 1
		""", (self.store, self.count_date, self.count_type, self.name))
		if existing:
			frappe.throw(_("Cycle count already submitted for this store/date/type"))

	def before_save(self):
		# Calculate total variance value
		total_variance = 0
		for item in self.items:
			if item.variance_value:
				total_variance += item.variance_value
		self.total_variance_value = total_variance
