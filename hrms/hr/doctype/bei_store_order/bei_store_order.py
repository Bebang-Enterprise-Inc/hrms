# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, nowdate


class BEIStoreOrder(Document):
	def before_save(self):
		# Auto-set delivery date to next day if not set
		if not self.delivery_date:
			self.delivery_date = add_days(self.order_date or nowdate(), 1)

	def validate(self):
		self.validate_items()
		self.compute_deviations()
		self.set_approval_status()

	def validate_items(self):
		if not self.items:
			frappe.throw("At least one item is required")
		for item in self.items:
			if item.qty_requested <= 0:
				frappe.throw(f"Quantity for {item.item_code} must be greater than 0")

	def compute_deviations(self):
		for item in self.items:
			baseline = item.recommended_qty if item.recommended_qty is not None else item.suggested_qty
			baseline = float(baseline or 0)
			if baseline and baseline > 0:
				item.deviation_pct = round(((item.qty_requested - baseline) / baseline) * 100, 1)
			else:
				item.deviation_pct = 0.0
			item.is_edited = 1 if item.qty_requested != baseline else 0

	def set_approval_status(self):
		# Only auto-set status when document is in Draft or Pending Approval
		if self.status not in ("Draft", "Pending Approval"):
			return

		# Bulk orders always require manual approval
		if self.is_bulk_order:
			self.status = "Pending Approval"
			return

		# If any line was edited from recommendation baseline (including 0 -> >0), require approval.
		has_deviation = any(item.is_edited == 1 or item.deviation_pct != 0.0 for item in self.items)

		if has_deviation:
			self.status = "Pending Approval"
		else:
			self.status = "Approved"

	def before_submit(self):
		self.submitted_by = frappe.session.user
		if self.status == "Draft":
			self.status = "Pending Approval"
