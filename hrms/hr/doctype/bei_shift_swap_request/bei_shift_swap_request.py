# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class BEIShiftSwapRequest(Document):
	def validate(self):
		if self.requester_employee and self.target_employee and self.requester_employee == self.target_employee:
			frappe.throw(_("Requester and target employee must be different."))

		if self.requester_shift_assignment and self.target_shift_assignment:
			if self.requester_shift_assignment == self.target_shift_assignment:
				frappe.throw(_("Requester and target shift assignments must be different."))

