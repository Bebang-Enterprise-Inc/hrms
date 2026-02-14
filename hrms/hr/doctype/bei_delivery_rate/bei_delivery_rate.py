import frappe
from frappe.model.document import Document
from frappe import _


class BEIDeliveryRate(Document):
	def validate(self):
		if self.status == "Active":
			existing = frappe.db.exists("BEI Delivery Rate", {
				"store": self.store,
				"cargo_type": self.cargo_type,
				"status": "Active",
				"name": ["!=", self.name]
			})
			if existing:
				frappe.throw(
					_("An active rate already exists for {0} - {1}: {2}").format(
						self.store, self.cargo_type, existing
					)
				)

	def before_save(self):
		if not self.set_by:
			self.set_by = frappe.session.user
			user_roles = frappe.get_roles(frappe.session.user)
			if "Accounts Manager" in user_roles:
				self.set_by_role = "Finance"
			elif "Supply Chain Manager" in user_roles:
				self.set_by_role = "Supply Chain"
