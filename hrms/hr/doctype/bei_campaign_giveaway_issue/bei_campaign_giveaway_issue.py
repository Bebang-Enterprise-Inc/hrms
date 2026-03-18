from __future__ import annotations

import frappe
from frappe.model.document import Document


class BEICampaignGiveawayIssue(Document):
	def before_insert(self):
		if not self.issued_by:
			self.issued_by = frappe.session.user

	def validate(self):
		if not self.campaign:
			frappe.throw("Campaign is required.")
		if not self.source_location:
			frappe.throw("Source location is required.")
		if not self.item_code:
			frappe.throw("Item code is required.")
		if float(self.quantity or 0) <= 0:
			frappe.throw("Issued quantity must be greater than 0.")
		self.actual_total_cost = round(float(self.quantity or 0) * float(self.actual_unit_cost or 0), 2)
		if not self.finance_expense_account:
			self.finance_expense_account = "6005001 - MARKETING GIVEAWAYS"
