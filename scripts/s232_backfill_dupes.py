"""S232 Phase 0.6 — Backfill duplicate flags on existing pos_orders rows.

Resolves audit blocker A1 (must run BEFORE Phase 1.1 unique partial index ships).

Strategy:
  1. Find every (location_id, business_date, bill_number) cluster with >1 row
  2. For each cluster: kept_id = MIN(id) (deterministic tie-breaker per H7)
  3. Mark all OTHER rows in the cluster: is_duplicate=true, kept_order_id=<kept_id>
  4. Also set webhook_received_at = paid_at on all rows where webhook_received_at IS NULL
     (resolves H8 — historical poll rows had this NULL; cluster-window fallback can't function without it)
  5. Mark child rows (pos_order_items, pos_order_payments) is_duplicate=true via
     order_id IN (... is_duplicate=true ...)  — resolves audit B4

Idempotency:
  - Re-running this script is safe. Already-flagged rows stay flagged. The kept_order_id
    rule (MIN(id)) is deterministic across runs.

Pre-requirements:
  - The is_duplicate, kept_order_id, webhook_received_at columns must exist on pos_orders.
    This script will create them if missing (idempotent ADD COLUMN IF NOT EXISTS).
  - is_duplicate column must exist on pos_order_items and pos_order_payments. Same pattern.

Usage:
  python scripts/s232_backfill_dupes.py --dry-run     # default — preview only
  python scripts/s232_backfill_dupes.py --apply       # actually write
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "output" / "s232" / "verification"
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


def sql(query: str) -> list[dict]:
    if not MGMT_TOKEN:
        print("ERROR: SUPABASE_MGMT_TOKEN missing", flush=True)
        sys.exit(1)
    r = httpx.post(
        SQL_URL,
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=300,
    )
    if r.status_code >= 400:
        print(f"SQL error {r.status_code}: {r.text[:500]}", flush=True)
        r.raise_for_status()
    return r.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually write changes (default: --dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview only (default)")
    args = parser.parse_args()
    apply_changes = args.apply
    mode = "APPLY" if apply_changes else "DRY-RUN"

    print(f"S232 PHASE 0.6 BACKFILL — mode: {mode}")
    print(f"{'='*70}\n")

    # Step 1: Ensure columns exist (idempotent)
    print("[Step 1] Ensuring required columns exist on pos_orders + child tables...")
    if apply_changes:
        sql("""
        ALTER TABLE pos_orders
          ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false,
          ADD COLUMN IF NOT EXISTS kept_order_id BIGINT,
          ADD COLUMN IF NOT EXISTS webhook_received_at TIMESTAMPTZ;
        ALTER TABLE pos_order_items
          ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false;
        ALTER TABLE pos_order_payments
          ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false;
        """)
        print("  Columns ensured.")
    else:
        # Check current state
        col_check = sql("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name IN ('pos_orders','pos_order_items','pos_order_payments')
          AND column_name IN ('is_duplicate','kept_order_id','webhook_received_at')
        ORDER BY table_name, column_name;
        """)
        print(f"  Current dedup columns present: {col_check}")

    # Step 2: Discover dupe clusters
    print("\n[Step 2] Discovering duplicate clusters in pos_orders...")
    cluster_rows = sql("""
    WITH dupes AS (
      SELECT location_id, business_date, bill_number,
             COUNT(*)::int AS dupe_count,
             MIN(id) AS kept_id,
             ARRAY_AGG(id ORDER BY id) AS all_ids
      FROM pos_orders
      WHERE bill_number IS NOT NULL
      GROUP BY location_id, business_date, bill_number
      HAVING COUNT(*) > 1
    )
    SELECT location_id, business_date, bill_number, dupe_count,
           kept_id::int8 AS kept_id,
           all_ids
    FROM dupes
    ORDER BY dupe_count DESC, business_date DESC
    LIMIT 5000;
    """)
    print(f"  Clusters found: {len(cluster_rows)}")
    total_extras = sum(c["dupe_count"] - 1 for c in cluster_rows)
    print(f"  Total duplicate rows to flag: {total_extras}")

    # Persist cluster ledger BEFORE applying changes
    ledger_path = OUT / "dedup_collisions_before.csv"
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("location_id,business_date,bill_number,dupe_count,kept_id,all_ids\n")
        for c in cluster_rows:
            ids_str = "|".join(str(i) for i in c["all_ids"])
            f.write(f'{c["location_id"]},{c["business_date"]},{c["bill_number"]},'
                    f'{c["dupe_count"]},{c["kept_id"]},{ids_str}\n')
    print(f"  Ledger written: {ledger_path}")

    if total_extras == 0:
        print("\nNo duplicates to flag. Exiting.")
        sys.exit(0)

    # Step 3: Apply (or dry-run preview)
    print(f"\n[Step 3] {mode} — flagging duplicates on pos_orders...")
    if apply_changes:
        # Flag duplicates: every row whose id != kept_id within its cluster
        sql_update = """
        WITH dupes AS (
          SELECT location_id, business_date, bill_number, MIN(id) AS kept_id
          FROM pos_orders
          WHERE bill_number IS NOT NULL
          GROUP BY location_id, business_date, bill_number
          HAVING COUNT(*) > 1
        )
        UPDATE pos_orders p
        SET is_duplicate = true,
            kept_order_id = d.kept_id
        FROM dupes d
        WHERE p.location_id = d.location_id
          AND p.business_date = d.business_date
          AND p.bill_number = d.bill_number
          AND p.id <> d.kept_id;
        """
        sql(sql_update)

        # Verify
        verify = sql("""
        SELECT
          COUNT(*) FILTER (WHERE is_duplicate = true)::int AS flagged_count,
          COUNT(*) FILTER (WHERE is_duplicate = false AND bill_number IS NOT NULL)::int AS clean_count
        FROM pos_orders;
        """)
        print(f"  After flag: {verify[0]['flagged_count']} flagged, {verify[0]['clean_count']} clean.")

        # Step 4: webhook_received_at NULL backfill (H8)
        print("\n[Step 4] Backfilling webhook_received_at = paid_at where NULL (H8)...")
        sql("""
        UPDATE pos_orders
        SET webhook_received_at = paid_at
        WHERE webhook_received_at IS NULL
          AND paid_at IS NOT NULL;
        """)
        wri_check = sql("""
        SELECT COUNT(*) FILTER (WHERE webhook_received_at IS NULL)::int AS still_null,
               COUNT(*) FILTER (WHERE webhook_received_at IS NOT NULL)::int AS populated
        FROM pos_orders;
        """)
        print(f"  webhook_received_at: {wri_check[0]['populated']} populated, {wri_check[0]['still_null']} still NULL")

        # Step 5: cascade is_duplicate to children (B4)
        print("\n[Step 5] Cascading is_duplicate to pos_order_items + pos_order_payments...")
        sql("""
        UPDATE pos_order_items
        SET is_duplicate = true
        WHERE order_id IN (SELECT id FROM pos_orders WHERE is_duplicate = true);
        """)
        items_check = sql("""
        SELECT COUNT(*) FILTER (WHERE is_duplicate = true)::int AS flagged
        FROM pos_order_items;
        """)
        print(f"  pos_order_items flagged: {items_check[0]['flagged']}")

        sql("""
        UPDATE pos_order_payments
        SET is_duplicate = true
        WHERE order_id IN (SELECT id FROM pos_orders WHERE is_duplicate = true);
        """)
        pay_check = sql("""
        SELECT COUNT(*) FILTER (WHERE is_duplicate = true)::int AS flagged
        FROM pos_order_payments;
        """)
        print(f"  pos_order_payments flagged: {pay_check[0]['flagged']}")

        # Step 6: write after-state ledger
        print("\n[Step 6] Writing after-state ledger...")
        after = sql("""
        SELECT location_id, business_date, bill_number,
               COUNT(*)::int AS total_rows,
               COUNT(*) FILTER (WHERE is_duplicate = true)::int AS flagged_rows,
               MIN(id) FILTER (WHERE is_duplicate = false) AS kept_id
        FROM pos_orders
        WHERE bill_number IS NOT NULL
        GROUP BY location_id, business_date, bill_number
        HAVING COUNT(*) > 1
        ORDER BY total_rows DESC
        LIMIT 5000;
        """)
        after_path = OUT / "dedup_collisions_after.csv"
        with open(after_path, "w", encoding="utf-8") as f:
            f.write("location_id,business_date,bill_number,total_rows,flagged_rows,kept_id\n")
            for c in after:
                f.write(f'{c["location_id"]},{c["business_date"]},{c["bill_number"]},'
                        f'{c["total_rows"]},{c["flagged_rows"]},{c["kept_id"]}\n')
        print(f"  Ledger written: {after_path}")

        # Step 7: assertion — every cluster has exactly one kept (is_duplicate=false) row
        print("\n[Step 7] Asserting every cluster has exactly 1 kept row...")
        bad = sql("""
        SELECT COUNT(*)::int AS clusters_with_zero_kept
        FROM (
          SELECT location_id, business_date, bill_number
          FROM pos_orders
          WHERE bill_number IS NOT NULL
          GROUP BY location_id, business_date, bill_number
          HAVING COUNT(*) > 1
             AND COUNT(*) FILTER (WHERE is_duplicate = false) <> 1
        ) t;
        """)
        if bad[0]["clusters_with_zero_kept"] != 0:
            print(f"  ASSERTION FAIL: {bad[0]['clusters_with_zero_kept']} clusters have != 1 kept row")
            sys.exit(2)
        print("  All clusters have exactly 1 kept row.")

        # Final summary JSON
        result_path = OUT / "dedup_backfill_result.json"
        result_path.write_text(json.dumps({
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "mode": "APPLY",
            "clusters_flagged": len(cluster_rows),
            "rows_flagged_pos_orders": verify[0]["flagged_count"],
            "rows_flagged_pos_order_items": items_check[0]["flagged"],
            "rows_flagged_pos_order_payments": pay_check[0]["flagged"],
            "webhook_received_at_populated": wri_check[0]["populated"],
            "assertion_clusters_with_one_kept": "PASS",
        }, indent=2), encoding="utf-8")
        print(f"\nResult JSON: {result_path}")
    else:
        print("  DRY-RUN — would update:")
        print(f"    {total_extras} pos_orders rows → is_duplicate=true")
        print(f"    pos_order_items rows linked to those ~{total_extras*3} (avg 3 items/order)")
        print(f"    pos_order_payments rows linked to those ~{total_extras} (avg 1 payment/order)")
        print(f"    pos_orders rows with NULL webhook_received_at → set to paid_at")

    print(f"\nPHASE 0.6 BACKFILL: {mode} COMPLETE")


if __name__ == "__main__":
    main()
