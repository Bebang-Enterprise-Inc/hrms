# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate


class BEIClearance(Document):
    """Submittable parent doctype for an employee clearance.

    Lifecycle:
        Draft -> In Progress -> Pending Approval -> Approved -> Released

    On submit (`docstatus 0 -> 1`), the linked Employee transitions to
    `status="Left"` with the relieving date copied from the linked
    Employee Separation. ADMS biometric de-enrollment is OUT OF SCOPE for
    this minimum-viable doctype (handled by the separate transfer/separation
    ADMS workflow — see MEMORY lesson #21).
    """

    def validate(self):
        """All items must be in a terminal state before submit."""
        if not self.items:
            return
        if self.docstatus == 0:
            return  # only enforce on submit
        terminal = {"Returned", "Waived", "Missing"}
        pending = [
            row.station for row in self.items if (row.status or "Pending") not in terminal
        ]
        if pending:
            frappe.throw(
                _("Cannot submit clearance — these stations still have Pending items: {0}").format(
                    ", ".join(pending)
                )
            )

    def before_submit(self):
        """Run validation again right before docstatus flip."""
        terminal = {"Returned", "Waived", "Missing"}
        pending = [
            row.station for row in (self.items or []) if (row.status or "Pending") not in terminal
        ]
        if pending:
            frappe.throw(
                _("Cannot submit clearance — these stations still have Pending items: {0}").format(
                    ", ".join(pending)
                )
            )

    def on_submit(self):
        """Transition the linked Employee to status='Left'.

        Uses `frappe.db.set_value` (NOT the Employee ORM) to avoid the
        well-known Employee write trap (MEMORY lesson #6). Wraps the write
        in try/except with explicit rollback so a failed transition surfaces
        as an error rather than a silent partial state.
        """
        if not self.employee:
            return
        relieving_date = self.relieving_date or nowdate()
        try:
            frappe.db.set_value(
                "Employee",
                self.employee,
                {
                    "status": "Left",
                    "relieving_date": relieving_date,
                },
                update_modified=True,
            )
            frappe.db.commit()
            self.db_set("status", "Released")
            self.db_set("approved_on", nowdate())
            self.db_set("approved_by", frappe.session.user)
        except Exception as exc:
            frappe.db.rollback()
            frappe.log_error(
                title="S170 BEI Clearance on_submit",
                message=f"Failed to transition employee {self.employee} to Left: {exc}",
            )
            raise

    def on_cancel(self):
        """Best-effort revert: set the employee back to Active.

        This does NOT restore prior `status` history — admin should review.
        """
        if not self.employee:
            return
        try:
            frappe.db.set_value(
                "Employee",
                self.employee,
                {"status": "Active"},
                update_modified=True,
            )
            frappe.db.commit()
        except Exception as exc:
            frappe.db.rollback()
            frappe.log_error(
                title="S170 BEI Clearance on_cancel",
                message=f"Failed to revert employee {self.employee}: {exc}",
            )
            raise
