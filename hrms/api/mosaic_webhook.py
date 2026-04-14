"""Mosaic POS webhook receiver -- handles order.cancelled and order.completed events.

S169: order.cancelled — writes cancelled_at/cancellation_reason on pos_orders
S189: order.completed — upserts pos_orders + pos_order_items with ingestion_source='webhook'
      (complements hourly poll sync for real-time BOM consumption; poll remains
      authoritative for order_status and sums since stores may have unstable internet).

Auth path:
  - Optional HMAC check via MOSAIC_WEBHOOK_SECRET env var (if set, verify X-Mosaic-Signature)
  - Path B fallback: round-trip Mosaic GET /api/v1/orders/{id}
    * order.cancelled expects HTTP 404
    * order.completed expects HTTP 200 (order exists)

See docs/plans/2026-04-13-sprint-189-realtime-bom-consumption.md (Phase 7) and
docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md (Phase 0).
"""
import csv
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import frappe
import requests

from hrms.utils.sentry import set_backend_observability_context
from hrms.utils.supabase import SUPABASE_URL, get_service_key, supabase_query_sql


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
        module="mosaic",
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

    # S189 T7.2: if MOSAIC_WEBHOOK_SECRET is set, verify HMAC signature before processing.
    # Falls back to round-trip Path B auth if no secret is configured.
    if not _verify_hmac_signature(raw_body):
        frappe.local.response.http_status_code = 401
        return {"ok": False, "reason": "hmac_signature_invalid"}

    event = (payload.get("event") or "").strip()
    data = payload.get("data") or {}

    # Mosaic may send a registration ping; treat as a no-op success.
    if event == "ping":
        return {"ok": True, "handled": False, "reason": "ping"}

    if event == "order.cancelled":
        return _handle_order_cancelled(data)
    if event == "order.completed":
        return _handle_order_completed(data)

    # Any other event is a mis-registration.
    return {"ok": True, "handled": False, "reason": f"ignored event: {event}"}


def _handle_order_cancelled(data: dict) -> dict:
    """S169: tombstone a cancelled order in pos_orders."""
    order_id = data.get("id")
    if not order_id:
        frappe.local.response.http_status_code = 400
        return {"ok": False, "reason": "missing order id"}

    # Path B auth: verify by calling GET /api/v1/orders/{id} — expect 404.
    if not _authenticate_webhook(order_id, data, expect_status=404):
        frappe.log_error(
            title="Mosaic webhook auth failed",
            message=f"order_id={order_id} event=order.cancelled",
        )
        frappe.local.response.http_status_code = 401
        return {"ok": False, "reason": "round_trip_confirm_failed", "order_id": order_id}

    cancelled_at = data.get("cancelled_at") or datetime.now(timezone.utc).isoformat()
    reason = (data.get("cancellation_reason") or "mosaic_webhook_missing_reason")[:500]

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


def _handle_order_completed(data: dict) -> dict:
    """S189 T7.4: upsert a completed order into pos_orders + pos_order_items.

    Idempotent: re-delivery of the same webhook or collision with hourly poll
    does not create duplicates. Sets ingestion_source='webhook' on pos_orders.
    """
    set_backend_observability_context(
        module="mosaic",
        action="handle_order_completed",
        mutation_type="create",
    )

    order_id = data.get("id")
    if not order_id:
        frappe.local.response.http_status_code = 400
        return {"ok": False, "reason": "missing order id"}

    # Round-trip: fetch full order from Mosaic. Expect HTTP 200.
    order = _fetch_mosaic_order(order_id, data)
    if not order:
        frappe.local.response.http_status_code = 401
        return {"ok": False, "reason": "round_trip_fetch_failed", "order_id": order_id}

    try:
        _upsert_completed_order(order)
    except Exception as e:
        frappe.log_error(
            title="Mosaic webhook order.completed upsert failed",
            message=f"order_id={order_id} error={str(e)[:500]}",
        )
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        frappe.local.response.http_status_code = 500
        return {"ok": False, "reason": "supabase_upsert_failed", "order_id": order_id}

    frappe.logger().info(
        f"S189 mosaic webhook: completed order_id={order_id} "
        f"loc={order.get('location_id')} date={order.get('business_date')}"
    )
    return {"ok": True, "handled": True, "order_id": order_id}


def _authenticate_webhook(order_id, data: dict, expect_status: int = 404) -> bool:
    """Path B round-trip confirm.

    Calls Mosaic GET /api/v1/orders/{order_id} and returns True only if the
    HTTP status matches ``expect_status``:
      - expect_status=404 for order.cancelled (order should be gone)
      - expect_status=200 for order.completed (order should exist)
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

    return r.status_code == expect_status


def _verify_hmac_signature(raw_body: str) -> bool:
    """S189 T7.2: optional HMAC signature verification.

    If MOSAIC_WEBHOOK_SECRET is set, verify the ``X-Mosaic-Signature`` header
    matches HMAC-SHA256(secret, raw_body). If the secret is not set, return
    True (fall through to Path B round-trip auth).
    """
    secret = (os.environ.get("MOSAIC_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return True  # No secret configured — skip HMAC, rely on round-trip

    try:
        provided = frappe.request.headers.get("X-Mosaic-Signature", "") or ""
    except Exception:
        return False

    if not provided:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        (raw_body or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, provided.strip())


def _fetch_mosaic_order(order_id, data: dict) -> dict:
    """S189 T7.4: round-trip fetch full order payload from Mosaic.

    Returns the order dict on HTTP 200, empty dict on any failure. Used by
    order.completed handler to get authoritative order data rather than
    trusting the webhook payload (payloads can be partial).
    """
    location_id = data.get("location_id")
    if not location_id:
        return {}

    cred = _find_credential(location_id)
    if not cred:
        return {}

    token = _ensure_oauth_token(cred)
    if not token:
        return {}

    try:
        r = requests.get(
            f"{MOSAIC_API_BASE}/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except requests.RequestException:
        return {}

    if r.status_code != 200:
        return {}

    try:
        body = r.json()
    except (ValueError, TypeError):
        return {}

    # Mosaic responses may wrap data: {data: {...}} or return the order directly
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
        return body["data"]
    if isinstance(body, dict):
        return body
    return {}


def _resolve_channel(order: dict) -> str:
    """Derive channel from Mosaic service_type_id + service_channel_id.

    Same logic as scripts/sync_pos_to_supabase.py._resolve_channel to keep the
    webhook + poll paths consistent.
    """
    channel_map = {1: "GrabFood", 2: "FoodPanda", 16: "FoodPanda", 19: "WebDelivery"}
    stype = order.get("service_type_id")
    if stype == 3:
        return channel_map.get(order.get("service_channel_id"), "Delivery")
    if stype in (91, 17):
        return "POS"
    if stype is None:
        return "Unknown"
    return "POS"


def _map_order_row(order: dict) -> dict:
    """Map a Mosaic order payload to a pos_orders row (same shape as poll sync)."""
    pb = order.get("price_breakdown") or {}
    upper_or_none = lambda v: v.upper() if isinstance(v, str) and v else None
    return {
        "id": order["id"],
        "location_id": order["location_id"],
        "business_date": order["business_date"],
        "bill_number": order.get("bill_number"),
        "receipt_number": order.get("receipt_number"),
        "pax_count": order.get("pax_count"),
        "service_type_id": order.get("service_type_id"),
        "service_channel_id": order.get("service_channel_id"),
        "channel": _resolve_channel(order),
        "original_gross_sales": pb.get("original_gross_sales", 0),
        "gross_sales": pb.get("gross_sales", 0),
        "net_sales": pb.get("net_sales", 0),
        "vatable_sales": pb.get("vatable_sales", 0),
        "vat_amount": pb.get("vat_amount", 0),
        "vat_exempt_sales": pb.get("vat_exempt_sales", 0),
        "zero_rated_sales": pb.get("zero_rated_sales", 0),
        "total_discounts": pb.get("total_discounts", 0),
        "delivery_fee": pb.get("delivery_fee", 0),
        "payment_status": upper_or_none(order.get("payment_status")),
        "order_status": upper_or_none(order.get("order_status")),
        "completed_at": order.get("completed_at"),
        "billed_at": order.get("billed_at"),
        "paid_at": order.get("paid_at"),
        # S189 T7.1: mark this row as webhook-sourced so the reconciliation
        # views can distinguish webhook vs poll ingestion.
        "ingestion_source": "webhook",
    }


def _map_order_items(order: dict) -> list[dict]:
    """Map Mosaic order items to pos_order_items rows."""
    rows = []
    for idx, item in enumerate(order.get("items") or []):
        ipb = item.get("price_breakdown") or {}
        discount = item.get("discount") or {}
        rows.append({
            "order_id": order["id"],
            "line_number": idx,
            "product_id": item.get("product_id"),
            "product_name": item.get("name") or item.get("product_name"),
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("price") or item.get("unit_price"),
            "gross_sales": item.get("gross_sales") or ipb.get("gross_sales", 0),
            "net_sales": item.get("net_sales") or ipb.get("net_sales", 0),
            "vatable_sales": item.get("vatable_sales") or ipb.get("vatable_sales", 0),
            "vat_amount": item.get("vat_amount") or ipb.get("vat_amount", 0),
            "vat_exempt_sales": item.get("vat_exempt_sales") or ipb.get("vat_exempt_sales", 0),
            "zero_rated_sales": item.get("zero_rated_sales") or ipb.get("zero_rated_sales", 0),
            "discount_id": discount.get("id"),
            "discount_name": discount.get("name"),
            "discount_amount": discount.get("amount", 0),
        })
    return rows


def _upsert_completed_order(order: dict) -> None:
    """S189 T7.4/T7.5: idempotent upsert of order + items via PostgREST.

    Uses PostgREST merge-duplicates Prefer header to deduplicate on primary key.
    Safe under burst replays (store internet recovers after outage) because:
      - pos_orders PK is id — duplicate INSERT merges
      - pos_order_items unique index on (order_id, product_id, line_number)
      - Supabase triggers use ON CONFLICT ON CONSTRAINT idx_dmc_unique
        + delta=0 short-circuit, preventing phantom consumption on re-delivery
    """
    key = get_service_key()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    order_row = _map_order_row(order)
    r_order = requests.post(
        f"{SUPABASE_URL}/rest/v1/pos_orders",
        headers=headers,
        json=[order_row],
        timeout=15,
    )
    r_order.raise_for_status()

    item_rows = _map_order_items(order)
    if item_rows:
        r_items = requests.post(
            f"{SUPABASE_URL}/rest/v1/pos_order_items",
            headers=headers,
            json=item_rows,
            timeout=15,
        )
        r_items.raise_for_status()


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
