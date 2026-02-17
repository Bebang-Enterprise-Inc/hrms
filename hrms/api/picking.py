# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
BEI Pick List API
Handles warehouse picking workflow: order approved -> items picked -> loaded -> trip departs
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt


# RBAC roles for picking module
SCM_PICKING_ROLES = {"Warehouse Manager", "Warehouse Staff", "Logistics Coordinator", "System Manager"}


def _check_picking_permission(allowed_roles, action="access this resource"):
    """Check if current user has any of the allowed roles."""
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(allowed_roles):
        frappe.throw(
            _("You do not have permission to {0}").format(action),
            frappe.PermissionError
        )


@frappe.whitelist()
def generate_pick_list(trip_name):
    """
    Auto-create pick list from trip's approved BEI Store Orders.
    Groups items by store. Returns existing pick list if already created.
    """
    _check_picking_permission(SCM_PICKING_ROLES, "generate pick lists")

    # Check if a pick list already exists for this trip
    existing = frappe.db.get_value("BEI Pick List", {"trip": trip_name}, "name")
    if existing:
        return {"pick_list": existing, "message": _("Pick list already exists for this trip")}

    # Get the trip to find warehouse
    trip = frappe.get_doc("BEI Distribution Trip", trip_name)

    # Get all approved store orders linked to this trip
    store_orders = frappe.get_all(
        "BEI Store Order",
        filters={"trip": trip_name, "status": ["in", ["Approved", "Dispatched"]]},
        fields=["name", "store", "status"]
    )

    if not store_orders:
        frappe.throw(
            _("No approved Store Orders found for trip {0}").format(trip_name)
        )

    # Collect all items from all approved store orders, grouped by store+item
    item_map = {}  # key: (store, item_code) -> {qty, uom, store}

    # Batch-fetch all items from all store orders in a single query (avoid N+1)
    so_names = [so.name for so in store_orders]
    so_store_map = {so.name: so.store for so in store_orders}

    all_so_items = frappe.get_all(
        "BEI Store Order Item",
        filters={"parent": ["in", so_names]},
        fields=["parent", "item_code", "item_name", "qty_requested", "uom"]
    )

    for item in all_so_items:
        store = so_store_map[item.parent]
        key = (store, item.item_code)
        if key in item_map:
            item_map[key]["qty_ordered"] += flt(item.qty_requested, 3)
        else:
            item_map[key] = {
                "store": store,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty_ordered": flt(item.qty_requested, 3),
                "uom": item.uom or "",
                "qty_picked": 0,
                "picked": 0
            }

    if not item_map:
        frappe.throw(_("No items found in approved Store Orders for trip {0}").format(trip_name))

    # Determine source warehouse from trip
    source_warehouse = getattr(trip, "warehouse", None) or getattr(trip, "source_warehouse", None)
    if not source_warehouse:
        # Fallback: try to get commissary/main warehouse
        source_warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "disabled": 0}, "name")

    frappe.db.savepoint("generate_pick_list")
    try:
        pick_list = frappe.get_doc({
            "doctype": "BEI Pick List",
            "trip": trip_name,
            "warehouse": source_warehouse,
            "pick_date": nowdate(),
            "status": "Pending",
            "items": list(item_map.values())
        })
        pick_list.insert(ignore_permissions=True)

        return {
            "pick_list": pick_list.name,
            "item_count": len(item_map),
            "message": _("Pick list {0} created with {1} items").format(
                pick_list.name, len(item_map)
            )
        }
    except Exception:
        frappe.db.rollback(save_point="generate_pick_list")
        raise


@frappe.whitelist()
def get_pick_list(trip_name):
    """Fetch pick list with all items for a given trip."""
    _check_picking_permission(SCM_PICKING_ROLES, "view pick lists")

    pick_list_name = frappe.db.get_value("BEI Pick List", {"trip": trip_name}, "name")
    if not pick_list_name:
        return {"pick_list": None, "message": _("No pick list found for trip {0}").format(trip_name)}

    pick_list = frappe.get_doc("BEI Pick List", pick_list_name)

    items = [
        {
            "idx": item.idx,
            "store": item.store,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty_ordered": flt(item.qty_ordered, 3),
            "qty_picked": flt(item.qty_picked, 3),
            "uom": item.uom,
            "bin_location": item.bin_location,
            "picked": item.picked
        }
        for item in pick_list.items
    ]

    total_items = len(items)
    picked_items = sum(1 for i in items if i["picked"])

    return {
        "pick_list": {
            "name": pick_list.name,
            "trip": pick_list.trip,
            "warehouse": pick_list.warehouse,
            "pick_date": pick_list.pick_date,
            "status": pick_list.status,
            "picked_by": pick_list.picked_by,
            "verified_by": pick_list.verified_by,
            "packed_at": pick_list.packed_at,
            "loaded_at": pick_list.loaded_at,
            "total_items": total_items,
            "picked_items": picked_items,
            "items": items
        }
    }


@frappe.whitelist()
def update_pick_item(pick_list_name, item_idx, qty_picked):
    """
    Picker updates the actual qty picked for a specific item.
    Sets item.picked = 1 when qty_picked >= 0.
    """
    _check_picking_permission(SCM_PICKING_ROLES, "update pick items")

    qty_picked = flt(qty_picked, 3)
    if qty_picked < 0:
        frappe.throw(_("qty_picked cannot be negative"))

    item_idx = int(item_idx)

    pick_list = frappe.get_doc("BEI Pick List", pick_list_name)

    if pick_list.status == "Loaded":
        frappe.throw(_("Cannot update items on a Loaded pick list"))

    # Find the item by idx
    target_item = None
    for item in pick_list.items:
        if item.idx == item_idx:
            target_item = item
            break

    if not target_item:
        frappe.throw(_("Item at index {0} not found in pick list {1}").format(
            item_idx, pick_list_name
        ))

    target_item.qty_picked = qty_picked
    target_item.picked = 1

    # Advance status to In Progress if still Pending
    if pick_list.status == "Pending":
        pick_list.status = "In Progress"

    pick_list.save(ignore_permissions=True)

    return {
        "success": True,
        "item_idx": item_idx,
        "qty_picked": qty_picked,
        "status": pick_list.status,
        "message": _("Item updated")
    }


@frappe.whitelist()
def complete_picking(pick_list_name):
    """
    Mark pick list as Packed after all items have been picked.
    Validates that every item has picked=1 before proceeding.
    """
    _check_picking_permission(SCM_PICKING_ROLES, "complete picking")

    pick_list = frappe.get_doc("BEI Pick List", pick_list_name)

    if pick_list.status not in ["Pending", "In Progress"]:
        frappe.throw(
            _("Pick list must be Pending or In Progress to complete picking. Current: {0}").format(
                pick_list.status
            )
        )

    # Validate all items have been picked
    unpicked = [
        item.item_code for item in pick_list.items if not item.picked
    ]
    if unpicked:
        frappe.throw(
            _("The following items have not been picked yet: {0}").format(
                ", ".join(unpicked)
            )
        )

    pick_list.status = "Packed"
    pick_list.packed_at = now_datetime()
    pick_list.save(ignore_permissions=True)

    return {
        "success": True,
        "status": "Packed",
        "packed_at": str(pick_list.packed_at),
        "message": _("Pick list {0} marked as Packed").format(pick_list_name)
    }


@frappe.whitelist()
def confirm_loaded(pick_list_name):
    """
    Mark pick list as Loaded (driver confirms items on truck).
    Creates a Frappe Stock Entry (Material Issue) to deduct inventory.
    Uses savepoint to safely wrap stock deduction.
    """
    _check_picking_permission(SCM_PICKING_ROLES, "confirm loaded")

    pick_list = frappe.get_doc("BEI Pick List", pick_list_name)

    if pick_list.status != "Packed":
        frappe.throw(
            _("Pick list must be Packed before confirming load. Current: {0}").format(
                pick_list.status
            )
        )

    if not pick_list.warehouse:
        frappe.throw(_("Pick list has no source warehouse set"))

    frappe.db.savepoint("confirm_loaded")
    try:
        # Create Material Issue Stock Entry to deduct from source warehouse
        stock_entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "from_warehouse": pick_list.warehouse,
            "posting_date": nowdate(),
            "posting_time": frappe.utils.nowtime(),
            "company": frappe.defaults.get_global_default("company") or "Bebang Enterprise Inc.",
            "remarks": _("Pick List {0} - Trip {1}").format(pick_list_name, pick_list.trip),
            "items": [
                {
                    "item_code": item.item_code,
                    "qty": flt(item.qty_picked, 3),
                    "s_warehouse": pick_list.warehouse,
                    "uom": item.uom or frappe.db.get_value("Item", item.item_code, "stock_uom") or "Nos"
                }
                for item in pick_list.items
                if flt(item.qty_picked, 3) > 0
            ]
        })

        if not stock_entry.items:
            frappe.throw(_("No items with picked quantity > 0 to issue from stock"))

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        pick_list.status = "Loaded"
        pick_list.loaded_at = now_datetime()
        pick_list.save(ignore_permissions=True)

        return {
            "success": True,
            "status": "Loaded",
            "loaded_at": str(pick_list.loaded_at),
            "stock_entry": stock_entry.name,
            "message": _("Pick list {0} confirmed as Loaded. Stock Entry {1} created.").format(
                pick_list_name, stock_entry.name
            )
        }

    except Exception:
        frappe.db.rollback(save_point="confirm_loaded")
        raise
