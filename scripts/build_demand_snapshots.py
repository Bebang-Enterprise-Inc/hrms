#!/usr/bin/env python3
"""
S154/P1-P5: BOM-Based Demand Pipeline

Nightly batch (2 AM PHT) that computes per-store per-ingredient demand
from POS sales × BOM recipes, applies weather + delivery-schedule coverage,
and writes BEI Inventory Risk Snapshot records to Frappe.

Pipeline:
  1. Read BOM recipes from CSV (15 POS products × 46 ingredients)
  2. Read POS→BOM crosswalk for name mapping
  3. Query Supabase POS: per-store per-product daily sales (last 7 days)
  4. Query Supabase daily_weather: 7-day forecast per store
  5. Explode via BOM: POS sales × recipe → ingredient demand/day
  6. Apply weather multiplier with exponential decay weighting
  7. Write BEI Inventory Risk Snapshot to Frappe via REST API

Usage:
  python scripts/build_demand_snapshots.py
  python scripts/build_demand_snapshots.py --store "Araneta Gateway"
  python scripts/build_demand_snapshots.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
MANILA_TZ = ZoneInfo("Asia/Manila")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")

# BOM CSV: P05 extraction from official BEBANG STANDARD BOM PER SKU.xlsx
BOM_CSV = ROOT / "data" / "_CLEANROOM" / "migration_runs" / "2026-03-02_frappe_go_live_zero_hallucination_v1" / "01_packets" / "P05_BOM_UOM" / "inputs_normalized" / "BOM_RECIPES_PACKET.csv"

# POS→BOM crosswalk
CROSSWALK_CSV = ROOT / "data" / "_CLEANROOM" / "agent_runs" / "2026-03-10_s032-dual-repo-safe-clean-start" / "checkpoints" / "phase1_snapshots" / "BEI-ERP" / "root_untracked_archive" / "hrms" / "fixtures" / "store_ordering" / "bom_fg_to_pos_crosswalk_compact.csv"

# Store mapping: location_id → Frappe warehouse
STORE_MAPPING_CSV = ROOT / "hrms" / "fixtures" / "sales_dashboard_store_mapping.csv"

# Weather exponential decay weights (BD-2: nearer days count more)
WEATHER_DAY_WEIGHTS = {1: 1.00, 2: 0.85, 3: 0.70, 4: 0.55, 5: 0.40, 6: 0.25, 7: 0.15}

LOOKBACK_DAYS = 7
BUFFER_PCT = 0.15


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def _get_secret(env_name: str, doppler_name: str | None = None) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    doppler_key = doppler_name or env_name
    result = subprocess.run(
        [
            "C:/Users/Sam/bin/doppler.exe",
            "secrets", "get", doppler_key,
            "--plain", "--project", "bei-erp", "--config", "dev",
        ],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"{env_name} not found in env or Doppler")


def _supabase_get(table: str, params: dict | None = None) -> list[dict]:
    """Query Supabase REST API directly (avoids local supabase/ folder shadow)."""
    key = _get_secret("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_frappe_auth() -> tuple[str, str]:
    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    return api_key, api_secret


# ---------------------------------------------------------------------------
# P1: Extract BOM to structured data
# ---------------------------------------------------------------------------

def load_bom_recipes() -> dict[str, list[dict]]:
    """Load BOM CSV → {product_name_upper: [{item_code, grams_per_cup, sku_conversion}]}.

    The 15 POS products are the primary keys. Each has 2-12 ingredients.
    """
    bom: dict[str, list[dict]] = defaultdict(list)
    with open(BOM_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = (row.get("Product (FG)") or "").strip().upper()
            item_code = (row.get("Item Code") or "").strip()
            grams = float(row.get("Grams per Cup") or 0)
            sku_conv = float(row.get("SKU Conversion") or 0)
            if product and item_code and grams > 0:
                bom[product].append({
                    "item_code": item_code,
                    "ingredient": (row.get("Ingredient") or "").strip(),
                    "grams_per_cup": grams,
                    "sku_conversion": sku_conv,
                })
    print(f"  BOM loaded: {len(bom)} products, {sum(len(v) for v in bom.values())} ingredient rows")
    return dict(bom)


# ---------------------------------------------------------------------------
# P2: POS → BOM crosswalk
# ---------------------------------------------------------------------------

def load_pos_crosswalk() -> dict[str, str]:
    """Load {pos_item_name_lower: product_name_upper} mapping."""
    xwalk: dict[str, str] = {}
    with open(CROSSWALK_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fg = (row.get("fg_name") or "").strip().upper()
            pos = (row.get("pos_item_name_top1") or "").strip().lower()
            if fg and pos:
                xwalk[pos] = fg
    print(f"  Crosswalk loaded: {len(xwalk)} POS->BOM mappings")
    return xwalk


# ---------------------------------------------------------------------------
# Store mapping
# ---------------------------------------------------------------------------

def load_store_mapping() -> tuple[dict[int, str], dict[str, int]]:
    """Returns (location_id→warehouse_record_name, warehouse_name→location_id).

    S155: Queries Frappe API for actual warehouse names to avoid stale CSV mapping.
    Falls back to CSV if API fails.
    """
    loc_to_wh: dict[int, str] = {}
    wh_to_loc: dict[str, int] = {}

    # Build location_id map from CSV
    csv_name_to_loc: dict[str, int] = {}
    with open(STORE_MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("warehouse_name") or "").strip()
            loc = int(row.get("location_id") or 0)
            if name.startswith("TEST-") or not loc:
                continue
            csv_name_to_loc[name.upper()] = loc

    # Fetch real warehouse names from Frappe
    try:
        api_key, api_secret = get_frappe_auth()
        resp = requests.get(
            f"{FRAPPE_URL}/api/resource/Warehouse",
            params={
                "filters": json.dumps([["is_group", "=", 0], ["disabled", "=", 0]]),
                "fields": json.dumps(["name"]),
                "limit_page_length": 200,
            },
            headers={"Authorization": f"token {api_key}:{api_secret}"},
            timeout=15,
        )
        if resp.status_code == 200:
            for wh in resp.json().get("data", []):
                full_name = wh["name"]
                # Strip suffix to match CSV display name
                short = full_name.upper().replace(" - BEBANG ENTERPRISE INC.", "").replace(" - BEI", "").replace(" - BKI", "").strip()
                loc = csv_name_to_loc.get(short)
                if loc:
                    loc_to_wh[loc] = full_name
                    wh_to_loc[full_name] = loc
            print(f"  Store mapping: {len(loc_to_wh)} stores (Frappe API)")
            return loc_to_wh, wh_to_loc
    except Exception as e:
        print(f"  Warning: Frappe API failed ({e}), falling back to CSV")

    # Fallback to CSV (may have stale names)
    with open(STORE_MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("warehouse_name") or "").strip()
            record = (row.get("warehouse_record_name") or "").strip()
            loc = int(row.get("location_id") or 0)
            if name.startswith("TEST-") or not loc or not record:
                continue
            loc_to_wh[loc] = record
            wh_to_loc[name] = loc
    return loc_to_wh, wh_to_loc


# ---------------------------------------------------------------------------
# P3: Supabase POS query
# ---------------------------------------------------------------------------

def fetch_pos_sales(since_date: str) -> list[dict]:
    """Query per-store per-product daily sales from Supabase.

    Uses the Supabase REST API with embedded joins.
    Returns [{location_id, business_date, item_name, qty_sold}].
    """
    print(f"  Querying POS sales since {since_date}...")

    all_rows: list[dict] = []
    current = datetime.strptime(since_date, "%Y-%m-%d").date()
    today = datetime.now(MANILA_TZ).date()

    while current <= today:
        date_str = current.strftime("%Y-%m-%d")
        try:
            # Two-step query: orders first, then items
            orders = _supabase_get("pos_orders", {
                "select": "id,location_id",
                "business_date": f"eq.{date_str}",
                "payment_status": "eq.PAID",
                "limit": "5000",
            })
            if not orders:
                current += timedelta(days=1)
                continue
            order_map = {o["id"]: o["location_id"] for o in orders}
            order_ids = list(order_map.keys())
            # Batch query items for these orders
            for batch_start in range(0, len(order_ids), 200):
                batch = order_ids[batch_start:batch_start + 200]
                ids_str = ",".join(str(oid) for oid in batch)
                items = _supabase_get("pos_order_items", {
                    "select": "order_id,product_name,quantity",
                    "order_id": f"in.({ids_str})",
                    "limit": "10000",
                })
                for row in items:
                    loc = order_map.get(row.get("order_id"))
                    if loc:
                        all_rows.append({
                            "location_id": loc,
                            "business_date": date_str,
                            "item_name": row.get("product_name", ""),
                            "qty": float(row.get("quantity") or 0),
                        })
        except Exception as e:
            print(f"  Warning: POS query failed for {date_str}: {e}")
        current += timedelta(days=1)

    print(f"  POS data: {len(all_rows)} item rows fetched")
    return all_rows


def aggregate_pos_sales(
    raw_rows: list[dict],
    loc_to_wh: dict[int, str],
) -> dict[str, dict[str, float]]:
    """Aggregate POS sales → {warehouse: {pos_item_name_lower: avg_daily_qty}}.

    Averages over the number of days with data (not LOOKBACK_DAYS), to handle
    stores that were closed for a day.
    """
    # {warehouse: {item_lower: {dates_set, total_qty}}}
    accum: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"dates": set(), "total": 0.0}))

    for row in raw_rows:
        loc_id = row.get("location_id")
        if not loc_id:
            continue
        wh = loc_to_wh.get(int(loc_id))
        if not wh:
            continue
        item = (row.get("item_name") or "").strip().lower()
        qty = float(row.get("qty") or 0)
        bdate = row.get("business_date", "")
        if item and qty > 0:
            accum[wh][item]["dates"].add(bdate)
            accum[wh][item]["total"] += qty

    result: dict[str, dict[str, float]] = {}
    for wh, items in accum.items():
        result[wh] = {}
        for item, data in items.items():
            days_with_data = max(1, len(data["dates"]))
            result[wh][item] = round(data["total"] / days_with_data, 4)

    return result


# ---------------------------------------------------------------------------
# Weather data
# ---------------------------------------------------------------------------

def fetch_weather_forecast(location_ids: set[int]) -> dict[int, list[dict]]:
    """Fetch 7-day weather forecast from daily_weather table.

    Returns {location_id: [{date, max_temperature, is_rainy, business_impact}]}.
    """
    today = datetime.now(MANILA_TZ).date()
    end = today + timedelta(days=7)

    weather: dict[int, list[dict]] = defaultdict(list)
    if not location_ids:
        return weather

    try:
        loc_csv = ",".join(str(x) for x in location_ids)
        # PostgREST: use 'and' filter for date range (can't have duplicate keys)
        key = _get_secret("SUPABASE_SERVICE_ROLE_KEY")
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        url = (
            f"{SUPABASE_URL}/rest/v1/daily_weather"
            f"?select=location_id,date,max_temperature,is_rainy,business_impact"
            f"&location_id=in.({loc_csv})"
            f"&and=(date.gte.{today},date.lte.{end})"
            f"&order=date"
            f"&limit=5000"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        rows = resp.json()
        for row in rows:
            loc = row.get("location_id")
            if loc:
                weather[int(loc)].append(row)
    except Exception as e:
        print(f"  Warning: Weather query failed: {e}")

    print(f"  Weather: {sum(len(v) for v in weather.values())} forecast rows for {len(weather)} stores")
    return weather


def compute_weather_multiplier(forecast_rows: list[dict], coverage_days: int) -> float:
    """Apply exponential decay weighted weather multiplier.

    BD-2: >35°C → 1.15-1.30, rain → 0.85-0.90.
    Nearer days get more weight.
    """
    if not forecast_rows:
        return 1.0

    total_weight = 0.0
    weighted_mult = 0.0
    window = min(coverage_days, 7)

    for i, row in enumerate(forecast_rows[:window]):
        day_num = i + 1
        weight = WEATHER_DAY_WEIGHTS.get(day_num, 0.10)
        total_weight += weight

        temp = float(row.get("max_temperature") or 30)
        is_rainy = row.get("is_rainy", False)

        # Temperature multiplier
        if temp >= 37:
            day_mult = 1.30
        elif temp >= 35:
            day_mult = 1.15 + (temp - 35) * 0.075  # Linear interpolation 1.15→1.30
        else:
            day_mult = 1.0

        # Rain dampener
        if is_rainy:
            day_mult *= 0.88

        weighted_mult += day_mult * weight

    if total_weight <= 0:
        return 1.0

    return round(weighted_mult / total_weight, 4)


# ---------------------------------------------------------------------------
# P4: BOM explosion + weather + coverage
# ---------------------------------------------------------------------------

def explode_demand(
    store_pos_sales: dict[str, float],  # {pos_item_lower: avg_daily_qty}
    bom: dict[str, list[dict]],
    crosswalk: dict[str, str],
    weather_mult: float,
    coverage_days: int,
) -> dict[str, dict]:
    """Explode POS sales through BOM to get ingredient demand.

    Returns {item_code: {
        avg_daily_demand, projected_demand, bom_consumption,
        weather_multiplier, coverage_days, bom_breakdown
    }}.
    """
    # Aggregate per-ingredient demand
    ingredient_demand: dict[str, float] = defaultdict(float)
    ingredient_breakdown: dict[str, list[dict]] = defaultdict(list)

    for pos_item, daily_cups in store_pos_sales.items():
        product = crosswalk.get(pos_item)
        if not product:
            continue
        recipe = bom.get(product)
        if not recipe:
            continue

        for component in recipe:
            item_code = component["item_code"]
            # Convert cups sold → ingredient units
            # grams_per_cup / 1000 = kg per cup (if UOM is KG)
            # sku_conversion handles this — it's the fractional unit per cup
            units_per_cup = component["sku_conversion"]
            if units_per_cup <= 0:
                # Fallback: use grams_per_cup / 1000 for KG items
                units_per_cup = component["grams_per_cup"] / 1000.0

            daily_ingredient = daily_cups * units_per_cup
            ingredient_demand[item_code] += daily_ingredient
            ingredient_breakdown[item_code].append({
                "product": product,
                "cups_per_day": round(daily_cups, 2),
                "units_per_cup": round(units_per_cup, 4),
                "contribution": round(daily_ingredient, 4),
            })

    # Build final demand per ingredient
    result: dict[str, dict] = {}
    for item_code, base_daily in ingredient_demand.items():
        projected = base_daily * weather_mult * coverage_days
        suggested = projected * (1 + BUFFER_PCT)

        result[item_code] = {
            "avg_daily_demand": round(base_daily, 4),
            "bom_consumption": round(base_daily, 4),
            "projected_sales": round(base_daily * weather_mult, 4),
            "projected_demand": round(projected, 4),
            "suggested_with_buffer": round(suggested, 4),
            "weather_multiplier": weather_mult,
            "coverage_days": coverage_days,
            "bom_breakdown": ingredient_breakdown.get(item_code, []),
        }

    return result


# ---------------------------------------------------------------------------
# P5: Write to Frappe
# ---------------------------------------------------------------------------

def write_snapshots_to_frappe(
    warehouse: str,
    demand: dict[str, dict],
    snapshot_date: str,
    api_key: str,
    api_secret: str,
    dry_run: bool = False,
) -> int:
    """Write BEI Inventory Risk Snapshot records via Frappe REST API."""
    if not demand:
        return 0

    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    written = 0
    for item_code, data in demand.items():
        source_ref = json.dumps({
            "src": "bom_pipeline",
            "cov": data["coverage_days"],
            "wx": round(data["weather_multiplier"], 3),
        })

        payload = {
            "doctype": "BEI Inventory Risk Snapshot",
            "snapshot_date": snapshot_date,
            "item_code": item_code,
            "warehouse": warehouse,
            "avg_daily_demand": data["avg_daily_demand"],
            "coverage_window_days": data["coverage_days"],
            "source_reference": source_ref,
        }

        if dry_run:
            print(f"    [DRY] {item_code}: demand={data['avg_daily_demand']:.4f}/day, "
                  f"projected={data['projected_demand']:.2f} over {data['coverage_days']}d")
            written += 1
            continue

        try:
            resp = requests.post(
                f"{FRAPPE_URL}/api/resource/BEI Inventory Risk Snapshot",
                headers=headers,
                json={"data": json.dumps(payload)},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                written += 1
            else:
                print(f"    Warning: Failed to write {item_code}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"    Warning: Failed to write {item_code}: {e}")

    return written


# ---------------------------------------------------------------------------
# S155/EX2a: Delivery schedule → coverage window
# ---------------------------------------------------------------------------

# Cache schedule coverage across stores to avoid repeated API calls
_schedule_coverage_cache: dict[str, int] = {}


def _get_schedule_coverage(warehouse_name: str, api_key: str, api_secret: str) -> int:
    """Query delivery schedule to determine how many days between deliveries.

    For a store that gets deliveries Mon+Wed+Fri (3x/week), coverage = 2-3 days.
    For a store that gets daily, coverage = 1.
    For a store with no schedule, falls back to 3.
    """
    if warehouse_name in _schedule_coverage_cache:
        return _schedule_coverage_cache[warehouse_name]

    default_coverage = 3
    if not api_key:
        _schedule_coverage_cache[warehouse_name] = default_coverage
        return default_coverage

    try:
        # Get this week's published schedule for the store
        from datetime import date as dt_date
        today = datetime.now(MANILA_TZ).date()
        # Find Monday of this week
        monday = today - timedelta(days=today.weekday())

        resp = requests.get(
            f"{FRAPPE_URL}/api/method/hrms.api.store.get_store_schedule",
            params={"store": warehouse_name},
            headers={"Authorization": f"token {api_key}:{api_secret}"},
            timeout=10,
        )
        if resp.status_code != 200:
            _schedule_coverage_cache[warehouse_name] = default_coverage
            return default_coverage

        data = resp.json().get("message", {})
        entries = data.get("entries", [])
        if not entries:
            _schedule_coverage_cache[warehouse_name] = default_coverage
            return default_coverage

        # Count unique delivery days per cargo type
        cold_days = set()
        dry_days = set()
        for entry in entries:
            day = entry.get("day_of_week", "")
            dtype = entry.get("delivery_type", "")
            if dtype == "COLD":
                cold_days.add(day)
            elif dtype == "DRY":
                dry_days.add(day)

        # Use the LESS frequent cargo type's coverage
        # (if store gets COLD 3x/week but DRY 2x/week, use DRY's longer gap)
        all_days = max(len(cold_days), len(dry_days), 1)
        # 7 days / delivery_count = average gap between deliveries
        coverage = max(1, round(7 / all_days))
        _schedule_coverage_cache[warehouse_name] = coverage
        return coverage

    except Exception:
        _schedule_coverage_cache[warehouse_name] = default_coverage
        return default_coverage


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    store_filter: str | None = None,
    dry_run: bool = False,
    coverage_override: int | None = None,
):
    today = datetime.now(MANILA_TZ).date()
    since = today - timedelta(days=LOOKBACK_DAYS)
    snapshot_date = str(today)

    print(f"=== BOM Demand Pipeline — {snapshot_date} ===")
    print(f"  Lookback: {LOOKBACK_DAYS} days (since {since})")

    # Load static data
    bom = load_bom_recipes()
    crosswalk = load_pos_crosswalk()
    loc_to_wh, wh_to_loc = load_store_mapping()

    # Filter stores if requested
    if store_filter:
        filtered = {k: v for k, v in wh_to_loc.items() if store_filter.lower() in k.lower()}
        if not filtered:
            print(f"  No stores matching '{store_filter}'")
            return
        wh_to_loc = filtered
        loc_to_wh = {v: loc_to_wh[v] for v in filtered.values() if v in loc_to_wh}

    print(f"  Stores: {len(wh_to_loc)}")

    # P3: Fetch POS sales
    pos_raw = fetch_pos_sales(str(since))
    pos_by_store = aggregate_pos_sales(pos_raw, loc_to_wh)
    stores_with_data = len(pos_by_store)
    print(f"  Stores with POS data: {stores_with_data}")

    if stores_with_data == 0:
        print("  No POS data found. Exiting.")
        return

    # Fetch weather
    all_locs = set(wh_to_loc.values())
    weather_by_loc = fetch_weather_forecast(all_locs)

    # Get Frappe credentials
    if not dry_run:
        api_key, api_secret = get_frappe_auth()
    else:
        api_key = api_secret = ""

    # Process each store
    total_written = 0
    for wh_name, loc_id in wh_to_loc.items():
        wh_record = loc_to_wh.get(loc_id)
        if not wh_record:
            continue

        store_sales = pos_by_store.get(wh_record, {})
        if not store_sales:
            continue

        # S155/EX2a: Query delivery schedule for per-store coverage window
        # Stores with daily delivery get coverage=1, weekly stores get coverage=7, etc.
        if coverage_override:
            coverage = coverage_override
        else:
            coverage = _get_schedule_coverage(wh_name, api_key, api_secret)

        # Weather multiplier
        forecast = weather_by_loc.get(loc_id, [])
        weather_mult = compute_weather_multiplier(forecast, coverage)

        # Explode demand
        demand = explode_demand(store_sales, bom, crosswalk, weather_mult, coverage)

        if demand:
            print(f"  {wh_name}: {len(demand)} ingredients, weather={weather_mult:.3f}, coverage={coverage}d")
            count = write_snapshots_to_frappe(
                wh_record, demand, snapshot_date, api_key, api_secret, dry_run
            )
            total_written += count

    print(f"\n=== Done: {total_written} snapshots written ===")


def main():
    parser = argparse.ArgumentParser(description="S154: BOM-based demand pipeline")
    parser.add_argument("--store", help="Filter to a single store (partial match)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't write to Frappe")
    parser.add_argument("--coverage", type=int, help="Override coverage window days")
    args = parser.parse_args()

    run_pipeline(
        store_filter=args.store,
        dry_run=args.dry_run,
        coverage_override=args.coverage,
    )


if __name__ == "__main__":
    main()
