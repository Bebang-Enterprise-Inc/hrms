"""
POS Extraction Pipeline: Mosaic POS API -> Supabase Data Lake

Pulls orders from all 45+ Bebang stores via Mosaic POS API and upserts
them into the Supabase data lake. Handles 12 credential groups (each with
its own OAuth token and 60 req/min rate limit), checkpoints per store-day
for resumability, and supports both daily cron and historical backfill.

Usage:
    python scripts/sync_pos_to_supabase.py --daily          # Yesterday only
    python scripts/sync_pos_to_supabase.py --from 2025-06-27 --to 2026-02-11
    python scripts/sync_pos_to_supabase.py --store 2338     # Single store
    python scripts/sync_pos_to_supabase.py --daily --refresh-views
"""

import argparse
import csv
import json
import os
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOSAIC_BASE_URL = "https://api.mosaic-pos.com"
MOSAIC_TOKEN_URL = f"{MOSAIC_BASE_URL}/oauth/token"
MOSAIC_ORDERS_URL = f"{MOSAIC_BASE_URL}/api/v1/orders"
MOSAIC_PAGE_SIZE = 100

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")


def _get_secret(env_name: str, doppler_name: str | None = None) -> str:
    """Get secret from env var, then Doppler fallback."""
    val = os.environ.get(env_name, "")
    if val:
        return val
    # Doppler fallback for local dev
    doppler_key = doppler_name or env_name
    try:
        import subprocess
        result = subprocess.run(
            ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", doppler_key,
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print(f"ERROR: {env_name} not set and Doppler unavailable", flush=True)
    sys.exit(1)


# Lazy-loaded secrets (resolved at runtime in main)
SUPABASE_KEY = ""
SUPABASE_MGMT_TOKEN = ""
SUPABASE_PROJECT_REF = "csnniykjrychgajfrgua"
SUPABASE_MGMT_SQL_URL = (
    f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
)

CREDENTIALS_CSV = Path(__file__).parent.parent / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"
EARLIEST_DATE = date(2025, 6, 27)  # Earliest Mosaic go-live date

# Rate limiting
REQUEST_INTERVAL = 1.2  # seconds between requests per credential group
RATE_LIMIT_WAIT = 65    # seconds to wait on HTTP 429
RETRY_WAIT = 10         # seconds between retries on 5xx / connection errors
MAX_RETRIES = 3

# Batching
UPSERT_BATCH_SIZE = 100  # records per Supabase REST API call

# Graceful shutdown flag
_shutdown_requested = False


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _handle_sigint(signum, frame):
    """Set shutdown flag on Ctrl+C so we finish the current store-day."""
    global _shutdown_requested
    if _shutdown_requested:
        # Second Ctrl+C = force exit
        log("Force exit requested.")
        sys.exit(1)
    _shutdown_requested = True
    log("Shutdown requested -- finishing current store-day then exiting.")


signal.signal(signal.SIGINT, _handle_sigint)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def load_credentials(csv_path: Path) -> list[dict]:
    """Load Mosaic credentials grouped by client_id.

    Returns a list of credential group dicts:
        {
            "client_id": "...",
            "client_secret": "...",
            "group_name": "...",
            "locations": [
                {"location_id": 2338, "store_name": "SM Megamall"},
                ...
            ],
            "token": None,
            "token_ts": 0,
        }
    """
    groups: dict[str, dict] = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["Mosaic Client ID"].strip()
            if not cid:
                continue
            if cid not in groups:
                groups[cid] = {
                    "client_id": cid,
                    "client_secret": row["Mosaic Client Secret"].strip(),
                    "group_name": row["Credential Group"].strip(),
                    "locations": [],
                    "token": None,
                    "token_ts": 0.0,
                }
            loc_id_str = row["Mosaic Location ID"].strip()
            if loc_id_str:
                groups[cid]["locations"].append({
                    "location_id": int(loc_id_str),
                    "store_name": row["Store Name"].strip(),
                })
    return list(groups.values())


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _supabase_headers(*, prefer: str = "") -> dict[str, str]:
    """Build standard Supabase REST API headers."""
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def supabase_upsert(client: httpx.Client, table: str, rows: list[dict],
                    on_conflict: str | None = None) -> None:
    """UPSERT rows into a Supabase table via PostgREST in batches."""
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i : i + UPSERT_BATCH_SIZE]
        for attempt in range(1, MAX_RETRIES + 1):
            r = client.post(
                url,
                headers=_supabase_headers(prefer="resolution=merge-duplicates,return=minimal"),
                json=batch,
                timeout=30,
            )
            if r.status_code in (200, 201):
                break
            if r.status_code == 429 and attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            raise RuntimeError(
                f"Supabase upsert {table} failed ({r.status_code}): {r.text[:300]}"
            )


def supabase_exec_sql(client: httpx.Client, sql: str) -> Any:
    """Execute raw SQL via the Supabase Management API."""
    r = client.post(
        SUPABASE_MGMT_SQL_URL,
        headers={
            "Authorization": f"Bearer {SUPABASE_MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=60,
    )
    if r.status_code != 201:
        raise RuntimeError(f"SQL exec error ({r.status_code}): {r.text[:300]}")
    return r.json()


def _sql_escape(value: Any) -> str:
    """Escape a value for inclusion in a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("'", "''")
    return f"'{s}'"


def upsert_items_batch(client: httpx.Client, items: list[dict]) -> None:
    """UPSERT order items via PostgREST (unique index on order_id, product_id, line_number)."""
    if not items:
        return
    supabase_upsert(client, "pos_order_items", items,
                    on_conflict="order_id,product_id,line_number")


# ---------------------------------------------------------------------------
# sync_progress helpers
# ---------------------------------------------------------------------------

def get_completed_store_days(client: httpx.Client, location_id: int,
                             start_date: date, end_date: date) -> set[str]:
    """Return set of YYYY-MM-DD strings already marked 'complete' for a store."""
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/sync_progress",
        headers=_supabase_headers(),
        params={
            "select": "business_date",
            "location_id": f"eq.{location_id}",
            "status": "eq.complete",
            "business_date": f"gte.{start_date.isoformat()}",
        },
        timeout=15,
    )
    if r.status_code != 200:
        return set()
    return {row["business_date"] for row in r.json()}


def set_sync_progress(client: httpx.Client, location_id: int,
                      business_date: str, status: str, *,
                      orders_synced: int = 0, error_message: str = ""):
    """Upsert a sync_progress row."""
    row = {
        "location_id": location_id,
        "business_date": business_date,
        "status": status,
        "orders_synced": orders_synced,
        "error_message": error_message[:500] if error_message else "",
        "synced_at": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
    }
    supabase_upsert(client, "sync_progress", [row],
                    on_conflict="location_id,business_date")


# ---------------------------------------------------------------------------
# Mosaic API helpers
# ---------------------------------------------------------------------------

def ensure_token(client: httpx.Client, cred: dict) -> str:
    """Get a valid OAuth token for the credential group, refreshing if needed."""
    if cred["token"] and (time.time() - cred["token_ts"]) < 55 * 60:
        return cred["token"]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.post(
                MOSAIC_TOKEN_URL,
                json={
                    "client_id": cred["client_id"],
                    "client_secret": cred["client_secret"],
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                cred["token"] = data["access_token"]
                cred["token_ts"] = time.time()
                return cred["token"]
            log(f"  Token request failed ({r.status_code}), attempt {attempt}/{MAX_RETRIES}")
        except httpx.RequestError as e:
            log(f"  Token request error: {e}, attempt {attempt}/{MAX_RETRIES}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT)

    raise RuntimeError(f"Failed to obtain token for {cred['group_name']}")


def fetch_orders_page(client: httpx.Client, token: str,
                      location_id: int, business_date: str,
                      page: int) -> dict:
    """Fetch one page of orders from Mosaic. Returns the full response JSON."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "filter[business_date]": business_date,
        "filter[location_id]": location_id,
        "page[number]": page,
        "page[size]": MOSAIC_PAGE_SIZE,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(
                MOSAIC_ORDERS_URL,
                headers=headers,
                params=params,
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                log(f"  Rate limited (429), waiting {RATE_LIMIT_WAIT}s ...")
                time.sleep(RATE_LIMIT_WAIT)
                continue
            if r.status_code >= 500:
                log(f"  Server error ({r.status_code}), retry {attempt}/{MAX_RETRIES}")
                time.sleep(RETRY_WAIT)
                continue
            # 4xx other than 429 - raise immediately
            raise RuntimeError(
                f"Mosaic API error {r.status_code}: {r.text[:200]}"
            )
        except httpx.RequestError as e:
            log(f"  Connection error: {e}, retry {attempt}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            raise

    raise RuntimeError("Max retries exceeded fetching orders")


def fetch_all_orders(client: httpx.Client, cred: dict,
                     location_id: int, business_date: str) -> list[dict]:
    """Fetch all orders for a store-day, handling pagination and rate limits."""
    token = ensure_token(client, cred)
    all_orders = []
    page = 1
    last_page = 1

    while page <= last_page:
        time.sleep(REQUEST_INTERVAL)
        data = fetch_orders_page(client, token, location_id, business_date, page)

        meta = data.get("meta", {})
        last_page = meta.get("last_page", 1)
        orders = data.get("data", [])
        all_orders.extend(orders)
        page += 1

    return all_orders


# ---------------------------------------------------------------------------
# Data mapping: Mosaic order -> DB records
# ---------------------------------------------------------------------------

def map_order(order: dict) -> dict:
    """Map a Mosaic order to a pos_orders row."""
    pb = order.get("price_breakdown") or {}
    return {
        "id": order["id"],
        "location_id": order["location_id"],
        "business_date": order["business_date"],
        "bill_number": order.get("bill_number"),
        "receipt_number": order.get("receipt_number"),
        "pax_count": order.get("pax_count"),
        "service_type_id": order.get("service_type_id"),
        "original_gross_sales": pb.get("original_gross_sales", 0),
        "gross_sales": pb.get("gross_sales", 0),
        "net_sales": pb.get("net_sales", 0),
        "vatable_sales": pb.get("vatable_sales", 0),
        "vat_amount": pb.get("vat_amount", 0),
        "vat_exempt_sales": pb.get("vat_exempt_sales", 0),
        "zero_rated_sales": pb.get("zero_rated_sales", 0),
        "total_discounts": pb.get("total_discounts", 0),
        "delivery_fee": pb.get("delivery_fee", 0),
        "payment_status": (order.get("payment_status") or "PAID").upper(),
        "billed_at": order.get("billed_at"),
        "paid_at": order.get("paid_at"),
    }


def map_order_items(order: dict) -> list[dict]:
    """Map Mosaic order items to pos_order_items rows."""
    rows = []
    for idx, item in enumerate(order.get("items") or []):
        ipb = item.get("price_breakdown") or {}
        discount = item.get("discount")
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
            "discount_id": discount["id"] if discount else None,
            "discount_name": discount["name"] if discount else None,
            "discount_amount": discount.get("amount", 0) if discount else 0,
            "discount_customer_first_name": discount.get("first_name") if discount else None,
            "discount_customer_last_name": discount.get("last_name") if discount else None,
            "discount_reference_number": discount.get("reference_number") if discount else None,
        })
    return rows


def map_order_payments(order: dict) -> list[dict]:
    """Map Mosaic order payments to pos_order_payments rows."""
    rows = []
    for idx, payment in enumerate(order.get("payment_methods") or order.get("payments") or []):
        rows.append({
            "order_id": order["id"],
            "line_number": idx,
            "payment_type": payment.get("payment_type"),
            "paid_amount": payment.get("paid_amount", 0),
            "returned_amount": payment.get("returned_amount", 0),
        })
    return rows


# ---------------------------------------------------------------------------
# Raw JSON storage (optional)
# ---------------------------------------------------------------------------

def store_raw_orders(client: httpx.Client, orders: list[dict],
                     location_id: int, business_date: str):
    """Store the raw Mosaic JSON in pos_orders_raw for audit trail."""
    rows = []
    for order in orders:
        rows.append({
            "order_id": order["id"],
            "raw_json": json.dumps(order, default=str),
        })
    if rows:
        supabase_upsert(client, "pos_orders_raw", rows,
                        on_conflict="order_id")


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def sync_store_day(client: httpx.Client, cred: dict,
                   location_id: int, store_name: str,
                   business_date: str, *, store_raw: bool = False) -> int:
    """Sync one store-day. Returns number of orders synced."""
    # Mark in-progress
    set_sync_progress(client, location_id, business_date, "in_progress")

    try:
        orders = fetch_all_orders(client, cred, location_id, business_date)
    except Exception as e:
        set_sync_progress(client, location_id, business_date, "error",
                          error_message=str(e))
        raise

    if not orders:
        set_sync_progress(client, location_id, business_date, "complete",
                          orders_synced=0)
        return 0

    # Map and collect
    order_rows = []
    item_rows = []
    payment_rows = []
    for order in orders:
        order_rows.append(map_order(order))
        item_rows.extend(map_order_items(order))
        payment_rows.extend(map_order_payments(order))

    # Upsert into Supabase
    try:
        supabase_upsert(client, "pos_orders", order_rows,
                        on_conflict="id")
        upsert_items_batch(client, item_rows)
        supabase_upsert(client, "pos_order_payments", payment_rows,
                        on_conflict="order_id,payment_type,line_number")
        if store_raw:
            store_raw_orders(client, orders, location_id, business_date)
    except Exception as e:
        set_sync_progress(client, location_id, business_date, "error",
                          error_message=str(e))
        raise

    n = len(order_rows)
    avg_items = len(item_rows) / n if n else 0
    set_sync_progress(client, location_id, business_date, "complete",
                      orders_synced=n)
    return n


def sync_credential_group(client: httpx.Client, cred: dict,
                           start_date: date, end_date: date, *,
                           store_raw: bool = False,
                           filter_location: Optional[int] = None) -> dict:
    """Sync all locations in a credential group over the date range.

    Returns summary dict with total_orders and store_days_synced.
    """
    locations = cred["locations"]
    if filter_location:
        locations = [loc for loc in locations if loc["location_id"] == filter_location]
        if not locations:
            return {"total_orders": 0, "store_days_synced": 0, "store_days_skipped": 0}

    total_orders = 0
    store_days_synced = 0
    store_days_skipped = 0

    for loc in locations:
        location_id = loc["location_id"]
        store_name = loc["store_name"]

        # Get already-completed days for this store in the date range
        completed = get_completed_store_days(client, location_id, start_date, end_date)

        current = start_date
        consecutive_zero = 0
        SKIP_JUMP = 7  # days to jump forward after consecutive zeros
        ZERO_THRESHOLD = 3  # consecutive 0-order days before skipping

        while current <= end_date:
            if _shutdown_requested:
                log(f"Shutdown: stopping after {store_days_synced} store-days, {total_orders} orders")
                return {
                    "total_orders": total_orders,
                    "store_days_synced": store_days_synced,
                    "store_days_skipped": store_days_skipped,
                }

            ds = current.isoformat()
            if ds in completed:
                store_days_skipped += 1
                current += timedelta(days=1)
                consecutive_zero = 0  # completed days reset the zero counter
                continue

            try:
                n = sync_store_day(
                    client, cred, location_id, store_name, ds,
                    store_raw=store_raw,
                )
                total_orders += n
                store_days_synced += 1
                if n > 0:
                    log(f"  [{cred['group_name']}] {store_name} ({location_id}) {ds}: {n} orders")
                    consecutive_zero = 0
                else:
                    consecutive_zero += 1
                    # Skip forward if many consecutive 0-order days (store not yet on Mosaic)
                    if consecutive_zero >= ZERO_THRESHOLD:
                        jump = min(SKIP_JUMP, (end_date - current).days)
                        if jump > 1:
                            log(f"  [{cred['group_name']}] {store_name} ({location_id}): "
                                f"{consecutive_zero} consecutive 0-order days, jumping +{jump}d")
                            current += timedelta(days=jump)
                            consecutive_zero = 0
                            continue
            except Exception as e:
                log(f"  ERROR [{cred['group_name']}] {store_name} ({location_id}) {ds}: {e}")
                consecutive_zero = 0

            current += timedelta(days=1)

    return {
        "total_orders": total_orders,
        "store_days_synced": store_days_synced,
        "store_days_skipped": store_days_skipped,
    }


# ---------------------------------------------------------------------------
# Materialized view refresh
# ---------------------------------------------------------------------------

MATERIALIZED_VIEWS = [
    "daily_revenue",
    "discount_summary",
    "payment_reconciliation",
]


def refresh_materialized_views(client: httpx.Client):
    """Refresh all materialized views concurrently."""
    for view in MATERIALIZED_VIEWS:
        log(f"Refreshing materialized view: {view} ...")
        try:
            supabase_exec_sql(client, f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};")
            log(f"  {view} refreshed.")
        except Exception as e:
            log(f"  WARNING: Failed to refresh {view}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync Mosaic POS orders to Supabase data lake",
    )
    parser.add_argument(
        "--daily", action="store_true",
        help="Only sync yesterday's data (for daily cron)",
    )
    parser.add_argument(
        "--from", dest="from_date", type=str, default=None,
        help="Start date YYYY-MM-DD (default: 2025-06-27)",
    )
    parser.add_argument(
        "--to", dest="to_date", type=str, default=None,
        help="End date YYYY-MM-DD (default: yesterday)",
    )
    parser.add_argument(
        "--store", type=int, default=None,
        help="Only sync one store by Mosaic location_id (for testing)",
    )
    parser.add_argument(
        "--store-raw", action="store_true",
        help="Also store raw JSON in pos_orders_raw",
    )
    parser.add_argument(
        "--refresh-views", action="store_true",
        help="Refresh materialized views after sync",
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="Run credential groups in parallel (1 thread per token)",
    )
    return parser


def _sync_one_group(idx: int, total: int, cred: dict,
                    start_date: date, end_date: date, *,
                    store_raw: bool = False,
                    filter_location: Optional[int] = None) -> dict:
    """Worker function for parallel execution. Each thread gets its own httpx.Client."""
    group_locs = len(cred["locations"])
    if filter_location:
        if not any(loc["location_id"] == filter_location for loc in cred["locations"]):
            return {"total_orders": 0, "store_days_synced": 0, "store_days_skipped": 0}

    log(f"[Thread {idx}/{total}] Starting {cred['group_name']} ({group_locs} stores)")

    client = httpx.Client(timeout=30)
    try:
        result = sync_credential_group(
            client, cred, start_date, end_date,
            store_raw=store_raw,
            filter_location=filter_location,
        )
        log(
            f"[Thread {idx}/{total}] Done {cred['group_name']}: "
            f"{result['store_days_synced']} synced, {result['total_orders']} orders"
        )
        return result
    except Exception as e:
        log(f"[Thread {idx}/{total}] FAILED {cred['group_name']}: {e}")
        return {"total_orders": 0, "store_days_synced": 0, "store_days_skipped": 0}
    finally:
        client.close()


def main():
    from concurrent.futures import ThreadPoolExecutor, as_completed

    parser = build_parser()
    args = parser.parse_args()

    # Resolve date range
    yesterday = date.today() - timedelta(days=1)
    if args.daily:
        start_date = yesterday
        end_date = yesterday
    else:
        start_date = date.fromisoformat(args.from_date) if args.from_date else EARLIEST_DATE
        end_date = date.fromisoformat(args.to_date) if args.to_date else yesterday

    if start_date > end_date:
        log(f"ERROR: start date {start_date} is after end date {end_date}")
        sys.exit(1)

    # Resolve secrets
    global SUPABASE_KEY, SUPABASE_MGMT_TOKEN
    SUPABASE_KEY = _get_secret("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_MGMT_TOKEN = _get_secret("SUPABASE_MGMT_TOKEN", "SUPABASE_ACCESS_TOKEN")

    # Load credentials
    creds = load_credentials(CREDENTIALS_CSV)
    total_locations = sum(len(c["locations"]) for c in creds)
    total_days = (end_date - start_date).days + 1
    total_store_days = total_locations * total_days
    if args.store:
        matching = sum(
            1 for c in creds
            for loc in c["locations"]
            if loc["location_id"] == args.store
        )
        if not matching:
            log(f"ERROR: Location ID {args.store} not found in credentials CSV")
            sys.exit(1)
        total_store_days = total_days

    mode = "parallel" if args.parallel else "sequential"
    log(
        f"Starting sync ({mode}): {total_locations} stores, "
        f"{len(creds)} credential groups, "
        f"{start_date} to {end_date} ({total_days} days, ~{total_store_days} store-days)"
    )

    t_start = time.time()

    if args.parallel:
        # --- Parallel: 1 thread per credential group (each has own rate limit) ---
        workers = len(creds)
        log(f"Launching {workers} parallel workers (1 per credential group)")

        grand_total_orders = 0
        grand_store_days_synced = 0
        grand_store_days_skipped = 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _sync_one_group, idx, len(creds), cred,
                    start_date, end_date,
                    store_raw=args.store_raw,
                    filter_location=args.store,
                ): cred
                for idx, cred in enumerate(creds, 1)
            }
            for future in as_completed(futures):
                result = future.result()
                grand_total_orders += result["total_orders"]
                grand_store_days_synced += result["store_days_synced"]
                grand_store_days_skipped += result["store_days_skipped"]

    else:
        # --- Sequential (original behavior) ---
        client = httpx.Client(timeout=30)
        grand_total_orders = 0
        grand_store_days_synced = 0
        grand_store_days_skipped = 0

        try:
            for idx, cred in enumerate(creds, 1):
                if _shutdown_requested:
                    break

                group_locs = len(cred["locations"])
                if args.store:
                    if not any(loc["location_id"] == args.store for loc in cred["locations"]):
                        continue

                log(
                    f"Credential group {idx}/{len(creds)}: "
                    f"{cred['group_name']} ({group_locs} stores)"
                )

                result = sync_credential_group(
                    client, cred, start_date, end_date,
                    store_raw=args.store_raw,
                    filter_location=args.store,
                )
                grand_total_orders += result["total_orders"]
                grand_store_days_synced += result["store_days_synced"]
                grand_store_days_skipped += result["store_days_skipped"]

                progress_pct = (
                    (grand_store_days_synced + grand_store_days_skipped) / total_store_days * 100
                    if total_store_days > 0 else 0
                )
                log(
                    f"Progress: {grand_store_days_synced + grand_store_days_skipped}"
                    f"/{total_store_days} store-days ({progress_pct:.1f}%), "
                    f"{grand_total_orders} orders synced"
                )
        finally:
            client.close()

    elapsed = time.time() - t_start
    log(
        f"Sync {'interrupted' if _shutdown_requested else 'complete'}. "
        f"{grand_store_days_synced} store-days synced, "
        f"{grand_store_days_skipped} skipped (already complete), "
        f"{grand_total_orders} orders total. "
        f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}m)"
    )

    if args.refresh_views and not _shutdown_requested:
        client = httpx.Client(timeout=30)
        try:
            refresh_materialized_views(client)
        finally:
            client.close()


if __name__ == "__main__":
    main()
