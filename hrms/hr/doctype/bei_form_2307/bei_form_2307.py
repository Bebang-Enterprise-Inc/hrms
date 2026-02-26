# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from hrms.api.tax import ATC_EWT_RATES, _parse_atc_code


class BEIForm2307(Document):

	def validate(self):
		"""Verify EWT rate matches BIR schedule for the selected ATC code."""
		atc = _parse_atc_code(self.atc_code)
		if not atc:
			frappe.throw(_("ATC Code is required"))

		expected_rate = ATC_EWT_RATES.get(atc)
		if expected_rate is None:
			frappe.throw(_("Unknown ATC code: {0}").format(atc))

		# Auto-set rate if blank
		if not self.ewt_rate:
			self.ewt_rate = expected_rate

		# Validate rate matches BIR schedule
		if flt(self.ewt_rate, 2) != flt(expected_rate, 2):
			frappe.throw(
				_("EWT Rate {0}% does not match BIR schedule for {1} (expected {2}%)").format(
					self.ewt_rate, atc, expected_rate
				)
			)

		# Auto-calculate ewt_amount
		if self.gross_amount and self.ewt_rate:
			self.ewt_amount = flt(self.gross_amount) * flt(self.ewt_rate) / 100.0

	def on_submit(self):
		"""Transition to For Review status on submit (MEMORY #22: set via flags)."""
		self.flags.ignore_permissions = True
		frappe.db.set_value("BEI Form 2307", self.name, "status", "For Review")
		self.status = "For Review"

	def on_cancel(self):
		"""Set status to Cancelled on cancel."""
		frappe.db.set_value("BEI Form 2307", self.name, "status", "Cancelled")
		self.status = "Cancelled"
