# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class BEIPurchaseRequisition(Document):
    def validate(self):
        self.calculate_totals()
        self.set_pr_no()

    def set_pr_no(self):
        """Set PR number from name if not already set."""
        if not self.pr_no and self.name:
            self.pr_no = self.name

    def calculate_totals(self):
        """Calculate total items and estimated cost."""
        total_cost = 0
        for item in self.items:
            item.estimated_amount = (item.qty or 0) * (item.estimated_unit_cost or 0)
            total_cost += item.estimated_amount

        self.total_items = len(self.items)
        self.total_estimated_cost = total_cost

    def after_insert(self):
        self.pr_no = self.name
        self.db_set("pr_no", self.name, update_modified=False)

    @frappe.whitelist()
    def submit_for_approval(self):
        """Submit PR for approval."""
        if self.status != "Draft":
            frappe.throw(_("Only Draft PRs can be submitted for approval"))

        if not self.items:
            frappe.throw(_("Please add at least one item"))

        self.status = "Pending Approval"
        self.save()

        # Notify approver (Aldrin)
        self.notify_approver()

        return {"success": True, "message": _("PR submitted for approval")}

    def notify_approver(self):
        """Send Google Chat notification to PR approver (CPO)."""
        try:
            from hrms.api.google_chat import send_notification_to_user

            # Get CPO email from BEI Settings, fall back to hardcoded
            approver_email = None
            try:
                approver_email = frappe.db.get_single_value("BEI Settings", "cpo_approver_email")
            except Exception:
                pass
            if not approver_email:
                from hrms.utils.delivery_billing_policy import CPO_APPROVER_EMAIL
                approver_email = CPO_APPROVER_EMAIL

            items_summary = ", ".join(
                f"{row.item_code or row.item_name} x{flt(row.qty)}"
                for row in (self.items or [])[:5]
            )
            if len(self.items or []) > 5:
                items_summary += f" (+{len(self.items) - 5} more)"

            message = (
                f"*PR Approval Required*\n"
                f"PR: {self.pr_no or self.name}\n"
                f"Department: {self.department or 'N/A'}\n"
                f"Estimated Cost: PHP {flt(self.total_estimated_cost):,.2f}\n"
                f"Items: {items_summary}\n"
                f"Requested by: {self.owner}\n"
                f"View: https://my.bebang.ph/procurement/pr/{self.name}"
            )
            send_notification_to_user(approver_email, message)
        except Exception as e:
            frappe.log_error(
                f"Failed to send PR approval notification for {self.name}: {e}",
                "PR Approval Notification Error",
            )

    @frappe.whitelist()
    def approve(self, comment=None):
        """Approve the PR."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only Pending Approval PRs can be approved"))

        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = now_datetime()
        self.save()

        return {"success": True, "message": _("PR approved successfully")}

    @frappe.whitelist()
    def reject(self, reason):
        """Reject the PR."""
        if self.status != "Pending Approval":
            frappe.throw(_("Only Pending Approval PRs can be rejected"))

        if not reason:
            frappe.throw(_("Please provide a rejection reason"))

        self.status = "Rejected"
        self.approved_by = frappe.session.user
        self.approval_date = now_datetime()
        self.rejection_reason = reason
        self.save()

        return {"success": True, "message": _("PR rejected")}

    @frappe.whitelist()
    def convert_to_po(self, supplier_code):
        """Convert approved PR to Purchase Order."""
        if self.status != "Approved":
            frappe.throw(_("Only Approved PRs can be converted to PO"))

        # Check supplier exists
        if not frappe.db.exists("BEI Supplier", supplier_code):
            frappe.throw(_("Supplier not found"))

        # Create PO
        po = frappe.new_doc("BEI Purchase Order")
        po.pr_reference = self.name
        po.supplier = supplier_code
        po.delivery_date = self.date_required
        po.ship_to = self.delivery_to

        # Copy items
        for pr_item in self.items:
            po.append("items", {
                "item_code": pr_item.item_code,
                "item_name": pr_item.item_name,
                "description": pr_item.description,
                "qty": pr_item.qty,
                "uom": pr_item.uom,
                "unit_cost": pr_item.estimated_unit_cost
            })

        po.insert()

        # Update PR status
        self.status = "Converted to PO"
        self.save()

        # Update PR items with PO reference
        for pr_item in self.items:
            pr_item.po_reference = po.name

        self.save()

        return {
            "success": True,
            "message": _("PO {0} created from PR").format(po.name),
            "po_name": po.name
        }
