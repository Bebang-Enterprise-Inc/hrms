# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, now_datetime, nowdate

from hrms.utils.bei_config import get_company

# CEO approval threshold
CEO_APPROVAL_THRESHOLD = 1000000  # 1 Million PHP


def _get_account_by_code(account_number, company=None):
	"""Get full Frappe account name from account number.

	Frappe Account names are full strings like "1113000 - Petty Cash Fund - BEI",
	not bare codes. This helper looks up by account_number field.

	Returns the full account name or None if not found.
	"""
	if account_number is None:
		return None

	account_number = str(account_number).strip()
	if not account_number:
		return None

	return frappe.db.get_value(
		"Account",
		{"account_number": account_number, "company": company or get_company()},
		"name",
	)


def _resolve_account_by_codes(account_numbers, company=None):
	"""Resolve first available account by account_number."""
	for account_number in account_numbers:
		account_name = _get_account_by_code(account_number, company=company)
		if account_name:
			return account_name
	return None


class BEIPaymentRequest(Document):
	"""
	4-Level Approval Workflow:
	Level 1: Review (Document completeness, 3-way match verified)
	Level 2: Budget (Budget availability check)
	Level 3: CFO - Butch (Financial approval)
	Level 4: CEO (Only for new suppliers or amounts > 1M)
	"""

	def validate(self):
		self.populate_invoice_context()
		self.auto_populate_ewt_from_supplier()
		self.set_payment_request_no()
		self.check_ceo_requirement()
		self.load_supplier_bank_info()
		self.auto_assign_gl_account()

	def auto_populate_ewt_from_supplier(self):
		"""S099/C4: Auto-populate EWT rate from supplier master.

		- If supplier has ewt_exempt=1, clear ewt_applicable and ewt fields.
		- If supplier has default_ewt_rate, use it when ewt_rate is not set.
		- ewt_exempt and ewt_applicable cannot both be 1.
		"""
		if not self.supplier:
			return

		supplier_fields = frappe.db.get_value(
			"BEI Supplier", self.supplier,
			["ewt_applicable", "ewt_exempt", "default_ewt_rate"],
			as_dict=True,
		)
		if not supplier_fields:
			return

		# ewt_exempt overrides ewt_applicable
		if cint(supplier_fields.get("ewt_exempt")):
			self.ewt_applicable = 0
			self.ewt_rate = 0
			self.ewt_amount = 0
			return

		# Auto-populate ewt_rate from supplier default if not already set
		if cint(supplier_fields.get("ewt_applicable")) and not self.ewt_rate:
			supplier_rate = flt(supplier_fields.get("default_ewt_rate"))
			if supplier_rate > 0:
				self.ewt_rate = supplier_rate
			else:
				# Fall back to BEI Settings default
				from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
				settings = get_procurement_settings()
				self.ewt_rate = flt(settings.get("default_ewt_rate", 1))

		# Recalculate ewt_amount if rate was auto-set
		if flt(self.ewt_rate) > 0 and flt(self.payment_amount) > 0:
			self.ewt_amount = flt(flt(self.payment_amount) * flt(self.ewt_rate) / 100, 2)

	def populate_invoice_context(self):
		"""Backfill canonical vendor-invoice fields from the linked invoice."""
		if not self.invoice:
			return

		invoice = frappe.get_doc("BEI Invoice", self.invoice)

		if not self.supplier and invoice.supplier:
			self.supplier = invoice.supplier

		if not self.supplier_name:
			self.supplier_name = invoice.supplier_name or (
				frappe.db.get_value("BEI Supplier", self.supplier, "supplier_name") if self.supplier else None
			)

		if not self.purchase_order and invoice.purchase_order:
			self.purchase_order = invoice.purchase_order

		if not self.goods_receipt and invoice.goods_receipt:
			self.goods_receipt = invoice.goods_receipt

		if not self.payment_amount:
			self.payment_amount = flt(invoice.balance_due or invoice.grand_total, 2)

		if not self.rfp_type:
			self.rfp_type = "Vendor Invoice"

	def set_payment_request_no(self):
		"""Set payment request number from name if not already set."""
		if not self.payment_request_no and self.name:
			self.payment_request_no = self.name

	def after_insert(self):
		self.payment_request_no = self.name
		self.db_set("payment_request_no", self.name, update_modified=False)

	def check_ceo_requirement(self):
		"""Check if CEO approval is required."""
		# CEO required for amounts > 1M
		if flt(self.payment_amount, 2) > CEO_APPROVAL_THRESHOLD:
			self.ceo_required = 1
			return

		# CEO required for new suppliers (within configured window)
		# FIX-D2 (S153): Use get_doc to invoke @property (computed), not stored field
		if self.supplier:
			supplier_doc = frappe.get_doc("BEI Supplier", self.supplier)
			if supplier_doc.is_new_supplier:
				self.ceo_required = 1
				return

		self.ceo_required = 0

	def load_supplier_bank_info(self):
		"""Load supplier bank information for payment."""
		if self.supplier:
			bank_info = frappe.db.get_value(
				"BEI Supplier",
				self.supplier,
				["bank_name", "bank_account_number", "bank_account_name"],
				as_dict=True,
			)
			if bank_info:
				self.supplier_bank_name = bank_info.bank_name
				self.supplier_bank_account = bank_info.bank_account_number
				self.supplier_account_name = bank_info.bank_account_name

	def auto_assign_gl_account(self):
		"""
		Auto-assign GL account code based on RFP type.

		Uses account_number lookup (not bare codes) because Frappe Account
		names are full strings like "1113000 - Petty Cash Fund - BEI".

		Priority #5 from Automation List: Automatic Account Titles
		"""
		if not self.rfp_type or self.account_code:
			return

		# Account number mapping (looked up via _resolve_account_by_codes)
		rfp_account_map = {
			"PCF Replenishment": ("1113000",),  # Petty Cash Fund
			"Delivery Fund": ("1115000",),  # Delivery Fund
			"Transpo Allowance": ("5300",),  # Transportation Expense
			"Rentals": ("5400",),  # Rent Expense
			"Vendor Invoice": None,  # Item-based mapping
			"Cash Advance": ("1200",),  # Advances/Prepayments
			"Reimbursement": ("2100",),  # AP - Reimbursements
			"Credit Card Transaction": ("2110",),  # Credit Card Payable
		}

		account_numbers = rfp_account_map.get(self.rfp_type)

		if account_numbers:
			account_name = _resolve_account_by_codes(account_numbers)
			if account_name:
				self.account_code = account_name
			else:
				account_number_text = ", ".join(account_numbers)
				frappe.log_error(
					f"GL account {account_number_text} not found for RFP type '{self.rfp_type}'",
					"GL Account Mapping Warning",
				)
				frappe.msgprint(
					_(
						"GL Account {0} for RFP type '{1}' not found. " "Please assign account manually."
					).format(account_number_text, self.rfp_type),
					indicator="orange",
				)
		elif self.rfp_type == "Vendor Invoice" and self.supplier:
			# For vendor invoices, use item-based expense account mapping
			# (handled by bei_invoice._get_expense_account at invoice level)
			pass

	def _check_role(self, allowed_roles):
		"""Verify current user has one of the allowed roles."""
		user_roles = frappe.get_roles(frappe.session.user)
		if not any(role in user_roles for role in allowed_roles):
			frappe.throw(
				_("You do not have permission to perform this action. " "Required role: {0}").format(
					" or ".join(allowed_roles)
				),
				frappe.PermissionError,
			)

	@frappe.whitelist()
	def submit_for_approval(self):
		"""Submit payment request for approval workflow."""
		if self.status != "Draft":
			frappe.throw(_("Only Draft requests can be submitted"))

		# Validate invoice is verified
		invoice = frappe.get_doc("BEI Invoice", self.invoice)
		if invoice.status not in ["Verified", "Partially Paid"]:
			frappe.throw(_("Invoice must be verified before payment request"))

		# Validate payment mode is set
		if not self.payment_mode:
			frappe.throw(_("Please select a payment mode (Bank Transfer or Check)"))

		if self.payment_mode not in ["Bank Transfer", "Check"]:
			frappe.throw(_("Payment mode must be Bank Transfer or Check"))

		self.requested_by = frappe.session.user
		self.status = "Pending Review"
		self.save()

		# TODO: Notify reviewer

		return {"success": True, "message": _("Payment request submitted for review")}

	@frappe.whitelist()
	def approve_review(self, comment: str | None = None):
		"""Level 1: Reviewer approves."""
		self._check_role(["Accounts User", "Accounts Manager", "System Manager"])
		if self.status != "Pending Review":
			frappe.throw(_("Request is not pending review"))

		self.reviewer_status = "Approved"
		self.reviewer = frappe.session.user
		self.reviewer_date = now_datetime()
		self.reviewer_comment = comment

		# Move to next level
		self.status = "Pending Budget Approval"
		self.save()

		self._notify_next_approver("Budget Approver", "cpo_approver_email")

		return {"success": True, "message": _("Review approved - pending budget approval")}

	@frappe.whitelist()
	def approve_budget(self, comment: str | None = None):
		"""Level 2: Budget approver approves."""
		self._check_role(["Accounts Manager", "System Manager"])
		if self.status != "Pending Budget Approval":
			frappe.throw(_("Request is not pending budget approval"))

		self.budget_status = "Approved"
		self.budget_approver = frappe.session.user
		self.budget_date = now_datetime()
		self.budget_comment = comment

		# Move to CFO (Level 3)
		self.status = "Pending CFO Approval"
		self.save()

		self._notify_next_approver("CFO", "cfo_approver_email")

		return {"success": True, "message": _("Budget approved - pending CFO approval")}

	@frappe.whitelist()
	def approve_cfo(self, comment: str | None = None):
		"""Level 3: CFO (Butch) approves."""
		self._check_role(["Accounts Manager", "System Manager"])
		if self.status != "Pending CFO Approval":
			frappe.throw(_("Request is not pending CFO approval"))

		self.cfo_status = "Approved"
		self.cfo_approver = frappe.session.user
		self.cfo_date = now_datetime()
		self.cfo_comment = comment

		if self.ceo_required:
			# Move to CEO (Level 4)
			self.status = "Pending CEO Approval"
			self._notify_next_approver("CEO", "ceo_approver_email")
		else:
			# Fully approved
			self.status = "Approved"
			self.on_fully_approved()

		self.save()

		if self.ceo_required:
			return {"success": True, "message": _("CFO approved - pending CEO approval")}
		else:
			return {"success": True, "message": _("Payment request fully approved")}

	@frappe.whitelist()
	def approve_ceo(self, comment: str | None = None):
		"""Level 4: CEO approves (only for new suppliers or >1M)."""
		self._check_role(["Accounts Manager", "System Manager"])
		if self.status != "Pending CEO Approval":
			frappe.throw(_("Request is not pending CEO approval"))

		if not self.ceo_required:
			frappe.throw(_("This request does not require CEO approval"))

		self.ceo_status = "Approved"
		self.ceo_approver = frappe.session.user
		self.ceo_date = now_datetime()
		self.ceo_comment = comment
		self.status = "Approved"
		self.save()

		self.on_fully_approved()

		return {"success": True, "message": _("Payment request approved by CEO")}

	def _notify_next_approver(self, approver_label: str, settings_field: str):
		"""Send Google Chat notification to the next approver in the payment approval chain."""
		try:
			from hrms.api.google_chat import send_notification_to_user

			approver_email = None
			try:
				approver_email = frappe.db.get_single_value("BEI Settings", settings_field)
			except Exception:
				pass
			if not approver_email:
				from hrms.utils.delivery_billing_policy import CPO_APPROVER_EMAIL, CFO_APPROVER_EMAIL
				email_map = {
					"cpo_approver_email": CPO_APPROVER_EMAIL,
					"cfo_approver_email": CFO_APPROVER_EMAIL,
					"ceo_approver_email": "sam@bebang.ph",
				}
				approver_email = email_map.get(settings_field)
			if not approver_email:
				return

			supplier_name = self.supplier_name or self.supplier or "Unknown"
			message = (
				f"*Payment Approval Required ({approver_label})*\n"
				f"Payment Request: {self.name}\n"
				f"Supplier: {supplier_name}\n"
				f"Amount: PHP {flt(self.payment_amount):,.2f}\n"
				f"Status: {self.status}\n"
				f"Invoice: {self.invoice or 'N/A'}\n"
				f"View: https://my.bebang.ph/procurement/payment/{self.name}"
			)
			send_notification_to_user(approver_email, message)
		except Exception as e:
			frappe.log_error(
				f"Failed to send payment approval notification for {self.name} to {approver_label}: {e}",
				"Payment Approval Notification Error",
			)

	def on_fully_approved(self):
		"""Actions when payment request is fully approved."""
		# Update invoice balance
		invoice = frappe.get_doc("BEI Invoice", self.invoice)
		invoice.record_payment(amount=self.payment_amount, payment_date=self.payment_date)

		supplier_id = self.supplier or invoice.supplier
		if supplier_id and not self.supplier:
			self.supplier = supplier_id
			self.db_set("supplier", supplier_id, update_modified=False)

		# Update supplier payment metrics
		if supplier_id:
			supplier = frappe.get_doc("BEI Supplier", supplier_id)
			supplier.update_metrics()
			supplier.save()

	def create_frappe_payment_entry(self):
		"""
		Create corresponding Frappe Payment Entry.

		PREREQUISITES:
		- Payment Request must be fully approved (status = "Approved")
		- Linked BEI Invoice must have Frappe Purchase Invoice
		- Payment mode must be Bank Transfer or Check

		FIELD MAPPING:
		- payment_amount -> paid_amount
		- payment_mode -> mode_of_payment
		- payment_date -> posting_date
		- bank_account -> paid_from (for Bank Transfer)
		- check_number -> reference_no (for Check)
		- transaction_reference -> reference_no

		GL ENTRIES (created automatically by Frappe):
		- Dr: Accounts Payable (Supplier)
		- Cr: Bank/Cash Account

		Returns: Frappe Payment Entry name or None
		"""
		if self.get("frappe_payment_entry"):
			frappe.msgprint(
				_("Already linked to Frappe Payment Entry: {0}").format(self.frappe_payment_entry),
				indicator="blue",
			)
			return self.frappe_payment_entry

		# Validate status
		if self.status not in ["Approved", "Processing", "Paid"]:
			frappe.throw(
				_("Cannot create Payment Entry - Request not approved. " "Current status: {0}").format(
					self.status
				)
			)

		# Validate payment mode
		if self.payment_mode not in ["Bank Transfer", "Check"]:
			frappe.throw(
				_("Payment mode must be 'Bank Transfer' or 'Check'. " "Current mode: {0}").format(
					self.payment_mode or "Not set"
				)
			)

		# Get linked documents
		bei_invoice = frappe.get_doc("BEI Invoice", self.invoice)

		# Ensure Frappe Purchase Invoice exists
		if not bei_invoice.frappe_purchase_invoice:
			if bei_invoice.status in ["Verified", "Partially Paid", "Paid"]:
				bei_invoice.create_frappe_purchase_invoice()
			else:
				frappe.throw(_("No Frappe Purchase Invoice linked. " "Verify BEI Invoice first."))

		frappe_pi = bei_invoice.frappe_purchase_invoice

		# Check PI is submitted
		pi_doc = frappe.get_doc("Purchase Invoice", frappe_pi)
		if pi_doc.docstatus == 0 and bei_invoice.status in ["Verified", "Partially Paid", "Paid"]:
			bei_invoice.submit_frappe_invoice()
			pi_doc = frappe.get_doc("Purchase Invoice", frappe_pi)

		if pi_doc.docstatus != 1:
			frappe.throw(
				_("Frappe Purchase Invoice {0} is not submitted. " "Please submit it first.").format(
					frappe_pi
				)
			)

		# Get Frappe Supplier
		supplier_id = self.supplier or bei_invoice.supplier
		if not supplier_id:
			frappe.throw(_("No BEI Supplier linked to Payment Request {0}.").format(self.name))

		if not self.supplier:
			self.supplier = supplier_id
			self.db_set("supplier", supplier_id, update_modified=False)

		bei_supplier = frappe.get_doc("BEI Supplier", supplier_id)
		frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

		# Determine accounts and mode of payment
		paid_from, mode_of_payment = self._get_payment_accounts()

		# Determine reference number
		reference_no = self.transaction_reference or self.check_number or ""

		# Create Payment Entry
		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Pay",
				"posting_date": self.payment_date or frappe.utils.nowdate(),
				"company": get_company(),
				"party_type": "Supplier",
				"party": frappe_supplier,
				"party_name": bei_supplier.supplier_name,
				"paid_from": paid_from,
				"paid_to": pi_doc.credit_to,  # Supplier payable account
				"paid_amount": flt(self.payment_amount, 2),
				"received_amount": flt(self.payment_amount, 2),
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"mode_of_payment": mode_of_payment,
				"reference_no": reference_no,
				"reference_date": self.payment_date or frappe.utils.nowdate(),
				"bei_payment_request": self.name,  # Reference back
			}
		)

		# Add reference to Purchase Invoice
		pe.append(
			"references",
			{
				"reference_doctype": "Purchase Invoice",
				"reference_name": frappe_pi,
				"total_amount": pi_doc.grand_total,
				"outstanding_amount": pi_doc.outstanding_amount,
				"allocated_amount": flt(self.payment_amount, 2),
			},
		)

		try:
			pe.insert(ignore_permissions=True)
			# Submit the payment entry
			pe.submit()

			# Store reference (need to add field if not exists)
			self.db_set("frappe_payment_entry", pe.name, update_modified=False)

			frappe.msgprint(
				_("Created and submitted Frappe Payment Entry: {0}").format(pe.name), indicator="green"
			)

			return pe.name

		except Exception as e:
			frappe.log_error(
				f"Failed to create Frappe PE for BEI Payment Request {self.name}: {e}",
				"BEI Payment Request Integration Error",
			)
			frappe.throw(_("Failed to create Frappe Payment Entry: {0}").format(str(e)))

	def _get_payment_accounts(self):
		"""
		Get payment from account and mode of payment based on payment mode.

		Bank Transfer: Uses specified bank account
		Check: Uses check bank account

		Returns: (paid_from_account, mode_of_payment)
		"""
		company = get_company()

		if self.payment_mode == "Bank Transfer":
			# Get bank account
			if self.bank_account:
				bank_account = frappe.get_doc("Bank Account", self.bank_account)
				paid_from = bank_account.account
			else:
				# Default bank account
				paid_from = (
					frappe.db.get_value("Company", company, "default_bank_account")
					or "1100 - Cash and Bank - BEI"
				)

			mode_of_payment = "Wire Transfer"

		elif self.payment_mode == "Check":
			# Check payments typically from a specific check account
			if self.bank_account:
				bank_account = frappe.get_doc("Bank Account", self.bank_account)
				paid_from = bank_account.account
			else:
				paid_from = (
					frappe.db.get_value("Company", company, "default_bank_account")
					or "1100 - Cash and Bank - BEI"
				)

			mode_of_payment = "Cheque"

		else:
			frappe.throw(_("Unsupported payment mode: {0}").format(self.payment_mode))

		# Verify mode of payment exists
		if not frappe.db.exists("Mode of Payment", mode_of_payment):
			# Create if doesn't exist
			mop = frappe.get_doc(
				{"doctype": "Mode of Payment", "mode_of_payment": mode_of_payment, "type": "Bank"}
			)
			mop.insert(ignore_permissions=True)

		return paid_from, mode_of_payment

	@frappe.whitelist()
	def reject(self, level: str, reason: str):
		"""Reject payment request at any level."""
		self._check_role(["Accounts User", "Accounts Manager", "System Manager"])
		valid_levels = {
			"review": ("Pending Review", "reviewer"),
			"budget": ("Pending Budget Approval", "budget"),
			"cfo": ("Pending CFO Approval", "cfo"),
			"ceo": ("Pending CEO Approval", "ceo"),
		}

		if level not in valid_levels:
			frappe.throw(_("Invalid approval level"))

		expected_status, field_prefix = valid_levels[level]

		if self.status != expected_status:
			frappe.throw(_("Request is not at the correct approval level"))

		if not reason:
			frappe.throw(_("Please provide a rejection reason"))

		# Set rejection fields
		setattr(self, f"{field_prefix}_status", "Rejected")
		if field_prefix == "reviewer":
			self.reviewer = frappe.session.user
			self.reviewer_date = now_datetime()
			self.reviewer_comment = reason
		elif field_prefix == "budget":
			self.budget_approver = frappe.session.user
			self.budget_date = now_datetime()
			self.budget_comment = reason
		elif field_prefix == "cfo":
			self.cfo_approver = frappe.session.user
			self.cfo_date = now_datetime()
			self.cfo_comment = reason
		elif field_prefix == "ceo":
			self.ceo_approver = frappe.session.user
			self.ceo_date = now_datetime()
			self.ceo_comment = reason

		self.status = "Rejected"
		self.save()

		return {"success": True, "message": _("Payment request rejected")}

	@frappe.whitelist()
	def mark_as_paid(
		self,
		transaction_reference: str | None = None,
		payment_proof: str | None = None,
	):
		"""
		Mark payment as processed/paid and create Frappe Payment Entry.

		This is the final step in the payment workflow:
		1. Updates status to Processing
		2. Creates Frappe Payment Entry (with GL postings)
		3. For advance payments: routes to 1105203 with EWT handling
		4. Updates status to Paid
		5. Updates BEI Invoice payment tracking
		"""
		self._check_role(["Accounts Manager", "System Manager"])
		if self.status != "Approved":
			frappe.throw(_("Only approved requests can be marked as paid"))

		# Update tracking fields
		self.transaction_reference = transaction_reference
		self.payment_proof = payment_proof
		self.processed_by = frappe.session.user
		self.processed_date = now_datetime()
		self.status = "Processing"
		self.save()

		pe_name = None
		pe_warning = None

		if cint(self.is_advance_payment):
			# Advance payment: custom GL routing to 1105203
			try:
				pe_name = self._create_advance_payment_entry()
			except Exception as e:
				frappe.log_error(
					f"Advance Payment Entry creation failed for {self.name}: {e}", "BEI Advance Payment Error"
				)
				pe_warning = str(e)
		else:
			# Standard payment: create Frappe Payment Entry
			try:
				pe_name = self.create_frappe_payment_entry()
			except Exception as e:
				frappe.log_error(
					f"Payment Entry creation failed for {self.name}: {e}", "BEI Payment Entry Error"
				)
				pe_warning = str(e)

		# Route based on OR requirement
		self._route_after_payment()
		self.save()

		msg = _("Payment completed")
		if pe_name:
			msg = _("Payment completed. Frappe Payment Entry: {0}").format(pe_name)

		result = {
			"success": True,
			"message": msg,
			"status": self.status,
			"or_status": self.or_status,
		}
		if pe_name:
			result["payment_entry"] = pe_name
		if pe_warning:
			result["warning"] = _(
				"Frappe Payment Entry creation failed - " "manual entry may be required. {0}"
			).format(pe_warning)
		return result

	def _create_advance_payment_entry(self):
		"""
		Create Payment Entry for advance payment with GL to 1105203.

		GL entries when NO EWT:
		  Dr 1105203 - ADVANCES TO SUPPLIERS (gross amount)
		  Cr Bank Account (gross amount)

		GL entries when EWT applicable:
		  Dr 1105203 - ADVANCES TO SUPPLIERS (gross amount)
		  Cr Bank Account (net = gross - ewt)
		  Cr 2102202 - EWT PAYABLE (ewt amount)

		NO VAT at advance payment time (EOPT Law: VAT recognized on delivery date).
		All GL rows include party_type + party per DM-1.
		Uses savepoint per DM-2.
		"""
		gross_amount = flt(self.payment_amount, 2)
		ewt_amount = 0.0

		# Check supplier EWT
		if self.supplier:
			supplier_doc = frappe.get_doc("BEI Supplier", self.supplier)
			if cint(supplier_doc.ewt_applicable) and flt(self.ewt_rate):
				ewt_amount = flt(gross_amount * flt(self.ewt_rate) / 100, 2)

		net_amount = flt(gross_amount - ewt_amount, 2)

		# Determine bank account
		paid_from, mode_of_payment = self._get_payment_accounts()

		# Get supplier name for party field
		supplier_name = (
			frappe.db.get_value("BEI Supplier", self.supplier, "supplier_name") if self.supplier else ""
		)

		# Get or create Frappe Supplier for party
		frappe_supplier = None
		if self.supplier:
			bei_supplier = frappe.get_doc("BEI Supplier", self.supplier)
			frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

		party_name = frappe_supplier or supplier_name

		reference_no = self.transaction_reference or self.check_number or ""

		sp = frappe.db.savepoint("advance_payment")
		try:
			# Create Payment Entry
			pe = frappe.get_doc(
				{
					"doctype": "Payment Entry",
					"payment_type": "Pay",
					"posting_date": self.payment_date or nowdate(),
					"company": get_company(),
					"party_type": "Supplier",
					"party": party_name,
					"paid_from": paid_from,
					"paid_to": "1105203 - ADVANCES TO SUPPLIERS - BEI",
					"paid_amount": gross_amount,
					"received_amount": gross_amount,
					"source_exchange_rate": 1,
					"target_exchange_rate": 1,
					"mode_of_payment": mode_of_payment,
					"reference_no": reference_no,
					"reference_date": self.payment_date or nowdate(),
					"bei_payment_request": self.name,
					"remarks": _("Advance payment to {0} against PO {1}").format(
						supplier_name, self.purchase_order or "N/A"
					),
				}
			)

			# If EWT, add deduction row
			if ewt_amount > 0:
				pe.append(
					"deductions",
					{
						"account": "2102202 - EWT PAYABLE - BEI",
						"cost_center": "Main - BEI",
						"amount": ewt_amount,
					},
				)
				# Adjust paid amount to net
				pe.paid_amount = net_amount
				pe.received_amount = gross_amount

			pe.insert(ignore_permissions=True)
			pe.submit()

			# Update advance tracking fields
			self.ewt_amount = ewt_amount
			self.advance_amount = gross_amount
			self.advance_cleared_amount = 0
			self.advance_outstanding = gross_amount
			self.advance_status = "Outstanding"
			self.advance_gl_account = "1105203 - ADVANCES TO SUPPLIERS - BEI"
			self.db_set("frappe_payment_entry", pe.name, update_modified=False)

			frappe.msgprint(_("Advance Payment Entry created: {0}").format(pe.name), indicator="green")

			return pe.name

		except Exception:
			frappe.db.rollback(save_point=sp)
			raise

	def _route_after_payment(self):
		"""Route payment to OR tracking or close based on or_required flag."""
		if self.or_required:
			self.status = "Paid - Awaiting OR"
			self.or_status = "Awaiting OR"
			# Calculate OR due date from supplier's payment terms
			payment_terms_days = 30  # default
			if self.supplier:
				supplier_terms = frappe.db.get_value("BEI Supplier", self.supplier, "payment_terms_days")
				if supplier_terms:
					payment_terms_days = int(supplier_terms)
			self.or_due_date = add_days(nowdate(), payment_terms_days)
		else:
			self.status = "Closed"
			self.or_status = "Not Required"

	@frappe.whitelist()
	def get_approval_status(self):
		"""Get detailed approval status for UI display."""
		return {
			"current_status": self.status,
			"ceo_required": self.ceo_required,
			"levels": {
				"review": {
					"status": self.reviewer_status,
					"approver": self.reviewer,
					"date": self.reviewer_date,
					"comment": self.reviewer_comment,
				},
				"budget": {
					"status": self.budget_status,
					"approver": self.budget_approver,
					"date": self.budget_date,
					"comment": self.budget_comment,
				},
				"cfo": {
					"status": self.cfo_status,
					"approver": self.cfo_approver,
					"date": self.cfo_date,
					"comment": self.cfo_comment,
				},
				"ceo": {
					"status": self.ceo_status if self.ceo_required else "N/A",
					"approver": self.ceo_approver,
					"date": self.ceo_date,
					"comment": self.ceo_comment,
				},
			},
		}
