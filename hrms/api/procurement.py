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
        **data
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

    po = frappe.get_doc({
        "doctype": "BEI Purchase Order",
        **data
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
        gr_exists = frappe.db.exists("BEI Goods Receipt", {
            "purchase_order": purchase_order,
            "status": ["in", ["Submitted", "Approved", "Inspected"]]
        })
        if not gr_exists:
            frappe.throw(
                _("Cannot create Invoice: No Goods Receipt found for PO {0}. "
                  "Create a GR first to confirm delivery.").format(purchase_order),
                title=_("Three-Way Match Required")
            )

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
    """Create new payment request.

    AUDIT CONTROL 2.1: Require Goods Receipt before Payment (Three-Way Matching)
    AUDIT CONTROL 2.2: Payment date cannot be earlier than Invoice date
    AUDIT CONTROL 2.3: Payment limited to received value (partial delivery control)
    AUDIT CONTROL 2.4: Block payment without complete PO approval for >₱500K
    Ref: Internal Audit Jan 30, 2026 - PO-2025320 paid ₱848,800 for partial delivery
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    invoice_name = data.get("invoice")
    if invoice_name:
        invoice = frappe.get_doc("BEI Invoice", invoice_name)
        purchase_order = invoice.purchase_order

        if purchase_order:
            po = frappe.get_doc("BEI Purchase Order", purchase_order)

            # AUDIT CONTROL 2.1: Check GR exists for this PO
            gr_exists = frappe.db.exists("BEI Goods Receipt", {
                "purchase_order": purchase_order,
                "status": ["in", ["Submitted", "Approved", "Inspected"]]
            })
            if not gr_exists:
                frappe.throw(
                    _("Cannot create Payment Request: No Goods Receipt found for PO {0}. "
                      "Delivery must be confirmed before payment.").format(purchase_order),
                    title=_("Three-Way Match Required")
                )

            # AUDIT CONTROL 2.3: Payment limited to received value
            received_value = frappe.db.sql("""
                SELECT COALESCE(SUM(gri.quantity * gri.unit_cost), 0)
                FROM `tabBEI Goods Receipt Item` gri
                JOIN `tabBEI Goods Receipt` gr ON gri.parent = gr.name
                WHERE gr.purchase_order = %s
                AND gr.status IN ('Submitted', 'Approved', 'Inspected')
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
            AND gr.status IN ('Submitted', 'Approved', 'Inspected')
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
            SUM(gri.quantity) as received_qty,
            gri.unit_cost,
            SUM(gri.quantity * gri.unit_cost) as received_value
        FROM `tabBEI Goods Receipt Item` gri
        JOIN `tabBEI Goods Receipt` gr ON gri.parent = gr.name
        WHERE gr.purchase_order = %s
        AND gr.status IN ('Submitted', 'Approved', 'Inspected')
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
            posting_date,
            total_amount,
            paid_amount,
            supplier,
            supplier_name,
            status
        FROM `tabBEI Invoice`
        WHERE status IN ('Pending Payment', 'Partially Paid', 'Verified')
        AND docstatus != 2
        ORDER BY posting_date ASC
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
        outstanding = flt(inv.total_amount, 2) - flt(inv.paid_amount, 2)

        if outstanding <= 0:
            continue

        # Calculate age in days
        age_days = (today - getdate(inv.posting_date)).days

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
            "posting_date": str(inv.posting_date),
            "age_days": age_days,
            "outstanding": flt(outstanding, 2)
        })

        total_payables += outstanding

        invoice_details.append({
            "invoice": inv.name,
            "supplier": inv.supplier_name,
            "posting_date": str(inv.posting_date),
            "total_amount": flt(inv.total_amount, 2),
            "paid_amount": flt(inv.paid_amount, 2),
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

    # Filter invoice details for this supplier
    supplier_invoices = [
        inv for inv in aging["invoice_details"]
        if inv["supplier"] == supplier or frappe.db.get_value("BEI Invoice", inv["invoice"], "supplier") == supplier
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
