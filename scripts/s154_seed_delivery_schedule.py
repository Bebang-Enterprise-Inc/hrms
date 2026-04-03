#!/usr/bin/env python3
"""
S154/S6: Seed initial delivery schedule from March actual data.

Creates the first 2 weeks of BEI Delivery Schedule Week records
with entries based on the Central Warehouse delivery schedule CSV.

Usage:
  python scripts/s154_seed_delivery_schedule.py --dry-run
  python scripts/s154_seed_delivery_schedule.py
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SCHEDULE_CSV = ROOT / "data" / "_CLEANROOM" / "central_warehouse_2026_03" / "delivery_schedule.csv"
STORE_MAPPING = ROOT / "hrms" / "fixtures" / "sales_dashboard_store_mapping.csv"

# Schedule pattern → days
SCHEDULE_TO_DAYS = {
    "MWF": ["Mon", "Wed", "Fri"],
    "TTHS": ["Tue", "Thu", "Sat"],
    "SUNDAY": ["Sun"],
}

# Store name normalization: CSV name → Frappe warehouse name prefix
STORE_NAME_MAP = {
    "MARKET": "Ayala Market Market",
    "MOA": "SM Mall Of Asia",
    "MEGAMALL": "SM Megamall",
    "NORTH EDSA": "SM North EDSA",
    "MANILA": "SM Manila",
    "PITX": "Megawide PITX",
    "SOUTHMALL": "SM Southmall",
    "THE TERMINAL": "The Terminal",
    "VALENZUELA": "SM Valenzuela",
    "SHAW": "SM Shaw",  # may not exist
    "THE GRID": "The Grid - Rockwell",
    "EVER COMMONWEALTH": "Ever Commonwealth",
    "ANTIPOLO": "Robinsons Antipolo",
    "EAST ORTIGAS": "SM East Ortigas",
    "FESTIVAL MALL": "Festival Mall Alabang",
    "GRAND CENTRAL": "SM Grand Central",
    "LCM": "Lucky Chinatown",
    "PASEO CENTER": "Megaworld Paseo Center",
    "FAIRVIEW": "Ayala Malls Fairview Terraces",
    "MARIKINA": "SM Marikina",
    "VENICE": "Megaworld Venice Grand Canal",
}


def _get_secret(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"{env_name} not found")


def load_store_mapping() -> dict[str, str]:
    """Load warehouse_name → warehouse_record_name from Frappe API."""
    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    mapping = {}

    # Fetch real warehouse names from Frappe
    try:
        import requests as req_lib
        resp = req_lib.get(
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
                # Build display→full name map
                # "ARANETA CITY - BEI" → key "ARANETA CITY"
                full_name = wh["name"]
                short = full_name.upper().replace(" - BEBANG ENTERPRISE INC.", "").replace(" - BEI", "").replace(" - BKI", "").strip()
                mapping[short] = full_name
                # Also index by title-case
                mapping[short.title()] = full_name
            print(f"  Loaded {len(mapping) // 2} warehouse mappings from Frappe")
            return mapping
    except Exception as e:
        print(f"  Warning: Frappe API fetch failed ({e}), falling back to CSV")

    # Fallback to CSV
    with open(STORE_MAPPING, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("warehouse_name") or "").strip()
            record = (row.get("warehouse_record_name") or "").strip()
            if name and record and not name.startswith("TEST-"):
                mapping[name] = record
    return mapping


def resolve_warehouse_name(csv_name: str, wh_map: dict[str, str]) -> str | None:
    """Resolve CSV store name to Frappe warehouse record name."""
    mapped = STORE_NAME_MAP.get(csv_name.strip().upper())
    if mapped and mapped in wh_map:
        return wh_map[mapped]
    # Try direct match
    for name, record in wh_map.items():
        if csv_name.upper() in name.upper():
            return record
    return None


def load_schedule_csv() -> list[dict]:
    """Load delivery schedule CSV."""
    entries = []
    with open(SCHEDULE_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            store = (row.get("store_name") or "").strip()
            schedule = (row.get("schedule") or "").strip().upper()
            if store and schedule in SCHEDULE_TO_DAYS:
                entries.append({"store": store, "schedule": schedule})
    return entries


def build_week_entries(
    schedule_rows: list[dict],
    wh_map: dict[str, str],
) -> list[dict]:
    """Build schedule entries from CSV data.

    Each store + day gets BOTH COLD and DRY deliveries (the most common pattern).
    """
    entries = []
    unresolved = set()

    for row in schedule_rows:
        wh_record = resolve_warehouse_name(row["store"], wh_map)
        if not wh_record:
            unresolved.add(row["store"])
            continue

        days = SCHEDULE_TO_DAYS.get(row["schedule"], [])
        for day in days:
            for dtype in ("COLD", "DRY"):
                entries.append({
                    "store": wh_record,
                    "day_of_week": day,
                    "delivery_type": dtype,
                })

    if unresolved:
        print(f"  Warning: {len(unresolved)} stores could not be resolved: {sorted(unresolved)}")

    return entries


def main():
    import argparse
    parser = argparse.ArgumentParser(description="S154/S6: Seed delivery schedule")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    wh_map = load_store_mapping()
    print(f"  Loaded {len(wh_map)} warehouse mappings")

    schedule_rows = load_schedule_csv()
    print(f"  Loaded {len(schedule_rows)} schedule entries from CSV")

    entries = build_week_entries(schedule_rows, wh_map)
    print(f"  Built {len(entries)} delivery entries")

    if args.dry_run:
        # Show summary
        from collections import Counter
        by_day = Counter(e["day_of_week"] for e in entries)
        by_type = Counter(e["delivery_type"] for e in entries)
        print(f"\n  By day: {dict(sorted(by_day.items()))}")
        print(f"  By type: {dict(by_type)}")
        print(f"\n  [DRY RUN] Would create 2 weeks of schedule")
        return

    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    # Create 2 weeks starting from the current Monday
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    for week_offset in range(2):
        week_start = monday + timedelta(weeks=week_offset)
        print(f"\n  Creating schedule for week of {week_start}...")

        payload = {
            "doctype": "BEI Delivery Schedule Week",
            "week_start": str(week_start),
            "published": 1 if week_offset == 0 else 0,
            "entries": entries,
        }

        try:
            resp = requests.post(
                f"{FRAPPE_URL}/api/resource/BEI Delivery Schedule Week",
                headers=headers,
                json={"data": json.dumps(payload)},
                timeout=60,
            )
            if resp.status_code in (200, 201):
                print(f"    Created with {len(entries)} entries (published={payload['published']})")
            else:
                print(f"    Warning: {resp.status_code} {resp.text[:300]}")
        except Exception as e:
            print(f"    Error: {e}")


if __name__ == "__main__":
    main()
