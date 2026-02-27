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
		"""Send notification to projects/ops channels for new maintenance requests."""
		lines = [
			f"*Store:* {self.store or '-'}",
			f"*Priority:* {self.priority or '-'}",
			f"*Category:* {self.issue_category or '-'}",
			f"*Impact:* {self.impact_on_operations or '-'}",
		]
		if self.description:
			lines.append(f"*Issue:* {self.description}")
		_notify_maintenance_event(
			title=f"*New Maintenance Request*\\n{self.name}",
			lines=lines,
			store=self.store,
		)

	def send_status_notification(self):
		"""Send notification when request status changes."""
		lines = [
			f"*Store:* {self.store or '-'}",
			f"*Priority:* {self.priority or '-'}",
			f"*Status:* {self.status or '-'}",
		]
		if self.assigned_to:
			lines.append(f"*Assigned To:* {self.assigned_to}")
		if self.vendor:
			lines.append(f"*Vendor:* {self.vendor}")
		if self.scheduled_date:
			lines.append(f"*Scheduled Date:* {self.scheduled_date}")
		_notify_maintenance_event(
			title=f"*Maintenance Status Updated*\\n{self.name}",
			lines=lines,
			store=self.store,
		)

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


def _notify_maintenance_event(title, lines, store=None):
	"""Best-effort Google Chat notification for maintenance lifecycle events."""
	try:
		from hrms.api.google_chat import send_message_to_space
		from hrms.utils.bei_config import SPACE_NOTIFICATIONS, get_chat_space

		spaces = []
		store_space = _resolve_store_chat_space(store)
		if store_space:
			spaces.append(store_space)

		default_space = get_chat_space(SPACE_NOTIFICATIONS)
		if default_space:
			spaces.append(default_space)

		if not spaces:
			return

		message = title
		if lines:
			message = f"{title}\\n\\n" + "\\n".join(lines)

		for space in dict.fromkeys(spaces):
			send_message_to_space(space, message)
	except Exception as e:
		frappe.log_error(
			title="Maintenance Notification Error",
			message=f"store={store}, title={title}, error={str(e)[:300]}",
		)


def _resolve_store_chat_space(store):
	"""Resolve per-store Google Chat space from Warehouse custom field."""
	if not store:
		return None
	try:
		return frappe.db.get_value("Warehouse", store, "custom_gchat_space")
	except Exception:
		return None
