# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, now_datetime

from hrms.utils.bei_config import get_company
from hrms.utils.procurement_math import calculate_goods_receipt_gross_total
from hrms.utils.standard_buying_bridge import apply_standard_buying_context


class BEIInvoice(Document):
	def validate(self):
		self.set_invoice_no()
		self.validate_goods_receipt()
		self.calculate_totals()
		self.load_reference_amounts()
		self.perform_three_way_match()

	def validate_goods_receipt(self):
		"""Require goods_receipt unless an approved match exception exists for this PO."""
		if self.goods_receipt:
			return

		if not self.purchase_order:
			frappe.throw(_("Either Goods Receipt or Purchase Order is required"))
			return

		approved_exception = frappe.db.exists(
			"BEI Match Exception",
			{
				"purchase_order": self.purchase_order,
				"status": "Approved",
			},
		)
		if not approved_exception:
			frappe.throw(
				_(
					"Goods Receipt is required unless a match exception is approved. "
					"Request an exception via the procurement flow."
				)
			)

	def set_invoice_no(self):
		"""Set invoice number from name if not already set."""
		if not self.invoice_no and self.name:
			self.invoice_no = self.name

	def after_insert(self):
		self.invoice_no = self.name
		self.db_set("invoice_no", self.name, update_modified=False)

	def calculate_totals(self):
		"""Calculate grand total and balance."""
		self.grand_total = flt(self.subtotal, 2) + flt(self.vat_amount, 2) - flt(self.withholding_tax, 2)
		self.balance_due = flt(self.grand_total, 2) - flt(self.amount_paid, 2)

		# Update payment status
		if flt(self.amount_paid, 2) >= flt(self.grand_total, 2):
			self.payment_status = "Paid"
		elif flt(self.amount_paid, 2) > 0:
			self.payment_status = "Partially Paid"
		else:
			self.payment_status = "Unpaid"

	def load_reference_amounts(self):
		"""Load PO and GR amounts for 3-way match."""
		if self.purchase_order:
			self.po_amount = flt(
				frappe.db.get_value("BEI Purchase Order", self.purchase_order, "grand_total")
			)

		if self.goods_receipt:
			po_items = frappe.db.sql(
				"""
                SELECT item_code, qty, unit_cost, vat_rate, vat_amount
                FROM `tabBEI PO Item`
                WHERE parent = %s
                ORDER BY idx
                """,
				(self.purchase_order,),
				as_dict=True,
			)
			gr_items = frappe.db.sql(
				"""
                SELECT item_code, accepted_qty, received_qty, rejected_qty, unit_cost
                FROM `tabBEI GR Item`
                WHERE parent = %s
                ORDER BY idx
                """,
				(self.goods_receipt,),
				as_dict=True,
			)
			receipt_slice_total = calculate_goods_receipt_gross_total(gr_items, po_items)
			self.gr_amount = receipt_slice_total
			if self.purchase_order:
				self.po_amount = receipt_slice_total

	def perform_three_way_match(self):
		"""Perform 3-way match between PO, GR, and Invoice."""
		if not self.purchase_order or not self.goods_receipt:
			self.match_status = "Pending"
			return

		# Preserve approved variance status - don't recalculate after approval
		if self.match_status == "Approved with Variance":
			return

		# Calculate variances
		self.po_gr_variance = flt(self.po_amount, 2) - flt(self.gr_amount, 2)
		self.gr_inv_variance = flt(self.gr_amount, 2) - flt(self.grand_total, 2)

		# Check if within tolerance
		tolerance = flt(self.variance_tolerance, 2) or 1000  # Default PHP 1000

		po_gr_ok = abs(flt(self.po_gr_variance, 2)) <= tolerance
		gr_inv_ok = abs(flt(self.gr_inv_variance, 2)) <= tolerance

		if po_gr_ok and gr_inv_ok:
			self.match_status = "Matched"
		else:
			self.match_status = "Variance Detected"

	@frappe.whitelist()
	def submit_for_verification(self):
		"""Submit invoice for 3-way match verification."""
		if self.status != "Draft":
			frappe.throw(_("Only Draft invoices can be submitted"))

		if not self.invoice_attachment:
			frappe.throw(_("Please attach the supplier invoice"))

		self.status = "Pending 3-Way Match"
		self.save()

		return {"success": True, "message": _("Invoice submitted for 3-way match")}

	@frappe.whitelist()
	def verify_match(self):
		"""Verify the 3-way match."""
		if self.status != "Pending 3-Way Match":
			frappe.throw(_("Invoice is not pending 3-way match"))

		if self.match_status == "Matched":
			self.status = "Verified"
			self.verified_by = frappe.session.user
			self.verified_date = now_datetime()
			self.save()

			# Create Frappe Purchase Invoice (best-effort - don't block verification)
			pi_message = ""
			try:
				self.create_frappe_purchase_invoice()
				pi_message = " Frappe Purchase Invoice created."
			except Exception as e:
				frappe.log_error(title="PI Creation Failed", message=str(e))
				pi_message = f" Note: Frappe PI creation deferred ({str(e)[:100]})"

			return {"success": True, "message": _("Invoice verified - 3-way match passed") + pi_message}

		elif self.match_status == "Variance Detected":
			self.status = "Variance Pending Approval"
			self.save()
			return {
				"success": False,
				"message": _("Variance detected - requires approval"),
				"po_gr_variance": self.po_gr_variance,
				"gr_inv_variance": self.gr_inv_variance,
			}

		else:
			self.status = "Match Failed"
			self.save()
			return {"success": False, "message": _("3-way match failed")}

	@frappe.whitelist()
	def approve_variance(self, notes=None):
		"""Approve invoice despite variance."""
		if self.status != "Variance Pending Approval":
			frappe.throw(_("Invoice is not pending variance approval"))

		self.match_status = "Approved with Variance"
		self.variance_approved_by = frappe.session.user
		self.variance_notes = notes
		self.status = "Verified"
		self.verified_by = frappe.session.user
		self.verified_date = now_datetime()
		self.save()

		# Create Frappe Purchase Invoice (best-effort - don't block variance approval)
		pi_message = ""
		try:
			self.create_frappe_purchase_invoice()
			pi_message = " Frappe Purchase Invoice created."
		except Exception as e:
			frappe.log_error(title="PI Creation Failed", message=str(e))
			pi_message = f" Note: Frappe PI creation deferred ({str(e)[:100]})"

		return {"success": True, "message": _("Variance approved - Invoice verified") + pi_message}

	@frappe.whitelist()
	def reject_variance(self, reason):
		"""Reject invoice due to variance."""
		if self.status != "Variance Pending Approval":
			frappe.throw(_("Invoice is not pending variance approval"))

		if not reason:
			frappe.throw(_("Please provide a rejection reason"))

		self.variance_notes = reason
		self.status = "Match Failed"
		self.save()

		return {"success": True, "message": _("Invoice rejected due to variance")}

	def create_frappe_purchase_invoice(self):
		"""
		Create corresponding Frappe Purchase Invoice.

		PREREQUISITES:
		- BEI Invoice must be Verified (3-way match passed or variance approved)
		- BEI PO must have Frappe PO linked
		- BEI GR must have Frappe Purchase Receipt linked

		FIELD MAPPING:
		- invoice_date -> posting_date
		- due_date -> due_date
		- supplier_invoice_no -> bill_no
		- items from GR (accepted quantities)
		- withholding_tax -> taxes (EWT)
		- Links to Frappe PO and PR for proper AP posting

		GL ENTRIES (created automatically by Frappe):
		- Dr: Expense/Stock Account (per item)
		- Cr: Accounts Payable

		Returns: Frappe Purchase Invoice name or None
		"""
		if self.frappe_purchase_invoice:
			frappe.msgprint(
				_("Already linked to Frappe Purchase Invoice: {0}").format(self.frappe_purchase_invoice),
				indicator="blue",
			)
			return self.frappe_purchase_invoice

		# Validate status - must be verified
		if self.status not in ["Verified", "Partially Paid", "Paid"]:
			frappe.throw(
				_("Cannot create Purchase Invoice - 3-way match not verified. " "Current status: {0}").format(
					self.status
				)
			)

		# Validate match status
		if self.match_status not in ["Matched", "Approved with Variance"]:
			frappe.throw(_("Cannot create Purchase Invoice - Match status: {0}").format(self.match_status))

		# Get Frappe Supplier
		bei_supplier = frappe.get_doc("BEI Supplier", self.supplier)
		frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

		if not frappe_supplier:
			frappe.throw(_("Could not get or create Frappe Supplier for {0}").format(self.supplier))

		# Get linked documents
		bei_po = frappe.get_doc("BEI Purchase Order", self.purchase_order)
		bei_gr = frappe.get_doc("BEI Goods Receipt", self.goods_receipt)

		# Ensure Frappe PO exists
		if not bei_po.frappe_po:
			if bei_po.status == "Approved":
				bei_po.create_frappe_purchase_order()
			else:
				frappe.throw(_("No Frappe PO linked. Please ensure BEI PO is approved first."))

		frappe_po = bei_po.frappe_po

		# Ensure Frappe PR exists
		if not bei_gr.frappe_purchase_receipt:
			if bei_gr.status in ["Accepted", "Partially Accepted"]:
				bei_gr.create_frappe_purchase_receipt()
			else:
				frappe.throw(_("No Frappe Purchase Receipt linked. " "Please ensure GR is accepted first."))

		frappe_pr = bei_gr.frappe_purchase_receipt

		# Prepare invoice items from GR (actual received quantities)
		pi_items = []
		for gr_item in bei_gr.items:
			accepted_qty = flt(gr_item.accepted_qty, 2)

			if accepted_qty <= 0:
				continue

			# Find corresponding PO and PR items
			po_item = self._find_po_item(frappe_po, gr_item.item_code)
			pr_item = self._find_pr_item(frappe_pr, gr_item.item_code)

			pi_items.append(
				{
					"item_code": gr_item.item_code,
					"item_name": gr_item.item_name,
					"description": gr_item.description or gr_item.item_name,
					"qty": accepted_qty,
					"stock_uom": gr_item.uom or "Nos",
					"uom": gr_item.uom or "Nos",
					"conversion_factor": 1,
					"rate": flt(gr_item.unit_cost, 2),
					"expense_account": self._get_expense_account(gr_item),
					"purchase_order": frappe_po,
					"po_detail": po_item,
					"purchase_receipt": frappe_pr,
					"pr_detail": pr_item,
					"bei_invoice_item": gr_item.name,  # Reference
				}
			)

		if not pi_items:
			frappe.throw(_("No valid items to create Purchase Invoice"))

		# Create Frappe Purchase Invoice
		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": frappe_supplier,
				"posting_date": self.invoice_date,
				"due_date": self.due_date,
				"bill_no": self.supplier_invoice_no,
				"bill_date": self.invoice_date,
				"company": get_company(),
				"currency": "PHP",
				"buying_price_list": "Standard Buying",
				"update_stock": 0,  # Stock already updated via PR
				"is_return": 0,
				"bei_invoice": self.name,  # Reference back
				"payment_terms_template": self.payment_terms,
				"items": pi_items,
			}
		)
		apply_standard_buying_context(
			pi,
			store_label=bei_gr.warehouse or bei_po.ship_to,
		)

		# Add withholding tax (EWT) if applicable
		if flt(self.withholding_tax, 2) > 0:
			self._add_withholding_tax(pi)

		try:
			pi.insert(ignore_permissions=True)
			# Don't submit yet - may need review
			# pi.submit()

			self.frappe_purchase_invoice = pi.name
			self.db_set("frappe_purchase_invoice", pi.name, update_modified=False)

			frappe.msgprint(
				_("Created Frappe Purchase Invoice (Draft): {0}. " "Review and submit manually.").format(
					pi.name
				),
				indicator="green",
			)

			return pi.name

		except Exception as e:
			frappe.log_error(
				f"Failed to create Frappe PI for BEI Invoice {self.name}: {e}",
				"BEI Invoice Integration Error",
			)
			frappe.throw(_("Failed to create Frappe Purchase Invoice: {0}").format(str(e)))

	def _find_po_item(self, frappe_po_name, item_code):
		"""Find Purchase Order Item for linking."""
		return frappe.db.get_value(
			"Purchase Order Item", {"parent": frappe_po_name, "item_code": item_code}, "name"
		)

	def _find_pr_item(self, frappe_pr_name, item_code):
		"""Find Purchase Receipt Item for linking."""
		return frappe.db.get_value(
			"Purchase Receipt Item", {"parent": frappe_pr_name, "item_code": item_code}, "name"
		)

	def _get_expense_account(self, item):
		"""
		Get appropriate expense account for invoice item.

		Account mapping based on item group:
		- Raw Materials: 5110 - Cost of Raw Materials
		- Finished Goods: 5100 - Cost of Goods Sold
		- Packaging: 5120 - Packaging Expenses
		- Consumables: 6200 - Operating Supplies
		- Fixed Assets: 1500 - Fixed Assets

		Returns: Account name
		"""
		# Get item group
		item_group = frappe.db.get_value("Item", item.item_code, "item_group")

		# Account mapping (BEI COA)
		account_map = {
			"Raw Material": "5110 - Cost of Raw Materials - BEI",
			"Finished Goods": "5100 - Cost of Goods Sold - BEI",
			"Packaging Material": "5120 - Packaging Expenses - BEI",
			"Consumable": "6200 - Operating Supplies - BEI",
			"Fixed Asset": "1500 - Fixed Assets - BEI",
			"Products": "5100 - Cost of Goods Sold - BEI",  # Default
		}

		# Return mapped account or default
		account = account_map.get(item_group, "5100 - Cost of Goods Sold - BEI")

		# Verify account exists, fallback to default expense account
		if not frappe.db.exists("Account", account):
			default_expense = frappe.db.get_value("Company", get_company(), "default_expense_account")
			return default_expense or "5100 - Cost of Goods Sold - BEI"

		return account

	def _add_withholding_tax(self, pi):
		"""
		Add withholding tax (EWT) to Purchase Invoice.

		Philippine EWT rates:
		- 1% for goods
		- 2% for services
		- 5% for professional fees

		This method adds a negative tax entry for EWT.
		"""
		ewt_account = "2150 - Withholding Tax Payable - BEI"

		# Verify EWT account exists
		if not frappe.db.exists("Account", ewt_account):
			# Try to find any withholding account
			ewt_account = frappe.db.get_value(
				"Account", {"account_name": ["like", "%Withholding%"], "company": get_company()}, "name"
			)

		if ewt_account:
			pi.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": ewt_account,
					"description": "Expanded Withholding Tax (EWT)",
					"tax_amount": -flt(self.withholding_tax, 2),  # Negative to reduce payable
					"category": "Total",
					"add_deduct_tax": "Deduct",
				},
			)

	@frappe.whitelist()
	def submit_frappe_invoice(self):
		"""Submit the linked Frappe Purchase Invoice."""
		if not self.frappe_purchase_invoice:
			frappe.throw(_("No Frappe Purchase Invoice linked"))

		pi = frappe.get_doc("Purchase Invoice", self.frappe_purchase_invoice)

		if pi.docstatus == 1:
			frappe.msgprint(_("Frappe Purchase Invoice already submitted"), indicator="blue")
			return

		try:
			pi.submit()
			frappe.msgprint(_("Submitted Frappe Purchase Invoice: {0}").format(pi.name), indicator="green")
			return pi.name
		except Exception as e:
			frappe.throw(_("Failed to submit Purchase Invoice: {0}").format(str(e)))

	@frappe.whitelist()
	def record_payment(self, amount, payment_date=None, reference=None):
		"""Record a payment against this invoice."""
		amount = flt(amount, 2)

		if amount <= 0:
			frappe.throw(_("Payment amount must be greater than zero"))

		if amount > self.balance_due:
			frappe.throw(_("Payment amount cannot exceed balance due"))

		self.amount_paid = flt(self.amount_paid, 2) + amount
		self.last_payment_date = payment_date or getdate()
		self.calculate_totals()

		if self.payment_status == "Paid":
			self.status = "Paid"
		else:
			self.status = "Partially Paid"

		self.save()

		return {
			"success": True,
			"message": _("Payment of {0} recorded").format(amount),
			"balance_due": self.balance_due,
		}

	def on_cancel(self):
		"""Handle invoice cancellation."""
		self.status = "Cancelled"
