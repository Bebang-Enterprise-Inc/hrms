# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Warehouse Supervisor APIs
Handles PO receiving, Material Request approval, and stock transfers for Ian.

Author: Claude Code
Date: 2026-02-02
"""

import frappe
from frappe import _
import json


# ============================================================
# 1. SUPPLIER RECEIVING
# ============================================================

@frappe.whitelist()
def get_pending_purchase_orders():
    """
    Get POs pending receipt at warehouse.
    Returns POs with status='To Receive and Bill' or 'To Receive'
    """
    pos = frappe.get_all(
        "Purchase Order",
        filters={
            "status": ["in", ["To Receive and Bill", "To Receive"]],
            "docstatus": 1
        },
        fields=[
            "name", "supplier", "supplier_name", "transaction_date",
            "grand_total", "status", "per_received"
        ],
        order_by="transaction_date desc",
        limit=50
    )

    # Add item summary for each PO
    for po in pos:
        items = frappe.get_all(
            "Purchase Order Item",
            filters={"parent": po.name},
            fields=["item_code", "item_name", "qty", "received_qty", "uom"]
        )
        po["items"] = items
        po["items_count"] = len(items)
        po["pending_items"] = sum(1 for i in items if i.qty > i.received_qty)

    return {"success": True, "data": pos}


@frappe.whitelist()
def get_purchase_order_items(po_name):
    """
    Get detailed items for a specific PO with receiving status.
    """
    if not frappe.db.exists("Purchase Order", po_name):
        frappe.throw(_("Purchase Order not found"))

    po = frappe.get_doc("Purchase Order", po_name)

    items = frappe.get_all(
        "Purchase Order Item",
        filters={"parent": po_name},
        fields=[
            "name", "item_code", "item_name", "description",
            "qty", "received_qty", "uom", "rate", "amount",
            "warehouse"
        ]
    )

    # Calculate pending qty for each item
    for item in items:
        item["pending_qty"] = item["qty"] - item["received_qty"]

    return {
        "success": True,
        "data": {
            "po_name": po.name,
            "supplier": po.supplier,
            "supplier_name": po.supplier_name,
            "transaction_date": po.transaction_date,
            "grand_total": po.grand_total,
            "items": items
        }
    }


@frappe.whitelist()
def create_purchase_receipt(po_name, items, remarks=None):
    """
    Create Purchase Receipt from PO.

    Args:
        po_name: Purchase Order name
        items: JSON array of {item_code, received_qty, rejected_qty, warehouse}
        remarks: Optional notes

    Returns:
        Purchase Receipt name
    """
    if isinstance(items, str):
        items = json.loads(items)

    if not frappe.db.exists("Purchase Order", po_name):
        frappe.throw(_("Purchase Order not found"))

    po = frappe.get_doc("Purchase Order", po_name)

    # Create Purchase Receipt
    pr = frappe.new_doc("Purchase Receipt")
    pr.supplier = po.supplier
    pr.supplier_name = po.supplier_name
    pr.company = po.company
    pr.posting_date = frappe.utils.today()
    pr.posting_time = frappe.utils.nowtime()
    pr.remarks = remarks or f"Received against {po_name}"

    # Add items
    for item_data in items:
        # Find matching PO item
        po_item = next(
            (i for i in po.items if i.item_code == item_data["item_code"]),
            None
        )
        if not po_item:
            continue

        received_qty = item_data.get("received_qty", 0)
        if received_qty <= 0:
            continue

        pr.append("items", {
            "item_code": item_data["item_code"],
            "item_name": po_item.item_name,
            "description": po_item.description,
            "qty": received_qty,
            "rejected_qty": item_data.get("rejected_qty", 0),
            "uom": po_item.uom,
            "stock_uom": po_item.stock_uom,
            "conversion_factor": po_item.conversion_factor or 1,
            "rate": po_item.rate,
            "warehouse": item_data.get("warehouse") or po_item.warehouse,
            "purchase_order": po_name,
            "purchase_order_item": po_item.name
        })

    if not pr.items:
        frappe.throw(_("No items to receive"))

    pr.insert()
    pr.submit()

    return {
        "success": True,
        "data": {
            "name": pr.name,
            "grand_total": pr.grand_total,
            "items_count": len(pr.items)
        },
        "message": f"Purchase Receipt {pr.name} created successfully"
    }


# ============================================================
# 2. MATERIAL REQUEST APPROVAL
# ============================================================

@frappe.whitelist()
def get_pending_material_requests():
    """
    Get Material Requests pending approval/fulfillment.
    """
    mrs = frappe.get_all(
        "Material Request",
        filters={
            "status": ["in", ["Pending", "Partially Ordered"]],
            "docstatus": 1,
            "material_request_type": "Material Transfer"
        },
        fields=[
            "name", "transaction_date", "schedule_date",
            "status", "set_warehouse"  # destination warehouse (store)
        ],
        order_by="schedule_date asc",
        limit=50
    )

    for mr in mrs:
        # Get warehouse/store name
        if mr.set_warehouse:
            mr["store_name"] = mr.set_warehouse.replace(" - BEI", "")

        # Get items summary
        items = frappe.get_all(
            "Material Request Item",
            filters={"parent": mr.name},
            fields=["item_code", "item_name", "qty", "ordered_qty", "uom"]
        )
        mr["items"] = items
        mr["items_count"] = len(items)
        mr["pending_items"] = sum(1 for i in items if i.qty > (i.ordered_qty or 0))

    return {"success": True, "data": mrs}


@frappe.whitelist()
def get_material_request_items(mr_name):
    """
    Get detailed items for a Material Request with stock availability.
    """
    if not frappe.db.exists("Material Request", mr_name):
        frappe.throw(_("Material Request not found"))

    mr = frappe.get_doc("Material Request", mr_name)

    items = frappe.get_all(
        "Material Request Item",
        filters={"parent": mr_name},
        fields=[
            "name", "item_code", "item_name", "description",
            "qty", "ordered_qty", "uom", "warehouse"
        ]
    )

    # Add stock availability from source warehouse (from_warehouse in MR items)
    # Fall back to "Commissary - BEI" or "TEST-COMMISSARY - BEI" if not specified
    default_commissary = "Commissary - BEI"
    for item in items:
        item["pending_qty"] = item["qty"] - (item["ordered_qty"] or 0)
        # Get from_warehouse for this item
        from_warehouse = frappe.db.get_value(
            "Material Request Item",
            item["name"],
            "from_warehouse"
        ) or default_commissary
        item["from_warehouse"] = from_warehouse
        # Get available stock at source warehouse
        bin_qty = frappe.db.get_value(
            "Bin",
            {"item_code": item["item_code"], "warehouse": from_warehouse},
            "actual_qty"
        ) or 0
        item["available_qty"] = bin_qty

    return {
        "success": True,
        "data": {
            "mr_name": mr.name,
            "store": mr.set_warehouse,
            "store_name": mr.set_warehouse.replace(" - BEI", "") if mr.set_warehouse else "",
            "transaction_date": mr.transaction_date,
            "schedule_date": mr.schedule_date,
            "items": items
        }
    }


@frappe.whitelist()
def approve_material_request(mr_name, approved_items):
    """
    Approve Material Request with optional quantity adjustments.

    Args:
        mr_name: Material Request name
        approved_items: JSON array of {item_code, approved_qty}
    """
    if isinstance(approved_items, str):
        approved_items = json.loads(approved_items)

    if not frappe.db.exists("Material Request", mr_name):
        frappe.throw(_("Material Request not found"))

    mr = frappe.get_doc("Material Request", mr_name)

    # Store approval info as comment
    approval_summary = []
    for item in approved_items:
        approval_summary.append(f"{item['item_code']}: {item.get('approved_qty', 0)}")

    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Material Request",
        "reference_name": mr_name,
        "content": f"Approved by {frappe.session.user}. Quantities: " + ", ".join(approval_summary)
    }).insert(ignore_permissions=True)

    return {
        "success": True,
        "message": f"Material Request {mr_name} approved"
    }


@frappe.whitelist()
def reject_material_request(mr_name, reason):
    """
    Reject/cancel a Material Request.
    """
    if not frappe.db.exists("Material Request", mr_name):
        frappe.throw(_("Material Request not found"))

    mr = frappe.get_doc("Material Request", mr_name)

    # Add rejection comment
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Material Request",
        "reference_name": mr_name,
        "content": f"Rejected by {frappe.session.user}. Reason: {reason}"
    }).insert(ignore_permissions=True)

    # Cancel the MR
    mr.cancel()

    return {
        "success": True,
        "message": f"Material Request {mr_name} rejected"
    }


# ============================================================
# 3. DISPATCH / STOCK TRANSFER
# ============================================================

@frappe.whitelist()
def get_ready_for_dispatch():
    """
    Get approved Material Requests ready for dispatch.
    Groups by destination store for trip planning.
    """
    mrs = frappe.get_all(
        "Material Request",
        filters={
            "status": ["in", ["Pending", "Partially Ordered"]],
            "docstatus": 1,
            "material_request_type": "Material Transfer"
        },
        fields=[
            "name", "transaction_date", "schedule_date",
            "status", "set_warehouse"
        ],
        order_by="schedule_date asc"
    )

    # Group by destination warehouse
    by_store = {}
    for mr in mrs:
        store = mr.set_warehouse or "Unknown"
        if store not in by_store:
            by_store[store] = {
                "store": store,
                "store_name": store.replace(" - BEI", ""),
                "requests": [],
                "total_items": 0
            }

        items = frappe.get_all(
            "Material Request Item",
            filters={"parent": mr.name},
            fields=["item_code", "item_name", "qty", "uom"]
        )
        mr["items"] = items
        mr["items_count"] = len(items)

        by_store[store]["requests"].append(mr)
        by_store[store]["total_items"] += len(items)

    return {"success": True, "data": list(by_store.values())}


@frappe.whitelist()
def create_stock_transfer(source_warehouse, target_warehouse, items, mr_name=None, remarks=None):
    """
    Create Stock Entry (Material Transfer) for dispatch.

    Args:
        source_warehouse: From warehouse (e.g., "Commissary - BEI")
        target_warehouse: To warehouse (e.g., "SM-CALOOCAN - BEI")
        items: JSON array of {item_code, qty, uom}
        mr_name: Optional Material Request reference
        remarks: Optional notes

    Returns:
        Stock Entry name
    """
    if isinstance(items, str):
        items = json.loads(items)

    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company = "Bebang Enterprise Inc."
    se.posting_date = frappe.utils.today()
    se.posting_time = frappe.utils.nowtime()
    se.from_warehouse = source_warehouse
    se.to_warehouse = target_warehouse
    se.remarks = remarks or f"Transfer to {target_warehouse}"

    # Add items
    for item_data in items:
        # Get item details
        item = frappe.get_doc("Item", item_data["item_code"])

        se.append("items", {
            "item_code": item_data["item_code"],
            "item_name": item.item_name,
            "description": item.description,
            "qty": item_data["qty"],
            "uom": item_data.get("uom") or item.stock_uom,
            "stock_uom": item.stock_uom,
            "conversion_factor": 1,
            "s_warehouse": source_warehouse,
            "t_warehouse": target_warehouse,
            "material_request": mr_name,
            "material_request_item": item_data.get("mr_item_name")
        })

    if not se.items:
        frappe.throw(_("No items to transfer"))

    se.insert()
    se.submit()

    return {
        "success": True,
        "data": {
            "name": se.name,
            "total_qty": sum(i.qty for i in se.items),
            "items_count": len(se.items)
        },
        "message": f"Stock Transfer {se.name} created successfully"
    }


@frappe.whitelist()
def get_dispatch_trips_today():
    """
    Get today's dispatch trips for tracking.
    """
    today = frappe.utils.today()

    # Check if BEI Distribution Trip DocType exists
    if not frappe.db.exists("DocType", "BEI Distribution Trip"):
        return {"success": True, "data": [], "message": "Trip tracking not configured"}

    trips = frappe.get_all(
        "BEI Distribution Trip",
        filters={
            "trip_date": today
        },
        fields=[
            "name", "trip_date", "route_name", "driver",
            "vehicle", "vehicle_plate", "departure_time",
            "status"
        ],
        order_by="creation desc"
    )

    for trip in trips:
        # Get stops summary if child table exists
        if frappe.db.exists("DocType", "BEI Trip Stop"):
            stops = frappe.get_all(
                "BEI Trip Stop",
                filters={"parent": trip.name},
                fields=["store", "stop_order", "items_count", "status"]
            )
            trip["stops"] = stops
            trip["stops_count"] = len(stops)
            trip["completed_stops"] = sum(1 for s in stops if s.get("status") == "Delivered")
        else:
            trip["stops"] = []
            trip["stops_count"] = 0
            trip["completed_stops"] = 0

    return {"success": True, "data": trips}


# ============================================================
# 4. DASHBOARD / SUMMARY
# ============================================================

@frappe.whitelist()
def get_warehouse_dashboard():
    """
    Get warehouse supervisor dashboard summary.
    """
    today = frappe.utils.today()

    # Pending Purchase Receipts
    pending_pos = frappe.db.count(
        "Purchase Order",
        filters={
            "status": ["in", ["To Receive and Bill", "To Receive"]],
            "docstatus": 1
        }
    )

    # Pending Material Requests
    pending_mrs = frappe.db.count(
        "Material Request",
        filters={
            "status": ["in", ["Pending", "Partially Ordered"]],
            "docstatus": 1,
            "material_request_type": "Material Transfer"
        }
    )

    # Today's trips (if DocType exists)
    todays_trips = 0
    if frappe.db.exists("DocType", "BEI Distribution Trip"):
        todays_trips = frappe.db.count(
            "BEI Distribution Trip",
            filters={"trip_date": today}
        )

    # Recent activity - Purchase Receipts
    recent_receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"posting_date": [">=", frappe.utils.add_days(today, -7)]},
        fields=["name", "posting_date", "supplier_name", "grand_total"],
        order_by="posting_date desc",
        limit=5
    )

    # Recent activity - Stock Transfers
    recent_transfers = frappe.get_all(
        "Stock Entry",
        filters={
            "posting_date": [">=", frappe.utils.add_days(today, -7)],
            "stock_entry_type": "Material Transfer"
        },
        fields=["name", "posting_date", "to_warehouse", "total_outgoing_value"],
        order_by="posting_date desc",
        limit=5
    )

    return {
        "success": True,
        "data": {
            "pending_pos": pending_pos,
            "pending_mrs": pending_mrs,
            "todays_trips": todays_trips,
            "recent_receipts": recent_receipts,
            "recent_transfers": recent_transfers
        }
    }
