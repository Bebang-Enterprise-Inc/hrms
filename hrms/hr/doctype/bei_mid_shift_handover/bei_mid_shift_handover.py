# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIMidShiftHandover(Document):
	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		if not self.submitted_at:
			self.submitted_at = now_datetime()

	def before_save(self):
		self.calculate_variance()
		self.update_status()

	def validate(self):
		self.validate_different_cashiers()
		self.validate_variance_explanation()

	def calculate_variance(self):
		"""Calculate variance between actual and expected cash."""
		self.variance = (self.cash_count or 0) - (self.expected_cash or 0)

	def update_status(self):
		"""Update status based on variance."""
		VARIANCE_THRESHOLD = 50

		if self.variance and abs(self.variance) > VARIANCE_THRESHOLD:
			self.status = "Variance Flagged"
		elif self.x_reading_photo and self.cash_count:
			self.status = "Submitted"

	def validate_different_cashiers(self):
		"""Ensure outgoing and incoming cashiers are different."""
		if self.outgoing_cashier == self.incoming_cashier:
			frappe.throw(_("Outgoing and incoming cashiers must be different"))

	def validate_variance_explanation(self):
		"""Require explanation if variance exceeds threshold."""
		VARIANCE_THRESHOLD = 50

		if self.variance and abs(self.variance) > VARIANCE_THRESHOLD:
			if not self.variance_explanation:
				frappe.throw(
					_("Variance explanation is required when variance exceeds ±₱{0}. "
					  "Current variance: ₱{1}").format(VARIANCE_THRESHOLD, self.variance)
				)

	def on_submit(self):
		"""Link to daily closing report if exists."""
		closing_report = frappe.db.get_value(
			"BEI Store Closing Report",
			{
				"store": self.store,
				"report_date": self.report_date,
				"docstatus": ["<", 2]
			},
			"name"
		)
		if closing_report:
			self.db_set("closing_report", closing_report)
