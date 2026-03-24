"""Leave Application hooks for BEI overtime-leave mutual exclusion.

Policy: CEO decision 2026-03-24
- Cannot file leave on dates with approved overtime
- When leave is approved, auto-reject pending OT on same dates
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate


# OT statuses that block leave filing (only finalized, not pending)
OT_BLOCKING_STATUSES = {"Approved", "Payroll Locked", "Bridged"}

# OT statuses that get auto-rejected when leave is approved
OT_PENDING_STATUSES = {
	"Pending Review",
	"Pending Approval",
	"Needs Clarification",
	"Clarification Submitted",
}


def validate_no_overtime_conflict(doc, method=None):
	"""Prevent leave filing on dates with approved/locked/bridged overtime.

	P2.5-2: Only blocks on finalized OT (Approved/Locked/Bridged).
	Does NOT block on Pending OT — supervisor may reject it.
	HARD BLOCKER: blocking on Pending would create a deadlock.
	"""
	# Check all saves, not just new applications
	cursor = getdate(doc.from_date)
	end = getdate(doc.to_date)
	while cursor <= end:
		ot_exists = frappe.db.exists("BEI Overtime Request", {
			"employee": doc.employee,
			"attendance_date": str(cursor),
			"overtime_status": ["in", list(OT_BLOCKING_STATUSES)],
		})
		if ot_exists:
			frappe.throw(
				_("Cannot file leave on {0} — approved overtime exists for that date. Cancel the OT first.").format(
					frappe.utils.formatdate(cursor)
				)
			)
		cursor = add_days(cursor, 1)


def on_leave_status_change(doc, method=None):
	"""Auto-reject pending OT when leave is approved.

	P2.5-3: When leave changes to Approved, any pending OT for the same
	employee on overlapping dates is auto-rejected with an audit note.
	"""
	if doc.status != "Approved":
		return

	cursor = getdate(doc.from_date)
	end = getdate(doc.to_date)
	while cursor <= end:
		pending_ots = frappe.get_all("BEI Overtime Request", filters={
			"employee": doc.employee,
			"attendance_date": str(cursor),
			"overtime_status": ["in", list(OT_PENDING_STATUSES)],
		}, pluck="name")
		for ot_name in pending_ots:
			frappe.db.set_value("BEI Overtime Request", ot_name, {
				"overtime_status": "Rejected",
				"review_note": f"Auto-rejected: leave approved for this date ({doc.leave_type}, {doc.name})",
			})
		cursor = add_days(cursor, 1)
