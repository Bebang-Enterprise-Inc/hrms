# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, getdate, add_days


class BEIInvoice(Document):
    def validate(self):
        self.set_invoice_no()
        self.calculate_totals()
        self.load_reference_amounts()
        self.perform_three_way_match()

    def set_invoice_no(self):
        """Set invoice number from name if not already set."""
        if not self.invoice_no and self.name:
            self.invoice_no = self.name

    def after_insert(self):
        self.invoice_no = self.name
        self.db_set("invoice_no", self.name, update_modified=False)

    def calculate_totals(self):
        """Calculate grand total and balance."""
        self.grand_total = (
            flt(self.subtotal, 2)
            + flt(self.vat_amount, 2)
            - flt(self.withholding_tax, 2)
        )
        self.balance_due = flt(self.grand_total, 2) - flt(self.amount_paid, 2)

        # Update payment status
        if self.amount_paid >= self.grand_total:
            self.payment_status = "Paid"
        elif self.amount_paid > 0:
            self.payment_status = "Partially Paid"
        else:
            self.payment_status = "Unpaid"

    def load_reference_amounts(self):
        """Load PO and GR amounts for 3-way match."""
        if self.purchase_order:
            po = frappe.get_doc("BEI Purchase Order", self.purchase_order)
            self.po_amount = po.grand_total

        if self.goods_receipt:
            gr = frappe.get_doc("BEI Goods Receipt", self.goods_receipt)
            self.gr_amount = gr.total_amount

    def perform_three_way_match(self):
        """Perform 3-way match between PO, GR, and Invoice."""
        if not self.purchase_order or not self.goods_receipt:
            self.match_status = "Pending"
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

            # Create Frappe Purchase Invoice
            self.create_frappe_purchase_invoice()

            return {"success": True, "message": _("Invoice verified - 3-way match passed")}

        elif self.match_status == "Variance Detected":
            self.status = "Variance Pending Approval"
            self.save()
            return {
                "success": False,
                "message": _("Variance detected - requires approval"),
                "po_gr_variance": self.po_gr_variance,
                "gr_inv_variance": self.gr_inv_variance
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

        # Create Frappe Purchase Invoice
        self.create_frappe_purchase_invoice()

        return {"success": True, "message": _("Variance approved - Invoice verified")}

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
        """Create corresponding Frappe Purchase Invoice."""
        if self.frappe_purchase_invoice:
            return  # Already created

        # Get Frappe supplier from BEI Supplier
        supplier = frappe.get_doc("BEI Supplier", self.supplier)
        frappe_supplier = supplier.frappe_supplier

        if not frappe_supplier:
            frappe.throw(
                _("Supplier {0} not linked to Frappe Supplier").format(self.supplier)
            )

        # Get PO items
        po = frappe.get_doc("BEI Purchase Order", self.purchase_order)

        pi = frappe.get_doc({
            "doctype": "Purchase Invoice",
            "supplier": frappe_supplier,
            "posting_date": self.invoice_date,
            "due_date": self.due_date,
            "bill_no": self.supplier_invoice_no,
            "bill_date": self.invoice_date,
            "company": "Bebang Enterprise Inc."
        })

        # Get GR items for actual received quantities
        gr = frappe.get_doc("BEI Goods Receipt", self.goods_receipt)

        for gr_item in gr.items:
            if flt(gr_item.accepted_qty, 2) > 0:
                pi.append("items", {
                    "item_code": gr_item.item_code,
                    "item_name": gr_item.item_name,
                    "description": gr_item.description,
                    "qty": gr_item.accepted_qty,
                    "uom": gr_item.uom or "Nos",
                    "rate": gr_item.unit_cost,
                    "purchase_order": po.frappe_po if po.frappe_po else None
                })

        if pi.items:
            pi.insert(ignore_permissions=True)

            self.frappe_purchase_invoice = pi.name
            self.db_set("frappe_purchase_invoice", pi.name)

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
            "balance_due": self.balance_due
        }

    def on_cancel(self):
        """Handle invoice cancellation."""
        self.status = "Cancelled"
