# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BEIProductionTarget(Document):
	def validate(self):
		"""Compute stored fields from child table (DM-5 compliance)."""
		total_recommended = 0
		total_targeted = 0
		total_produced = 0

		for row in self.get("items", []):
			total_recommended += flt(row.recommended_qty)
			total_targeted += flt(row.target_qty)
			total_produced += flt(row.actual_produced)

			# Division-by-zero guards (Blocker 7)
			row.deviation_pct = (
				flt((flt(row.target_qty) - flt(row.recommended_qty)) / flt(row.recommended_qty) * 100, 1)
				if flt(row.recommended_qty) > 0
				else 0
			)
			row.completion_pct = (
				flt(flt(row.actual_produced) / flt(row.target_qty) * 100, 1)
				if flt(row.target_qty) > 0
				else (100 if flt(row.target_qty) == 0 else 0)
			)

		self.total_recommended = flt(total_recommended, 2)
		self.total_targeted = flt(total_targeted, 2)
		self.total_produced = flt(total_produced, 2)
