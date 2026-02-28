# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, nowdate
from markupsafe import escape as html_escape
from hrms.utils.bei_config import get_company

VAT_RATE = 0.12

# GL account mapping by account_number (canonical first, legacy fallback second)
FEE_TO_ACCOUNT_NUMBERS = {
	"royalty_fee": ("4000003", "4000301"),
	"marketing_fee": ("4000006", "4000302"),
	"management_fee": ("4000004", "4000303"),
	"ecommerce_fee": ("4000304",),
	"delivery_fee": ("4000305",),
	"logistics_fee": ("4000306",),
}

# Fees where VAT is included in the amount and must be separated for GL posting
VAT_INCLUSIVE_FEES = {"royalty_fee", "management_fee"}

AR_ACCOUNT_NUMBERS = ("1103101",)
VAT_ACCOUNT_NUMBERS = ("2102205",)
FRANCHISE_INCOME_ACCOUNT_NUMBERS = ("4000300",)

NAMING_SERIES = {
	"Delivery": "BILL-DL-.YYYY.-.#####",
}
DEFAULT_NAMING_SERIES = "BILL-MF-.YYYY.-.#####"


def _get_account_by_number(account_number, company=None):
	"""Get full Frappe account name from account_number."""
	return frappe.db.get_value(
		"Account",
		{"account_number": str(account_number), "company": company or get_company()},
		"name",
	)


def _resolve_account_name(account_numbers, label, company=None):
	"""Resolve an account_name from canonical/legacy account numbers."""
	company_name = company or get_company()
	for account_number in account_numbers:
		account_name = _get_account_by_number(account_number, company=company_name)
		if account_name:
			return account_name

	expected_codes = ", ".join(str(code) for code in account_numbers)
	frappe.throw(
		_(
			"Missing GL Account for {0}. Configure Account.account_number in company {1}: {2}"
		).format(label, company_name, expected_codes),
		frappe.ValidationError,
	)


class BEIBillingSchedule(Document):
	def validate(self):
		"""Calculate all fees based on store type."""
		self.naming_series = NAMING_SERIES.get(self.billing_type, DEFAULT_NAMING_SERIES)
		self.calculate_fees()
		self.calculate_line_items()
		self.calculate_totals()

	def before_save(self):
		"""Create GL entries when billing transitions to Approved status."""
		prev = self.get_doc_before_save()
		if self.status == "Approved" and prev and prev.status != "Approved":
			self._create_gl_entries()

	def _create_gl_entries(self):
		"""Create a Journal Entry to record billing in General Ledger.

		Triggered when status changes to Approved (C-01 fix: use before_save
		instead of on_submit since DocType is not submittable).
		"""
		je = frappe.new_doc("Journal Entry")
		je.posting_date = nowdate()
		je.voucher_type = "Journal Entry"
		je.company = get_company()
		je.user_remark = f"Auto-generated from {self.name}"

		total_revenue = 0
		total_vat = 0

		for fee_field, account_numbers in FEE_TO_ACCOUNT_NUMBERS.items():
			amount = flt(getattr(self, fee_field, 0))
			if amount <= 0:
				continue

			account = _resolve_account_name(
				account_numbers,
				label=fee_field,
				company=je.company,
			)

			if fee_field in VAT_INCLUSIVE_FEES:
				base_amount = flt(amount / (1 + VAT_RATE), 2)
				vat_amount = flt(amount - base_amount, 2)
				total_vat += vat_amount
				credit_amount = base_amount
			else:
				credit_amount = amount

			total_revenue += credit_amount
			je.append("accounts", {
				"account": account,
				"credit_in_account_currency": credit_amount,
				"reference_type": "BEI Billing Schedule",
				"reference_name": self.name,
			})

		# Add handling_fee for delivery billings (franchise markup)
		if self.billing_type == "Delivery" and flt(self.handling_fee) > 0:
			franchise_income_account = _resolve_account_name(
				FRANCHISE_INCOME_ACCOUNT_NUMBERS,
				label="franchise_income",
				company=je.company,
			)
			total_revenue += flt(self.handling_fee)
			je.append("accounts", {
				"account": franchise_income_account,
				"credit_in_account_currency": flt(self.handling_fee),
				"reference_type": "BEI Billing Schedule",
				"reference_name": self.name,
			})

		if total_vat > 0:
			vat_account = _resolve_account_name(
				VAT_ACCOUNT_NUMBERS,
				label="output_vat",
				company=je.company,
			)
			je.append("accounts", {
				"account": vat_account,
				"credit_in_account_currency": total_vat,
			})

		# Debit AR for total (C-02 fix: removed invalid party_type "Department")
		total_debit = total_revenue + total_vat
		if total_debit > 0:
			ar_account = _resolve_account_name(
				AR_ACCOUNT_NUMBERS,
				label="accounts_receivable",
				company=je.company,
			)
			je.append("accounts", {
				"account": ar_account,
				"debit_in_account_currency": total_debit,
				"against_voucher_type": "BEI Billing Schedule",
				"against_voucher": self.name,
				"user_remark": f"AR for {self.store}",
			})

		if je.accounts:
			# C-03 fix: re-raise on failure to prevent billing without GL
			je.insert(ignore_permissions=True)
			je.submit()
			self.add_comment("Info", f"GL Entry created: {je.name}")

	def calculate_fees(self):
		"""Calculate all fees based on store type and billing type."""
		# Delivery billings have fees set by _create_delivery_billing()
		if self.billing_type == "Delivery":
			return

		# C-04/C-05 fix: Monthly fees should NOT include delivery/logistics
		# Those are billed per-delivery via Stream B
		self.delivery_fee = 0
		self.logistics_fee = 0
		self.goods_value = 0
		self.handling_fee = 0

		# Get store type from BEI Store Type master if not set
		if not self.store_type and self.store:
			self.store_type = frappe.db.get_value(
				"BEI Store Type", {"store": self.store}, "store_type"
			) or self.store_type

		gross = flt(self.gross_sales)
		net = flt(self.net_sales)
		web = flt(self.website_sales)

		# eCommerce fee: 4% of website sales (same for all store types)
		self.ecommerce_fee = web * 0.04

		if self.store_type == "JV":
			self.royalty_fee = 0
			self.management_fee = 0
			self.marketing_fee = net * 0.05  # JV uses NET sales

		elif self.store_type == "Managed Franchise":
			self.royalty_fee = gross * 0.07 * (1 + VAT_RATE)
			self.management_fee = gross * 0.025 * (1 + VAT_RATE)
			self.marketing_fee = gross * 0.05

		elif self.store_type == "Full Franchise":
			self.royalty_fee = gross * 0.07 * (1 + VAT_RATE)
			self.management_fee = 0
			self.marketing_fee = gross * 0.05

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
			self.preventive_maintenance or 0,
			self.goods_value or 0,
			self.handling_fee or 0,
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
		fee_labels = [
			("royalty_fee", "Royalty Fee"),
			("management_fee", "Management Fee"),
			("marketing_fee", "Marketing Fee"),
			("ecommerce_fee", "eCommerce Fee"),
			("delivery_fee", "Delivery Fee"),
			("logistics_fee", "Logistics Fee"),
			("repairs_maintenance", "Repairs & Maintenance"),
			("preventive_maintenance", "Preventive Maintenance"),
		]
		rows = [
			(label, getattr(self, field))
			for field, label in fee_labels
			if getattr(self, field)
		]

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
