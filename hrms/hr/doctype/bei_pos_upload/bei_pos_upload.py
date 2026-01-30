# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json


class BEIPOSUpload(Document):
    def before_insert(self):
        if not self.uploaded_by:
            self.uploaded_by = frappe.session.user

    def after_insert(self):
        """Auto-extract data from uploaded POS files."""
        self.extract_pos_data()

    def on_update(self):
        """Re-extract if files changed."""
        # Check if any file fields changed
        if self.has_value_changed("sales_summary") or \
           self.has_value_changed("transaction_report") or \
           self.has_value_changed("discount_report") or \
           self.has_value_changed("daily_sales_revenue") or \
           self.has_value_changed("product_mix"):
            self.extract_pos_data()

    def extract_pos_data(self):
        """Extract data from uploaded POS files and populate fields."""
        from hrms.utils.pos_parser import extract_all_pos_data

        try:
            # Get file contents
            sales_summary_content = self.get_file_content(self.sales_summary)
            transaction_report_content = self.get_file_content(self.transaction_report)
            discount_report_content = self.get_file_content(self.discount_report)
            daily_sales_revenue_content = self.get_file_content(self.daily_sales_revenue)
            product_mix_content = self.get_file_content(self.product_mix)

            # Extract data
            result = extract_all_pos_data(
                sales_summary_content=sales_summary_content,
                transaction_report_content=transaction_report_content,
                discount_report_content=discount_report_content,
                daily_sales_revenue_content=daily_sales_revenue_content,
                product_mix_content=product_mix_content
            )

            if result.get("success") and result.get("consolidated"):
                data = result["consolidated"]

                # Update fields directly in DB to avoid infinite loop
                updates = {
                    "gross_sales": data.get("gross_sales", 0),
                    "net_sales": data.get("net_sales", 0),
                    "vat_amount": data.get("vat", 0),
                    "beginning_si": data.get("beginning_si", 0),
                    "ending_si": data.get("ending_si", 0),
                    "transaction_count": data.get("transaction_count", 0),
                    "eod_counter": data.get("eod_counter", 0),
                    "discount_pwd": data.get("discount_pwd", 0),
                    "discount_senior": data.get("discount_senior", 0),
                    "discount_other": data.get("discount_other", 0),
                    "total_discount": data.get("total_discount", 0),
                    "vat_adjustment": data.get("vat_adjustment", 0),
                    "extracted_data": json.dumps(data, default=str),
                    "status": "Extracted"
                }

                for field, value in updates.items():
                    self.db_set(field, value, update_modified=False)

                frappe.msgprint(
                    f"POS data extracted successfully: "
                    f"Gross Sales ₱{data.get('gross_sales', 0):,.2f}, "
                    f"Net Sales ₱{data.get('net_sales', 0):,.2f}",
                    indicator="green",
                    alert=True
                )

            else:
                errors = result.get("errors", [])
                if errors:
                    frappe.log_error(
                        f"POS extraction errors: {errors}",
                        "BEI POS Upload"
                    )

        except Exception as e:
            frappe.log_error(
                f"POS extraction failed for {self.name}: {str(e)}",
                "BEI POS Upload"
            )

    def get_file_content(self, file_url):
        """Get file content from Frappe file URL."""
        if not file_url:
            return None

        try:
            file_doc = frappe.get_doc("File", {"file_url": file_url})
            return file_doc.get_content()
        except Exception:
            # Try direct file path
            if file_url.startswith("/files/"):
                import os
                file_path = frappe.get_site_path("public", file_url.lstrip("/"))
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        return f.read()
            return None

    @frappe.whitelist()
    def reextract(self):
        """Manually trigger re-extraction of POS data."""
        self.extract_pos_data()
        frappe.msgprint("POS data re-extracted", indicator="green")
