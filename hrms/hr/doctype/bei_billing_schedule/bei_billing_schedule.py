# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt
from markupsafe import escape as html_escape


class BEIBillingSchedule(Document):
	def validate(self):
		"""Calculate all fees based on store type."""
		self.calculate_fees()
		self.calculate_line_items()
		self.calculate_totals()

	def calculate_fees(self):
		"""Calculate fees based on store type and sales data."""
		VAT_RATE = 0.12

		# Get store type from BEI Store Type master if not set
		if not self.store_type and self.store:
			store_type_doc = frappe.db.get_value(
				"BEI Store Type",
				{"store": self.store},
				"store_type"
			)
			if store_type_doc:
				self.store_type = store_type_doc

		# Billing matrix by store type
		if self.store_type == "JV":
			# JV Stores
			self.royalty_fee = 0
			self.management_fee = 0

			# Marketing: 5% of NET sales (not gross!)
			self.marketing_fee = self.net_sales * 0.05 if self.net_sales else 0

			# eCommerce: 5% of online sales
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: Cost + 12% VAT (no 8% markup for JV)
			if self.delivery_cost:
				self.delivery_fee = self.delivery_cost * (1 + VAT_RATE)

			# Logistics: Cost + 12% VAT (no 8% markup for JV)
			if self.logistics_cost:
				self.logistics_fee = self.logistics_cost * (1 + VAT_RATE)

		elif self.store_type == "Managed Franchise":
			# Managed Franchise
			# Royalty: 7% gross + 12% VAT
			self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

			# Management: 2.5% gross + 12% VAT
			self.management_fee = self.gross_sales * 0.025 * (1 + VAT_RATE) if self.gross_sales else 0

			# Marketing: 5% gross
			self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

			# eCommerce: 5% online
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: (Cost + 12% VAT) + 8%
			if self.delivery_cost:
				base_delivery = self.delivery_cost * (1 + VAT_RATE)
				self.delivery_fee = base_delivery * 1.08

			# Logistics: (Cost + 12% VAT) + 8%
			if self.logistics_cost:
				base_logistics = self.logistics_cost * (1 + VAT_RATE)
				self.logistics_fee = base_logistics * 1.08

		elif self.store_type == "Full Franchise":
			# Full Franchise
			# Royalty: 7% gross + 12% VAT
			self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

			# Management: N/A
			self.management_fee = 0

			# Marketing: 5% gross
			self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

			# eCommerce: 5% online
			self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

			# Deliveries: (Cost + 12% VAT) + 8%
			if self.delivery_cost:
				base_delivery = self.delivery_cost * (1 + VAT_RATE)
				self.delivery_fee = base_delivery * 1.08

			# Logistics: (Cost + 12% VAT) + 8%
			if self.logistics_cost:
				base_logistics = self.logistics_cost * (1 + VAT_RATE)
				self.logistics_fee = base_logistics * 1.08

	def calculate_line_items(self):
		"""Update line item amounts."""
		for item in self.line_items:
			item.amount = flt(item.quantity or 0) * flt(item.unit_price or 0)

	def calculate_totals(self):
		"""Calculate subtotal, VAT, and total."""
		# Sum all fees
		fees = [
			self.royalty_fee or 0,
			self.management_fee or 0,
			self.marketing_fee or 0,
			self.ecommerce_fee or 0,
			self.delivery_fee or 0,
			self.logistics_fee or 0,
			self.repairs_maintenance or 0,
			self.preventive_maintenance or 0
		]

		# Add line items
		for item in self.line_items:
			fees.append(item.amount or 0)

		self.subtotal = sum(fees)

		# VAT already included in most fees, but calculate for line items
		vat_amount = 0
		for item in self.line_items:
			if item.vat_applicable:
				vat_amount += (item.amount or 0) * 0.12

		self.vat_amount = vat_amount
		self.total_amount = self.subtotal + self.vat_amount
		self.balance_due = flt(self.total_amount - flt(self.amount_paid or 0), 2)

	def send_to_store(self):
		"""Generate and send Statement of Account to store via email."""
		if self.status not in ("Draft", "Sent"):
			frappe.throw(_("Can only send billing statements with Draft or Sent status"))

		# Build the billing breakdown HTML
		rows = []
		if self.royalty_fee:
			rows.append(("Royalty Fee", self.royalty_fee))
		if self.management_fee:
			rows.append(("Management Fee", self.management_fee))
		if self.marketing_fee:
			rows.append(("Marketing Fee", self.marketing_fee))
		if self.ecommerce_fee:
			rows.append(("eCommerce Fee", self.ecommerce_fee))
		if self.delivery_fee:
			rows.append(("Delivery Fee", self.delivery_fee))
		if self.logistics_fee:
			rows.append(("Logistics Fee", self.logistics_fee))
		if self.repairs_maintenance:
			rows.append(("Repairs & Maintenance", self.repairs_maintenance))
		if self.preventive_maintenance:
			rows.append(("Preventive Maintenance", self.preventive_maintenance))

		for item in self.line_items:
			if item.amount:
				rows.append((item.description, item.amount))

		fee_rows_html = "".join(
			f"<tr><td>{html_escape(str(desc))}</td><td style='text-align:right'>₱{flt(amt):,.2f}</td></tr>"
			for desc, amt in rows
		)

		message = f"""
		<h2>Statement of Account</h2>
		<p><strong>Billing Period:</strong> {self.billing_period}</p>
		<p><strong>Store:</strong> {self.store}</p>
		<p><strong>Store Type:</strong> {self.store_type}</p>

		<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse; width:100%">
			<thead>
				<tr style="background:#f5f5f5">
					<th style="text-align:left">Description</th>
					<th style="text-align:right">Amount</th>
				</tr>
			</thead>
			<tbody>
				{fee_rows_html}
			</tbody>
			<tfoot>
				<tr><td><strong>Subtotal</strong></td><td style="text-align:right"><strong>₱{self.subtotal:,.2f}</strong></td></tr>
				<tr><td>VAT (on line items)</td><td style="text-align:right">₱{self.vat_amount:,.2f}</td></tr>
				<tr style="background:#f5f5f5"><td><strong>Total Amount Due</strong></td><td style="text-align:right"><strong>₱{self.total_amount:,.2f}</strong></td></tr>
			</tfoot>
		</table>

		<p style="margin-top:16px"><em>This is a system-generated statement from Bebang ERP.</em></p>
		"""

		# Get store manager email from Department
		recipients = []
		dept = frappe.db.get_value("Department", self.store, "department_email")
		if dept:
			recipients.append(dept)

		# Also notify Accounts Manager role users
		accounts_managers = frappe.get_all(
			"Has Role",
			filters={"role": "Accounts Manager", "parenttype": "User"},
			fields=["parent"],
		)
		for user in accounts_managers:
			if user.parent not in recipients and user.parent != "Administrator":
				recipients.append(user.parent)

		if recipients:
			try:
				frappe.sendmail(
					recipients=recipients,
					subject=_("Billing Statement: {0} - {1}").format(
						self.store, self.billing_period
					),
					message=message,
				)
			except Exception:
				frappe.log_error(
					f"Failed to send billing statement email for {self.name}",
					"Billing Statement Email Error",
				)

		self.status = "Sent"
		self.sent_on = frappe.utils.now()
		self.save()

		return {
			"success": True,
			"message": _("Billing statement sent to {0}").format(self.store),
			"recipients": recipients,
		}
