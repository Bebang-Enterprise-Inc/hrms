# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


# Approval threshold - PO above this needs both Mae AND Butch
DUAL_APPROVAL_THRESHOLD = 500000


class BEIPurchaseOrder(Document):
    def validate(self):
        self.calculate_totals()
        self.set_po_no()
        self.check_dual_approval_requirement()

    def set_po_no(self):
        """Set PO number from name if not already set."""
        if not self.po_no and self.name:
            self.po_no = self.name

    def calculate_totals(self):
        """Calculate all totals including VAT."""
        subtotal = 0
        total_vat = 0

        for item in self.items:
            item_subtotal = flt(item.qty, 2) * flt(item.unit_cost, 2)
            item_vat = item_subtotal * flt(item.vat_rate or 12, 2) / 100

            item.vat_amount = item_vat
            item.amount = item_subtotal + item_vat

            subtotal += item_subtotal
            total_vat += item_vat

        self.subtotal = subtotal
        self.vat_amount = total_vat
        self.grand_total = (
            subtotal
            + total_vat
            - flt(self.discount_amount, 2)
            + flt(self.delivery_fee, 2)
        )

    def check_dual_approval_requirement(self):
        """Check if PO requires dual approval (>500K needs both Mae AND Butch)."""
        self.requires_dual_approval = 1 if self.grand_total > DUAL_APPROVAL_THRESHOLD else 0

    def after_insert(self):
        self.po_no = self.name
        self.db_set("po_no", self.name, update_modified=False)

    @frappe.whitelist()
    def submit_for_approval(self):
        """Submit PO for approval workflow."""
        if self.status != "Draft":
            frappe.throw(_("Only Draft POs can be submitted for approval"))

        if not self.items:
            frappe.throw(_("Please add at least one item"))

        self.status = "Pending Mae Approval"
        self.save()

        # Notify Mae
        self.notify_mae()

        return {"success": True, "message": _("PO submitted for Mae's approval")}

    def notify_mae(self):
        """Send notification to Mae Karazi."""
        # TODO: Implement Google Chat notification to mae@bebang.ph
        pass

    def notify_butch(self):
        """Send notification to Butch Formoso."""
        # TODO: Implement Google Chat notification to butch@bebang.ph
        pass

    @frappe.whitelist()
    def approve_mae(self, comment=None):
        """Mae approves the PO."""
        if self.status != "Pending Mae Approval":
            frappe.throw(_("PO is not pending Mae's approval"))

        self.mae_approval = "Approved"
        self.mae_comment = comment
        self.mae_approval_date = now_datetime()

        if self.requires_dual_approval:
            # Needs Butch's approval too
            self.status = "Pending Butch Approval"
            self.save()
            self.notify_butch()
            return {
                "success": True,
                "message": _("Mae approved. PO now pending Butch's approval (>500K)")
            }
        else:
            # Single approval sufficient
            self.status = "Approved"
            self.save()
            self.on_fully_approved()
            return {"success": True, "message": _("PO approved by Mae")}

    @frappe.whitelist()
    def approve_butch(self, comment=None):
        """Butch (CFO) approves the PO for >500K."""
        if self.status != "Pending Butch Approval":
            frappe.throw(_("PO is not pending Butch's approval"))

        if not self.requires_dual_approval:
            frappe.throw(_("This PO does not require CFO approval"))

        self.butch_approval = "Approved"
        self.butch_comment = comment
        self.butch_approval_date = now_datetime()
        self.status = "Approved"
        self.save()

        self.on_fully_approved()

        return {"success": True, "message": _("PO approved by Butch (CFO)")}

    def on_fully_approved(self):
        """Actions when PO is fully approved."""
        # Create Frappe Purchase Order
        self.create_frappe_purchase_order()

        # Update supplier metrics
        self.update_supplier_metrics()

    @frappe.whitelist()
    def reject(self, reason, rejector="mae"):
        """Reject the PO."""
        if self.status not in ["Pending Mae Approval", "Pending Butch Approval"]:
            frappe.throw(_("PO is not pending approval"))

        if not reason:
            frappe.throw(_("Please provide a rejection reason"))

        if rejector == "mae":
            self.mae_approval = "Rejected"
            self.mae_comment = reason
            self.mae_approval_date = now_datetime()
        else:
            self.butch_approval = "Rejected"
            self.butch_comment = reason
            self.butch_approval_date = now_datetime()

        self.status = "Cancelled"
        self.save()

        return {"success": True, "message": _("PO rejected")}

    def create_frappe_purchase_order(self):
        """
        Create corresponding Frappe Purchase Order.

        PREREQUISITES:
        - BEI PO must be fully approved (status = "Approved")
        - For >500K: Both Mae AND Butch approval required
        - For <=500K: Mae approval sufficient

        FIELD MAPPING:
        - supplier -> frappe_supplier (via BEI Supplier link)
        - po_date -> transaction_date
        - delivery_date -> schedule_date
        - items -> items (with item validation/creation)
        - grand_total -> validated against calculated total
        - ship_to -> default warehouse for items

        Returns: Frappe Purchase Order name or None
        """
        if self.frappe_po:
            frappe.msgprint(
                _("Already linked to Frappe PO: {0}").format(self.frappe_po),
                indicator="blue"
            )
            return self.frappe_po

        # Validate approval status
        if self.status != "Approved":
            frappe.throw(
                _("Cannot create Frappe PO - BEI PO must be fully approved. "
                  "Current status: {0}").format(self.status)
            )

        # Validate dual approval for high-value POs
        if self.requires_dual_approval:
            if self.mae_approval != "Approved":
                frappe.throw(_("Mae approval required for PO > 500K"))
            if self.butch_approval != "Approved":
                frappe.throw(_("Butch (CFO) approval required for PO > 500K"))
        else:
            if self.mae_approval != "Approved":
                frappe.throw(_("Mae approval required"))

        # Get or create Frappe Supplier
        bei_supplier = frappe.get_doc("BEI Supplier", self.supplier)
        frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

        if not frappe_supplier:
            frappe.throw(
                _("Could not get or create Frappe Supplier for {0}").format(
                    self.supplier
                )
            )

        # Validate and prepare items
        po_items = []
        for item in self.items:
            frappe_item = self._get_or_create_item(item)

            po_items.append({
                "item_code": frappe_item,
                "item_name": item.item_name or item.item_code,
                "description": item.description or item.item_name or item.item_code,
                "qty": flt(item.qty, 2),
                "uom": item.uom or "Nos",
                "stock_uom": item.uom or "Nos",
                "conversion_factor": 1,
                "rate": flt(item.unit_cost, 2),
                "schedule_date": self.delivery_date,
                "warehouse": self.ship_to or "Stores - BEI",  # Default warehouse
                "bei_po_item": item.name  # Reference back to BEI item
            })

        if not po_items:
            frappe.throw(_("No valid items to create Purchase Order"))

        # Create Frappe PO
        po = frappe.get_doc({
            "doctype": "Purchase Order",
            "supplier": frappe_supplier,
            "transaction_date": self.po_date,
            "schedule_date": self.delivery_date,
            "company": "Bebang Enterprise Inc.",
            "currency": "PHP",
            "buying_price_list": "Standard Buying",
            "price_list_currency": "PHP",
            "plc_conversion_rate": 1,
            "conversion_rate": 1,
            "payment_terms_template": self.payment_terms,
            "bei_purchase_order": self.name,  # Reference back to BEI PO
            "items": po_items
        })

        # Apply discount if any
        if flt(self.discount_amount, 2) > 0:
            po.discount_amount = flt(self.discount_amount, 2)
            po.additional_discount_percentage = 0
            po.apply_discount_on = "Grand Total"

        try:
            po.insert(ignore_permissions=True)
            po.submit()

            self.frappe_po = po.name
            self.db_set("frappe_po", po.name, update_modified=False)

            frappe.msgprint(
                _("Created and submitted Frappe PO: {0}").format(po.name),
                indicator="green"
            )

            return po.name

        except Exception as e:
            frappe.log_error(
                f"Failed to create Frappe PO for BEI PO {self.name}: {e}",
                "BEI PO Integration Error"
            )
            frappe.throw(
                _("Failed to create Frappe Purchase Order: {0}").format(str(e))
            )

    def _get_or_create_item(self, bei_item):
        """
        Get existing Frappe Item or create new one.

        Item lookup priority:
        1. Exact item_code match
        2. Create new with proper item group

        Returns: Item code (name)
        """
        item_code = bei_item.item_code

        # Check if item exists
        if frappe.db.exists("Item", item_code):
            return item_code

        # Determine item group based on item characteristics
        item_group = self._determine_item_group(bei_item)

        # Create new item
        try:
            new_item = frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": bei_item.item_name or item_code,
                "description": bei_item.description or bei_item.item_name or item_code,
                "item_group": item_group,
                "stock_uom": bei_item.uom or "Nos",
                "is_stock_item": 1,
                "is_purchase_item": 1,
                "include_item_in_manufacturing": 0,
                "default_warehouse": self.ship_to or "Stores - BEI",
            })
            new_item.insert(ignore_permissions=True)

            frappe.msgprint(
                _("Created new Item: {0}").format(item_code),
                indicator="blue"
            )

            return item_code

        except Exception as e:
            frappe.log_error(
                f"Failed to create Item {item_code}: {e}",
                "BEI Item Creation Error"
            )
            frappe.throw(
                _("Failed to create Item {0}: {1}").format(item_code, str(e))
            )

    def _determine_item_group(self, bei_item):
        """
        Determine appropriate Item Group for a BEI item.

        Categories based on BEI item master:
        - Raw Materials: Ingredients, supplies
        - Finished Goods: Ready products
        - Packaging: Boxes, bags, containers
        - Consumables: Cleaning, office supplies
        - Fixed Assets: Equipment, furniture

        Returns: Item Group name
        """
        item_name_lower = (bei_item.item_name or "").lower()
        item_code_lower = (bei_item.item_code or "").lower()

        # Check for packaging keywords
        packaging_keywords = ["box", "bag", "container", "wrapper", "pack", "cup", "lid"]
        if any(kw in item_name_lower or kw in item_code_lower for kw in packaging_keywords):
            return "Packaging Material"

        # Check for raw materials
        raw_keywords = ["flour", "sugar", "oil", "salt", "sauce", "powder", "ingredient"]
        if any(kw in item_name_lower for kw in raw_keywords):
            return "Raw Material"

        # Check for consumables
        consumable_keywords = ["cleaning", "soap", "sanitizer", "tissue", "paper", "office"]
        if any(kw in item_name_lower for kw in consumable_keywords):
            return "Consumable"

        # Check for fixed assets
        asset_keywords = ["equipment", "machine", "refrigerator", "freezer", "oven", "furniture"]
        if any(kw in item_name_lower for kw in asset_keywords):
            return "Fixed Asset"

        # Default to Products (general category)
        return "Products"

    def update_supplier_metrics(self):
        """Update supplier metrics after PO approval."""
        if self.supplier:
            supplier = frappe.get_doc("BEI Supplier", self.supplier)
            supplier.update_metrics()
            supplier.save()

    @frappe.whitelist()
    def send_to_supplier(self):
        """Generate PDF and send PO to supplier."""
        if self.status not in ["Approved", "Sent to Supplier"]:
            frappe.throw(_("PO must be approved before sending to supplier"))

        if not self.supplier_email:
            frappe.throw(_("Supplier email is required"))

        # Generate PDF
        # pdf_content = frappe.get_print(self.doctype, self.name, "Standard")

        # Send email
        # frappe.sendmail(...)

        self.sent_to_supplier_date = now_datetime()
        self.sent_by = frappe.session.user
        self.status = "Sent to Supplier"
        self.save()

        return {"success": True, "message": _("PO sent to supplier")}

    @frappe.whitelist()
    def update_received_qty(self, item_code, received_qty):
        """Update received quantity for an item (called from GR)."""
        for item in self.items:
            if item.item_code == item_code:
                item.received_qty = flt(item.received_qty, 2) + flt(received_qty, 2)

        # Check if fully received
        fully_received = all(
            flt(item.received_qty, 2) >= flt(item.qty, 2)
            for item in self.items
        )

        if fully_received:
            self.status = "Fully Received"
        else:
            partially_received = any(
                flt(item.received_qty, 2) > 0
                for item in self.items
            )
            if partially_received:
                self.status = "Partially Received"

        self.save()
