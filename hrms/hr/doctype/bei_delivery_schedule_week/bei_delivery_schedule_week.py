# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIDeliveryScheduleWeek(Document):
	def validate(self):
		# Ensure week_start is a Monday
		if self.week_start:
			from frappe.utils import getdate
			d = getdate(self.week_start)
			if d.weekday() != 0:  # 0 = Monday
				frappe.throw(_("Week Start must be a Monday"))

	def before_save(self):
		if self.published and not self.published_at:
			self.published_by = frappe.session.user
			self.published_at = now_datetime()
