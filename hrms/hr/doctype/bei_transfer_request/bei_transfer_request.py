# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, getdate, now_datetime


class BEITransferRequest(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		if not self.requested_on:
			self.requested_on = now_datetime()
		if not self.current_stage:
			self.current_stage = "Pending Area Approval"
		if not self.stage_status:
			self.stage_status = "Pending"

	def validate(self):
		self._sync_employee_snapshot()
		self._validate_reliever_window()

	def _sync_employee_snapshot(self):
		if not self.employee or not frappe.db.exists("Employee", self.employee):
			return

		employee = frappe.get_cached_doc("Employee", self.employee)
		self.employee_name = employee.employee_name

		if not self.from_branch:
			self.from_branch = employee.branch
		if not self.from_department:
			self.from_department = employee.department
		if not self.from_designation:
			self.from_designation = employee.designation
		if not self.from_reports_to:
			self.from_reports_to = employee.reports_to

	def _validate_reliever_window(self):
		if not cint(self.is_reliever):
			self.reliever_days = None
			self.reliever_start_date = None
			self.reliever_end_date = None
			if not self.reliever_cleanup_status:
				self.reliever_cleanup_status = None
			return

		reliever_days = cint(self.reliever_days)
		if reliever_days <= 0:
			frappe.throw("Reliever days is required when reliever mode is enabled")

		start_date = getdate(self.effective_date)
		self.reliever_start_date = start_date
		self.reliever_end_date = getdate(add_to_date(start_date, days=reliever_days))
		if not self.reliever_cleanup_status:
			self.reliever_cleanup_status = "Pending"

