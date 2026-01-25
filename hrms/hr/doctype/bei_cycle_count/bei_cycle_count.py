# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEICycleCount(Document):
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
