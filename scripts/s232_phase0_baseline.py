"""S232 Phase 0 — baseline + synthetic store check + raw scope audit.

Tasks 0.4, 0.5, 0.7 in one script (read-only on Supabase):
- 0.4 Verify synthetic test store ID 9999 is free
- 0.5 Generate state_before.json baseline counts
- 0.7 Audit pos_orders_raw consumers + duplicate state

Uses Supabase Management API SQL endpoint (no SUPABASE_PG_URL needed).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "s232" / "verification"
OUT.mkdir(parents=True, exist_ok=True)


def _doppler(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    r = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


MGMT_TOKEN = _doppler("SUPABASE_MGMT_TOKEN")
PROJECT_REF = "csnniykjrychgajfrgua"
SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

if not MGMT_TOKEN:
    print("ERROR: SUPABASE_MGMT_TOKEN not in Doppler", flush=True)
    sys.exit(1)


def sql(query: str) -> list[dict]:
    r = httpx.post(
        SQL_URL,
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=120,
    )
    if r.status_code >= 400:
        print(f"SQL error {r.status_code}: {r.text[:400]}", flush=True)
        r.raise_for_status()
    return r.json()


print("=" * 70)
print("S232 PHASE 0 BASELINE")
print("=" * 70)

# 0.4: synthetic store ID 9999 collision check
print("\n[0.4] Synthetic store ID 9999 collision check...")
result = sql("SELECT count(*)::int AS hits FROM pos_orders WHERE location_id = 9999")
hits_9999 = int(result[0]["hits"])
synthetic_status = "PASS" if hits_9999 == 0 else "FAIL"
print(f"  Hits at location_id=9999: {hits_9999} → {synthetic_status}")

# Also check 999999 as extra-safe alternative
alt_check = sql("SELECT count(*)::int AS hits FROM pos_orders WHERE location_id = 999999")
print(f"  Hits at location_id=999999 (alt): {alt_check[0]['hits']}")

# 0.5: state_before baseline
print("\n[0.5] Generating state_before baseline...")

q_orders_14d = sql("""
SELECT
  COUNT(*)::int AS total_orders,
  COUNT(DISTINCT id)::int AS unique_ids,
  COUNT(DISTINCT (location_id, business_date, bill_number))::int AS unique_bills,
  COALESCE(ROUND(SUM(original_gross_sales)::numeric, 2)::float8, 0) AS gross_14d_sum,
  COALESCE(ROUND(SUM(net_sales)::numeric, 2)::float8, 0) AS net_14d_sum,
  COUNT(DISTINCT location_id)::int AS unique_locations
FROM pos_orders
WHERE business_date >= CURRENT_DATE - INTERVAL '14 days'
  AND bill_number IS NOT NULL;
""")

q_dupes = sql("""
SELECT COUNT(*)::int AS dupe_clusters,
       COALESCE(SUM(dupe_count - 1)::int, 0) AS extra_rows
FROM (
  SELECT location_id, business_date, bill_number, COUNT(*) AS dupe_count
  FROM pos_orders
  WHERE business_date >= CURRENT_DATE - INTERVAL '14 days'
    AND bill_number IS NOT NULL
  GROUP BY location_id, business_date, bill_number
  HAVING COUNT(*) > 1
) t;
""")

q_dupes_alltime = sql("""
SELECT COUNT(*)::int AS dupe_clusters,
       COALESCE(SUM(dupe_count - 1)::int, 0) AS extra_rows
FROM (
  SELECT location_id, business_date, bill_number, COUNT(*) AS dupe_count
  FROM pos_orders
  WHERE bill_number IS NOT NULL
  GROUP BY location_id, business_date, bill_number
  HAVING COUNT(*) > 1
) t;
""")

q_ingestion = sql("""
SELECT ingestion_source, COUNT(*)::int AS rows
FROM pos_orders
WHERE business_date >= CURRENT_DATE - INTERVAL '14 days'
GROUP BY ingestion_source;
""")

q_items_14d = sql("""
SELECT COUNT(*)::int AS total_items
FROM pos_order_items
WHERE order_id IN (
  SELECT id FROM pos_orders WHERE business_date >= CURRENT_DATE - INTERVAL '14 days'
);
""")

q_payments_14d = sql("""
SELECT COUNT(*)::int AS total_payments
FROM pos_order_payments
WHERE order_id IN (
  SELECT id FROM pos_orders WHERE business_date >= CURRENT_DATE - INTERVAL '14 days'
);
""")

q_null_payment_fp = sql("""
SELECT COUNT(*)::int AS fp_orders_no_payment
FROM pos_orders po
WHERE po.business_date >= CURRENT_DATE - INTERVAL '14 days'
  AND po.service_channel_id IN (1, 2)
  AND NOT EXISTS (SELECT 1 FROM pos_order_payments pop WHERE pop.order_id = po.id);
""")

# 0.7: pos_orders_raw scope
print("\n[0.7] pos_orders_raw scope audit...")

# First, discover columns
raw_columns = sql("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND table_name='pos_orders_raw'
ORDER BY ordinal_position;
""")
print(f"  pos_orders_raw columns: {[c['column_name'] for c in raw_columns]}")
state_raw_cols = [c["column_name"] for c in raw_columns]

# Pick the right timestamp column
ts_col = None
for cand in ("ingested_at", "synced_at", "fetched_at", "inserted_at", "updated_at", "business_date"):
    if cand in state_raw_cols:
        ts_col = cand
        break

q_raw_total = sql(f"SELECT COUNT(*)::int AS rows FROM pos_orders_raw WHERE synced_at >= CURRENT_DATE - INTERVAL '14 days';")
if "bill_number" in state_raw_cols:
    q_raw_dupes = sql("""
    SELECT COUNT(*)::int AS dupe_clusters,
           COALESCE(SUM(dupe_count - 1)::int, 0) AS extra_rows
    FROM (
      SELECT location_id, business_date, bill_number, COUNT(*) AS dupe_count
      FROM pos_orders_raw
      WHERE synced_at >= CURRENT_DATE - INTERVAL '14 days'
        AND bill_number IS NOT NULL
      GROUP BY location_id, business_date, bill_number
      HAVING COUNT(*) > 1
    ) t;
    """)
else:
    # B3 RESOLUTION: pos_orders_raw is forensics-only (raw JSON dump, indexed by Mosaic order_id)
    # No bill_number/location_id/business_date columns to natural-key dedup on.
    # Decision: NO DEDUP needed — intentionally raw for vendor-side debugging.
    q_raw_dupes = [{"dupe_clusters": "n/a (no bill_number col — forensics-only)", "extra_rows": 0, "decision": "FORENSICS_ONLY_NO_DEDUP"}]

state = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "phase": "0",
    "synthetic_store_check": synthetic_status,
    "synthetic_store_hits_9999": hits_9999,
    "synthetic_store_hits_999999": int(alt_check[0]["hits"]),
    "pos_orders_14d": q_orders_14d[0],
    "pos_orders_14d_dupes": q_dupes[0],
    "pos_orders_alltime_dupes": q_dupes_alltime[0],
    "ingestion_source_14d": q_ingestion,
    "pos_order_items_14d_count": q_items_14d[0]["total_items"],
    "pos_order_payments_14d_count": q_payments_14d[0]["total_payments"],
    "fp_grab_orders_no_payment_14d": q_null_payment_fp[0]["fp_orders_no_payment"],
    "pos_orders_raw_14d_rows": q_raw_total[0]["rows"],
    "pos_orders_raw_14d_dupes": q_raw_dupes[0],
}

state_path = OUT / "state_before.json"
state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

print(f"\nWritten: {state_path}")
print(f"\nKey numbers:")
print(f"  pos_orders 14d: {state['pos_orders_14d']['total_orders']:,} rows / {state['pos_orders_14d']['unique_bills']:,} unique bills")
print(f"  pos_orders 14d dupes: {state['pos_orders_14d_dupes']['extra_rows']} extra rows in {state['pos_orders_14d_dupes']['dupe_clusters']} clusters")
print(f"  pos_orders ALL-TIME dupes: {state['pos_orders_alltime_dupes']['extra_rows']} extra rows in {state['pos_orders_alltime_dupes']['dupe_clusters']} clusters")
print(f"  ingestion_source: {state['ingestion_source_14d']}")
print(f"  pos_orders_raw 14d: {state['pos_orders_raw_14d_rows']:,} rows / {state['pos_orders_raw_14d_dupes']['extra_rows']} dupe extras")
print(f"  FP/Grab orders missing payment row: {state['fp_grab_orders_no_payment_14d']}")
print(f"  Synthetic store 9999 free: {state['synthetic_store_check']}")

if synthetic_status != "PASS":
    print("\nSTOP — synthetic store ID 9999 collides with real data. Pick alternate ID and edit plan inline.")
    sys.exit(2)

# 0.7: pos_orders_raw consumers — grep
import subprocess
print("\n[0.7b] Searching codebase for pos_orders_raw consumers...")
result = subprocess.run(
    ["grep", "-rln", "pos_orders_raw",
     str(ROOT / "hrms"),
     str(ROOT / "scripts"),
     "--include=*.py", "--include=*.sql"],
    capture_output=True, text=True,
)
consumer_files = [l for l in result.stdout.strip().splitlines() if l]
state["pos_orders_raw_consumers"] = consumer_files
state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
print(f"  Files referencing pos_orders_raw: {len(consumer_files)}")
for f in consumer_files:
    print(f"    {f}")

print("\nPHASE 0 BASELINE: COMPLETE")
