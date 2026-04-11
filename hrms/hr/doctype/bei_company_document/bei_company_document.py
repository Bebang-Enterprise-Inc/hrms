# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BEICompanyDocument(Document):
	def validate(self):
		# S181: at least one of `file` (Frappe Attach) or `drive_file_url` (Google
		# Drive URL) must be set. BD can upload directly to Frappe OR link to the
		# existing Google Drive copy; both are allowed (e.g., upload the scan AND
		# link to the authoritative Drive version). This mirrors the frontend
		# Save-button guard in bei-tasks so UI and backend stay aligned.
		if not self.file and not self.drive_file_url:
			frappe.throw(
				f"Document '{self.document_name or self.document_type}' must have "
				f"either an uploaded File or a Google Drive URL (or both)."
			)

		# Light URL shape check on the Drive link — reject non-Google URLs so BD
		# cannot silently paste a WhatsApp/Dropbox link that everyone else would
		# have to chase down later.
		if self.drive_file_url and not (
			self.drive_file_url.startswith("https://drive.google.com/")
			or self.drive_file_url.startswith("https://docs.google.com/")
		):
			frappe.throw(
				f"Google Drive URL for '{self.document_name or self.document_type}' "
				f"must start with https://drive.google.com/ or https://docs.google.com/"
			)
