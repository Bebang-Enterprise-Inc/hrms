"""S191 follow-up — investigate the 48 vs 36 vs 44 store gap.

Run via:
  doppler run --project bei-erp --config dev -- python output/s191-followup/store_gap_investigation.py
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).parent

# Supabase Mgmt API
SUPA_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
SUPA_PROJECT = os.environ.get("SUPABASE_PROJECT_ID", "csnniykjrychgajfrgua")
SUPA_URL = f"https://api.supabase.com/v1/projects/{SUPA_PROJECT}/database/query"

# Frappe API
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://lfg.bebang.ph").rstrip("/")
FRAPPE_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_SECRET = os.environ.get("FRAPPE_API_SECRET", "")


def supa(sql: str) -> list[dict]:
    r = requests.post(
        SUPA_URL,
        headers={"Authorization": f"Bearer {SUPA_TOKEN}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=180,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"Supabase SQL failed ({r.status_code}): {r.text[:600]}")
    p = r.json()
    return p if isinstance(p, list) else (p.get("result") or [])


def frappe(method: str, params: dict) -> dict:
    r = requests.get(
        f"{FRAPPE_URL}/api/method/{method}",
        headers={"Authorization": f"token {FRAPPE_KEY}:{FRAPPE_SECRET}"},
        params=params,
        timeout=120,
    )
    if r.status_code != 200:
        raise SystemExit(f"{method} HTTP {r.status_code}: {r.text[:600]}")
    return r.json().get("message") or {}


def main() -> int:
    print("[S191-followup] Store gap investigation")
    print(f"  Supabase project: {SUPA_PROJECT}")
    print(f"  Frappe URL: {FRAPPE_URL}")
    print()

    # 1. Supabase — distinct location_ids in each source, last 30 days
    print("== Supabase distinct location_ids (last 60 days) ==")

    mosaic_locs = supa("""
        SELECT DISTINCT location_id
        FROM public.v_pos_orders_live
        WHERE payment_status = 'PAID'
          AND business_date >= CURRENT_DATE - INTERVAL '60 days'
        ORDER BY location_id;
    """)
    mosaic_set = {int(r["location_id"]) for r in mosaic_locs}
    print(f"  v_pos_orders_live (all channels): {len(mosaic_set)} stores")

    mosaic_fp_locs = supa("""
        SELECT DISTINCT location_id
        FROM public.v_pos_orders_live
        WHERE payment_status = 'PAID' AND channel = 'FoodPanda'
          AND business_date >= CURRENT_DATE - INTERVAL '60 days'
        ORDER BY location_id;
    """)
    mosaic_fp_set = {int(r["location_id"]) for r in mosaic_fp_locs}
    print(f"  v_pos_orders_live (FoodPanda):    {len(mosaic_fp_set)} stores")

    legacy_fp_locs = supa("""
        SELECT DISTINCT location_id
        FROM public.foodpanda_orders
        WHERE LOWER(order_status) = 'delivered'
          AND business_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY location_id;
    """)
    legacy_fp_set = {int(r["location_id"]) for r in legacy_fp_locs}
    print(f"  foodpanda_orders (legacy 90 days): {len(legacy_fp_set)} stores")

    # 2. Supabase — MV distinct location_ids
    mv_locs = supa("""
        SELECT DISTINCT location_id
        FROM public.sales_dashboard_daily_store_metrics
        WHERE business_date >= CURRENT_DATE - INTERVAL '60 days'
        ORDER BY location_id;
    """)
    mv_set = {int(r["location_id"]) for r in mv_locs}
    print(f"  sales_dashboard_daily_store_metrics MV: {len(mv_set)} stores")

    # 3. Frappe — enumerate Company doctype (S188 per-store companies)
    print()
    print("== Frappe companies (S188 per-store) ==")
    # Use the frappe.client.get_list method
    companies = frappe(
        "frappe.client.get_list",
        {
            "doctype": "Company",
            "fields": '["name","company_name","parent_company","is_group","default_currency"]',
            "limit_page_length": "200",
        },
    )
    if isinstance(companies, list):
        comp_rows = companies
    else:
        comp_rows = companies.get("message") if isinstance(companies, dict) else []
    print(f"  Frappe Company (disabled=0): {len(comp_rows)} rows")
    for c in comp_rows[:5]:
        print(f"    - {c}")

    # 4. Frappe — custom field location_id on Company? Or Warehouse?
    # Use the BEI store ordering scope helper via sales_dashboard endpoint
    print()
    print("== Frappe Analytics scope (sales_dashboard) ==")
    try:
        scope_res = frappe(
            "hrms.api.sales_dashboard.get_sales_dashboard_overview",
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
        stores = scope_res.get("scope", {}).get("selected_stores") or []
        print(f"  Analytics scope.selected_stores: {len(stores)} stores")
        analytics_locs = []
        for s in stores[:50]:
            lid = s.get("location_id")
            name = s.get("store_name") or s.get("name") or s.get("company")
            analytics_locs.append((int(lid) if lid else None, name))
        analytics_set = {lid for lid, _ in analytics_locs if lid is not None}
        print(f"  Analytics distinct location_ids: {len(analytics_set)}")
    except Exception as e:
        print(f"  (could not fetch scope: {e})")
        analytics_set = set()
        analytics_locs = []

    # Union — total universe
    universe = mosaic_set | legacy_fp_set | mv_set | analytics_set
    print()
    print(f"== UNIVERSE (union of all sources): {len(universe)} location_ids ==")

    # Set diffs
    missing_from_analytics = universe - analytics_set
    missing_from_mosaic_recent = universe - mosaic_set
    missing_from_legacy_fp = universe - legacy_fp_set
    missing_from_mv = universe - mv_set

    # 5. Map location_id → store_name via Mosaic CSV + v_pos_orders_live sample
    # Try v_pos_orders_live for a store-name join (might not have — fall back to Mosaic KEYS CSV)
    name_map: dict[int, str] = {}
    # Try the MV first which has warehouse/store_name columns
    try:
        name_rows = supa("""
            SELECT DISTINCT location_id, warehouse
            FROM public.sales_dashboard_daily_store_metrics
            WHERE business_date >= CURRENT_DATE - INTERVAL '90 days';
        """)
        for r in name_rows:
            lid = int(r["location_id"])
            name_map[lid] = r.get("warehouse") or ""
    except Exception as e:
        print(f"  name_map fallback: {e}")

    # Also map from Mosaic CSV
    mosaic_csv = Path(__file__).resolve().parents[2] / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"
    if mosaic_csv.exists():
        import csv as _csv
        with mosaic_csv.open(encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                lid_raw = row.get("location_id") or row.get("locationId")
                if lid_raw:
                    try:
                        lid = int(lid_raw)
                    except Exception:
                        continue
                    if lid not in name_map or not name_map[lid]:
                        name_map[lid] = (
                            row.get("store_name") or row.get("storeName") or row.get("name") or ""
                        )

    def lookup(lid: int) -> str:
        return name_map.get(lid, "(unknown)")

    # Print diffs with names
    print()
    print("== Missing from Analytics scope (should be there) ==")
    for lid in sorted(missing_from_analytics):
        present_in = []
        if lid in mosaic_set: present_in.append("mosaic")
        if lid in legacy_fp_set: present_in.append("legacy_fp")
        if lid in mv_set: present_in.append("MV")
        print(f"  {lid:>5}  {lookup(lid):<42}  present_in=[{', '.join(present_in)}]")

    print()
    print("== Missing from recent Mosaic POS (last 60 days PAID) ==")
    for lid in sorted(missing_from_mosaic_recent):
        present_in = []
        if lid in legacy_fp_set: present_in.append("legacy_fp")
        if lid in mv_set: present_in.append("MV")
        if lid in analytics_set: present_in.append("analytics")
        print(f"  {lid:>5}  {lookup(lid):<42}  present_in=[{', '.join(present_in)}]")

    print()
    print("== Missing from Mosaic FoodPanda (last 60 days) ==")
    mosaic_fp_gap = universe - mosaic_fp_set
    for lid in sorted(mosaic_fp_gap):
        present_in = []
        if lid in mosaic_set: present_in.append("mosaic_other")
        if lid in legacy_fp_set: present_in.append("legacy_fp")
        if lid in analytics_set: present_in.append("analytics")
        print(f"  {lid:>5}  {lookup(lid):<42}  present_in=[{', '.join(present_in)}]")

    # Dump JSON
    payload = {
        "counts": {
            "mosaic_all_channels": len(mosaic_set),
            "mosaic_foodpanda": len(mosaic_fp_set),
            "legacy_foodpanda": len(legacy_fp_set),
            "daily_store_metrics_MV": len(mv_set),
            "analytics_scope": len(analytics_set),
            "universe": len(universe),
            "frappe_companies": len(comp_rows),
        },
        "sets": {
            "mosaic_all_channels": sorted(mosaic_set),
            "mosaic_foodpanda": sorted(mosaic_fp_set),
            "legacy_foodpanda": sorted(legacy_fp_set),
            "daily_store_metrics_MV": sorted(mv_set),
            "analytics_scope": sorted(analytics_set),
            "universe": sorted(universe),
        },
        "diffs": {
            "missing_from_analytics": sorted(missing_from_analytics),
            "missing_from_mosaic_recent": sorted(missing_from_mosaic_recent),
            "missing_from_legacy_fp": sorted(missing_from_legacy_fp),
            "missing_from_mv": sorted(missing_from_mv),
            "missing_from_mosaic_foodpanda": sorted(mosaic_fp_gap),
        },
        "analytics_stores": [[lid, n] for lid, n in analytics_locs],
        "name_map": name_map,
    }
    (OUT / "store_gap_result.json").write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print()
    print(f"Wrote {OUT / 'store_gap_result.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
