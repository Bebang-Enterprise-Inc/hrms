"""
Sync online/web orders from Superadmin API to Supabase web_orders table.

Usage:
    python scripts/sync_web_to_supabase.py --start-date 2025-10-01 --end-date 2026-02-13
    python scripts/sync_web_to_supabase.py --daily  # yesterday only

Data flow:
    Superadmin API (GET /api/online-orders) -> Supabase web_orders + web_order_items

Auth:
    - Superadmin: x-api-key header
    - Supabase: service role key from Doppler
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ─── Logging ────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent / "scratchpad"
LOG_FILE = LOG_DIR / "web_sync_log.txt"


def log(msg):
    """Print and log to file with flush."""
    print(msg, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass  # CI environments may not have scratchpad dir

# ─── Configuration ───────────────────────────────────────────────────────────

SUPERADMIN_URL = "https://superadmin.bebang.ph"
def _get_superadmin_key() -> str:
    """Get Superadmin API key from env var, then Doppler fallback."""
    key = os.environ.get("SUPERADMIN_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", "SUPERADMIN_STORES_API_KEY",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    log("ERROR: SUPERADMIN_API_KEY not set and Doppler unavailable")
    sys.exit(1)


SUPERADMIN_API_KEY = ""  # Resolved in main()

SUPABASE_URL = "https://csnniykjrychgajfrgua.supabase.co"

# Rate limits
SA_RATE_LIMIT_SLEEP = 2.5  # 30 req/min = 1 req per 2s, add buffer
SUPABASE_BATCH_SIZE = 50   # orders per UPSERT batch

# ─── Load tenant-to-location mapping ─────────────────────────────────────────

TENANT_MAP_FILE = Path(__file__).parent.parent / "data" / "POS_Extraction" / "mosaic_tenants.json"


def load_tenant_map():
    """Load slug -> location_id mapping from mosaic_tenants.json."""
    with open(TENANT_MAP_FILE, "r") as f:
        data = json.load(f)
    mapping = {}
    for slug, info in data.items():
        if isinstance(info, dict) and info.get("location_id"):
            mapping[slug] = {
                "location_id": info["location_id"],
                "store_name": info.get("store_name", slug),
            }
    return mapping


# ─── Platform classification ─────────────────────────────────────────────────

def classify_platform(order):
    """Determine platform from order data."""
    platform_name = (order.get("platform_name") or "").lower().strip()
    order_type = (order.get("order_type") or "").lower().strip()

    if "grab" in platform_name:
        return "GrabFood"
    if "panda" in platform_name or "foodpanda" in platform_name:
        return "FoodPanda"
    if platform_name in ("web", "website"):
        return "Website"
    if platform_name:
        return "Other"

    # Fallback: check payment mode or order type
    payment_mode = (order.get("payment_mode") or "").lower()
    if "paymongo" in payment_mode or "gcash" in payment_mode:
        return "Website"

    return "Website"  # Default for online orders endpoint


# ─── Map Superadmin order -> Supabase web_orders row ─────────────────────────

def map_order(order, tenant_map):
    """Convert Superadmin order to web_orders row."""
    store_slug = order.get("store_id", "")
    tenant_info = tenant_map.get(store_slug, {})
    location_id = tenant_info.get("location_id")

    if not location_id:
        return None, f"Unknown store slug: {store_slug}"

    # Parse dates
    created_at = order.get("created_at")
    deliver_on = order.get("deliver_on")
    business_date = None
    if deliver_on:
        try:
            business_date = datetime.fromisoformat(deliver_on.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass
    if not business_date and created_at:
        try:
            business_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            business_date = str(date.today())

    # Financial fields
    subtotal = float(order.get("subtotal") or 0)
    amount = float(order.get("amount") or 0)
    discount = float(order.get("discount") or 0)
    delivery_fee = float(order.get("deliver_rate") or 0)
    senior_discount = float(order.get("senior_discount") or 0)
    pwd_discount = float(order.get("pwd_discount") or 0)
    partner_discount = float(order.get("partner_discount") or 0)
    coupon_value = 0
    if order.get("coupon_value"):
        try:
            coupon_value = float(order["coupon_value"])
        except (ValueError, TypeError):
            pass

    total_discounts = discount + senior_discount + pwd_discount + partner_discount + coupon_value

    # VAT calculation (12% standard, from gross)
    gross_sales = amount
    net_sales = gross_sales / 1.12 if gross_sales > 0 else 0
    vat_amount = gross_sales - net_sales
    vatable_sales = net_sales
    vat_exempt = senior_discount + pwd_discount  # SC/PWD are VAT-exempt

    # Platform
    platform = classify_platform(order)

    # Payment gateway
    payment_mode = order.get("payment_mode") or ""
    payment_gateway = None
    if "paymongo" in payment_mode.lower():
        payment_gateway = "PayMongo"
    elif "cod" in payment_mode.lower() or "cash" in payment_mode.lower():
        payment_gateway = "COD"
    elif "gcash" in payment_mode.lower():
        payment_gateway = "GCash"
    elif payment_mode:
        payment_gateway = payment_mode

    # Map payment status
    order_status = (order.get("order_status") or "").lower()
    payment_status_raw = (order.get("payment_status") or "").lower()
    if payment_status_raw == "paid" and order_status not in ("cancelled", "canceled"):
        payment_status = "PAID"
    elif order_status in ("cancelled", "canceled"):
        payment_status = "CANCELLED"
    else:
        payment_status = "PENDING"

    # External reference
    ref_order_id = order.get("ref_order_id") or order.get("order_id") or ""

    row = {
        "id": order["id"],
        "location_id": location_id,
        "business_date": business_date,
        "platform": platform,
        "reference_id": str(ref_order_id)[:100],
        "aggregator_order_id": order.get("order_id"),
        "original_gross_sales": gross_sales,
        "gross_sales": gross_sales,
        "net_sales": round(net_sales, 2),
        "vatable_sales": round(vatable_sales, 2),
        "vat_amount": round(vat_amount, 2),
        "vat_exempt_sales": round(vat_exempt, 2),
        "zero_rated_sales": 0,
        "total_discounts": round(total_discounts, 2),
        "delivery_fee": delivery_fee,
        "payment_status": payment_status,
        "payment_gateway": payment_gateway,
        "order_datetime": created_at,
        "delivery_datetime": deliver_on,
    }
    return row, None


def map_order_items(order, web_order_id):
    """Convert order items to web_order_items rows."""
    items = order.get("order_item") or []
    rows = []
    for idx, item in enumerate(items):
        price = float(item.get("price") or item.get("actual_price") or 0)
        qty = int(item.get("quantity") or 1)
        gross = price * qty

        rows.append({
            "order_id": web_order_id,
            "product_name": item.get("item", "Unknown"),
            "quantity": qty,
            "unit_price": price,
            "gross_sales": gross,
            "net_sales": round(gross / 1.12, 2) if gross > 0 else 0,
            "vatable_sales": round(gross / 1.12, 2) if gross > 0 else 0,
            "vat_amount": round(gross - gross / 1.12, 2) if gross > 0 else 0,
        })
    return rows


# ─── Supabase helpers ────────────────────────────────────────────────────────

def get_supabase_key():
    """Get Supabase service role key from env var or Doppler."""
    # Prefer env var (for CI/GitHub Actions)
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if key:
        return key
    # Fallback to Doppler (local dev)
    try:
        result = subprocess.run(
            ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", "SUPABASE_SERVICE_ROLE_KEY",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True
        )
        key = result.stdout.strip()
    except FileNotFoundError:
        key = ""
    if not key:
        log("ERROR: Could not get SUPABASE_SERVICE_ROLE_KEY from env or Doppler")
        sys.exit(1)
    return key


def _post_with_retry(url, supabase_key, payload, prefer="return=minimal", max_retries=3):
    """POST to Supabase with retry on timeout/429/5xx."""
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }

    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)

            if r.status_code in (200, 201):
                return r, None
            elif r.status_code == 409:
                return r, None  # conflict — caller handles
            elif r.status_code == 429:
                wait = 10 * (attempt + 1)
                log(f"    429 rate limit, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            elif r.status_code >= 500:
                wait = 5 * (attempt + 1)
                log(f"    {r.status_code} server error, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            else:
                return r, f"HTTP {r.status_code}: {r.text[:300]}"

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            wait = 15 * (attempt + 1)
            log(f"    Timeout/connection error, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue

    return None, f"Failed after {max_retries} retries"


def upsert_web_orders(supabase_key, orders):
    """UPSERT batch of web_orders into Supabase."""
    if not orders:
        return 0

    r, err = _post_with_retry(
        f"{SUPABASE_URL}/rest/v1/web_orders",
        supabase_key,
        orders,
        prefer="resolution=merge-duplicates,return=minimal",
    )

    if err:
        log(f"    UPSERT orders failed: {err}")
        return 0
    return len(orders)


def upsert_web_order_items(supabase_key, items):
    """Insert web_order_items (no upsert needed — delete+insert per order)."""
    if not items:
        return 0

    r, err = _post_with_retry(
        f"{SUPABASE_URL}/rest/v1/web_order_items",
        supabase_key,
        items,
    )

    if err:
        # Non-critical: items are bonus data
        return 0
    if r and r.status_code == 409:
        return 0  # already exist
    return len(items)


# ─── Superadmin API fetch ────────────────────────────────────────────────────

def fetch_online_orders(from_date, to_date, store_id=None, page=1, per_page=100):
    """Fetch online orders from Superadmin API."""
    params = {
        "from": from_date,
        "to": to_date,
        "page": page,
        "per_page": per_page,
    }
    if store_id:
        params["store_id"] = store_id

    headers = {
        "x-api-key": SUPERADMIN_API_KEY,
        "Accept": "application/json",
    }

    r = requests.get(
        f"{SUPERADMIN_URL}/api/online-orders",
        headers=headers,
        params=params,
        timeout=60,
    )

    if r.status_code == 200:
        return r.json()
    elif r.status_code == 429:
        log(f"    SA 429 rate limit at page {page}, sleeping 30s...")
        time.sleep(30)
        r2 = requests.get(
            f"{SUPERADMIN_URL}/api/online-orders",
            headers=headers,
            params=params,
            timeout=60,
        )
        if r2.status_code == 200:
            return r2.json()
        log(f"    SA retry failed: {r2.status_code}")
        return None
    else:
        log(f"    SA API error: {r.status_code} {r.text[:300]}")
        return None


# ─── Main sync logic ─────────────────────────────────────────────────────────

def sync_date_range(start_date, end_date, supabase_key, tenant_map):
    """Sync all online orders for a date range."""
    total_orders = 0
    total_items = 0
    total_skipped = 0
    total_errors = 0

    # Fetch ALL orders for the date range (Superadmin handles date filtering)
    # Process in weekly chunks to avoid API timeouts
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=6), end_date)
        from_str = current_start.strftime("%Y-%m-%d")
        to_str = current_end.strftime("%Y-%m-%d")

        log(f"\nFetching {from_str} to {to_str}...")

        page = 1
        chunk_orders = 0
        chunk_items = 0

        while True:
            time.sleep(SA_RATE_LIMIT_SLEEP)
            result = fetch_online_orders(from_str, to_str, page=page, per_page=100)

            if result is None:
                total_errors += 1
                break

            orders_data = result.get("data", [])
            last_page = result.get("last_page", 1)
            total_in_range = result.get("total", 0)

            if page == 1:
                log(f"  Total orders in range: {total_in_range}, pages: {last_page}")

            if not orders_data:
                break

            # Map orders
            order_batch = []
            item_batch = []
            for order in orders_data:
                row, err = map_order(order, tenant_map)
                if err:
                    total_skipped += 1
                    if total_skipped <= 10:
                        log(f"    SKIP: {err}")
                    continue

                order_batch.append(row)

                # Map items
                items = map_order_items(order, order["id"])
                item_batch.extend(items)

            # UPSERT to Supabase
            if order_batch:
                inserted = upsert_web_orders(supabase_key, order_batch)
                chunk_orders += inserted

            if item_batch:
                inserted_items = upsert_web_order_items(supabase_key, item_batch)
                chunk_items += inserted_items

            # Progress every 5 pages
            if page % 5 == 0 or page >= last_page:
                log(f"    pg {page}/{last_page} -> {chunk_orders} orders so far")

            if page >= last_page:
                break
            page += 1

        log(f"  Week {from_str}-{to_str}: {chunk_orders} orders, {chunk_items} items")
        total_orders += chunk_orders
        total_items += chunk_items

        current_start = current_end + timedelta(days=1)

    return {
        "total_orders": total_orders,
        "total_items": total_items,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
    }


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync web orders from Superadmin to Supabase")
    parser.add_argument("--start-date", type=str, default="2025-10-01",
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                        help="End date (YYYY-MM-DD, default: today)")
    parser.add_argument("--daily", action="store_true",
                        help="Only sync yesterday's orders")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and map but don't write to Supabase")
    args = parser.parse_args()

    # Use PHT (UTC+8) so GH Actions runners (UTC) get the correct Philippine business date
    PHT = timezone(timedelta(hours=8))
    today_pht = datetime.now(PHT).date()

    if args.daily:
        start = today_pht - timedelta(days=1)
        end = today_pht
    else:
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date) if args.end_date else today_pht

    # Clear log file for fresh run
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        f.write("")

    log("=" * 60)
    log("Web Orders Sync: Superadmin -> Supabase")
    log("=" * 60)
    log(f"Date range: {start} to {end}")
    log(f"Days: {(end - start).days + 1}")

    # Load tenant mapping
    tenant_map = load_tenant_map()
    log(f"Tenant slugs loaded: {len(tenant_map)}")

    # Resolve secrets
    global SUPERADMIN_API_KEY
    SUPERADMIN_API_KEY = _get_superadmin_key()
    supabase_key = get_supabase_key()
    log(f"Supabase key: ...{supabase_key[-8:]}")

    if args.dry_run:
        log("\n--- DRY RUN MODE ---")

    # Quick API test
    log("\nTesting Superadmin API...")
    test = fetch_online_orders(end.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), per_page=1)
    if test is None:
        log("ERROR: Superadmin API unreachable")
        sys.exit(1)
    log(f"  API OK. {test.get('total', 0)} orders today.")

    # Run sync
    log("\nStarting sync...")
    t0 = time.time()

    if args.dry_run:
        # Just fetch and count
        result = fetch_online_orders(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            per_page=1
        )
        if result:
            log(f"Would sync {result.get('total', 0)} orders")
        return

    result = sync_date_range(start, end, supabase_key, tenant_map)

    elapsed = time.time() - t0
    log("\n" + "=" * 60)
    log("SYNC COMPLETE")
    log("=" * 60)
    log(f"Orders synced:  {result['total_orders']:,}")
    log(f"Items synced:   {result['total_items']:,}")
    log(f"Skipped:        {result['total_skipped']:,}")
    log(f"Errors:         {result['total_errors']:,}")
    log(f"Duration:       {elapsed:.0f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    main()
