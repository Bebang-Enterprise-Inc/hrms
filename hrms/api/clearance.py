"""S170 — BEI Clearance API.

Provides endpoints for the employee-facing clearance flow:
    create_clearance(separation_name)        -> initialize from stations fixture
    update_clearance_item(...)               -> mark a single item terminal
    submit_clearance(clearance_name)         -> docstatus 0->1 (releases employee)
    get_clearance_for_user()                 -> read view for the current user

The clearance lifecycle is intentionally simple in v1 — Documenso integration,
ADMS biometric de-enrollment, and auto-creation on separation approval are all
deferred to a follow-up sprint. The minimum viable goal is: HR can create a
clearance from a separation, mark items as Returned/Waived/Missing, submit the
clearance, and watch the linked Employee transition to status='Left'.
"""
from __future__ import annotations

import frappe
from frappe import _

from hrms.utils.sentry import set_backend_observability_context


@frappe.whitelist()
def create_clearance(separation_name: str) -> dict:
    """Create a Draft BEI Clearance for the given Employee Separation.

    Auto-populates one item per enabled BEI Clearance Station, sorted by
    sort_order. Idempotent: if a clearance already exists for this separation,
    returns it instead of creating a duplicate.
    """
    set_backend_observability_context(
        module="clearance",
        action="create_clearance",
        mutation_type="create",
    )

    frappe.has_permission("BEI Clearance", "create", throw=True)

    if not separation_name:
        frappe.throw(_("separation_name is required"))

    separation = frappe.get_doc("Employee Separation", separation_name)
    if not separation.employee:
        frappe.throw(_("Employee Separation {0} has no employee linked").format(separation_name))

    # Idempotency check
    existing = frappe.db.get_value(
        "BEI Clearance",
        {"separation_request": separation_name, "docstatus": ["!=", 2]},
        "name",
    )
    if existing:
        return _serialize_clearance(frappe.get_doc("BEI Clearance", existing))

    # Pull enabled stations sorted
    stations = frappe.get_all(
        "BEI Clearance Station",
        filters={"enabled": 1},
        fields=["name", "station_name", "station_code", "sort_order"],
        order_by="sort_order asc, station_code asc",
    )
    if not stations:
        frappe.throw(
            _(
                "No enabled BEI Clearance Stations found. Load the fixture before "
                "creating clearances."
            )
        )

    doc = frappe.get_doc(
        {
            "doctype": "BEI Clearance",
            "employee": separation.employee,
            "separation_request": separation_name,
            "status": "Draft",
            "items": [
                {
                    "station": s["name"],
                    "item_description": s["station_name"],
                    "required_qty": 1,
                    "returned_qty": 0,
                    "status": "Pending",
                }
                for s in stations
            ],
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()

    return _serialize_clearance(doc)


@frappe.whitelist()
def update_clearance_item(
    clearance_name: str,
    item_idx: int,
    status: str,
    notes: str | None = None,
    proof_file_url: str | None = None,
) -> dict:
    """Mark a single clearance item as Returned / Waived / Missing.

    Promotes the parent clearance from Draft -> In Progress on first update.
    """
    set_backend_observability_context(
        module="clearance",
        action="update_clearance_item",
        mutation_type="update",
    )

    frappe.has_permission("BEI Clearance", "write", throw=True)

    if status not in {"Pending", "Returned", "Waived", "Missing"}:
        frappe.throw(_("Invalid item status: {0}").format(status))

    doc = frappe.get_doc("BEI Clearance", clearance_name)
    if doc.docstatus == 1:
        frappe.throw(_("Cannot edit a submitted clearance."))

    try:
        idx = int(item_idx)
    except (TypeError, ValueError):
        frappe.throw(_("item_idx must be an integer"))

    if idx < 0 or idx >= len(doc.items or []):
        frappe.throw(_("item_idx out of range"))

    item = doc.items[idx]
    item.status = status
    if status == "Returned":
        item.returned_qty = item.required_qty or 1
        item.returned_on = frappe.utils.nowdate()
    if notes is not None:
        item.notes = notes
    if proof_file_url is not None:
        item.proof_file = proof_file_url

    if doc.status == "Draft":
        doc.status = "In Progress"

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return _serialize_clearance(doc)


@frappe.whitelist()
def submit_clearance(clearance_name: str) -> dict:
    """Submit (docstatus 0 -> 1) the clearance, releasing the employee.

    `BEIClearance.on_submit` transitions the linked Employee to status='Left'.
    """
    set_backend_observability_context(
        module="clearance",
        action="submit_clearance",
        mutation_type="update",
    )

    frappe.has_permission("BEI Clearance", "submit", throw=True)

    doc = frappe.get_doc("BEI Clearance", clearance_name)
    if doc.docstatus == 1:
        frappe.throw(_("Clearance is already submitted."))

    doc.flags.ignore_permissions = True
    doc.submit()
    frappe.db.commit()

    return _serialize_clearance(doc)


@frappe.whitelist()
def get_clearance_for_user() -> dict | None:
    """Return the current user's clearance, if any.

    Used by the employee-facing /clearance page to render the right state.
    """
    set_backend_observability_context(
        module="clearance",
        action="get_clearance_for_user",
        mutation_type="read",
    )

    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    if not employee:
        return None

    # Find the most recent active separation
    separation = frappe.db.get_value(
        "Employee Separation",
        {"employee": employee, "docstatus": ["!=", 2]},
        "name",
        order_by="modified desc",
    )

    clearance_name = None
    if separation:
        clearance_name = frappe.db.get_value(
            "BEI Clearance",
            {"separation_request": separation, "docstatus": ["!=", 2]},
            "name",
            order_by="modified desc",
        )

    return {
        "employee": employee,
        "separation": separation,
        "clearance": _serialize_clearance(frappe.get_doc("BEI Clearance", clearance_name))
        if clearance_name
        else None,
    }


def _serialize_clearance(doc) -> dict:
    return {
        "name": doc.name,
        "employee": doc.employee,
        "employee_name": doc.employee_name,
        "separation_request": doc.separation_request,
        "relieving_date": str(doc.relieving_date) if doc.relieving_date else None,
        "status": doc.status,
        "docstatus": doc.docstatus,
        "initiated_on": str(doc.initiated_on) if doc.initiated_on else None,
        "initiated_by": doc.initiated_by,
        "approved_on": str(doc.approved_on) if doc.approved_on else None,
        "approved_by": doc.approved_by,
        "notes": doc.notes,
        "items": [
            {
                "idx": idx,
                "station": item.station,
                "item_description": item.item_description,
                "required_qty": item.required_qty,
                "returned_qty": item.returned_qty,
                "status": item.status,
                "returned_on": str(item.returned_on) if item.returned_on else None,
                "returned_to": item.returned_to,
                "notes": item.notes,
                "proof_file": item.proof_file,
            }
            for idx, item in enumerate(doc.items or [])
        ],
    }
