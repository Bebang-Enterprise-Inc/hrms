# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEICycleCount(Document):
	def validate(self):
		"""Compute counted_qty from WHOLE + LOOSE, fetch unit_cost, compute variance."""
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

			# Fetch unit_cost from Item.valuation_rate (read-only, never from frontend)
			item.unit_cost = frappe.db.get_value("Item", item.item_code, "valuation_rate") or 0.0

			# Compute variance
			item.variance_qty = item.counted_qty - (item.system_qty or 0)
			item.variance_value = item.variance_qty * item.unit_cost

	def before_insert(self):
		if not self.counted_by:
			self.counted_by = frappe.session.user

	def before_save(self):
		# Calculate total variance value
		total_variance = 0
		for item in self.items:
			if item.variance_value:
				total_variance += item.variance_value
		self.total_variance_value = total_variance
