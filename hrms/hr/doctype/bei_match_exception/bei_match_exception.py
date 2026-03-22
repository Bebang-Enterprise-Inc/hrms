# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Configurable approver mapping by tier
EXCEPTION_APPROVERS = {
	"CPO": "mae@bebang.ph",
	"CPO+CFO": "mae@bebang.ph",
	"CPO+CEO": "mae@bebang.ph",
	"CFO": "butch@bebang.ph",
	"CEO": "sam@bebang.ph",
}

# Amount thresholds for tier assignment (PHP)
TIER_THRESHOLDS = {
	"CPO": 500000,  # < 500K
	"CFO": 1000000,  # 500K to < 1M
	# CEO: >= 1M
}


def get_approval_tier(po_amount):
	"""Determine approval tier based on PO amount.

	< 500K -> CPO (Mae)
	500K to < 1M -> CPO+CFO
	>= 1M -> CPO+CEO
	"""
	amount = flt(po_amount)
	if amount < TIER_THRESHOLDS["CPO"]:
		return "CPO"
	elif amount < TIER_THRESHOLDS["CFO"]:
		return "CPO+CFO"
	else:
		return "CPO+CEO"


def get_tier_status(tier):
	"""Return the pending status string for a given tier."""
	# Dual-tier flows always start with CPO review before escalation.
	if tier in {"CPO+CFO", "CPO+CEO"}:
		return "Pending CPO"
	return f"Pending {tier}"


class BEIMatchException(Document):
	def before_insert(self):
		# Auto-set tier and approver based on PO amount
		if self.purchase_order and not self.approval_tier:
			po_amount = frappe.db.get_value("BEI Purchase Order", self.purchase_order, "grand_total")
			self.po_amount = flt(po_amount)
			self.approval_tier = get_approval_tier(self.po_amount)

		if self.approval_tier and not self.approver:
			self.approver = EXCEPTION_APPROVERS.get(self.approval_tier)

		if not self.status:
			self.status = get_tier_status(self.approval_tier or "CPO")

		if not self.requested_by:
			self.requested_by = frappe.session.user

		if not self.requested_date:
			self.requested_date = now_datetime()

		if not self.approver_status:
			self.approver_status = "Pending"
