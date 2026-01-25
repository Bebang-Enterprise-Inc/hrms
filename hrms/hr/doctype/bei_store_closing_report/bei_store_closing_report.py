# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIStoreClosingReport(Document):
	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user

	def before_save(self):
		# Calculate cash variance
		expected_cash = (self.pos_total_sales or 0) - (self.card_payments or 0) - (self.gcash_total or 0)
		self.cash_variance = (self.actual_cash_count or 0) - expected_cash

		# Flag if variance exceeds threshold
		if abs(self.cash_variance) > 100:
			self.status = "Variance Flagged"
