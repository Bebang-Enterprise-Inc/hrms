import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BEIStatementofAccount(Document):
	def validate(self):
		self.calculate_totals()
		if not self.store_type and self.store:
			self.store_type = frappe.db.get_value("BEI Store Type", {"store": self.store}, "store_type") or ""

	def calculate_totals(self):
		"""Sum all line item amounts."""
		self.total_billings = sum(flt(item.amount) for item in self.line_items)
		# total_payments would come from payment records — placeholder for now
		if not self.total_payments:
			self.total_payments = 0
		self.balance_due = flt(self.total_billings - flt(self.total_payments), 2)

	def before_submit(self):
		"""Mark as Pending Review on submit."""
		self.status = "Pending Review"

	def before_cancel(self):
		self.status = "Cancelled"
