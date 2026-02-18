# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
from hrms.utils.bei_config import get_company


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
        """
        Create corresponding Frappe Purchase Receipt.

        PREREQUISITES:
        - GR must be Accepted (inspection passed or not required)
        - Linked BEI PO must have a Frappe PO
        - At least one item with accepted_qty > 0

        FIELD MAPPING:
        - receipt_date -> posting_date
        - warehouse -> set_warehouse
        - items (accepted_qty) -> items (qty)
        - Links back to Frappe PO for proper stock tracking

        STOCK IMPACT:
        - Creates stock ledger entries
        - Updates warehouse quantities
        - Links to PO for landed cost tracking

        Returns: Frappe Purchase Receipt name or None
        """
        if self.frappe_purchase_receipt:
            frappe.msgprint(
                _("Already linked to Frappe Purchase Receipt: {0}").format(
                    self.frappe_purchase_receipt
                ),
                indicator="blue"
            )
            return self.frappe_purchase_receipt

        # Validate status
        if self.status not in ["Accepted", "Partially Accepted"]:
            frappe.throw(
                _("Cannot create Purchase Receipt - GR must be Accepted. "
                  "Current status: {0}").format(self.status)
            )

        # Validate inspection if required
        if self.inspection_required and self.inspection_status != "Passed":
            frappe.throw(
                _("Cannot create Purchase Receipt - Quality inspection not passed. "
                  "Inspection status: {0}").format(self.inspection_status)
            )

        if not self.purchase_order:
            frappe.throw(_("Cannot create Purchase Receipt - No linked Purchase Order"))

        # Get BEI PO and Frappe PO
        bei_po = frappe.get_doc("BEI Purchase Order", self.purchase_order)

        if not bei_po.frappe_po:
            # Try to create Frappe PO first
            if bei_po.status == "Approved":
                bei_po.create_frappe_purchase_order()
            else:
                frappe.throw(
                    _("No Frappe PO linked. Approve BEI PO first to create Frappe PO.")
                )

        frappe_po = bei_po.frappe_po

        # Get Frappe Supplier
        bei_supplier = frappe.get_doc("BEI Supplier", self.supplier)
        frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

        # Prepare PR items - only accepted quantities
        pr_items = []
        for item in self.items:
            accepted_qty = flt(item.accepted_qty, 2)

            if accepted_qty <= 0:
                continue

            # Find matching PO item for rate and proper linking
            po_item = self._find_frappe_po_item(frappe_po, item.item_code)

            pr_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description or item.item_name,
                "qty": accepted_qty,
                "stock_uom": item.uom or "Nos",
                "uom": item.uom or "Nos",
                "conversion_factor": 1,
                "rate": flt(item.unit_cost, 2),
                "warehouse": self.warehouse or "Stores - BEI",
                "purchase_order": frappe_po,
                "purchase_order_item": po_item,
                "rejected_qty": flt(item.rejected_qty, 2),
                "bei_gr_item": item.name,  # Reference back
            })

        if not pr_items:
            frappe.throw(_("No items with accepted quantity to create Purchase Receipt"))

        # Create Frappe Purchase Receipt
        pr = frappe.get_doc({
            "doctype": "Purchase Receipt",
            "supplier": frappe_supplier,
            "posting_date": self.receipt_date,
            "posting_time": frappe.utils.nowtime(),
            "company": get_company(),
            "currency": "PHP",
            "buying_price_list": "Standard Buying",
            "set_warehouse": self.warehouse or "Stores - BEI",
            "bei_goods_receipt": self.name,  # Reference back to BEI GR
            "items": pr_items
        })

        # Add rejected warehouse if there are rejections
        if self.total_rejected_qty > 0:
            pr.rejected_warehouse = "Rejected Warehouse - BEI"

        try:
            pr.insert(ignore_permissions=True)
            pr.submit()

            self.frappe_purchase_receipt = pr.name
            self.db_set("frappe_purchase_receipt", pr.name, update_modified=False)

            frappe.msgprint(
                _("Created and submitted Frappe Purchase Receipt: {0}").format(pr.name),
                indicator="green"
            )

            return pr.name

        except Exception as e:
            frappe.log_error(
                f"Failed to create Frappe PR for BEI GR {self.name}: {e}",
                "BEI GR Integration Error"
            )
            frappe.throw(
                _("Failed to create Frappe Purchase Receipt: {0}").format(str(e))
            )

    def _find_frappe_po_item(self, frappe_po_name, item_code):
        """
        Find the Purchase Order Item for proper linking.

        Returns: Purchase Order Item name or None
        """
        po_item = frappe.db.get_value(
            "Purchase Order Item",
            {
                "parent": frappe_po_name,
                "item_code": item_code
            },
            "name"
        )
        return po_item

    @frappe.whitelist()
    def force_create_purchase_receipt(self):
        """
        Force create Purchase Receipt even if inspection pending.
        Use only for emergency cases where goods need to be booked immediately.

        Requires Stock Manager role.
        """
        if not frappe.has_permission("BEI Goods Receipt", "write", self.name):
            frappe.throw(_("Insufficient permissions"))

        # Bypass inspection check
        original_status = self.status
        self.status = "Accepted"

        try:
            result = self.create_frappe_purchase_receipt()
            return result
        finally:
            # Restore original status if PR creation failed
            if not self.frappe_purchase_receipt:
                self.status = original_status
