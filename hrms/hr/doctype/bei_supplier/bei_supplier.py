# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEISupplier(Document):
    def validate(self):
        self.validate_supplier_code()
        self.validate_required_documents()

    def validate_supplier_code(self):
        """Ensure supplier code is unique and properly formatted."""
        if self.supplier_code:
            self.supplier_code = self.supplier_code.strip().upper()

    def validate_required_documents(self):
        """For Active status, require BIR and SEC documents."""
        if self.status == "Active":
            missing = []
            if not self.bir_2307:
                missing.append("BIR 2307")
            if not self.sec_certificate:
                missing.append("SEC Certificate")

            if missing:
                frappe.msgprint(
                    _("Warning: Active supplier missing required documents: {0}").format(
                        ", ".join(missing)
                    ),
                    indicator="orange",
                    alert=True
                )

    def before_save(self):
        self.update_metrics()

    def update_metrics(self):
        """Update calculated metrics from PO and payment data."""
        # Count POs
        po_count = frappe.db.count(
            "BEI Purchase Order",
            filters={"supplier": self.name, "docstatus": ["!=", 2]}
        )
        self.total_po_count = po_count

        # Sum PO value
        po_value = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabBEI Purchase Order`
            WHERE supplier = %s AND docstatus != 2
        """, self.name)[0][0] or 0
        self.total_po_value = po_value

        # Calculate outstanding from payment requests
        paid = frappe.db.sql("""
            SELECT COALESCE(SUM(net_amount), 0)
            FROM `tabBEI Payment Request`
            WHERE supplier = %s AND status = 'Paid'
        """, self.name)[0][0] or 0

        invoiced = frappe.db.sql("""
            SELECT COALESCE(SUM(invoice_amount), 0)
            FROM `tabBEI Invoice`
            WHERE supplier = %s
        """, self.name)[0][0] or 0

        self.total_outstanding = invoiced - paid

    def on_update(self):
        """Sync with Frappe Supplier if linked."""
        if self.frappe_supplier:
            self.sync_to_frappe_supplier()

    def sync_to_frappe_supplier(self):
        """Update linked Frappe Supplier with our data."""
        if not self.frappe_supplier:
            return

        try:
            supplier = frappe.get_doc("Supplier", self.frappe_supplier)
            supplier.supplier_name = self.supplier_name
            supplier.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(
                f"Failed to sync BEI Supplier {self.name} to Frappe Supplier: {e}",
                "BEI Supplier Sync Error"
            )

    @frappe.whitelist()
    def create_frappe_supplier(self):
        """Create corresponding Frappe Supplier."""
        if self.frappe_supplier:
            frappe.throw(_("Frappe Supplier already linked"))

        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": self.supplier_name,
            "supplier_type": "Company",
            "tax_id": self.tin
        })
        supplier.insert(ignore_permissions=True)

        self.frappe_supplier = supplier.name
        self.save()

        return supplier.name
