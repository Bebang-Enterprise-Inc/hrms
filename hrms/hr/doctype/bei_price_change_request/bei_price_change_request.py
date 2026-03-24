"""BEI Price Change Request controller.

S104: Manages the approval workflow for price changes.
Only the CPO (from BEI Settings) can approve price changes.
On approval, creates a new Item Price record (versioned) and expires the old one.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, today, add_days


class BEIPriceChangeRequest(Document):
    def before_insert(self):
        self.requested_by = frappe.session.user
        self.status = "Draft"

        # Auto-fill current price from Item Price
        from hrms.api.procurement import get_contracted_price
        contracted = get_contracted_price(self.item_code)
        if contracted:
            self.current_price = contracted["contracted_rate"]

    def submit_for_approval(self):
        """Submit for CPO approval."""
        if self.status != "Draft":
            frappe.throw(_("Only Draft requests can be submitted for approval"))

        if not self.reason:
            frappe.throw(_("Reason is required"))

        if not self.supporting_document:
            frappe.throw(_("Supporting document (supplier quote or market evidence) is required"))

        self.status = "Pending CPO Approval"
        self.save()

        # Notify CPO
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        settings = get_procurement_settings()
        cpo_email = settings.get("cpo_approver_email")
        if cpo_email:
            frappe.sendmail(
                recipients=[cpo_email],
                subject=f"Price Change Request: {self.item_code}",
                message=f"Price change requested for {self.item_code}: "
                        f"₱{flt(self.current_price, 2):,.2f} → ₱{flt(self.requested_price, 2):,.2f}. "
                        f"Reason: {self.reason}",
            )

        return {"success": True, "status": self.status}

    def approve(self, comment=None):
        """CPO approves the price change. Creates new Item Price, expires old one."""
        if self.status != "Pending CPO Approval":
            frappe.throw(_("Only requests pending CPO approval can be approved"))

        # Identity check — only CPO can approve
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        settings = get_procurement_settings()
        cpo_email = settings.get("cpo_approver_email")
        if frappe.session.user != cpo_email and frappe.session.user != "Administrator":
            frappe.throw(
                _("Only {0} (CPO) can approve price changes").format(cpo_email),
                title=_("Unauthorized")
            )

        # Get validity days
        validity_days = int(settings.get("price_validity_days") or 90)
        valid_from = today()
        valid_upto = add_days(valid_from, validity_days)

        # Expire old Item Price records for this item in Standard Buying
        from frappe.utils import add_days as _add_days
        yesterday = _add_days(today(), -1)
        old_prices = frappe.get_all("Item Price", filters={
            "item_code": self.item_code,
            "price_list": "Standard Buying",
            "buying": 1,
        }, fields=["name", "valid_upto"])

        for old in old_prices:
            # Only expire if not already expired
            if not old.valid_upto or str(old.valid_upto) >= today():
                frappe.db.set_value("Item Price", old.name, "valid_upto", yesterday,
                                   update_modified=False)

        # Create NEW Item Price record (versioned, not overwritten)
        new_ip = frappe.get_doc({
            "doctype": "Item Price",
            "item_code": self.item_code,
            "price_list": "Standard Buying",
            "price_list_rate": self.requested_price,
            "buying": 1,
            "selling": 0,
            "currency": "PHP",
            "valid_from": valid_from,
            "valid_upto": valid_upto,
        })
        new_ip.insert(ignore_permissions=True)

        # Create Price Change Log entry
        frappe.get_doc({
            "doctype": "BEI Price Change Log",
            "item_code": self.item_code,
            "before_price": self.current_price,
            "after_price": self.requested_price,
            "change_type": "Price Update",
            "reason": self.reason or comment or "",
            "supporting_document": self.supporting_document,
            "price_change_request": self.name,
            "approved_by": frappe.session.user,
            "approved_date": now_datetime(),
        }).insert(ignore_permissions=True)

        # Update request status
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_date = now_datetime()
        self.save()

        frappe.db.commit()
        return {"success": True, "status": "Approved", "new_item_price": new_ip.name}

    def reject(self, reason=None):
        """CPO rejects the price change request."""
        if self.status != "Pending CPO Approval":
            frappe.throw(_("Only requests pending CPO approval can be rejected"))

        # Identity check
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        cpo_email = get_procurement_settings().get("cpo_approver_email")
        if frappe.session.user != cpo_email and frappe.session.user != "Administrator":
            frappe.throw(
                _("Only {0} (CPO) can reject price changes").format(cpo_email),
                title=_("Unauthorized")
            )

        if not reason:
            frappe.throw(_("Rejection reason is required"))

        self.status = "Rejected"
        self.approved_by = frappe.session.user
        self.approved_date = now_datetime()
        self.rejection_reason = reason
        self.save()

        return {"success": True, "status": "Rejected"}
