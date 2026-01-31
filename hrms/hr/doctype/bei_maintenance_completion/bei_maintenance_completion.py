# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today


class BEIMaintenanceCompletion(Document):
	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		if not self.submitted_at:
			self.submitted_at = now_datetime()

	def before_save(self):
		self.update_verification_timestamp()

	def validate(self):
		self.validate_follow_up()

	def after_insert(self):
		"""Link completion to maintenance request and update status."""
		self.update_maintenance_request("Completed")

	def on_update(self):
		"""Update maintenance request when verification status changes."""
		if self.has_value_changed("status"):
			if self.status == "Verified":
				self.update_maintenance_request("Verified")

	def update_verification_timestamp(self):
		"""Set verification timestamp when verified."""
		if self.verified_by_store and not self.verified_at:
			self.verified_at = now_datetime()
			self.verified_by = frappe.session.user
			self.status = "Verified"

	def validate_follow_up(self):
		"""Require follow-up notes if follow-up is needed."""
		if self.follow_up_needed and not self.follow_up_notes:
			frappe.throw(_("Follow-up notes are required when follow-up is needed"))

	def update_maintenance_request(self, status):
		"""Update the linked maintenance request."""
		if self.maintenance_request:
			request = frappe.get_doc("BEI Maintenance Request", self.maintenance_request)
			request.status = status
			request.completion = self.name
			request.resolved_date = self.completion_date
			request.save()

	@frappe.whitelist()
	def verify_completion(self, notes=None):
		"""Store staff verifies the completion."""
		self.verified_by_store = 1
		self.verified_at = now_datetime()
		self.verified_by = frappe.session.user
		self.status = "Verified"
		if notes:
			self.verification_notes = notes
		self.save()
		return {"status": "success", "message": _("Maintenance completion verified")}

	@frappe.whitelist()
	def reject_completion(self, notes):
		"""Store staff rejects the completion."""
		self.status = "Rejected"
		self.verification_notes = notes
		self.verified_at = now_datetime()
		self.verified_by = frappe.session.user
		self.save()

		# Update maintenance request back to In Progress
		if self.maintenance_request:
			request = frappe.get_doc("BEI Maintenance Request", self.maintenance_request)
			request.status = "In Progress"
			request.add_comment("Comment", _("Completion rejected: {0}").format(notes))
			request.save()

		return {"status": "success", "message": _("Maintenance completion rejected")}


@frappe.whitelist()
def get_pending_verifications_for_store(store):
	"""Get all pending maintenance verifications for a store."""
	return frappe.get_all(
		"BEI Maintenance Completion",
		filters={
			"store": store,
			"status": "Pending Verification"
		},
		fields=["name", "maintenance_request", "completion_date", "technician_name", "work_description"]
	)


@frappe.whitelist()
def check_maintenance_for_closing_report(store, report_date):
	"""Check if there's maintenance to verify for the closing report."""
	# Get completed maintenance requests for today that need verification
	completions = frappe.get_all(
		"BEI Maintenance Completion",
		filters={
			"store": store,
			"completion_date": report_date,
			"status": "Pending Verification"
		},
		fields=["name", "maintenance_request", "technician_name", "work_description", "resolution_status"]
	)

	return {
		"has_maintenance": len(completions) > 0,
		"completions": completions
	}
