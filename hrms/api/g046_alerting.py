"""GAP-046 alert payload helpers.

This module is intentionally framework-light so payload shape and forced-failure
behavior can be unit-tested without a running Frappe site.
"""

from __future__ import annotations

import json


G046_ALERT_SCHEMA_VERSION = "1.0"
G046_ALERT_ACTIONS = [
    "Validate BKI/BEI internal customer-supplier mapping.",
    "Retry _create_intercompany_invoices_async for this Stock Entry.",
    "Verify both Sales Invoice and Purchase Invoice are submitted.",
]


def normalize_store_info(store_info):
    """Return deterministic store info structure for GAP-046 payloads."""
    data = store_info or {}
    return {
        "store_type": data.get("store_type") or "",
        "department": data.get("department") or "",
        "customer": data.get("customer") or "",
        "warehouse_name": data.get("warehouse_name") or "",
    }


def get_force_failure_stage(store_info):
    """Resolve optional forced-failure stage from store_info test hooks."""
    if not isinstance(store_info, dict):
        return ""
    return (
        store_info.get("force_failure_stage")
        or store_info.get("_force_failure_stage")
        or store_info.get("__force_failure_stage")
        or ""
    ).strip()


def maybe_raise_forced_failure(force_failure_stage, stage):
    """Raise deterministic forced failure exception for tests/verification."""
    if not force_failure_stage:
        return
    if force_failure_stage in ("*", "any", "always", stage):
        raise RuntimeError(f"GAP-046 forced failure at stage={stage}")


def build_failure_alert_payload(
    *,
    stock_entry_name,
    stage,
    error,
    store_info=None,
    sales_invoice_name="",
    purchase_invoice_name="",
    forced_failure_stage="",
    target_company="",
):
    """Build deterministic GAP-046 alert payload."""
    error_text = str(error or "unknown_error")
    error_type = type(error).__name__ if error else "Error"
    normalized_store_info = normalize_store_info(store_info)

    return {
        "schema_version": G046_ALERT_SCHEMA_VERSION,
        "event": "intercompany_invoice_failure",
        "gap_id": "GAP-046",
        "flow_id": "G-046",
        "severity": "high",
        "trace_id": f"G046::{stock_entry_name}",
        "stock_entry_name": stock_entry_name or "",
        "stage": stage or "",
        "forced_failure": bool(forced_failure_stage),
        "forced_failure_stage": forced_failure_stage or "",
        "documents": {
            "sales_invoice": sales_invoice_name or "",
            "purchase_invoice": purchase_invoice_name or "",
        },
        "store": normalized_store_info,
        "companies": {
            "source_company": "Bebang Kitchen Inc.",
            "target_company": target_company or "",
        },
        "error": {
            "type": error_type,
            "message": error_text[:500],
        },
        "actions": list(G046_ALERT_ACTIONS),
    }


def serialize_alert_payload(payload):
    """Return deterministic JSON serialization for logging/transmission."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_failure_alert_message(payload):
    """Build actionable Google Chat message with traceable context."""
    docs = payload.get("documents", {})
    store = payload.get("store", {})
    err = payload.get("error", {})

    lines = [
        "*GAP-046 Inter-company Invoice Failure*",
        f"Trace: `{payload.get('trace_id')}`",
        f"Stock Entry: `{payload.get('stock_entry_name')}`",
        f"Stage: `{payload.get('stage')}`",
        f"Sales Invoice: `{docs.get('sales_invoice') or 'N/A'}`",
        f"Purchase Invoice: `{docs.get('purchase_invoice') or 'N/A'}`",
        f"Store Type: `{store.get('store_type') or 'N/A'}` | Warehouse: `{store.get('warehouse_name') or 'N/A'}`",
        f"Error: `{err.get('type')}` - {err.get('message')}",
        "",
        "*Action Checklist*",
        "1. Validate BKI/BEI internal customer-supplier mapping.",
        "2. Retry `_create_intercompany_invoices_async` for this stock entry.",
        "3. Confirm SI + PI are both submitted.",
        "",
        f"Payload JSON: `{serialize_alert_payload(payload)}`",
    ]
    return "\n".join(lines)


def emit_failure_alert(payload, *, log_error, send_chat_message):
    """Emit payload to error log and chat via injected side effects."""
    payload_json = serialize_alert_payload(payload)
    log_error(payload_json, "GAP-046 Failure Alert Payload")
    send_chat_message(build_failure_alert_message(payload))
    return payload_json
