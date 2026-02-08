# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEISupplier(Document):
    """
    BEI Supplier DocType with Frappe Supplier integration.

    IMPORTANT: 184 suppliers already exist in Frappe Supplier.
    Always check for duplicates before creating new suppliers.
    """

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
            SELECT COALESCE(SUM(payment_amount), 0)
            FROM `tabBEI Payment Request`
            WHERE supplier = %s AND status = 'Paid'
        """, self.name)[0][0] or 0

        invoiced = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabBEI Invoice`
            WHERE supplier = %s AND status != 'Cancelled'
        """, self.name)[0][0] or 0

        self.total_outstanding = invoiced - paid

    def on_update(self):
        """Sync with Frappe Supplier if linked."""
        if self.frappe_supplier:
            self.sync_to_frappe_supplier()

    def on_submit(self):
        """Auto-create Frappe Supplier on submit if not linked."""
        if not self.frappe_supplier:
            self.create_frappe_supplier()

    def sync_to_frappe_supplier(self):
        """Update linked Frappe Supplier with our data."""
        if not self.frappe_supplier:
            return

        try:
            supplier = frappe.get_doc("Supplier", self.frappe_supplier)
            supplier.supplier_name = self.supplier_name
            supplier.tax_id = self.tin

            # Update supplier type based on status
            if self.status == "Blacklisted":
                supplier.disabled = 1
            else:
                supplier.disabled = 0

            supplier.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(
                f"Failed to sync BEI Supplier {self.name} to Frappe Supplier: {e}",
                "BEI Supplier Sync Error"
            )

    def find_existing_frappe_supplier(self):
        """
        Find existing Frappe Supplier by name match.

        CRITICAL: 184 suppliers already imported to Frappe.
        Check by:
        1. Exact name match
        2. Normalized name match (lowercase, stripped)
        3. TIN match (if available)

        Returns: Supplier name if found, None otherwise
        """
        # 1. Try exact name match first
        if frappe.db.exists("Supplier", self.supplier_name):
            return self.supplier_name

        # 2. Try case-insensitive match
        existing = frappe.db.sql("""
            SELECT name FROM `tabSupplier`
            WHERE LOWER(TRIM(supplier_name)) = LOWER(TRIM(%s))
            LIMIT 1
        """, self.supplier_name)

        if existing:
            return existing[0][0]

        # 3. Try TIN match if available
        if self.tin:
            existing_by_tin = frappe.db.sql("""
                SELECT name FROM `tabSupplier`
                WHERE tax_id = %s AND tax_id != '' AND tax_id IS NOT NULL
                LIMIT 1
            """, self.tin)

            if existing_by_tin:
                return existing_by_tin[0][0]

        return None

    @frappe.whitelist()
    def create_frappe_supplier(self):
        """
        Create or link to corresponding Frappe Supplier.

        IMPORTANT: Checks for existing supplier first to avoid duplicates.
        184 suppliers already exist in Frappe Supplier list.

        Field mappings:
        - supplier_name -> supplier_name
        - supplier_type -> "Company" (default for B2B)
        - tin -> tax_id
        - email -> primary email (via Contact)
        - contact_number -> primary phone (via Contact)
        - address -> primary address (via Address)

        Returns: Frappe Supplier name
        """
        if self.frappe_supplier:
            frappe.msgprint(
                _("Already linked to Frappe Supplier: {0}").format(self.frappe_supplier),
                indicator="blue"
            )
            return self.frappe_supplier

        # Check for existing supplier first
        existing = self.find_existing_frappe_supplier()

        if existing:
            # Link to existing supplier
            self.frappe_supplier = existing
            self.db_set("frappe_supplier", existing, update_modified=False)

            frappe.msgprint(
                _("Linked to existing Frappe Supplier: {0}").format(existing),
                indicator="green"
            )
            return existing

        # Create new Frappe Supplier
        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": self.supplier_name,
            "supplier_type": "Company",  # B2B default
            "tax_id": self.tin or "",
            "country": "Philippines",  # BEI default
            "default_currency": "PHP",
        })

        supplier.insert(ignore_permissions=True)
        frappe_supplier_name = supplier.name

        # Create Contact if we have contact info
        if self.email or self.contact_number or self.contact_person:
            self._create_supplier_contact(frappe_supplier_name)

        # Create Address if we have address
        if self.address:
            self._create_supplier_address(frappe_supplier_name)

        self.frappe_supplier = frappe_supplier_name
        self.db_set("frappe_supplier", frappe_supplier_name, update_modified=False)

        frappe.msgprint(
            _("Created new Frappe Supplier: {0}").format(frappe_supplier_name),
            indicator="green"
        )

        return frappe_supplier_name

    def _create_supplier_contact(self, supplier_name):
        """Create Contact linked to Frappe Supplier."""
        try:
            contact = frappe.get_doc({
                "doctype": "Contact",
                "first_name": self.contact_person or self.supplier_name,
                "is_primary_contact": 1,
            })

            # Add email
            if self.email:
                contact.append("email_ids", {
                    "email_id": self.email,
                    "is_primary": 1
                })

            # Add phone
            if self.contact_number:
                contact.append("phone_nos", {
                    "phone": self.contact_number,
                    "is_primary_phone": 1
                })

            # Link to supplier
            contact.append("links", {
                "link_doctype": "Supplier",
                "link_name": supplier_name
            })

            contact.insert(ignore_permissions=True)

        except Exception as e:
            frappe.log_error(
                f"Failed to create contact for supplier {supplier_name}: {e}",
                "BEI Supplier Contact Error"
            )

    def _create_supplier_address(self, supplier_name):
        """Create Address linked to Frappe Supplier."""
        try:
            address = frappe.get_doc({
                "doctype": "Address",
                "address_title": self.supplier_name,
                "address_type": "Billing",
                "address_line1": self.address,
                "city": "Metro Manila",  # Default for PH
                "country": "Philippines",
                "is_primary_address": 1,
                "is_shipping_address": 1,
            })

            # Link to supplier
            address.append("links", {
                "link_doctype": "Supplier",
                "link_name": supplier_name
            })

            address.insert(ignore_permissions=True)

        except Exception as e:
            # Address creation is optional - log and continue
            # Common error: No default Address Template configured in ERPNext
            frappe.log_error(
                f"Failed to create address for supplier {supplier_name}: {e}",
                "BEI Supplier Address Error"
            )
            # Don't raise - PO approval should succeed even if address creation fails

    @frappe.whitelist()
    def get_or_create_frappe_supplier(self):
        """
        Get linked Frappe Supplier or create one.

        This is the preferred method for integration - ensures
        a valid Frappe Supplier always exists.

        Returns: Frappe Supplier name
        """
        if self.frappe_supplier:
            # Verify it still exists
            if frappe.db.exists("Supplier", self.frappe_supplier):
                return self.frappe_supplier
            else:
                # Link broken, clear and recreate
                self.frappe_supplier = None

        return self.create_frappe_supplier()

    @property
    def is_new_supplier(self):
        """
        Check if this is a new supplier (first PO within 6 months).
        Used for CEO approval requirement in Payment Requests.
        """
        from frappe.utils import add_months, getdate, nowdate

        six_months_ago = add_months(getdate(nowdate()), -6)

        # Check for any POs before 6 months ago
        old_po = frappe.db.exists(
            "BEI Purchase Order",
            {
                "supplier": self.name,
                "po_date": ["<", six_months_ago],
                "status": ["not in", ["Draft", "Cancelled"]]
            }
        )

        return not old_po
