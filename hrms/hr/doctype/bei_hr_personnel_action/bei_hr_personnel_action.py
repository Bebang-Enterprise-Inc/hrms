# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class BEIHRPersonnelAction(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		if not self.requested_on:
			self.requested_on = now_datetime()
		if not self.status:
			self.status = "Pending HR Approval"

	def validate(self):
		self._sync_employee_snapshot()
		self._compute_compensation_totals()

	def _sync_employee_snapshot(self):
		if not self.employee or not frappe.db.exists("Employee", self.employee):
			return

		employee = frappe.get_cached_doc("Employee", self.employee)
		self.employee_name = employee.employee_name
		self.from_branch = employee.branch
		self.from_department = employee.department
		self.from_designation = employee.designation
		self.from_reports_to = employee.reports_to

	def _compute_compensation_totals(self):
		total_old = 0.0
		total_new = 0.0
		for row in self.get("compensation_changes") or []:
			if not getattr(row, "include_in_total", 1):
				continue
			total_old += flt(getattr(row, "from_amount", 0))
			total_new += flt(getattr(row, "to_amount", 0))
		self.total_compensation_old = total_old
		self.total_compensation_new = total_new
