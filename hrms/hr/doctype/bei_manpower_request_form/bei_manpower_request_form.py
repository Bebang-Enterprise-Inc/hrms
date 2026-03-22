"""BEI Manpower Request Form DocType"""

import frappe
from frappe import _
from frappe.model.document import Document


class BEIManpowerRequestForm(Document):
    """Manpower Request Form for recruitment pipeline."""

    def validate(self):
        """Validate MRF before save."""
        # Ensure requesting_department matches requested_by's department
        if self.requested_by:
            emp_dept = frappe.db.get_value("Employee", self.requested_by, "department")
            if emp_dept and emp_dept != self.requesting_department:
                frappe.msgprint(
                    _(
                        f"Requested by employee belongs to {emp_dept}, "
                        f"but requesting department is {self.requesting_department}"
                    ),
                    indicator="orange",
                    alert=True,
                )

        # Replacement reason requires replaced_employee
        if self.reason == "Replacement" and not self.replaced_employee:
            frappe.throw(_("Please specify the replaced employee for replacement positions"))

        # Salary range validation
        if self.salary_range_min and self.salary_range_max:
            if self.salary_range_min > self.salary_range_max:
                frappe.throw(_("Salary range minimum cannot exceed maximum"))

    def on_submit(self):
        """Auto-transition to Pending Hiring Manager status on submit."""
        if self.status == "Draft":
            self.db_set("status", "Pending Hiring Manager")
            frappe.msgprint(
                _("MRF submitted and forwarded to Hiring Manager for approval"),
                indicator="green",
                alert=True,
            )

    def on_cancel(self):
        """Set status to Cancelled on cancel."""
        self.db_set("status", "Cancelled")
