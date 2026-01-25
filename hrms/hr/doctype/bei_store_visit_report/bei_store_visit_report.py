# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEIStoreVisitReport(Document):
	def before_insert(self):
		if not self.visited_by:
			self.visited_by = frappe.session.user

	def before_save(self):
		# Calculate overall score
		self.overall_score = (
			(self.score_funds or 0) +
			(self.score_stocks or 0) +
			(self.score_organization or 0) +
			(self.score_staffing or 0) +
			(self.score_coaching or 0)
		)

		# Determine grade based on score
		if self.overall_score >= 90:
			self.overall_grade = "EXCELLENT"
		elif self.overall_score >= 70:
			self.overall_grade = "SATISFACTORY"
		else:
			self.overall_grade = "NEEDS IMPROVEMENT"
