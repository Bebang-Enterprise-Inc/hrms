"""
BEI Brain S023B Phase 1D: Frappe doc_events hook handler.

Fires on document lifecycle events, POSTs event payload to
Supabase Edge Function (ingest-frappe-event) via background job.

Module path: hrms.utils.brain_sync
Registered in: hrms/hooks.py doc_events
"""
import frappe
import json
import hashlib
import requests
from frappe.utils.background_jobs import enqueue

# Translate Frappe hook names to clean event types
HOOK_EVENT_MAP = {
    "on_submit": "submit",
    "on_update_after_submit": "update",
    "on_cancel": "cancel",
    "after_insert": "create",
    "on_update": "update",
}

# Fields to EXCLUDE from event_data snapshot (internal Frappe fields)
EXCLUDE_FIELDS = {
    "_liked_by", "_comments", "_assign", "_seen", "docstatus",
    "modified_by", "owner", "creation", "modified",
    "idx", "doctype", "name",
}
MAX_EVENT_DATA_KEYS = 50

# DocType -> domain + flow mapping (52 DocTypes)
DOCTYPE_MAP = {
    # D01 - Procurement & Billing
    "BEI Purchase Order":        {"domain": "procurement", "flow": "F01"},
    "BEI Purchase Requisition":  {"domain": "procurement", "flow": "F01"},
    "BEI Goods Receipt":         {"domain": "procurement", "flow": "F01"},
    "BEI Invoice":               {"domain": "procurement", "flow": "F01"},
    "BEI Payment Request":       {"domain": "procurement", "flow": "F01"},
    "BEI Statement of Account":  {"domain": "procurement", "flow": "F01"},
    "Expense Claim":             {"domain": "procurement", "flow": "F04"},
    "Employee Advance":          {"domain": "procurement", "flow": "F04"},

    # D02 - Inventory & Warehouse
    "BEI Cycle Count":           {"domain": "inventory",   "flow": "F05"},
    "BEI Store Order":           {"domain": "inventory",   "flow": "F08"},
    "BEI Store Receiving":       {"domain": "inventory",   "flow": "F08"},
    "BEI FQI Report":            {"domain": "inventory",   "flow": "F05"},
    "BEI Pick List":             {"domain": "inventory",   "flow": "F07"},

    # D03 - Commissary & Production
    "BEI Production":            {"domain": "commissary",  "flow": "F07"},
    "BEI QC Form":               {"domain": "commissary",  "flow": "F07"},
    "BEI Distribution Trip":     {"domain": "commissary",  "flow": "F06"},

    # D04 - HR Core & Workforce
    "Attendance":                {"domain": "hr",          "flow": "F03"},
    "Attendance Request":        {"domain": "hr",          "flow": "F03"},
    "Leave Application":         {"domain": "hr",          "flow": "F04"},
    "Leave Allocation":          {"domain": "hr",          "flow": "F04"},
    "BEI Overtime Request":      {"domain": "hr",          "flow": "F03"},
    "Shift Assignment":          {"domain": "hr",          "flow": "F03"},
    "Shift Request":             {"domain": "hr",          "flow": "F03"},
    "Overtime Slip":             {"domain": "hr",          "flow": "F03"},
    "BEI Official Business":     {"domain": "hr",          "flow": "F03"},
    "Salary Slip":               {"domain": "hr",          "flow": "F03"},
    "Payroll Entry":             {"domain": "hr",          "flow": "F03"},
    "Employee Separation":       {"domain": "hr",          "flow": "F13"},
    "Employee Transfer":         {"domain": "hr",          "flow": "F13"},
    "Employee Promotion":        {"domain": "hr",          "flow": "F13"},
    "BEI Transfer Request":      {"domain": "hr",          "flow": "F13"},
    "BEI HR Personnel Action":   {"domain": "hr",          "flow": "F13"},
    "BEI Incident Report":       {"domain": "hr",          "flow": "F13"},
    "BEI Notice to Explain":     {"domain": "hr",          "flow": "F13"},
    "BEI Notice of Decision":    {"domain": "hr",          "flow": "F13"},
    "Job Applicant":             {"domain": "hr",          "flow": "F02"},
    "Job Offer":                 {"domain": "hr",          "flow": "F02"},
    "Employee Onboarding":       {"domain": "hr",          "flow": "F02"},
    "Appraisal":                 {"domain": "hr",          "flow": "F03"},
    "BEI Expense Request":       {"domain": "hr",          "flow": "F04"},
    "BEI Petty Cash Fund":       {"domain": "hr",          "flow": "F04"},

    # D05 - Projects & Maintenance
    "BEI Maintenance Request":   {"domain": "projects",    "flow": "F09"},
    "BEI Maintenance Completion": {"domain": "projects",   "flow": "F09"},
    "BEI Project":               {"domain": "projects",    "flow": "F09"},
    "BEI Site Inspection":       {"domain": "projects",    "flow": "F09"},

    # D06 - Integrations & Platform
    "BEI Announcement":          {"domain": "platform",    "flow": "F10"},
    "BEI POS Upload":            {"domain": "platform",    "flow": "F11"},

    # D07 - Finance & Analytics
    "BEI Store Opening Report":  {"domain": "finance",     "flow": "F12"},
    "BEI Store Closing Report":  {"domain": "finance",     "flow": "F12"},
    "BEI Bank Deposit":          {"domain": "finance",     "flow": "F12"},
    "BEI Store Visit Report":    {"domain": "finance",     "flow": "F12"},
    "BEI Mid-Shift Handover":    {"domain": "finance",     "flow": "F12"},
}

# Very-high-volume DocTypes: store event_data but SKIP embedding
SKIP_EMBEDDING_DOCTYPES = {
    "Attendance", "Employee Checkin", "Leave Ledger Entry",
    "Shift Assignment", "Shift Schedule", "Leave Allocation",
}


def generate_content_summary(doc, event_type):
    """Generate a human-readable content summary for semantic search."""
    dt = doc.doctype
    dn = doc.name
    actor = frappe.session.user
    date_str = str(
        doc.get("posting_date")
        or doc.get("transaction_date")
        or doc.get("attendance_date")
        or doc.get("creation")
        or ""
    )

    if dt == "BEI Purchase Order":
        return (
            f"Purchase Order {dn} {event_type} by {actor}. "
            f"Supplier: {doc.get('supplier_name', 'N/A')}. "
            f"Amount: PHP {(doc.get('grand_total') or 0):,.2f}. "
            f"Items: {doc.get('total_qty', 0)} items. Date: {date_str}."
        )
    elif dt == "BEI Purchase Requisition":
        return (
            f"Purchase Requisition {dn} {event_type} by {actor}. "
            f"Requestor: {doc.get('requested_by', 'N/A')}. "
            f"Items: {doc.get('total_qty', 0)}. Date: {date_str}."
        )
    elif dt == "Leave Application":
        return (
            f"Leave Application {dn} {event_type} by {actor}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"Type: {doc.get('leave_type', 'N/A')}. "
            f"From {doc.get('from_date')} to {doc.get('to_date')} "
            f"({doc.get('total_leave_days', 0)} days)."
        )
    elif dt == "Attendance":
        return (
            f"Attendance {dn} {event_type}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"Status: {doc.get('status', 'N/A')}. "
            f"Date: {doc.get('attendance_date', date_str)}."
        )
    elif dt == "BEI Store Closing Report":
        return (
            f"Store Closing Report {dn} {event_type} by {actor}. "
            f"Store: {doc.get('store', 'N/A')}. Date: {date_str}. "
            f"Total sales: PHP {(doc.get('total_sales') or 0):,.2f}."
        )
    elif dt == "Employee Separation":
        return (
            f"Employee Separation {dn} {event_type} by {actor}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"Department: {doc.get('department', 'N/A')}. "
            f"Reason: {doc.get('reason_for_leaving', 'Not specified')}."
        )
    elif dt == "Salary Slip":
        return (
            f"Salary Slip {dn} {event_type}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"Net Pay: PHP {(doc.get('net_pay') or 0):,.2f}. "
            f"Period: {doc.get('start_date')} to {doc.get('end_date')}."
        )
    elif dt == "BEI Maintenance Request":
        desc = (doc.get("description") or "")[:200]
        return (
            f"Maintenance Request {dn} {event_type} by {actor}. "
            f"Store: {doc.get('store', 'N/A')}. "
            f"Category: {doc.get('category', 'N/A')}. "
            f"Description: {desc}."
        )
    elif dt == "BEI Goods Receipt":
        return (
            f"Goods Receipt {dn} {event_type} by {actor}. "
            f"Supplier: {doc.get('supplier_name', 'N/A')}. "
            f"PO Ref: {doc.get('purchase_order', 'N/A')}. "
            f"Items: {doc.get('total_qty', 0)}. Date: {date_str}."
        )
    elif dt == "BEI Incident Report":
        return (
            f"Incident Report {dn} {event_type} by {actor}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"Store: {doc.get('store', 'N/A')}. "
            f"Type: {doc.get('incident_type', 'N/A')}."
        )
    elif dt == "Employee Transfer":
        return (
            f"Employee Transfer {dn} {event_type} by {actor}. "
            f"Employee: {doc.get('employee_name', 'N/A')}. "
            f"From: {doc.get('previous_designation', 'N/A')}. "
            f"To: {doc.get('new_designation', 'N/A')}."
        )
    elif dt == "BEI Store Order":
        return (
            f"Store Order {dn} {event_type} by {actor}. "
            f"Store: {doc.get('store', 'N/A')}. "
            f"Items: {doc.get('total_qty', 0)}. Date: {date_str}."
        )
    else:
        # Generic fallback: pull common fields
        fields = []
        for f in ["employee_name", "supplier_name", "store", "department",
                   "status", "grand_total", "total_qty"]:
            val = doc.get(f)
            if val:
                fields.append(f"{f.replace('_', ' ').title()}: {val}")
        field_str = ". ".join(fields) if fields else "No additional details"
        return f"{dt} {dn} {event_type} by {actor}. {field_str}. Date: {date_str}."


def calculate_importance(doc, event_type):
    """Score importance 1-10 based on business impact."""
    dt = doc.doctype

    # High-impact events
    if dt == "Employee Separation":
        return 9
    if dt in ("Employee Transfer", "Employee Promotion", "BEI HR Personnel Action"):
        return 8
    if dt == "BEI Purchase Order":
        total = doc.get("grand_total") or 0
        if total > 500000:
            return 10
        if total > 100000:
            return 8
        return 6
    if dt in ("BEI Incident Report", "BEI Notice to Explain", "BEI Notice of Decision"):
        return 8

    # Cancellations are always notable
    if event_type == "cancel":
        return 7

    # Medium-impact
    if dt in ("Leave Application", "BEI Store Closing Report"):
        return 6
    if dt in ("Salary Slip", "Payroll Entry"):
        return 6
    if dt in ("BEI Maintenance Request", "BEI Cycle Count"):
        return 5
    if dt in ("BEI Store Order", "BEI Goods Receipt", "BEI Purchase Requisition"):
        return 5

    # Low-impact routine
    if dt in ("Attendance", "Shift Assignment"):
        return 2
    if dt in ("Leave Ledger Entry", "Leave Allocation"):
        return 3

    return 5  # default


def _slim_doc_dict(doc):
    """Return a size-limited document snapshot for event_data."""
    raw = doc.as_dict()
    slimmed = {
        k: v for k, v in raw.items()
        if k not in EXCLUDE_FIELDS and not k.startswith("_")
    }
    # Limit keys to prevent bloat
    if len(slimmed) > MAX_EVENT_DATA_KEYS:
        slimmed = dict(list(slimmed.items())[:MAX_EVENT_DATA_KEYS])
    return slimmed


def on_event(doc, event_type):
    """Main hook handler — called by Frappe doc_events.

    Ignores unknown DocTypes silently. Enqueues async POST
    to Supabase Edge Function for known DocTypes.
    """
    dt = doc.doctype
    if dt not in DOCTYPE_MAP:
        return  # Unknown DocType — ignore silently

    clean_event = HOOK_EVENT_MAP.get(event_type, event_type)
    mapping = DOCTYPE_MAP[dt]
    content = generate_content_summary(doc, clean_event)
    importance = calculate_importance(doc, clean_event)
    skip_embedding = dt in SKIP_EMBEDDING_DOCTYPES

    payload = {
        "doctype": dt,
        "docname": doc.name,
        "event_type": clean_event,
        "domain": mapping["domain"],
        "flow": mapping["flow"],
        "content": content,
        "importance_score": importance,
        "actor": frappe.session.user,
        "event_data": _slim_doc_dict(doc),
        "embedding_skipped": skip_embedding,
        "hook_version": "1.0",
    }

    enqueue(
        "hrms.utils.brain_sync.post_to_supabase",
        payload=payload,
        queue="short",
        timeout=30,
    )


def post_to_supabase(payload):
    """Background job: POST event to Supabase Edge Function.

    On failure, logs to Frappe Error Log for monitoring.
    Future: write to BEI Brain Sync Queue for retry.
    """
    supabase_url = frappe.conf.get("brain_supabase_url")
    supabase_key = frappe.conf.get("brain_supabase_service_key")

    if not supabase_url or not supabase_key:
        frappe.log_error(
            "BEI Brain: Missing Supabase config in site_config.json. "
            "Required: brain_supabase_url, brain_supabase_service_key",
            "brain_sync",
        )
        return

    try:
        resp = requests.post(
            f"{supabase_url}/functions/v1/ingest-frappe-event",
            json=payload,
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        frappe.log_error(
            f"BEI Brain sync timeout for {payload['doctype']} {payload['docname']}",
            "brain_sync",
        )
    except Exception as e:
        frappe.log_error(
            f"BEI Brain sync failed for {payload['doctype']} {payload['docname']}: {e}",
            "brain_sync",
        )


def health_check():
    """POST-deploy smoke test endpoint.
    Call: bench execute hrms.utils.brain_sync.health_check
    """
    configured_doctypes = len(DOCTYPE_MAP)
    skip_embed_count = len(SKIP_EMBEDDING_DOCTYPES)
    has_supabase = bool(
        frappe.conf.get("brain_supabase_url")
        and frappe.conf.get("brain_supabase_service_key")
    )
    return {
        "status": "ok",
        "configured_doctypes": configured_doctypes,
        "skip_embedding_doctypes": skip_embed_count,
        "supabase_configured": has_supabase,
        "hook_version": "1.0",
    }
