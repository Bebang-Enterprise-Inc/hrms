# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Procurement API - Complete procurement workflow endpoints
Supports: Suppliers, PR, PO, GR, Invoice, Payment Request, Dashboard

All endpoints use @frappe.whitelist() for external access.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_days, get_first_day, get_last_day


# =============================================================================
# SUPPLIER ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_suppliers(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of suppliers with optional filters."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(supplier_code LIKE %(search)s OR supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    # Get total count
    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Supplier` WHERE {where_clause}",
        values
    )[0][0]

    # Get suppliers (is_new_supplier computed based on creation date - last 30 days)
    suppliers = frappe.db.sql(f"""
        SELECT
            name, supplier_code, supplier_name, status,
            email, contact_person, contact_number, address,
            tin, bank_name, bank_account_number, payment_terms,
            total_po_count, total_po_value, total_outstanding,
            avg_delivery_days, on_time_rate,
            bir_2307, sec_certificate, business_permit,
            CASE WHEN creation >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END as is_new_supplier
        FROM `tabBEI Supplier`
        WHERE {where_clause}
        ORDER BY supplier_name ASC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": suppliers,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_supplier(name):
    """Get single supplier with full details."""
    supplier = frappe.get_doc("BEI Supplier", name)
    return supplier.as_dict()


@frappe.whitelist()
def create_supplier(data):
    """Create new supplier."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    supplier = frappe.get_doc({
        "doctype": "BEI Supplier",
        **data
    })
    supplier.insert()

    return {"success": True, "name": supplier.name, "message": _("Supplier created")}


@frappe.whitelist()
def update_supplier(name, data):
    """Update existing supplier."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    supplier = frappe.get_doc("BEI Supplier", name)

    for key, value in data.items():
        if hasattr(supplier, key):
            setattr(supplier, key, value)

    supplier.save()

    return {"success": True, "message": _("Supplier updated")}


@frappe.whitelist()
def get_supplier_metrics(name):
    """Get supplier performance metrics."""
    supplier = frappe.get_doc("BEI Supplier", name)

    # Get recent POs
    recent_pos = frappe.db.sql("""
        SELECT name, po_date, grand_total, status
        FROM `tabBEI Purchase Order`
        WHERE supplier = %s
        ORDER BY po_date DESC
        LIMIT 10
    """, (name,), as_dict=True)

    # Get outstanding invoices
    outstanding = frappe.db.sql("""
        SELECT name, invoice_date, grand_total, balance_due, due_date
        FROM `tabBEI Invoice`
        WHERE supplier = %s AND payment_status != 'Paid'
        ORDER BY due_date ASC
    """, (name,), as_dict=True)

    return {
        "supplier": supplier.as_dict(),
        "recent_pos": recent_pos,
        "outstanding_invoices": outstanding,
        "total_outstanding": sum(flt(inv.get("balance_due", 0)) for inv in outstanding)
    }


# =============================================================================
# PURCHASE REQUISITION ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_purchase_requisitions(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of PRs."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(pr_no LIKE %(search)s OR department LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("department"):
            conditions.append("department = %(department)s")
            values["department"] = filters["department"]

        if filters.get("requested_by"):
            conditions.append("requested_by = %(requested_by)s")
            values["requested_by"] = filters["requested_by"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Purchase Requisition` WHERE {where_clause}",
        values
    )[0][0]

    prs = frappe.db.sql(f"""
        SELECT
            name, pr_no, request_date, status, department,
            requested_by, total_estimated_cost
        FROM `tabBEI Purchase Requisition`
        WHERE {where_clause}
        ORDER BY request_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": prs,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_purchase_requisition(name):
    """Get single PR with items."""
    pr = frappe.get_doc("BEI Purchase Requisition", name)
    return pr.as_dict()


@frappe.whitelist()
def create_purchase_requisition(data):
    """Create new PR."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    pr = frappe.get_doc({
        "doctype": "BEI Purchase Requisition",
        **data
    })
    pr.insert()

    return {"success": True, "name": pr.name, "message": _("PR created")}


@frappe.whitelist()
def submit_pr_for_approval(name):
    """Submit PR for approval."""
    pr = frappe.get_doc("BEI Purchase Requisition", name)
    return pr.submit_for_approval()


@frappe.whitelist()
def approve_pr(name, comment=None):
    """Approve PR."""
    pr = frappe.get_doc("BEI Purchase Requisition", name)
    return pr.approve(comment)


@frappe.whitelist()
def reject_pr(name, reason):
    """Reject PR."""
    pr = frappe.get_doc("BEI Purchase Requisition", name)
    return pr.reject(reason)


@frappe.whitelist()
def convert_pr_to_po(name, supplier):
    """Convert approved PR to PO."""
    pr = frappe.get_doc("BEI Purchase Requisition", name)
    return pr.convert_to_po(supplier)


# =============================================================================
# PURCHASE ORDER ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_purchase_orders(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of POs."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(po_no LIKE %(search)s OR supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("supplier"):
            conditions.append("supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("requires_dual_approval"):
            conditions.append("requires_dual_approval = 1")

        if filters.get("pending_approval"):
            conditions.append(
                "status IN ('Pending Mae Approval', 'Pending Butch Approval')"
            )

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Purchase Order` WHERE {where_clause}",
        values
    )[0][0]

    pos = frappe.db.sql(f"""
        SELECT
            name, po_no, po_date, status, supplier, supplier_name,
            grand_total, requires_dual_approval, mae_approval, butch_approval,
            delivery_date
        FROM `tabBEI Purchase Order`
        WHERE {where_clause}
        ORDER BY po_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": pos,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_purchase_order(name):
    """Get single PO with items."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.as_dict()


@frappe.whitelist()
def create_purchase_order(data):
    """Create new PO."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    po = frappe.get_doc({
        "doctype": "BEI Purchase Order",
        **data
    })
    po.insert()

    return {"success": True, "name": po.name, "message": _("PO created")}


@frappe.whitelist()
def submit_po_for_approval(name):
    """Submit PO for Mae's approval."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.submit_for_approval()


@frappe.whitelist()
def approve_po_mae(name, comment=None):
    """Mae approves PO."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.approve_mae(comment)


@frappe.whitelist()
def approve_po_butch(name, comment=None):
    """Butch (CFO) approves PO for >500K."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.approve_butch(comment)


@frappe.whitelist()
def reject_po(name, reason, rejector="mae"):
    """Reject PO."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.reject(reason, rejector)


@frappe.whitelist()
def send_po_to_supplier(name):
    """Send PO to supplier via email."""
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.send_to_supplier()


@frappe.whitelist()
def get_pending_po_approvals():
    """Get all POs pending approval (for queue view)."""
    pending_mae = frappe.db.sql("""
        SELECT
            name, po_no, po_date, supplier_name, grand_total,
            requires_dual_approval, 'mae' as pending_level
        FROM `tabBEI Purchase Order`
        WHERE status = 'Pending Mae Approval'
        ORDER BY po_date ASC
    """, as_dict=True)

    pending_butch = frappe.db.sql("""
        SELECT
            name, po_no, po_date, supplier_name, grand_total,
            requires_dual_approval, 'butch' as pending_level
        FROM `tabBEI Purchase Order`
        WHERE status = 'Pending Butch Approval'
        ORDER BY po_date ASC
    """, as_dict=True)

    return {
        "pending_mae": pending_mae,
        "pending_butch": pending_butch,
        "total_pending": len(pending_mae) + len(pending_butch)
    }


# =============================================================================
# GOODS RECEIPT ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_goods_receipts(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of GRs."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(gr_no LIKE %(search)s OR supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("supplier"):
            conditions.append("supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("purchase_order"):
            conditions.append("purchase_order = %(purchase_order)s")
            values["purchase_order"] = filters["purchase_order"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Goods Receipt` WHERE {where_clause}",
        values
    )[0][0]

    grs = frappe.db.sql(f"""
        SELECT
            name, gr_no, receipt_date, status, purchase_order,
            supplier, supplier_name, total_received_qty, total_amount
        FROM `tabBEI Goods Receipt`
        WHERE {where_clause}
        ORDER BY receipt_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": grs,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_goods_receipt(name):
    """Get single GR with items."""
    gr = frappe.get_doc("BEI Goods Receipt", name)
    return gr.as_dict()


@frappe.whitelist()
def create_goods_receipt(data):
    """Create new GR."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # Map 'rate' to 'unit_cost' in items if needed
    if "items" in data:
        for item in data["items"]:
            if "rate" in item and "unit_cost" not in item:
                item["unit_cost"] = item.pop("rate")

    gr = frappe.get_doc({
        "doctype": "BEI Goods Receipt",
        **data
    })
    gr.insert()

    return {"success": True, "name": gr.name, "message": _("GR created")}


@frappe.whitelist()
def load_gr_from_po(name, purchase_order):
    """Load GR items from PO."""
    gr = frappe.get_doc("BEI Goods Receipt", name)
    gr.purchase_order = purchase_order
    return gr.load_from_po()


@frappe.whitelist()
def submit_goods_receipt(name):
    """Submit GR."""
    gr = frappe.get_doc("BEI Goods Receipt", name)
    return gr.submit_receipt()


@frappe.whitelist()
def complete_gr_inspection(name, passed=True, notes=None):
    """Complete quality inspection on GR."""
    gr = frappe.get_doc("BEI Goods Receipt", name)
    return gr.complete_inspection(passed, notes)


@frappe.whitelist()
def get_pending_gr_for_po(purchase_order):
    """Get receivable items for a PO."""
    po = frappe.get_doc("BEI Purchase Order", purchase_order)

    pending_items = []
    for item in po.items:
        remaining = flt(item.qty, 2) - flt(item.received_qty, 2)
        if remaining > 0:
            pending_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "ordered_qty": item.qty,
                "received_qty": item.received_qty,
                "remaining_qty": remaining,
                "uom": item.uom,
                "unit_cost": item.unit_cost
            })

    return {
        "purchase_order": po.as_dict(),
        "pending_items": pending_items
    }


# =============================================================================
# INVOICE ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_invoices(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of invoices."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(invoice_no LIKE %(search)s OR supplier_name LIKE %(search)s "
            "OR supplier_invoice_no LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("supplier"):
            conditions.append("supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("payment_status"):
            conditions.append("payment_status = %(payment_status)s")
            values["payment_status"] = filters["payment_status"]

        if filters.get("overdue"):
            conditions.append("due_date < %(today)s AND payment_status != 'Paid'")
            values["today"] = nowdate()

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Invoice` WHERE {where_clause}",
        values
    )[0][0]

    invoices = frappe.db.sql(f"""
        SELECT
            name, invoice_no, supplier_invoice_no, invoice_date, due_date,
            status, supplier, supplier_name, grand_total, balance_due,
            payment_status, match_status
        FROM `tabBEI Invoice`
        WHERE {where_clause}
        ORDER BY due_date ASC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": invoices,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_invoice(name):
    """Get single invoice with full details."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.as_dict()


@frappe.whitelist()
def create_invoice(data):
    """Create new invoice."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    invoice = frappe.get_doc({
        "doctype": "BEI Invoice",
        **data
    })
    invoice.insert()

    return {"success": True, "name": invoice.name, "message": _("Invoice created")}


@frappe.whitelist()
def submit_invoice_for_verification(name):
    """Submit invoice for 3-way match."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.submit_for_verification()


@frappe.whitelist()
def verify_invoice_match(name):
    """Verify 3-way match."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.verify_match()


@frappe.whitelist()
def approve_invoice_variance(name, notes=None):
    """Approve invoice despite variance."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.approve_variance(notes)


@frappe.whitelist()
def reject_invoice_variance(name, reason):
    """Reject invoice due to variance."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.reject_variance(reason)


# =============================================================================
# PAYMENT REQUEST ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_payment_requests(filters=None, page=1, page_size=20, search=None):
    """Get paginated list of payment requests."""
    conditions = []
    values = {}

    if search:
        conditions.append(
            "(payment_request_no LIKE %(search)s OR supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("supplier"):
            conditions.append("supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("pending_approval"):
            conditions.append(
                "status IN ('Pending Review', 'Pending Budget Approval', "
                "'Pending CFO Approval', 'Pending CEO Approval')"
            )

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Payment Request` WHERE {where_clause}",
        values
    )[0][0]

    requests = frappe.db.sql(f"""
        SELECT
            name, payment_request_no, request_date, status, supplier,
            supplier_name, payment_amount, payment_mode, invoice,
            ceo_required, payment_date
        FROM `tabBEI Payment Request`
        WHERE {where_clause}
        ORDER BY request_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": requests,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_payment_request(name):
    """Get single payment request with approval status."""
    request = frappe.get_doc("BEI Payment Request", name)
    data = request.as_dict()
    data["approval_status"] = request.get_approval_status()
    return data


@frappe.whitelist()
def create_payment_request(data):
    """Create new payment request."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    request = frappe.get_doc({
        "doctype": "BEI Payment Request",
        **data
    })
    request.insert()

    return {"success": True, "name": request.name, "message": _("Payment request created")}


@frappe.whitelist()
def submit_payment_for_approval(name):
    """Submit payment request for 4-level approval."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.submit_for_approval()


@frappe.whitelist()
def approve_payment_review(name, comment=None):
    """Level 1: Reviewer approves."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.approve_review(comment)


@frappe.whitelist()
def approve_payment_budget(name, comment=None):
    """Level 2: Budget approves."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.approve_budget(comment)


@frappe.whitelist()
def approve_payment_cfo(name, comment=None):
    """Level 3: CFO (Butch) approves."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.approve_cfo(comment)


@frappe.whitelist()
def approve_payment_ceo(name, comment=None):
    """Level 4: CEO approves (for new suppliers or >1M)."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.approve_ceo(comment)


@frappe.whitelist()
def reject_payment_request(name, level, reason):
    """Reject payment request at any level."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.reject(level, reason)


@frappe.whitelist()
def mark_payment_complete(name, transaction_reference=None, payment_proof=None):
    """Mark payment as complete."""
    request = frappe.get_doc("BEI Payment Request", name)
    return request.mark_as_paid(transaction_reference, payment_proof)


@frappe.whitelist()
def get_pending_payment_approvals():
    """Get all payments pending approval at each level."""
    levels = {
        "review": "Pending Review",
        "budget": "Pending Budget Approval",
        "cfo": "Pending CFO Approval",
        "ceo": "Pending CEO Approval"
    }

    result = {}
    total = 0

    for level, status in levels.items():
        pending = frappe.db.sql("""
            SELECT
                name, payment_request_no, request_date, supplier_name,
                payment_amount, payment_mode, ceo_required
            FROM `tabBEI Payment Request`
            WHERE status = %s
            ORDER BY request_date ASC
        """, (status,), as_dict=True)

        result[level] = pending
        total += len(pending)

    result["total_pending"] = total
    return result


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_dashboard_kpis():
    """Get key performance indicators for executive dashboard."""
    today = getdate(nowdate())
    month_start = get_first_day(today)
    month_end = get_last_day(today)

    # Total outstanding (unpaid invoices)
    total_outstanding = frappe.db.sql("""
        SELECT COALESCE(SUM(balance_due), 0) as total
        FROM `tabBEI Invoice`
        WHERE payment_status != 'Paid'
    """)[0][0] or 0

    # Overdue amount
    overdue_amount = frappe.db.sql("""
        SELECT COALESCE(SUM(balance_due), 0) as total
        FROM `tabBEI Invoice`
        WHERE payment_status != 'Paid' AND due_date < %s
    """, (today,))[0][0] or 0

    # Month-to-date POs
    mtd_po_value = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0) as total
        FROM `tabBEI Purchase Order`
        WHERE po_date BETWEEN %s AND %s
        AND status NOT IN ('Draft', 'Cancelled')
    """, (month_start, month_end))[0][0] or 0

    mtd_po_count = frappe.db.sql("""
        SELECT COUNT(*) as total
        FROM `tabBEI Purchase Order`
        WHERE po_date BETWEEN %s AND %s
        AND status NOT IN ('Draft', 'Cancelled')
    """, (month_start, month_end))[0][0] or 0

    # Pending approvals
    pending_po = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBEI Purchase Order`
        WHERE status IN ('Pending Mae Approval', 'Pending Butch Approval')
    """)[0][0] or 0

    pending_payments = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBEI Payment Request`
        WHERE status IN ('Pending Review', 'Pending Budget Approval',
                        'Pending CFO Approval', 'Pending CEO Approval')
    """)[0][0] or 0

    # Active suppliers
    active_suppliers = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBEI Supplier`
        WHERE status = 'Active'
    """)[0][0] or 0

    # Average payment days (last 30 days)
    avg_payment_days = frappe.db.sql("""
        SELECT AVG(DATEDIFF(processed_date, request_date)) as avg_days
        FROM `tabBEI Payment Request`
        WHERE status = 'Paid'
        AND processed_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """)[0][0] or 0

    return {
        "total_outstanding": flt(total_outstanding, 2),
        "overdue_amount": flt(overdue_amount, 2),
        "mtd_po_value": flt(mtd_po_value, 2),
        "mtd_po_count": int(mtd_po_count),
        "pending_po_approvals": int(pending_po),
        "pending_payment_approvals": int(pending_payments),
        "active_suppliers": int(active_suppliers),
        "avg_payment_days": flt(avg_payment_days, 1)
    }


@frappe.whitelist()
def get_outstanding_by_supplier():
    """Get outstanding amounts grouped by supplier."""
    data = frappe.db.sql("""
        SELECT
            s.name as supplier,
            s.supplier_name,
            COALESCE(SUM(i.balance_due), 0) as outstanding,
            COUNT(i.name) as invoice_count,
            MIN(i.due_date) as earliest_due
        FROM `tabBEI Supplier` s
        LEFT JOIN `tabBEI Invoice` i ON i.supplier = s.name
            AND i.payment_status != 'Paid'
        WHERE s.status = 'Active'
        GROUP BY s.name, s.supplier_name
        HAVING outstanding > 0
        ORDER BY outstanding DESC
    """, as_dict=True)

    return data


@frappe.whitelist()
def get_aging_analysis():
    """Get accounts payable aging analysis."""
    today = getdate(nowdate())

    aging = {
        "current": 0,
        "days_1_30": 0,
        "days_31_60": 0,
        "days_61_90": 0,
        "over_90": 0
    }

    invoices = frappe.db.sql("""
        SELECT balance_due, due_date
        FROM `tabBEI Invoice`
        WHERE payment_status != 'Paid'
    """, as_dict=True)

    for inv in invoices:
        days_overdue = (today - getdate(inv.due_date)).days

        if days_overdue <= 0:
            aging["current"] += flt(inv.balance_due, 2)
        elif days_overdue <= 30:
            aging["days_1_30"] += flt(inv.balance_due, 2)
        elif days_overdue <= 60:
            aging["days_31_60"] += flt(inv.balance_due, 2)
        elif days_overdue <= 90:
            aging["days_61_90"] += flt(inv.balance_due, 2)
        else:
            aging["over_90"] += flt(inv.balance_due, 2)

    aging["total"] = sum(aging.values())

    return aging


@frappe.whitelist()
def get_monthly_po_trend(months=6):
    """Get PO trend for the last N months."""
    data = frappe.db.sql("""
        SELECT
            DATE_FORMAT(po_date, '%%Y-%%m') as month,
            COUNT(*) as po_count,
            SUM(grand_total) as po_value
        FROM `tabBEI Purchase Order`
        WHERE po_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        AND status NOT IN ('Draft', 'Cancelled')
        GROUP BY DATE_FORMAT(po_date, '%%Y-%%m')
        ORDER BY month ASC
    """, (months,), as_dict=True)

    return data


@frappe.whitelist()
def get_payment_schedule():
    """Get upcoming payment schedule."""
    data = frappe.db.sql("""
        SELECT
            i.name as invoice,
            i.invoice_no,
            i.supplier_name,
            i.balance_due,
            i.due_date,
            DATEDIFF(i.due_date, CURDATE()) as days_until_due
        FROM `tabBEI Invoice` i
        WHERE i.payment_status != 'Paid'
        ORDER BY i.due_date ASC
        LIMIT 20
    """, as_dict=True)

    return data


@frappe.whitelist()
def get_supplier_performance():
    """Get supplier performance metrics."""
    data = frappe.db.sql("""
        SELECT
            s.name as supplier,
            s.supplier_name,
            s.total_po_count as po_count,
            s.total_po_value as total_value,
            ROUND(s.total_po_value / NULLIF(s.total_po_count, 0), 2) as avg_order_value,
            COALESCE(s.on_time_rate, 0) as on_time_delivery_rate
        FROM `tabBEI Supplier` s
        WHERE s.status = 'Active'
        ORDER BY s.total_po_value DESC
        LIMIT 10
    """, as_dict=True)

    return data
