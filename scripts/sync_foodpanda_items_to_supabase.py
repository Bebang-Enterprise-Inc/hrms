#!/usr/bin/env python3
"""
Sync FoodPanda order-level item data from Google Sheets into Supabase.

Source:
    FP_ITEMS_CLEAN tab in the canonical FoodPanda workbook (1F9Zqn_...).
    Row 1 = description, Row 2 = headers, Row 3+ = data.

Target:
    foodpanda_order_items table in Supabase (created on first run if missing).

Usage:
    python scripts/sync_foodpanda_items_to_supabase.py --backfill
    python scripts/sync_foodpanda_items_to_supabase.py --date 2026-03-15
    python scripts/sync_foodpanda_items_to_supabase.py --rolling-days 7
    python scripts/sync_foodpanda_items_to_supabase.py --start-date 2026-03-01 --end-date 2026-03-15
    python scripts/sync_foodpanda_items_to_supabase.py --backfill --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Configuration ────────────────────────────────────────────────────────────

SERVICE_ACCOUNT_FILE = "credentials/task-manager-service.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
GOOGLE_IMPERSONATE_USER = "sam@bebang.ph"
SPREADSHEET_ID = "1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78"
SHEET_NAME = "FP_ITEMS_CLEAN"

SUPABASE_PROJECT_ID = "csnniykjrychgajfrgua"
SUPABASE_QUERY_URL = (
    f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_ID}/database/query"
)

MANILA_TZ = pytz.timezone("Asia/Manila")

# Store name/code -> location_id mapping (superset from sync_foodpanda_to_supabase.py)
STORE_LOCATION_MAP = {
    "Ayala Malls Fairview Terraces": 2220,
    "Ayala UPTC": 2425,
    "Ayala Vermosa": 2428,
    "BF Homes": 2217,
    "CTTM Tomas Morato": 2526,
    "Ever Commonwealth": 2281,
    "Festival Mall Alabang": 2222,
    "Lucky Chinatown": 2311,
    "Megawide PITX": 2179,
    "Megaworld Paseo Center": 2177,
    "Megaworld Venice Grand Canal": 2216,
    "Robinsons Antipolo": 2342,
    "SM Bicutan": 2412,
    "SM Caloocan": 2464,
    "SM East Ortigas": 2184,
    "SM Grand Central": 2218,
    "SM Mall Of Asia": 2219,
    "SM Manila": 2339,
    "SM Marikina": 2317,
    "SM Marilao": 2413,
    "SM Megamall": 2338,
    "SM North EDSA": 2284,
    "SM Sangandaan": 2482,
    "SM Southmall": 2340,
    "SM Valenzuela": 2341,
    "The Terminal": 2319,
    "Araneta Gateway": 2557,
    "SM Tanza": 2411,
    "SM Pulilan": 2478,
    "SM SJDM": 2481,
    "Ayala Solenad": 2547,
    "Ayala Evo": 2426,
    "SM Clark": 2646,
    "SM Taytay": 2812,
    "Vista Mall Taguig": 2556,
    "Sta. Lucia East Grand Mall": 2558,
    "Robinson Imus": 2408,
    "Robinson General Trias": 2430,
    "Robinsons Galleria South": 2515,
    "Ayala Market Market": 2287,
    "D'Verde Calamba": 2766,
    "SM Sta. Rosa": 2774,
    "SM San Pablo": 2912,
    "The Grid - Rockwell": 2250,
    "Up Town Mall BGC": 2548,
    "SM Sta Rosa": 2774,
    # Aliases from FoodPanda SUMMARY sheet
    "Fairview Terraces": 2220,
    "UP Town Center": 2425,
    "CTTM": 2526,
    "Ever Gotesco": 2281,
    "Festival Mall": 2222,
    "Gateway Mall": 2557,
    "Chinatown": 2311,
    "Market Market": 2287,
    "Paseo De Roxas": 2177,
    "PITX": 2179,
    "Rob Imus": 2408,
    "Rob Gen Trias": 2430,
    "SM North": 2284,
    "Sta. Lucia": 2558,
    "NAIA": 2319,
    "Uptown Mall": 2548,
    "Venice Grand": 2216,
    "Rob Galleria South": 2515,
    "Terminal Alabang": 2319,
    "The Grid": 2250,
    "Vistamall Taguig": 2556,
    "Dverde Calamba": 2766,
    "SM MOA": 2219,
    "Rob Antipolo": 2342,
    "SJDM": 2481,
}

# ── DDL (run once) ───────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.foodpanda_order_items (
    order_id          text          NOT NULL,
    location_id       integer,
    business_date     date,
    product_name      text          NOT NULL,
    product_code      text,
    quantity          integer       NOT NULL DEFAULT 0,
    net_sales         numeric(12,2) DEFAULT 0,
    source_item_name  text,
    synced_at         timestamptz   DEFAULT now(),
    PRIMARY KEY (order_id, product_name)
);

CREATE INDEX IF NOT EXISTS idx_fp_items_business_date
    ON public.foodpanda_order_items(business_date);
CREATE INDEX IF NOT EXISTS idx_fp_items_product
    ON public.foodpanda_order_items(product_name);
CREATE INDEX IF NOT EXISTS idx_fp_items_location
    ON public.foodpanda_order_items(location_id);
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_management_token() -> str:
    """Read Supabase Management API token from env or Doppler."""
    token = os.environ.get("SUPABASE_MGMT_TOKEN")
    if token:
        return token.strip()
    return subprocess.check_output(
        [
            "doppler",
            "secrets",
            "get",
            "SUPABASE_MGMT_TOKEN",
            "--plain",
            "--project",
            "bei-erp",
            "--config",
            "dev",
        ],
        text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    ).strip()


def execute_supabase_query(
    token: str, query: str
) -> list[dict[str, Any]] | dict[str, Any]:
    """Execute SQL query via Supabase Management API."""
    response = requests.post(
        SUPABASE_QUERY_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def get_sheets_service():
    """Create Google Sheets API service with domain-wide delegation."""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=GOOGLE_SCOPES,
    ).with_subject(
        os.environ.get("GOOGLE_IMPERSONATE_USER", GOOGLE_IMPERSONATE_USER)
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def escape_text(value: Any) -> str:
    """Escape a string for SQL, or return NULL."""
    if value in (None, ""):
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def escape_num(value: Any) -> str:
    if value in (None, ""):
        return "NULL"
    return str(value)


def parse_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_store_name(value: Any) -> str:
    name = str(value or "").strip()
    return " ".join(name.replace("\u2019", "'").split())


def build_date_range(start: date, end: date) -> list[date]:
    """Inclusive date range."""
    return [start + timedelta(days=d) for d in range((end - start).days + 1)]


# ── Store code mapping from Supabase ────────────────────────────────────────

def fetch_store_code_mapping(token: str) -> Dict[str, int]:
    """
    Try to load store_code -> location_id from foodpanda_store_mapping table.
    Falls back to STORE_LOCATION_MAP keyed on store_name/store_code.
    """
    try:
        result = execute_supabase_query(
            token,
            "SELECT store_code, location_id FROM public.foodpanda_store_mapping;",
        )
        if isinstance(result, list) and result:
            mapping = {}
            for row in result:
                code = str(row.get("store_code", "")).strip()
                loc = row.get("location_id")
                if code and loc:
                    mapping[code] = int(loc)
            if mapping:
                print(f"Loaded {len(mapping)} store codes from foodpanda_store_mapping")
                return mapping
    except Exception as exc:
        print(f"foodpanda_store_mapping not available ({exc}), using built-in map")
    return {}


# ── Extract ──────────────────────────────────────────────────────────────────

def extract_items(
    target_dates: Optional[set[date]] = None,
    store_code_map: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """
    Read FP_ITEMS_CLEAN tab.
    Row 1 = description (skip), Row 2 = headers, Row 3+ = data.
    """
    service = get_sheets_service()

    # Open-ended range starting at row 1 (description row)
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{SHEET_NAME}'!A1:L",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    values = result.get("values", [])
    if len(values) < 3:
        print("FP_ITEMS_CLEAN has fewer than 3 rows (need description + headers + data)")
        return []

    # Row 1 = description (skip), Row 2 = headers
    headers = [str(cell).strip().lower() for cell in values[1]]
    idx = {h: i for i, h in enumerate(headers)}
    print(f"Headers: {headers}")

    items: List[Dict[str, Any]] = []
    skipped_date = 0
    skipped_store = 0

    for row_num, raw in enumerate(values[2:], start=3):

        def cell(header: str) -> str:
            col = idx.get(header)
            return str(raw[col]).strip() if col is not None and col < len(raw) else ""

        business_date_str = cell("business_date")
        if not business_date_str:
            continue

        # Date filter
        if target_dates:
            try:
                bd = date.fromisoformat(business_date_str)
            except ValueError:
                continue
            if bd not in target_dates:
                skipped_date += 1
                continue

        order_id = cell("order_id")
        if not order_id:
            continue

        canonical_name = cell("canonical_product_name")
        if not canonical_name:
            continue

        # Resolve location_id: try store_code first, then store_name
        location_id: Optional[int] = None
        store_code = cell("store_code")
        store_name = normalize_store_name(cell("store_name"))

        if store_code and store_code_map:
            location_id = store_code_map.get(store_code)
        if not location_id and store_name:
            location_id = STORE_LOCATION_MAP.get(store_name)
        if not location_id and store_code:
            # Try store_code as a name alias too
            location_id = STORE_LOCATION_MAP.get(store_code)

        if not location_id:
            skipped_store += 1
            continue

        items.append(
            {
                "order_id": order_id,
                "location_id": location_id,
                "business_date": business_date_str,
                "product_name": canonical_name,
                "product_code": cell("product_code") or None,
                "quantity": parse_int(cell("qty_sold")),
                "net_sales": round(parse_float(cell("net_sales_amount")), 2),
                "source_item_name": cell("source_item_name") or None,
            }
        )

    print(f"\nExtraction summary:")
    print(f"  Items extracted: {len(items)}")
    print(f"  Skipped (date filter): {skipped_date}")
    print(f"  Skipped (unmapped store): {skipped_store}")
    return items


# ── Ensure table ─────────────────────────────────────────────────────────────

def ensure_table(token: str) -> None:
    """Create foodpanda_order_items table if it doesn't exist."""
    try:
        execute_supabase_query(token, CREATE_TABLE_SQL)
        print("Table foodpanda_order_items ensured.")
    except Exception as exc:
        # If the table already exists, the CREATE IF NOT EXISTS should be fine.
        # Only log unexpected errors.
        print(f"Warning during table creation: {exc}")


# ── Upsert ───────────────────────────────────────────────────────────────────

def upsert_items(token: str, items: List[Dict[str, Any]]) -> None:
    """Batch upsert items into foodpanda_order_items."""
    if not items:
        print("No items to upsert.")
        return

    batch_size = 100
    total_batches = (len(items) + batch_size - 1) // batch_size
    print(f"\nUpserting {len(items)} items in {total_batches} batches...")

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_num = i // batch_size + 1

        values_clauses = []
        for item in batch:
            clause = (
                f"({escape_text(item['order_id'])},"
                f"{escape_num(item['location_id'])},"
                f"{escape_text(item['business_date'])},"
                f"{escape_text(item['product_name'])},"
                f"{escape_text(item['product_code'])},"
                f"{escape_num(item['quantity'])},"
                f"{escape_num(item['net_sales'])},"
                f"{escape_text(item['source_item_name'])},"
                f"NOW())"
            )
            values_clauses.append(clause)

        query = f"""
            INSERT INTO public.foodpanda_order_items (
                order_id, location_id, business_date, product_name,
                product_code, quantity, net_sales, source_item_name, synced_at
            )
            VALUES {",".join(values_clauses)}
            ON CONFLICT (order_id, product_name)
            DO UPDATE SET
                location_id      = EXCLUDED.location_id,
                business_date    = EXCLUDED.business_date,
                product_code     = EXCLUDED.product_code,
                quantity          = EXCLUDED.quantity,
                net_sales         = EXCLUDED.net_sales,
                source_item_name = EXCLUDED.source_item_name,
                synced_at         = NOW();
        """

        try:
            execute_supabase_query(token, query)
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)")
        except Exception as exc:
            print(f"  Batch {batch_num}/{total_batches} FAILED: {exc}")
            raise

    print(f"\nSuccessfully upserted {len(items)} items to foodpanda_order_items")


# ── Summary ──────────────────────────────────────────────────────────────────

def print_summary(items: List[Dict[str, Any]]) -> None:
    if not items:
        return

    by_date: Dict[str, int] = defaultdict(int)
    by_product: Dict[str, int] = defaultdict(int)
    total_qty = 0
    total_sales = 0.0

    for item in items:
        by_date[item["business_date"]] += 1
        by_product[item["product_name"]] += item["quantity"]
        total_qty += item["quantity"]
        total_sales += item["net_sales"]

    print(f"\nSummary:")
    print(f"  Dates covered: {len(by_date)} ({min(by_date)}..{max(by_date)})")
    print(f"  Unique products: {len(by_product)}")
    print(f"  Total quantity: {total_qty:,}")
    print(f"  Total net sales: P{total_sales:,.2f}")

    print(f"\n  Top 10 products by quantity:")
    for name, qty in sorted(by_product.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    {name}: {qty:,}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync FoodPanda item-level data from Google Sheets to Supabase"
    )
    parser.add_argument("--date", help="Single date YYYY-MM-DD")
    parser.add_argument("--start-date", help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Inclusive end date YYYY-MM-DD")
    parser.add_argument(
        "--rolling-days",
        type=int,
        help="Sync last N days (ending yesterday)",
    )
    parser.add_argument("--backfill", action="store_true", help="Sync all data")
    parser.add_argument(
        "--dry-run", action="store_true", help="Extract only, do not upsert"
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Exit non-zero if zero items extracted",
    )
    args = parser.parse_args()

    # Validate mutually exclusive modes
    mode_count = sum(
        [
            bool(args.date),
            bool(args.start_date or args.end_date),
            bool(args.rolling_days),
            args.backfill,
        ]
    )
    if mode_count > 1:
        print("Error: specify only one of --date, --start-date/--end-date, --rolling-days, --backfill")
        return 1
    if bool(args.start_date) != bool(args.end_date):
        print("Error: --start-date and --end-date must be used together")
        return 1

    # Determine target dates
    target_dates: Optional[set[date]] = None

    if args.date:
        d = date.fromisoformat(args.date)
        target_dates = {d}
        print(f"Mode: single date {d}")
    elif args.start_date and args.end_date:
        s = date.fromisoformat(args.start_date)
        e = date.fromisoformat(args.end_date)
        if s > e:
            print(f"Error: start-date {s} is after end-date {e}")
            return 1
        target_dates = set(build_date_range(s, e))
        print(f"Mode: date range {s} to {e} ({len(target_dates)} days)")
    elif args.rolling_days:
        if args.rolling_days < 1:
            print("Error: --rolling-days must be >= 1")
            return 1
        end = (datetime.now(MANILA_TZ) - timedelta(days=1)).date()
        start = end - timedelta(days=args.rolling_days - 1)
        target_dates = set(build_date_range(start, end))
        print(f"Mode: rolling {args.rolling_days} days ({start} to {end})")
    elif args.backfill:
        print("Mode: full backfill (all rows)")
    else:
        # Default: today
        d = datetime.now(MANILA_TZ).date()
        target_dates = {d}
        print(f"Mode: default (today {d})")

    # Get Supabase token and ensure table exists
    token = get_management_token()
    ensure_table(token)

    # Load store_code -> location_id from Supabase (if available)
    store_code_map = fetch_store_code_mapping(token)

    # Extract items from Google Sheets
    print(f"\nExtracting items from {SHEET_NAME}...")
    items = extract_items(target_dates, store_code_map)

    if not items:
        print("\nNo items extracted.")
        return 1 if args.fail_on_empty else 0

    print_summary(items)

    # Upsert
    if not args.dry_run:
        upsert_items(token, items)
    else:
        print("\nDRY RUN - no data written to Supabase")

    print("\nSync complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
