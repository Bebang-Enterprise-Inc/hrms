"""
Documenso integration for BEI ERP.

Sends documents for signature collection via Documenso API.
Webhook handling for signature completion events.
"""

import json
import requests
import frappe
from frappe.utils import get_url
from typing import List, Dict, Any


DOCUMENSO_BASE_URL = "https://sign.bebang.ph/api/v1"


def get_api_token() -> str:
    """Fetch Documenso API token from Doppler."""
    token = frappe.conf.get("documenso_api_token")
    if not token:
        # Fallback: fetch from Doppler
        import subprocess
        result = subprocess.run(
            ["doppler", "secrets", "get", "DOCUMENSO_API_TOKEN", "--plain"],
            capture_output=True,
            text=True,
            cwd="."
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            frappe.conf["documenso_api_token"] = token
        else:
            frappe.throw("Documenso API token not found in Doppler")
    return token


def send_document_for_signing(
    document_name: str,
    recipients: List[Dict[str, str]],
    file_path: str,
    subject: str = None,
    message: str = None,
) -> Dict[str, Any]:
    """
    Send a document for signing via Documenso.

    Args:
        document_name: Name of the document in Frappe (for webhook tracking)
        recipients: List of dicts with 'email' and 'name' keys
        file_path: Full path to PDF file
        subject: Email subject
        message: Email message body

    Returns:
        Dict with 'document_id', 'token', 'signing_url'

    Example:
        >>> send_document_for_signing(
        ...     "Employment Contract - John Doe",
        ...     [{"email": "john@example.com", "name": "John Doe"}],
        ...     "/tmp/contract.pdf",
        ...     subject="Please sign your employment contract"
        ... )
    """

    token = get_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Step 1: Create document
    frappe.logger().info(f"[Documenso] Creating document: {document_name}")

    with open(file_path, "rb") as f:
        files = {
            "file": ("document.pdf", f, "application/pdf"),
            "name": (None, document_name),
            "teamId": (None, str(get_team_id())),  # Team BEI
        }

        response = requests.post(
            f"{DOCUMENSO_BASE_URL}/documents",
            headers={"Authorization": headers["Authorization"]},
            files=files,
        )

    if response.status_code != 201:
        frappe.throw(
            f"Failed to create Documenso document: {response.status_code} - {response.text}"
        )

    doc_data = response.json()
    documenso_id = doc_data.get("id")

    frappe.logger().info(f"[Documenso] Document created: {documenso_id}")

    # Step 2: Add recipients (signers)
    signing_fields = []
    for i, recipient in enumerate(recipients):
        signing_fields.append({
            "email": recipient["email"],
            "name": recipient["name"],
            "role": "SIGNER",
            "signingOrder": i + 1,
        })

    recipient_payload = {
        "documentId": documenso_id,
        "recipients": signing_fields,
    }

    frappe.logger().info(f"[Documenso] Adding {len(signing_fields)} recipients")

    response = requests.post(
        f"{DOCUMENSO_BASE_URL}/documents/{documenso_id}/recipients",
        headers=headers,
        json=recipient_payload,
    )

    if response.status_code != 201:
        frappe.throw(
            f"Failed to add recipients: {response.status_code} - {response.text}"
        )

    recipients_data = response.json()

    # Step 3: Send document for signing
    send_payload = {
        "documentId": documenso_id,
        "email": {
            "subject": subject or f"Please sign: {document_name}",
            "message": message or "You have a document to sign.",
        },
        "meta": {
            "frappe_document": document_name,
            "frappe_timestamp": frappe.utils.now(),
        },
    }

    frappe.logger().info(f"[Documenso] Sending document for signing")

    response = requests.post(
        f"{DOCUMENSO_BASE_URL}/documents/{documenso_id}/send",
        headers=headers,
        json=send_payload,
    )

    if response.status_code != 200:
        frappe.throw(
            f"Failed to send document: {response.status_code} - {response.text}"
        )

    send_data = response.json()

    # Store Documenso reference in Frappe
    result = {
        "documenso_id": documenso_id,
        "token": send_data.get("token"),
        "signing_url": f"https://sign.bebang.ph/document/{documenso_id}/{send_data.get('token')}",
        "recipients": [r["email"] for r in signing_fields],
    }

    frappe.logger().info(f"[Documenso] Document sent: {result['signing_url']}")

    return result


def get_team_id() -> str:
    """Get Documenso Team ID for 'BEI' team."""
    # Hardcoded for now (Team BEI = 3), but could be fetched from DB
    return "3"


@frappe.whitelist()
def get_document_status(documenso_id: str) -> Dict[str, Any]:
    """Fetch document signing status from Documenso."""
    token = get_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = requests.get(
        f"{DOCUMENSO_BASE_URL}/documents/{documenso_id}",
        headers=headers,
    )

    if response.status_code != 200:
        frappe.throw(f"Failed to fetch document: {response.status_code}")

    return response.json()


@frappe.whitelist(allow_guest=True)
def webhook_document_signed():
    """
    Handle Documenso webhook for document signing events.

    Documenso sends POST to:
    /api/method/hrms.api.documenso.webhook_document_signed

    Payload:
    {
        "event": "document.completed",
        "data": {
            "documentId": "...",
            "meta": {"frappe_document": "..."}
        }
    }
    """

    try:
        payload = json.loads(frappe.request.get_data(as_text=True))
    except:
        frappe.logger().error("Invalid webhook payload")
        return {"status": "error"}

    event = payload.get("event")
    data = payload.get("data", {})
    documenso_id = data.get("documentId")
    frappe_doc = data.get("meta", {}).get("frappe_document")

    frappe.logger().info(f"[Documenso Webhook] Event: {event}, Doc: {frappe_doc}")

    if event == "document.completed" and frappe_doc:
        # Document was fully signed - update Frappe record
        try:
            doc = frappe.get_doc(frappe_doc)
            if hasattr(doc, "documenso_status"):
                doc.documenso_status = "Signed"
                doc.documenso_id = documenso_id
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                frappe.logger().info(f"[Documenso] Updated Frappe doc: {frappe_doc}")
        except Exception as e:
            frappe.logger().error(f"[Documenso] Error updating Frappe: {str(e)}")

    return {"status": "ok"}
