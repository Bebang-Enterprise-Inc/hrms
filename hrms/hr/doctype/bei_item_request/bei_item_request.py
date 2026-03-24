"""BEI Item Request controller.

S104: Manages the approval workflow for new items in the procurement system.
Only the CPO (from BEI Settings) can approve new items.
On approval, creates the Frappe Item + Item Price + Price Change Log.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, today, add_days


class BEIItemRequest(Document):
    def before_insert(self):
        self.requested_by = frappe.session.user
        self.status = "Draft"

        # Validate item code doesn't already exist
        if frappe.db.exists("Item", self.item_code):
            frappe.throw(_("Item {0} already exists in Frappe. "
                          "Use a Price Change Request to update its price.").format(self.item_code))

    def submit_for_approval(self):
        """Submit for CPO approval."""
        if self.status != "Draft":
            frappe.throw(_("Only Draft requests can be submitted for approval"))

        self.status = "Pending CPO Approval"
        self.save(ignore_permissions=True)

        # Notify CPO
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        cpo_email = get_procurement_settings().get("cpo_approver_email")
        if cpo_email:
            frappe.sendmail(
                recipients=[cpo_email],
                subject=f"New Item Request: {self.item_code}",
                message=f"New item requested: {self.item_code} ({self.item_name}), "
                        f"contracted price ₱{flt(self.contracted_unit_cost, 2):,.2f}. "
                        f"Justification: {self.cost_justification}",
            )

        return {"success": True, "status": self.status}

    def approve(self):
        """CPO approves the new item request.

        Creates: Frappe Item + Item Price in Standard Buying + Price Change Log.
        """
        if self.status != "Pending CPO Approval":
            frappe.throw(_("Only requests pending CPO approval can be approved"))

        # Identity check
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        settings = get_procurement_settings()
        cpo_email = settings.get("cpo_approver_email")
        if frappe.session.user != cpo_email and frappe.session.user != "Administrator":
            frappe.throw(
                _("Only {0} (CPO) can approve new items").format(cpo_email),
                title=_("Unauthorized")
            )

        validity_days = int(settings.get("price_validity_days") or 90)

        # Map item_group select value to Frappe Item Group
        group_map = {
            "Raw Material": "Raw Material",
            "Finished Goods": "Finished Goods",
            "Packaging Material": "Packaging Material",
            "Consumables": "Consumables",
            "Supplies": "Consumables",  # fallback
        }
        frappe_group = group_map.get(self.item_group, "All Item Groups")

        # Ensure the item group exists
        if not frappe.db.exists("Item Group", frappe_group):
            frappe_group = "All Item Groups"

        # 1. Create Frappe Item
        new_item = frappe.get_doc({
            "doctype": "Item",
            "item_code": self.item_code,
            "item_name": self.item_name,
            "description": self.description or self.item_name,
            "item_group": frappe_group,
            "stock_uom": self.stock_uom,
            "is_stock_item": 1,
            "is_purchase_item": 1,
            "include_item_in_manufacturing": 0,
        })
        new_item.insert(ignore_permissions=True)

        # 2. Create Item Price in Standard Buying
        new_ip = frappe.get_doc({
            "doctype": "Item Price",
            "item_code": self.item_code,
            "price_list": "Standard Buying",
            "price_list_rate": self.contracted_unit_cost,
            "buying": 1,
            "selling": 0,
            "currency": "PHP",
            "valid_from": today(),
            "valid_upto": add_days(today(), validity_days),
        })
        new_ip.insert(ignore_permissions=True)

        # 3. Create Price Change Log as "Initial Price"
        frappe.get_doc({
            "doctype": "BEI Price Change Log",
            "item_code": self.item_code,
            "before_price": 0,
            "after_price": self.contracted_unit_cost,
            "change_type": "Initial Price",
            "reason": self.cost_justification,
            "supporting_document": self.supporting_document,
            "approved_by": frappe.session.user,
            "approved_date": now_datetime(),
        }).insert(ignore_permissions=True)

        # Update request status
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_date = now_datetime()
        self.save(ignore_permissions=True)

        frappe.db.commit()
        return {
            "success": True,
            "status": "Approved",
            "item": self.item_code,
            "item_price": new_ip.name,
        }

    def reject(self, reason=None):
        """CPO rejects the new item request."""
        if self.status != "Pending CPO Approval":
            frappe.throw(_("Only requests pending CPO approval can be rejected"))

        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        cpo_email = get_procurement_settings().get("cpo_approver_email")
        if frappe.session.user != cpo_email and frappe.session.user != "Administrator":
            frappe.throw(
                _("Only {0} (CPO) can reject new item requests").format(cpo_email),
                title=_("Unauthorized")
            )

        if not reason:
            frappe.throw(_("Rejection reason is required"))

        self.status = "Rejected"
        self.approved_by = frappe.session.user
        self.approved_date = now_datetime()
        self.rejection_reason = reason
        self.save(ignore_permissions=True)

        return {"success": True, "status": "Rejected"}
