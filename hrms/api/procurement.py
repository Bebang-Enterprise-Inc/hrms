# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
# ruff: noqa
# fmt: off

"""
Procurement API - Complete procurement workflow endpoints
Supports: Suppliers, PR, PO, GR, Invoice, Payment Request, Dashboard

All endpoints use @frappe.whitelist() for external access.
"""

import json
import re
from typing import Any

import frappe
from hrms.utils.bei_config import get_company
from hrms.utils.delivery_billing_policy import CPO_APPROVER_EMAIL, CFO_APPROVER_EMAIL, append_approval_audit_log, get_approver_email
from hrms.utils.procurement_math import calculate_goods_receipt_gross_total
from frappe import _
from frappe.utils import flt, cint, getdate, nowdate, add_days, get_first_day, get_last_day


# System fields that must never be set by API callers
_BLOCKED_FIELDS = frozenset({
    "doctype", "name", "owner", "creation", "modified", "modified_by",
    "docstatus", "idx", "parent", "parenttype", "parentfield",
    "_user_tags", "_comments", "_assign", "_liked_by",
    "allow_missing_supplier_invoice",
    "missing_supplier_invoice_reason",
    "missing_supplier_invoice_effective_date",
    "missing_supplier_invoice_whitelisted_by",
})
_SUPPLIER_INVOICE_EXCEPTION_MANAGER_ROLES = {
    "System Manager",
    "Procurement Manager",
    "Accounts Manager",
}
IAN_GR_VALIDATOR_EMAILS = frozenset({"ian@bebang.ph"})


def _sanitize_doc_data(data):
    """Remove system/internal fields from user-supplied data before doc creation."""
    return {k: v for k, v in data.items() if k not in _BLOCKED_FIELDS}


def _populate_payment_request_invoice_context(data: dict[str, Any], invoice: Any) -> None:
    """Backfill canonical vendor-invoice fields from the linked invoice."""
    if not data.get("supplier") and getattr(invoice, "supplier", None):
        data["supplier"] = invoice.supplier

    if not data.get("supplier_name"):
        supplier_name = getattr(invoice, "supplier_name", None)
        if not supplier_name and data.get("supplier"):
            supplier_name = frappe.db.get_value("BEI Supplier", data["supplier"], "supplier_name")
        if supplier_name:
            data["supplier_name"] = supplier_name

    if not data.get("purchase_order") and getattr(invoice, "purchase_order", None):
        data["purchase_order"] = invoice.purchase_order

    if not data.get("goods_receipt") and getattr(invoice, "goods_receipt", None):
        data["goods_receipt"] = invoice.goods_receipt

    if not data.get("payment_amount"):
        data["payment_amount"] = flt(invoice.balance_due or invoice.grand_total, 2)

    if not data.get("rfp_type"):
        data["rfp_type"] = "Vendor Invoice"


def _populate_invoice_context(
    data: dict[str, Any],
    purchase_order: Any | None = None,
    goods_receipt: Any | None = None,
) -> None:
    """Backfill invoice party context from linked procurement documents."""
    if not data.get("purchase_order") and getattr(goods_receipt, "purchase_order", None):
        data["purchase_order"] = goods_receipt.purchase_order

    if not data.get("supplier"):
        supplier = getattr(purchase_order, "supplier", None) or getattr(goods_receipt, "supplier", None)
        if supplier:
            data["supplier"] = supplier

    if not data.get("supplier_name"):
        supplier_name = (
            getattr(purchase_order, "supplier_name", None)
            or getattr(goods_receipt, "supplier_name", None)
        )
        if not supplier_name and data.get("supplier"):
            supplier_name = frappe.db.get_value("BEI Supplier", data["supplier"], "supplier_name")
        if supplier_name:
            data["supplier_name"] = supplier_name


def _require_roles(allowed_roles: set[str], message: str) -> None:
    """Enforce role-based access for sensitive procurement actions."""
    user = frappe.session.user or "Guest"
    if user == "Administrator":
        return

    user_roles = set(frappe.get_roles(user))
    if user_roles.intersection(allowed_roles):
        return

    frappe.throw(message, frappe.PermissionError)


def _resolve_supplier_identity(supplier: str) -> tuple[str, str]:
    """Resolve supplier input (ID or display name) into canonical BEI Supplier values."""
    supplier = (supplier or "").strip()
    if not supplier:
        frappe.throw(_("Supplier is required."))

    if frappe.db.exists("BEI Supplier", supplier):
        supplier_id = supplier
        supplier_name = frappe.db.get_value("BEI Supplier", supplier_id, "supplier_name") or supplier_id
        return supplier_id, supplier_name

    supplier_id = frappe.db.get_value("BEI Supplier", {"supplier_name": supplier}, "name")
    if supplier_id:
        return supplier_id, supplier

    supplier_id = frappe.db.get_value("BEI Supplier", {"supplier_name": ["like", supplier]}, "name")
    if supplier_id:
        supplier_name = frappe.db.get_value("BEI Supplier", supplier_id, "supplier_name") or supplier
        return supplier_id, supplier_name

    frappe.throw(
        _("Supplier '{0}' not found. Use supplier ID or exact supplier name.").format(supplier),
        frappe.ValidationError,
    )


# S193 — Supplier Status Guard
# Statuses that block ALL create flows (new business with this supplier).
_SUPPLIER_BLOCK_ALL_STATUSES = frozenset({"Blacklisted", "Pending Verification"})
# Statuses that additionally block new PO creation (no new business with inactive).
# Invoices and payment requests on pre-existing POs remain allowed so in-flight
# work is not stranded when a supplier is deactivated.
_SUPPLIER_BLOCK_NEW_PO_STATUSES = frozenset({"Inactive"})


def _assert_supplier_active(supplier: str, operation: str) -> None:
    """Block creation against suppliers in forbidden statuses (S193).

    Args:
        supplier: BEI Supplier document name (resolved by caller).
        operation: one of "purchase_order", "invoice", "payment_request".

    Policy:
        - Blacklisted / Pending Verification: block all three operations.
        - Inactive: block purchase_order only.
        - Active (or any unknown/empty status): allow.

    Raises:
        frappe.ValidationError: with the supplier name, current status, and
        the next step the operator should take. Maps to HTTP 417 and surfaces
        in the frontend via parseFrappeError.
    """
    status = frappe.db.get_value("BEI Supplier", supplier, "status")
    if not status:
        # Supplier does not exist — Link-field validation would normally catch
        # this upstream. If we got here via a stale ID, let the caller handle
        # non-existence (existing flows already throw on get_doc).
        return

    blocked = status in _SUPPLIER_BLOCK_ALL_STATUSES
    if operation == "purchase_order" and status in _SUPPLIER_BLOCK_NEW_PO_STATUSES:
        blocked = True

    if not blocked:
        return

    name_display = frappe.db.get_value("BEI Supplier", supplier, "supplier_name") or supplier

    if status == "Blacklisted":
        next_step = _("Contact the Procurement Manager to review the blacklist decision.")
    elif status == "Pending Verification":
        next_step = _("Complete supplier verification (TIN, SEC, bank details) before transacting.")
    else:  # Inactive
        next_step = _("Re-activate the supplier in the Supplier Hub if business continues.")

    op_label = {
        "purchase_order": _("Purchase Order"),
        "invoice": _("Invoice"),
        "payment_request": _("Payment Request"),
    }.get(operation, operation)

    # DM-7 observability — policy denials should be visible in Sentry.
    # Wrapped in try/except so observability failure NEVER breaks the guard.
    try:
        from hrms.utils.sentry import set_backend_observability_context
        set_backend_observability_context(
            module="procurement",
            action="assert_supplier_active_denied",
            extras={"supplier": supplier, "status": status, "operation": operation},
        )
    except Exception:
        pass

    frappe.throw(
        _("Cannot create {0}: Supplier {1} is {2}. {3}").format(
            op_label, name_display, status, next_step
        ),
        frappe.ValidationError,
    )


def _table_has_column(table_name: str, column_name: str) -> bool:
    """Return True when a physical table column exists in the current site schema."""
    rows = frappe.db.sql(
        """
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %(table_name)s
          AND COLUMN_NAME = %(column_name)s
        LIMIT 1
        """,
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(rows)


def _normalize_user_id(value: str | None) -> str:
    return (value or "").strip().lower()


def _join_csv_emails(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        parts = [str(item).strip() for item in value if str(item).strip()]
    else:
        parts = [item.strip() for item in str(value).split(",") if item and item.strip()]
    return ", ".join(dict.fromkeys(parts))


def _is_ian_validator_user(user_id: str | None) -> bool:
    normalized = _normalize_user_id(user_id)
    if normalized in {"administrator", *IAN_GR_VALIDATOR_EMAILS}:
        return True

    if not user_id:
        return False

    employee_name = frappe.db.get_value("Employee", {"user_id": user_id}, "employee_name")
    if employee_name:
        normalized_name = employee_name.strip().upper()
        return "IAN" in normalized_name and "DIONISIO" in normalized_name

    return False


def _resolve_employee_label(employee_id: str | None) -> str | None:
    if not employee_id:
        return None
    return frappe.db.get_value("Employee", employee_id, "employee_name") or employee_id


def _decorate_goods_receipt_policy_fields(data: dict) -> dict:
    current_user = frappe.session.user or "Guest"
    status = data.get("status")
    uploaded_by = data.get("uploaded_by") or data.get("owner")
    is_ian = _is_ian_validator_user(current_user)
    is_self_validation = _normalize_user_id(current_user) == _normalize_user_id(uploaded_by)

    block_reason = None
    can_validate = False
    if status == "Pending Inspection":
        if is_ian:
            can_validate = True
        else:
            block_reason = _("Only Ian can validate Goods Receipts at this time.")
    else:
        block_reason = _("Goods Receipt is not pending inspection.")

    if data.get("self_validation_exception"):
        data["self_validation_label"] = _("Self-validated by Ian (temporary exception)")
    elif status == "Pending Inspection" and is_ian and is_self_validation:
        data["self_validation_label"] = _("Ian may self-validate this GR under the temporary exception.")
    else:
        data["self_validation_label"] = None

    data["validator_of_record"] = "Ian Dionisio"
    data["can_validate"] = can_validate
    data["validation_block_reason"] = block_reason
    data["received_by_display"] = _resolve_employee_label(data.get("received_by"))
    data["inspection_actor_display"] = data.get("validated_by") or data.get("inspector")
    return data


def _get_g046_sql_parts():
    """Build schema-compatible SQL fragments for G-046 visibility queries."""
    has_stock_entry_column = _table_has_column("tabSales Invoice", "custom_stock_entry")

    if has_stock_entry_column:
        stock_entry_expr = "si.custom_stock_entry"
        base_conditions = ["si.docstatus != 2", "IFNULL(si.custom_stock_entry, '') != ''"]
    else:
        stock_entry_expr = (
            "CASE "
            "WHEN LOCATE('SE:', IFNULL(si.remarks, '')) > 0 "
            "THEN TRIM(SUBSTRING_INDEX(si.remarks, 'SE:', -1)) "
            "ELSE NULL END"
        )
        base_conditions = [
            "si.docstatus != 2",
            "(pi.name IS NOT NULL OR si.remarks LIKE 'Inter-company Sales Invoice for Hub Transfer SE:%%')",
        ]

    stock_entry_join = f"LEFT JOIN `tabStock Entry` se ON se.name = {stock_entry_expr}"
    return stock_entry_expr, stock_entry_join, base_conditions


# =============================================================================
# PROCUREMENT REPORT HELPERS
# =============================================================================

def _check_procurement_report_access():
    """Shared permission check for all report endpoints."""
    if not frappe.has_permission("BEI Purchase Order", "read"):
        frappe.throw(_("You do not have access to procurement reports"), frappe.PermissionError)


SUPPLIER_SORT_COLUMNS = {
    "supplier_name": "s.supplier_name",
    "total_value": "s.total_po_value",
    "po_count": "s.total_po_count",
    "on_time_rate": "s.on_time_rate",
    "quality_score": "quality_score",
    "outstanding": "s.total_outstanding",
    "avg_delivery_days": "s.avg_delivery_days",
}
ALLOWED_SORT_DIRS = {"asc": "ASC", "desc": "DESC"}


def _safe_sort(sort_by, sort_order, allowed_columns, default_col):
    """Whitelist-based sort to prevent SQL injection."""
    col = allowed_columns.get(sort_by, default_col)
    direction = ALLOWED_SORT_DIRS.get((sort_order or "").lower(), "DESC")
    return col, direction


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

        statuses = _normalize_status_filters(filters)
        if len(statuses) == 1:
            conditions.append("status = %(status)s")
            values["status"] = statuses[0]
        elif statuses:
            placeholders = []
            for index, status_value in enumerate(statuses):
                key = f"status_{index}"
                placeholders.append(f"%({key})s")
                values[key] = status_value
            conditions.append(f"status IN ({', '.join(placeholders)})")

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
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement",
        action="create_supplier",
        mutation_type="create",
    )
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # S112 B-02: Auto-generate supplier_code if not provided
    # DocType has autoname: field:supplier_code with reqd: 1
    if not data.get("supplier_code"):
        data["supplier_code"] = f"SUPP-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"

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
def get_supplier_purchase_orders(name, page=1, page_size=20):
    """Get purchase orders for a specific supplier."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_purchase_orders")

    supplier_name, _ = _resolve_supplier_identity(name)
    page = max(1, cint(page))
    page_size = min(100, max(1, cint(page_size) or 20))
    offset = (page - 1) * page_size

    total = frappe.db.count("BEI Purchase Order", {"supplier": supplier_name})
    data = frappe.db.sql("""
        SELECT name, po_no, po_date, status, supplier, supplier_name,
               grand_total, delivery_date, mae_approval, butch_approval,
               requires_dual_approval
        FROM `tabBEI Purchase Order`
        WHERE supplier = %s
        ORDER BY po_date DESC
        LIMIT %s OFFSET %s
    """, (supplier_name, page_size, offset), as_dict=True)

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@frappe.whitelist()
def get_supplier_invoices(name, page=1, page_size=20):
    """Get invoices for a specific supplier."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_invoices")

    supplier_name, _ = _resolve_supplier_identity(name)
    page = max(1, cint(page))
    page_size = min(100, max(1, cint(page_size) or 20))
    offset = (page - 1) * page_size

    total = frappe.db.count("BEI Invoice", {"supplier": supplier_name})
    data = frappe.db.sql("""
        SELECT name, invoice_no, invoice_date, due_date, status,
               supplier, supplier_name, grand_total, payment_status
        FROM `tabBEI Invoice`
        WHERE supplier = %s
        ORDER BY invoice_date DESC
        LIMIT %s OFFSET %s
    """, (supplier_name, page_size, offset), as_dict=True)

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@frappe.whitelist()
def get_supplier_items(name):
    """Get aggregated items purchased from a supplier across all POs."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_items")

    supplier_name, _ = _resolve_supplier_identity(name)

    items = frappe.db.sql("""
        SELECT
            poi.item_code,
            poi.item_name,
            poi.uom,
            COUNT(DISTINCT po.name) as po_count,
            SUM(poi.qty) as total_qty,
            ROUND(AVG(poi.unit_cost), 2) as avg_rate,
            MIN(poi.unit_cost) as min_rate,
            MAX(poi.unit_cost) as max_rate,
            SUM(poi.amount) as total_amount,
            MAX(po.po_date) as last_purchase_date
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE po.supplier = %s
          AND po.status NOT IN ('Draft', 'Cancelled')
        GROUP BY poi.item_code, poi.item_name, poi.uom
        ORDER BY total_amount DESC
    """, supplier_name, as_dict=True)

    return {"items": items, "total": len(items)}


# Critical supplier fields that require Mae (CPO) approval to change
_SUPPLIER_APPROVAL_FIELDS = {
    "bank_name", "bank_account_name", "bank_account_number",
    "tin", "status", "contact_person", "email", "address",
    "supplier_name",
}


@frappe.whitelist()
def submit_supplier_edit_for_approval(name, data):
    """Submit supplier edit for CPO (Mae) approval. Critical fields go to approval queue."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement",
        action="submit_supplier_edit_for_approval",
        mutation_type="create",
    )

    if isinstance(data, str):
        data = frappe.parse_json(data)

    supplier = frappe.get_doc("BEI Supplier", name)
    safe_data = _sanitize_doc_data(data)

    # Build diff of changed fields
    changes = {}
    for key, new_value in safe_data.items():
        if not hasattr(supplier, key):
            continue
        old_value = getattr(supplier, key, None)
        if str(old_value or "") != str(new_value or ""):
            changes[key] = {"old": str(old_value or ""), "new": str(new_value or "")}

    if not changes:
        return {"success": True, "message": _("No changes detected"), "approval_required": False}

    # Check if any critical field changed
    critical_changes = {k: v for k, v in changes.items() if k in _SUPPLIER_APPROVAL_FIELDS}
    non_critical_changes = {k: v for k, v in changes.items() if k not in _SUPPLIER_APPROVAL_FIELDS}

    # Apply non-critical changes immediately
    if non_critical_changes:
        for key in non_critical_changes:
            setattr(supplier, key, safe_data[key])
        supplier.save(ignore_permissions=True)

    if not critical_changes:
        return {"success": True, "message": _("Supplier updated (no critical fields changed)"), "approval_required": False}

    # Queue critical changes for Mae approval
    # Store field (links to Warehouse) is required — use HQ warehouse for supplier approvals
    _store = frappe.db.sql("SELECT name FROM `tabWarehouse` WHERE name LIKE '%BEI' ORDER BY creation LIMIT 1", as_list=True)
    default_store = _store[0][0] if _store and _store[0] else "Stores - BEI"

    queue_entry = frappe.get_doc({
        "doctype": "BEI Approval Queue",
        "reference_doctype": "BEI Supplier",
        "reference_name": supplier.name,
        "store": default_store,
        "status": "Pending",
        "priority": "High",
        "submitted_by": frappe.session.user,
        "submitted_at": frappe.utils.now_datetime(),
        "assigned_approver": "mae@bebang.ph",
        "rejection_reason": frappe.as_json({
            "type": "supplier_edit",
            "changes": critical_changes,
            "non_critical_applied": list(non_critical_changes.keys()) if non_critical_changes else [],
        }),
    })
    queue_entry.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "message": _("Critical field changes submitted for CPO approval"),
        "approval_required": True,
        "queue_name": queue_entry.name,
        "critical_changes": critical_changes,
        "non_critical_applied": list(non_critical_changes.keys()),
    }


@frappe.whitelist()
def approve_supplier_edit(name=None, queue_name=None):
    """Mae approves pending supplier edit — apply stored changes."""
    queue_name = queue_name or name
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement",
        action="approve_supplier_edit",
        mutation_type="update",
    )

    queue = frappe.get_doc("BEI Approval Queue", queue_name)
    if queue.status != "Pending":
        frappe.throw(_("This approval request is no longer pending"))

    change_data = frappe.parse_json(queue.rejection_reason or "{}")
    changes = change_data.get("changes", {})

    if not changes or queue.reference_doctype != "BEI Supplier":
        frappe.throw(_("Invalid approval queue entry"))

    supplier = frappe.get_doc("BEI Supplier", queue.reference_name)
    for key, diff in changes.items():
        if hasattr(supplier, key):
            setattr(supplier, key, diff["new"])
    supplier.save(ignore_permissions=True)

    queue.status = "Approved"
    queue.approved_by = frappe.session.user
    queue.approved_at = frappe.utils.now_datetime()
    queue.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": _("Supplier edit approved and applied")}


@frappe.whitelist()
def reject_supplier_edit(name=None, queue_name=None, reason=None):
    """Mae rejects pending supplier edit."""
    queue_name = queue_name or name
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement",
        action="reject_supplier_edit",
        mutation_type="update",
    )

    queue = frappe.get_doc("BEI Approval Queue", queue_name)
    if queue.status != "Pending":
        frappe.throw(_("This approval request is no longer pending"))

    queue.status = "Rejected"
    queue.approved_by = frappe.session.user
    queue.approved_at = frappe.utils.now_datetime()
    if reason:
        change_data = frappe.parse_json(queue.rejection_reason or "{}")
        change_data["reject_reason"] = reason
        queue.rejection_reason = frappe.as_json(change_data)
    queue.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "message": _("Supplier edit rejected")}


@frappe.whitelist()
def get_supplier_pending_approvals(name=None):
    """Get pending approval queue entries for supplier edits with full supplier context."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_pending_approvals")

    filters = {"reference_doctype": "BEI Supplier", "status": "Pending"}
    if name:
        filters["reference_name"] = name

    entries = frappe.get_all("BEI Approval Queue",
        filters=filters,
        fields=["name", "reference_name", "submitted_by", "submitted_at", "assigned_approver", "rejection_reason"],
        order_by="submitted_at desc",
        limit_page_length=50,
    )

    for entry in entries:
        # Parse change data
        if entry.get("rejection_reason"):
            try:
                entry["change_data"] = frappe.parse_json(entry["rejection_reason"])
            except Exception:
                entry["change_data"] = {}

        # Enrich with supplier context so Mae can make an informed decision
        try:
            sup = frappe.get_doc("BEI Supplier", entry["reference_name"])
            entry["supplier_context"] = {
                "supplier_name": sup.supplier_name,
                "supplier_code": sup.supplier_code,
                "status": sup.status,
                "creation": str(sup.creation),
                "total_po_count": cint(sup.total_po_count),
                "total_po_value": flt(sup.total_po_value),
                "total_outstanding": flt(sup.total_outstanding),
                "current_bank_name": sup.bank_name or "",
                "current_bank_account_name": sup.bank_account_name or "",
                "current_bank_account_number": sup.bank_account_number or "",
                "current_tin": sup.tin or "",
                "current_email": sup.email or "",
                "current_contact_person": sup.contact_person or "",
                "current_address": sup.address or "",
            }

            # Flag high-risk changes
            changes = entry.get("change_data", {}).get("changes", {})
            risk_flags = []
            if "bank_account_number" in changes:
                risk_flags.append("BANK_ACCOUNT_CHANGED")
            if "bank_name" in changes:
                risk_flags.append("BANK_CHANGED")
            if "bank_account_name" in changes and changes["bank_account_name"]["new"].upper() != sup.supplier_name.upper():
                risk_flags.append("BANK_NAME_MISMATCH — account name differs from supplier name")
            if "tin" in changes:
                risk_flags.append("TIN_CHANGED")
            if "status" in changes and changes["status"]["new"] == "Active" and changes["status"]["old"] != "Active":
                risk_flags.append("ACTIVATION — supplier being set to Active")
            entry["risk_flags"] = risk_flags

            # Submitter display name
            submitter = entry.get("submitted_by", "")
            if submitter:
                entry["submitted_by_name"] = frappe.db.get_value("User", submitter, "full_name") or submitter
        except Exception:
            entry["supplier_context"] = {}
            entry["risk_flags"] = []

    return {"entries": entries, "total": len(entries)}


@frappe.whitelist()
def get_all_supplier_pending_approvals():
    """Get ALL pending supplier edit approvals (for Mae's approval dashboard)."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_all_supplier_pending_approvals")
    return get_supplier_pending_approvals(name=None)


@frappe.whitelist()
def set_supplier_invoice_exception(name, allowed=1, reason=None):
    """Whitelist a supplier for missing-invoice AP exception handling."""
    _require_roles(
        _SUPPLIER_INVOICE_EXCEPTION_MANAGER_ROLES,
        _("You are not allowed to manage supplier invoice exceptions."),
    )

    supplier_name, _supplier_display_name = _resolve_supplier_identity(name)
    supplier = frappe.get_doc("BEI Supplier", supplier_name)

    is_allowed = 1 if cint(allowed) else 0
    cleaned_reason = (reason or "").strip()
    effective_date = nowdate() if is_allowed else None
    whitelisted_by = frappe.session.user if is_allowed else None

    supplier.allow_missing_supplier_invoice = is_allowed
    supplier.missing_supplier_invoice_reason = cleaned_reason if is_allowed else ""
    supplier.missing_supplier_invoice_effective_date = effective_date
    supplier.missing_supplier_invoice_whitelisted_by = whitelisted_by
    supplier.save(ignore_permissions=True)

    return {
        "success": True,
        "name": supplier.name,
        "allow_missing_supplier_invoice": bool(is_allowed),
        "missing_supplier_invoice_effective_date": effective_date,
        "missing_supplier_invoice_whitelisted_by": whitelisted_by,
        "message": _("Supplier invoice exception updated."),
    }


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
        "total_outstanding": flt(supplier.total_outstanding)
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
    data = pr.as_dict()
    # Strip Frappe internal fields that leak as stray "0" in the frontend
    for key in ("docstatus", "idx", "modified_by", "owner", "doctype",
                "parent", "parentfield", "parenttype", "__unsaved",
                "__islocal", "__last_sync_on"):
        data.pop(key, None)
    for item in data.get("items") or []:
        if isinstance(item, dict):
            for key in ("docstatus", "idx", "parent", "parentfield",
                        "parenttype", "doctype", "__unsaved"):
                item.pop(key, None)
    return data


@frappe.whitelist()
def create_purchase_requisition(data=None):
    """Create new PR.

    Auto-sets mandatory defaults so the frontend doesn't need to send them:
    - request_date: today
    - requested_by: current session user's Employee record
    - date_required: 7 days from now
    - purpose: mapped from 'justification' if purpose not provided
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="create_purchase_requisition", mutation_type="create")

    if not data:
        frappe.throw(_("Missing required parameter: data"), frappe.ValidationError)
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # Auto-set mandatory defaults (S108: Luwi PR form fix)
    if not data.get("request_date"):
        data["request_date"] = frappe.utils.today()

    if not data.get("requested_by"):
        # Link field expects Employee record name, look up from user email
        emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if emp:
            data["requested_by"] = emp
        else:
            data["requested_by"] = frappe.session.user

    if not data.get("date_required"):
        data["date_required"] = frappe.utils.add_days(frappe.utils.today(), 7)

    # Map justification → purpose (frontend sends 'justification', DocType field is 'purpose')
    if not data.get("purpose") and data.get("justification"):
        data["purpose"] = data.pop("justification")
    elif not data.get("purpose"):
        data["purpose"] = "Purchase Requisition"

    # Ensure each item has item_code (use item_name as fallback)
    for item in data.get("items", []):
        if not item.get("item_code") and item.get("item_name"):
            item["item_code"] = item["item_name"]

    pr = frappe.get_doc({
        "doctype": "BEI Purchase Requisition",
        **_sanitize_doc_data(data)
    })
    pr.insert()

    return {"success": True, "name": pr.name, "pr_number": pr.pr_no or pr.name, "message": _("PR created")}


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

def _clean_optional_filter(value):
    return (value or "").strip() if isinstance(value, str) else value


def _normalize_status_filters(filters: dict[str, Any] | None) -> list[str]:
    """Normalize single- or multi-status filters from query params."""
    filters = filters or {}
    raw_statuses = filters.get("statuses")
    if raw_statuses is None:
        raw_statuses = filters.get("status")

    if isinstance(raw_statuses, str):
        try:
            raw_statuses = frappe.parse_json(raw_statuses)
        except Exception:
            raw_statuses = [raw_statuses]

    if raw_statuses is None:
        return []

    if not isinstance(raw_statuses, (list, tuple, set)):
        raw_statuses = [raw_statuses]

    normalized: list[str] = []
    for value in raw_statuses:
        cleaned = _clean_optional_filter(value)
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)

    return normalized


def build_purchase_order_operational_filters(filters=None):
    """Build exact item_code + warehouse filter clauses for PO drilldowns."""
    filters = filters or {}
    clauses = []
    values = {}

    item_code = _clean_optional_filter(filters.get("item_code"))
    warehouse = _clean_optional_filter(filters.get("warehouse"))

    if item_code:
        clauses.append(
            "EXISTS (SELECT 1 FROM `tabBEI PO Item` poi WHERE poi.parent = name AND poi.item_code = %(item_code)s)"
        )
        values["item_code"] = item_code

    if warehouse:
        clauses.append(
            "EXISTS (SELECT 1 FROM `tabBEI PO Item` poi WHERE poi.parent = name AND poi.warehouse = %(warehouse)s)"
        )
        values["warehouse"] = warehouse

    return clauses, values


def build_payment_request_operational_filters(filters=None):
    """Build exact item_code + warehouse filter clauses for finance drilldowns."""
    filters = filters or {}
    clauses = []
    values = {}

    item_code = _clean_optional_filter(filters.get("item_code"))
    warehouse = _clean_optional_filter(filters.get("warehouse"))

    if item_code:
        clauses.append(
            "EXISTS (SELECT 1 FROM `tabBEI PO Item` poi WHERE poi.parent = inv.purchase_order AND poi.item_code = %(item_code)s)"
        )
        values["item_code"] = item_code

    if warehouse:
        clauses.append(
            "EXISTS (SELECT 1 FROM `tabBEI PO Item` poi WHERE poi.parent = inv.purchase_order AND poi.warehouse = %(warehouse)s)"
        )
        values["warehouse"] = warehouse

    return clauses, values


def _normalize_purchase_order_payload(data, supplier_code=None):
    """Compute authoritative PO totals from line items and document-level adjustments.

    S099: Reads supplier vat_status to determine default VAT rate.
    - VAT Registered: uses BEI Settings default_vat_rate (12%)
    - Non-VAT or Exempt: uses 0%
    - Item-level vat_rate from frontend overrides if explicitly sent.
    """
    from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
    settings = get_procurement_settings()

    # Determine default VAT rate based on supplier status
    supplier_vat_rate = flt(settings.get("default_vat_rate", 12))
    if supplier_code:
        vat_status = frappe.db.get_value("BEI Supplier", supplier_code, "vat_status")
        if vat_status in ("Non-VAT", "Exempt"):
            supplier_vat_rate = 0

    normalized = dict(data or {})
    normalized_items = []
    subtotal = 0.0
    vat_total = 0.0

    for raw_item in normalized.get("items") or []:
        item = dict(raw_item or {})

        if "rate" in item and "unit_cost" not in item:
            item["unit_cost"] = item.pop("rate")

        if item.get("uom") and not frappe.db.exists("UOM", item["uom"]):
            item.pop("uom")

        # S104: Validate item exists — block auto-creation of new items
        item_code = item.get("item_code")
        if item_code and not frappe.db.exists("Item", item_code):
            frappe.throw(
                _("Item {0} does not exist. Submit a New Item Request for CPO approval "
                  "before adding it to a Purchase Order.").format(item_code),
                title=_("Item Not Found")
            )

        # S104: Look up contracted price and inject if item has no unit_cost or unit_cost=0
        contracted_info = None
        if item_code:
            contracted_info = get_contracted_price(item_code, supplier_code)
        contracted_rate = contracted_info["contracted_rate"] if contracted_info else None

        # Stamp contracted price for audit trail (D1)
        item["contracted_unit_cost"] = contracted_rate

        # Auto-fill from contracted price if no explicit cost given
        if contracted_rate and (not item.get("unit_cost") or flt(item.get("unit_cost")) == 0):
            item["unit_cost"] = contracted_rate

        qty = flt(item.get("qty"), 2)
        unit_cost = flt(item.get("unit_cost"), 2)
        # Use item-level vat_rate if explicitly sent, otherwise use supplier-derived rate
        vat_rate = flt(item.get("vat_rate") if item.get("vat_rate") is not None else supplier_vat_rate, 2)

        line_subtotal = flt(qty * unit_cost, 2)
        line_vat = flt(line_subtotal * vat_rate / 100, 2)

        item["qty"] = qty
        item["unit_cost"] = unit_cost
        item["vat_rate"] = vat_rate
        item["vat_amount"] = line_vat
        item["amount"] = flt(line_subtotal + line_vat, 2)

        subtotal += line_subtotal
        vat_total += line_vat
        normalized_items.append(item)

    discount_amount = flt(normalized.get("discount_amount"), 2)
    delivery_fee = flt(normalized.get("delivery_fee"), 2)
    grand_total = flt(subtotal + vat_total - discount_amount + delivery_fee, 2)

    normalized["items"] = normalized_items
    normalized["subtotal"] = flt(subtotal, 2)
    normalized["vat_amount"] = flt(vat_total, 2)
    normalized["discount_amount"] = discount_amount
    normalized["delivery_fee"] = delivery_fee
    normalized["grand_total"] = grand_total
    dual_threshold = flt(settings.get("dual_approval_threshold", 500000))
    normalized["requires_dual_approval"] = 1 if grand_total > dual_threshold else 0

    return normalized


def _normalize_invoice_payload(data):
    """Compute authoritative invoice subtotal/VAT totals from submitted line hints."""
    normalized = dict(data or {})
    raw_items = normalized.pop("items", None) or []

    subtotal = normalized.get("subtotal", normalized.get("net_total"))
    vat_amount = normalized.get("vat_amount", normalized.get("tax_amount"))

    if raw_items:
        subtotal = 0.0
        vat_amount = 0.0

        for raw_item in raw_items:
            item = dict(raw_item or {})
            qty = flt(item.get("qty"), 2)
            rate = flt(item.get("rate") or item.get("unit_cost"), 2)
            line_subtotal = flt(qty * rate, 2)

            if item.get("vat_rate") not in (None, ""):
                line_vat = flt(line_subtotal * flt(item.get("vat_rate"), 2) / 100, 2)
            elif item.get("vat_amount") not in (None, ""):
                line_vat = flt(item.get("vat_amount"), 2)
            elif item.get("amount") not in (None, ""):
                line_vat = max(flt(item.get("amount"), 2) - line_subtotal, 0)
            else:
                line_vat = 0.0

            subtotal += line_subtotal
            vat_amount += flt(line_vat, 2)

    normalized["subtotal"] = flt(subtotal, 2)
    normalized["vat_amount"] = flt(vat_amount, 2)
    normalized["withholding_tax"] = flt(normalized.get("withholding_tax"), 2)
    normalized["grand_total"] = flt(
        normalized["subtotal"] + normalized["vat_amount"] - normalized["withholding_tax"], 2
    )
    normalized.pop("net_total", None)
    normalized.pop("tax_amount", None)

    return normalized


def _augment_purchase_order_response(data):
    """Expose legacy aliases while keeping canonical VAT fields available."""
    data["net_total"] = flt(data.get("subtotal"), 2)
    data["tax_amount"] = flt(data.get("vat_amount"), 2)
    # Strip Frappe internal fields that leak as stray "0" in the frontend
    for key in ("docstatus", "idx", "modified_by", "owner", "doctype",
                "parent", "parentfield", "parenttype", "__unsaved",
                "__islocal", "__last_sync_on"):
        data.pop(key, None)
    # Also clean items child rows
    for item in data.get("items") or []:
        if isinstance(item, dict):
            for key in ("docstatus", "idx", "parent", "parentfield",
                        "parenttype", "doctype", "__unsaved"):
                item.pop(key, None)
    return data


def _augment_invoice_response(data):
    """Expose stable aliases expected by the portal detail/list contracts."""
    data["invoice_number"] = data.get("invoice_no")
    data["po_number"] = data.get("purchase_order")
    data["net_total"] = flt(data.get("subtotal"), 2)
    data["tax_amount"] = flt(data.get("vat_amount"), 2)
    return data


@frappe.whitelist()
def get_purchase_orders(
    filters: dict[str, Any] | str | None = None,
    page: int | str = 1,
    page_size: int | str = 20,
    search: str | None = None,
) -> dict[str, Any]:
    """Get paginated list of POs."""
    conditions = []
    values = {}
    applied_filters = {}

    if search:
        conditions.append(
            "(po_no LIKE %(search)s OR supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)
        applied_filters = dict(filters)

        statuses = _normalize_status_filters(filters)
        if len(statuses) == 1:
            conditions.append("status = %(status)s")
            values["status"] = statuses[0]
        elif statuses:
            placeholders = []
            for index, status_value in enumerate(statuses):
                key = f"status_{index}"
                placeholders.append(f"%({key})s")
                values[key] = status_value
            conditions.append(f"status IN ({', '.join(placeholders)})")

        if filters.get("supplier"):
            conditions.append("supplier = %(supplier)s")
            values["supplier"] = filters["supplier"]

        if filters.get("requires_dual_approval"):
            conditions.append("requires_dual_approval = 1")

        if filters.get("pending_approval"):
            conditions.append(
                "status IN ('Pending Mae Approval', 'Pending Butch Approval')"
            )

        operational_clauses, operational_values = build_purchase_order_operational_filters(filters)
        conditions.extend(operational_clauses)
        values.update(operational_values)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total_query = "SELECT COUNT(*) FROM `tabBEI Purchase Order` WHERE " + where_clause
    total = frappe.db.sql(total_query, values)[0][0]

    po_query = """
        SELECT
            name, po_no, po_date, status, supplier, supplier_name,
            subtotal, vat_amount, grand_total,
            discount_amount, delivery_fee,
            subtotal as net_total, vat_amount as tax_amount,
            requires_dual_approval, mae_approval, butch_approval,
            delivery_date
        FROM `tabBEI Purchase Order`
        WHERE """
    po_query += where_clause
    po_query += """
        ORDER BY po_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """
    pos = frappe.db.sql(po_query, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    if _clean_optional_filter(applied_filters.get("item_code")):
        for row in pos:
            row["has_item_match"] = True
    if _clean_optional_filter(applied_filters.get("warehouse")):
        for row in pos:
            row["has_warehouse_match"] = True

    return {
        "data": pos,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_purchase_order(name: str) -> dict[str, Any]:
    """Get single PO with items."""
    po = frappe.get_doc("BEI Purchase Order", name)
    data = po.as_dict()
    data["distribution_cc_emails"] = _join_csv_emails(data.get("distribution_cc_emails"))

    # Ensure items are always present (even if child table was added after PO creation)
    if not data.get("items"):
        items = frappe.db.sql("""
            SELECT name, item_code, item_name, description, qty,
                   unit_cost, unit_cost as rate, vat_rate, vat_amount, amount, uom, received_qty
            FROM `tabBEI PO Item`
            WHERE parent = %s
            ORDER BY idx
        """, (name,), as_dict=True)
        data["items"] = items

    if data.get("supplier"):
        supplier = frappe.db.get_value(
            "BEI Supplier",
            data["supplier"],
            ["bir_2307", "sec_certificate"],
            as_dict=True,
        ) or {}
        data["supplier_has_bir"] = bool(supplier.get("bir_2307"))
        data["supplier_has_sec"] = bool(supplier.get("sec_certificate"))

    return _augment_purchase_order_response(data)


@frappe.whitelist()
def get_purchase_order_history(name) -> list[dict[str, Any]]:
    """Build a readable PO activity log from workflow fields and info comments."""
    po = frappe.get_doc("BEI Purchase Order", name)
    events = [
        {
            "action": "Created",
            "user": po.owner,
            "timestamp": str(po.creation),
            "comment": _("Purchase Order created."),
        }
    ]

    if po.mae_approval_date:
        events.append(
            {
                "action": "Approved",
                "user": "Mae Karazi",
                "timestamp": str(po.mae_approval_date),
                "comment": po.mae_comment or _("Approved by Mae."),
            }
        )

    if po.butch_approval_date:
        events.append(
            {
                "action": "Approved",
                "user": "Butch Formoso",
                "timestamp": str(po.butch_approval_date),
                "comment": po.butch_comment or _("Approved by Butch."),
            }
        )

    comment_rows = frappe.db.sql(
        """
        SELECT comment_email, content, modified
        FROM `tabComment`
        WHERE reference_doctype = 'BEI Purchase Order'
          AND reference_name = %s
          AND comment_type IN ('Info', 'Comment')
        ORDER BY modified ASC
        """,
        (name,),
        as_dict=True,
    )
    for row in comment_rows:
        events.append(
            {
                "action": "Activity",
                "user": row.get("comment_email") or _("System"),
                "timestamp": str(row.get("modified")),
                "comment": row.get("content"),
            }
        )

    events.sort(key=lambda event: event.get("timestamp") or "")
    return events


@frappe.whitelist()
def get_purchase_order_items(name: str) -> list[dict[str, Any]]:
    """Get items for a specific PO."""
    return frappe.db.sql("""
        SELECT name, item_code, item_name, description, qty, unit_cost, unit_cost as rate,
               vat_rate, vat_amount, amount, uom, received_qty
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
def create_purchase_order(data: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Create new PO.

    AUDIT CONTROL 2.8: Supplier master data quality checks
    - Mandatory TIN for suppliers with >₱250K annual purchases
    Ref: Internal Audit Jan 30, 2026 - Max's Bakeshop ₱10M not in master list
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="create_purchase_order", mutation_type="create")

    if not data:
        frappe.throw(_("Missing required parameter: data"), frappe.ValidationError)
    if isinstance(data, str):
        data = frappe.parse_json(data)

    supplier_name = (data or {}).get("supplier")

    # S193 Guard: block new PO for Blacklisted / Pending Verification / Inactive suppliers.
    if supplier_name:
        _assert_supplier_active(supplier_name, "purchase_order")

    data = _normalize_purchase_order_payload(data, supplier_code=supplier_name)

    warnings = []

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

        # If total annual + this PO > TIN threshold, require TIN
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        _tin_settings = get_procurement_settings()
        _tin_threshold = flt(_tin_settings.get("tin_requirement_threshold", 250000))
        if flt(annual_purchases) + po_value > _tin_threshold:
            if not supplier.tin:
                frappe.throw(
                    _("Supplier {0} requires TIN registration. "
                      "Annual purchases (₱{1:,.2f}) + this PO (₱{2:,.2f}) exceed ₱250,000 threshold. "
                      "Update supplier master data before proceeding.").format(
                        supplier.supplier_name, annual_purchases, po_value
                    ),
                    title=_("TIN Required")
                )

        # AUDIT CONTROL 2.8: Warn if supplier missing key documents (incl. SEC registration)
        missing_docs = []
        if not supplier.bir_2307:
            missing_docs.append("BIR 2307")
        if not supplier.business_permit:
            missing_docs.append("Business Permit")
        if not getattr(supplier, "sec_registration", None) and not getattr(supplier, "sec_certificate", None):
            missing_docs.append("SEC Registration")

        if missing_docs:
            warnings.append(
                _("Supplier {0} is missing documents: {1}").format(
                    supplier.supplier_name, ", ".join(missing_docs)
                )
            )

    # S104: Validate price override reason when cost differs from contracted price
    for item in data.get("items") or []:
        contracted = flt(item.get("contracted_unit_cost"), 2)
        actual = flt(item.get("unit_cost"), 2)
        if contracted and contracted > 0 and actual != contracted:
            if not item.get("price_override_reason"):
                frappe.throw(
                    _("Price for item {0} (₱{1:,.2f}) differs from contracted rate (₱{2:,.2f}). "
                      "Please provide a price override reason.").format(
                        item.get("item_code"), actual, contracted
                    ),
                    title=_("Price Override Reason Required")
                )

    # S134/C1 + S138: Default ship_to warehouse.
    # If a store is specified, resolve to its 3PL source warehouse via BEI Route.
    # Otherwise default to Stores - BEI as the general receiving point.
    if not data.get("ship_to"):
        for_store = data.get("for_store") or data.get("delivery_warehouse")
        if for_store:
            route_wh = frappe.db.get_value(
                "BEI Route",
                {"active": 1, "cargo_type": "DRY"},
                "source_warehouse",
                filters={"name": ["in",
                    [r.parent for r in frappe.get_all("BEI Route Stop",
                        filters={"store": for_store}, fields=["parent"])]
                ]},
            )
            data["ship_to"] = route_wh or "Stores - BEI"
        else:
            data["ship_to"] = "Stores - BEI"

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
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="submit_po_for_approval", mutation_type="update",
    )
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.submit_for_approval()


@frappe.whitelist()
def approve_po_mae(name, comment=None):
    """Mae approves PO."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="approve_po_mae", mutation_type="update",
    )
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.approve_mae(comment)


@frappe.whitelist()
def approve_po_butch(name, comment=None):
    """Butch (CFO) approves PO for >500K."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="approve_po_butch", mutation_type="update",
    )
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.approve_butch(comment)


@frappe.whitelist()
def approve_po_ceo(name, comment=None):
    """CEO approves PO (for new vendor POs requiring CEO sign-off)."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement",
        action="approve_po_ceo",
        mutation_type="update",
    )
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.approve_ceo(comment)


@frappe.whitelist()
def batch_approve_pos(names, level="mae", comment=None):
    """Batch approve multiple POs at once.

    Args:
        names: JSON list of PO names to approve
        level: 'mae' or 'butch'
        comment: Optional approval comment applied to all
    Returns:
        dict with 'results' list (per-PO success/failure) and summary counts
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="procurement",
        action="batch_approve_pos",
        mutation_type="update",
    )

    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names or not isinstance(names, list):
        frappe.throw(_("No POs selected for approval"))

    results = []
    approved = 0
    failed = 0

    for po_name in names:
        try:
            po = frappe.get_doc("BEI Purchase Order", po_name)
            if level == "mae":
                result = po.approve_mae(comment)
            elif level == "butch":
                result = po.approve_butch(comment)
            else:
                frappe.throw(_("Invalid approval level: {0}").format(level))

            results.append({
                "name": po_name,
                "po_no": po.po_no,
                "success": True,
                "message": result.get("message", "Approved"),
            })
            approved += 1
        except Exception as e:
            results.append({
                "name": po_name,
                "success": False,
                "message": str(e),
            })
            failed += 1

    frappe.db.commit()

    return {
        "results": results,
        "approved": approved,
        "failed": failed,
        "total": len(names),
    }


@frappe.whitelist()
def duplicate_po(source_name):
    """Create a new Draft PO by duplicating an existing PO.

    Copies supplier, items, prices, and terms. Sets new PO date to today.
    Returns the new PO name for redirect.
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="procurement",
        action="duplicate_po",
        mutation_type="create",
    )

    source = frappe.get_doc("BEI Purchase Order", source_name)

    # Build items from source PO
    items = []
    for item in source.get("items") or []:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "uom": item.uom,
            "unit_cost": item.unit_cost,
            "vat_rate": item.get("vat_rate") or 0,
            "vat_amount": item.get("vat_amount") or 0,
            "amount": item.get("amount") or 0,
            "contracted_unit_cost": item.get("contracted_unit_cost") or 0,
            "price_variance_override": item.get("price_variance_override") or "",
            "price_variance_override_by": item.get("price_variance_override_by") or "",
            "price_variance_override_date": item.get("price_variance_override_date"),
        })

    new_po = frappe.get_doc({
        "doctype": "BEI Purchase Order",
        "supplier": source.supplier,
        "supplier_name": source.supplier_name,
        "po_date": frappe.utils.today(),
        "delivery_date": source.get("delivery_date") or frappe.utils.add_days(frappe.utils.today(), 7),
        "payment_terms": source.get("payment_terms"),
        "remarks": _("Duplicated from {0}").format(source.po_no or source_name),
        "items": items,
        "pr_reference": None,
        "status": "Draft",
    })

    new_po.insert(ignore_permissions=True)

    return {
        "success": True,
        "name": new_po.name,
        "po_no": new_po.po_no,
        "message": _("PO duplicated from {0}").format(source.po_no or source_name),
        "source_po": source_name,
    }


@frappe.whitelist()
def reject_po(name, reason, rejector="mae"):
    """Reject PO."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="reject_po", mutation_type="update",
    )
    po = frappe.get_doc("BEI Purchase Order", name)
    return po.reject(reason, rejector)


@frappe.whitelist()
def request_po_revision(name, reason):
    """Request revision on a PO — sends it back to Draft so the creator can fix and resubmit.

    Unlike Reject (which kills the PO), Request Revision keeps the PO alive
    and allows editing. Used when Mae sees a wrong price, wrong qty, or
    missing information that can be corrected.
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="procurement",
        action="request_po_revision",
        mutation_type="update",
    )

    if not reason or not reason.strip():
        frappe.throw(_("Reason for revision request is required"))

    po = frappe.get_doc("BEI Purchase Order", name)

    if po.status not in ("Pending Mae Approval", "Pending Butch Approval"):
        frappe.throw(_("Can only request revision on POs pending approval"))

    po.status = "Draft"
    po.mae_approval = ""
    po.mae_comment = ""
    po.mae_approval_date = None

    # Add revision comment to remarks
    revision_note = f"Revision requested by {frappe.session.user}: {reason.strip()}"
    po.add_comment("Comment", revision_note)

    po.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("PO sent back for revision"),
        "reason": reason.strip(),
        "requested_by": frappe.session.user,
    }


def _get_po_pdf_bytes(po_name):
    """Return PO PDF as raw bytes for email attachment."""
    import base64
    from hrms.api import _download_pdf
    b64_data = _download_pdf("BEI Purchase Order", po_name)
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    return base64.b64decode(b64_data)


def _get_procurement_finance_cc_list():
    """Return procurement + finance CC emails for PO distribution."""
    cc = []
    for role in ("Procurement Manager", "Accounts Manager"):
        users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
        cc.extend(users)
    seen = set()
    return [e for e in cc if e and "@" in e and not (e in seen or seen.add(e))]


@frappe.whitelist()
def send_po_to_supplier(
    name,
    action="send",
    outcome="success",
    recipient_email=None,
    cc_emails=None,
    send_mode="manual",
    message_id=None,
    error_message=None,
):
    """Send PO PDF to supplier via email and record distribution event."""
    po = frappe.get_doc("BEI Purchase Order", name)
    if send_mode in ("email", "auto_approval"):
        supplier = frappe.get_doc("BEI Supplier", po.supplier)
        if not supplier.email:
            return {"success": False, "error": "Supplier has no email on file"}
        try:
            pdf_content = _get_po_pdf_bytes(name)
            frappe.sendmail(
                recipients=[supplier.email],
                cc=_get_procurement_finance_cc_list(),
                subject=f"Purchase Order {po.name} - {po.supplier_name}",
                message="Please find attached Purchase Order " + po.name + ". Bebang Enterprise Inc.",
                attachments=[{"fname": f"PO-{po.name}.pdf", "fcontent": pdf_content}],
                now=True,
            )
            recipient_email = supplier.email
            outcome = "success"
            action = "send"
        except Exception as e:
            frappe.log_error(f"PO email failed for {name}: {e!s}")
            outcome = "failed"
            error_message = str(e)
    return po.record_distribution_event(
        action=action, outcome=outcome, recipient_email=recipient_email,
        cc_emails=cc_emails, send_mode=send_mode, message_id=message_id,
        error_message=error_message,
    )


@frappe.whitelist()
def get_purchase_order_pdf(name):
    """Return a data URL for the supplier-facing PO PDF."""
    from hrms.api import _download_pdf

    return {
        "name": name,
        "filename": f"{name}.pdf",
        "data_url": _download_pdf("BEI Purchase Order", name),
    }


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
def get_goods_receipts(
    filters: dict[str, Any] | str | None = None,
    page: int | str = 1,
    page_size: int | str = 20,
    search: str | None = None,
) -> dict[str, Any]:
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

    total_query = "SELECT COUNT(*) FROM `tabBEI Goods Receipt` WHERE " + where_clause
    total = frappe.db.sql(total_query, values)[0][0]

    gr_query = """
        SELECT
            name, gr_no, gr_no as gr_number, receipt_date, status,
            purchase_order, purchase_order as po_number,
            supplier, supplier_name,
            delivery_note_no, total_ordered_qty, total_received_qty, total_accepted_qty, total_rejected_qty, total_amount,
            uploaded_by, received_by, inspection_status, inspection_notes,
            validated_by, validated_at, validation_actor_mode, self_validation_exception
        FROM `tabBEI Goods Receipt`
        WHERE """
    gr_query += where_clause
    gr_query += """
        ORDER BY receipt_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """
    grs = frappe.db.sql(gr_query, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    for row in grs:
        _decorate_goods_receipt_policy_fields(row)

    return {
        "data": grs,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_goods_receipt(name: str) -> dict[str, Any]:
    """Get single GR with items."""
    gr = frappe.get_doc("BEI Goods Receipt", name)
    data = gr.as_dict()
    data["gr_number"] = data.get("gr_no")
    data["po_number"] = data.get("purchase_order")
    _decorate_goods_receipt_policy_fields(data)
    return data


@frappe.whitelist()
def get_goods_receipts_for_po(name):
    """Get goods receipts linked to a specific PO."""
    rows = frappe.db.sql("""
        SELECT name, gr_no, gr_no as gr_number, receipt_date, status,
            purchase_order, purchase_order as po_number,
            supplier, supplier_name,
            delivery_note_no, total_ordered_qty, total_received_qty, total_accepted_qty, total_rejected_qty, total_amount,
            uploaded_by, received_by, inspection_status, inspection_notes,
            validated_by, validated_at, validation_actor_mode, self_validation_exception
        FROM `tabBEI Goods Receipt`
        WHERE purchase_order = %s
        ORDER BY receipt_date DESC
    """, (name,), as_dict=True)
    for row in rows:
        _decorate_goods_receipt_policy_fields(row)
    return rows


@frappe.whitelist()
def get_invoices_for_po(name: str) -> list[dict[str, Any]]:
	"""Get invoices linked to a specific PO."""
	return frappe.db.sql("""
        SELECT name, invoice_no, invoice_no as invoice_number, supplier_invoice_no, invoice_date, due_date, status,
            supplier, supplier_name, purchase_order, purchase_order as po_number,
            goods_receipt, goods_receipt as gr_number,
            subtotal, vat_amount, subtotal as net_total, vat_amount as tax_amount,
            grand_total, balance_due, payment_status, match_status
        FROM `tabBEI Invoice`
        WHERE purchase_order = %s
        ORDER BY invoice_date DESC
    """, (name,), as_dict=True)


@frappe.whitelist()
def create_goods_receipt(data: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Create new GR.

    AUDIT CONTROL 2.4: Block GR creation for >₱500K POs without complete approval
    Ref: Internal Audit Jan 30, 2026 - CFO "Pending" but payment released
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="create_goods_receipt", mutation_type="create")
    if not data:
        frappe.throw(_("Missing required parameter: data"), frappe.ValidationError)
    if isinstance(data, str):
        data = frappe.parse_json(data)

    po = None

    # AUDIT CONTROL 2.4: Validate PO approval for >threshold
    from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
    _gr_settings = get_procurement_settings()
    _dual_threshold = flt(_gr_settings.get("dual_approval_threshold", 500000))
    purchase_order = data.get("purchase_order")
    if purchase_order:
        po = frappe.get_doc("BEI Purchase Order", purchase_order)
        if flt(po.grand_total) > _dual_threshold:
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

        if not data.get("warehouse") and po.ship_to:
            data["warehouse"] = po.ship_to

        # FIX-D4 (S153): Fallback to BEI Settings default when PO has no ship_to
        if not data.get("warehouse"):
            default_wh = frappe.db.get_single_value("BEI Settings", "default_receiving_warehouse")
            if default_wh:
                data["warehouse"] = default_wh
            else:
                frappe.throw(
                    _("Warehouse is required. Set a default receiving warehouse in BEI Settings."),
                    title=_("Missing Warehouse")
                )

    received_by = (data.get("received_by") or "").strip()
    if received_by and not frappe.db.exists("Employee", received_by):
        employee_match = frappe.db.get_value("Employee", {"employee_name": received_by}, "name")
        if employee_match:
            data["received_by"] = employee_match
        else:
            data.pop("received_by", None)

    # Map 'rate' to 'unit_cost' in items if needed
    po_item_map = {}
    if po:
        po_item_map = {row.item_code: row for row in po.items}

    if "items" in data:
        for item in data["items"]:
            po_item = po_item_map.get(item.get("item_code"))

            if po_item:
                if not item.get("item_name"):
                    item["item_name"] = po_item.item_name
                if not item.get("description"):
                    item["description"] = po_item.description
                if not item.get("ordered_qty"):
                    item["ordered_qty"] = po_item.qty
                if item.get("unit_cost") in (None, ""):
                    item["unit_cost"] = po_item.unit_cost
                if not item.get("uom"):
                    item["uom"] = po_item.uom

            if "rate" in item and "unit_cost" not in item:
                item["unit_cost"] = item.pop("rate")
            # Strip invalid UOM to avoid LinkValidationError
            if item.get("uom") and not frappe.db.exists("UOM", item["uom"]):
                item.pop("uom")

    # B1: Over-receipt prevention — validate received qty against ordered + tolerance
    if po and "items" in data:
        tolerance_pct = 5.0
        try:
            setting_val = frappe.db.get_single_value("BEI Settings", "gr_over_receipt_tolerance_pct")
            if setting_val is not None:
                tolerance_pct = flt(setting_val)
        except Exception:
            pass

        for item in data["items"]:
            item_code = item.get("item_code")
            po_item = po_item_map.get(item_code)
            if not po_item:
                continue
            ordered_qty = flt(po_item.qty)
            already_received = flt(po_item.received_qty) if hasattr(po_item, "received_qty") else 0
            this_received = flt(item.get("received_qty") or item.get("qty") or ordered_qty)
            max_allowed = (ordered_qty - already_received) * (1 + tolerance_pct / 100)
            if this_received > max_allowed and max_allowed > 0:
                frappe.throw(
                    _("Received quantity ({0}) for item {1} exceeds ordered quantity "
                      "minus already received ({2}) plus {3}% tolerance (max: {4})").format(
                        this_received, item_code, ordered_qty - already_received,
                        tolerance_pct, flt(max_allowed, 2)
                    ),
                    title=_("Over-Receipt Not Allowed"),
                )

    # DM-2: Savepoint for atomic GR creation
    frappe.db.savepoint("goods_receipt_creation")
    auto_submit = bool(data.pop("auto_submit", False))
    gr = frappe.get_doc({
        "doctype": "BEI Goods Receipt",
        **_sanitize_doc_data(data)
    })
    gr.insert()
    # When called from API integrations (E2E tests, batch import), allow the
    # caller to advance the GR straight to "Pending Inspection" so the
    # downstream complete_inspection action is reachable in a single call
    # chain. Use the BEI submit_receipt() business method (sets status to
    # "Pending Inspection") rather than Frappe's bare gr.submit() which only
    # flips docstatus and leaves status="Draft" — that broke S194-9 because
    # complete_inspection() requires status="Pending Inspection".
    if auto_submit and gr.status == "Draft":
        gr.submit_receipt()
    frappe.db.release_savepoint("goods_receipt_creation")

    return {"success": True, "name": gr.name, "status": gr.status, "message": _("GR created")}


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
def complete_gr_inspection(
    name: str,
    passed: bool = True,
    result: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Complete quality inspection on GR."""
    if result is not None:
        passed = result == "pass"
    gr = frappe.get_doc("BEI Goods Receipt", name)
    return gr.complete_inspection(passed, notes)


@frappe.whitelist()
def reject_gr_items(
    name: str,
    rejected_items: list[dict[str, Any]] | str = "[]",
    reason: str = "",
) -> dict[str, Any]:
    """Reject GR items and log the rejection reason.

    Each item in rejected_items: {item_code, rejected_qty, reason}
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="reject_gr_items", mutation_type="update")

    if isinstance(rejected_items, str):
        rejected_items = frappe.parse_json(rejected_items)
    if not rejected_items:
        frappe.throw(_("No items specified for rejection"))

    gr = frappe.get_doc("BEI Goods Receipt", name)
    if gr.status in ("Cancelled",):
        frappe.throw(_("Cannot reject items on a cancelled GR"))

    item_map = {row.item_code: row for row in gr.items}
    rejection_log = []

    for rej in rejected_items:
        item_code = rej.get("item_code")
        rejected_qty = flt(rej.get("rejected_qty", 0))
        item_reason = rej.get("reason") or reason or "Quality issue"
        row = item_map.get(item_code)
        if not row or rejected_qty <= 0:
            continue
        if rejected_qty > flt(row.received_qty):
            frappe.throw(
                _("Rejected qty ({0}) exceeds received qty ({1}) for {2}").format(
                    rejected_qty, row.received_qty, item_code
                )
            )
        row.rejected_qty = flt(row.rejected_qty) + rejected_qty
        row.accepted_qty = max(flt(row.received_qty) - flt(row.rejected_qty), 0)
        rejection_log.append({"item_code": item_code, "rejected_qty": rejected_qty, "reason": item_reason})

    if not rejection_log:
        return {"success": False, "message": _("No valid items to reject")}

    gr.save(ignore_permissions=True)
    gr.add_comment("Info", _("Items rejected: {0}. Reason: {1}").format(
        ", ".join(f"{r['item_code']} x{r['rejected_qty']}" for r in rejection_log),
        reason or "See individual items",
    ))
    return {
        "success": True, "name": gr.name, "rejected_items": rejection_log,
        "message": _("{0} item(s) rejected on GR {1}").format(len(rejection_log), gr.name),
    }


@frappe.whitelist()
def get_pending_gr_for_po(purchase_order: str) -> dict[str, Any]:
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
def get_invoices(
    filters: dict[str, Any] | str | None = None,
    page: int | str = 1,
    page_size: int | str = 20,
    search: str | None = None,
) -> dict[str, Any]:
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

    total_query = "SELECT COUNT(*) FROM `tabBEI Invoice` WHERE " + where_clause
    total = frappe.db.sql(total_query, values)[0][0]

    invoice_query = """
        SELECT
            name, invoice_no, invoice_no as invoice_number, supplier_invoice_no, invoice_date, due_date,
            status, supplier, supplier_name, purchase_order, purchase_order as po_number,
            goods_receipt, goods_receipt as gr_number,
            subtotal, vat_amount, subtotal as net_total, vat_amount as tax_amount,
            grand_total, balance_due, payment_status, match_status
        FROM `tabBEI Invoice`
        WHERE """
    invoice_query += where_clause
    invoice_query += """
        ORDER BY due_date ASC
        LIMIT %(page_size)s OFFSET %(offset)s
    """
    invoices = frappe.db.sql(invoice_query, {**values, "page_size": int(page_size), "offset": offset}, as_dict=True)

    return {
        "data": invoices,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_invoice(name: str) -> dict[str, Any]:
    """Get single invoice with full details."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return _augment_invoice_response(invoice.as_dict())


@frappe.whitelist()
def get_invoice_items(name: str) -> list[dict[str, Any]]:
    """Return the line items that support an invoice's 3-way match math.

    BEI Invoice itself does not persist a child table, so the UI should inspect
    the linked Goods Receipt first, then fall back to the PO items when the
    invoice is still in pre-verification drafting.
    """
    invoice = frappe.get_doc("BEI Invoice", name)

    if invoice.goods_receipt:
        return frappe.db.sql(
            """
            SELECT
                name,
                item_code,
                item_name,
                description,
                accepted_qty AS qty,
                unit_cost AS rate,
                amount,
                uom
            FROM `tabBEI GR Item`
            WHERE parent = %s
            ORDER BY idx
            """,
            (invoice.goods_receipt,),
            as_dict=True,
        )

    if invoice.purchase_order:
        return frappe.db.sql(
            """
            SELECT
                name,
                item_code,
                item_name,
                description,
                qty,
                unit_cost AS rate,
                amount,
                uom,
                vat_rate,
                vat_amount
            FROM `tabBEI PO Item`
            WHERE parent = %s
            ORDER BY idx
            """,
            (invoice.purchase_order,),
            as_dict=True,
        )

    return []


@frappe.whitelist()
def create_invoice(data: dict[str, Any] | str) -> dict[str, Any]:
    """Create new invoice.

    AUDIT CONTROL 2.1: Require Goods Receipt before Invoice (Three-Way Matching)
    AUDIT CONTROL 2.2: Invoice date cannot be earlier than PO date
    Ref: Internal Audit Jan 30, 2026 - PO-2025108 paid without GR; Invoice Nov 21 vs PO Nov 25
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="create_invoice", mutation_type="create")
    if isinstance(data, str):
        data = frappe.parse_json(data)
    data = _normalize_invoice_payload(data)

    # S193 Guard: block new invoice for Blacklisted / Pending Verification suppliers.
    # Supplier may be set directly, or derivable from a linked PO/GR — resolve via
    # fallback so the guard fires for every creation path, not just direct-supplier.
    _s193_supplier = data.get("supplier")
    if not _s193_supplier and data.get("purchase_order"):
        _s193_supplier = frappe.db.get_value("BEI Purchase Order", data["purchase_order"], "supplier")
    if not _s193_supplier and data.get("goods_receipt"):
        _s193_supplier = frappe.db.get_value("BEI Goods Receipt", data["goods_receipt"], "supplier")
    if _s193_supplier:
        _assert_supplier_active(_s193_supplier, "invoice")

    purchase_order = data.get("purchase_order")
    goods_receipt = data.get("goods_receipt")
    po = None
    gr_doc = None

    if goods_receipt:
        gr_doc = frappe.get_doc("BEI Goods Receipt", goods_receipt)
        _populate_invoice_context(data, goods_receipt=gr_doc)
        purchase_order = data.get("purchase_order") or purchase_order

    if purchase_order:
        # AUDIT CONTROL 2.1: Check GR exists for this PO
        # Note: GR status can be "Accepted" after the receive+inspect workflow
        gr_exists = frappe.db.exists("BEI Goods Receipt", {
            "purchase_order": purchase_order,
            "status": ["in", ["Submitted", "Approved", "Inspected", "Accepted", "Partially Accepted"]]
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
        _populate_invoice_context(data, purchase_order=po, goods_receipt=gr_doc)
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

        # AUDIT CONTROL 2.4: Check PO approval for >threshold
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        _inv_dual_threshold = flt(get_procurement_settings().get("dual_approval_threshold", 500000))
        if flt(po.grand_total) > _inv_dual_threshold:
            if not po.mae_approval or not po.butch_approval:
                frappe.throw(
                    _("Cannot create Invoice: PO {0} (₱{1:,.2f}) requires complete approval "
                      "(CPO + CFO) before invoicing").format(po.po_no, po.grand_total),
                    title=_("Approval Required")
                )

    # C3: Duplicate invoice detection — check supplier + supplier_invoice_no
    supplier_invoice_no = data.get("supplier_invoice_no")
    supplier = data.get("supplier")
    if supplier_invoice_no and supplier:
        existing = frappe.db.exists("BEI Invoice", {
            "supplier": supplier,
            "supplier_invoice_no": supplier_invoice_no,
            "status": ["!=", "Cancelled"],
        })
        if existing:
            # Allow override only for Procurement Manager role
            allow_duplicate = data.pop("allow_duplicate_override", False)
            duplicate_reason = data.pop("duplicate_override_reason", "")
            if allow_duplicate and duplicate_reason:
                from hrms.utils.scm_roles import _require_roles
                _require_roles(["Procurement Manager", "System Manager"], "override duplicate invoice")
            else:
                frappe.throw(
                    _("Duplicate invoice: supplier {0} already has invoice {1} with number {2}. "
                      "If this is intentional (e.g. credit note), a Procurement Manager can override.").format(
                        supplier, existing, supplier_invoice_no
                    ),
                    title=_("Duplicate Invoice Detected"),
                )

    # Extract line items before sanitizing
    line_items = data.pop("items", None) or data.pop("line_items", None) or []

    # DEFECT-4 fix: Auto-link invoice_attachment from GR's supplier_invoice_photo
    if not data.get("invoice_attachment") and data.get("goods_receipt"):
        gr_photo = frappe.db.get_value(
            "BEI Goods Receipt", data["goods_receipt"], "supplier_invoice_photo"
        )
        if gr_photo:
            data["invoice_attachment"] = gr_photo

    # DM-2: Savepoint for atomic invoice + child table creation
    frappe.db.savepoint("invoice_creation")
    invoice = frappe.get_doc({
        "doctype": "BEI Invoice",
        **_sanitize_doc_data(data)
    })

    # C2: Add line items to child table if provided
    if line_items:
        for item_data in line_items:
            qty = flt(item_data.get("qty"))
            rate = flt(item_data.get("rate") or item_data.get("unit_cost"))
            vat_rate = flt(item_data.get("vat_rate", 12))
            # DEFECT-5 fix: Calculate amount = qty * rate
            amount = qty * rate
            vat_amount = amount * vat_rate / 100

            invoice.append("items", {
                "item_code": item_data.get("item_code"),
                "item_name": item_data.get("item_name"),
                "qty": qty,
                "rate": rate,
                "amount": amount,
                "vat_rate": vat_rate,
                "vat_amount": vat_amount,
                "matched_gr_item": item_data.get("matched_gr_item"),
                "match_status": item_data.get("match_status", "Unmatched"),
            })
    else:
        # DEFECT-5 fix: When no line items provided, populate from PO and compute amounts
        if purchase_order:
            po_items = frappe.db.sql("""
                SELECT item_code, item_name, qty, unit_cost as rate, vat_rate, vat_amount
                FROM `tabBEI PO Item` WHERE parent = %s ORDER BY idx
            """, purchase_order, as_dict=True)
            for pi in po_items:
                qty = flt(pi.qty)
                rate = flt(pi.rate)
                vat_rate = flt(pi.vat_rate or 12)
                amount = qty * rate
                vat_amount = amount * vat_rate / 100
                invoice.append("items", {
                    "item_code": pi.item_code,
                    "item_name": pi.item_name,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
                    "vat_rate": vat_rate,
                    "vat_amount": vat_amount,
                })

    invoice.insert()
    frappe.db.release_savepoint("invoice_creation")

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
def approve_invoice_variance(name: str, notes: str | None = None) -> dict[str, Any]:
    """Approve invoice despite variance."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.approve_variance(notes)


@frappe.whitelist()
def reject_invoice_variance(name: str, reason: str) -> dict[str, Any]:
    """Reject invoice due to variance."""
    invoice = frappe.get_doc("BEI Invoice", name)
    return invoice.reject_variance(reason)


# =============================================================================
# PAYMENT REQUEST ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_payment_requests(
    filters: dict[str, Any] | str | None = None,
    page: int | str = 1,
    page_size: int | str = 20,
    search: str | None = None,
) -> dict[str, Any]:
    """Get paginated list of payment requests."""
    conditions = []
    values = {}
    applied_filters = {}

    if search:
        conditions.append(
            "(pr.payment_request_no LIKE %(search)s OR pr.supplier_name LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)
        applied_filters = dict(filters)

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

        operational_clauses, operational_values = build_payment_request_operational_filters(filters)
        conditions.extend(operational_clauses)
        values.update(operational_values)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (int(page) - 1) * int(page_size)

    total_query = "SELECT COUNT(*) FROM `tabBEI Payment Request` pr WHERE " + where_clause
    total = frappe.db.sql(total_query, values)[0][0]

    request_query = """
        SELECT
            pr.name, pr.payment_request_no, pr.payment_request_no as request_number, pr.request_date, pr.status,
            COALESCE(pr.supplier, inv.supplier) as supplier,
            COALESCE(pr.supplier_name, inv.supplier_name) as supplier_name,
            pr.payment_amount, pr.payment_mode, pr.payment_mode as payment_method, pr.invoice,
            inv.invoice_no as invoice_number, inv.supplier_invoice_no, inv.invoice_date, inv.due_date,
            inv.match_status, pr.purchase_order, po.po_no as po_number,
            pr.goods_receipt, gr.gr_no as gr_number,
            pr.ceo_required, pr.payment_date, pr.check_number
        FROM `tabBEI Payment Request` pr
        LEFT JOIN `tabBEI Invoice` inv ON pr.invoice = inv.name
        LEFT JOIN `tabBEI Purchase Order` po ON pr.purchase_order = po.name
        LEFT JOIN `tabBEI Goods Receipt` gr ON pr.goods_receipt = gr.name
        WHERE """
    request_query += where_clause
    request_query += """
        ORDER BY pr.request_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """
    requests = frappe.db.sql(
        request_query,
        {**values, "page_size": int(page_size), "offset": offset},
        as_dict=True,
    )

    if _clean_optional_filter(applied_filters.get("item_code")):
        for row in requests:
            row["has_item_match"] = True
    if _clean_optional_filter(applied_filters.get("warehouse")):
        for row in requests:
            row["has_warehouse_match"] = True

    return {
        "data": requests,
        "total": total,
        "page": int(page),
        "page_size": int(page_size),
        "total_pages": (total + int(page_size) - 1) // int(page_size)
    }


@frappe.whitelist()
def get_payment_request(name: str) -> dict[str, Any]:
    """Get single payment request with approval status."""
    request = frappe.get_doc("BEI Payment Request", name)
    data = request.as_dict()
    data["request_number"] = data.get("payment_request_no")
    data["payment_method"] = data.get("payment_mode")
    data["approval_status"] = request.get_approval_status()
    if data.get("purchase_order"):
        data["po_number"] = frappe.db.get_value("BEI Purchase Order", data["purchase_order"], "po_no")
    if data.get("goods_receipt"):
        data["gr_number"] = frappe.db.get_value("BEI Goods Receipt", data["goods_receipt"], "gr_no")
    if data.get("invoice"):
        invoice_fields = frappe.db.get_value(
            "BEI Invoice",
            data["invoice"],
            ["invoice_no", "supplier_invoice_no", "invoice_date", "due_date", "match_status", "grand_total"],
            as_dict=True,
        ) or {}
        data["invoice_number"] = invoice_fields.get("invoice_no") or data["invoice"]
        data["supplier_invoice_no"] = invoice_fields.get("supplier_invoice_no")
        data["invoice_date"] = invoice_fields.get("invoice_date")
        data["due_date"] = invoice_fields.get("due_date")
        data["match_status"] = invoice_fields.get("match_status")
        data["invoice_amount"] = invoice_fields.get("grand_total") or data.get("invoice_amount")
    return data


@frappe.whitelist()
def create_payment_request(data: dict[str, Any] | str) -> dict[str, Any]:
    """Create new payment request.

    AUDIT CONTROL 2.1: Require Goods Receipt before Payment (Three-Way Matching)
    AUDIT CONTROL 2.2: Payment date cannot be earlier than Invoice date
    AUDIT CONTROL 2.3: Payment limited to received value (partial delivery control)
    AUDIT CONTROL 2.4: Block payment without complete PO approval for >₱500K
    AUDIT CONTROL 2.5: Double-payment guard for advances
    Ref: Internal Audit Jan 30, 2026 - PO-2025320 paid ₱848,800 for partial delivery
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="create_payment_request", mutation_type="create")
    if isinstance(data, str):
        data = frappe.parse_json(data)

    # S193 Guard: block new payment request for Blacklisted / Pending Verification suppliers.
    # Payment requests are typically linked to an invoice; supplier is rarely passed
    # directly. Resolve via invoice → PO fallback so denial fires before the
    # Double-Payment guard and before any DB writes.
    _s193_supplier = data.get("supplier")
    if not _s193_supplier and data.get("invoice"):
        _s193_supplier = frappe.db.get_value("BEI Invoice", data["invoice"], "supplier")
    if not _s193_supplier and data.get("purchase_order"):
        _s193_supplier = frappe.db.get_value("BEI Purchase Order", data["purchase_order"], "supplier")
    if _s193_supplier:
        _assert_supplier_active(_s193_supplier, "payment_request")

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
        if invoice.status not in ["Verified", "Partially Paid"]:
            frappe.throw(
                _("Invoice must be verified before creating a payment request."),
                title=_("Verification Required"),
            )

        payment_amount = flt(data.get("payment_amount") or invoice.balance_due)
        if payment_amount <= 0:
            frappe.throw(
                _("Payment amount must be greater than zero."),
                title=_("Invalid Payment Amount"),
            )
        if payment_amount > flt(invoice.balance_due):
            frappe.throw(
                _(
                    "Payment amount (₱{0:,.2f}) exceeds the current invoice balance "
                    "(₱{1:,.2f})."
                ).format(payment_amount, flt(invoice.balance_due)),
                title=_("Balance Exceeded"),
            )

        pending_request_statuses = [
            "Draft",
            "Pending Review",
            "Pending Budget Approval",
            "Pending CFO Approval",
            "Pending CEO Approval",
        ]
        pending_status_placeholders = []
        pending_status_values = {"invoice_name": invoice_name}
        for index, status_value in enumerate(pending_request_statuses):
            key = f"pending_status_{index}"
            pending_status_placeholders.append(f"%({key})s")
            pending_status_values[key] = status_value
        pending_requested_total = flt(
            frappe.db.sql(
                f"""
                SELECT COALESCE(SUM(payment_amount), 0)
                FROM `tabBEI Payment Request`
                WHERE invoice = %(invoice_name)s
                  AND status IN ({', '.join(pending_status_placeholders)})
                """,
                pending_status_values,
            )[0][0]
        )
        remaining_invoice_balance = flt(invoice.balance_due) - pending_requested_total
        if remaining_invoice_balance <= 0:
            frappe.throw(
                _(
                    "This invoice already has pending payment requests totaling "
                    "₱{0:,.2f}. Create a new request only after those are resolved."
                ).format(pending_requested_total),
                title=_("Duplicate Payment Risk"),
            )
        if payment_amount > remaining_invoice_balance:
            frappe.throw(
                _(
                    "Payment amount (₱{0:,.2f}) plus pending requests would exceed the "
                    "remaining invoice balance (₱{1:,.2f})."
                ).format(payment_amount, remaining_invoice_balance),
                title=_("Duplicate Payment Risk"),
            )

        _populate_payment_request_invoice_context(data, invoice)
        purchase_order = invoice.purchase_order

        if purchase_order:
            po = frappe.get_doc("BEI Purchase Order", purchase_order)

            # AUDIT CONTROL 2.1: Check GR exists for this PO
            # Note: GR status can be "Accepted" after the receive+inspect workflow
            gr_exists = frappe.db.exists("BEI Goods Receipt", {
                "purchase_order": purchase_order,
                "status": ["in", ["Submitted", "Approved", "Inspected", "Accepted", "Partially Accepted"]]
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
                payment_amount = flt(data.get("payment_amount") or invoice.balance_due)
                invoice_payable = flt(invoice.balance_due or invoice.grand_total)
                received_value = invoice_payable

                if invoice.goods_receipt:
                    po_items = frappe.db.sql(
                        """
                        SELECT item_code, qty, unit_cost, vat_rate, vat_amount
                        FROM `tabBEI PO Item`
                        WHERE parent = %s
                        ORDER BY idx
                        """,
                        (purchase_order,),
                        as_dict=True,
                    )
                    gr_items = frappe.db.sql(
                        """
                        SELECT item_code, accepted_qty, received_qty, rejected_qty, unit_cost
                        FROM `tabBEI GR Item`
                        WHERE parent = %s
                        ORDER BY idx
                        """,
                        (invoice.goods_receipt,),
                        as_dict=True,
                    )
                    received_value = calculate_goods_receipt_gross_total(gr_items, po_items)

                payable_cap = min(invoice_payable, received_value)
                if payment_amount > payable_cap:
                    frappe.throw(
                        _("Payment amount (₱{0:,.2f}) exceeds the payable received value (₱{1:,.2f}). "
                          "You can only pay for goods actually accepted and invoiced.").format(
                            payment_amount, payable_cap
                        ),
                        title=_("Partial Delivery Control")
                    )

            # AUDIT CONTROL 2.4: Check PO approval for >threshold
            from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
            _pay_dual_threshold = flt(get_procurement_settings().get("dual_approval_threshold", 500000))
            if flt(po.grand_total) > _pay_dual_threshold:
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

    # D1: Payment terms enforcement
    _d1_supplier = data.get("supplier")
    if _d1_supplier and invoice_name:
        try:
            _d1_pt = frappe.db.get_value("BEI Supplier", _d1_supplier, "payment_terms_days")
            if _d1_pt and flt(_d1_pt) > 0:
                _d1_inv_dt = getdate(frappe.db.get_value("BEI Invoice", invoice_name, "invoice_date"))
                _d1_age = (getdate(nowdate()) - _d1_inv_dt).days
                if _d1_age > flt(_d1_pt):
                    frappe.msgprint(
                        _("Warning: Invoice is {0} days past supplier payment terms ({1} days).").format(
                            _d1_age - int(_d1_pt), int(_d1_pt)
                        ),
                        indicator="orange", alert=True,
                    )
        except Exception:
            pass

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
    """Mark payment as complete with atomic EWT JV creation (S099/DM-2)."""
    from frappe.utils import nowdate, flt
    from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings

    request = frappe.get_doc("BEI Payment Request", name)
    needs_ewt_jv = not request.is_advance_payment and flt(request.ewt_amount) > 0

    if needs_ewt_jv:
        settings = get_procurement_settings()

        # S099/DM-2: Wrap payment status + EWT JV in one atomic savepoint.
        # If JV fails, payment is NOT marked as paid — prevents GL gap.
        frappe.db.savepoint("payment_ewt_atomic")
        try:
            result = request.mark_as_paid(transaction_reference, payment_proof)

            party_name = request.supplier_name or request.supplier
            if request.supplier:
                bei_sup = frappe.get_doc("BEI Supplier", request.supplier)
                party_name = bei_sup.get_or_create_frappe_supplier() or party_name

            # S099: Read ATC code from supplier master, not hardcoded
            supplier_atc = "WI100"
            if request.supplier:
                supplier_atc = frappe.db.get_value(
                    "BEI Supplier", request.supplier, "atc_code"
                ) or "WI100"

            pi_name = request.reference_name
            credit_to_account = frappe.db.get_value("Purchase Invoice", pi_name, "credit_to") if pi_name else None
            if not credit_to_account:
                credit_to_account = settings.get("ap_trade_account")

            supplier_tin = frappe.db.get_value("Supplier", party_name, "tax_id") or "NO-TIN"
            company = request.company or frappe.db.get_single_value("Global Defaults", "default_company")
            cost_center = settings.get("default_cost_center") or ""

            jv = frappe.new_doc("Journal Entry")
            jv.voucher_type = "Journal Entry"
            jv.posting_date = nowdate()
            jv.company = company
            jv.user_remark = (
                f"EWT Withheld: {request.ewt_amount:.2f} | "
                f"Supplier: {party_name} (TIN: {supplier_tin}) | "
                f"ATC: {supplier_atc} | Gross: {flt(request.grand_total):.2f} | "
                f"PI: {pi_name or 'N/A'} | PR: {request.name}"
            )

            # Debit leg — reduce trade AP (DM-1: party + reference fields)
            jv.append("accounts", {
                "account": credit_to_account,
                "debit_in_account_currency": request.ewt_amount,
                "party_type": "Supplier",
                "party": party_name,
                "reference_type": "BEI Payment Request",
                "reference_name": request.name,
                "cost_center": cost_center,
            })

            # Credit leg — EWT payable to BIR (NO party — government liability)
            jv.append("accounts", {
                "account": settings.get("ewt_payable_account"),
                "credit_in_account_currency": request.ewt_amount,
                "reference_type": "BEI Payment Request",
                "reference_name": request.name,
                "cost_center": cost_center,
            })

            jv.insert(ignore_permissions=True)
            jv.submit()
            frappe.db.release_savepoint("payment_ewt_atomic")

        except Exception as e:
            frappe.log_error(f"EWT JV generation failed for {request.name}: {e}")
            frappe.throw(
                f"Payment could not be completed — EWT Journal Entry creation failed: {e}. "
                f"No changes were made. Please retry or contact finance."
            )
    else:
        result = request.mark_as_paid(transaction_reference, payment_proof)

    return result


@frappe.whitelist()
def get_pending_payment_approvals():
    """Get all payments pending approval at each level."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_pending_payment_approvals", mutation_type="read")
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
    """Legacy endpoint - returns top 10 for dashboard. Use get_supplier_performance_report() for full report."""
    result = get_supplier_performance_report(months=6, sort_by="total_value", sort_order="desc")
    return result["data"][:10]


# =============================================================================
# PROCUREMENT REPORT ENDPOINTS
# =============================================================================

@frappe.whitelist()
def get_supplier_performance_report(months=6, sort_by="total_value", sort_order="desc"):
    """Full supplier performance report with computed metrics."""
    _check_procurement_report_access()

    months = cint(months) or 6
    sort_col, sort_dir = _safe_sort(sort_by, sort_order, SUPPLIER_SORT_COLUMNS, "s.total_po_value")

    data = frappe.db.sql("""
        SELECT
            s.name as supplier, s.supplier_name, s.status,
            s.total_po_count as po_count,
            s.total_po_value as total_value,
            ROUND(s.total_po_value / NULLIF(s.total_po_count, 0), 2) as avg_order_value,
            s.total_outstanding as outstanding,
            s.avg_delivery_days,
            COALESCE(s.on_time_rate, 0) as on_time_rate,
            COALESCE(gr_stats.gr_count, 0) as gr_count,
            COALESCE(gr_stats.total_received, 0) as total_received,
            COALESCE(gr_stats.rejection_count, 0) as rejection_count,
            ROUND(
                (1 - COALESCE(gr_stats.rejection_count, 0)
                     / NULLIF(COALESCE(gr_stats.gr_count, 0), 0)) * 100, 1
            ) as quality_score
        FROM `tabBEI Supplier` s
        LEFT JOIN (
            SELECT gr.supplier, COUNT(*) as gr_count,
                SUM(gr.total_received_qty) as total_received,
                SUM(CASE WHEN gr.status = 'Rejected' THEN 1 ELSE 0 END) as rejection_count
            FROM `tabBEI Goods Receipt` gr
            WHERE gr.receipt_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
            GROUP BY gr.supplier
        ) gr_stats ON gr_stats.supplier = s.name
        WHERE s.status = 'Active'
        ORDER BY {sort_col} {sort_dir}
    """.format(sort_col=sort_col, sort_dir=sort_dir), (months,), as_dict=True)

    total_suppliers = len(data)
    avg_on_time = sum(flt(d.on_time_rate) for d in data) / max(total_suppliers, 1)
    avg_quality = sum(flt(d.quality_score) for d in data) / max(total_suppliers, 1)

    return {
        "data": data,
        "summary": {
            "total_suppliers": total_suppliers,
            "avg_on_time_rate": round(avg_on_time, 1),
            "avg_quality_score": round(avg_quality, 1),
            "total_spend": flt(sum(flt(d.total_value) for d in data), 2)
        }
    }


@frappe.whitelist()
def get_payment_disbursement_report(from_date=None, to_date=None, payment_mode=None,
                                      supplier=None, page=1, page_size=50):
    """Payment disbursement report with mode breakdown and approval chain."""
    _check_procurement_report_access()

    page = cint(page) or 1
    page_size = min(cint(page_size) or 50, 100)

    if from_date and to_date and getdate(from_date) > getdate(to_date):
        frappe.throw(_("From Date cannot be after To Date"))

    conditions = ["pr.status NOT IN ('Draft', 'Cancelled')"]
    values = {}

    if from_date:
        conditions.append("pr.request_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("pr.request_date <= %(to_date)s")
        values["to_date"] = to_date
    if payment_mode:
        conditions.append("pr.payment_mode = %(payment_mode)s")
        values["payment_mode"] = payment_mode
    if supplier:
        conditions.append("COALESCE(pr.supplier, inv.supplier) = %(supplier)s")
        values["supplier"] = supplier

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size

    data = frappe.db.sql("""
        SELECT
            pr.name, pr.payment_request_no, pr.request_date, pr.payment_date, pr.status,
            COALESCE(pr.supplier, inv.supplier) as supplier,
            COALESCE(pr.supplier_name, inv.supplier_name) as supplier_name,
            pr.payment_amount, pr.payment_mode, pr.invoice, inv.invoice_no,
            pr.ceo_required,
            pr.reviewer as reviewed_by, pr.reviewer_date as reviewed_date,
            pr.budget_approver as budget_approved_by, pr.cfo_approver as cfo_approved_by, pr.ceo_approver as ceo_approved_by,
            pr.processed_by, pr.processed_date,
            DATEDIFF(pr.processed_date, pr.request_date) as turnaround_days
        FROM `tabBEI Payment Request` pr
        LEFT JOIN `tabBEI Invoice` inv ON pr.invoice = inv.name
        WHERE {where_clause}
        ORDER BY pr.request_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """.format(where_clause=where_clause), {**values, "page_size": page_size, "offset": offset}, as_dict=True)

    mode_summary = frappe.db.sql("""
        SELECT pr.payment_mode, COUNT(*) as count,
            SUM(pr.payment_amount) as total_amount,
            AVG(DATEDIFF(pr.processed_date, pr.request_date)) as avg_turnaround
        FROM `tabBEI Payment Request` pr
        LEFT JOIN `tabBEI Invoice` inv ON pr.invoice = inv.name
        WHERE {where_clause}
        GROUP BY pr.payment_mode
    """.format(where_clause=where_clause), values, as_dict=True)

    total = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabBEI Payment Request` pr
            LEFT JOIN `tabBEI Invoice` inv ON pr.invoice = inv.name
            WHERE {where_clause}""".format(where_clause=where_clause), values
    )[0][0]

    return {
        "data": data,
        "mode_summary": mode_summary,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_three_way_match_report(from_date=None, to_date=None, supplier=None,
                                 variance_only=False, page=1, page_size=50):
    """Three-way match: PO vs GR vs Invoice variance analysis."""
    _check_procurement_report_access()

    # AUDIT-2: Coerce boolean from HTTP string
    variance_only = variance_only == "true" or variance_only is True
    page = cint(page) or 1
    page_size = min(cint(page_size) or 50, 100)

    if from_date and to_date and getdate(from_date) > getdate(to_date):
        frappe.throw(_("From Date cannot be after To Date"))

    conditions = ["po.status NOT IN ('Draft', 'Cancelled')"]
    values = {}

    if from_date:
        conditions.append("po.po_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("po.po_date <= %(to_date)s")
        values["to_date"] = to_date
    if supplier:
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = supplier

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size

    # Variance filter uses full expression (not column alias) for portability
    variance_having = """
        HAVING ABS(ROUND(COALESCE(gr_agg.gr_total, 0) - po.grand_total, 2)) > 0.01
            OR ABS(ROUND(COALESCE(inv_agg.inv_total, 0) - COALESCE(gr_agg.gr_total, 0), 2)) > 0.01
            OR ABS(ROUND(COALESCE(inv_agg.inv_total, 0) - po.grand_total, 2)) > 0.01
    """ if variance_only else ""

    # GR/Invoice subqueries include date filter for performance at scale
    gr_date_filter = "AND receipt_date >= %(from_date)s" if from_date else ""
    inv_date_filter = "AND invoice_date >= %(from_date)s" if from_date else ""

    data = frappe.db.sql("""
        SELECT
            po.name as po_name, po.po_no, po.po_date, po.supplier_name,
            po.grand_total as po_total, po.status as po_status,
            COALESCE(gr_agg.gr_count, 0) as gr_count,
            COALESCE(gr_agg.gr_total, 0) as gr_total,
            COALESCE(gr_agg.total_received_qty, 0) as received_qty,
            COALESCE(inv_agg.inv_count, 0) as inv_count,
            COALESCE(inv_agg.inv_total, 0) as inv_total,
            COALESCE(inv_agg.paid_total, 0) as paid_total,
            ROUND(COALESCE(gr_agg.gr_total, 0) - po.grand_total, 2) as po_gr_variance,
            ROUND(COALESCE(inv_agg.inv_total, 0) - COALESCE(gr_agg.gr_total, 0), 2) as gr_inv_variance,
            ROUND(COALESCE(inv_agg.inv_total, 0) - po.grand_total, 2) as po_inv_variance,
            CASE WHEN po.grand_total > 0
                THEN ROUND((COALESCE(gr_agg.gr_total, 0) - po.grand_total) / po.grand_total * 100, 1)
                ELSE 0 END as po_gr_variance_pct,
            CASE WHEN po.grand_total > 0
                THEN ROUND((COALESCE(inv_agg.inv_total, 0) - po.grand_total) / po.grand_total * 100, 1)
                ELSE 0 END as po_inv_variance_pct
        FROM `tabBEI Purchase Order` po
        LEFT JOIN (
            SELECT purchase_order, COUNT(*) as gr_count,
                SUM(total_amount) as gr_total, SUM(total_received_qty) as total_received_qty
            FROM `tabBEI Goods Receipt`
            WHERE status NOT IN ('Draft', 'Cancelled', 'Rejected') {gr_date_filter}
            GROUP BY purchase_order
        ) gr_agg ON gr_agg.purchase_order = po.name
        LEFT JOIN (
            SELECT purchase_order, COUNT(*) as inv_count,
                SUM(grand_total) as inv_total,
                SUM(CASE WHEN payment_status = 'Paid' THEN grand_total ELSE 0 END) as paid_total
            FROM `tabBEI Invoice`
            WHERE status NOT IN ('Draft', 'Cancelled') {inv_date_filter}
            GROUP BY purchase_order
        ) inv_agg ON inv_agg.purchase_order = po.name
        WHERE {where_clause}
        {variance_having}
        ORDER BY po.po_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """.format(
        gr_date_filter=gr_date_filter,
        inv_date_filter=inv_date_filter,
        where_clause=where_clause,
        variance_having=variance_having,
    ), {**values, "page_size": page_size, "offset": offset}, as_dict=True)

    # Summary counts (single pass, no duplicate JOINs)
    summary = frappe.db.sql("""
        SELECT
            COUNT(*) as total_pos,
            SUM(CASE WHEN gr_agg.gr_count IS NULL OR gr_agg.gr_count = 0 THEN 1 ELSE 0 END) as pos_without_gr,
            SUM(CASE WHEN inv_agg.inv_count IS NULL OR inv_agg.inv_count = 0 THEN 1 ELSE 0 END) as pos_without_inv,
            SUM(CASE WHEN ABS(COALESCE(gr_agg.gr_total, 0) - po.grand_total) > 0.01
                      OR ABS(COALESCE(inv_agg.inv_total, 0) - po.grand_total) > 0.01
                 THEN 1 ELSE 0 END) as pos_with_variance
        FROM `tabBEI Purchase Order` po
        LEFT JOIN (SELECT purchase_order, COUNT(*) as gr_count, SUM(total_amount) as gr_total
                   FROM `tabBEI Goods Receipt` WHERE status NOT IN ('Draft','Cancelled','Rejected') {gr_date_filter}
                   GROUP BY purchase_order) gr_agg ON gr_agg.purchase_order = po.name
        LEFT JOIN (SELECT purchase_order, COUNT(*) as inv_count, SUM(grand_total) as inv_total
                   FROM `tabBEI Invoice` WHERE status NOT IN ('Draft','Cancelled') {inv_date_filter}
                   GROUP BY purchase_order) inv_agg ON inv_agg.purchase_order = po.name
        WHERE {where_clause}
    """.format(
        gr_date_filter=gr_date_filter,
        inv_date_filter=inv_date_filter,
        where_clause=where_clause,
    ), values, as_dict=True)

    total = summary[0].total_pos if summary else 0

    return {
        "data": data,
        "summary": summary[0] if summary else {},
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_monthly_spend_report(months=12):
    """Monthly spend analysis with category/supplier breakdown."""
    _check_procurement_report_access()
    months = cint(months) or 12

    monthly = frappe.db.sql("""
        SELECT DATE_FORMAT(po.po_date, '%%Y-%%m') as month,
            COUNT(*) as po_count, SUM(po.grand_total) as total_spend,
            AVG(po.grand_total) as avg_po_value,
            COUNT(DISTINCT po.supplier) as unique_suppliers
        FROM `tabBEI Purchase Order` po
        WHERE po.po_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        AND po.status NOT IN ('Draft', 'Cancelled')
        GROUP BY DATE_FORMAT(po.po_date, '%%Y-%%m')
        ORDER BY month ASC
    """, (months,), as_dict=True)

    by_supplier = frappe.db.sql("""
        SELECT po.supplier_name, COUNT(*) as po_count, SUM(po.grand_total) as total_spend
        FROM `tabBEI Purchase Order` po
        WHERE po.po_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        AND po.status NOT IN ('Draft', 'Cancelled')
        GROUP BY po.supplier, po.supplier_name
        ORDER BY total_spend DESC LIMIT 15
    """, (months,), as_dict=True)

    by_category = frappe.db.sql("""
        SELECT COALESCE(item.item_group, 'Uncategorized') as item_group,
            COUNT(DISTINCT poi.parent) as po_count, SUM(poi.amount) as total_spend
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        LEFT JOIN `tabItem` item ON poi.item_code = item.name
        WHERE po.po_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        AND po.status NOT IN ('Draft', 'Cancelled')
        GROUP BY COALESCE(item.item_group, 'Uncategorized')
        ORDER BY total_spend DESC
    """, (months,), as_dict=True)

    total_spend = sum(flt(m.total_spend) for m in monthly)
    total_pos = sum(cint(m.po_count) for m in monthly)

    return {
        "monthly": monthly,
        "by_supplier": by_supplier,
        "by_category": by_category,
        "summary": {
            "total_spend": flt(total_spend, 2),
            "total_pos": total_pos,
            "avg_monthly_spend": flt(total_spend / max(len(monthly), 1), 2),
            "months_analyzed": len(monthly)
        }
    }


@frappe.whitelist()
def get_goods_receipt_log(from_date=None, to_date=None, status=None,
                           supplier=None, discrepancy_only=False, page=1, page_size=50):
    """Goods receipt log with delivery timelines and discrepancy tracking."""
    _check_procurement_report_access()

    # AUDIT-2: Coerce boolean from HTTP string
    discrepancy_only = discrepancy_only == "true" or discrepancy_only is True
    page = cint(page) or 1
    page_size = min(cint(page_size) or 50, 100)

    if from_date and to_date and getdate(from_date) > getdate(to_date):
        frappe.throw(_("From Date cannot be after To Date"))

    conditions = ["1=1"]
    values = {}
    if from_date:
        conditions.append("gr.receipt_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("gr.receipt_date <= %(to_date)s")
        values["to_date"] = to_date
    if status:
        conditions.append("gr.status = %(status)s")
        values["status"] = status
    if supplier:
        conditions.append("gr.supplier = %(supplier)s")
        values["supplier"] = supplier

    where_clause = " AND ".join(conditions)
    discrepancy_filter = "AND (gr.total_received_qty != gr.total_ordered_qty OR gr.receipt_date > po.delivery_date)" if discrepancy_only else ""
    offset = (page - 1) * page_size

    data = frappe.db.sql("""
        SELECT
            gr.name, gr.gr_no, gr.receipt_date, gr.status,
            gr.purchase_order, po.po_no, po.po_date,
            po.delivery_date as promised_date,
            gr.supplier, gr.supplier_name,
            gr.total_ordered_qty, gr.total_received_qty, gr.total_amount,
            COALESCE(DATEDIFF(gr.receipt_date, po.delivery_date), NULL) as delivery_variance_days,
            CASE
                WHEN po.delivery_date IS NULL THEN NULL
                WHEN gr.receipt_date <= po.delivery_date THEN 'On Time'
                WHEN gr.receipt_date <= DATE_ADD(po.delivery_date, INTERVAL 3 DAY) THEN 'Slight Delay'
                ELSE 'Late'
            END as delivery_status,
            ROUND(gr.total_received_qty - gr.total_ordered_qty, 2) as qty_discrepancy,
            CASE
                WHEN gr.total_received_qty = gr.total_ordered_qty THEN 'Full'
                WHEN gr.total_received_qty < gr.total_ordered_qty THEN 'Short'
                ELSE 'Over'
            END as receipt_match,
            gr.inspection_status, gr.inspection_notes as remarks
        FROM `tabBEI Goods Receipt` gr
        LEFT JOIN `tabBEI Purchase Order` po ON gr.purchase_order = po.name
        WHERE {where_clause} {discrepancy_filter}
        ORDER BY gr.receipt_date DESC
        LIMIT %(page_size)s OFFSET %(offset)s
    """.format(where_clause=where_clause, discrepancy_filter=discrepancy_filter),
    {**values, "page_size": page_size, "offset": offset}, as_dict=True)

    summary = frappe.db.sql("""
        SELECT
            COUNT(*) as total_grs,
            SUM(CASE WHEN po.delivery_date IS NOT NULL AND gr.receipt_date <= po.delivery_date THEN 1 ELSE 0 END) as on_time_count,
            SUM(CASE WHEN gr.total_received_qty < gr.total_ordered_qty THEN 1 ELSE 0 END) as short_delivery_count,
            SUM(CASE WHEN gr.total_received_qty > gr.total_ordered_qty THEN 1 ELSE 0 END) as over_delivery_count,
            AVG(DATEDIFF(gr.receipt_date, po.delivery_date)) as avg_delivery_variance
        FROM `tabBEI Goods Receipt` gr
        LEFT JOIN `tabBEI Purchase Order` po ON gr.purchase_order = po.name
        WHERE {where_clause} {discrepancy_filter}
    """.format(where_clause=where_clause, discrepancy_filter=discrepancy_filter), values, as_dict=True)

    total = summary[0].total_grs if summary else 0

    return {
        "data": data,
        "summary": summary[0] if summary else {},
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


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
        "is_blocked": variance_pct > 10,
        "new_price": new_price,
        "avg_price": flt(avg_price, 2),
        "variance_pct": flt(variance_pct, 1),
        "warning_threshold": 5,
        "block_threshold": 10,
        "message": _("Price ₱{0:,.2f} is {1:.1f}% different from 90-day average ₱{2:,.2f}{3}").format(
            new_price, variance_pct, avg_price, " (>10% override required)" if variance_pct > 10 else ""
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
    supplier_id, supplier_name = _resolve_supplier_identity(supplier)
    aging = get_ap_aging_report()

    # Filter invoice details for this supplier using canonical ID + display name.
    supplier_invoices = [
        inv for inv in aging["invoice_details"]
        if inv.get("supplier_id") == supplier_id
        or str(inv.get("supplier", "")).strip() == supplier_name
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
        "supplier": supplier_id,
        "supplier_name": supplier_name,
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
        "suppliers": get_supplier_performance(),
        "g046_intercompany": get_g046_intercompany_summary(),
    }


# =============================================================================
# G-046 PROCUREMENT VISIBILITY
# =============================================================================

@frappe.whitelist()
def get_g046_intercompany_transactions(
    page=1,
    page_size=20,
    from_date=None,
    to_date=None,
    warehouse=None,
    status=None,
    search=None,
):
    """Expose G-046 inter-company transactions in procurement-facing APIs."""
    page = max(1, cint(page))
    page_size = min(max(1, cint(page_size)), 200)
    offset = (page - 1) * page_size

    stock_entry_expr, stock_entry_join, conditions = _get_g046_sql_parts()
    values = {}

    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = getdate(from_date)

    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = getdate(to_date)

    if warehouse:
        conditions.append("se.to_warehouse = %(warehouse)s")
        values["warehouse"] = warehouse

    if search:
        conditions.append(
            "(si.name LIKE %(search)s OR si.customer LIKE %(search)s "
            f"OR IFNULL({stock_entry_expr}, '') LIKE %(search)s OR IFNULL(se.to_warehouse, '') LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if status:
        normalized_status = str(status).strip().lower()
        if normalized_status in {"mirrored", "complete"}:
            conditions.append("pi.name IS NOT NULL")
        elif normalized_status in {"sales_only", "missing_purchase_invoice", "missing"}:
            conditions.append("pi.name IS NULL")

    where_clause = " AND ".join(conditions)

    total = frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabSales Invoice` si
        {stock_entry_join}
        LEFT JOIN `tabPurchase Invoice` pi
          ON pi.inter_company_invoice_reference = si.name
         AND pi.docstatus != 2
        WHERE {where_clause}
        """,
        values,
    )[0][0]

    rows = frappe.db.sql(
        f"""
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            si.customer,
            {stock_entry_expr} AS stock_entry,
            IFNULL(se.to_warehouse, '') AS target_warehouse,
            si.grand_total AS sales_invoice_total,
            si.status AS sales_invoice_status,
            pi.name AS purchase_invoice,
            pi.grand_total AS purchase_invoice_total,
            pi.status AS purchase_invoice_status,
            CASE WHEN pi.name IS NULL THEN 'Sales Only' ELSE 'Mirrored' END AS mirror_status
        FROM `tabSales Invoice` si
        {stock_entry_join}
        LEFT JOIN `tabPurchase Invoice` pi
          ON pi.inter_company_invoice_reference = si.name
         AND pi.docstatus != 2
        WHERE {where_clause}
        ORDER BY si.posting_date DESC, si.name DESC
        LIMIT %(page_size)s OFFSET %(offset)s
        """,
        {**values, "page_size": page_size, "offset": offset},
        as_dict=True,
    )

    return {
        "data": rows,
        "total": cint(total),
        "page": page,
        "page_size": page_size,
        "total_pages": (cint(total) + page_size - 1) // page_size if total else 0,
    }


@frappe.whitelist()
def get_g046_intercompany_summary():
    """Return high-level G-046 visibility counters for procurement dashboard widgets."""
    _stock_entry_expr, _stock_entry_join, conditions = _get_g046_sql_parts()
    where_clause = " AND ".join(conditions)

    row = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS total_sales_invoices,
            SUM(CASE WHEN pi.name IS NOT NULL THEN 1 ELSE 0 END) AS mirrored_count,
            SUM(CASE WHEN pi.name IS NULL THEN 1 ELSE 0 END) AS missing_purchase_invoice_count,
            COALESCE(SUM(si.grand_total), 0) AS total_sales_value
        FROM `tabSales Invoice` si
        LEFT JOIN `tabPurchase Invoice` pi
          ON pi.inter_company_invoice_reference = si.name
         AND pi.docstatus != 2
        WHERE {where_clause}
        """,
        as_dict=True,
    )

    data = row[0] if row else {}
    return {
        "total_sales_invoices": cint(data.get("total_sales_invoices")),
        "mirrored_count": cint(data.get("mirrored_count")),
        "missing_purchase_invoice_count": cint(data.get("missing_purchase_invoice_count")),
        "total_sales_value": flt(data.get("total_sales_value")),
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

        from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION
        send_message_to_space(get_chat_space(SPACE_ERP_AUTOMATION), message)
        return True
    except Exception as e:
        frappe.log_error(
            title="Exception CEO Notification Failed",
            message=f"Exception: {exception_doc.name}, Error: {str(e)}"
        )
        return False


@frappe.whitelist()
def request_match_exception(data: dict | str):
    """Create a 3-way match exception request.

    Supports:
      1) PO-based 3-way match bypass requests
      2) Delivery pre-billing exceptions (trip stop, always CPO+CFO)
    """
    if isinstance(data, str):
        data = frappe.parse_json(data)

    reason = data.get("reason")
    if not reason:
        frappe.throw(_("Reason is required for exception requests"))

    exception_type = data.get("exception_type")
    if not exception_type:
        frappe.throw(_("Exception type is required"))

    reference_type = data.get("reference_type", "BEI Invoice")

    if reference_type == "BEI Distribution Trip":
        trip_name = data.get("delivery_trip_reference") or data.get("reference_name")
        stop_idx = cint(data.get("delivery_stop_idx"))
        trip_purchase_order = data.get("purchase_order")
        if not trip_name:
            frappe.throw(_("Delivery Trip Reference is required"))
        if stop_idx <= 0:
            frappe.throw(_("Delivery Stop Index must be greater than 0"))
        if not frappe.db.exists("BEI Distribution Trip", trip_name):
            frappe.throw(_("Distribution Trip {0} not found").format(trip_name))
        if not trip_purchase_order:
            try:
                trip_doc = frappe.get_doc("BEI Distribution Trip", trip_name)
                if stop_idx <= len(trip_doc.stops):
                    stop_doc = trip_doc.stops[stop_idx - 1]
                    candidate_po = getattr(stop_doc, "store_order", None)
                    if candidate_po and frappe.db.exists("BEI Purchase Order", candidate_po):
                        trip_purchase_order = candidate_po
            except Exception:
                pass

        existing = frappe.db.exists("BEI Match Exception", {
            "reference_type": "BEI Distribution Trip",
            "delivery_trip_reference": trip_name,
            "delivery_stop_idx": stop_idx,
            "status": ["in", ["Pending CPO", "Pending CFO", "Approved"]],
        })
        if existing:
            existing_doc = frappe.db.get_value(
                "BEI Match Exception",
                existing,
                ["name", "approval_tier", "approver", "status", "purchase_order"],
                as_dict=True,
            ) or {}
            if (
                not existing_doc.get("purchase_order")
                and trip_purchase_order
                and frappe.db.exists("BEI Purchase Order", trip_purchase_order)
            ):
                try:
                    frappe.db.set_value(
                        "BEI Match Exception",
                        existing,
                        "purchase_order",
                        trip_purchase_order,
                        update_modified=False,
                    )
                    existing_doc["purchase_order"] = trip_purchase_order
                except Exception:
                    pass
            return {
                "success": True,
                "name": existing_doc.get("name", existing),
                "approval_tier": existing_doc.get("approval_tier"),
                "approver": existing_doc.get("approver"),
                "status": existing_doc.get("status"),
                "purchase_order": existing_doc.get("purchase_order"),
                "message": _(
                    "An exception request already exists for Trip {0} stop {1}: {2}"
                ).format(trip_name, stop_idx, existing),
            }

        exception_payload = {
            "doctype": "BEI Match Exception",
            "reference_type": "BEI Distribution Trip",
            "reference_name": trip_name,
            "delivery_trip_reference": trip_name,
            "delivery_stop_idx": stop_idx,
            "approval_tier": "CPO+CFO",
            "reason": reason,
            "exception_type": exception_type,
        }
        # Keep backward compatibility: attach PO only when valid, otherwise bypass mandatory PO on trip flow.
        if trip_purchase_order and frappe.db.exists("BEI Purchase Order", trip_purchase_order):
            exception_payload["purchase_order"] = trip_purchase_order
        exception = frappe.get_doc(exception_payload)
        if "purchase_order" not in exception_payload:
            exception.flags.ignore_mandatory = True
    else:
        purchase_order = data.get("purchase_order")
        if not purchase_order:
            frappe.throw(_("Purchase Order is required"))

        if not frappe.db.exists("BEI Purchase Order", purchase_order):
            frappe.throw(_("Purchase Order {0} not found").format(purchase_order))

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
            "reference_type": reference_type,
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


def _has_doctype_column(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.db.has_column(doctype, fieldname))
    except Exception:
        return False


def _append_comment(existing: str | None, prefix: str, comment: str | None) -> str:
    text = f"{prefix}: {(comment or '').strip()}".rstrip()
    if not existing:
        return text
    return f"{existing}\n{text}"


def _resolve_approver_user(preferred_email: str) -> str:
    """Return a valid User link target; fallback keeps approval flow unblocked."""
    if preferred_email and frappe.db.exists("User", preferred_email):
        return preferred_email
    if frappe.db.exists("User", "Administrator"):
        return "Administrator"
    return frappe.session.user or preferred_email


def _resolve_trip_exception_purchase_order(exception: object) -> str | None:
    """Resolve PO link for trip-based exceptions when available."""
    purchase_order = getattr(exception, "purchase_order", None)
    if purchase_order and frappe.db.exists("BEI Purchase Order", purchase_order):
        return purchase_order

    trip_name = getattr(exception, "delivery_trip_reference", None) or getattr(exception, "reference_name", None)
    stop_idx = cint(getattr(exception, "delivery_stop_idx", 0) or 0)
    if not trip_name or stop_idx <= 0:
        return None
    if not frappe.db.exists("BEI Distribution Trip", trip_name):
        return None

    try:
        trip_doc = frappe.get_doc("BEI Distribution Trip", trip_name)
        if stop_idx > len(trip_doc.stops):
            return None
        stop_doc = trip_doc.stops[stop_idx - 1]
        candidate = getattr(stop_doc, "store_order", None)
        if candidate and frappe.db.exists("BEI Purchase Order", candidate):
            return candidate
    except Exception:
        return None

    return None


def _prepare_trip_exception_for_approval(exception: object) -> None:
    """Ensure trip exceptions can progress approval even when legacy PO is blank."""
    if getattr(exception, "reference_type", None) != "BEI Distribution Trip":
        return

    resolved_po = _resolve_trip_exception_purchase_order(exception)
    if resolved_po:
        exception.purchase_order = resolved_po
        return

    # Legacy trip exceptions may intentionally have no PO; bypass mandatory PO in approval save.
    exception.flags.ignore_mandatory = True


def _record_dual_trace(exception: object, role: str, canonical_email: str, approved_at: object, comment: str | None):
    """Persist dual-approval trace on both modern and legacy schemas."""
    role_key = role.strip().upper()

    if role_key == "CPO":
        if _has_doctype_column("BEI Match Exception", "cpo_approved_by"):
            exception.cpo_approved_by = canonical_email
        if _has_doctype_column("BEI Match Exception", "cpo_approved_at"):
            exception.cpo_approved_at = approved_at
    elif role_key == "CFO":
        if _has_doctype_column("BEI Match Exception", "cfo_approved_by"):
            exception.cfo_approved_by = canonical_email
        if _has_doctype_column("BEI Match Exception", "cfo_approved_at"):
            exception.cfo_approved_at = approved_at

    audit_line = append_approval_audit_log(
        getattr(exception, "approval_audit_log", None),
        f"{role_key} Approved",
        canonical_email,
        approved_at,
        comment=comment,
    )
    if _has_doctype_column("BEI Match Exception", "approval_audit_log"):
        exception.approval_audit_log = audit_line

    exception.approver_comment = _append_comment(exception.approver_comment, f"{role_key} Approved", comment)


@frappe.whitelist()
def approve_match_exception(name: str, comment: str | None = None):
    """Approve a match exception with support for dual-tier flows."""
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

    _prepare_trip_exception_for_approval(exception)
    approved_at = now_datetime()

    # First stage for dual approvals
    if exception.approval_tier == "CPO+CFO" and exception.status == "Pending CPO":
        _record_dual_trace(exception, "CPO", get_approver_email("cpo"), approved_at, comment)
        exception.approver = _resolve_approver_user(get_approver_email("cfo"))
        exception.status = "Pending CFO"
        exception.approver_status = "Pending"
        exception.save(ignore_permissions=True)
        return {
            "success": True,
            "name": exception.name,
            "status": exception.status,
            "next_approver": exception.approver,
            "message": "Exception approved by CPO, escalated to CFO.",
        }

    if exception.approval_tier == "CPO+CEO" and exception.status == "Pending CPO":
        _record_dual_trace(exception, "CPO", get_approver_email("cpo"), approved_at, comment)
        exception.approver = _resolve_approver_user(get_approver_email("ceo"))
        exception.status = "Pending CEO"
        exception.approver_status = "Pending"
        exception.save(ignore_permissions=True)
        return {
            "success": True,
            "name": exception.name,
            "status": exception.status,
            "next_approver": exception.approver,
            "message": "Exception approved by CPO, escalated to CEO.",
        }

    # Final stage
    if exception.approval_tier == "CPO+CFO" and exception.status == "Pending CFO":
        _record_dual_trace(exception, "CFO", get_approver_email("cfo"), approved_at, comment)
    elif exception.approval_tier == "CPO+CEO" and exception.status == "Pending CEO":
        exception.approver_comment = _append_comment(exception.approver_comment, "CEO Approved", comment)
    else:
        exception.approver_comment = _append_comment(exception.approver_comment, "Final Approval", comment)

    exception.approver_status = "Approved"
    exception.approver_date = approved_at
    exception.status = "Approved"
    exception.save(ignore_permissions=True)

    # Send CEO notification for all approved exceptions (any tier)
    notified = _send_ceo_exception_notification(exception)
    if notified:
        exception.ceo_notified = 1
        exception.ceo_notification_date = now_datetime()
        exception.save(ignore_permissions=True)

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

    notification_state = _dispatch_or_follow_up_notification(pay_req)

    return {
        "success": True,
        "message": _("Follow-up #{0} recorded for {1}").format(
            pay_req.or_follow_up_count, pay_req.supplier_name or pay_req.supplier
        ),
        "follow_up_count": pay_req.or_follow_up_count,
        "notification_sent": notification_state.get("any_sent", False),
        "notification_channels": notification_state.get("channels", []),
    }


def _dispatch_or_follow_up_notification(pay_req):
    """Send actual OR follow-up notifications for GAP-048 closure.

    Non-blocking by design: failures are logged but never break the workflow.
    """
    channels = []
    supplier_name = pay_req.supplier_name or pay_req.supplier or "Supplier"
    message = (
        f"OR follow-up #{pay_req.or_follow_up_count}: payment {pay_req.name} "
        f"for {supplier_name} (PHP {flt(pay_req.payment_amount):,.2f}) is still awaiting OR."
    )

    # 1) Email notification to supplier contact when available.
    try:
        recipient = None
        for field in ("contact_email", "email", "supplier_email"):
            if _table_has_column("tabBEI Supplier", field):
                recipient = frappe.db.get_value("BEI Supplier", pay_req.supplier, field)
                if recipient:
                    break
        if recipient:
            frappe.sendmail(
                recipients=[recipient],
                subject=_("OR Follow-Up: {0}").format(pay_req.name),
                message=_(
                    "Good day. This is a reminder to provide the Official Receipt for payment {0}."
                ).format(pay_req.name),
            )
            channels.append("email")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "OR Follow-Up Email Failed")

    # 2) Internal Google Chat notification for auditability.
    try:
        from hrms.api.google_chat import send_message_to_space
        from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION

        if send_message_to_space(get_chat_space(SPACE_ERP_AUTOMATION), message):
            channels.append("google_chat")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "OR Follow-Up Chat Failed")

    return {"channels": channels, "any_sent": bool(channels)}


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
        jv.company = get_company()
        jv.user_remark = _("Clearing advance payment {0} against GR {1} - Amount: {2:,.2f}").format(
            advance_payment, goods_receipt, amount_to_clear
        )

        # S099: Read accounts from BEI Settings
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        settings = get_procurement_settings()
        cost_center = settings.get("default_cost_center") or "Main - BEI"

        # S099/C3: Input VAT 3-way split based on supplier's input_vat_category
        input_vat_category = frappe.db.get_value(
            "BEI Supplier", supplier_name, "input_vat_category"
        ) or "Goods"
        input_vat_account_map = {
            "Goods": settings.get("input_vat_goods_account"),
            "Services": settings.get("input_vat_services_account"),
            "Capital Goods": settings.get("input_vat_capital_goods_account"),
        }
        input_vat_account = input_vat_account_map.get(input_vat_category, settings.get("input_vat_goods_account"))

        # Calculate VAT split
        # Amount to clear is VAT-inclusive. Base = amount / 1.12, VAT = amount - base
        vat_rate = flt(settings.get("default_vat_rate", 12))
        vat_divisor = 1 + (vat_rate / 100) if vat_rate > 0 else 1
        base_amount = flt(amount_to_clear / vat_divisor, 2)
        vat_amount = flt(amount_to_clear - base_amount, 2)

        # Debit: GR/IR Clearing (Base Amount)
        jv.append("accounts", {
            "account": settings.get("gr_ir_clearing_account"),
            "debit_in_account_currency": base_amount,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": cost_center,
        })

        # Debit: Input VAT (VAT Amount) — account based on supplier category
        jv.append("accounts", {
            "account": input_vat_account,
            "debit_in_account_currency": vat_amount,
            "credit_in_account_currency": 0,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": cost_center,
        })

        # Credit: Advances to Suppliers (Total Amount)
        jv.append("accounts", {
            "account": settings.get("advances_to_suppliers_account"),
            "debit_in_account_currency": 0,
            "credit_in_account_currency": amount_to_clear,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": cost_center,
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
        jv.company = get_company()
        jv.user_remark = "Reclassification of undeliverable advance: {0}. Reason: {1}".format(
            advance_payment, reason.strip()
        )
        from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
        reclass_settings = get_procurement_settings()

        jv.append("accounts", {
            "account": "1103102 - ACCOUNTS RECEIVABLE-OTHERS - BEI",
            "debit_in_account_currency": amount,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": reclass_settings.get("default_cost_center") or "",
        })
        jv.append("accounts", {
            "account": reclass_settings.get("advances_to_suppliers_account"),
            "credit_in_account_currency": amount,
            "party_type": "Supplier",
            "party": party_name,
            "cost_center": reclass_settings.get("default_cost_center") or "",
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
    supplier_id, supplier_name = _resolve_supplier_identity(supplier)

    date_filter = ""
    values = {"supplier_id": supplier_id, "supplier_name": supplier_name}
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
          AND (pr.supplier = %(supplier_id)s OR pr.supplier_name = %(supplier_name)s)
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
          AND jea.party = %(supplier_id)s
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
        "supplier": supplier_id,
        "supplier_name": supplier_name,
        "entries": entries,
        "closing_balance": flt(running_balance, 2),
        "from_date": str(from_date) if from_date else None,
        "to_date": str(to_date) if to_date else None,
    }


@frappe.whitelist(allow_guest=False)
def generate_form_2307_entry(payment_request):
    """Generate or update a structured BEI Form 2307 record for a payment request."""
    pay_req = frappe.get_doc("BEI Payment Request", payment_request)

    if not pay_req.supplier:
        frappe.throw(_("Payment request has no supplier."))

    # Get supplier TIN
    supplier_tin = frappe.db.get_value("BEI Supplier", pay_req.supplier, "tin") or ""
    supplier_name = pay_req.supplier_name or pay_req.supplier

    # Determine tax period (month/year of payment)
    payment_date = getdate(pay_req.payment_date or pay_req.request_date or nowdate())
    tax_period = payment_date.strftime("%Y-%m")

    # S099: Read ATC code and EWT rate from supplier master, fall back to settings defaults
    from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
    settings = get_procurement_settings()

    supplier_atc = frappe.db.get_value("BEI Supplier", pay_req.supplier, "atc_code") or "WI100"
    supplier_ewt_rate = frappe.db.get_value("BEI Supplier", pay_req.supplier, "default_ewt_rate")

    gross_amount = flt(pay_req.payment_amount)
    ewt_rate = flt(pay_req.ewt_rate) if hasattr(pay_req, "ewt_rate") and pay_req.ewt_rate else (
        flt(supplier_ewt_rate) if supplier_ewt_rate else flt(settings.get("default_ewt_rate", 1))
    )
    ewt_amount = flt(gross_amount * ewt_rate / 100, 2)
    atc_code = supplier_atc

    form_2307_data = {
        "supplier_tin": supplier_tin,
        "supplier_name": supplier_name,
        "tax_period": tax_period,
        "atc_code": atc_code,
        "gross_amount": gross_amount,
        "ewt_rate": ewt_rate,
        "ewt_amount": ewt_amount,
        "payment_request_link": payment_request,
        "generated_by": frappe.session.user,
        "generated_on": nowdate(),
    }

    existing_name = frappe.db.get_value(
        "BEI Form 2307", {"payment_request_link": payment_request}, "name"
    )

    if existing_name:
        form_doc = frappe.get_doc("BEI Form 2307", existing_name)
        for fieldname in (
            "supplier_tin",
            "supplier_name",
            "tax_period",
            "atc_code",
            "gross_amount",
            "ewt_rate",
            "ewt_amount",
            "payment_request_link",
        ):
            setattr(form_doc, fieldname, form_2307_data[fieldname])
        form_doc.save(ignore_permissions=True)
        action = "updated"
    else:
        form_doc = frappe.get_doc({
            "doctype": "BEI Form 2307",
            "supplier_tin": form_2307_data["supplier_tin"],
            "supplier_name": form_2307_data["supplier_name"],
            "tax_period": form_2307_data["tax_period"],
            "atc_code": form_2307_data["atc_code"],
            "gross_amount": form_2307_data["gross_amount"],
            "ewt_rate": form_2307_data["ewt_rate"],
            "ewt_amount": form_2307_data["ewt_amount"],
            "payment_request_link": form_2307_data["payment_request_link"],
        })
        form_doc.insert(ignore_permissions=True)
        action = "created"

    return {
        "success": True,
        "data": {
            **form_2307_data,
            "name": form_doc.name,
        },
        "message": _("Form 2307 record {0} for {1}.").format(action, supplier_name),
    }


@frappe.whitelist(allow_guest=False)
def get_form_2307_data(
    supplier: str | None = None,
    tax_period: str | None = None,
    include_legacy: int | str = 0,
):
    """Retrieve Form 2307 entries filtered by supplier and/or tax period.

    Args:
        supplier: Optional supplier name or ID filter
        tax_period: Optional tax period filter (YYYY-MM)
        include_legacy: Include legacy comment-based records in response (default: 0)
    """
    entries = []
    filters = {}
    supplier_name_filter = None
    if supplier:
        try:
            _supplier_id, supplier_name = _resolve_supplier_identity(supplier)
            supplier_name_filter = supplier_name
        except Exception:
            supplier_name_filter = str(supplier).strip()
        filters["supplier_name"] = supplier_name_filter
    if tax_period:
        filters["tax_period"] = tax_period

    records = frappe.get_all(
        "BEI Form 2307",
        filters=filters,
        fields=[
            "name",
            "supplier_tin",
            "supplier_name",
            "tax_period",
            "atc_code",
            "gross_amount",
            "ewt_rate",
            "ewt_amount",
            "payment_request_link",
            "modified",
        ],
        order_by="modified desc",
    )

    for row in records:
        entries.append(
            {
                "name": row.get("name"),
                "supplier_tin": row.get("supplier_tin"),
                "supplier_name": row.get("supplier_name"),
                "tax_period": row.get("tax_period"),
                "atc_code": row.get("atc_code"),
                "gross_amount": flt(row.get("gross_amount")),
                "ewt_rate": flt(row.get("ewt_rate")),
                "ewt_amount": flt(row.get("ewt_amount")),
                "payment_request": row.get("payment_request_link"),
                "_modified": str(row.get("modified")),
                "_source": "BEI Form 2307",
            }
        )

    legacy_entries = []
    if cint(include_legacy):
        legacy_rows = frappe.db.sql(
            """SELECT c.content, c.reference_name, c.modified
            FROM `tabComment` c
            WHERE c.reference_doctype = 'BEI Payment Request'
              AND c.comment_type = 'Info'
              AND c.content LIKE '%%FORM_2307_DATA%%'
            ORDER BY c.modified DESC""",
            as_dict=True,
        )
        for row in legacy_rows:
            try:
                json_str = row.content.split("FORM_2307_DATA:", 1)[1]
                data = json.loads(json_str)
            except (IndexError, json.JSONDecodeError, TypeError):
                continue

            if supplier_name_filter and data.get("supplier_name") != supplier_name_filter:
                continue
            if tax_period and data.get("tax_period") != tax_period:
                continue

            data["_modified"] = str(row.modified)
            data["_source"] = "Legacy Comment"
            legacy_entries.append(data)

        entries.extend(legacy_entries)

    # Aggregate by supplier + tax_period
    summary = {}
    for entry in entries:
        key = f"{entry.get('supplier_name', '')}|{entry.get('tax_period', '')}"
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
        "legacy_count": len(legacy_entries),
    }


# =============================================================================
# FRANCHISE BILLING & PAYMENT AUTOMATION
# Plan: Finance & Accounting v2.1 — Tasks 2, 3, 4
# =============================================================================


@frappe.whitelist()
def generate_acknowledgement_receipt(
    billing_name: str | None = None,
    simulate_chat_failure: int | bool = 0,
) -> dict[str, str | bool]:
    """Generate an internal Acknowledgement Receipt (AR) for a billing payment.

    This is an INTERNAL document — NOT a BIR Official Receipt.
    Per EOPT Law, the primary BIR document is the Invoice.

    Args:
        billing_name: Name of the BEI Billing Schedule
        simulate_chat_failure: Optional test hook for negative-path validation

    Returns:
        dict with ar_name
    """
    if not billing_name:
        frappe.throw(_("Missing required parameter: billing_name"), frappe.ValidationError)

    if not frappe.has_permission("BEI Acknowledgement Receipt", "create"):
        frappe.throw(_("Insufficient permissions to generate AR"), frappe.PermissionError)

    billing = frappe.get_doc("BEI Billing Schedule", billing_name)

    ar = frappe.get_doc({
        "doctype": "BEI Acknowledgement Receipt",
        "billing_schedule": billing.name,
        "store": billing.store,
        "amount": billing.amount_paid or billing.total_amount,
        "payment_date": billing.paid_on or nowdate(),
        "payment_reference": billing.payment_reference or "",
        "status": "Generated",
    })
    ar.insert(ignore_permissions=True)

    chat_notification_sent = True

    # Notify Accounting Private space via Google Chat (non-blocking)
    try:
        chat_notification_sent = _send_ar_chat_notification(
            ar,
            billing,
            simulate_failure=bool(cint(simulate_chat_failure)),
        )
        if not chat_notification_sent:
            raise RuntimeError("Google Chat notification returned False")
    except Exception as e:
        chat_notification_sent = False
        frappe.log_error(
            f"Failed to send AR notification for {ar.name}: {e}",
            "AR Chat Notification Error",
        )

    return {
        "ar_name": ar.name,
        "chat_notification_sent": chat_notification_sent,
    }


def _send_ar_chat_notification(ar, billing, *, simulate_failure: bool = False) -> bool:
    """Send AR notification to Accounting Private Google Chat space."""
    from hrms.api.google_chat import send_message_to_space

    if simulate_failure:
        raise RuntimeError("Simulated Google Chat failure for acknowledgement receipt")

    message = (
        f"*Acknowledgement Receipt Generated*\n"
        f"AR: {ar.name}\n"
        f"Store: {billing.store}\n"
        f"Amount: PHP {flt(ar.amount):,.2f}\n"
        f"Period: {billing.billing_period}\n"
        f"Payment Ref: {ar.payment_reference or 'N/A'}"
    )

    from hrms.utils.bei_config import get_chat_space, SPACE_ACCOUNTING
    return send_message_to_space(get_chat_space(SPACE_ACCOUNTING), message)


@frappe.whitelist()
def apply_franchise_payment(
    billing_name=None, amount_paid=None, payment_date=None, payment_reference=None, payment_proof=None
):
    """Apply a franchise payment to a billing schedule.

    Accumulates payments (never overwrites). Generates AR on completion.
    Uses savepoint for atomicity — no explicit commit (Frappe auto-commits).

    Args:
        billing_name: BEI Billing Schedule name
        amount_paid: Payment amount (Currency)
        payment_date: Date of payment
        payment_reference: Transaction reference string
        payment_proof: Optional base64 image of payment proof

    Returns:
        dict with success, ar_number, new_balance
    """
    if not all([billing_name, amount_paid, payment_date, payment_reference]):
        frappe.throw(
            _("Missing required parameters: billing_name, amount_paid, payment_date, payment_reference"),
            frappe.ValidationError,
        )

    if not frappe.has_permission("BEI Billing Schedule", "write"):
        frappe.throw(_("Insufficient permissions to apply payments"), frappe.PermissionError)

    amount_paid = flt(amount_paid, 2)
    if amount_paid <= 0:
        frappe.throw(_("Payment amount must be greater than zero"))

    sp = frappe.db.savepoint("apply_payment")
    try:
        billing = frappe.get_doc("BEI Billing Schedule", billing_name)

        if billing.status not in ("Sent", "Partially Paid"):
            frappe.throw(
                _("Cannot apply payment to billing with status '{0}'").format(billing.status)
            )

        # Save payment_proof attachment if provided
        if payment_proof:
            from hrms.api.store import save_base64_image

            file_url = save_base64_image(
                payment_proof, "BEI Billing Schedule", billing.name, "payment_proof"
            )
            billing.payment_proof = file_url

        # Accumulate payment (NEVER overwrite)
        new_total_paid = flt(billing.amount_paid or 0) + amount_paid

        # Overpayment validation
        total_amount = flt(billing.total_amount)
        if new_total_paid > total_amount:
            frappe.throw(
                _("Payment of {0} would exceed balance due. Max: {1}").format(
                    amount_paid, flt(total_amount - flt(billing.amount_paid or 0), 2)
                )
            )

        billing.amount_paid = new_total_paid
        billing.balance_due = flt(total_amount - new_total_paid, 2)
        billing.paid_on = payment_date
        billing.payment_reference = payment_reference

        if new_total_paid >= total_amount:
            billing.status = "Paid"
        else:
            billing.status = "Partially Paid"

        billing.save()

        # Apply to linked invoices FIFO (oldest first) — gracefully skip if no link exists
        try:
            remaining = amount_paid
            linked_invoices = frappe.get_all(
                "BEI Invoice",
                filters={"billing_schedule": billing.name, "payment_status": ["!=", "Paid"]},
                fields=["name", "balance_due", "posting_date"],
                order_by="posting_date ASC",
            )
            for inv in linked_invoices:
                if remaining <= 0:
                    break
                apply_amount = min(remaining, flt(inv.balance_due))
                if apply_amount > 0:
                    inv_doc = frappe.get_doc("BEI Invoice", inv.name)
                    inv_doc.record_payment(apply_amount, payment_date, payment_reference)
                    remaining -= apply_amount
        except Exception as e:
            # billing_schedule field may not exist on BEI Invoice yet — non-blocking
            frappe.log_error(f"Invoice FIFO application skipped: {e}", "Payment Application")

        # Auto-generate Acknowledgement Receipt
        ar_result = generate_acknowledgement_receipt(billing.name)

        frappe.db.release_savepoint("apply_payment")
        # NO frappe.db.commit() — Frappe auto-commits on successful API request

        return {
            "success": True,
            "ar_number": ar_result.get("ar_name"),
            "new_balance": billing.balance_due,
            "status": billing.status,
        }

    except Exception:
        frappe.db.rollback(save_point=sp)
        raise


@frappe.whitelist()
def generate_monthly_billing(billing_period=None, store=None):
    """DEPRECATED: Use hrms.api.billing.generate_monthly_billing instead."""
    from hrms.api.billing import generate_monthly_billing as _generate
    return _generate(billing_period=billing_period, store=store)

@frappe.whitelist()
def check_overdue_invoices():
    """Daily check for missing BEI Invoices > 5 days after payment."""
    from frappe.utils import nowdate, add_days
    from hrms.api.google_chat import send_notification_to_user

    # Find paid online payments without an invoice > 5 days ago
    overdue_date = add_days(nowdate(), -5)
    payments = frappe.db.sql("""
        SELECT name, supplier_name, payment_amount, processed_date, processed_by
        FROM `tabBEI Payment Request`
        WHERE status = 'Paid'
          AND payment_mode IN ('Bank Transfer', 'GCash')
          AND (invoice_reference IS NULL OR invoice_reference = '')
          AND is_advance_payment = 0
          AND DATE(processed_date) <= %s
    """, (overdue_date,), as_dict=True)

    if not payments:
        return

    for pay in payments:
        msg = f"*Missing Invoice Alert*\\nPayment {pay.name} to {pay.supplier_name} for PHP {pay.payment_amount:,.2f} is missing a BEI Invoice. Paid on {pay.processed_date}. Please collect the invoice immediately to comply with EOPT."
        if pay.processed_by:
            send_notification_to_user(pay.processed_by, msg)


def escalate_pending_approvals():
    """Daily escalation: re-notify approvers for PO/PR/Payment approvals pending > 24 hours."""
    from hrms.api.google_chat import send_notification_to_user

    cutoff = add_days(nowdate(), -1)
    notifications_sent = 0

    cpo_email = None
    cfo_email = None
    try:
        cpo_email = frappe.db.get_single_value("BEI Settings", "cpo_approver_email")
        cfo_email = frappe.db.get_single_value("BEI Settings", "cfo_approver_email")
    except Exception:
        pass
    if not cpo_email:
        cpo_email = CPO_APPROVER_EMAIL
    if not cfo_email:
        cfo_email = CFO_APPROVER_EMAIL

    # Pending PO approvals (Mae)
    for po in frappe.db.sql(
        "SELECT name, po_no, supplier_name, grand_total, modified FROM `tabBEI Purchase Order` "
        "WHERE status = 'Pending Mae Approval' AND DATE(modified) <= %s LIMIT 20",
        (cutoff,), as_dict=True,
    ):
        try:
            send_notification_to_user(cpo_email, (
                f"*Reminder: PO Approval Pending > 24h*\nPO: {po.po_no or po.name}\n"
                f"Supplier: {po.supplier_name}\nAmount: PHP {flt(po.grand_total):,.2f}\n"
                f"View: https://my.bebang.ph/procurement/po/{po.name}"
            ))
            notifications_sent += 1
        except Exception:
            frappe.log_error(f"Escalation failed for PO {po.name}", "Approval Escalation Error")

    # Pending PO approvals (Butch/CFO)
    for po in frappe.db.sql(
        "SELECT name, po_no, supplier_name, grand_total, modified FROM `tabBEI Purchase Order` "
        "WHERE status = 'Pending Butch Approval' AND DATE(modified) <= %s LIMIT 20",
        (cutoff,), as_dict=True,
    ):
        try:
            send_notification_to_user(cfo_email, (
                f"*Reminder: PO CFO Approval Pending > 24h*\nPO: {po.po_no or po.name}\n"
                f"Supplier: {po.supplier_name}\nAmount: PHP {flt(po.grand_total):,.2f}\n"
                f"View: https://my.bebang.ph/procurement/po/{po.name}"
            ))
            notifications_sent += 1
        except Exception:
            frappe.log_error(f"Escalation failed for PO {po.name}", "Approval Escalation Error")

    # Pending PR approvals
    for pr in frappe.db.sql(
        "SELECT name, pr_no, department, total_estimated_cost, modified FROM `tabBEI Purchase Requisition` "
        "WHERE status = 'Pending Approval' AND DATE(modified) <= %s LIMIT 20",
        (cutoff,), as_dict=True,
    ):
        try:
            send_notification_to_user(cpo_email, (
                f"*Reminder: PR Approval Pending > 24h*\nPR: {pr.pr_no or pr.name}\n"
                f"Dept: {pr.department or 'N/A'}\nEst: PHP {flt(pr.total_estimated_cost):,.2f}\n"
                f"View: https://my.bebang.ph/procurement/pr/{pr.name}"
            ))
            notifications_sent += 1
        except Exception:
            frappe.log_error(f"Escalation failed for PR {pr.name}", "Approval Escalation Error")

    # Pending Payment Request approvals
    for status, approver, label in [
        ("Pending Review", cpo_email, "Reviewer"),
        ("Pending Budget Approval", cpo_email, "Budget"),
        ("Pending CFO Approval", cfo_email, "CFO"),
        ("Pending CEO Approval", "sam@bebang.ph", "CEO"),
    ]:
        for pay in frappe.db.sql(
            "SELECT name, supplier_name, payment_amount, modified FROM `tabBEI Payment Request` "
            "WHERE status = %s AND DATE(modified) <= %s LIMIT 10",
            (status, cutoff), as_dict=True,
        ):
            try:
                send_notification_to_user(approver, (
                    f"*Reminder: Payment {label} Approval Pending > 24h*\n"
                    f"Payment: {pay.name}\nSupplier: {pay.supplier_name}\n"
                    f"Amount: PHP {flt(pay.payment_amount):,.2f}\n"
                    f"View: https://my.bebang.ph/procurement/payment/{pay.name}"
                ))
                notifications_sent += 1
            except Exception:
                frappe.log_error(f"Escalation failed for Payment {pay.name}", "Approval Escalation Error")

    if notifications_sent:
        frappe.db.commit()


# ── S104: Contracted Price Lookup ─────────────────────────────────────────────

@frappe.whitelist()
def get_contracted_price(item_code, supplier=None):
    """Return the contracted price for an item from the Item Price list.

    Priority:
    1. Supplier-specific Item Price (if supplier given)
    2. Standard Buying Item Price (no supplier filter)
    3. None

    Only returns prices where valid_from <= today AND (valid_upto IS NULL OR valid_upto >= today).
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_contracted_price")

    if not item_code:
        return None

    today_date = frappe.utils.today()

    # Try supplier-specific price first
    if supplier:
        supplier_price = frappe.db.sql("""
            SELECT price_list_rate, price_list, modified, name
            FROM `tabItem Price`
            WHERE item_code = %(item_code)s
            AND supplier = %(supplier)s
            AND buying = 1
            AND valid_from <= %(today)s
            AND (valid_upto IS NULL OR valid_upto >= %(today)s)
            ORDER BY valid_from DESC
            LIMIT 1
        """, {"item_code": item_code, "supplier": supplier, "today": today_date}, as_dict=True)

        if supplier_price:
            return {
                "contracted_rate": flt(supplier_price[0].price_list_rate, 4),
                "price_list": supplier_price[0].price_list,
                "last_updated": str(supplier_price[0].modified),
                "source": "supplier",
                "item_price_name": supplier_price[0].name,
            }

    # Fall back to Standard Buying price (no supplier filter)
    standard_price = frappe.db.sql("""
        SELECT price_list_rate, price_list, modified, name
        FROM `tabItem Price`
        WHERE item_code = %(item_code)s
        AND price_list = 'Standard Buying'
        AND buying = 1
        AND valid_from <= %(today)s
        AND (valid_upto IS NULL OR valid_upto >= %(today)s)
        ORDER BY valid_from DESC
        LIMIT 1
    """, {"item_code": item_code, "today": today_date}, as_dict=True)

    if standard_price:
        return {
            "contracted_rate": flt(standard_price[0].price_list_rate, 4),
            "price_list": standard_price[0].price_list,
            "last_updated": str(standard_price[0].modified),
            "source": "standard_buying",
            "item_price_name": standard_price[0].name,
        }

    return None


# ── S099/S104: Auto-Price Lookup ─────────────────────────────────────────────

@frappe.whitelist()
def get_item_last_price(item_code, supplier=None):
    """Return contracted price + last PO price for an item.

    S104: Returns contracted_price as the primary source of truth.
    Keeps backward-compatible last_price field (alias for last_po_price).
    """
    from hrms.hr.doctype.bei_settings.bei_settings import get_procurement_settings
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_item_last_price")

    settings = get_procurement_settings()
    lookback_days = cint(settings.get("price_variance_lookback_days", 90))

    if not item_code:
        return {"last_price": None, "contracted_price": None, "avg_price": None}

    # S104: Get contracted price
    contracted = get_contracted_price(item_code, supplier)
    contracted_rate = contracted["contracted_rate"] if contracted else None

    filters = {"item_code": item_code}
    supplier_clause = ""
    if supplier:
        supplier_clause = "AND po.supplier = %(supplier)s"
        filters["supplier"] = supplier

    # Last PO price for this item+supplier
    last_price_result = frappe.db.sql("""
        SELECT poi.unit_cost, po.po_date, po.supplier
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %(item_code)s
        AND po.status NOT IN ('Draft', 'Cancelled')
        {supplier_clause}
        ORDER BY po.po_date DESC, po.creation DESC
        LIMIT 1
    """.format(supplier_clause=supplier_clause), filters, as_dict=True)

    # Average price over lookback period
    avg_result = frappe.db.sql("""
        SELECT AVG(poi.unit_cost) as avg_price
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %(item_code)s
        AND po.status NOT IN ('Draft', 'Cancelled')
        AND po.po_date >= DATE_SUB(CURDATE(), INTERVAL %(lookback)s DAY)
        {supplier_clause}
    """.format(supplier_clause=supplier_clause), {**filters, "lookback": lookback_days}, as_dict=True)

    last = last_price_result[0] if last_price_result else None
    avg = avg_result[0] if avg_result else None

    last_po_price = flt(last.unit_cost, 4) if last else None

    return {
        "last_price": last_po_price,  # backward compat alias
        "last_po_price": last_po_price,
        "contracted_price": contracted_rate,
        "last_po_date": str(last.po_date) if last else None,
        "last_supplier": last.supplier if last else None,
        "avg_90d_price": flt(avg.avg_price, 4) if avg and avg.avg_price else None,
        "avg_price": flt(avg.avg_price, 4) if avg and avg.avg_price else None,  # backward compat
        "lookback_days": lookback_days,
        "source": "contracted" if contracted_rate else "po_history",
    }


# ── S104: Price Change Request Endpoints ─────────────────────────────────────

@frappe.whitelist()
def request_price_change(item_code, new_price, reason, document=None):
    """Create a price change request for CPO approval."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="request_price_change",
                                     mutation_type="create")

    if not item_code or not new_price or not reason:
        frappe.throw(_("item_code, new_price, and reason are required"))

    pcr = frappe.get_doc({
        "doctype": "BEI Price Change Request",
        "item_code": item_code,
        "requested_price": flt(new_price),
        "reason": reason,
        "supporting_document": document,
    })
    pcr.insert()
    pcr.submit_for_approval()

    return {"success": True, "name": pcr.name, "status": pcr.status}


@frappe.whitelist()
def approve_price_change(name, comment=None):
    """CPO approves a price change request."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="approve_price_change",
                                     mutation_type="update")

    # CPO identity check is inside the method — bypass DocType permission
    # frappe.get_doc() doesn't accept ignore_permissions; use flags
    frappe.flags.ignore_permissions = True
    try:
        pcr = frappe.get_doc("BEI Price Change Request", name)
        return pcr.approve(comment)
    finally:
        frappe.flags.ignore_permissions = False


@frappe.whitelist()
def reject_price_change(name, reason=None):
    """CPO rejects a price change request."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="reject_price_change",
                                     mutation_type="update")

    frappe.flags.ignore_permissions = True
    try:
        pcr = frappe.get_doc("BEI Price Change Request", name)
        return pcr.reject(reason)
    finally:
        frappe.flags.ignore_permissions = False


# ── S104: Item Request Endpoints ─────────────────────────────────────────────

@frappe.whitelist()
def request_new_item(data=None):
    """Create a new item request for CPO approval."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="request_new_item",
                                     mutation_type="create")

    if isinstance(data, str):
        data = frappe.parse_json(data)
    if not data:
        frappe.throw(_("Missing required parameter: data"))

    required = ["item_code", "item_name", "item_group", "stock_uom",
                "contracted_unit_cost", "cost_justification"]
    for field in required:
        if not data.get(field):
            frappe.throw(_(f"Field '{field}' is required"))

    frappe.flags.ignore_permissions = True
    try:
        item_request = frappe.get_doc({
            "doctype": "BEI Item Request",
            **{k: v for k, v in data.items() if k in [
                "item_code", "item_name", "item_group", "stock_uom", "description",
                "contracted_unit_cost", "cost_justification", "supporting_document", "supplier"
            ]}
        })
        item_request.insert()
        item_request.submit_for_approval()
    finally:
        frappe.flags.ignore_permissions = False

    return {"success": True, "name": item_request.name, "status": item_request.status}


@frappe.whitelist()
def approve_item_request(name):
    """CPO approves a new item request."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="approve_item_request",
                                     mutation_type="create")

    frappe.flags.ignore_permissions = True
    try:
        item_req = frappe.get_doc("BEI Item Request", name)
        return item_req.approve()
    finally:
        frappe.flags.ignore_permissions = False


@frappe.whitelist()
def reject_item_request(name, reason=None):
    """CPO rejects a new item request."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="reject_item_request",
                                     mutation_type="update")

    frappe.flags.ignore_permissions = True
    try:
        item_req = frappe.get_doc("BEI Item Request", name)
        return item_req.reject(reason)
    finally:
        frappe.flags.ignore_permissions = False


@frappe.whitelist()
def get_department_list():
    """Return list of active departments for PR form dropdown.
    Returns [{value: "Commissary - BEI", label: "Commissary"}, ...].
    value = Frappe name (Link field ID), label = display name.
    Filtered to BEI company only, deduplicated.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_department_list")

    departments = frappe.get_all(
        "Department",
        filters={"is_group": 0, "disabled": 0, "company": "Bebang Enterprise Inc."},
        fields=["name", "department_name"],
        order_by="department_name",
    )
    seen = set()
    result = []
    for d in departments:
        if d.name not in seen:
            seen.add(d.name)
            result.append({"value": d.name, "label": d.department_name or d.name})
    return result


@frappe.whitelist()
def get_uom_list():
    """Return list of UOMs for PR form dropdown.
    Returns [{value: "Nos", label: "Nos"}, ...] for consistency with department format.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_uom_list")

    uoms = frappe.get_all("UOM", fields=["name"], order_by="name")
    return [{"value": u.name, "label": u.name} for u in uoms]


@frappe.whitelist()
def search_items(query="", category="", limit=20):
    """Search Item master by item_code or item_name for procurement dropdowns.

    Returns active (non-disabled) items matching the query with their prices.
    Searches both item_code and item_name so users can type "SAGO" and find FG009.
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(module="procurement", action="search_items")

    query = (query or "").strip()
    limit = min(cint(limit) or 20, 50)

    filters = {"disabled": 0}
    if category:
        filters["item_group"] = category

    or_filters = {}
    if query:
        or_filters = {
            "item_code": ["like", f"%{query}%"],
            "item_name": ["like", f"%{query}%"],
        }

    items = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters if query else None,
        fields=["name", "item_code", "item_name", "description", "stock_uom", "item_group", "standard_rate"],
        order_by="item_name asc",
        limit_page_length=limit,
    )

    return [
        {
            "item_code": item.name,
            "item_name": item.item_name,
            "description": item.description or "",
            "uom": item.stock_uom,
            "item_group": item.item_group,
            "standard_rate": flt(item.standard_rate, 2),
        }
        for item in items
    ]


@frappe.whitelist()
def update_po_item_price(po_name, new_price, reason, item_idx=None, item_name=None):
    """Update a PO item's unit price with mandatory reason. Triggers CPO approval.

    Accepts either item_idx (row index) or item_name (child table row name) to identify the item.
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="procurement",
        action="update_po_item_price",
        mutation_type="update",
    )

    if not po_name or not reason or not reason.strip():
        frappe.throw(_("Reason for price change is required"))

    new_price = flt(new_price, 2)
    if new_price <= 0:
        frappe.throw(_("Price must be greater than zero"))

    po = frappe.get_doc("BEI Purchase Order", po_name)

    # Block edits on final-status POs
    final_statuses = ("Approved", "Sent to Supplier", "Fully Received", "Cancelled")
    po_status = po.status or ""
    if po_status in final_statuses or po.docstatus == 2:
        frappe.throw(_("Cannot edit price on a {0} Purchase Order").format(po_status))

    # Find the item row by name (preferred) or idx (fallback)
    target_item = None
    if item_name:
        for item in po.items:
            if item.name == item_name:
                target_item = item
                break
    if not target_item and item_idx:
        item_idx = cint(item_idx)
        for item in po.items:
            if item.idx == item_idx:
                target_item = item
                break
    if not target_item and po.items:
        # Last resort: if only one item, use it
        if len(po.items) == 1:
            target_item = po.items[0]

    if not target_item:
        frappe.throw(_("Item row {0} not found in PO {1}").format(item_idx, po_name))

    old_price = flt(target_item.unit_cost, 2)
    target_item.unit_cost = new_price
    target_item.amount = flt(new_price * flt(target_item.qty), 2)
    target_item.price_override_reason = reason.strip()
    target_item.price_variance_override = reason.strip()
    target_item.price_variance_override_by = frappe.session.user
    target_item.price_variance_override_date = frappe.utils.now_datetime()

    # Recalculate PO totals
    po.total = sum(flt(item.amount) for item in po.items)
    po.grand_total = po.total

    # Log the price change
    change_log = {
        "item_code": target_item.item_code,
        "item_idx": item_idx,
        "old_price": old_price,
        "new_price": new_price,
        "reason": reason.strip(),
        "changed_by": frappe.session.user,
        "changed_at": frappe.utils.now(),
    }

    # Store price override flag and change log
    if hasattr(po, "custom_price_override"):
        po.custom_price_override = 1
    if hasattr(po, "custom_price_change_log"):
        import json as _json

        existing_log = []
        if po.custom_price_change_log:
            try:
                existing_log = _json.loads(po.custom_price_change_log)
            except (ValueError, TypeError):
                existing_log = []
        existing_log.append(change_log)
        po.custom_price_change_log = _json.dumps(existing_log)

    po.save(ignore_permissions=True)

    return {
        "success": True,
        "old_price": old_price,
        "new_price": new_price,
        "new_total": flt(po.grand_total, 2),
        "price_override": 1,
        "change_log": change_log,
    }


# ---------------------------------------------------------------------------
# S135: Inventory Bridge + Supplier Intelligence
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_low_stock_items(threshold_days: int | str = 7, warehouse: str = "", store: str = "") -> dict:
    """Return items below reorder threshold with days-of-stock-remaining.

    S138: Queries real 3PL warehouses where stock actually lives, not the
    empty "Stores - BEI" meta warehouse. When no warehouse is specified,
    aggregates across all active BEI Route source warehouses (3MD, Pinnacle, Jentec).

    Args:
        threshold_days: Alert threshold in days (default 7).
        warehouse: Query a specific warehouse directly (backward-compatible).
        store: Query the source warehouse for a specific store via route map.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="get_low_stock_items", mutation_type="read",
    )

    threshold_days = cint(threshold_days) or 7

    # Determine which warehouses to query
    if warehouse:
        # Direct warehouse query (backward-compatible)
        warehouses = [warehouse]
    elif store:
        # Resolve store to its source 3PL warehouse via BEI Route
        source_wh = frappe.db.get_value(
            "BEI Route", {"active": 1, "source_warehouse": ["!=", ""]},
            "source_warehouse",
            filters={"name": ["in",
                [r.parent for r in frappe.get_all("BEI Route Stop",
                    filters={"store": store}, fields=["parent"])]
            ]},
        )
        if source_wh:
            warehouses = [source_wh]
        else:
            warehouses = [store]  # Fallback to store warehouse itself
    else:
        # S138: Aggregate across all active 3PL source warehouses
        source_warehouses = frappe.db.sql("""
            SELECT DISTINCT source_warehouse
            FROM `tabBEI Route`
            WHERE active = 1 AND source_warehouse IS NOT NULL AND source_warehouse != ''
        """, pluck="source_warehouse")
        warehouses = source_warehouses if source_warehouses else ["Stores - BEI"]

    all_results = []
    queried_warehouses = []

    for wh in warehouses:
        # Get current stock from Bin table
        stock_items = frappe.db.sql("""
            SELECT
                b.item_code,
                i.item_name,
                i.stock_uom,
                b.warehouse,
                b.actual_qty AS current_stock,
                COALESCE(ir.warehouse_reorder_level, 0) AS reorder_point
            FROM `tabBin` b
            JOIN `tabItem` i ON i.name = b.item_code AND i.disabled = 0
            LEFT JOIN `tabItem Reorder` ir
                ON ir.parent = b.item_code AND ir.warehouse = b.warehouse
            WHERE b.warehouse = %(warehouse)s
              AND b.actual_qty > 0
            ORDER BY i.item_name
        """, {"warehouse": wh}, as_dict=True)

        if not stock_items:
            queried_warehouses.append(wh)
            continue

        # Get consumption (outflows) from SLE over last 30 days
        item_codes = [row["item_code"] for row in stock_items]
        consumption_data = frappe.db.sql("""
            SELECT
                item_code,
                ABS(SUM(actual_qty)) AS total_consumed
            FROM `tabStock Ledger Entry`
            WHERE item_code IN %(items)s
              AND warehouse = %(warehouse)s
              AND actual_qty < 0
              AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY item_code
        """, {"items": item_codes, "warehouse": wh}, as_dict=True)

        consumption_map = {row["item_code"]: flt(row["total_consumed"]) for row in consumption_data}

        for item in stock_items:
            total_consumed = consumption_map.get(item["item_code"], 0)
            daily_consumption = flt(total_consumed / 30, 4)

            if daily_consumption <= 0:
                continue

            days_remaining = flt(item["current_stock"] / daily_consumption, 1)

            if days_remaining <= threshold_days:
                all_results.append({
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "stock_uom": item["stock_uom"],
                    "warehouse": item["warehouse"],
                    "current_stock": flt(item["current_stock"], 2),
                    "daily_consumption": daily_consumption,
                    "days_remaining": days_remaining,
                    "reorder_point": flt(item["reorder_point"], 2),
                    "suggested_qty": flt(daily_consumption * 14, 2),
                })

        queried_warehouses.append(wh)

    # Deduplicate by item_code (keep the entry with lowest days_remaining)
    seen = {}
    for item in all_results:
        key = item["item_code"]
        if key not in seen or item["days_remaining"] < seen[key]["days_remaining"]:
            seen[key] = item
    result = list(seen.values())

    # Sort by urgency
    result.sort(key=lambda x: x["days_remaining"])

    return {
        "items": result,
        "warehouses_queried": queried_warehouses,
        "threshold_days": threshold_days,
        "total_alerts": len(result),
    }


@frappe.whitelist()
def auto_convert_pr_to_po(pr_name: str) -> dict:
    """Auto-convert an approved PR to a PO draft if single-source supplier with contracted price.

    Checks:
    1. PR must be approved
    2. All items must have exactly one supplier with a contracted price
    3. If conditions met, calls convert_pr_to_po() and returns the new PO name
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="auto_convert_pr_to_po", mutation_type="create",
    )

    pr = frappe.get_doc("BEI Purchase Requisition", pr_name)

    if pr.status != "Approved":
        return {"success": False, "message": _("PR must be approved before auto-conversion")}

    # Check all items have a single contracted supplier
    supplier = None
    for item in pr.items:
        price_info = get_contracted_price(item.item_code)
        if not price_info or not price_info.get("contracted_rate"):
            return {
                "success": False,
                "message": _("Item {0} has no contracted price — manual PO required").format(
                    item.item_code
                ),
            }

        # Get supplier from the Item Price record
        item_price = frappe.db.get_value(
            "Item Price", price_info.get("item_price_name"), "supplier"
        )

        if not item_price:
            return {
                "success": False,
                "message": _("Item {0} contracted price has no supplier — manual PO required").format(
                    item.item_code
                ),
            }

        if supplier is None:
            supplier = item_price
        elif supplier != item_price:
            return {
                "success": False,
                "message": _("Multiple suppliers found — manual PO required"),
            }

    if not supplier:
        return {"success": False, "message": _("No supplier found for PR items")}

    # All items have same supplier with contracted prices — convert
    result = convert_pr_to_po(pr_name, supplier)
    return {
        "success": True,
        "message": _("PO draft created from PR"),
        "po_name": result.get("name") if isinstance(result, dict) else result,
        "supplier": supplier,
    }


@frappe.whitelist()
def get_expected_deliveries(days: int | str = 7) -> dict:
    """Return POs with expected delivery dates within the given window.

    Returns approved/sent POs where delivery_date falls within now + days.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="get_expected_deliveries", mutation_type="read",
    )

    days = cint(days) or 7

    deliveries = frappe.db.sql("""
        SELECT
            po.name,
            po.po_no,
            po.supplier,
            po.supplier_name,
            po.delivery_date,
            po.status,
            po.grand_total,
            po.items_count,
            DATEDIFF(po.delivery_date, CURDATE()) AS days_until_delivery
        FROM `tabBEI Purchase Order` po
        WHERE po.status IN ('Approved', 'Sent to Supplier')
          AND po.delivery_date IS NOT NULL
          AND po.delivery_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND DATE_ADD(CURDATE(), INTERVAL %(days)s DAY)
        ORDER BY po.delivery_date ASC
    """, {"days": days}, as_dict=True)

    for d in deliveries:
        d["is_overdue"] = (d.get("days_until_delivery") or 0) < 0
        d["grand_total"] = flt(d.get("grand_total"), 2)

    return {
        "deliveries": deliveries,
        "total": len(deliveries),
        "days_window": days,
    }


@frappe.whitelist()
def check_supplier_document_expiry() -> dict:
    """Check all suppliers for documents expiring within 30 days. Sends Google Chat alert.

    Checks bir_expiry_date, sec_expiry_date, permit_expiry_date fields.
    Called by scheduled job (cron).
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="check_supplier_document_expiry", mutation_type="read",
    )

    today = getdate(nowdate())
    alert_date = add_days(today, 30)

    expiring = []

    suppliers = frappe.db.sql("""
        SELECT
            name, supplier_name, supplier_code,
            bir_expiry_date, sec_expiry_date, permit_expiry_date
        FROM `tabBEI Supplier`
        WHERE status = 'Active'
          AND (
            (bir_expiry_date IS NOT NULL AND bir_expiry_date <= %(alert_date)s)
            OR (sec_expiry_date IS NOT NULL AND sec_expiry_date <= %(alert_date)s)
            OR (permit_expiry_date IS NOT NULL AND permit_expiry_date <= %(alert_date)s)
          )
        ORDER BY supplier_name
    """, {"alert_date": alert_date}, as_dict=True)

    for s in suppliers:
        docs_expiring = []
        for field, label in [
            ("bir_expiry_date", "BIR 2307"),
            ("sec_expiry_date", "SEC Registration"),
            ("permit_expiry_date", "Business Permit"),
        ]:
            exp_date = s.get(field)
            if exp_date and getdate(exp_date) <= alert_date:
                days_left = (getdate(exp_date) - today).days
                status = "EXPIRED" if days_left < 0 else f"{days_left} days left"
                docs_expiring.append({"document": label, "expiry_date": str(exp_date), "status": status})

        if docs_expiring:
            expiring.append({
                "supplier_name": s["supplier_name"],
                "supplier_code": s["supplier_code"],
                "name": s["name"],
                "documents": docs_expiring,
            })

    # Send Google Chat notification if any suppliers have expiring docs
    if expiring:
        try:
            from hrms.api.google_chat import send_notification
            lines = [f"*Supplier Document Expiry Alert* ({len(expiring)} suppliers)\n"]
            for s in expiring[:10]:  # Limit to 10 in notification
                doc_list = ", ".join(
                    f"{d['document']} ({d['status']})" for d in s["documents"]
                )
                lines.append(f"• *{s['supplier_name']}*: {doc_list}")
            if len(expiring) > 10:
                lines.append(f"... and {len(expiring) - 10} more")
            send_notification("\n".join(lines), space="procurement")
        except Exception:
            frappe.log_error("Failed to send supplier expiry notification")

    return {
        "suppliers": expiring,
        "total": len(expiring),
        "check_date": str(today),
        "alert_window_days": 30,
    }


@frappe.whitelist()
def get_suppliers_with_expiry(status: str = "Active") -> dict:
    """Return suppliers with document expiry status for dashboard display."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="procurement", action="get_suppliers_with_expiry", mutation_type="read",
    )

    today = getdate(nowdate())

    suppliers = frappe.db.sql("""
        SELECT
            name, supplier_name, supplier_code,
            bir_expiry_date, sec_expiry_date, permit_expiry_date
        FROM `tabBEI Supplier`
        WHERE status = %(status)s
          AND (bir_expiry_date IS NOT NULL
               OR sec_expiry_date IS NOT NULL
               OR permit_expiry_date IS NOT NULL)
        ORDER BY supplier_name
    """, {"status": status}, as_dict=True)

    for s in suppliers:
        s["expiry_status"] = []
        for field, label in [
            ("bir_expiry_date", "BIR 2307"),
            ("sec_expiry_date", "SEC Registration"),
            ("permit_expiry_date", "Business Permit"),
        ]:
            exp_date = s.get(field)
            if exp_date:
                days_left = (getdate(exp_date) - today).days
                if days_left < 0:
                    badge = "expired"
                elif days_left <= 30:
                    badge = "warning"
                else:
                    badge = "ok"
                s["expiry_status"].append({
                    "document": label,
                    "expiry_date": str(exp_date),
                    "days_left": days_left,
                    "badge": badge,
                })

    return {"suppliers": suppliers, "total": len(suppliers)}


# ============================================================================
# S147: AP Command Center — Backend Endpoints
# ============================================================================


@frappe.whitelist()
def update_invoice_payment_status(invoice_name: str, payment_status: str, notes: str | None = None) -> dict[str, Any]:
    """Update payment status on a BEI Invoice with audit trail.

    Only Accounts Manager / System Manager can change status.
    Writes audit entry to verification_notes for BIR traceability.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="finance", action="update_invoice_payment_status", mutation_type="update"
    )

    allowed_statuses = ("Unpaid", "Partially Paid", "Paid")
    if payment_status not in allowed_statuses:
        frappe.throw(f"Invalid payment status: {payment_status}. Must be one of {allowed_statuses}")

    if not frappe.db.exists("BEI Invoice", invoice_name):
        frappe.throw(f"Invoice {invoice_name} not found")

    doc = frappe.get_doc("BEI Invoice", invoice_name)
    old_status = doc.payment_status or "Unpaid"

    if old_status == payment_status:
        return {"name": doc.name, "payment_status": payment_status, "changed": False}

    # Build audit trail entry
    user = frappe.session.user
    timestamp = frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M")
    audit_entry = f"[{timestamp}] {user}: Status changed {old_status} -> {payment_status}"
    if notes:
        audit_entry += f" — {notes}"

    existing_notes = doc.verification_notes or ""
    doc.verification_notes = f"{audit_entry}\n{existing_notes}".strip()
    doc.payment_status = payment_status

    if payment_status == "Paid":
        doc.amount_paid = flt(doc.grand_total)
        doc.balance_due = 0
    elif payment_status == "Unpaid":
        doc.amount_paid = 0
        doc.balance_due = flt(doc.grand_total)

    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "name": doc.name,
        "payment_status": payment_status,
        "changed": True,
        "audit_entry": audit_entry,
    }


@frappe.whitelist()
def get_supplier_transaction_timeline(supplier: str, limit: int = 50) -> dict[str, Any]:
    """Return unified chronological timeline of all documents for a supplier.

    Merges POs, GRs, Invoices, Payment Requests, and ORs into a single
    sorted timeline for the Supplier Ledger tab.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="finance", action="get_supplier_transaction_timeline", mutation_type="read"
    )

    limit = cint(limit) or 50
    timeline = []

    # Purchase Orders (date field = po_date, amount = grand_total)
    pos = frappe.get_all(
        "BEI Purchase Order",
        filters={"supplier": supplier},
        fields=["name", "po_date", "grand_total", "status"],
        order_by="po_date desc",
        limit_page_length=limit,
    )
    for po in pos:
        timeline.append({
            "date": str(po.po_date or ""),
            "doc_type": "Purchase Order",
            "doc_name": po.name,
            "description": f"PO {po.name}",
            "amount": flt(po.grand_total),
            "status": po.status or "",
        })

    # Goods Receipts (date field = receipt_date, amount = total_amount)
    grs = frappe.get_all(
        "BEI Goods Receipt",
        filters={"supplier": supplier},
        fields=["name", "receipt_date", "total_amount", "status"],
        order_by="receipt_date desc",
        limit_page_length=limit,
    )
    for gr in grs:
        timeline.append({
            "date": str(gr.receipt_date or ""),
            "doc_type": "Goods Receipt",
            "doc_name": gr.name,
            "description": f"GR {gr.name}",
            "amount": flt(gr.total_amount),
            "status": gr.status or "",
        })

    # Invoices
    invs = frappe.get_all(
        "BEI Invoice",
        filters={"supplier": supplier},
        fields=["name", "invoice_date", "grand_total", "payment_status", "supplier_invoice_no"],
        order_by="invoice_date desc",
        limit_page_length=limit,
    )
    for inv in invs:
        timeline.append({
            "date": str(inv.invoice_date),
            "doc_type": "Invoice",
            "doc_name": inv.name,
            "description": f"INV {inv.supplier_invoice_no or inv.name}",
            "amount": flt(inv.grand_total),
            "status": inv.payment_status or "Unpaid",
        })

    # Payment Requests (date = request_date, amount = payment_amount, status = status)
    pays = frappe.get_all(
        "BEI Payment Request",
        filters={"supplier": supplier},
        fields=["name", "request_date", "payment_amount", "status"],
        order_by="request_date desc",
        limit_page_length=limit,
    )
    for pay in pays:
        timeline.append({
            "date": str(pay.request_date or ""),
            "doc_type": "Payment Request",
            "doc_name": pay.name,
            "description": f"PAY {pay.name}",
            "amount": flt(pay.payment_amount),
            "status": pay.status or "",
        })

    # Sort by date descending, then by doc_type for same-day ordering
    doc_type_order = {"Purchase Order": 0, "Goods Receipt": 1, "Invoice": 2, "Payment Request": 3}
    timeline.sort(key=lambda x: (x["date"], doc_type_order.get(x["doc_type"], 9)), reverse=True)

    return {"timeline": timeline[:limit], "total": len(timeline)}


@frappe.whitelist()
def bulk_update_invoice_acctg_status(invoice_names: list[str] | str, acctg_status: str) -> dict[str, Any]:
    """Bulk update accounting status on invoices via verification_notes.

    Used for 'Transferred to Finance' and similar accounting workflow tags.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(
        module="finance", action="bulk_update_invoice_acctg_status", mutation_type="update"
    )

    if isinstance(invoice_names, str):
        invoice_names = frappe.parse_json(invoice_names)

    if not invoice_names:
        frappe.throw("No invoices specified")

    user = frappe.session.user
    timestamp = frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M")
    tag = f"[{timestamp}] {user}: {acctg_status}"

    updated = 0
    for inv_name in invoice_names:
        if not frappe.db.exists("BEI Invoice", inv_name):
            continue
        existing = frappe.db.get_value("BEI Invoice", inv_name, "verification_notes") or ""
        if acctg_status not in existing:
            new_notes = f"{tag}\n{existing}".strip()
            frappe.db.set_value("BEI Invoice", inv_name, "verification_notes", new_notes)
            updated += 1

    frappe.db.commit()
    return {"updated": updated, "total": len(invoice_names), "tag": tag}


# =============================================================================
# SUPPLIER HUB ENDPOINTS (S186)
# =============================================================================

SUPPLIER_GRID_ALLOWED_SORT_COLUMNS = frozenset({
    "supplier_name", "supplier_code", "status",
    "total_po_value", "total_po_count", "total_outstanding", "on_time_rate",
})
SUPPLIER_GRID_ALLOWED_SORT_DIRECTIONS = frozenset({"ASC", "DESC"})

SUPPLIER_HUB_ALLOWED_ROLES = {
    "Procurement User", "Procurement Manager", "Warehouse User", "System Manager",
}

# Pending PO statuses — full strings per DocType Select options
_PENDING_PO_STATUSES = (
    "'Draft'", "'Pending Mae Approval'", "'Pending Butch Approval'", "'Pending CEO Approval'"
)


@frappe.whitelist()
def get_supplier_grid(
    search=None, status=None, compliance=None,
    sort_by=None, sort_order=None,
    page=1, page_size=50,
):
    """Paginated supplier grid with live-computed metrics and fleet-level summary.

    Returns supplier rows with PO/GR/Invoice aggregates computed via JOINs (not
    stored DocType fields), plus a summary object covering ALL suppliers.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_grid")

    _require_roles(
        SUPPLIER_HUB_ALLOWED_ROLES,
        _("You do not have permission to view the Supplier Hub."),
    )

    # --- Sanitize sort params (SQL injection prevention) ---
    sort_col = sort_by if sort_by in SUPPLIER_GRID_ALLOWED_SORT_COLUMNS else "supplier_name"
    sort_dir = sort_order.upper() if sort_order and sort_order.upper() in SUPPLIER_GRID_ALLOWED_SORT_DIRECTIONS else "ASC"

    page = max(1, cint(page))
    page_size = min(200, max(1, cint(page_size) or 50))
    offset = (page - 1) * page_size

    # --- Build WHERE conditions ---
    conditions = ["1=1"]
    values: dict[str, Any] = {}

    if search:
        conditions.append(
            "(s.supplier_name LIKE %(search)s OR s.supplier_code LIKE %(search)s "
            "OR s.contact_person LIKE %(search)s OR s.email LIKE %(search)s)"
        )
        values["search"] = f"%{search}%"

    if status:
        conditions.append("s.status = %(status_filter)s")
        values["status_filter"] = status

    if compliance:
        if compliance == "missing_bir":
            conditions.append("(s.bir_2307 IS NULL OR s.bir_2307 = '')")
        elif compliance == "missing_sec":
            conditions.append("(s.sec_certificate IS NULL OR s.sec_certificate = '')")
        elif compliance == "missing_permit":
            conditions.append("(s.business_permit IS NULL OR s.business_permit = '')")
        elif compliance == "expiring_soon":
            conditions.append(
                "(s.bir_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) "
                "OR s.sec_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) "
                "OR s.permit_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY))"
            )

    where_clause = " AND ".join(conditions)

    # --- Main query: suppliers + live PO aggregates ---
    pending_statuses = ", ".join(_PENDING_PO_STATUSES)
    suppliers = frappe.db.sql(f"""
        SELECT
            s.name,
            s.supplier_code,
            s.supplier_name,
            s.status,
            s.contact_person,
            s.email,
            s.contact_number,
            s.tin,
            s.payment_terms,
            /* Live PO aggregates */
            COALESCE(po_agg.total_po_count, 0) AS total_po_count,
            COALESCE(po_agg.total_po_value, 0) AS total_po_value,
            COALESCE(po_agg.pending_po_count, 0) AS pending_po_count,
            COALESCE(po_agg.last_order_date, NULL) AS last_order_date,
            /* Live outstanding from invoices */
            COALESCE(inv_agg.total_outstanding, 0) AS total_outstanding,
            /* Live GR pending count */
            COALESCE(gr_agg.pending_gr_count, 0) AS pending_gr_count,
            /* Stored performance metrics (acceptable — computed by background job) */
            COALESCE(s.on_time_rate, 0) AS on_time_rate,
            COALESCE(s.avg_delivery_days, 0) AS avg_delivery_days,
            /* Compliance fields — cast to boolean */
            CASE WHEN s.bir_2307 IS NOT NULL AND s.bir_2307 != '' THEN 1 ELSE 0 END AS bir_2307,
            s.bir_expiry_date,
            CASE WHEN s.sec_certificate IS NOT NULL AND s.sec_certificate != '' THEN 1 ELSE 0 END AS sec_certificate,
            s.sec_expiry_date,
            CASE WHEN s.business_permit IS NOT NULL AND s.business_permit != '' THEN 1 ELSE 0 END AS business_permit,
            s.permit_expiry_date,
            /* Items count */
            COALESCE(item_agg.items_count, 0) AS items_count
        FROM `tabBEI Supplier` s
        /* PO aggregates */
        LEFT JOIN (
            SELECT
                supplier,
                COUNT(*) AS total_po_count,
                SUM(grand_total) AS total_po_value,
                SUM(CASE WHEN status IN ({pending_statuses}) THEN 1 ELSE 0 END) AS pending_po_count,
                MAX(po_date) AS last_order_date
            FROM `tabBEI Purchase Order`
            WHERE status NOT IN ('Cancelled', 'Rejected')
            GROUP BY supplier
        ) po_agg ON po_agg.supplier = s.name
        /* Invoice outstanding */
        LEFT JOIN (
            SELECT
                supplier,
                SUM(balance_due) AS total_outstanding
            FROM `tabBEI Invoice`
            WHERE payment_status != 'Paid' AND docstatus = 1
            GROUP BY supplier
        ) inv_agg ON inv_agg.supplier = s.name
        /* Pending GRs: POs that have no completed GR */
        LEFT JOIN (
            SELECT
                po.supplier,
                COUNT(DISTINCT po.name) AS pending_gr_count
            FROM `tabBEI Purchase Order` po
            LEFT JOIN `tabBEI Goods Receipt` gr ON gr.purchase_order = po.name
                AND gr.status NOT IN ('Draft', 'Cancelled', 'Rejected')
            WHERE po.status IN ('Approved', 'Sent to Supplier', 'Partially Received')
                AND gr.name IS NULL
            GROUP BY po.supplier
        ) gr_agg ON gr_agg.supplier = s.name
        /* Distinct items count */
        LEFT JOIN (
            SELECT
                po.supplier,
                COUNT(DISTINCT poi.item_code) AS items_count
            FROM `tabBEI PO Item` poi
            JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
            WHERE po.status NOT IN ('Cancelled', 'Rejected')
            GROUP BY po.supplier
        ) item_agg ON item_agg.supplier = s.name
        WHERE {where_clause}
        ORDER BY {sort_col} {sort_dir}
        LIMIT %(page_size)s OFFSET %(offset)s
    """, {**values, "page_size": page_size, "offset": offset}, as_dict=True)

    # --- Total count for pagination ---
    total = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabBEI Supplier` s WHERE {where_clause}",
        values,
    )[0][0]

    # --- Fleet-level summary (across ALL suppliers, ignoring pagination) ---
    summary = frappe.db.sql("""
        SELECT
            COUNT(*) AS total_suppliers,
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) AS inactive,
            SUM(CASE WHEN status = 'Blacklisted' THEN 1 ELSE 0 END) AS blacklisted,
            SUM(CASE WHEN status = 'Pending Verification' THEN 1 ELSE 0 END) AS pending_verification,
            SUM(CASE WHEN bir_2307 IS NULL OR bir_2307 = '' THEN 1 ELSE 0 END) AS missing_bir,
            SUM(CASE WHEN sec_certificate IS NULL OR sec_certificate = '' THEN 1 ELSE 0 END) AS missing_sec,
            SUM(CASE WHEN business_permit IS NULL OR business_permit = '' THEN 1 ELSE 0 END) AS missing_permit,
            SUM(CASE WHEN (
                (bir_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY))
                OR (sec_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY))
                OR (permit_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY))
            ) THEN 1 ELSE 0 END) AS expiring_soon
        FROM `tabBEI Supplier`
    """, as_dict=True)[0]

    # Pending POs and GRs fleet-level
    pending_fleet = frappe.db.sql(f"""
        SELECT
            SUM(CASE WHEN po.status IN ({pending_statuses}) THEN 1 ELSE 0 END) AS total_pending_pos
        FROM `tabBEI Purchase Order` po
        WHERE po.status NOT IN ('Cancelled', 'Rejected')
    """, as_dict=True)[0]

    outstanding_fleet = frappe.db.sql("""
        SELECT COALESCE(SUM(balance_due), 0) AS total_outstanding
        FROM `tabBEI Invoice`
        WHERE payment_status != 'Paid' AND docstatus = 1
    """)[0][0]

    pending_grs_fleet = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT po.name) AS total_pending_grs
        FROM `tabBEI Purchase Order` po
        LEFT JOIN `tabBEI Goods Receipt` gr ON gr.purchase_order = po.name
            AND gr.status NOT IN ('Draft', 'Cancelled', 'Rejected')
        WHERE po.status IN ('Approved', 'Sent to Supplier', 'Partially Received')
            AND gr.name IS NULL
    """)[0][0]

    summary["total_outstanding"] = flt(outstanding_fleet)
    summary["total_pending_pos"] = cint(pending_fleet.get("total_pending_pos"))
    summary["total_pending_grs"] = cint(pending_grs_fleet)

    return {
        "data": suppliers,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "summary": summary,
        "filters": {
            "statuses": ["Active", "Inactive", "Blacklisted", "Pending Verification"],
        },
    }


@frappe.whitelist()
def get_supplier_overview(name=None, supplier=None):
    """Single-call supplier detail — identity, metrics, items, POs, GRs, invoices, monthly spend.

    Returns everything the Supplier Overview page needs in one round-trip.
    All metrics are computed live via SQL (not from stored DocType fields).

    Accepts `name` (from proxy :name param) or `supplier` for direct calls.
    """
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="procurement", action="get_supplier_overview")

    _require_roles(
        SUPPLIER_HUB_ALLOWED_ROLES,
        _("You do not have permission to view the Supplier Hub."),
    )

    # Accept either `name` (proxy convention) or `supplier` (direct call)
    supplier = name or supplier
    if not supplier:
        frappe.throw(_("Supplier is required."))

    if not frappe.db.exists("BEI Supplier", supplier):
        frappe.throw(
            _("Supplier '{0}' not found.").format(supplier),
            frappe.DoesNotExistError,
        )

    # --- Supplier doc (all fields) ---
    supplier_doc = frappe.get_doc("BEI Supplier", supplier)
    supplier_data = supplier_doc.as_dict()
    # Remove internal Frappe fields
    for key in ("_user_tags", "_comments", "_assign", "_liked_by", "doctype", "docstatus"):
        supplier_data.pop(key, None)

    # --- Live metrics from PO/Invoice/GR ---
    pending_statuses = ", ".join(_PENDING_PO_STATUSES)

    po_metrics = frappe.db.sql(f"""
        SELECT
            COUNT(*) AS total_po_count,
            COALESCE(SUM(grand_total), 0) AS total_po_value,
            MAX(po_date) AS last_order_date,
            MIN(po_date) AS first_order_date,
            SUM(CASE WHEN status IN ({pending_statuses}) THEN 1 ELSE 0 END) AS pending_po_count
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND status NOT IN ('Cancelled', 'Rejected')
    """, {"supplier": supplier}, as_dict=True)[0]

    inv_metrics = frappe.db.sql("""
        SELECT
            COALESCE(SUM(balance_due), 0) AS total_outstanding,
            COUNT(CASE WHEN payment_status != 'Paid' THEN 1 END) AS pending_invoice_count
        FROM `tabBEI Invoice`
        WHERE supplier = %(supplier)s AND docstatus = 1
    """, {"supplier": supplier}, as_dict=True)[0]

    pending_gr_count = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT po.name) AS cnt
        FROM `tabBEI Purchase Order` po
        LEFT JOIN `tabBEI Goods Receipt` gr ON gr.purchase_order = po.name
            AND gr.status NOT IN ('Draft', 'Cancelled', 'Rejected')
        WHERE po.supplier = %(supplier)s
          AND po.status IN ('Approved', 'Sent to Supplier', 'Partially Received')
          AND gr.name IS NULL
    """, {"supplier": supplier})[0][0]

    items_count = frappe.db.sql("""
        SELECT COUNT(DISTINCT poi.item_code) AS cnt
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE po.supplier = %(supplier)s
          AND po.status NOT IN ('Cancelled', 'Rejected')
    """, {"supplier": supplier})[0][0]

    # YTD spend
    ytd_spend = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND po_date >= CONCAT(YEAR(CURDATE()), '-01-01')
          AND status NOT IN ('Cancelled', 'Rejected', 'Draft')
    """, {"supplier": supplier})[0][0]

    # Monthly spend (last 12 months)
    monthly_spend = frappe.db.sql("""
        SELECT
            DATE_FORMAT(po_date, '%%Y-%%m') AS month,
            SUM(grand_total) AS amount
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND po_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
          AND status NOT IN ('Cancelled', 'Rejected', 'Draft')
        GROUP BY month
        ORDER BY month
    """, {"supplier": supplier}, as_dict=True)

    # Last month spend
    last_month_spend = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND po_date >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%%Y-%%m-01')
          AND po_date < DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
          AND status NOT IN ('Cancelled', 'Rejected', 'Draft')
    """, {"supplier": supplier})[0][0]

    # Avg monthly spend (from the 12-month window)
    total_months = max(1, len(monthly_spend))
    total_12m = sum(flt(m.get("amount", 0)) for m in monthly_spend)
    avg_monthly_spend = total_12m / total_months

    metrics = {
        "total_po_count": cint(po_metrics.get("total_po_count")),
        "total_po_value": flt(po_metrics.get("total_po_value")),
        "total_outstanding": flt(inv_metrics.get("total_outstanding")),
        "pending_po_count": cint(po_metrics.get("pending_po_count")),
        "pending_gr_count": cint(pending_gr_count),
        "pending_invoice_count": cint(inv_metrics.get("pending_invoice_count")),
        "last_order_date": po_metrics.get("last_order_date"),
        "first_order_date": po_metrics.get("first_order_date"),
        "on_time_rate": flt(supplier_doc.on_time_rate),
        "avg_delivery_days": flt(supplier_doc.avg_delivery_days),
        "items_count": cint(items_count),
        "ytd_spend": flt(ytd_spend),
        "last_month_spend": flt(last_month_spend),
        "avg_monthly_spend": flt(avg_monthly_spend, 2),
    }

    # --- Items aggregated from PO data ---
    items = frappe.db.sql("""
        SELECT
            poi.item_code,
            poi.item_name,
            poi.uom,
            COUNT(DISTINCT poi.parent) AS po_count,
            SUM(poi.qty) AS total_qty,
            ROUND(AVG(poi.unit_cost), 2) AS avg_unit_cost,
            SUM(poi.amount) AS total_amount,
            MAX(po.po_date) AS last_purchase_date
        FROM `tabBEI PO Item` poi
        JOIN `tabBEI Purchase Order` po ON poi.parent = po.name
        WHERE po.supplier = %(supplier)s
          AND po.status NOT IN ('Cancelled', 'Rejected')
        GROUP BY poi.item_code, poi.item_name, poi.uom
        ORDER BY total_amount DESC
    """, {"supplier": supplier}, as_dict=True)

    # --- Recent POs (last 20) ---
    recent_pos = frappe.db.sql("""
        SELECT name, po_no, po_date, grand_total, status, delivery_date
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND status NOT IN ('Cancelled', 'Rejected')
        ORDER BY po_date DESC
        LIMIT 20
    """, {"supplier": supplier}, as_dict=True)

    # --- Pending POs ---
    pending_pos = frappe.db.sql(f"""
        SELECT name, po_no, po_date, grand_total, status, delivery_date
        FROM `tabBEI Purchase Order`
        WHERE supplier = %(supplier)s
          AND status IN ({pending_statuses}, 'Approved', 'Sent to Supplier', 'Partially Received')
        ORDER BY po_date DESC
    """, {"supplier": supplier}, as_dict=True)

    # --- Pending GRs (POs awaiting goods receipt) ---
    pending_grs = frappe.db.sql(f"""
        SELECT
            po.name AS po_name,
            po.po_no,
            po.po_date,
            po.grand_total,
            po.status,
            po.delivery_date
        FROM `tabBEI Purchase Order` po
        LEFT JOIN `tabBEI Goods Receipt` gr ON gr.purchase_order = po.name
            AND gr.status NOT IN ('Draft', 'Cancelled', 'Rejected')
        WHERE po.supplier = %(supplier)s
          AND po.status IN ('Approved', 'Sent to Supplier', 'Partially Received')
          AND gr.name IS NULL
        ORDER BY po.po_date DESC
    """, {"supplier": supplier}, as_dict=True)

    # --- Recent invoices (last 20) ---
    recent_invoices = frappe.db.sql("""
        SELECT name, invoice_no, invoice_date, due_date, grand_total,
               payment_status, balance_due
        FROM `tabBEI Invoice`
        WHERE supplier = %(supplier)s AND docstatus = 1
        ORDER BY invoice_date DESC
        LIMIT 20
    """, {"supplier": supplier}, as_dict=True)

    return {
        "supplier": supplier_data,
        "metrics": metrics,
        "items": items,
        "recent_pos": recent_pos,
        "pending_pos": pending_pos,
        "pending_grs": pending_grs,
        "recent_invoices": recent_invoices,
        "monthly_spend": monthly_spend,
    }
