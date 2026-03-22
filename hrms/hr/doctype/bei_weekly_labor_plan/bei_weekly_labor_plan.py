# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days


class BEIWeeklyLaborPlan(Document):
	def before_insert(self):
		if not self.planned_by:
			self.planned_by = frappe.session.user

		# Auto-calculate week end date if not set
		if self.week_start_date and not self.week_end_date:
			self.week_end_date = add_days(self.week_start_date, 6)

	def before_save(self):
		# Calculate total hours from shifts
		total_hours = 0
		for shift in self.shifts:
			if shift.hours:
				total_hours += shift.hours
		self.total_hours = total_hours
