# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


# CEO approval threshold
CEO_APPROVAL_THRESHOLD = 1000000  # 1 Million PHP


class BEIPaymentRequest(Document):
    """
    4-Level Approval Workflow:
    Level 1: Review (Document completeness, 3-way match verified)
    Level 2: Budget (Budget availability check)
    Level 3: CFO - Butch (Financial approval)
    Level 4: CEO (Only for new suppliers or amounts > 1M)
    """

    def validate(self):
        self.set_payment_request_no()
        self.check_ceo_requirement()
        self.load_supplier_bank_info()

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

        # CEO required for new suppliers (first PO within 6 months)
        if self.supplier:
            supplier = frappe.get_doc("BEI Supplier", self.supplier)
            if supplier.is_new_supplier:
                self.ceo_required = 1
                return

        self.ceo_required = 0

    def load_supplier_bank_info(self):
        """Load supplier bank information for payment."""
        if self.supplier:
            supplier = frappe.get_doc("BEI Supplier", self.supplier)
            self.supplier_bank_name = supplier.bank_name
            self.supplier_bank_account = supplier.bank_account_no
            self.supplier_account_name = supplier.bank_account_name

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
    def approve_review(self, comment=None):
        """Level 1: Reviewer approves."""
        if self.status != "Pending Review":
            frappe.throw(_("Request is not pending review"))

        self.reviewer_status = "Approved"
        self.reviewer = frappe.session.user
        self.reviewer_date = now_datetime()
        self.reviewer_comment = comment

        # Move to next level
        self.status = "Pending Budget Approval"
        self.save()

        # TODO: Notify budget approver

        return {"success": True, "message": _("Review approved - pending budget approval")}

    @frappe.whitelist()
    def approve_budget(self, comment=None):
        """Level 2: Budget approver approves."""
        if self.status != "Pending Budget Approval":
            frappe.throw(_("Request is not pending budget approval"))

        self.budget_status = "Approved"
        self.budget_approver = frappe.session.user
        self.budget_date = now_datetime()
        self.budget_comment = comment

        # Move to CFO (Level 3)
        self.status = "Pending CFO Approval"
        self.save()

        # TODO: Notify CFO (Butch)

        return {"success": True, "message": _("Budget approved - pending CFO approval")}

    @frappe.whitelist()
    def approve_cfo(self, comment=None):
        """Level 3: CFO (Butch) approves."""
        if self.status != "Pending CFO Approval":
            frappe.throw(_("Request is not pending CFO approval"))

        self.cfo_status = "Approved"
        self.cfo_approver = frappe.session.user
        self.cfo_date = now_datetime()
        self.cfo_comment = comment

        if self.ceo_required:
            # Move to CEO (Level 4)
            self.status = "Pending CEO Approval"
            # TODO: Notify CEO
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
    def approve_ceo(self, comment=None):
        """Level 4: CEO approves (only for new suppliers or >1M)."""
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

    def on_fully_approved(self):
        """Actions when payment request is fully approved."""
        # Update invoice balance
        invoice = frappe.get_doc("BEI Invoice", self.invoice)
        invoice.record_payment(
            amount=self.payment_amount,
            payment_date=self.payment_date
        )

        # Update supplier payment metrics
        if self.supplier:
            supplier = frappe.get_doc("BEI Supplier", self.supplier)
            supplier.update_metrics()
            supplier.save()

        # TODO: Create Payment Entry in Frappe

    @frappe.whitelist()
    def reject(self, level, reason):
        """Reject payment request at any level."""
        valid_levels = {
            "review": ("Pending Review", "reviewer"),
            "budget": ("Pending Budget Approval", "budget"),
            "cfo": ("Pending CFO Approval", "cfo"),
            "ceo": ("Pending CEO Approval", "ceo")
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
    def mark_as_paid(self, transaction_reference=None, payment_proof=None):
        """Mark payment as processed/paid."""
        if self.status != "Approved":
            frappe.throw(_("Only approved requests can be marked as paid"))

        self.status = "Processing"
        self.processed_by = frappe.session.user
        self.processed_date = now_datetime()
        self.transaction_reference = transaction_reference
        self.payment_proof = payment_proof
        self.save()

        # Update status to Paid after confirmation
        self.status = "Paid"
        self.save()

        return {"success": True, "message": _("Payment marked as completed")}

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
                    "comment": self.reviewer_comment
                },
                "budget": {
                    "status": self.budget_status,
                    "approver": self.budget_approver,
                    "date": self.budget_date,
                    "comment": self.budget_comment
                },
                "cfo": {
                    "status": self.cfo_status,
                    "approver": self.cfo_approver,
                    "date": self.cfo_date,
                    "comment": self.cfo_comment
                },
                "ceo": {
                    "status": self.ceo_status if self.ceo_required else "N/A",
                    "approver": self.ceo_approver,
                    "date": self.ceo_date,
                    "comment": self.ceo_comment
                }
            }
        }
