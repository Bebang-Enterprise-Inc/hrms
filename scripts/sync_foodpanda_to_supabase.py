#!/usr/bin/env python3
"""
FoodPanda to Supabase Data Warehouse ETL Script

Extracts order data from FoodPanda Google Sheet and upserts into Supabase.
Supports daily incremental sync and full backfill.

Usage:
    python scripts/sync_foodpanda_to_supabase.py --date 2026-02-14  # Daily sync
    python scripts/sync_foodpanda_to_supabase.py --rolling-days 7    # Rolling catch-up sync
    python scripts/sync_foodpanda_to_supabase.py --start-date 2026-02-25 --end-date 2026-03-10
    python scripts/sync_foodpanda_to_supabase.py --backfill          # Full backfill
"""

import argparse
import os
import sys
import requests

# Fix Windows console encoding for emoji output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz

# Configuration
SERVICE_ACCOUNT_FILE = 'credentials/task-manager-service.json'
SPREADSHEET_ID = '1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
IMPERSONATE_USER = 'sam@bebang.ph'

SUPABASE_PROJECT_ID = 'csnniykjrychgajfrgua'
SUPABASE_API_URL = f'https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_ID}/database/query'
SUPABASE_MANAGEMENT_TOKEN = os.environ['SUPABASE_MGMT_TOKEN']

MANILA_TZ = pytz.timezone('Asia/Manila')

# Store name → location_id mapping (from MOSAIC_POS_API_KEYS.csv)
STORE_LOCATION_MAP = {
    'Ayala Malls Fairview Terraces': 2220,
    'Ayala UPTC': 2425,
    'Ayala Vermosa': 2428,
    'BF Homes': 2217,
    'CTTM Tomas Morato': 2526,
    'Ever Commonwealth': 2281,
    'Festival Mall Alabang': 2222,
    'Lucky Chinatown': 2311,
    'Megawide PITX': 2179,
    'Megaworld Paseo Center': 2177,
    'Megaworld Venice Grand Canal': 2216,
    'Robinsons Antipolo': 2342,
    'SM Bicutan': 2412,
    'SM Caloocan': 2464,
    'SM East Ortigas': 2184,
    'SM Grand Central': 2218,
    'SM Mall Of Asia': 2219,
    'SM Manila': 2339,
    'SM Marikina': 2317,
    'SM Marilao': 2413,
    'SM Megamall': 2338,
    'SM North EDSA': 2284,
    'SM Sangandaan': 2482,
    'SM Southmall': 2340,
    'SM Valenzuela': 2341,
    'The Terminal': 2319,
    'Araneta Gateway': 2557,
    'SM Tanza': 2411,
    'SM Pulilan': 2478,
    'SM SJDM': 2481,
    'Ayala Solenad': 2547,
    'Ayala Evo': 2426,
    'SM Clark': 2646,
    'SM Taytay': 2812,
    'Vista Mall Taguig': 2556,
    'Sta. Lucia East Grand Mall': 2558,
    'Robinson Imus': 2408,
    'Robinson General Trias': 2430,
    'Robinsons Galleria South': 2515,
    'Ayala Market Market': 2287,
    "D'Verde Calamba": 2766,
    'SM Sta. Rosa': 2774,
    'SM San Pablo': 2912,
    'The Grid - Rockwell': 2250,
    'Up Town Mall BGC': 2548,
    'SM Sta Rosa': 2774,
    # Aliases from FoodPanda SUMMARY sheet (abbreviated names)
    'Fairview Terraces': 2220,
    'UP Town Center': 2425,
    'CTTM': 2526,
    'Ever Gotesco': 2281,
    'Festival Mall': 2222,
    'Gateway Mall': 2557,
    'Chinatown': 2311,
    'Market Market': 2287,
    'Paseo De Roxas': 2177,
    'PITX': 2179,
    'Rob Imus': 2408,
    'Rob Gen Trias': 2430,
    'SM North': 2284,
    'Sta. Lucia': 2558,
    'NAIA': 2319,  # The Terminal (near NAIA)
    'Uptown Mall': 2548,
    'Venice Grand': 2216,
    'Rob Galleria South': 2515,
    'Terminal Alabang': 2319,
    'The Grid': 2250,
    'Vistamall Taguig': 2556,
    'Dverde Calamba': 2766,
    'SM MOA': 2219,
    'Rob Antipolo': 2342,
}


def build_date_range(start_date: date, end_date: date) -> List[date]:
    """Build inclusive date range."""
    days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(days + 1)]

def get_sheets_service():
    """Create Google Sheets API service with domain-wide delegation."""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    delegated_credentials = credentials.with_subject(IMPERSONATE_USER)
    return build('sheets', 'v4', credentials=delegated_credentials)

def execute_supabase_query(query: str) -> Dict[str, Any]:
    """Execute SQL query via Supabase Management API."""
    headers = {
        'Authorization': f'Bearer {SUPABASE_MANAGEMENT_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {'query': query}

    response = requests.post(SUPABASE_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def fetch_store_mapping() -> Dict[str, int]:
    """
    Fetch store mapping from SUMMARY sheet.
    Returns: Dict[fp_restaurant_name, location_id]
    """
    service = get_sheets_service()
    range_name = "'SUMMARY'!A2:D100"

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()

    values = result.get('values', [])
    if not values or len(values) < 2:
        print("⚠️ SUMMARY sheet is empty or missing headers")
        return {}

    # Skip header row (row 2 in sheet = values[0])
    mapping = {}
    for row in values[1:]:
        if len(row) >= 4:
            fp_name = row[0]  # Col A: Food Panda Store Names
            store_name = row[3]  # Col D: STORE NAME

            if fp_name and store_name:
                # Match against STORE_LOCATION_MAP
                location_id = STORE_LOCATION_MAP.get(store_name)
                if location_id:
                    mapping[fp_name] = location_id
                else:
                    print(f"⚠️ No location_id found for store: {store_name}")

    print(f"✅ Loaded {len(mapping)} store mappings from SUMMARY sheet")
    return mapping

EXCEL_EPOCH = datetime(1899, 12, 30)

def parse_datetime(value) -> Optional[datetime]:
    """Parse datetime from text string or Excel serial number."""
    if value is None or value == '':
        return None
    # Handle Excel serial numbers (float/int)
    if isinstance(value, (int, float)):
        try:
            naive_dt = EXCEL_EPOCH + timedelta(days=float(value))
            return MANILA_TZ.localize(naive_dt)
        except Exception:
            return None
    if not isinstance(value, str):
        return None
    try:
        for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S']:
            try:
                naive_dt = datetime.strptime(value, fmt)
                return MANILA_TZ.localize(naive_dt)
            except ValueError:
                continue
        return None
    except Exception as e:
        print(f"⚠️ Failed to parse datetime '{value}': {e}")
        return None

def parse_bool(value: Optional[str]) -> bool:
    """Convert Y/N string to boolean."""
    if not value:
        return False
    return str(value).strip().upper() == 'Y'

def parse_decimal(value: Any) -> Optional[float]:
    """Parse numeric value, handling empty/null."""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def extract_foodpanda_orders(target_dates: Optional[set[date]] = None) -> List[Dict[str, Any]]:
    """
    Extract FoodPanda orders from Google Sheet.

    Args:
        target_dates: If provided, only extract orders matching these business dates.
                      If None, extract all orders.

    Returns:
        List of order dictionaries ready for Supabase upsert.
    """
    service = get_sheets_service()
    store_mapping = fetch_store_mapping()

    # Read all data from FP SUMMARY sheet (row 2 = headers, row 3+ = data)
    # Use open-ended range to avoid truncating newly appended rows
    range_name = "'FP SUMMARY'!A2:Z"

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()

    values = result.get('values', [])
    if not values or len(values) < 2:
        print("❌ No data found in FP SUMMARY sheet")
        return []

    headers = values[0]
    print(f"✅ Found {len(values) - 1} rows in FP SUMMARY sheet")

    orders = []
    skipped_no_mapping = 0
    skipped_no_received_at = 0
    skipped_wrong_date = 0

    for row_idx, row in enumerate(values[1:], start=3):  # Start at row 3 (first data row)
        try:
            # Pad row to ensure we have all columns
            while len(row) < 26:
                row.append(None)

            restaurant_name = row[0]  # Col A
            order_id = row[1]  # Col B
            restaurant_id = row[2]  # Col C
            delivery_type = row[3]  # Col D
            payment_type = row[4]  # Col E
            payment_method = row[5]  # Col F
            is_pro_order = parse_bool(row[6])  # Col G
            order_status = row[7]  # Col H
            order_received_at = parse_datetime(row[8])  # Col I
            accepted_at = parse_datetime(row[9])  # Col J
            # Cols K-P (indices 10-15): Various timestamps (not mapped yet)
            has_complaint = parse_bool(row[16])  # Col Q
            complaint_reason = row[17]  # Col R
            cancelled_at = parse_datetime(row[18])  # Col S
            cancellation_reason = row[19]  # Col T
            cancellation_owner = row[20]  # Col U
            subtotal = parse_decimal(row[21])  # Col V
            packaging_charges = parse_decimal(row[22])  # Col W
            minimum_order_value_fee = parse_decimal(row[23])  # Col X
            vendor_refunds = parse_decimal(row[24])  # Col Y
            tax_charge = parse_decimal(row[25])  # Col Z

            # Skip rows without required fields
            if not order_id or not restaurant_id:
                continue

            if not order_received_at:
                skipped_no_received_at += 1
                continue

            # Calculate business_date (date portion of order_received_at in Manila timezone)
            business_date = order_received_at.date()

            # Filter by business date if specified
            if target_dates and business_date not in target_dates:
                skipped_wrong_date += 1
                continue

            # Map restaurant name to location_id
            location_id = store_mapping.get(restaurant_name)
            if not location_id:
                skipped_no_mapping += 1
                continue

            # Build order record (columns must match foodpanda_orders table schema)
            order = {
                'order_id': order_id,
                'fp_restaurant_code': restaurant_id,
                'location_id': location_id,
                'business_date': business_date.isoformat(),
                'order_received_at': order_received_at.isoformat(),
                'accepted_at': accepted_at.isoformat() if accepted_at else None,
                'cancelled_at': cancelled_at.isoformat() if cancelled_at else None,
                'delivery_type': delivery_type,
                'payment_type': payment_type,
                'payment_method': payment_method,
                'is_pro_order': is_pro_order,
                'order_status': order_status,
                'has_complaint': has_complaint,
                'cancellation_reason': cancellation_reason,
                'cancellation_owner': cancellation_owner,
                'subtotal': subtotal,
                'packaging_charges': packaging_charges,
                'tax_charge': tax_charge,
                # Keep restaurant_name for summary display only (not upserted)
                '_restaurant_name': restaurant_name,
            }

            orders.append(order)

        except Exception as e:
            print(f"⚠️ Error processing row {row_idx}: {e}")
            continue

    print(f"\n📊 Extraction Summary:")
    print(f"  ✅ Orders extracted: {len(orders)}")
    print(f"  ⚠️ Skipped (no mapping): {skipped_no_mapping}")
    print(f"  ⚠️ Skipped (no received_at): {skipped_no_received_at}")
    if target_dates:
        print(f"  ⚠️ Skipped (wrong date): {skipped_wrong_date}")

    return orders

def upsert_orders_to_supabase(orders: List[Dict[str, Any]]) -> None:
    """
    Upsert orders to Supabase foodpanda_orders table.
    Uses batch INSERT with ON CONFLICT DO UPDATE.
    """
    if not orders:
        print("⚠️ No orders to upsert")
        return

    # Build batch INSERT statement
    values_clauses = []
    for order in orders:
        # Escape single quotes in strings
        def escape_str(s):
            if s is None:
                return 'NULL'
            return f"'{str(s).replace(chr(39), chr(39) + chr(39))}'"

        def escape_num(n):
            return str(n) if n is not None else 'NULL'

        def escape_bool(b):
            return 'TRUE' if b else 'FALSE'

        values = f"""(
            {escape_str(order['order_id'])},
            {escape_str(order['fp_restaurant_code'])},
            {escape_num(order['location_id'])},
            {escape_str(order['business_date'])},
            {escape_str(order['order_received_at'])},
            {escape_str(order['accepted_at'])},
            {escape_str(order['cancelled_at'])},
            {escape_str(order['delivery_type'])},
            {escape_str(order['payment_type'])},
            {escape_str(order['payment_method'])},
            {escape_bool(order['is_pro_order'])},
            {escape_str(order['order_status'])},
            {escape_bool(order['has_complaint'])},
            {escape_str(order['cancellation_reason'])},
            {escape_str(order['cancellation_owner'])},
            {escape_num(order['subtotal'])},
            {escape_num(order['packaging_charges'])},
            {escape_num(order['tax_charge'])},
            NOW()
        )"""
        values_clauses.append(values)

    # Split into batches of 100 to avoid query size limits
    batch_size = 100
    total_batches = (len(values_clauses) + batch_size - 1) // batch_size

    print(f"\n🔄 Upserting {len(orders)} orders in {total_batches} batches...")

    for i in range(0, len(values_clauses), batch_size):
        batch = values_clauses[i:i + batch_size]
        batch_num = i // batch_size + 1

        query = f"""
            INSERT INTO foodpanda_orders (
                order_id, fp_restaurant_code, location_id, business_date,
                order_received_at, accepted_at, cancelled_at, delivery_type, payment_type,
                payment_method, is_pro_order, order_status, has_complaint,
                cancellation_reason, cancellation_owner, subtotal, packaging_charges,
                tax_charge, synced_at
            )
            VALUES {','.join(batch)}
            ON CONFLICT (order_id)
            DO UPDATE SET
                fp_restaurant_code = EXCLUDED.fp_restaurant_code,
                location_id = EXCLUDED.location_id,
                business_date = EXCLUDED.business_date,
                order_received_at = EXCLUDED.order_received_at,
                accepted_at = EXCLUDED.accepted_at,
                cancelled_at = EXCLUDED.cancelled_at,
                delivery_type = EXCLUDED.delivery_type,
                payment_type = EXCLUDED.payment_type,
                payment_method = EXCLUDED.payment_method,
                is_pro_order = EXCLUDED.is_pro_order,
                order_status = EXCLUDED.order_status,
                has_complaint = EXCLUDED.has_complaint,
                cancellation_reason = EXCLUDED.cancellation_reason,
                cancellation_owner = EXCLUDED.cancellation_owner,
                subtotal = EXCLUDED.subtotal,
                packaging_charges = EXCLUDED.packaging_charges,
                tax_charge = EXCLUDED.tax_charge,
                synced_at = NOW();
        """

        try:
            execute_supabase_query(query)
            print(f"  ✅ Batch {batch_num}/{total_batches} complete ({len(batch)} orders)")
        except Exception as e:
            print(f"  ❌ Batch {batch_num}/{total_batches} failed: {e}")
            raise

    print(f"\n✅ Successfully upserted {len(orders)} orders to Supabase")

def print_summary(orders: List[Dict[str, Any]]) -> None:
    """Print summary statistics of extracted orders."""
    if not orders:
        return

    # Group by store
    by_store = defaultdict(int)
    by_status = defaultdict(int)
    total_revenue = 0.0

    for order in orders:
        by_store[order.get('_restaurant_name', 'Unknown')] += 1
        by_status[order['order_status']] += 1
        if order['subtotal']:
            total_revenue += order['subtotal']

    print("\n📈 Orders by Store:")
    for store, count in sorted(by_store.items(), key=lambda x: x[1], reverse=True):
        print(f"  {store}: {count}")

    print("\n📊 Orders by Status:")
    for status, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")

    print(f"\n💰 Total Revenue: ₱{total_revenue:,.2f}")

def main():
    parser = argparse.ArgumentParser(
        description='Sync FoodPanda orders from Google Sheets to Supabase'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Target date (YYYY-MM-DD) for incremental sync'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD) for inclusive date range sync'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD) for inclusive date range sync'
    )
    parser.add_argument(
        '--daily',
        action='store_true',
        help='Sync yesterday\'s orders (for cron/CI usage)'
    )
    parser.add_argument(
        '--rolling-days',
        type=int,
        help='Sync an inclusive rolling window ending yesterday (for late-arriving sheet updates)'
    )
    parser.add_argument(
        '--backfill',
        action='store_true',
        help='Extract all historical orders'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Extract and print summary without upserting to Supabase'
    )
    parser.add_argument(
        '--fail-on-empty',
        action='store_true',
        help='Exit non-zero if extraction returns zero orders'
    )

    args = parser.parse_args()

    # Validate arguments
    mode_count = sum(
        [
            bool(args.date),
            bool(args.start_date or args.end_date),
            args.daily,
            bool(args.rolling_days),
            args.backfill,
        ]
    )
    if mode_count > 1:
        print("Cannot combine --date, --start-date/--end-date, --daily, --rolling-days, and --backfill")
        return 1
    if bool(args.start_date) != bool(args.end_date):
        print("Must specify both --start-date and --end-date together")
        return 1

    target_dates: Optional[set[date]] = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            target_dates = {target_date}
            print(f"Target date: {target_date}")
        except ValueError:
            print(f"Invalid date format: {args.date} (expected YYYY-MM-DD)")
            return 1
    elif args.start_date and args.end_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        except ValueError:
            print("Invalid start/end date format (expected YYYY-MM-DD)")
            return 1
        if start_date > end_date:
            print(f"Invalid date range: {start_date} is after {end_date}")
            return 1
        target_dates = set(build_date_range(start_date, end_date))
        print(f"Date range mode - syncing {start_date} to {end_date} ({len(target_dates)} day(s))")
    elif args.daily:
        target_date = (datetime.now(MANILA_TZ) - timedelta(days=1)).date()
        target_dates = {target_date}
        print(f"Daily mode - syncing yesterday: {target_date}")
    elif args.rolling_days:
        if args.rolling_days < 1:
            print("--rolling-days must be at least 1")
            return 1
        end_date = (datetime.now(MANILA_TZ) - timedelta(days=1)).date()
        start_date = end_date - timedelta(days=args.rolling_days - 1)
        target_dates = set(build_date_range(start_date, end_date))
        print(f"Rolling window mode - syncing {start_date} to {end_date} ({args.rolling_days} day(s))")
    elif args.backfill:
        print("Full backfill mode (extracting all orders)")
    else:
        # Default: today's date
        target_date = datetime.now(MANILA_TZ).date()
        target_dates = {target_date}
        print(f"Default target date (today): {target_date}")

    # Extract orders
    print(f"\n📥 Extracting FoodPanda orders...")
    orders = extract_foodpanda_orders(target_dates)

    if not orders:
        print("\n⚠️ No orders extracted")
        return 1 if args.fail_on_empty else 0

    # Print summary
    print_summary(orders)

    # Upsert to Supabase
    if not args.dry_run:
        upsert_orders_to_supabase(orders)
    else:
        print("\n🏷️  DRY RUN - No data written to Supabase")

    print("\n✅ Sync complete!")
    return 0

if __name__ == '__main__':
    exit(main())
