# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Mall Permit Registry API
Centralized registry for store delivery/loading permits with expiry tracking.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, date_diff, add_days


# RBAC roles for permit management
SCM_PERMIT_ROLES = {"Warehouse Manager", "Logistics Coordinator", "HR Manager", "System Manager"}


def _check_permit_permission(action="access permit records"):
    """Check if current user has any of the allowed roles."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(SCM_PERMIT_ROLES):
        frappe.throw(
            _("You do not have permission to {0}").format(action),
            frappe.PermissionError
        )


@frappe.whitelist()
def get_permits(store=None, status=None):
    """
    GET list of mall permits with optional filters.

    Args:
        store (str, optional): Filter by Warehouse name
        status (str, optional): Filter by status (Active, Expiring Soon, Expired, Renewal Pending)

    Returns:
        list: Permit records with fields needed for the registry table
    """
    _check_permit_permission("view permit records")

    filters = {}
    if store:
        filters["store"] = store
    if status:
        filters["status"] = status

    permits = frappe.get_all(
        "BEI Mall Permit",
        filters=filters,
        fields=[
            "name",
            "store",
            "store_name",
            "permit_type",
            "permit_number",
            "issued_date",
            "expiry_date",
            "status",
            "renewal_contact",
            "renewal_cost",
            "document",
            "notes",
        ],
        order_by="expiry_date asc",
    )

    # Annotate with days_remaining for UI display
    today = getdate(nowdate())
    for p in permits:
        if p.get("expiry_date"):
            p["days_remaining"] = date_diff(getdate(p["expiry_date"]), today)
        else:
            p["days_remaining"] = None

    return permits


@frappe.whitelist()
def create_permit(store, permit_type, expiry_date, permit_number=None,
                  issued_date=None, renewal_contact=None, renewal_cost=None,
                  document=None, notes=None):
    """
    POST create a new mall permit.

    Args:
        store (str): Warehouse name (required)
        permit_type (str): e.g. "Delivery Permit", "Loading/Unloading Permit" (required)
        expiry_date (str): YYYY-MM-DD (required)
        permit_number (str, optional): Official permit number
        issued_date (str, optional): YYYY-MM-DD
        renewal_contact (str, optional): Contact person for renewal
        renewal_cost (float, optional): Cost to renew in PHP
        document (str, optional): Attached file URL
        notes (str, optional): Additional notes

    Returns:
        dict: Created permit name and status
    """
    _check_permit_permission("create permit records")

    permit = frappe.get_doc({
        "doctype": "BEI Mall Permit",
        "store": store,
        "permit_type": permit_type,
        "expiry_date": expiry_date,
        "permit_number": permit_number,
        "issued_date": issued_date,
        "renewal_contact": renewal_contact,
        "renewal_cost": renewal_cost,
        "document": document,
        "notes": notes,
    })
    permit.insert(ignore_permissions=True)

    return {
        "success": True,
        "permit_name": permit.name,
        "status": permit.status,
        "message": _("Permit {0} created successfully").format(permit.name),
    }


@frappe.whitelist()
def update_permit(permit_name, updates):
    """
    POST update fields on an existing permit.

    Args:
        permit_name (str): BEI Mall Permit name (e.g. BEI-PERMIT-0001)
        updates (dict): Fields to update. Allowed fields:
            permit_type, permit_number, issued_date, expiry_date,
            status, renewal_contact, renewal_cost, document, notes

    Returns:
        dict: Updated permit name and new status
    """
    _check_permit_permission("update permit records")

    if isinstance(updates, str):
        import json
        updates = json.loads(updates)

    ALLOWED_FIELDS = {
        "permit_type", "permit_number", "issued_date", "expiry_date",
        "status", "renewal_contact", "renewal_cost", "document", "notes",
    }

    permit = frappe.get_doc("BEI Mall Permit", permit_name)

    for field, value in updates.items():
        if field in ALLOWED_FIELDS:
            setattr(permit, field, value)

    permit.save(ignore_permissions=True)

    return {
        "success": True,
        "permit_name": permit.name,
        "status": permit.status,
        "message": _("Permit {0} updated successfully").format(permit.name),
    }


@frappe.whitelist()
def get_expiring_permits(days=30):
    """
    GET permits expiring within N days from today.

    Args:
        days (int): Look-ahead window in days (default: 30)

    Returns:
        list: Permits expiring within the given window, sorted by expiry_date
    """
    _check_permit_permission("view permit records")

    days = int(days)
    today = nowdate()
    cutoff = add_days(today, days)

    permits = frappe.db.sql(
        """
        SELECT
            name, store, store_name, permit_type, permit_number,
            expiry_date, status, renewal_contact, renewal_cost,
            DATEDIFF(expiry_date, CURDATE()) AS days_remaining
        FROM `tabBEI Mall Permit`
        WHERE expiry_date >= %(today)s
          AND expiry_date <= %(cutoff)s
          AND status != 'Expired'
        ORDER BY expiry_date ASC
        """,
        {"today": today, "cutoff": cutoff},
        as_dict=True,
    )

    return permits


@frappe.whitelist()
def get_permit_summary():
    """
    GET summary counts: total active, expiring soon, expired, renewal pending.

    Returns:
        dict: Counts per status plus total
    """
    _check_permit_permission("view permit records")

    rows = frappe.db.sql(
        """
        SELECT status, COUNT(*) AS count
        FROM `tabBEI Mall Permit`
        GROUP BY status
        """,
        as_dict=True,
    )

    summary = {
        "Active": 0,
        "Expiring Soon": 0,
        "Expired": 0,
        "Renewal Pending": 0,
        "total": 0,
    }

    for row in rows:
        if row["status"] in summary:
            summary[row["status"]] = row["count"]
        summary["total"] += row["count"]

    return summary


# ─── Scheduler job ────────────────────────────────────────────────────────────

def check_permit_expiry():
    """
    Daily scheduler job: refresh permit statuses and send GChat alerts.

    - Updates status on all permits based on current date
    - Sends GChat alert for permits expiring within 7 days
    - Sends GChat alert for newly expired permits
    - Registered in hooks.py under scheduler_events["daily"]
    """
    today = getdate(nowdate())
    seven_days_out = add_days(today, 7)

    # Fetch all non-cancelled permits
    permits = frappe.get_all(
        "BEI Mall Permit",
        fields=["name", "expiry_date", "status", "store_name", "permit_type", "renewal_contact"],
    )

    expiring_alerts = []
    expired_alerts = []

    for p in permits:
        if not p.get("expiry_date"):
            continue

        expiry = getdate(p["expiry_date"])
        days_remaining = date_diff(expiry, today)

        # Compute new status (preserve Renewal Pending if manually set)
        if p["status"] == "Renewal Pending":
            new_status = "Renewal Pending"
        elif days_remaining < 0:
            new_status = "Expired"
        elif days_remaining <= 30:
            new_status = "Expiring Soon"
        else:
            new_status = "Active"

        # Update if status changed
        if new_status != p["status"]:
            frappe.db.set_value("BEI Mall Permit", p["name"], "status", new_status, update_modified=False)

        # Build alert lists
        store_label = p.get("store_name") or p["name"]
        contact_info = " (Contact: {0})".format(p["renewal_contact"]) if p.get("renewal_contact") else ""

        if 0 <= days_remaining <= 7:
            expiring_alerts.append(
                "- {store} | {ptype} | Expires {exp} ({days}d remaining){contact}".format(
                    store=store_label,
                    ptype=p["permit_type"],
                    exp=p["expiry_date"],
                    days=days_remaining,
                    contact=contact_info,
                )
            )
        elif days_remaining < 0 and p["status"] != "Expired":
            # Was not yet marked expired — just discovered
            expired_alerts.append(
                "- {store} | {ptype} | Expired {exp}{contact}".format(
                    store=store_label,
                    ptype=p["permit_type"],
                    exp=p["expiry_date"],
                    contact=contact_info,
                )
            )

    # Send GChat notifications
    messages = []

    if expiring_alerts:
        lines = ["*PERMIT EXPIRY ALERT* — {0} permit(s) expiring within 7 days:".format(len(expiring_alerts))]
        lines.extend(expiring_alerts)
        lines.append("\nPlease coordinate permit renewals immediately.")
        messages.append("\n".join(lines))

    if expired_alerts:
        lines = ["*EXPIRED PERMITS* — {0} permit(s) have expired:".format(len(expired_alerts))]
        lines.extend(expired_alerts)
        lines.append("\nDelivery access may be blocked. Renew immediately.")
        messages.append("\n".join(lines))

    for msg in messages:
        _send_permit_gchat_notification(msg)


def _send_permit_gchat_notification(text):
    """
    Send a Google Chat message for permit alerts.
    Delegates to shared send_message_to_space() utility.
    """
    from hrms.api.google_chat import send_message_to_space

    space = "spaces/AAQABiNmpBg"
    try:
        configured = frappe.db.get_single_value("BEI Settings", "gchat_notification_space")
        if configured:
            space = configured
    except Exception:
        pass

    send_message_to_space(space, text)
