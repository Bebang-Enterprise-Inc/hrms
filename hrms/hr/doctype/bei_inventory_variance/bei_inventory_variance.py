# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIInventoryVariance(Document):
	def before_insert(self):
		if not self.reported_by:
			self.reported_by = frappe.session.user

	def before_save(self):
		# Calculate variance qty
		if self.actual_qty is not None and self.system_qty is not None:
			self.variance_qty = (self.actual_qty or 0) - (self.system_qty or 0)
