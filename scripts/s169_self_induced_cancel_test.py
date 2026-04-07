"""S169 T0.5 / T8.7 — Self-induced Mosaic order create+cancel webhook test.

Picks the smallest credential group, creates a tiny test order with a marked
bill_number, immediately cancels it, then waits for the cancellation to
propagate to Supabase via the deployed Frappe webhook receiver.

Modes:
  --mode probe   T0.5 phase 0 probe -- target webhook.site (--webhook-url required)
  --mode verify  T8.7 live test -- target the deployed Frappe endpoint

Usage:
    python scripts/s169_self_induced_cancel_test.py --mode probe \
        --webhook-url https://webhook.site/<uuid>
    python scripts/s169_self_induced_cancel_test.py --mode verify

Code only -- do NOT execute against live Mosaic without explicit Sam approval.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOSAIC_BASE_URL = "https://api.mosaic-pos.com"
MOSAIC_TOKEN_URL = f"{MOSAIC_BASE_URL}/oauth/token"
MOSAIC_ORDERS_URL = f"{MOSAIC_BASE_URL}/api/v1/orders"
MOSAIC_PRODUCTS_URL = f"{MOSAIC_BASE_URL}/api/v1/products"

REPO_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_CSV = REPO_ROOT / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"

OUT_DIR = REPO_ROOT / "output" / "l3" / "s169"
ORDER_ID_FILE = OUT_DIR / "self_induced_test_order_id.txt"
PAYLOAD_FILE = OUT_DIR / "webhook_live_test_payload.json"
RESPONSE_FILE = OUT_DIR / "webhook_live_test_response.json"

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co"
)

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "BEI-S169-WebhookProbe/1.0",
    "X-Source": "s169",
}

REQUEST_TIMEOUT = 30
POLL_TIMEOUT = 60  # seconds
POLL_INTERVAL = 5  # seconds

TEST_BILL_NUMBER_PROBE = "999991"
TEST_BILL_NUMBER_VERIFY = "999992"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Doppler secrets
# ---------------------------------------------------------------------------


def get_doppler_secret(key: str) -> str:
    """Fetch secret from Doppler bei-erp/dev (headless on Windows)."""
    val = os.environ.get(key, "")
    if val:
        return val
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            [
                "C:/Users/Sam/bin/doppler.exe",
                "secrets",
                "get",
                key,
                "--plain",
                "--project",
                "bei-erp",
                "--config",
                "dev",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=creationflags,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        log(f"  [DOPPLER_ERROR] {key}: {exc}")
    return ""


# ---------------------------------------------------------------------------
# Credential selection
# ---------------------------------------------------------------------------


def pick_smallest_group() -> dict:
    """Return the credential group with the fewest locations.

    Prefer 'Dedicated' single-store groups when available.
    """
    groups: dict[str, dict] = {}
    with open(CREDENTIALS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("Mosaic Client ID") or "").strip()
            if not cid:
                continue
            if cid not in groups:
                groups[cid] = {
                    "client_id": cid,
                    "client_secret": (row.get("Mosaic Client Secret") or "").strip(),
                    "group_name": (row.get("Credential Group") or "").strip(),
                    "locations": [],
                }
            loc_id = (row.get("Mosaic Location ID") or "").strip()
            if loc_id:
                groups[cid]["locations"].append(
                    {
                        "location_id": int(loc_id),
                        "store_name": (row.get("Store Name") or "").strip(),
                    }
                )

    candidates = list(groups.values())
    # Prefer Dedicated single-store
    dedicated = [g for g in candidates if "Dedicated" in g["group_name"] and len(g["locations"]) == 1]
    if dedicated:
        return dedicated[0]
    candidates.sort(key=lambda g: len(g["locations"]))
    return candidates[0]


# ---------------------------------------------------------------------------
# Mosaic API
# ---------------------------------------------------------------------------


def get_access_token(client_id: str, client_secret: str) -> str:
    r = requests.post(
        MOSAIC_TOKEN_URL,
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        headers=DEFAULT_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("OAuth response missing access_token")
    return token


def fetch_first_product(token: str, location_id: int) -> dict | None:
    """Look up any product available at this location for the test line."""
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    try:
        r = requests.get(
            MOSAIC_PRODUCTS_URL,
            headers=headers,
            params={"filter[location_id]": location_id, "page[size]": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else body
        if data:
            return data[0]
    except Exception as exc:
        log(f"  [PRODUCT_LOOKUP_WARN] {exc}")
    return None


def create_test_order(
    token: str,
    location_id: int,
    bill_number: str,
    reason_tag: str,
) -> dict:
    """POST a tiny ₱1 test order. Falls back gracefully if product lookup fails."""
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    business_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    item: dict = {
        "name": f"S169 test {reason_tag}",
        "price": 1.00,
        "quantity": 1,
        "gross_sales": 1.00,
        "net_sales": 0.8929,
        "vatable_sales": 0.8929,
        "vat_amount": 0.1071,
        "vat_exempt_sales": 0,
        "zero_rated_sales": 0,
        "discount_amount": 0,
        "modifiers": [],
        "discount": None,
    }

    product = fetch_first_product(token, location_id)
    if product:
        if product.get("sku"):
            item["product_sku"] = product["sku"]
        if product.get("id"):
            item["product_id"] = product["id"]
        if product.get("name"):
            item["name"] = product["name"]

    body = {
        "location_id": location_id,
        "bill_number": bill_number,
        "business_date": business_date,
        "ordered_at": now_iso,
        "price_breakdown": {
            "gross_sales": 1.00,
            "net_sales": 0.8929,
            "vatable_sales": 0.8929,
            "vat_amount": 0.1071,
            "vat_exempt_sales": 0,
            "zero_rated_sales": 0,
            "total_discounts": 0,
            "delivery_fee": 0,
        },
        "items": [item],
        "payment_details": [
            {"payment_type": "Cash", "paid_amount": 1.00, "returned_amount": 0}
        ],
    }

    r = requests.post(MOSAIC_ORDERS_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
    if r.status_code >= 400:
        # Fallback: try without items in case Mosaic rejects synthetic items
        log(f"  [CREATE_WARN] {r.status_code} -- retrying without items")
        body.pop("items", None)
        r = requests.post(MOSAIC_ORDERS_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return {"request": body, "response": r.json(), "status": r.status_code}


def cancel_order(token: str, order_id: int, reason: str) -> dict:
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    url = f"{MOSAIC_BASE_URL}/api/v1/orders/{order_id}/cancel"
    body = {"reason": reason}
    r = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return {"request": body, "response": r.json() if r.text else {}, "status": r.status_code}


# ---------------------------------------------------------------------------
# Supabase verification
# ---------------------------------------------------------------------------


def poll_supabase_for_cancellation(order_id: int) -> dict | None:
    """Poll PostgREST until cancelled_at IS NOT NULL or POLL_TIMEOUT elapses."""
    service_key = get_doppler_secret("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        log("  [SUPABASE_ERROR] SUPABASE_SERVICE_ROLE_KEY not available")
        return None

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
    }
    url = f"{SUPABASE_URL}/rest/v1/pos_orders"
    params = {
        "id": f"eq.{order_id}",
        "select": "id,cancelled_at,cancellation_reason,order_status",
    }

    deadline = time.time() + POLL_TIMEOUT
    last: dict | None = None
    while time.time() < deadline:
        try:
            r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                rows = r.json()
                if rows:
                    last = rows[0]
                    if last.get("cancelled_at"):
                        log(f"  [SUPABASE] cancelled_at={last['cancelled_at']}")
                        return last
        except Exception as exc:
            log(f"  [SUPABASE_POLL_WARN] {exc}")
        time.sleep(POLL_INTERVAL)
    return last


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="S169 self-induced Mosaic cancel test")
    parser.add_argument("--mode", choices=["probe", "verify"], required=True)
    parser.add_argument("--webhook-url", type=str, default=None,
                        help="webhook.site URL for probe mode (informational only)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bill_number = TEST_BILL_NUMBER_PROBE if args.mode == "probe" else TEST_BILL_NUMBER_VERIFY
    reason_tag = (
        "S169 webhook signing probe test -- safe to ignore"
        if args.mode == "probe"
        else "S169 Phase 8 live webhook test -- safe to ignore"
    )

    if args.mode == "probe" and not args.webhook_url:
        log("WARN: probe mode requires the test webhook to already be registered at webhook.site")

    group = pick_smallest_group()
    location = group["locations"][0]
    log(f"Picked credential group: {group['group_name']} ({len(group['locations'])} locations)")
    log(f"Test location: {location['store_name']} (id={location['location_id']})")
    log(f"Mode: {args.mode} | bill_number: {bill_number}")

    trace: dict = {
        "mode": args.mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "credential_group": group["group_name"],
        "location_id": location["location_id"],
        "bill_number": bill_number,
        "reason": reason_tag,
        "steps": [],
    }

    try:
        log("Step 1: OAuth")
        token = get_access_token(group["client_id"], group["client_secret"])
        trace["steps"].append({"step": "oauth", "ok": True})

        log("Step 2: create test order")
        create_result = create_test_order(token, location["location_id"], bill_number, reason_tag)
        trace["steps"].append({"step": "create_order", **create_result})

        order_obj = create_result["response"]
        if isinstance(order_obj, dict) and "data" in order_obj:
            order_obj = order_obj["data"]
        order_id = (
            order_obj.get("id")
            if isinstance(order_obj, dict)
            else None
        )
        if not order_id:
            log("FATAL: could not extract order id from create response")
            PAYLOAD_FILE.write_text(json.dumps(trace, indent=2, default=str))
            return 2

        ORDER_ID_FILE.write_text(str(order_id))
        log(f"  Created order id={order_id}")

        log("Step 3: sleep 2s, then cancel")
        time.sleep(2)
        cancel_result = cancel_order(token, int(order_id), reason_tag)
        trace["steps"].append({"step": "cancel_order", **cancel_result})
        log(f"  Cancel HTTP {cancel_result['status']}")

    except requests.HTTPError as exc:
        log(f"FATAL: Mosaic API error: {exc} -- body: {getattr(exc.response, 'text', '')[:300]}")
        trace["error"] = str(exc)
        PAYLOAD_FILE.write_text(json.dumps(trace, indent=2, default=str))
        return 2
    except Exception as exc:
        log(f"FATAL: {exc}")
        trace["error"] = str(exc)
        PAYLOAD_FILE.write_text(json.dumps(trace, indent=2, default=str))
        return 2

    log(f"Step 4: sleep 30s for webhook propagation")
    time.sleep(30)

    log("Step 5: poll Supabase for cancellation")
    supabase_state = poll_supabase_for_cancellation(int(order_id))
    trace["supabase_state"] = supabase_state
    trace["finished_at"] = datetime.now(timezone.utc).isoformat()

    PAYLOAD_FILE.write_text(json.dumps(trace, indent=2, default=str))
    RESPONSE_FILE.write_text(
        json.dumps(
            {
                "order_id": order_id,
                "supabase_state": supabase_state,
                "mode": args.mode,
            },
            indent=2,
            default=str,
        )
    )

    if supabase_state and supabase_state.get("cancelled_at"):
        log("SUCCESS: cancellation propagated to Supabase")
        return 0
    log("TIMEOUT: cancellation did not propagate within poll window")
    return 1


if __name__ == "__main__":
    sys.exit(main())
