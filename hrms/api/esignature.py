"""
BEI E-Signature Integration — Documenso webhook receiver and signing trigger API.

Endpoints:
  - webhook_receiver: Receives Documenso webhook events (allow_guest=True)
  - send_for_signature: Triggers document signing via Documenso API
  - get_signed_documents: Lists BEI Signed Document records
"""

import hashlib
import hmac
import json

import frappe
import requests
from frappe import _

from hrms.utils.sentry import set_backend_observability_context


# ---------------------------------------------------------------------------
# Webhook Receiver (Documenso → Frappe)
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook_receiver():
    """Receive and process Documenso webhook events.

    Verifies HMAC-SHA256 signature via x-documenso-signature header,
    then creates/updates BEI Signed Document records.
    """
    set_backend_observability_context(
        module="esignature",
        action="webhook_receiver",
        mutation_type="update",
    )

    # --- Signature verification ---
    webhook_secret = frappe.conf.get("documenso_webhook_secret") or frappe.get_single_value(
        "BEI Settings", "documenso_webhook_secret"
    )
    if not webhook_secret:
        webhook_secret = _get_doppler_secret("DOCUMENSO_WEBHOOK_SECRET")

    raw_body = frappe.request.get_data(as_text=True)
    received_sig = frappe.request.headers.get("x-documenso-signature", "")

    if webhook_secret and received_sig:
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, received_sig):
            frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)
    elif webhook_secret and not received_sig:
        frappe.throw(_("Missing webhook signature header"), frappe.AuthenticationError)

    # --- Parse payload ---
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        frappe.throw(_("Invalid JSON payload"))

    event = payload.get("event", "")
    data = payload.get("data", {})

    if not event or not data:
        frappe.throw(_("Missing event or data in webhook payload"))

    document_id = str(data.get("id", ""))
    if not document_id:
        return {"status": "ignored", "reason": "no document id"}

    # --- Process event ---
    if event == "DOCUMENT_COMPLETED":
        _handle_document_completed(document_id, data)
    elif event == "DOCUMENT_SENT":
        _handle_document_sent(document_id, data)
    elif event == "DOCUMENT_SIGNED":
        _handle_document_signed(document_id, data)
    elif event == "DOCUMENT_REJECTED":
        _handle_document_declined(document_id, data)
    else:
        return {"status": "ignored", "reason": f"unhandled event: {event}"}

    frappe.db.commit()
    return {"status": "ok", "event": event, "document_id": document_id}


def _handle_document_completed(document_id, data):
    """Mark document as Completed and update all signers."""
    doc = _get_or_create_signed_doc(document_id, data)
    doc.status = "Completed"
    doc.completed_at = frappe.utils.now_datetime()

    _sync_recipients(doc, data.get("recipients", []))
    doc.save(ignore_permissions=True)


def _handle_document_sent(document_id, data):
    """Mark document as Sent."""
    doc = _get_or_create_signed_doc(document_id, data)
    if doc.status == "Draft":
        doc.status = "Sent"

    _sync_recipients(doc, data.get("recipients", []))
    doc.save(ignore_permissions=True)


def _handle_document_signed(document_id, data):
    """Update individual signer status. If all signed, mark Completed."""
    doc = _get_or_create_signed_doc(document_id, data)

    recipients = data.get("recipients", [])
    _sync_recipients(doc, recipients)

    all_signed = all(
        r.get("signingStatus") == "SIGNED" for r in recipients
    ) if recipients else False

    if all_signed:
        doc.status = "Completed"
        doc.completed_at = frappe.utils.now_datetime()
    elif any(r.get("signingStatus") == "SIGNED" for r in recipients):
        doc.status = "Partially Signed"

    doc.save(ignore_permissions=True)


def _handle_document_declined(document_id, data):
    """Mark document as Declined."""
    doc = _get_or_create_signed_doc(document_id, data)
    doc.status = "Declined"

    _sync_recipients(doc, data.get("recipients", []))
    doc.save(ignore_permissions=True)


def _get_or_create_signed_doc(document_id, data):
    """Find existing BEI Signed Document by Documenso ID, or create one."""
    existing = frappe.db.get_value(
        "BEI Signed Document",
        {"documenso_document_id": document_id},
        "name",
    )

    if existing:
        return frappe.get_doc("BEI Signed Document", existing)

    doc = frappe.new_doc("BEI Signed Document")
    doc.documenso_document_id = document_id
    doc.document_title = data.get("title", "Untitled Document")
    doc.status = "Draft"
    doc.insert(ignore_permissions=True)
    return doc


def _sync_recipients(doc, recipients):
    """Sync Documenso recipients to the signers child table."""
    if not recipients:
        return

    existing_map = {
        row.documenso_recipient_id: row
        for row in doc.signers
        if row.documenso_recipient_id
    }

    for r in recipients:
        rid = str(r.get("id", ""))
        status_map = {
            "NOT_SIGNED": "Pending",
            "SENT": "Sent",
            "OPENED": "Viewed",
            "SIGNED": "Signed",
            "REJECTED": "Declined",
        }

        if rid in existing_map:
            row = existing_map[rid]
            row.signer_status = status_map.get(r.get("signingStatus", ""), "Pending")
            if r.get("signingStatus") == "SIGNED" and not row.signed_at:
                row.signed_at = frappe.utils.now_datetime()
        else:
            doc.append("signers", {
                "signer_name": r.get("name", r.get("email", "")),
                "signer_email": r.get("email", ""),
                "signer_status": status_map.get(r.get("signingStatus", ""), "Pending"),
                "documenso_recipient_id": rid,
                "signed_at": frappe.utils.now_datetime() if r.get("signingStatus") == "SIGNED" else None,
            })


# ---------------------------------------------------------------------------
# Signing Trigger API (Frappe → Documenso)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def send_for_signature(template_id, signers, document_title=None, linked_doctype=None, linked_docname=None):
    """Create a document from a Documenso template and send for signature.

    Args:
        template_id: Documenso template ID
        signers: JSON array of {name, email, role} objects
        document_title: Optional title override
        linked_doctype: Optional Frappe DocType to link
        linked_docname: Optional Frappe document name to link

    Returns:
        dict with bei_signed_document name and documenso_document_id
    """
    set_backend_observability_context(
        module="esignature",
        action="send_for_signature",
        mutation_type="create",
    )

    if isinstance(signers, str):
        signers = json.loads(signers)

    api_token = _get_documenso_api_token()
    base_url = _get_documenso_base_url()

    # Create document from template via Documenso API
    response = requests.post(
        f"{base_url}/api/v1/templates/{template_id}/create-document",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={
            "title": document_title or f"BEI Document - {frappe.utils.now()}",
            "recipients": [
                {
                    "name": s.get("name", ""),
                    "email": s["email"],
                    "role": s.get("role", "SIGNER"),
                }
                for s in signers
            ],
        },
        timeout=30,
    )

    if response.status_code not in (200, 201):
        frappe.throw(
            _("Documenso API error: {0} - {1}").format(response.status_code, response.text[:500])
        )

    result = response.json()
    documenso_doc_id = str(result.get("id", result.get("documentId", "")))

    # Send the document for signing
    send_response = requests.post(
        f"{base_url}/api/v1/documents/{documenso_doc_id}/send",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    # Create BEI Signed Document record
    bei_doc = frappe.new_doc("BEI Signed Document")
    bei_doc.document_title = document_title or f"BEI Document - {frappe.utils.now()}"
    bei_doc.documenso_document_id = documenso_doc_id
    bei_doc.status = "Sent" if send_response.status_code in (200, 201) else "Draft"
    bei_doc.document_url = f"{base_url}/documents/{documenso_doc_id}"

    if linked_doctype and linked_docname:
        bei_doc.linked_doctype = linked_doctype
        bei_doc.linked_docname = linked_docname

    for s in signers:
        bei_doc.append("signers", {
            "signer_name": s.get("name", s["email"]),
            "signer_email": s["email"],
            "signer_status": "Sent" if send_response.status_code in (200, 201) else "Pending",
        })

    bei_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "bei_signed_document": bei_doc.name,
        "documenso_document_id": documenso_doc_id,
        "status": bei_doc.status,
        "document_url": bei_doc.document_url,
    }


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_signed_documents(status=None, linked_doctype=None, linked_docname=None, limit=20):
    """List BEI Signed Document records with optional filters."""
    set_backend_observability_context(
        module="esignature",
        action="get_signed_documents",
        mutation_type="read",
    )

    filters = {}
    if status:
        filters["status"] = status
    if linked_doctype:
        filters["linked_doctype"] = linked_doctype
    if linked_docname:
        filters["linked_docname"] = linked_docname

    docs = frappe.get_all(
        "BEI Signed Document",
        filters=filters,
        fields=[
            "name", "document_title", "status", "documenso_document_id",
            "completed_at", "document_url", "linked_doctype", "linked_docname",
            "creation", "modified",
        ],
        order_by="modified desc",
        limit_page_length=int(limit),
    )

    return docs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_documenso_api_token():
    """Get Documenso API token from site config or Doppler."""
    token = frappe.conf.get("documenso_api_token")
    if not token:
        token = _get_doppler_secret("DOCUMENSO_API_TOKEN")
    if not token:
        frappe.throw(_("Documenso API token not configured"))
    return token


def _get_documenso_base_url():
    """Get Documenso instance base URL."""
    url = frappe.conf.get("documenso_base_url", "https://sign.bebang.ph")
    return url.rstrip("/")


def _get_doppler_secret(key):
    """Attempt to read a secret from Doppler CLI if available."""
    import subprocess
    try:
        result = subprocess.run(
            ["doppler", "secrets", "get", key, "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
