#!/usr/bin/env python3
"""
Parse FoodPanda item-level data directly from the FP SUMMARY tab's AU+ columns
and upsert into foodpanda_order_items in Supabase.

This replaces reliance on the FP_ITEMS_CLEAN tab (which stopped updating Mar 8).

Source: FP SUMMARY tab, columns AU-BI (product quantity per order)
Target: foodpanda_order_items table in Supabase

Usage:
    python scripts/sync_fp_items_from_summary.py --backfill          # All historical data
    python scripts/sync_fp_items_from_summary.py --date 2026-03-15   # Single day
    python scripts/sync_fp_items_from_summary.py --rolling-days 7    # Last N days
    python scripts/sync_fp_items_from_summary.py --backfill --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import date, datetime, timedelta
from typing import Any

import pytz
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Configuration ────────────────────────────────────────────────────────────

SERVICE_ACCOUNT_FILE = "credentials/task-manager-service.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
GOOGLE_IMPERSONATE_USER = "sam@bebang.ph"
SPREADSHEET_ID = "1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78"
SHEET_NAME = "FP SUMMARY"

SUPABASE_PROJECT_ID = "csnniykjrychgajfrgua"
SUPABASE_QUERY_URL = (
    f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_ID}/database/query"
)

MANILA_TZ = pytz.timezone("Asia/Manila")

# Product columns: index 46 (AU) through 60 (BI)
PRODUCT_START_COL = 46
PRODUCT_NAMES = [
    "Presidential",
    "Halokay Ube",
    "Mango Classic",
    "Mango Graham Caramel",
    "Melon",
    "So Corny",
    "Buko Fruit",
    "Special",
    "Buko Pandan",
    "Choco Brownie",
    "Cookie Crumble",
    "Banana Cinnamon",
    "Strawberry Pistachio",
    "Blueberry Pistachio",
    "Matcharap",
]

# Key column indices in FP SUMMARY
COL_RESTAURANT = 0
COL_ORDER_ID = 1
COL_STATUS = 7
COL_RECEIVED_AT = 8
COL_DELIVERED_AT = 15
COL_SUBTOTAL = 21

# Restaurant name -> location_id
STORE_LOCATION_MAP = {
    "Bebang Halo-Halo - Ayala Malls Fairview Terraces": 2220,
    "Bebang Halo-Halo - Ayala UPTC": 2425,
    "Bebang Halo-Halo - Ayala Vermosa": 2428,
    "Bebang Halo-Halo - BF Homes": 2217,
    "Bebang Halo-Halo - CTTM Tomas Morato": 2526,
    "Bebang Halo-Halo - Ever Commonwealth": 2281,
    "Bebang Halo-Halo - Festival Mall Alabang": 2222,
    "Bebang Halo-Halo - Lucky Chinatown": 2311,
    "Bebang Halo-Halo - Megawide PITX": 2179,
    "Bebang Halo-Halo - Megaworld Paseo Center": 2177,
    "Bebang Halo-Halo - Megaworld Venice Grand Canal": 2216,
    "Bebang Halo-Halo - Robinson Imus": 2408,
    "Bebang Halo-Halo - Robinsons Antipolo": 2342,
    "Bebang Halo-Halo - SM Bicutan": 2412,
    "Bebang Halo-Halo - SM Caloocan": 2464,
    "Bebang Halo-Halo - SM East Ortigas": 2184,
    "Bebang Halo-Halo - SM Grand Central": 2218,
    "Bebang Halo-Halo - SM Mall Of Asia": 2219,
    "Bebang Halo-Halo - SM Manila": 2339,
    "Bebang Halo-Halo - SM Marikina": 2317,
    "Bebang Halo-Halo - SM Marilao": 2413,
    "Bebang Halo-Halo - SM Megamall": 2338,
    "Bebang Halo-Halo - SM North EDSA": 2284,
    "Bebang Halo-Halo - SM Sangandaan": 2482,
    "Bebang Halo-Halo - SM Southmall": 2340,
    "Bebang Halo-Halo - SM Valenzuela": 2341,
    "Bebang Halo-Halo - The Terminal": 2319,
    "Bebang Halo-Halo - Gateway Mall 1": 2557,
    "Bebang Halo-Halo - SM Tanza": 2411,
    "Bebang Halo-Halo - SM Pulilan": 2478,
    "Bebang Halo-Halo - SM SJDM": 2481,
    "Bebang Halo-Halo - Ayala Solenad": 2547,
    "Bebang Halo-Halo - Ayala Evo": 2426,
    "Bebang Halo-Halo - SM Clark": 2646,
    "Bebang Halo-Halo - SM Taytay": 2812,
    "Bebang Halo-Halo - Vista Mall Taguig": 2556,
    "Bebang Halo-Halo - Sta. Lucia East Grand Mall": 2558,
    "Bebang Halo-Halo - Ayala Market Market": 2287,
    "Bebang Halo-Halo - Up Town Mall BGC": 2548,
    "Bebang Halo-Halo - Robinsons Galleria South": 2515,
    "Bebang Halo-Halo - D'Verde Calamba": 2766,
    "Bebang Halo-Halo - SM Sta. Rosa": 2774,
    "Bebang Halo-Halo - Robinson General Trias": 2430,
    "Bebang Halo-Halo - The Grid - Rockwell": 2250,
    "Bebang Halo-Halo - SM San Pablo": 2912,
}


def log(msg: str):
    ts = datetime.now(MANILA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_supabase_token() -> str:
    token = os.environ.get("SUPABASE_MGMT_TOKEN")
    if not token:
        token = subprocess.check_output(
            ["doppler", "secrets", "get", "SUPABASE_MGMT_TOKEN",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            text=True,
        ).strip()
    return token


def query_supabase(sql: str, token: str, timeout: int = 60) -> list:
    r = requests.post(
        SUPABASE_QUERY_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout,
    )
    data = r.json()
    if isinstance(data, dict) and "message" in data:
        raise RuntimeError(f"Supabase error: {data['message'][:200]}")
    return data


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=GOOGLE_SCOPES,
        subject=GOOGLE_IMPERSONATE_USER,
    )
    return build("sheets", "v4", credentials=creds)


def parse_business_date(received_at) -> str | None:
    """Extract business_date from 'Order received at' — handles both date strings and Excel serial numbers."""
    if received_at is None or received_at == "":
        return None
    try:
        # Excel serial number (float like 46065.7354)
        if isinstance(received_at, (int, float)):
            from datetime import datetime as dt_cls, timedelta as td_cls
            base = dt_cls(1899, 12, 30)
            d = base + td_cls(days=float(received_at))
            return d.strftime("%Y-%m-%d")
        # String that looks like a serial number
        dt_str = str(received_at).strip()
        if dt_str.replace(".", "").isdigit() and float(dt_str) > 40000:
            from datetime import datetime as dt_cls, timedelta as td_cls
            base = dt_cls(1899, 12, 30)
            d = base + td_cls(days=float(dt_str))
            return d.strftime("%Y-%m-%d")
        # Normal date string: "2026-02-07 16:59"
        if len(dt_str) >= 10:
            return dt_str[:10]
    except Exception:
        pass
    return None


def resolve_location_id(restaurant_name: str) -> int | None:
    return STORE_LOCATION_MAP.get(restaurant_name)


def fetch_all_rows(service, batch_size: int = 5000) -> list[list]:
    """Fetch all data rows from FP SUMMARY (skip header rows 1-2)."""
    all_rows = []
    start_row = 3  # Row 1 = group headers, Row 2 = column headers
    while True:
        end_row = start_row + batch_size - 1
        range_str = f"'{SHEET_NAME}'!A{start_row}:BI{end_row}"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_str,
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        rows = result.get("values", [])
        if not rows:
            break
        all_rows.extend(rows)
        log(f"  Fetched rows {start_row}-{start_row + len(rows) - 1} ({len(rows)} rows)")
        if len(rows) < batch_size:
            break
        start_row += batch_size
    return all_rows


import re

def parse_order_items_text(text: str) -> list[tuple[str, int]]:
    """Parse 'Order Items' text like '2 Mango Graham, 1 Matcharap' into [(name, qty), ...]."""
    if not text or not text.strip():
        return []
    items = []
    # Split by comma, each part is like "2 Presidential" or "1 Mango Graham Caramel"
    for part in str(text).split(","):
        part = part.strip()
        m = re.match(r"^(\d+)\s+(.+)$", part)
        if m:
            qty = int(m.group(1))
            name = m.group(2).strip()
            items.append((name, qty))
    return items


# Canonical name mapping for FP products (align with POS/Web dedup)
FP_CANONICAL_MAP = {
    "Halukay Ube": "Halokay Ube",
    "Buko Fruit Salad": "Buko Fruit",
    "Banana Cinnamon Con Yelo": "Banana Cinnamon",
    "Mango Graham": "Mango Graham Caramel",
    # Add more as discovered
}


def canonicalize_product(name: str) -> str:
    return FP_CANONICAL_MAP.get(name, name)


def parse_items_from_row(row: list) -> list[dict]:
    """Parse product quantities from Order Items text (col 44) or AU+ columns as fallback."""
    order_id = row[COL_ORDER_ID] if len(row) > COL_ORDER_ID else None
    if not order_id:
        return []

    status = str(row[COL_STATUS]).strip().lower() if len(row) > COL_STATUS else ""
    if status == "cancelled":
        return []

    restaurant = row[COL_RESTAURANT] if len(row) > COL_RESTAURANT else ""
    location_id = resolve_location_id(restaurant)

    received_at = row[COL_RECEIVED_AT] if len(row) > COL_RECEIVED_AT else None
    business_date = parse_business_date(received_at)

    subtotal = row[COL_SUBTOTAL] if len(row) > COL_SUBTOTAL else 0
    try:
        subtotal = float(subtotal) if subtotal else 0
    except (ValueError, TypeError):
        subtotal = 0

    # Strategy 1: Parse "Order Items" text column (always available)
    order_items_text = row[44] if len(row) > 44 else ""
    parsed_text = parse_order_items_text(order_items_text)

    # Strategy 2: AU+ columns (only filled for older orders)
    au_items = []
    for i, product_name in enumerate(PRODUCT_NAMES):
        col_idx = PRODUCT_START_COL + i
        qty = row[col_idx] if len(row) > col_idx else 0
        try:
            qty = int(qty) if qty else 0
        except (ValueError, TypeError):
            qty = 0
        if qty > 0:
            au_items.append((product_name, qty))

    # Prefer text parsing (always available); fall back to AU+ if text is empty
    source_items = parsed_text if parsed_text else au_items
    if not source_items:
        return []

    # Aggregate by canonical name (e.g., "Halukay Ube" + "Halokay Ube" -> one row)
    total_qty = sum(qty for _, qty in source_items)
    merged = {}
    for name, qty in source_items:
        canonical = canonicalize_product(name)
        if canonical in merged:
            merged[canonical]["quantity"] += qty
            merged[canonical]["source_item_name"] += f", {name}"
        else:
            merged[canonical] = {
                "order_id": str(order_id).strip(),
                "location_id": location_id,
                "business_date": business_date,
                "product_name": canonical,
                "product_code": None,
                "quantity": qty,
                "net_sales": 0,
                "source_item_name": name,
            }

    # Distribute net_sales proportionally
    for item in merged.values():
        item["net_sales"] = round(subtotal * item["quantity"] / total_qty, 2) if total_qty > 0 and subtotal > 0 else 0

    return list(merged.values())


def escape_sql(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def upsert_batch(items: list[dict], token: str, dry_run: bool = False) -> int:
    if not items:
        return 0

    values_parts = []
    for item in items:
        vals = (
            f"({escape_sql(item['order_id'])}, {escape_sql(item['location_id'])}, "
            f"{escape_sql(item['business_date'])}, {escape_sql(item['product_name'])}, "
            f"{escape_sql(item['product_code'])}, {item['quantity']}, "
            f"{item['net_sales']}, {escape_sql(item['source_item_name'])}, now())"
        )
        values_parts.append(vals)

    sql = f"""
    INSERT INTO foodpanda_order_items
        (order_id, location_id, business_date, product_name, product_code,
         quantity, net_sales, source_item_name, synced_at)
    VALUES {', '.join(values_parts)}
    ON CONFLICT (order_id, product_name) DO UPDATE SET
        location_id = EXCLUDED.location_id,
        business_date = EXCLUDED.business_date,
        quantity = EXCLUDED.quantity,
        net_sales = EXCLUDED.net_sales,
        synced_at = now()
    """

    if dry_run:
        return len(items)

    import time
    for attempt in range(5):
        try:
            query_supabase(sql, token, timeout=120)
            return len(items)
        except RuntimeError as e:
            if "Too Many Requests" in str(e) or "ThrottlerException" in str(e):
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise
    # Final attempt without catch
    query_supabase(sql, token, timeout=120)
    return len(items)


def main():
    parser = argparse.ArgumentParser(description="Sync FP items from FP SUMMARY AU+ columns")
    parser.add_argument("--backfill", action="store_true", help="Sync all historical data")
    parser.add_argument("--date", type=str, help="Sync single date (YYYY-MM-DD)")
    parser.add_argument("--rolling-days", type=int, help="Sync last N days")
    parser.add_argument("--start-date", type=str, help="Start date for range sync")
    parser.add_argument("--end-date", type=str, help="End date for range sync")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't write to Supabase")
    parser.add_argument("--batch-size", type=int, default=100, help="SQL batch size")
    args = parser.parse_args()

    # Resolve date filter
    PHT = MANILA_TZ
    today = datetime.now(PHT).date()
    date_filter = None  # None = all dates (backfill)

    if args.date:
        date_filter = (args.date, args.date)
    elif args.rolling_days:
        start = (today - timedelta(days=args.rolling_days)).isoformat()
        date_filter = (start, today.isoformat())
    elif args.start_date:
        end = args.end_date or today.isoformat()
        date_filter = (args.start_date, end)
    elif not args.backfill:
        parser.error("Specify --backfill, --date, --rolling-days, or --start-date/--end-date")

    log("FoodPanda Items Sync (from FP SUMMARY AU+ columns)")
    log(f"Date filter: {date_filter or 'ALL (backfill)'}")
    if args.dry_run:
        log("DRY RUN — no writes to Supabase")

    # Get Supabase token
    token = get_supabase_token()

    # Fetch all rows from Google Sheets
    log("Fetching FP SUMMARY data from Google Sheets...")
    service = get_sheets_service()
    all_rows = fetch_all_rows(service)
    log(f"Total rows fetched: {len(all_rows):,}")

    # Parse items
    log("Parsing item data from AU+ columns...")
    all_items = []
    skipped_no_date = 0
    skipped_date_filter = 0
    skipped_no_items = 0
    skipped_cancelled = 0

    for row in all_rows:
        status = str(row[COL_STATUS]).strip().lower() if len(row) > COL_STATUS else ""
        if status == "cancelled":
            skipped_cancelled += 1
            continue

        items = parse_items_from_row(row)
        if not items:
            skipped_no_items += 1
            continue

        bdate = items[0]["business_date"]
        if not bdate:
            skipped_no_date += 1
            continue

        if date_filter:
            if bdate < date_filter[0] or bdate > date_filter[1]:
                skipped_date_filter += 1
                continue

        all_items.extend(items)

    log(f"Parsed {len(all_items):,} item rows from {len(all_rows):,} orders")
    log(f"  Skipped: {skipped_cancelled:,} cancelled, {skipped_no_items:,} no items, "
        f"{skipped_no_date:,} no date, {skipped_date_filter:,} outside date range")

    if not all_items:
        log("Nothing to sync.")
        return

    # Upsert in batches
    log(f"Upserting {len(all_items):,} items in batches of {args.batch_size}...")
    total_upserted = 0
    for i in range(0, len(all_items), args.batch_size):
        batch = all_items[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(all_items) + args.batch_size - 1) // args.batch_size
        try:
            count = upsert_batch(batch, token, dry_run=args.dry_run)
            total_upserted += count
            if batch_num % 50 == 0 or batch_num == total_batches:
                log(f"  Batch {batch_num}/{total_batches} — {total_upserted:,} items so far")
        except Exception as e:
            log(f"  ERROR batch {batch_num}: {str(e)[:200]}")

    log(f"Sync complete. {total_upserted:,} items upserted.")

    # Summary by date
    if not args.dry_run:
        try:
            summary = query_supabase(
                "SELECT MIN(business_date)::text as min_dt, MAX(business_date)::text as max_dt, "
                "COUNT(*)::int as total, COUNT(DISTINCT business_date)::int as dates "
                "FROM foodpanda_order_items",
                token,
            )
            s = summary[0]
            log(f"Table now has {s['total']:,} rows, {s['dates']} dates ({s['min_dt']} to {s['max_dt']})")
        except Exception:
            pass


if __name__ == "__main__":
    main()
