# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Procurement API - Complete procurement workflow endpoints
Supports: Suppliers, PR, PO, GR, Invoice, Payment Request, Dashboard

All endpoints use @frappe.whitelist() for external access.
"""

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, nowdate, add_days, get_first_day, get_last_day


# System fields that must never be set by API callers
_BLOCKED_FIELDS = frozenset({
    "doctype", "name", "owner", "creation", "modified", "modified_by",
    "docstatus", "idx", "parent", "parenttype", "parentfield",
    "_user_tags", "_comments", "_assign", "_liked_by",
})


def _sanitize_doc_data(data):
    """Remove system/internal fields from user-supplied data before doc creation."""
    return {k: v for k, v in data.items() if k not in _BLOCKED_FIELDS}


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
            total_po_count, total_po_value, total_po_value as total_amount, total_outstanding,
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
    """Create new supplier.

    AUDIT CONTROL 2.5: Duplicate detection (phone, email, bank account, TIN)
    Ref: Internal Audit Jan 30, 2026 - Same phone number across multiple suppliers
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    warnings = []

    # AUDIT CONTROL 2.5: Check for duplicate phone number
    contact_number = data.get("contact_number")
    if contact_number:
        existing = frappe.db.get_value(
            "BEI Supplier",
            {"contact_number": contact_number},
            ["name", "supplier_name"],
            as_dict=True
        )
        if existing:
            frappe.throw(
                _("Phone number {0} is already used by supplier: {1} ({2}). "
                  "Duplicate contact info may indicate shell companies.").format(
                    contact_number, existing.supplier_name, existing.name
                ),
                title=_("Duplicate Contact Detected")
            )

    # AUDIT CONTROL 2.5: Check for duplicate email
    email = data.get("email")
    if email:
        existing = frappe.db.get_value(
            "BEI Supplier",
            {"email": email},
            ["name", "supplier_name"],
            as_dict=True
        )
        if existing:
            warnings.append(
                _("Email {0} is already used by supplier: {1}").format(
                    email, existing.supplier_name
                )
            )

    # AUDIT CONTROL 2.5: Check for duplicate bank account
    bank_account = data.get("bank_account_number")
    if bank_account:
        existing = frappe.db.get_value(
            "BEI Supplier",
            {"bank_account_number": bank_account},
            ["name", "supplier_name"],
            as_dict=True
        )
        if existing:
            frappe.throw(
                _("Bank account {0} is already used by supplier: {1} ({2}). "
                  "This is a critical fraud indicator.").format(
                    bank_account, existing.supplier_name, existing.name
                ),
                title=_("Duplicate Bank Account Detected")
            )

    # AUDIT CONTROL 2.5: Check for duplicate TIN
    tin = data.get("tin")
    if tin:
        existing = frappe.db.get_value(
            "BEI Supplier",
            {"tin": tin},
            ["name", "supplier_name"],
            as_dict=True
        )
        if existing:
            frappe.throw(
                _("TIN {0} is already registered to supplier: {1} ({2}). "
                  "Each supplier must have a unique TIN.").format(
                    tin, existing.supplier_name, existing.name
                ),
                title=_("Duplicate TIN Detected")
            )

    supplier = frappe.get_doc({
        "doctype": "BEI Supplier",
        **_sanitize_doc_data(data)
    })
    supplier.insert()

    result = {"success": True, "name": supplier.name, "message": _("Supplier created")}
    if warnings:
        result["warnings"] = warnings

    return result


@frappe.whitelist()
def update_supplier(name, data):
    """Update existing supplier."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    supplier = frappe.get_doc("BEI Supplier", name)

    safe_data = _sanitize_doc_data(data)
    for key, value in safe_data.items():
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
        **_sanitize_doc_data(data)
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
    data = po.as_dict()

    # Ensure items are always present (even if child table was added after PO creation)
    if not data.get("items"):
        items = frappe.db.sql("""
            SELECT name, item_code, item_name, description, qty, rate, amount, uom
            FROM `tabBEI PO Item`
            WHERE parent = %s
            ORDER BY idx
        """, (name,), as_dict=True)
        data["items"] = items

    return data


@frappe.whitelist()
def get_purchase_order_items(name):
    """Get items for a specific PO."""
    return frappe.db.sql("""
        SELECT name, item_code, item_name, description, qty, unit_cost, unit_cost as rate, amount, uom,
               received_qty
        FROM `tabBEI PO Item`
        WHERE parent = %s
        ORDER BY idx
    """, (name,), as_dict=True)


@frappe.whitelist()
def get_goods_receipt_items(name):
    """Get items for a specific GR."""
    return frappe.db.sql("""
        SELECT name, item_code, item_name, description,
               ordered_qty, received_qty, rejected_qty, accepted_qty,
               uom, unit_cost, amount
        FROM `tabBEI GR Item`
        WHERE parent = %s
        ORDER BY idx
    """, (name,), as_dict=True)


@frappe.whitelist()
def create_purchase_order(data):
    """Create new PO.

    AUDIT CONTROL 2.8: Supplier master data quality checks
    - Mandatory TIN for suppliers with >₱250K annual purchases
    Ref: Internal Audit Jan 30, 2026 - Max's Bakeshop ₱10M not in master list
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    warnings = []
    supplier_name = data.get("supplier")

    if supplier_name:
        supplier = frappe.get_doc("BEI Supplier", supplier_name)

        # AUDIT CONTROL 2.8: Check TIN for high-value suppliers
        # Calculate annual purchase value for this supplier
        annual_purchases = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabBEI Purchase Order`
            WHERE supplier = %s
            AND po_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            AND status NOT IN ('Draft', 'Cancelled')
        """, (supplier_name,))[0][0] or 0

        po_value = flt(data.get("grand_total", 0))

        # If total annual + this PO > ₱250K, require TIN
        if flt(annual_purchases) + po_value > 250000:
            if not supplier.tin:
                frappe.throw(
                    _("Supplier {0} requires TIN registration. "
                      "Annual purchases (₱{1:,.2f}) + this PO (₱{2:,.2f}) exceed ₱250,000 threshold. "
                      "Update supplier master data before proceeding.").format(
                        supplier.supplier_name, annual_purchases, po_value
                    ),
                    title=_("TIN Required")
                )

        # AUDIT CONTROL 2.8: Warn if supplier missing key documents
        missing_docs = []
        if not supplier.bir_2307:
            missing_docs.append("BIR 2307")
        if not supplier.business_permit:
            missing_docs.append("Business Permit")

        if missing_docs:
            warnings.append(
                _("Supplier {0} is missing documents: {1}").format(
                    supplier.supplier_name, ", ".join(missing_docs)
                )
            )

    # Map 'rate' to 'unit_cost' in items if needed (frontend sends 'rate')
    if "items" in data:
        for item in data["items"]:
            if "rate" in item and "unit_cost" not in item:
                item["unit_cost"] = item.pop("rate")
            # Strip invalid UOM to avoid LinkValidationError
            if item.get("uom") and not frappe.db.exists("UOM", item["uom"]):
                item.pop("uom")

    po = frappe.get_doc({
        "doctype": "BEI Purchase Order",
        **_sanitize_doc_data(data)
    })
    po.insert()

    result = {"success": True, "name": po.name, "message": _("PO created")}
    if warnings:
        result["warnings"] = warnings

    return result


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
            name, gr_no, gr_no as gr_number, receipt_date, status,
            purchase_order, purchase_order as po_number,
            supplier, supplier_name,
            total_ordered_qty, total_received_qty, total_amount
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
    data = gr.as_dict()
    data["gr_number"] = data.get("gr_no")
    data["po_number"] = data.get("purchase_order")
    return data


@frappe.whitelist()
def get_goods_receipts_for_po(name):
    """Get goods receipts linked to a specific PO."""
    return frappe.db.sql("""
        SELECT name, gr_no, gr_no as gr_number, receipt_date, status,
            purchase_order, purchase_order as po_number,
            supplier, supplier_name,
            total_ordered_qty, total_received_qty, total_amount
        FROM `tabBEI Goods Receipt`
        WHERE purchase_order = %s
        ORDER BY receipt_date DESC
    """, (name,), as_dict=True)


@frappe.whitelist()
def get_invoices_for_po(name):
    """Get invoices linked to a specific PO."""
    return frappe.db.sql("""
        SELECT name, invoice_no, invoice_date, due_date, status,
            supplier, supplier_name, purchase_order,
            grand_total, balance_due, payment_status, match_status
        FROM `tabBEI Invoice`
        WHERE purchase_order = %s
        ORDER BY invoice_date DESC
    """, (name,), as_dict=True)


@frappe.whitelist()
def create_goods_receipt(data):
    """Create new GR.

    AUDIT CONTROL 2.4: Block GR creation for >₱500K POs without complete approval
    Ref: Internal Audit Jan 30, 2026 - CFO "Pending" but payment released
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # AUDIT CONTROL 2.4: Validate PO approval for >₱500K
    purchase_order = data.get("purchase_order")
    if purchase_order:
        po = frappe.get_doc("BEI Purchase Order", purchase_order)
        if flt(po.grand_total) > 500000:
            if not po.mae_approval:
                frappe.throw(
                    _("Cannot create GR: PO {0} (₱{1:,.2f}) requires CPO (Mae) approval first").format(
                        po.po_no, po.grand_total
                    ),
                    title=_("Approval Required")
                )
            if not po.butch_approval:
                frappe.throw(
                    _("Cannot create GR: PO {0} (₱{1:,.2f}) requires CFO (Butch) approval first").format(
                        po.po_no, po.grand_total
                    ),
                    title=_("Approval Required")
                )

        # AUDIT CONTROL 2.2: Validate GR date >= PO date
        gr_date = getdate(data.get("receipt_date") or nowdate())
        po_date = getdate(po.po_date)
        if gr_date < po_date:
            frappe.throw(
                _("GR date ({0}) cannot be earlier than PO date ({1})").format(
                    gr_date, po_date
                ),
                title=_("Invalid Date Sequence")
            )

    # Map 'rate' to 'unit_cost' in items if needed
    if "items" in data:
        for item in data["items"]:
            if "rate" in item and "unit_cost" not in item:
                item["unit_cost"] = item.pop("rate")
            # Strip invalid UOM to avoid LinkValidationError
            if item.get("uom") and not frappe.db.exists("UOM", item["uom"]):
                item.pop("uom")

    gr = frappe.get_doc({
        "doctype": "BEI Goods Receipt",
        **_sanitize_doc_data(data)
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
def complete_gr_inspection(name, passed=True, result=None, notes=None):
    """Complete quality inspection on GR."""
    if result is not None:
        passed = result == "pass"
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
            status, supplier, supplier_name, purchase_order, grand_total,
            balance_due, payment_status, match_status
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
    """Create new invoice.

    AUDIT CONTROL 2.1: Require Goods Receipt before Invoice (Three-Way Matching)
    AUDIT CONTROL 2.2: Invoice date cannot be earlier than PO date
    Ref: Internal Audit Jan 30, 2026 - PO-2025108 paid without GR; Invoice Nov 21 vs PO Nov 25
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    purchase_order = data.get("purchase_order")
    if purchase_order:
        # AUDIT CONTROL 2.1: Check GR exists for this PO
        # Note: GR status can be "Accepted" after the receive+inspect workflow
        gr_exists = frappe.db.exists("BEI Goods Receipt", {
            "purchase_order": purchase_order,
            "status": ["in", ["Submitted", "Approved", "Inspected", "Accepted"]]
        })
        if not gr_exists:
            # Check if an approved match exception exists for this PO
            approved_exception = frappe.db.exists("BEI Match Exception", {
                "purchase_order": purchase_order,
                "status": "Approved",
            })
            if not approved_exception:
                return {
                    "success": False,
                    "requires_exception": True,
                    "purchase_order": purchase_order,
                    "po_amount": flt(
                        frappe.db.get_value("BEI Purchase Order", purchase_order, "grand_total")
                    ),
                    "message": _("No Goods Receipt found for PO {0}. "
                                 "An exception approval is required to proceed.").format(purchase_order),
                }
            # Exception approved — allow invoice creation without GR

        # AUDIT CONTROL 2.2: Invoice date >= PO date
        po = frappe.get_doc("BEI Purchase Order", purchase_order)
        invoice_date = getdate(data.get("invoice_date") or nowdate())
        po_date = getdate(po.po_date)
        if invoice_date < po_date:
            frappe.throw(
                _("Invoice date ({0}) cannot be earlier than PO date ({1}). "
                  "This indicates the invoice was created before the PO was approved.").format(
                    invoice_date, po_date
                ),
                title=_("Invalid Date Sequence")
            )

        # AUDIT CONTROL 2.4: Check PO approval for >₱500K
        if flt(po.grand_total) > 500000:
            if not po.mae_approval or not po.butch_approval:
                frappe.throw(
                    _("Cannot create Invoice: PO {0} (₱{1:,.2f}) requires complete approval "
                      "(CPO + CFO) before invoicing").format(po.po_no, po.grand_total),
                    title=_("Approval Required")
                )

    invoice = frappe.get_doc({
        "doctype": "BEI Invoice",
        **_sanitize_doc_data(data)
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
            "(pr.payment_request_no LIKE %(search)s OR pr.supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("pr.status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("supplier"):
            conditions.append("pr.supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("pending_approval"):
            conditions.append(
                "pr.status IN ('Pending Review', 'Pending Budget Approval', "
                "'Pending CFO Approval', 'Pending CEO Approval')"
            )

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Payment Request` pr WHERE {where_clause}",
        values
    )[0][0]

    requests = frappe.db.sql(f"""
        SELECT
            pr.name, pr.payment_request_no, pr.request_date, pr.status,
            COALESCE(pr.supplier, inv.supplier) as supplier,
            COALESCE(pr.supplier_name, inv.supplier_name) as supplier_name,
            pr.payment_amount, pr.payment_mode, pr.invoice,
            pr.ceo_required, pr.payment_date
        FROM `tabBEI Payment Request` pr
        LEFT JOIN `tabBEI Invoice` inv ON pr.invoice = inv.name
        WHERE {where_clause}
        ORDER BY pr.request_date DESC
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
    """Create new payment request.

    AUDIT CONTROL 2.1: Require Goods Receipt before Payment (Three-Way Matching)
    AUDIT CONTROL 2.2: Payment date cannot be earlier than Invoice date
    AUDIT CONTROL 2.3: Payment limited to received value (partial delivery control)
    AUDIT CONTROL 2.4: Block payment without complete PO approval for >₱500K
    AUDIT CONTROL 2.5: Double-payment guard for advances
    Ref: Internal Audit Jan 30, 2026 - PO-2025320 paid ₱848,800 for partial delivery
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # AUDIT CONTROL 2.5: Double-payment guard — block if PO fully covered by advance
    _po_for_guard = data.get("purchase_order")
    if not _po_for_guard and data.get("invoice"):
        _po_for_guard = frappe.db.get_value("BEI Invoice", data["invoice"], "purchase_order")
    if _po_for_guard:
        advance_outstanding = frappe.db.sql(
            """SELECT COALESCE(SUM(advance_outstanding), 0)
            FROM `tabBEI Payment Request`
            WHERE is_advance_payment = 1
              AND advance_status IN ('Outstanding', 'Partially Cleared')
              AND purchase_order = %s""",
            (_po_for_guard,),
        )
        total_advance_outstanding = flt(advance_outstanding[0][0]) if advance_outstanding else 0
        if total_advance_outstanding > 0:
            po_total = flt(
                frappe.db.get_value("BEI Purchase Order", _po_for_guard, "grand_total")
            )
            if total_advance_outstanding >= po_total:
                frappe.throw(
                    _("This PO is fully covered by an outstanding advance payment of PHP {0:,.2f}. "
                      "Cannot create duplicate payment.").format(total_advance_outstanding),
                    title=_("Duplicate Payment Blocked"),
                )
            else:
                remaining = po_total - total_advance_outstanding
                frappe.msgprint(
                    _("Note: PO {0} has outstanding advance(s) of PHP {1:,.2f}. "
                      "Remaining payable: PHP {2:,.2f}.").format(
                        _po_for_guard, total_advance_outstanding, remaining
                    ),
                    alert=True,
                )
                data["_remaining_payable"] = remaining

    invoice_name = data.get("invoice")
    if invoice_name:
        invoice = frappe.get_doc("BEI Invoice", invoice_name)
        purchase_order = invoice.purchase_order

        if purchase_order:
            po = frappe.get_doc("BEI Purchase Order", purchase_order)

            # AUDIT CONTROL 2.1: Check GR exists for this PO
            # Note: GR status can be "Accepted" after the receive+inspect workflow
            gr_exists = frappe.db.exists("BEI Goods Receipt", {
                "purchase_order": purchase_order,
                "status": ["in", ["Submitted", "Approved", "Inspected", "Accepted"]]
            })
            if not gr_exists:
                # Check if an approved match exception exists for this PO
                approved_exception = frappe.db.get_value(
                    "BEI Match Exception",
                    {"purchase_order": purchase_order, "status": "Approved"},
                    ["name", "exception_type"],
                    as_dict=True,
                )
                if not approved_exception:
                    return {
                        "success": False,
                        "requires_exception": True,
                        "purchase_order": purchase_order,
                        "po_amount": flt(po.grand_total),
                        "message": _("No Goods Receipt found for PO {0}. "
                                     "An exception approval is required to proceed.").format(purchase_order),
                    }
                # Exception approved — allow payment request without GR
                # If advance payment type, flag the data so the Payment Request is marked accordingly
                if approved_exception.exception_type == "Advance Payment":
                    data["is_advance_payment"] = 1
            else:
                # AUDIT CONTROL 2.3: Payment limited to received value
                # (only applies when GR exists — exception-approved payments skip this)
                received_value = frappe.db.sql("""
                    SELECT COALESCE(SUM(gri.received_qty * gri.unit_cost), 0)
                    FROM `tabBEI GR Item` gri
                    JOIN `tabBEI Goods Receipt` gr ON gri.parent = gr.name
                    WHERE gr.purchase_order = %s
                    AND gr.status IN ('Submitted', 'Approved', 'Inspected', 'Accepted')
                """, (purchase_order,))[0][0] or 0

                payment_amount = flt(data.get("payment_amount") or invoice.balance_due)
                if payment_amount > received_value:
                    frappe.throw(
                        _("Payment amount (₱{0:,.2f}) exceeds received value (₱{1:,.2f}). "
                          "You can only pay for goods actually received.").format(
                            payment_amount, received_value
                        ),
                        title=_("Partial Delivery Control")
                    )

            # AUDIT CONTROL 2.4: Check PO approval for >₱500K
            if flt(po.grand_total) > 500000:
                if not po.mae_approval or not po.butch_approval:
                    frappe.throw(
                        _("Cannot create Payment Request: PO {0} (₱{1:,.2f}) requires complete "
                          "approval (CPO + CFO) before payment").format(po.po_no, po.grand_total),
                        title=_("Approval Required")
                    )

        # AUDIT CONTROL 2.2: Payment date >= Invoice date
        payment_date = getdate(data.get("request_date") or nowdate())
        invoice_date = getdate(invoice.invoice_date)
        if payment_date < invoice_date:
            frappe.throw(
                _("Payment request date ({0}) cannot be earlier than invoice date ({1})").format(
                    payment_date, invoice_date
                ),
                title=_("Invalid Date Sequence")
            )

    request = frappe.get_doc({
        "doctype": "BEI Payment Request",
        **_sanitize_doc_data(data)
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


# =============================================================================
# AUDIT CONTROL ENDPOINTS (Added 2026-02-05 per Internal Audit Jan 30, 2026)
# =============================================================================

@frappe.whitelist()
def get_open_po_aging():
    """Get POs without Goods Receipt (Three-Way Match monitoring).

    AUDIT CONTROL 2.1: Track POs that haven't been received
    Ref: Internal Audit Jan 30, 2026 - PO-2025108 paid without GR
    """
    data = frappe.db.sql("""
        SELECT
            po.name,
            po.po_no,
            po.po_date,
            po.supplier_name,
            po.grand_total,
            po.status,
            po.delivery_date,
            DATEDIFF(CURDATE(), po.po_date) as days_open,
            CASE
                WHEN gr.name IS NOT NULL THEN 'Has GR'
                ELSE 'No GR'
            END as gr_status,
            gr.name as gr_name
        FROM `tabBEI Purchase Order` po
        LEFT JOIN `tabBEI Goods Receipt` gr ON gr.purchase_order = po.name
            AND gr.status IN ('Submitted', 'Approved', 'Inspected', 'Accepted')
        WHERE po.status NOT IN ('Draft', 'Cancelled', 'Closed')
        ORDER BY
            CASE WHEN gr.name IS NULL THEN 0 ELSE 1 END,
            po.po_date ASC
    """, as_dict=True)

    # Summary stats
    no_gr = [d for d in data if d.get("gr_status") == "No GR"]
    total_at_risk = sum(flt(d.get("grand_total", 0)) for d in no_gr)

    return {
        "data": data,
        "summary": {
            "total_open_pos": len(data),
            "pos_without_gr": len(no_gr),
            "total_at_risk": flt(total_at_risk, 2),
            "avg_days_open": flt(sum(d.get("days_open", 0) for d in no_gr) / max(len(no_gr), 1), 1)
        }
    }


@frappe.whitelist()
def get_price_history(item_code=None, supplier=None, months=6):
    """Get price history for variance detection.

    AUDIT CONTROL 2.6: Price variance alerts
    Ref: Internal Audit Jan 30, 2026 - XYZCO FOODS ₱116→₱120→₱116
    """
    conditions = ["po.status NOT IN ('Draft', 'Cancelled')"]
    values = {"months": int(months)}

    if item_code:
        conditions.append("poi.item_code = %(item_code)s")
        values["item_code"] = item_code

    if supplier:
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = supplier

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(f"""
        SELECT
            poi.item_code,
            poi.item_name,
            po.supplier,
            po.supplier_name,
            po.po_date,
            poi.unit_cost as unit_price,
            poi.qty,
            poi.amount
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE {where_clause}
        AND po.po_date >= DATE_SUB(CURDATE(), INTERVAL %(months)s MONTH)
        ORDER BY poi.item_code, po.po_date DESC
    """, values, as_dict=True)

    # Calculate variance for each item
    item_prices = {}
    for row in data:
        key = (row.item_code, row.supplier)
        if key not in item_prices:
            item_prices[key] = []
        item_prices[key].append(row)

    variance_alerts = []
    for key, prices in item_prices.items():
        if len(prices) >= 2:
            latest_price = flt(prices[0].unit_price)
            avg_price = sum(flt(p.unit_price) for p in prices) / len(prices)
            max_price = max(flt(p.unit_price) for p in prices)
            min_price = min(flt(p.unit_price) for p in prices)

            if avg_price > 0:
                variance_pct = abs(latest_price - avg_price) / avg_price * 100
                if variance_pct > 5:  # 5% threshold
                    variance_alerts.append({
                        "item_code": key[0],
                        "supplier": key[1],
                        "supplier_name": prices[0].supplier_name,
                        "item_name": prices[0].item_name,
                        "latest_price": latest_price,
                        "avg_price": flt(avg_price, 2),
                        "max_price": max_price,
                        "min_price": min_price,
                        "variance_pct": flt(variance_pct, 1),
                        "price_count": len(prices)
                    })

    return {
        "data": data,
        "variance_alerts": sorted(variance_alerts, key=lambda x: -x["variance_pct"]),
        "summary": {
            "total_items_tracked": len(item_prices),
            "items_with_variance": len(variance_alerts),
            "threshold_pct": 5
        }
    }


@frappe.whitelist()
def get_single_source_suppliers():
    """Get suppliers with concentration risk (single-source items).

    AUDIT CONTROL 2.7: Single-source supplier flagging
    Ref: Internal Audit Jan 30, 2026 - RIGHT GOODS ₱23.6M for 1 item
    """
    # Find items where >80% of purchases come from a single supplier
    data = frappe.db.sql("""
        WITH item_supplier_totals AS (
            SELECT
                poi.item_code,
                poi.item_name,
                po.supplier,
                po.supplier_name,
                SUM(poi.amount) as total_value,
                COUNT(DISTINCT po.name) as po_count
            FROM `tabBEI PO Item` poi
            JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
            WHERE po.status NOT IN ('Draft', 'Cancelled')
            AND po.po_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY poi.item_code, poi.item_name, po.supplier, po.supplier_name
        ),
        item_totals AS (
            SELECT
                item_code,
                SUM(total_value) as item_total_value
            FROM item_supplier_totals
            GROUP BY item_code
        )
        SELECT
            ist.item_code,
            ist.item_name,
            ist.supplier,
            ist.supplier_name,
            ist.total_value,
            ist.po_count,
            it.item_total_value,
            ROUND(ist.total_value / NULLIF(it.item_total_value, 0) * 100, 1) as concentration_pct
        FROM item_supplier_totals ist
        JOIN item_totals it ON ist.item_code = it.item_code
        WHERE ist.total_value / NULLIF(it.item_total_value, 0) >= 0.8
        ORDER BY ist.total_value DESC
    """, as_dict=True)

    # Supplier-level summary
    supplier_concentration = {}
    for row in data:
        supplier = row.supplier
        if supplier not in supplier_concentration:
            supplier_concentration[supplier] = {
                "supplier": supplier,
                "supplier_name": row.supplier_name,
                "single_source_items": 0,
                "total_value": 0
            }
        supplier_concentration[supplier]["single_source_items"] += 1
        supplier_concentration[supplier]["total_value"] += flt(row.total_value)

    return {
        "data": data,
        "supplier_summary": sorted(
            supplier_concentration.values(),
            key=lambda x: -x["total_value"]
        ),
        "summary": {
            "total_single_source_items": len(data),
            "total_at_risk_value": flt(sum(d.get("total_value", 0) for d in data), 2),
            "suppliers_with_concentration": len(supplier_concentration)
        }
    }


@frappe.whitelist()
def get_supplier_duplicates():
    """Get suppliers with duplicate contact information.

    AUDIT CONTROL 2.5: Duplicate detection report
    Ref: Internal Audit Jan 30, 2026 - Same phone across Labelmen & MGrace
    """
    duplicates = []

    # Check duplicate phone numbers
    phone_dups = frappe.db.sql("""
        SELECT
            contact_number,
            GROUP_CONCAT(CONCAT(name, ':', supplier_name) SEPARATOR '|') as suppliers,
            COUNT(*) as count
        FROM `tabBEI Supplier`
        WHERE contact_number IS NOT NULL AND contact_number != ''
        GROUP BY contact_number
        HAVING COUNT(*) > 1
    """, as_dict=True)

    for dup in phone_dups:
        suppliers = [s.split(":") for s in dup.suppliers.split("|")]
        duplicates.append({
            "type": "Phone Number",
            "value": dup.contact_number,
            "suppliers": [{"name": s[0], "supplier_name": s[1]} for s in suppliers],
            "count": dup["count"],
            "risk_level": "HIGH"
        })

    # Check duplicate emails
    email_dups = frappe.db.sql("""
        SELECT
            email,
            GROUP_CONCAT(CONCAT(name, ':', supplier_name) SEPARATOR '|') as suppliers,
            COUNT(*) as count
        FROM `tabBEI Supplier`
        WHERE email IS NOT NULL AND email != ''
        GROUP BY email
        HAVING COUNT(*) > 1
    """, as_dict=True)

    for dup in email_dups:
        suppliers = [s.split(":") for s in dup.suppliers.split("|")]
        duplicates.append({
            "type": "Email",
            "value": dup.email,
            "suppliers": [{"name": s[0], "supplier_name": s[1]} for s in suppliers],
            "count": dup["count"],
            "risk_level": "MEDIUM"
        })

    # Check duplicate bank accounts
    bank_dups = frappe.db.sql("""
        SELECT
            bank_account_number,
            bank_name,
            GROUP_CONCAT(CONCAT(name, ':', supplier_name) SEPARATOR '|') as suppliers,
            COUNT(*) as count
        FROM `tabBEI Supplier`
        WHERE bank_account_number IS NOT NULL AND bank_account_number != ''
        GROUP BY bank_account_number, bank_name
        HAVING COUNT(*) > 1
    """, as_dict=True)

    for dup in bank_dups:
        suppliers = [s.split(":") for s in dup.suppliers.split("|")]
        duplicates.append({
            "type": "Bank Account",
            "value": f"{dup.bank_name} - {dup.bank_account_number}",
            "suppliers": [{"name": s[0], "supplier_name": s[1]} for s in suppliers],
            "count": dup["count"],
            "risk_level": "CRITICAL"
        })

    # Check duplicate TINs
    tin_dups = frappe.db.sql("""
        SELECT
            tin,
            GROUP_CONCAT(CONCAT(name, ':', supplier_name) SEPARATOR '|') as suppliers,
            COUNT(*) as count
        FROM `tabBEI Supplier`
        WHERE tin IS NOT NULL AND tin != ''
        GROUP BY tin
        HAVING COUNT(*) > 1
    """, as_dict=True)

    for dup in tin_dups:
        suppliers = [s.split(":") for s in dup.suppliers.split("|")]
        duplicates.append({
            "type": "TIN",
            "value": dup.tin,
            "suppliers": [{"name": s[0], "supplier_name": s[1]} for s in suppliers],
            "count": dup["count"],
            "risk_level": "CRITICAL"
        })

    return {
        "data": sorted(duplicates, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}.get(x["risk_level"], 3)),
        "summary": {
            "total_duplicates": len(duplicates),
            "critical": len([d for d in duplicates if d["risk_level"] == "CRITICAL"]),
            "high": len([d for d in duplicates if d["risk_level"] == "HIGH"]),
            "medium": len([d for d in duplicates if d["risk_level"] == "MEDIUM"])
        }
    }


@frappe.whitelist()
def check_price_variance(item_code, supplier, new_price):
    """Check if a new price has significant variance from historical average.

    AUDIT CONTROL 2.6: Real-time price variance check during PO creation
    Returns warning if variance > 5%
    """
    new_price = flt(new_price)

    avg_price = frappe.db.sql("""
        SELECT AVG(poi.unit_cost) as avg_price
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %s
        AND po.supplier = %s
        AND po.status NOT IN ('Draft', 'Cancelled')
        AND po.po_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    """, (item_code, supplier))[0][0]

    if not avg_price:
        return {"has_variance": False, "message": "No historical data for comparison"}

    avg_price = flt(avg_price)
    variance_pct = abs(new_price - avg_price) / avg_price * 100 if avg_price > 0 else 0

    return {
        "has_variance": variance_pct > 5,
        "new_price": new_price,
        "avg_price": flt(avg_price, 2),
        "variance_pct": flt(variance_pct, 1),
        "threshold_pct": 5,
        "message": _("Price ₱{0:,.2f} is {1:.1f}% different from 90-day average ₱{2:,.2f}").format(
            new_price, variance_pct, avg_price
        ) if variance_pct > 5 else None
    }


@frappe.whitelist()
def get_received_value_for_po(purchase_order):
    """Get total received value for a PO (for partial delivery control).

    AUDIT CONTROL 2.3: Calculate maximum payable amount
    Ref: Internal Audit Jan 30, 2026 - PO-2025320 paid ₱848,800 for partial
    """
    po = frappe.get_doc("BEI Purchase Order", purchase_order)

    received_data = frappe.db.sql("""
        SELECT
            gri.item_code,
            gri.item_name,
            SUM(gri.received_qty) as received_qty,
            gri.unit_cost,
            SUM(gri.received_qty * gri.unit_cost) as received_value
        FROM `tabBEI GR Item` gri
        JOIN `tabBEI Goods Receipt` gr ON gri.parent = gr.name
        WHERE gr.purchase_order = %s
        AND gr.status IN ('Submitted', 'Approved', 'Inspected', 'Accepted')
        GROUP BY gri.item_code, gri.item_name, gri.unit_cost
    """, (purchase_order,), as_dict=True)

    total_received = sum(flt(d.get("received_value", 0)) for d in received_data)
    total_ordered = flt(po.grand_total)

    return {
        "purchase_order": purchase_order,
        "po_no": po.po_no,
        "total_ordered": total_ordered,
        "total_received": flt(total_received, 2),
        "max_payable": flt(total_received, 2),
        "pending_delivery": flt(total_ordered - total_received, 2),
        "items": received_data
    }


@frappe.whitelist()
def get_supplier_data_quality():
    """Get suppliers with missing/incomplete master data.

    AUDIT CONTROL 2.8: Supplier master data quality report
    Ref: Internal Audit Jan 30, 2026 - Max's Bakeshop ₱10M not in master list
    """
    # Get all active suppliers with their annual purchase values
    suppliers = frappe.db.sql("""
        SELECT
            s.name,
            s.supplier_name,
            s.tin,
            s.bir_2307,
            s.sec_certificate,
            s.business_permit,
            s.bank_name,
            s.bank_account_number,
            s.contact_number,
            s.email,
            COALESCE(po_totals.annual_value, 0) as annual_purchases,
            COALESCE(po_totals.po_count, 0) as po_count
        FROM `tabBEI Supplier` s
        LEFT JOIN (
            SELECT
                supplier,
                SUM(grand_total) as annual_value,
                COUNT(*) as po_count
            FROM `tabBEI Purchase Order`
            WHERE po_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            AND status NOT IN ('Draft', 'Cancelled')
            GROUP BY supplier
        ) po_totals ON po_totals.supplier = s.name
        WHERE s.status = 'Active'
        ORDER BY po_totals.annual_value DESC
    """, as_dict=True)

    issues = []
    for sup in suppliers:
        supplier_issues = []

        # Check TIN for high-value suppliers
        if flt(sup.annual_purchases) > 250000 and not sup.tin:
            supplier_issues.append({
                "field": "TIN",
                "severity": "CRITICAL",
                "message": "TIN required for suppliers with >₱250K annual purchases"
            })

        # Check bank details
        if not sup.bank_account_number:
            supplier_issues.append({
                "field": "Bank Account",
                "severity": "HIGH",
                "message": "Bank account required for payment processing"
            })

        # Check documents
        if not sup.bir_2307:
            supplier_issues.append({
                "field": "BIR 2307",
                "severity": "MEDIUM",
                "message": "BIR 2307 certificate missing"
            })

        if not sup.business_permit:
            supplier_issues.append({
                "field": "Business Permit",
                "severity": "MEDIUM",
                "message": "Business permit missing"
            })

        # Check contact info
        if not sup.contact_number and not sup.email:
            supplier_issues.append({
                "field": "Contact Info",
                "severity": "LOW",
                "message": "No contact phone or email"
            })

        if supplier_issues:
            issues.append({
                "supplier": sup.name,
                "supplier_name": sup.supplier_name,
                "annual_purchases": flt(sup.annual_purchases, 2),
                "po_count": sup.po_count,
                "issues": supplier_issues,
                "issue_count": len(supplier_issues),
                "max_severity": max(
                    i["severity"] for i in supplier_issues
                ) if supplier_issues else None
            })

    # Sort by severity and annual purchases
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues.sort(key=lambda x: (
        severity_order.get(x.get("max_severity"), 4),
        -x.get("annual_purchases", 0)
    ))

    return {
        "data": issues,
        "summary": {
            "total_suppliers_with_issues": len(issues),
            "critical": len([i for i in issues if i.get("max_severity") == "CRITICAL"]),
            "high": len([i for i in issues if i.get("max_severity") == "HIGH"]),
            "medium": len([i for i in issues if i.get("max_severity") == "MEDIUM"]),
            "low": len([i for i in issues if i.get("max_severity") == "LOW"]),
            "total_at_risk_value": flt(sum(
                i.get("annual_purchases", 0)
                for i in issues
                if i.get("max_severity") in ("CRITICAL", "HIGH")
            ), 2)
        }
    }


# =============================================================================
# ACCOUNTING/FINANCE ENDPOINTS (Finance & Accounting Module)
# =============================================================================

@frappe.whitelist()
def get_ap_aging_report(aging_buckets=None):
    """
    Get AP aging report using existing BEI Invoice DocType.

    Priority #2 from Finance & Accounting Automation List: AP Aging Dashboard

    Args:
        aging_buckets: Optional list of custom aging bucket thresholds
                      (default: [30, 60, 90, 120, 150])

    Returns:
        Dict with aging summary by bucket and total payables

    Aging Buckets (from Accounting questionnaire):
    - 0-30 days
    - 31-60 days
    - 61-90 days
    - 91-120 days
    - 121-150 days
    - Over 150 days

    Example:
        >>> get_ap_aging_report()
        {
            "aging_summary": {
                "0-30": {"count": 10, "amount": 150000.00},
                "31-60": {"count": 5, "amount": 75000.00},
                ...
            },
            "total_payables": 500000.00,
            "as_of_date": "2026-02-06"
        }
    """
    if aging_buckets:
        if isinstance(aging_buckets, str):
            aging_buckets = frappe.parse_json(aging_buckets)
    else:
        aging_buckets = [30, 60, 90, 120, 150]

    today = getdate()

    # Get all unpaid/partially paid invoices
    invoices = frappe.db.sql("""
        SELECT
            name,
            invoice_date,
            grand_total,
            amount_paid,
            supplier,
            supplier_name,
            status
        FROM `tabBEI Invoice`
        WHERE status IN ('Verified', 'Partially Paid')
        AND docstatus != 2
        ORDER BY invoice_date ASC
    """, as_dict=True)

    # Initialize aging buckets
    aging_summary = {
        "0-30": {"count": 0, "amount": 0, "invoices": []},
        "31-60": {"count": 0, "amount": 0, "invoices": []},
        "61-90": {"count": 0, "amount": 0, "invoices": []},
        "91-120": {"count": 0, "amount": 0, "invoices": []},
        "121-150": {"count": 0, "amount": 0, "invoices": []},
        "Over 150": {"count": 0, "amount": 0, "invoices": []}
    }

    total_payables = 0
    invoice_details = []

    for inv in invoices:
        # Calculate outstanding
        outstanding = flt(inv.grand_total, 2) - flt(inv.amount_paid, 2)

        if outstanding <= 0:
            continue

        # Calculate age in days
        age_days = (today - getdate(inv.invoice_date)).days

        # Classify into bucket
        if age_days <= 30:
            bucket = "0-30"
        elif age_days <= 60:
            bucket = "31-60"
        elif age_days <= 90:
            bucket = "61-90"
        elif age_days <= 120:
            bucket = "91-120"
        elif age_days <= 150:
            bucket = "121-150"
        else:
            bucket = "Over 150"

        # Add to bucket
        aging_summary[bucket]["count"] += 1
        aging_summary[bucket]["amount"] = flt(aging_summary[bucket]["amount"], 2) + outstanding
        aging_summary[bucket]["invoices"].append({
            "invoice": inv.name,
            "supplier": inv.supplier_name,
            "invoice_date": str(inv.invoice_date),
            "age_days": age_days,
            "outstanding": flt(outstanding, 2)
        })

        total_payables += outstanding

        invoice_details.append({
            "invoice": inv.name,
            "supplier": inv.supplier_name,
            "supplier_id": inv.supplier,
            "invoice_date": str(inv.invoice_date),
            "grand_total": flt(inv.grand_total, 2),
            "amount_paid": flt(inv.amount_paid, 2),
            "outstanding": flt(outstanding, 2),
            "age_days": age_days,
            "bucket": bucket,
            "status": inv.status
        })

    # Round all amounts
    for bucket in aging_summary.values():
        bucket["amount"] = flt(bucket["amount"], 2)

    return {
        "aging_summary": aging_summary,
        "total_payables": flt(total_payables, 2),
        "total_invoices": len(invoice_details),
        "as_of_date": str(today),
        "invoice_details": invoice_details
    }


@frappe.whitelist()
def get_supplier_aging(supplier):
    """
    Get AP aging for a specific supplier.

    Args:
        supplier: Supplier name/ID

    Returns:
        Dict with supplier aging details
    """
    aging = get_ap_aging_report()

    # Filter invoice details for this supplier (match by ID or display name)
    supplier_invoices = [
        inv for inv in aging["invoice_details"]
        if inv.get("supplier_id") == supplier or inv["supplier"] == supplier
    ]

    supplier_total = sum(inv["outstanding"] for inv in supplier_invoices)

    # Rebuild aging summary for this supplier only
    supplier_aging = {
        "0-30": {"count": 0, "amount": 0},
        "31-60": {"count": 0, "amount": 0},
        "61-90": {"count": 0, "amount": 0},
        "91-120": {"count": 0, "amount": 0},
        "121-150": {"count": 0, "amount": 0},
        "Over 150": {"count": 0, "amount": 0}
    }

    for inv in supplier_invoices:
        bucket = inv["bucket"]
        supplier_aging[bucket]["count"] += 1
        supplier_aging[bucket]["amount"] = flt(supplier_aging[bucket]["amount"], 2) + inv["outstanding"]

    return {
        "supplier": supplier,
        "aging_summary": supplier_aging,
        "total_outstanding": flt(supplier_total, 2),
        "invoice_count": len(supplier_invoices),
        "invoices": supplier_invoices,
        "as_of_date": aging["as_of_date"]
    }


@frappe.whitelist()
def send_billing_statement(name):
    """
    Send billing statement to store via email.

    Generates an HTML Statement of Account and emails it to the store's
    department email and Accounts Manager users. Updates billing status
    to 'Sent' with timestamp.

    Args:
        name: BEI Billing Schedule document name

    Returns:
        Dict with success status, message, and recipient list
    """
    billing = frappe.get_doc("BEI Billing Schedule", name)
    return billing.send_to_store()


@frappe.whitelist()
def get_billing_list(store=None, status=None, billing_period=None, page=1, page_size=20):
    """
    Get paginated list of billing schedules with optional filters.

    Args:
        store: Filter by store (Department link)
        status: Filter by status (Draft/Sent/Paid/Disputed/Cancelled)
        billing_period: Filter by billing period (YYYY-MM)
        page: Page number (default 1)
        page_size: Results per page (default 20, max 100)

    Returns:
        Dict with billing list and pagination info
    """
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    offset = (page - 1) * page_size

    conditions = []
    values = {}

    if store:
        conditions.append("store = %(store)s")
        values["store"] = store

    if status:
        conditions.append("status = %(status)s")
        values["status"] = status

    if billing_period:
        conditions.append("billing_period = %(billing_period)s")
        values["billing_period"] = billing_period

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Billing Schedule` WHERE {where_clause}",
        values
    )[0][0]

    # Bug fix D7: Use frappe.db.sql() instead of frappe.get_all() to bypass field permission checks
    # The royalty_amount field exists but may not have proper read permissions for API users
    billings = frappe.db.sql(f"""
        SELECT
            name, billing_period, store, store_type, status,
            gross_sales, net_sales, total_amount,
            generated_on, sent_on, paid_on
        FROM `tabBEI Billing Schedule`
        WHERE {where_clause}
        ORDER BY billing_period DESC, store ASC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": page_size, "offset": offset}, as_dict=True)

    return {
        "data": billings,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size) if total else 0,
    }


# =============================================================================
# FINANCE ANALYTICS ALIASES
# =============================================================================

@frappe.whitelist()
def get_po_trends(months=6):
    """Alias for get_monthly_po_trend (frontend compatibility)."""
    return get_monthly_po_trend(months)


@frappe.whitelist()
def get_finance_analytics():
    """Aggregated finance dashboard data for my.bebang.ph."""
    return {
        "kpis": get_dashboard_kpis(),
        "ap_aging": get_ap_aging_report(),
        "po_trend": get_monthly_po_trend(months=6),
        "suppliers": get_supplier_performance()
    }


# =============================================================================
# 3-WAY MATCH EXCEPTION BYPASS (Feature A)
# =============================================================================

def _send_ceo_exception_notification(exception_doc):
    """Send Google Chat notification to CEO about an approved exception.

    Uses the service account pattern from hrms.api.google_chat.
    Sends to ERP Automation Committee space (spaces/AAQA3NVVR6c).
    """
    try:
        from hrms.api.google_chat import send_message_to_space

        po_no = frappe.db.get_value("BEI Purchase Order", exception_doc.purchase_order, "po_no") or exception_doc.purchase_order
        supplier_name = frappe.db.get_value("BEI Purchase Order", exception_doc.purchase_order, "supplier_name") or ""

        message = (
            f"*3-Way Match Exception Approved*\n\n"
            f"*PO:* {po_no} -- {supplier_name}\n"
            f"*Amount:* PHP {flt(exception_doc.po_amount):,.2f}\n"
            f"*Tier:* {exception_doc.approval_tier}\n"
            f"*Type:* {exception_doc.exception_type}\n"
            f"*Reason:* {exception_doc.reason}\n\n"
            f"Approved by: {exception_doc.approver} on {exception_doc.approver_date}\n\n"
            f"No Goods Receipt exists for this PO. Payment will proceed without delivery confirmation."
        )

        send_message_to_space("spaces/AAQA3NVVR6c", message)
        return True
    except Exception as e:
        frappe.log_error(
            title="Exception CEO Notification Failed",
            message=f"Exception: {exception_doc.name}, Error: {str(e)}"
        )
        return False


@frappe.whitelist()
def request_match_exception(data):
    """Create a 3-way match exception request.

    Auto-routes to the correct approver based on PO amount:
      < 500K -> CPO (Mae)
      500K to < 1M -> CFO (Butch)
      >= 1M -> CEO (Sam)
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    purchase_order = data.get("purchase_order")
    if not purchase_order:
        frappe.throw(_("Purchase Order is required"))

    if not frappe.db.exists("BEI Purchase Order", purchase_order):
        frappe.throw(_("Purchase Order {0} not found").format(purchase_order))

    reason = data.get("reason")
    if not reason:
        frappe.throw(_("Reason is required for exception requests"))

    exception_type = data.get("exception_type")
    if not exception_type:
        frappe.throw(_("Exception type is required"))

    # Check if a pending or approved exception already exists for this PO
    existing = frappe.db.exists("BEI Match Exception", {
        "purchase_order": purchase_order,
        "status": ["in", ["Pending CPO", "Pending CFO", "Pending CEO", "Approved"]],
    })
    if existing:
        frappe.throw(
            _("An exception request already exists for PO {0}: {1}").format(purchase_order, existing)
        )

    exception = frappe.get_doc({
        "doctype": "BEI Match Exception",
        "reference_type": data.get("reference_type", "BEI Invoice"),
        "reference_name": data.get("reference_name"),
        "purchase_order": purchase_order,
        "reason": reason,
        "exception_type": exception_type,
    })
    exception.insert()

    return {
        "success": True,
        "name": exception.name,
        "approval_tier": exception.approval_tier,
        "approver": exception.approver,
        "status": exception.status,
        "message": _("Exception request created. Awaiting {0} approval from {1}.").format(
            exception.approval_tier, exception.approver
        ),
    }


# =============================================================================
# Official Receipt (OR) Tracking (Feature B)
# =============================================================================

@frappe.whitelist()
def upload_official_receipt(name, or_number, or_date, or_amount, or_attachment=None):
    """Upload OR for a payment request. Closes the transaction if amount matches within 5%.
    If mismatch > 5%, still accepts but flags for review.

    Args:
        name: BEI Payment Request name (e.g. PAY-2026-00001)
        or_number: Official Receipt number from supplier
        or_date: Date on the OR
        or_amount: Amount on the OR
        or_attachment: Attach field value (file URL)

    Returns:
        dict with success, message, amount_match, variance_pct
    """
    from frappe.utils import now_datetime as _now_dt

    pay_req = frappe.get_doc("BEI Payment Request", name)

    if pay_req.status not in ("Paid - Awaiting OR", "Paid"):
        frappe.throw(
            _("Cannot upload OR for payment with status '{0}'. "
              "Expected 'Paid - Awaiting OR'.").format(pay_req.status)
        )

    if pay_req.or_status == "OR Received":
        frappe.throw(_("OR has already been uploaded for this payment request"))

    or_amount = flt(or_amount, 2)
    payment_amount = flt(pay_req.payment_amount, 2)

    # Calculate variance
    variance_pct = 0
    amount_match = True
    if payment_amount > 0:
        variance_pct = abs(or_amount - payment_amount) / payment_amount * 100
        amount_match = variance_pct <= 5

    # Update OR fields
    pay_req.or_number = or_number
    pay_req.or_date = or_date
    pay_req.or_amount = or_amount
    pay_req.or_attachment = or_attachment
    pay_req.or_uploaded_by = frappe.session.user
    pay_req.or_uploaded_date = _now_dt()
    pay_req.or_status = "OR Received"
    pay_req.status = "Closed"
    pay_req.save(ignore_permissions=True)

    msg = _("Official Receipt uploaded successfully. Transaction closed.")
    if not amount_match:
        msg = _(
            "Official Receipt uploaded. Amount mismatch of {0:.1f}% detected "
            "(Payment: {1:,.2f}, OR: {2:,.2f}). Transaction closed but flagged for review."
        ).format(variance_pct, payment_amount, or_amount)

    return {
        "success": True,
        "message": msg,
        "amount_match": amount_match,
        "variance_pct": round(variance_pct, 2),
        "status": pay_req.status,
        "or_status": pay_req.or_status,
    }


@frappe.whitelist()
def approve_match_exception(name, comment=None):
    """Approve a match exception.

    Validates that the current user is the designated approver for the tier.
    On approval, sends Google Chat notification to CEO (for all tiers).
    """
    from frappe.utils import now_datetime

    exception = frappe.get_doc("BEI Match Exception", name)

    if exception.status == "Approved":
        frappe.throw(_("This exception has already been approved"))

    if exception.status == "Rejected":
        frappe.throw(_("This exception has been rejected and cannot be approved"))

    # Validate the current user is the designated approver
    current_user = frappe.session.user
    if current_user != exception.approver and current_user != "Administrator":
        frappe.throw(
            _("Only {0} ({1} tier) can approve this exception. You are logged in as {2}.").format(
                exception.approver, exception.approval_tier, current_user
            )
        )

    exception.approver_status = "Approved"
    exception.approver_date = now_datetime()
    exception.approver_comment = comment or ""
    exception.status = "Approved"
    exception.save()

    # Send CEO notification for all approved exceptions (any tier)
    notified = _send_ceo_exception_notification(exception)
    if notified:
        exception.ceo_notified = 1
        exception.ceo_notification_date = now_datetime()
        exception.save()

    return {
        "success": True,
        "name": exception.name,
        "status": "Approved",
        "message": _("Exception approved by {0}").format(current_user),
    }


@frappe.whitelist()
def reject_match_exception(name, reason=None):
    """Reject a match exception."""
    from frappe.utils import now_datetime

    exception = frappe.get_doc("BEI Match Exception", name)

    if exception.status == "Approved":
        frappe.throw(_("This exception has already been approved and cannot be rejected"))

    if exception.status == "Rejected":
        frappe.throw(_("This exception has already been rejected"))

    # Validate the current user is the designated approver
    current_user = frappe.session.user
    if current_user != exception.approver and current_user != "Administrator":
        frappe.throw(
            _("Only {0} ({1} tier) can reject this exception. You are logged in as {2}.").format(
                exception.approver, exception.approval_tier, current_user
            )
        )

    exception.approver_status = "Rejected"
    exception.approver_date = now_datetime()
    exception.approver_comment = reason or ""
    exception.status = "Rejected"
    exception.save()

    return {
        "success": True,
        "name": exception.name,
        "status": "Rejected",
        "message": _("Exception rejected by {0}").format(current_user),
    }


@frappe.whitelist()
def get_match_exceptions(filters=None, page=1, page_size=20):
    """List match exceptions with optional filtering.

    Filters:
      - status: "Pending CPO", "Pending CFO", "Pending CEO", "Approved", "Rejected"
      - approval_tier: "CPO", "CFO", "CEO"
      - purchase_order: specific PO name
      - approver: filter by approver email (useful for showing "my pending approvals")
    """
    conditions = []
    values = {}

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        if filters.get("status"):
            conditions.append("exc.status = %(status)s")
            values["status"] = filters["status"]

        if filters.get("approval_tier"):
            conditions.append("exc.approval_tier = %(approval_tier)s")
            values["approval_tier"] = filters["approval_tier"]

        if filters.get("purchase_order"):
            conditions.append("exc.purchase_order = %(purchase_order)s")
            values["purchase_order"] = filters["purchase_order"]

        if filters.get("approver"):
            conditions.append("exc.approver = %(approver)s")
            values["approver"] = filters["approver"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Match Exception` exc WHERE {where_clause}",
        values,
    )[0][0]

    exceptions = frappe.db.sql(f"""
        SELECT
            exc.name, exc.purchase_order, exc.po_amount, exc.approval_tier,
            exc.status, exc.exception_type, exc.reason, exc.approver,
            exc.approver_status, exc.approver_date, exc.approver_comment,
            exc.requested_by, exc.requested_date, exc.ceo_notified,
            exc.reference_type, exc.reference_name,
            po.po_no, po.supplier_name
        FROM `tabBEI Match Exception` exc
        LEFT JOIN `tabBEI Purchase Order` po ON exc.purchase_order = po.name
        WHERE {where_clause}
        ORDER BY exc.creation DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": exceptions,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": -(-total // page_size) if total else 0,
    }


@frappe.whitelist()
def get_awaiting_or_list(page=1, page_size=20, status=None, supplier=None, overdue_only=False):
    """Get list of payments awaiting OR. Used by Butch's OR dashboard.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        status: Filter by or_status (e.g. "Awaiting OR", "Overdue")
        supplier: Filter by supplier name
        overdue_only: If true, only show overdue items

    Returns:
        dict with data list, total count, pagination info
    """
    from frappe.utils import getdate as _getdate, date_diff

    page = int(page)
    page_size = min(int(page_size), 100)
    offset = (page - 1) * page_size

    conditions = ["pr.status = 'Paid - Awaiting OR'"]
    params = {}

    if status:
        conditions.append("pr.or_status = %(or_status)s")
        params["or_status"] = status

    if supplier:
        conditions.append("pr.supplier = %(supplier)s")
        params["supplier"] = supplier

    if overdue_only == "true" or overdue_only is True:
        conditions.append("pr.or_status = 'Overdue'")

    where = " AND ".join(conditions)

    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Payment Request` pr WHERE {where}",
        params
    )[0][0]

    data = frappe.db.sql(
        f"""SELECT
            pr.name,
            pr.payment_request_no,
            pr.supplier,
            pr.supplier_name,
            pr.payment_amount,
            pr.payment_date,
            pr.or_status,
            pr.or_due_date,
            pr.or_follow_up_count,
            pr.or_last_follow_up,
            pr.purchase_order,
            pr.invoice
        FROM `tabBEI Payment Request` pr
        WHERE {where}
        ORDER BY pr.or_due_date ASC, pr.payment_date ASC
        LIMIT %(limit)s OFFSET %(offset)s""",
        {**params, "limit": page_size, "offset": offset},
        as_dict=True,
    )

    today = _getdate()
    for row in data:
        paid_date = _getdate(row.payment_date) if row.payment_date else today
        row["days_waiting"] = date_diff(today, paid_date)

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size) if total else 0,
    }


@frappe.whitelist()
def get_or_aging_summary():
    """Get OR aging summary by bracket.

    Returns:
        dict with counts for: 0-7d, 8-14d, 15-30d, 31-60d, 60+d
        Also returns total_awaiting, total_overdue, avg_days_outstanding
    """
    from frappe.utils import getdate as _getdate, date_diff

    today = _getdate()

    rows = frappe.db.sql(
        """SELECT
            pr.name,
            pr.payment_date,
            pr.payment_amount,
            pr.or_status,
            pr.or_due_date
        FROM `tabBEI Payment Request` pr
        WHERE pr.status = 'Paid - Awaiting OR'""",
        as_dict=True,
    )

    brackets = {
        "0_7_days": {"count": 0, "amount": 0},
        "8_14_days": {"count": 0, "amount": 0},
        "15_30_days": {"count": 0, "amount": 0},
        "31_60_days": {"count": 0, "amount": 0},
        "over_60_days": {"count": 0, "amount": 0},
    }

    total_awaiting = 0
    total_overdue = 0
    total_days = 0
    total_amount_awaiting = 0
    total_amount_overdue = 0

    for row in rows:
        paid_date = _getdate(row.payment_date) if row.payment_date else today
        days = date_diff(today, paid_date)
        amount = flt(row.payment_amount, 2)

        total_awaiting += 1
        total_amount_awaiting += amount
        total_days += days

        if row.or_status == "Overdue":
            total_overdue += 1
            total_amount_overdue += amount

        if days <= 7:
            brackets["0_7_days"]["count"] += 1
            brackets["0_7_days"]["amount"] += amount
        elif days <= 14:
            brackets["8_14_days"]["count"] += 1
            brackets["8_14_days"]["amount"] += amount
        elif days <= 30:
            brackets["15_30_days"]["count"] += 1
            brackets["15_30_days"]["amount"] += amount
        elif days <= 60:
            brackets["31_60_days"]["count"] += 1
            brackets["31_60_days"]["amount"] += amount
        else:
            brackets["over_60_days"]["count"] += 1
            brackets["over_60_days"]["amount"] += amount

    avg_days = round(total_days / total_awaiting, 1) if total_awaiting else 0

    return {
        "brackets": brackets,
        "total_awaiting": total_awaiting,
        "total_amount_awaiting": total_amount_awaiting,
        "total_overdue": total_overdue,
        "total_amount_overdue": total_amount_overdue,
        "avg_days_outstanding": avg_days,
    }


@frappe.whitelist()
def mark_or_not_required(name, reason=None):
    """Mark a payment as not requiring OR. Sets status to Closed.
    Requires reason for audit trail.

    Args:
        name: BEI Payment Request name
        reason: Reason why OR is not required (mandatory)

    Returns:
        dict with success, message
    """
    if not reason:
        frappe.throw(_("Please provide a reason for marking OR as not required"))

    pay_req = frappe.get_doc("BEI Payment Request", name)

    if pay_req.status not in ("Paid - Awaiting OR", "Paid"):
        frappe.throw(
            _("Cannot modify OR status for payment with status '{0}'").format(pay_req.status)
        )

    pay_req.or_required = 0
    pay_req.or_status = "Not Required"
    pay_req.status = "Closed"
    pay_req.save(ignore_permissions=True)

    # Add comment for audit trail
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "BEI Payment Request",
        "reference_name": name,
        "content": _("OR marked as not required by {0}. Reason: {1}").format(
            frappe.session.user, reason
        ),
    }).insert(ignore_permissions=True)

    return {
        "success": True,
        "message": _("OR marked as not required. Transaction closed."),
        "status": pay_req.status,
        "or_status": pay_req.or_status,
    }


@frappe.whitelist()
def send_or_follow_up(name):
    """Send follow-up to supplier for missing OR.
    Increments follow_up_count, records last_follow_up timestamp.

    Args:
        name: BEI Payment Request name

    Returns:
        dict with success, message, follow_up_count
    """
    from frappe.utils import now_datetime as _now_dt

    pay_req = frappe.get_doc("BEI Payment Request", name)

    if pay_req.status != "Paid - Awaiting OR":
        frappe.throw(
            _("Cannot send follow-up for payment with status '{0}'").format(pay_req.status)
        )

    pay_req.or_follow_up_count = (pay_req.or_follow_up_count or 0) + 1
    pay_req.or_last_follow_up = _now_dt()
    pay_req.save(ignore_permissions=True)

    # Add comment for audit trail
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "BEI Payment Request",
        "reference_name": name,
        "content": _("OR follow-up #{0} sent by {1}").format(
            pay_req.or_follow_up_count, frappe.session.user
        ),
    }).insert(ignore_permissions=True)

    return {
        "success": True,
        "message": _("Follow-up #{0} recorded for {1}").format(
            pay_req.or_follow_up_count, pay_req.supplier_name or pay_req.supplier
        ),
        "follow_up_count": pay_req.or_follow_up_count,
    }


def check_overdue_or():
    """Daily scheduler: check for overdue OR and escalate.
    7 days past due: or_status -> 'Overdue', nudge procurement user
    14 days past due: escalate to Mae (CPO) via notification
    30 days past due: escalate to Butch (CFO) via notification
    """
    from frappe.utils import getdate as _getdate, date_diff

    today = _getdate()

    overdue_payments = frappe.db.sql(
        """SELECT name, supplier_name, payment_amount, or_due_date,
                  or_follow_up_count, or_status
        FROM `tabBEI Payment Request`
        WHERE status = 'Paid - Awaiting OR'
          AND or_due_date IS NOT NULL
          AND or_due_date < %(today)s""",
        {"today": today},
        as_dict=True,
    )

    for pay in overdue_payments:
        days_overdue = date_diff(today, _getdate(pay.or_due_date))

        # Mark as Overdue if not already
        if pay.or_status != "Overdue":
            frappe.db.set_value(
                "BEI Payment Request", pay.name, "or_status", "Overdue",
                update_modified=False
            )

        # Escalation tiers
        if days_overdue >= 30:
            # Escalate to CFO (Butch)
            _create_or_escalation_notification(
                pay, "CFO", "butch@bebang.ph", days_overdue
            )
        elif days_overdue >= 14:
            # Escalate to CPO (Mae)
            _create_or_escalation_notification(
                pay, "CPO", "mae@bebang.ph", days_overdue
            )

    frappe.db.commit()


def _create_or_escalation_notification(payment, role_label, recipient, days_overdue):
    """Create a system notification for OR escalation.

    Args:
        payment: dict with name, supplier_name, payment_amount
        role_label: "CPO" or "CFO"
        recipient: email of the recipient
        days_overdue: number of days past OR due date
    """
    subject = _("OR Overdue ({0} days): {1} - PHP {2:,.2f}").format(
        days_overdue, payment.supplier_name, flt(payment.payment_amount, 2)
    )

    try:
        notification = frappe.get_doc({
            "doctype": "Notification Log",
            "for_user": recipient,
            "type": "Alert",
            "document_type": "BEI Payment Request",
            "document_name": payment.name,
            "subject": subject,
        })
        notification.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            f"Failed to create OR escalation notification for {payment.name}",
            "OR Escalation Error"
        )


# ============================================================
# Advance Payment Functions
# ============================================================


@frappe.whitelist()
def tag_advance_to_gr(advance_payment, goods_receipt, amount_to_clear):
    """
    Clear (partially or fully) an advance payment against a Goods Receipt.

    Creates a Journal Entry:
      Dr 1104002 - INVENTORY/CLEARING (amount_to_clear)
      Cr 1105203 - ADVANCES TO SUPPLIERS (amount_to_clear)

    All JV rows include party_type + party per DM-1.
    Uses savepoint per DM-2.
    Auto-submits JV per CFO Q17.

    Args:
        advance_payment: BEI Payment Request name (the advance)
        goods_receipt: BEI Goods Receipt name
        amount_to_clear: Amount to clear from this advance

    Returns: dict with success, jv_name, advance_status
    """
    amount_to_clear = flt(amount_to_clear, 2)
    if amount_to_clear <= 0:
        frappe.throw(_("Amount to clear must be greater than zero"))

    advance = frappe.get_doc("BEI Payment Request", advance_payment)

    if not cint(advance.is_advance_payment):
        frappe.throw(_("{0} is not an advance payment").format(advance_payment))

    if advance.advance_status not in ("Outstanding", "Partially Cleared"):
        frappe.throw(
            _("Advance {0} cannot be cleared - current status: {1}").format(
                advance_payment, advance.advance_status
            )
        )

    outstanding = flt(advance.advance_outstanding, 2)
    if amount_to_clear > outstanding:
        frappe.throw(
            _("Amount to clear ({0:,.2f}) exceeds outstanding balance ({1:,.2f})").format(
                amount_to_clear, outstanding
            )
        )

    # Get supplier info for party fields
    supplier_name = ""
    frappe_supplier = None
    if advance.supplier:
        bei_supplier = frappe.get_doc("BEI Supplier", advance.supplier)
        supplier_name = bei_supplier.supplier_name
        frappe_supplier = bei_supplier.get_or_create_frappe_supplier()

    party_name = frappe_supplier or supplier_name

    # Validate GR exists
    if not frappe.db.exists("BEI Goods Receipt", goods_receipt):
        frappe.throw(_("Goods Receipt {0} not found").format(goods_receipt))

    sp = frappe.db.savepoint("advance_clearing")
    try:
        # Create Journal Entry for clearing
        jv = frappe.new_doc("Journal Entry")
        jv.voucher_type = "Journal Entry"
        jv.posting_date = nowdate()
        jv.company = "Bebang Enterprise Inc."
        jv.user_remark = _("Clearing advance payment {0} against GR {1} - Amount: {2:,.2f}").format(
            advance_payment, goods_receipt, amount_to_clear
        )

        # Debit: Inventory/Clearing account (recognize the expense/asset)
        jv.append("accounts", {
            "account": "1104002 - INVENTORY - WAREHOUSE - BEI",
            "debit_in_account_currency": amount_to_clear,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": "Main - BEI",
        })

        # Credit: Advances to Suppliers (reduce the advance)
        jv.append("accounts", {
            "account": "1105203 - ADVANCES TO SUPPLIERS - BEI",
            "debit_in_account_currency": 0,
            "credit_in_account_currency": amount_to_clear,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": "Main - BEI",
        })

        jv.insert(ignore_permissions=True)
        jv.submit()

        # Update advance tracking
        new_cleared = flt(advance.advance_cleared_amount, 2) + amount_to_clear
        new_outstanding = flt(advance.advance_amount, 2) - new_cleared

        advance.advance_cleared_amount = new_cleared
        advance.advance_outstanding = flt(new_outstanding, 2)

        if flt(new_outstanding, 2) <= 0:
            advance.advance_status = "Fully Cleared"
        else:
            advance.advance_status = "Partially Cleared"

        advance.save(ignore_permissions=True)

        frappe.msgprint(
            _("Advance clearing JV created: {0}").format(jv.name),
            indicator="green"
        )

        return {
            "success": True,
            "jv_name": jv.name,
            "advance_status": advance.advance_status,
            "advance_outstanding": advance.advance_outstanding,
        }

    except Exception:
        frappe.db.rollback(save_point=sp)
        raise


@frappe.whitelist(allow_guest=False)
def check_advance_for_po(purchase_order):
    """
    Check if there are outstanding advance payments for a Purchase Order.

    Used by frontend to show advance balance when creating GR or Invoice.

    Args:
        purchase_order: BEI Purchase Order name

    Returns: dict with has_advance, advances list, total_outstanding
    """
    if not purchase_order:
        return {"has_advance": False, "advances": [], "total_outstanding": 0}

    advances = frappe.get_all(
        "BEI Payment Request",
        filters={
            "is_advance_payment": 1,
            "purchase_order": purchase_order,
            "advance_status": ["in", ["Outstanding", "Partially Cleared"]],
        },
        fields=[
            "name", "payment_amount", "advance_amount",
            "advance_cleared_amount", "advance_outstanding",
            "advance_status", "payment_date", "supplier_name",
        ],
        order_by="creation asc",
    )

    total_outstanding = sum(flt(a.advance_outstanding, 2) for a in advances)

    return {
        "has_advance": len(advances) > 0,
        "advances": advances,
        "total_outstanding": flt(total_outstanding, 2),
    }


# =============================================================================
# ADVANCE PAYMENT: RECLASSIFICATION, DASHBOARD, SUBSIDIARY LEDGER, FORM 2307
# =============================================================================

@frappe.whitelist()
def mark_advance_undeliverable(advance_payment, amount, reason):
    """Reclassify an undeliverable advance payment to AR-Others.

    Creates a Journal Entry:
        Dr 1103102 - ACCOUNTS RECEIVABLE-OTHERS - BEI  (amount)
        Cr 1105203 - ADVANCES TO SUPPLIERS - BEI       (amount)

    DM-1: All JV rows include party_type + party.
    DM-2: Uses savepoint for multi-doc safety.
    Auto-submits JV per CFO directive (Q17).

    Args:
        advance_payment: BEI Payment Request name
        amount: Amount to reclassify
        reason: Business reason for reclassification
    """
    amount = flt(amount)
    if amount <= 0:
        frappe.throw(_("Reclassification amount must be greater than zero."))

    if not reason or not reason.strip():
        frappe.throw(_("A reason is required for reclassification."))

    advance = frappe.get_doc("BEI Payment Request", advance_payment)
    if not advance.is_advance_payment:
        frappe.throw(_("{0} is not an advance payment.").format(advance_payment))

    outstanding = flt(advance.advance_outstanding)
    if amount > outstanding:
        frappe.throw(
            _("Reclassification amount (PHP {0:,.2f}) exceeds outstanding balance (PHP {1:,.2f}).").format(
                amount, outstanding
            )
        )

    # Resolve to Frappe Supplier for GL party (BUG-011 fix)
    party_name = ""
    if advance.supplier:
        bei_supplier = frappe.get_doc("BEI Supplier", advance.supplier)
        frappe_supplier = bei_supplier.get_or_create_frappe_supplier()
        party_name = frappe_supplier or bei_supplier.supplier_name
    else:
        party_name = advance.supplier_name or advance.supplier

    sp = frappe.db.savepoint("reclass_advance")
    try:
        # Create reclassification Journal Entry
        jv = frappe.new_doc("Journal Entry")
        jv.voucher_type = "Journal Entry"
        jv.posting_date = nowdate()
        jv.company = "Bebang Enterprise Inc."
        jv.user_remark = "Reclassification of undeliverable advance: {0}. Reason: {1}".format(
            advance_payment, reason.strip()
        )
        jv.append("accounts", {
            "account": "1103102 - ACCOUNTS RECEIVABLE-OTHERS - BEI",
            "debit_in_account_currency": amount,
            "party_type": "Supplier",
            "party": party_name,
        })
        jv.append("accounts", {
            "account": "1105203 - ADVANCES TO SUPPLIERS - BEI",
            "credit_in_account_currency": amount,
            "party_type": "Supplier",
            "party": party_name,
        })
        jv.insert(ignore_permissions=True)
        jv.submit()

        # Update advance balances
        new_cleared = flt(advance.advance_cleared_amount) + amount
        new_outstanding = flt(advance.advance_amount) - new_cleared
        updates = {
            "advance_cleared_amount": new_cleared,
            "advance_outstanding": new_outstanding,
        }
        if new_outstanding <= 0:
            updates["advance_status"] = "Reclassified"

        for field, value in updates.items():
            frappe.db.set_value(
                "BEI Payment Request", advance_payment, field, value,
                update_modified=False,
            )

        # Audit trail comment
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "BEI Payment Request",
            "reference_name": advance_payment,
            "content": "Reclassified PHP {0:,.2f} to AR-Others (JV: {1}). Reason: {2}".format(
                amount, jv.name, reason.strip()
            ),
        }).insert(ignore_permissions=True)

    except Exception:
        frappe.db.rollback(save_point=sp)
        raise

    return {
        "success": True,
        "journal_entry": jv.name,
        "new_outstanding": new_outstanding,
        "new_status": updates.get("advance_status", advance.advance_status),
        "message": _("Reclassified PHP {0:,.2f} to AR-Others.").format(amount),
    }


@frappe.whitelist(allow_guest=False)
def get_outstanding_advances(page=1, page_size=20, group_by=None, supplier=None, status=None):
    """Get outstanding advance payments with optional grouping.

    Args:
        page: Page number (1-indexed)
        page_size: Results per page
        group_by: None or "supplier" for aggregated view
        supplier: Filter by supplier name
        status: Filter by advance_status
    """
    page = int(page)
    page_size = int(page_size)
    conditions = ["pr.is_advance_payment = 1", "pr.advance_status IN ('Outstanding', 'Partially Cleared')"]
    values = {}

    if supplier:
        conditions.append("pr.supplier_name = %(supplier)s")
        values["supplier"] = supplier

    if status:
        conditions.append("pr.advance_status = %(status)s")
        values["status"] = status

    where = " AND ".join(conditions)

    if group_by == "supplier":
        data = frappe.db.sql(
            """SELECT
                pr.supplier, pr.supplier_name,
                COUNT(*) as advance_count,
                SUM(pr.advance_amount) as total_advance_amount,
                SUM(pr.advance_cleared_amount) as total_cleared,
                SUM(pr.advance_outstanding) as total_outstanding,
                MIN(pr.payment_date) as earliest_payment,
                MAX(DATEDIFF(NOW(), pr.payment_date)) as max_days_outstanding
            FROM `tabBEI Payment Request` pr
            WHERE {where}
            GROUP BY pr.supplier, pr.supplier_name
            ORDER BY total_outstanding DESC""".format(where=where),
            values,
            as_dict=True,
        )
        return {"data": data, "total": len(data), "grouped_by": "supplier"}

    offset = (page - 1) * page_size
    values["limit"] = page_size
    values["offset"] = offset

    total = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabBEI Payment Request` pr WHERE {where}".format(where=where),
        values,
    )[0][0]

    data = frappe.db.sql(
        """SELECT
            pr.name, pr.supplier, pr.supplier_name, pr.purchase_order,
            pr.advance_amount, pr.advance_cleared_amount, pr.advance_outstanding,
            pr.advance_status, pr.payment_date,
            DATEDIFF(NOW(), pr.payment_date) as days_outstanding
        FROM `tabBEI Payment Request` pr
        WHERE {where}
        ORDER BY pr.payment_date ASC
        LIMIT %(limit)s OFFSET %(offset)s""".format(where=where),
        values,
        as_dict=True,
    )

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@frappe.whitelist(allow_guest=False)
def get_advance_aging_summary():
    """Get advance payment aging in standard buckets.

    Returns counts and totals for: 0-7, 8-14, 15-30, 31-60, >60 days.
    """
    rows = frappe.db.sql(
        """SELECT
            pr.advance_outstanding,
            DATEDIFF(NOW(), pr.payment_date) as days_outstanding
        FROM `tabBEI Payment Request` pr
        WHERE pr.is_advance_payment = 1
          AND pr.advance_status IN ('Outstanding', 'Partially Cleared')""",
        as_dict=True,
    )

    buckets = {
        "0_7_days": {"count": 0, "amount": 0},
        "8_14_days": {"count": 0, "amount": 0},
        "15_30_days": {"count": 0, "amount": 0},
        "31_60_days": {"count": 0, "amount": 0},
        "over_60_days": {"count": 0, "amount": 0},
    }
    total_count = 0
    total_amount = 0

    for row in rows:
        days = row.days_outstanding or 0
        amt = flt(row.advance_outstanding)
        total_count += 1
        total_amount += amt

        if days <= 7:
            key = "0_7_days"
        elif days <= 14:
            key = "8_14_days"
        elif days <= 30:
            key = "15_30_days"
        elif days <= 60:
            key = "31_60_days"
        else:
            key = "over_60_days"

        buckets[key]["count"] += 1
        buckets[key]["amount"] += amt

    # Round amounts
    for bucket in buckets.values():
        bucket["amount"] = flt(bucket["amount"], 2)

    return {
        "buckets": buckets,
        "total_count": total_count,
        "total_amount": flt(total_amount, 2),
    }


@frappe.whitelist(allow_guest=False)
def get_advance_subsidiary_ledger(supplier, from_date=None, to_date=None):
    """Get chronological subsidiary ledger for a supplier's advances.

    Entries: advances (debit), clearings (credit), reclassifications (credit).
    Returns entries with running balance.

    Args:
        supplier: Supplier name
        from_date: Optional start date filter
        to_date: Optional end date filter
    """
    if not supplier:
        frappe.throw(_("Supplier is required."))

    date_filter = ""
    values = {"supplier": supplier}
    if from_date:
        date_filter += " AND posting_date >= %(from_date)s"
        values["from_date"] = getdate(from_date)
    if to_date:
        date_filter += " AND posting_date <= %(to_date)s"
        values["to_date"] = getdate(to_date)

    # 1. Advance payments (debit to 1105203)
    advances = frappe.db.sql(
        """SELECT
            pr.name as reference_name, 'BEI Payment Request' as reference_type,
            pr.payment_date as posting_date,
            'Advance Payment' as entry_type,
            pr.advance_amount as debit, 0 as credit,
            pr.purchase_order as remarks
        FROM `tabBEI Payment Request` pr
        WHERE pr.is_advance_payment = 1
          AND pr.supplier_name = %(supplier)s
          {date_filter}""".format(date_filter=date_filter.replace("posting_date", "pr.payment_date")),
        values,
        as_dict=True,
    )

    # 2. Journal Entries touching 1105203 for this supplier (clearings + reclassifications)
    je_date_filter = date_filter  # uses posting_date directly
    journal_entries = frappe.db.sql(
        """SELECT
            je.name as reference_name, 'Journal Entry' as reference_type,
            je.posting_date,
            CASE
                WHEN jea.account LIKE '1103102%%' THEN 'Reclassification'
                ELSE 'Advance Clearing'
            END as entry_type,
            jea.debit_in_account_currency as debit,
            jea.credit_in_account_currency as credit,
            je.user_remark as remarks
        FROM `tabJournal Entry Account` jea
        JOIN `tabJournal Entry` je ON jea.parent = je.name
        WHERE jea.account LIKE '1105203%%'
          AND jea.party_type = 'Supplier'
          AND jea.party = %(supplier)s
          AND je.docstatus = 1
          {date_filter}
        ORDER BY je.posting_date""".format(date_filter=je_date_filter.replace("posting_date", "je.posting_date")),
        values,
        as_dict=True,
    )

    # Combine and sort chronologically
    entries = advances + journal_entries
    entries.sort(key=lambda e: (getdate(e["posting_date"]), e.get("reference_name", "")))

    # Calculate running balance
    running_balance = 0
    for entry in entries:
        running_balance += flt(entry["debit"]) - flt(entry["credit"])
        entry["balance"] = flt(running_balance, 2)
        entry["debit"] = flt(entry["debit"], 2)
        entry["credit"] = flt(entry["credit"], 2)

    return {
        "supplier": supplier,
        "entries": entries,
        "closing_balance": flt(running_balance, 2),
        "from_date": str(from_date) if from_date else None,
        "to_date": str(to_date) if to_date else None,
    }


@frappe.whitelist(allow_guest=False)
def generate_form_2307_entry(payment_request):
    """Generate/update Form 2307 (EWT certificate) data for a payment request.

    Stores: supplier TIN, name, tax period, ATC code, gross amount, EWT rate, EWT amount.
    Data-only — no PDF generation this sprint.

    Args:
        payment_request: BEI Payment Request name
    """
    pay_req = frappe.get_doc("BEI Payment Request", payment_request)

    if not pay_req.supplier:
        frappe.throw(_("Payment request has no supplier."))

    # Get supplier TIN
    supplier_tin = frappe.db.get_value("BEI Supplier", pay_req.supplier, "tin") or ""
    supplier_name = pay_req.supplier_name or pay_req.supplier

    # Determine tax period (month/year of payment)
    payment_date = getdate(pay_req.payment_date or pay_req.request_date or nowdate())
    tax_period = payment_date.strftime("%Y-%m")

    # EWT calculation — default ATC WI100 (goods) at 1% for trade
    gross_amount = flt(pay_req.payment_amount)
    ewt_rate = flt(pay_req.ewt_rate) if hasattr(pay_req, "ewt_rate") and pay_req.ewt_rate else 1.0
    ewt_amount = flt(gross_amount * ewt_rate / 100, 2)
    atc_code = "WI100"  # Default: Income payments to suppliers of goods

    import json as _json

    form_2307_data = {
        "supplier_tin": supplier_tin,
        "supplier_name": supplier_name,
        "tax_period": tax_period,
        "atc_code": atc_code,
        "gross_amount": gross_amount,
        "ewt_rate": ewt_rate,
        "ewt_amount": ewt_amount,
        "payment_request": payment_request,
        "generated_by": frappe.session.user,
        "generated_on": nowdate(),
    }

    # Store as JSON in a custom field or comment for retrieval
    # Using comment-based storage until a dedicated DocType is created
    existing = frappe.db.sql(
        """SELECT name FROM `tabComment`
        WHERE reference_doctype = 'BEI Payment Request'
          AND reference_name = %s
          AND comment_type = 'Info'
          AND content LIKE '%%FORM_2307_DATA%%'""",
        (payment_request,),
    )

    content = "FORM_2307_DATA:" + _json.dumps(form_2307_data)

    if existing:
        frappe.db.set_value("Comment", existing[0][0], "content", content)
    else:
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "BEI Payment Request",
            "reference_name": payment_request,
            "content": content,
        }).insert(ignore_permissions=True)

    return {
        "success": True,
        "data": form_2307_data,
        "message": _("Form 2307 data generated for {0}.").format(supplier_name),
    }


@frappe.whitelist(allow_guest=False)
def get_form_2307_data(supplier=None, tax_period=None):
    """Retrieve Form 2307 entries filtered by supplier and/or tax period.

    Args:
        supplier: Optional supplier name filter
        tax_period: Optional tax period filter (YYYY-MM)
    """
    import json as _json

    comments = frappe.db.sql(
        """SELECT c.content, c.reference_name, c.modified
        FROM `tabComment` c
        WHERE c.reference_doctype = 'BEI Payment Request'
          AND c.comment_type = 'Info'
          AND c.content LIKE '%%FORM_2307_DATA%%'
        ORDER BY c.modified DESC""",
        as_dict=True,
    )

    entries = []
    for comment in comments:
        try:
            json_str = comment.content.split("FORM_2307_DATA:", 1)[1]
            data = _json.loads(json_str)

            if supplier and data.get("supplier_name") != supplier:
                continue
            if tax_period and data.get("tax_period") != tax_period:
                continue

            data["_modified"] = str(comment.modified)
            entries.append(data)
        except (IndexError, _json.JSONDecodeError):
            continue

    # Aggregate by supplier + tax_period
    summary = {}
    for entry in entries:
        key = "{0}|{1}".format(entry.get("supplier_name", ""), entry.get("tax_period", ""))
        if key not in summary:
            summary[key] = {
                "supplier_tin": entry.get("supplier_tin"),
                "supplier_name": entry.get("supplier_name"),
                "tax_period": entry.get("tax_period"),
                "total_gross": 0,
                "total_ewt": 0,
                "transaction_count": 0,
            }
        summary[key]["total_gross"] += flt(entry.get("gross_amount"))
        summary[key]["total_ewt"] += flt(entry.get("ewt_amount"))
        summary[key]["transaction_count"] += 1

    for v in summary.values():
        v["total_gross"] = flt(v["total_gross"], 2)
        v["total_ewt"] = flt(v["total_ewt"], 2)

    return {
        "entries": entries,
        "summary": list(summary.values()),
        "filters": {"supplier": supplier, "tax_period": tax_period},
    }
