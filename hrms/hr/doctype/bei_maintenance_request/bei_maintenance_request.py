# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today


class BEIMaintenanceRequest(Document):
	def before_insert(self):
		if not self.reported_by:
			self.reported_by = frappe.session.user
		if not self.reported_at:
			self.reported_at = now_datetime()

	def before_save(self):
		self.modified_by = frappe.session.user
		self.modified_at = now_datetime()

	def after_insert(self):
		"""Send notifications for new maintenance requests."""
		self.send_notification()

	def on_update(self):
		"""Send notifications on status changes."""
		if self.has_value_changed("status"):
			self.send_status_notification()

	def send_notification(self):
		"""Send notification to Projects team for new requests."""
		# TODO: Implement notification to Daniel and Projects team
		# Based on priority:
		# - Urgent: Push + SMS to Daniel + Area Supervisor
		# - High/Normal: Push + Email to Daniel
		pass

	def send_status_notification(self):
		"""Send notification when status changes."""
		# Notify store manager when work is assigned or completed
		pass

	@frappe.whitelist()
	def assign_to_user(self, user, scheduled_date=None, estimated_cost=None):
		"""Assign maintenance request to internal user."""
		self.assigned_to = user
		self.status = "Assigned"
		if scheduled_date:
			self.scheduled_date = scheduled_date
		if estimated_cost:
			self.estimated_cost = estimated_cost
		self.save()
		return {"status": "success", "message": _("Request assigned to {0}").format(user)}

	@frappe.whitelist()
	def assign_to_vendor(self, vendor, scheduled_date=None, estimated_cost=None):
		"""Assign maintenance request to external vendor."""
		self.vendor = vendor
		self.status = "Assigned"
		if scheduled_date:
			self.scheduled_date = scheduled_date
		if estimated_cost:
			self.estimated_cost = estimated_cost
		self.save()
		return {"status": "success", "message": _("Request assigned to vendor: {0}").format(vendor)}

	@frappe.whitelist()
	def mark_in_progress(self):
		"""Mark request as in progress."""
		self.status = "In Progress"
		self.save()
		return {"status": "success"}

	@frappe.whitelist()
	def cancel_request(self, reason):
		"""Cancel maintenance request."""
		self.status = "Cancelled"
		self.add_comment("Comment", _("Cancelled: {0}").format(reason))
		self.save()
		return {"status": "success"}


@frappe.whitelist()
def get_open_requests_for_store(store):
	"""Get all open maintenance requests for a store."""
	return frappe.get_all(
		"BEI Maintenance Request",
		filters={
			"store": store,
			"status": ["in", ["Open", "Assigned", "In Progress"]]
		},
		fields=["name", "issue_category", "priority", "status", "scheduled_date", "description"]
	)


@frappe.whitelist()
def get_scheduled_maintenance_today(store):
	"""Check if store has scheduled maintenance today."""
	return frappe.db.exists(
		"BEI Maintenance Request",
		{
			"store": store,
			"scheduled_date": today(),
			"status": ["in", ["Assigned", "In Progress"]]
		}
	)
