"""S189: Backfill daily_material_consumption from historical POS + Web orders.

Reads pos_order_items + web_order_items joined with their parent orders,
looks up BOM in product_bom, and bulk-upserts into daily_material_consumption.

Usage:
    python scripts/s189_backfill_consumption.py --from 2026-03-14 --to 2026-04-13
    python scripts/s189_backfill_consumption.py --from 2026-04-01 --to 2026-04-13 --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"


def sb_headers(prefer="return=minimal"):
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def mgmt_headers():
    return {
        "Authorization": f"Bearer {MGMT_TOKEN}",
        "Content-Type": "application/json",
    }


def run_sql(sql):
    """Execute SQL via Management API and return rows."""
    r = requests.post(MGMT_URL, headers=mgmt_headers(), json={"query": sql}, timeout=60)
    r.raise_for_status()
    return r.json()


def load_bom_lookup():
    """Load product_bom from Supabase into a dict keyed by product_name."""
    print("Loading product_bom lookup...")
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/product_bom",
        params={"select": "product_name,material_code,material_name,grams_per_serving", "is_active": "eq.true"},
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
    )
    r.raise_for_status()
    rows = r.json()
    lookup = {}
    for row in rows:
        pn = row["product_name"]
        if pn not in lookup:
            lookup[pn] = []
        lookup[pn].append(row)
    print(f"  Loaded {len(rows)} BOM entries for {len(lookup)} products")
    return lookup


def backfill_channel(channel, date_from, date_to, bom_lookup, dry_run=False):
    """Backfill consumption for one channel (POS or Web)."""
    if channel == "POS":
        items_table = "pos_order_items"
        orders_table = "pos_orders"
    else:
        items_table = "web_order_items"
        orders_table = "web_orders"

    print(f"\nBackfilling {channel} from {date_from} to {date_to}...")

    # S232 followup: filter is_duplicate when running for POS (web tables don't have the column).
    # Reading flagged dupes here would consume BOM materials twice for the same physical sale.
    pos_dupe_filter = (
        "AND COALESCE(o.is_duplicate, false) = false AND COALESCE(i.is_duplicate, false) = false"
        if channel == "POS" else ""
    )

    # Query aggregated sales per product per day per location
    sql = f"""
    SELECT
        o.business_date,
        o.location_id,
        i.product_name,
        SUM(COALESCE(i.quantity, 1)) AS total_qty
    FROM {items_table} i
    JOIN {orders_table} o ON o.id = i.order_id
    WHERE o.business_date >= '{date_from}'
      AND o.business_date <= '{date_to}'
      {pos_dupe_filter}
    GROUP BY o.business_date, o.location_id, i.product_name
    ORDER BY o.business_date, i.product_name
    """

    rows = run_sql(sql)
    print(f"  Got {len(rows)} aggregated sales rows")

    # Build consumption rows
    consumption = {}  # (date, material_code, channel, location_id) -> {cups, grams, name}
    unmatched = set()

    for row in rows:
        product_name = row["product_name"]
        bom_items = bom_lookup.get(product_name, [])
        if not bom_items:
            unmatched.add(product_name)
            continue

        qty = int(row["total_qty"])
        bdate = row["business_date"]
        loc = row["location_id"] or 0

        for bi in bom_items:
            key = (bdate, bi["material_code"], channel, loc)
            if key not in consumption:
                consumption[key] = {
                    "material_name": bi["material_name"],
                    "total_cups": 0,
                    "total_grams": 0.0,
                }
            consumption[key]["total_cups"] += qty
            consumption[key]["total_grams"] += qty * float(bi["grams_per_serving"])

    if unmatched:
        print(f"  WARNING: {len(unmatched)} products not in BOM: {sorted(unmatched)[:10]}...")

    # Build upsert payload
    upsert_rows = []
    for (bdate, mat_code, chan, loc), vals in consumption.items():
        upsert_rows.append({
            "business_date": bdate,
            "material_code": mat_code,
            "material_name": vals["material_name"],
            "channel": chan,
            "location_id": loc,
            "total_cups": vals["total_cups"],
            "total_grams": round(vals["total_grams"], 2),
        })

    print(f"  Built {len(upsert_rows)} consumption rows")

    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(upsert_rows)} rows")
        return len(upsert_rows)

    # Upsert in batches of 500
    batch_size = 500
    for i in range(0, len(upsert_rows), batch_size):
        batch = upsert_rows[i:i + batch_size]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/daily_material_consumption",
            headers=sb_headers("resolution=merge-duplicates,return=minimal"),
            json=batch,
        )
        if not r.ok:
            print(f"  ERROR batch {i//batch_size}: {r.status_code} {r.text[:200]}")
            sys.exit(1)
        print(f"  Upserted batch {i//batch_size + 1} ({len(batch)} rows)")

    return len(upsert_rows)


def main():
    parser = argparse.ArgumentParser(description="Backfill daily_material_consumption")
    parser.add_argument("--from", dest="date_from", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bom_lookup = load_bom_lookup()

    pos_count = backfill_channel("POS", args.date_from, args.date_to, bom_lookup, args.dry_run)
    web_count = backfill_channel("Web", args.date_from, args.date_to, bom_lookup, args.dry_run)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Total: {pos_count + web_count} consumption rows")
    print(f"  POS: {pos_count}, Web: {web_count}")


if __name__ == "__main__":
    main()
