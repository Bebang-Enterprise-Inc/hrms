# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class BEIPurchaseRequisition(Document):
    def validate(self):
        self.calculate_totals()
        self.validate_item_prices()
        self.set_pr_no()

    def validate_item_prices(self):
        """Warn if items have ₱0 price when a known price exists in Item master."""
        for item in self.items:
            if flt(item.estimated_unit_cost) <= 0:
                standard_rate = flt(frappe.db.get_value("Item", item.item_code, "standard_rate") or 0)
                if standard_rate > 0:
                    # Auto-fill from Item master instead of blocking
                    item.estimated_unit_cost = standard_rate
                    item.estimated_amount = flt(item.qty or 0) * standard_rate

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
        """Convert PR to Purchase Order. Approval gate is at PO level (Mae), not PR level."""
        if self.status in ("Cancelled", "Converted"):
            frappe.throw(_("Cannot convert a {0} PR to PO").format(self.status))

        # Check supplier exists
        if not frappe.db.exists("BEI Supplier", supplier_code):
            frappe.throw(_("Supplier not found"))

        # S193 guard — block conversion against Blacklisted / Pending Verification /
        # Inactive suppliers. convert_to_po was previously bypassing the guard that
        # applies to direct create_purchase_order calls. Discovered by S194-6.
        from hrms.api.procurement import _assert_supplier_active
        _assert_supplier_active(supplier_code, "purchase_order")

        # S194-15 — TIN gate must fire on convert_to_po as well as direct create.
        # Compute the projected PO value from PR items and check the supplier's
        # TIN against the rolling 12-month annual-purchase threshold (default ₱250K).
        from hrms.api.procurement import get_contracted_price
        supplier_doc = frappe.get_doc("BEI Supplier", supplier_code)
        projected_po_value = 0.0
        for pr_item in self.items:
            contracted = get_contracted_price(pr_item.item_code, supplier_code)
            contracted_rate = contracted["contracted_rate"] if contracted else None
            unit_cost = contracted_rate or flt(pr_item.estimated_unit_cost) or flt(
                frappe.db.get_value("Item", pr_item.item_code, "standard_rate") or 0
            )
            projected_po_value += flt(unit_cost) * flt(pr_item.qty)

        annual_purchases_row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabBEI Purchase Order`
            WHERE supplier = %s
              AND po_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
              AND status NOT IN ('Draft', 'Cancelled')
            """,
            (supplier_code,),
        )
        annual_purchases = flt(annual_purchases_row[0][0]) if annual_purchases_row else 0.0

        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        _tin_settings = get_procurement_settings()
        _tin_threshold = flt(_tin_settings.get("tin_requirement_threshold", 250000))
        if annual_purchases + projected_po_value > _tin_threshold and not supplier_doc.tin:
            frappe.throw(
                _("Supplier {0} requires TIN registration. "
                  "Annual purchases (₱{1:,.2f}) + this PO (₱{2:,.2f}) exceed ₱{3:,.0f} threshold. "
                  "Update supplier master data before proceeding.").format(
                    supplier_doc.supplier_name, annual_purchases, projected_po_value, _tin_threshold,
                ),
                title=_("TIN Required"),
            )

        # Create PO
        po = frappe.new_doc("BEI Purchase Order")
        po.pr_reference = self.name
        po.supplier = supplier_code
        po.delivery_date = self.date_required
        po.ship_to = self.delivery_to

        # Copy items — S104: use contracted price if available, fall back to PR estimate
        for pr_item in self.items:
            contracted = get_contracted_price(pr_item.item_code, supplier_code)
            contracted_rate = contracted["contracted_rate"] if contracted else None
            # Price chain: contracted_rate → PR estimated_unit_cost → standard_rate → 0
            unit_cost = contracted_rate or flt(pr_item.estimated_unit_cost) or flt(
                frappe.db.get_value("Item", pr_item.item_code, "standard_rate") or 0
            )

            po.append("items", {
                "item_code": pr_item.item_code,
                "item_name": pr_item.item_name,
                "description": pr_item.description,
                "qty": pr_item.qty,
                "uom": pr_item.uom,
                "unit_cost": unit_cost,
                "contracted_unit_cost": contracted_rate,
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
