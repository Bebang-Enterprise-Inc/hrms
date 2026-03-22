# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class BEIEditRequest(Document):
    """Employee data edit request for HR approval."""

    # Field name to human-readable label mapping
    FIELD_LABELS = {
        "first_name": "First Name",
        "middle_name": "Middle Name",
        "last_name": "Last Name",
        "date_of_birth": "Date of Birth",
        "marital_status": "Marital Status",
        "ctc_sss": "SSS Number",
        "ctc_tin": "TIN",
        "ctc_philhealth": "PhilHealth Number",
        "ctc_pagibig": "Pag-IBIG Number",
        "custom_nickname": "Nickname",
    }

    def before_insert(self):
        """Set computed fields before insert."""
        self.submission_date = now_datetime()

        # Set field label from mapping
        if self.field_name and not self.field_label:
            self.field_label = self.FIELD_LABELS.get(self.field_name, self.field_name)

        # Fetch current value from employee
        if self.employee and self.field_name and not self.current_value:
            current = frappe.db.get_value("Employee", self.employee, self.field_name)
            self.current_value = str(current) if current else ""

    def validate(self):
        """Validate the edit request."""
        # Ensure requested value is different from current
        if self.requested_value == self.current_value:
            frappe.throw(_("Requested value must be different from current value"))

        # Validate employee exists
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw(_("Employee {0} not found").format(self.employee))

    def on_update(self):
        """Handle status changes."""
        if self.has_value_changed("status"):
            if self.status == "Approved":
                self._apply_change()
                self._notify_employee_approved()
            elif self.status == "Rejected":
                self._notify_employee_rejected()
            elif self.status == "More Info Needed":
                self._notify_employee_more_info()

    def _apply_change(self):
        """Apply the approved change to the employee record."""
        try:
            # Use db.set_value to bypass document validation (some employees
            # may have data quality issues like missing naming_series)
            frappe.db.set_value(
                "Employee",
                self.employee,
                self.field_name,
                self.requested_value,
                update_modified=True,
            )

            # Get employee name for the message
            emp_name = frappe.db.get_value("Employee", self.employee, "employee_name")

            frappe.msgprint(
                _("Employee {0} field '{1}' updated to '{2}'").format(
                    emp_name, self.field_label, self.requested_value
                )
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to apply edit request {self.name}: {e}",
                "BEI Edit Request Error",
            )
            frappe.throw(_("Failed to apply change: {0}").format(str(e)))

    def _notify_employee_approved(self):
        """Send notification to employee that request was approved."""
        try:
            emp = frappe.get_doc("Employee", self.employee)
            if emp.user_id:
                frappe.sendmail(
                    recipients=[emp.user_id],
                    subject=_("Your Edit Request Approved"),
                    message=_(
                        """
                        <p>Your request to change <strong>{field}</strong> has been approved.</p>
                        <p><strong>New Value:</strong> {value}</p>
                        <p>Your profile has been updated.</p>
                        """
                    ).format(field=self.field_label, value=self.requested_value),
                )
        except Exception:
            pass  # Don't fail if notification fails

    def _notify_employee_rejected(self):
        """Send notification to employee that request was rejected."""
        try:
            emp = frappe.get_doc("Employee", self.employee)
            if emp.user_id:
                frappe.sendmail(
                    recipients=[emp.user_id],
                    subject=_("Your Edit Request Rejected"),
                    message=_(
                        """
                        <p>Your request to change <strong>{field}</strong> has been rejected.</p>
                        <p><strong>HR Notes:</strong> {notes}</p>
                        <p>Please contact HR if you have questions.</p>
                        """
                    ).format(field=self.field_label, notes=self.hr_notes or "No notes provided"),
                )
        except Exception:
            pass

    def _notify_employee_more_info(self):
        """Send notification to employee that more info is needed."""
        try:
            emp = frappe.get_doc("Employee", self.employee)
            if emp.user_id:
                frappe.sendmail(
                    recipients=[emp.user_id],
                    subject=_("More Information Needed for Edit Request"),
                    message=_(
                        """
                        <p>HR needs more information for your request to change <strong>{field}</strong>.</p>
                        <p><strong>HR Notes:</strong> {notes}</p>
                        <p>Please update your request with additional documentation.</p>
                        """
                    ).format(field=self.field_label, notes=self.hr_notes or ""),
                )
        except Exception:
            pass
