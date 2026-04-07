"""Mosaic POS webhook receiver -- handles order.cancelled events.

Per S169 plan: the webhook handler is the ONLY writer of `cancelled_at` and
`cancellation_reason` columns on pos_orders (along with the nightly verify
script's tombstone_extras path). The hourly poller never touches these
columns -- see Design Rationale decision #9 for the full rationale.

When a cancel event arrives, this handler:
  1. Parses the JSON body using the canonical BEI pattern (get_data + json.loads)
  2. Round-trip confirms against Mosaic's GET /api/v1/orders/{id} -- expects 404
     (Path B auth, per T0.5 outcome: Mosaic webhook docs do not document signing)
  3. Atomically updates the pos_orders row: cancelled_at + cancellation_reason
     + order_status='CANCELLED', guarded by WHERE cancelled_at IS NULL
  4. Returns HTTP 200 on success, HTTP 500 on Supabase failure (so Mosaic retries)

See docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md
"""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import frappe
import requests

from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supabase import supabase_query_sql


# Production Mosaic base URL per docs/api/MOSAIC_API.md (Section 1).
# Staging is https://stg-api.mosaicpos.com -- override via env if needed.
MOSAIC_API_BASE = os.environ.get("MOSAIC_API_BASE", "https://api.mosaic-pos.com")

# Mosaic credential CSV (SSOT for client_id/client_secret per location_id).
MOSAIC_KEYS_CSV = (
    Path(frappe.get_app_path("hrms")).parent
    / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"
)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
    """Handle inbound Mosaic webhooks (primarily order.cancelled).

    Returns:
        dict with `ok: bool` and either `handled: bool` + `order_id` on success
        or `reason` + optional error fields on failure.
    """
    # DM-7: observability context MUST be the first meaningful line.
    set_backend_observability_context(
        module="sync_verification",
        action="mosaic_webhook_receive",
        mutation_type="update",
    )

    # BLOCKER 4: canonical BEI JSON parse pattern (see hrms/api/esignature.py).
    # DO NOT use frappe.request.get_json() -- it does not exist in this codebase.
    raw_body = frappe.request.get_data(as_text=True)
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError as e:
        frappe.log_error(
            title="Mosaic webhook invalid JSON",
            message=f"body_snippet={raw_body[:200]} error={e}",
        )
        frappe.local.response.http_status_code = 400
        return {"ok": False, "reason": "invalid_json"}

    event = (payload.get("event") or "").strip()
    data = payload.get("data") or {}

    # Mosaic may send a registration ping; treat as a no-op success.
    if event == "ping":
        return {"ok": True, "handled": False, "reason": "ping"}

    if event != "order.cancelled":
        # We only subscribe to order.cancelled. Any other event is a mis-registration.
        return {"ok": True, "handled": False, "reason": f"ignored event: {event}"}

    order_id = data.get("id")
    if not order_id:
        frappe.local.response.http_status_code = 400
        return {"ok": False, "reason": "missing order id"}

    # Path B auth (T0.5 outcome): Mosaic does not sign webhooks, so verify the
    # claim by calling GET /api/v1/orders/{id} and only proceeding on HTTP 404.
    if not _authenticate_webhook(order_id, data):
        frappe.log_error(
            title="Mosaic webhook auth failed",
            message=f"order_id={order_id} event={event}",
        )
        frappe.local.response.http_status_code = 401
        return {"ok": False, "reason": "round_trip_confirm_failed", "order_id": order_id}

    # Prefer Mosaic's authoritative timestamp; wall-clock fallback only if absent.
    cancelled_at = data.get("cancelled_at") or datetime.now(timezone.utc).isoformat()
    reason = (data.get("cancellation_reason") or "mosaic_webhook_missing_reason")[:500]

    # HIGH 8: wrap Supabase write in try/except. Return 500 on failure so Mosaic
    # retries instead of silently marking the event delivered.
    try:
        result = supabase_query_sql(
            """
            UPDATE pos_orders
               SET cancelled_at = %s,
                   cancellation_reason = %s,
                   order_status = 'CANCELLED'
             WHERE id = %s
               AND cancelled_at IS NULL
            RETURNING id, location_id, business_date
            """,
            (cancelled_at, reason, int(order_id)),
        )
    except Exception as e:
        frappe.log_error(
            title="Mosaic webhook Supabase UPDATE failed",
            message=f"order_id={order_id} cancelled_at={cancelled_at} error={str(e)[:500]}",
        )
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        frappe.local.response.http_status_code = 500
        return {"ok": False, "reason": "supabase_update_failed", "order_id": order_id}

    if not result:
        # Either: (a) already tombstoned by a prior webhook/verify run, or
        # (b) order_id does not exist in pos_orders. Both are idempotent no-ops.
        return {
            "ok": True,
            "handled": False,
            "reason": "already_tombstoned_or_not_found",
            "order_id": order_id,
        }

    row = result[0] if isinstance(result, list) and result else {}
    frappe.logger().info(
        f"S169 mosaic webhook: tombstoned order_id={order_id} "
        f"loc={row.get('location_id')} date={row.get('business_date')} reason={reason[:60]}"
    )
    return {"ok": True, "handled": True, "order_id": order_id}


def _authenticate_webhook(order_id, data: dict) -> bool:
    """Path B round-trip confirm.

    Look up the credential row for ``data.location_id`` in the Mosaic CSV,
    obtain an OAuth token, and call ``GET /api/v1/orders/{order_id}``. Returns
    True only if Mosaic responds with HTTP 404 (confirming the order really
    was cancelled). Any other status (200, 401, 500, network error) is treated
    as auth failure -- the webhook will be rejected and Mosaic will retry.
    """
    location_id = data.get("location_id")
    if not location_id:
        return False

    cred = _find_credential(location_id)
    if not cred:
        return False

    token = _ensure_oauth_token(cred)
    if not token:
        return False

    try:
        r = requests.get(
            f"{MOSAIC_API_BASE}/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException:
        return False

    return r.status_code == 404


def _find_credential(location_id) -> dict:
    """Look up the credential row for a given Mosaic location_id from the CSV SSOT."""
    if not MOSAIC_KEYS_CSV.exists():
        return {}
    target = str(location_id).strip()
    try:
        with MOSAIC_KEYS_CSV.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("Mosaic Location ID", "")).strip() == target:
                    return row
    except Exception:
        return {}
    return {}


def _ensure_oauth_token(cred: dict):
    """OAuth client_credentials grant for one Mosaic credential row.

    Returns the bearer token string on success, or None on any failure.
    No caching here -- webhook traffic is low and tokens are cheap.
    """
    cid = (cred.get("Mosaic Client ID") or "").strip()
    secret = (cred.get("Mosaic Client Secret") or "").strip()
    if not cid or not secret:
        return None
    try:
        r = requests.post(
            f"{MOSAIC_API_BASE}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": cid,
                "client_secret": secret,
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("access_token")
    except requests.RequestException:
        return None
