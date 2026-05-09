#!/usr/bin/env python3
"""S242 Phase 0.4 — capture baseline state of pos_orders before migration.

Outputs:
- output/s242/migration/before_state.json — full baseline snapshot
- output/s242/state/active_run.json — claim ownership

What it captures:
1. Current `pos_orders_bill_number_natural_key` index DDL (for rollback evidence).
2. Count of channel-distinct tombstones (rows_to_restore).
3. Count of same-channel tombstones (rows_to_keep_tombstoned).
4. Full row IDs + current values of the 74 rows that the migration will flip
   (id, location_id, business_date, bill_number, channel, gross_sales, net_sales,
    payment_status, paid_at, canonical_channel) — used for rollback if needed.
5. Channel-pair distribution (POS↔FoodPanda, POS↔GrabFood, etc.) — used by
   Phase 0.5 shape check (locked from 2026-05-08 snapshot:
   POS↔FoodPanda=40, POS↔GrabFood=26, POS↔Delivery=3, FoodPanda↔POS=2,
   GrabFood↔FoodPanda=2, GrabFood↔POS=1).

Idempotent: rerunnable; overwrites before_state.json.

Authentication: SUPABASE_MGMT_TOKEN from Doppler (project=bei-erp config=dev).
Project ref: csnniykjrychgajfrgua.

Headless rule: any subprocess call uses creationflags=CREATE_NO_WINDOW (0x08000000).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

# Locked snapshot from plan §"Population-level impact" (2026-05-08 13:30 PHT).
# Plan listed pairs in bidirectional notation (POS↔FoodPanda); the actual SQL
# groups by (canonical_channel, tombstone_channel). The pairs below use the
# canonical-first observed direction matching the Paseo bill 39966 example
# (FoodPanda PHP 704 beats POS PHP 228 → FoodPanda canonical, POS tombstone).
EXPECTED_PAIR_SHAPE = {
    ("FoodPanda", "POS"): 40,
    ("GrabFood", "POS"): 26,
    ("Delivery", "POS"): 3,
    ("FoodPanda", "GrabFood"): 2,
    ("POS", "FoodPanda"): 2,
    ("POS", "GrabFood"): 1,
}
SHAPE_TOLERANCE_PER_PAIR = 2


def get_token() -> str:
    """Fetch SUPABASE_MGMT_TOKEN from Doppler."""
    CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
    result = subprocess.run(
        ["doppler", "secrets", "get", "SUPABASE_MGMT_TOKEN", "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Doppler fetch failed: {result.stderr}")
    return result.stdout.strip()


def exec_sql(client: httpx.Client, token: str, sql: str) -> list[dict]:
    """Execute SQL via Supabase Management API and return result rows."""
    r = client.post(
        MGMT_SQL_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"SQL exec failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def main() -> int:
    token = get_token()
    out_dir = Path("output/s242/migration")
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = Path("output/s242/state")
    state_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        # 1. Capture current index definition
        index_rows = exec_sql(client, token, """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'pos_orders'
              AND indexname = 'pos_orders_bill_number_natural_key';
        """)
        current_index_ddl = index_rows[0]["indexdef"] if index_rows else None
        print(f"[1/5] Index DDL: {current_index_ddl}")

        # 2. Count of channel-distinct tombstones (rows_to_restore)
        restore_count_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT id AS canonical_id, location_id, business_date,
                     bill_number, channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT COUNT(*)::bigint AS row_count,
                   COALESCE(SUM(t.gross_sales), 0)::numeric AS total_gross
            FROM pos_orders t
            JOIN canonical c USING (location_id, business_date, bill_number)
            WHERE c.canonical_channel IS DISTINCT FROM t.channel
              AND t.is_duplicate = true
              AND t.payment_status = 'PAID'
              AND t.bill_number IS NOT NULL;
        """)
        rows_to_restore = int(restore_count_rows[0]["row_count"])
        gross_to_restore = float(restore_count_rows[0]["total_gross"])
        print(f"[2/5] rows_to_restore={rows_to_restore} gross={gross_to_restore:.2f}")

        # 3. Count of same-channel tombstones (rows_to_keep_tombstoned)
        keep_count_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT id AS canonical_id, location_id, business_date,
                     bill_number, channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT COUNT(*)::bigint AS row_count,
                   COALESCE(SUM(t.gross_sales), 0)::numeric AS total_gross
            FROM pos_orders t
            JOIN canonical c USING (location_id, business_date, bill_number)
            WHERE c.canonical_channel = t.channel
              AND t.is_duplicate = true
              AND t.payment_status = 'PAID'
              AND t.bill_number IS NOT NULL;
        """)
        rows_to_keep_tombstoned = int(keep_count_rows[0]["row_count"])
        print(f"[3/5] rows_to_keep_tombstoned={rows_to_keep_tombstoned}")

        # 4. Full row dump for rollback
        rollback_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT id AS canonical_id, location_id, business_date,
                     bill_number, channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT t.id, t.location_id, t.business_date::text AS business_date,
                   t.bill_number, t.channel, t.gross_sales::numeric AS gross_sales,
                   t.net_sales::numeric AS net_sales, t.payment_status,
                   t.paid_at::text AS paid_at,
                   c.canonical_channel, c.canonical_id
            FROM pos_orders t
            JOIN canonical c USING (location_id, business_date, bill_number)
            WHERE c.canonical_channel IS DISTINCT FROM t.channel
              AND t.is_duplicate = true
              AND t.payment_status = 'PAID'
              AND t.bill_number IS NOT NULL
            ORDER BY t.business_date, t.location_id, t.bill_number;
        """)
        print(f"[4/5] Captured {len(rollback_rows)} rollback rows")

        # 5. Channel-pair shape (canonical_channel × tombstone_channel)
        shape_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT id, location_id, business_date, bill_number,
                     channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT c.canonical_channel, t.channel AS tombstone_channel,
                   COUNT(*)::bigint AS pair_count
            FROM pos_orders t
            JOIN canonical c USING (location_id, business_date, bill_number)
            WHERE c.canonical_channel IS DISTINCT FROM t.channel
              AND t.is_duplicate = true
              AND t.payment_status = 'PAID'
              AND t.bill_number IS NOT NULL
            GROUP BY c.canonical_channel, t.channel
            ORDER BY pair_count DESC;
        """)
        observed_shape = {
            (row["canonical_channel"], row["tombstone_channel"]): int(row["pair_count"])
            for row in shape_rows
        }
        print(f"[5/5] Channel-pair shape: {observed_shape}")

        # Shape-match check (Phase 0.5)
        shape_match = True
        shape_deltas: list[dict] = []
        for pair, expected in EXPECTED_PAIR_SHAPE.items():
            observed = observed_shape.get(pair, 0)
            delta = abs(observed - expected)
            in_tolerance = delta <= SHAPE_TOLERANCE_PER_PAIR
            shape_deltas.append({
                "pair": f"{pair[0]}->{pair[1]}",
                "expected": expected,
                "observed": observed,
                "delta": delta,
                "within_tolerance": in_tolerance,
            })
            if not in_tolerance:
                shape_match = False
        # Check for new pair categories with >5 rows
        for pair, observed in observed_shape.items():
            if pair not in EXPECTED_PAIR_SHAPE and observed > 5:
                shape_match = False
                shape_deltas.append({
                    "pair": f"{pair[0]}->{pair[1]}",
                    "expected": 0,
                    "observed": observed,
                    "delta": observed,
                    "within_tolerance": False,
                    "note": "new pair category exceeding tolerance",
                })

        # Distinct store-day count
        store_days_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT location_id, business_date, bill_number,
                     channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT COUNT(DISTINCT (t.location_id, t.business_date))::bigint AS store_day_count
            FROM pos_orders t
            JOIN canonical c USING (location_id, business_date, bill_number)
            WHERE c.canonical_channel IS DISTINCT FROM t.channel
              AND t.is_duplicate = true
              AND t.payment_status = 'PAID'
              AND t.bill_number IS NOT NULL;
        """)
        store_day_count = int(store_days_rows[0]["store_day_count"])

    # Assemble before_state.json
    before_state = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "current_index_ddl": current_index_ddl,
        "rows_to_restore": rows_to_restore,
        "gross_to_restore": gross_to_restore,
        "rows_to_keep_tombstoned": rows_to_keep_tombstoned,
        "store_day_count": store_day_count,
        "channel_pair_distribution": [
            {"canonical_channel": k[0], "tombstone_channel": k[1], "count": v}
            for k, v in observed_shape.items()
        ],
        "channel_pair_shape_match": shape_match,
        "channel_pair_shape_deltas": shape_deltas,
        "rollback_rows": rollback_rows,
    }
    out_path = out_dir / "before_state.json"
    out_path.write_text(json.dumps(before_state, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Wrote {out_path}")
    print(f"     rows_to_restore={rows_to_restore}")
    print(f"     rows_to_keep_tombstoned={rows_to_keep_tombstoned}")
    print(f"     channel_pair_shape_match={shape_match}")

    # Phase 0.5 STOP gate
    if not shape_match:
        print("\n[STOP] Channel-pair shape check failed. Materially different from snapshot.")
        for d in shape_deltas:
            if not d.get("within_tolerance", True):
                print(f"  - {d['pair']}: expected {d['expected']}, observed {d['observed']} "
                      f"(delta={d['delta']}) {d.get('note', '')}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
