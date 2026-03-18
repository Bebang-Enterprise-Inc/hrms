from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BEICampaignGiveawayException(Document):
	def before_insert(self):
		if not self.created_by:
			self.created_by = frappe.session.user

	def validate(self):
		self.requested_quantity = flt(self.requested_quantity or 0, 3)
		self.attempted_value = flt(self.attempted_value or 0, 2)
		if self.status == "Resolved" and not self.resolved_by:
			self.resolved_by = frappe.session.user
