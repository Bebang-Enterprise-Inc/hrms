# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class BEIGoodsReceipt(Document):
    def validate(self):
        self.set_gr_no()
        self.calculate_totals()
        self.update_accepted_qty()

    def set_gr_no(self):
        """Set GR number from name if not already set."""
        if not self.gr_no and self.name:
            self.gr_no = self.name

    def after_insert(self):
        self.gr_no = self.name
        self.db_set("gr_no", self.name, update_modified=False)

    def calculate_totals(self):
        """Calculate all totals from items."""
        total_ordered = 0
        total_received = 0
        total_accepted = 0
        total_rejected = 0
        total_amount = 0

        for item in self.items:
            total_ordered += flt(item.ordered_qty, 2)
            total_received += flt(item.received_qty, 2)
            total_rejected += flt(item.rejected_qty, 2)

            # Accepted = Received - Rejected
            item.accepted_qty = flt(item.received_qty, 2) - flt(item.rejected_qty, 2)
            total_accepted += item.accepted_qty

            # Amount based on accepted qty
            item.amount = item.accepted_qty * flt(item.unit_cost, 2)
            total_amount += item.amount

        self.total_ordered_qty = total_ordered
        self.total_received_qty = total_received
        self.total_accepted_qty = total_accepted
        self.total_rejected_qty = total_rejected
        self.total_amount = total_amount

    def update_accepted_qty(self):
        """Update accepted qty for each item."""
        for item in self.items:
            item.accepted_qty = flt(item.received_qty, 2) - flt(item.rejected_qty, 2)

    @frappe.whitelist()
    def load_from_po(self):
        """Load items from linked Purchase Order."""
        if not self.purchase_order:
            frappe.throw(_("Please select a Purchase Order first"))

        po = frappe.get_doc("BEI Purchase Order", self.purchase_order)

        # Check PO is approved
        if po.status not in ["Approved", "Sent to Supplier", "Partially Received"]:
            frappe.throw(_("PO must be approved before creating GR"))

        # Set supplier info
        self.supplier = po.supplier
        self.warehouse = po.ship_to

        # Clear existing items
        self.items = []

        # Load PO items
        for po_item in po.items:
            remaining_qty = flt(po_item.qty, 2) - flt(po_item.received_qty, 2)

            if remaining_qty > 0:
                self.append("items", {
                    "item_code": po_item.item_code,
                    "item_name": po_item.item_name,
                    "description": po_item.description,
                    "ordered_qty": po_item.qty,
                    "received_qty": remaining_qty,  # Default to remaining
                    "uom": po_item.uom,
                    "unit_cost": po_item.unit_cost
                })

        return {"success": True, "message": _("Items loaded from PO")}

    @frappe.whitelist()
    def submit_receipt(self):
        """Submit the goods receipt."""
        if self.status != "Draft":
            frappe.throw(_("Only Draft GRs can be submitted"))

        if not self.items:
            frappe.throw(_("Please add at least one item"))

        # Validate all items have received qty
        for item in self.items:
            if flt(item.received_qty, 2) <= 0:
                frappe.throw(
                    _("Item {0} must have a received quantity").format(item.item_code)
                )

        # Determine status based on rejections
        if self.total_rejected_qty > 0:
            if self.total_accepted_qty > 0:
                self.status = "Partially Accepted"
            else:
                self.status = "Rejected"
        else:
            if self.inspection_required:
                self.status = "Pending Inspection"
            else:
                self.status = "Accepted"

        self.save()

        # Update PO received quantities
        self.update_po_received_qty()

        return {"success": True, "message": _("Goods Receipt submitted")}

    def update_po_received_qty(self):
        """Update received quantities on the linked PO."""
        if not self.purchase_order:
            return

        po = frappe.get_doc("BEI Purchase Order", self.purchase_order)

        for gr_item in self.items:
            po.update_received_qty(gr_item.item_code, gr_item.accepted_qty)

    @frappe.whitelist()
    def complete_inspection(self, passed=True, notes=None):
        """Complete quality inspection."""
        if self.status != "Pending Inspection":
            frappe.throw(_("GR is not pending inspection"))

        self.inspection_status = "Passed" if passed else "Failed"
        self.inspection_date = now_datetime()
        self.inspection_notes = notes

        if passed:
            self.status = "Accepted"
            # Create Frappe Purchase Receipt
            self.create_frappe_purchase_receipt()
        else:
            self.status = "Rejected"

        self.save()

        return {
            "success": True,
            "message": _("Inspection completed - {0}").format(
                "Passed" if passed else "Failed"
            )
        }

    def create_frappe_purchase_receipt(self):
        """Create corresponding Frappe Purchase Receipt."""
        if self.frappe_purchase_receipt:
            return  # Already created

        if not self.purchase_order:
            return

        po = frappe.get_doc("BEI Purchase Order", self.purchase_order)

        if not po.frappe_po:
            return  # No Frappe PO to link to

        pr = frappe.get_doc({
            "doctype": "Purchase Receipt",
            "supplier": po.frappe_supplier if hasattr(po, 'frappe_supplier') else None,
            "posting_date": self.receipt_date,
            "company": "Bebang Enterprise Inc.",
            "set_warehouse": self.warehouse
        })

        for item in self.items:
            if flt(item.accepted_qty, 2) > 0:
                pr.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": item.description,
                    "qty": item.accepted_qty,
                    "uom": item.uom or "Nos",
                    "rate": item.unit_cost,
                    "warehouse": self.warehouse,
                    "purchase_order": po.frappe_po
                })

        if pr.items:
            pr.insert(ignore_permissions=True)
            pr.submit()

            self.frappe_purchase_receipt = pr.name
            self.db_set("frappe_purchase_receipt", pr.name)
