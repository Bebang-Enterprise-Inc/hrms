#!/usr/bin/env python3
"""S242 Phase 3 — schema migration: extend pos_orders_bill_number_natural_key
with channel discriminator + restore 74 channel-distinct tombstones.

Migration runs as a SINGLE TRANSACTION via the Supabase Management API:
  BEGIN;
    DROP INDEX IF EXISTS pos_orders_bill_number_natural_key;
    CREATE UNIQUE INDEX IF NOT EXISTS pos_orders_bill_number_natural_key
      ON public.pos_orders USING btree
        (location_id, business_date, bill_number, channel)
      WHERE ((bill_number IS NOT NULL) AND (is_duplicate = false));
    UPDATE pos_orders SET is_duplicate = false
      WHERE id IN (...74 ids whose canonical sibling has DIFFERENT channel...)
      RETURNING ...;
  COMMIT;

Outputs:
- output/s242/migration/restored_rows_ledger.csv — every flipped row's full
  values (id, location_id, business_date, bill_number, channel, gross_sales,
  net_sales, paid_at). Use this as the rollback list if needed.
- stdout: restored_count, JSON summary

Idempotent: re-running produces 0 additional updates (tombstones whose
canonical sibling has a DIFFERENT channel will all already be is_duplicate=false).

Headless rule: any subprocess uses creationflags=CREATE_NO_WINDOW.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


# Locked migration SQL — DO NOT MODIFY without writing a new migration plan.
MIGRATION_SQL = """
BEGIN;

-- Step A: Drop old index (silently no-op if already dropped)
DROP INDEX IF EXISTS public.pos_orders_bill_number_natural_key;

-- Step B: Recreate with channel as part of the natural key.
-- IF NOT EXISTS for true idempotency.
CREATE UNIQUE INDEX IF NOT EXISTS pos_orders_bill_number_natural_key
  ON public.pos_orders USING btree
    (location_id, business_date, bill_number, channel)
  WHERE ((bill_number IS NOT NULL) AND (is_duplicate = false));

-- Step C: Restore tombstones whose canonical sibling has a DIFFERENT channel.
-- SAME-channel tombstones (true Mosaic-returned-twice duplicates) stay
-- is_duplicate=true (the constraint above keeps them safely excluded from
-- the partial index).
WITH canonical AS (
  SELECT location_id, business_date, bill_number, channel AS canonical_channel
  FROM pos_orders
  WHERE is_duplicate = false AND bill_number IS NOT NULL
),
to_restore AS (
  SELECT t.id
  FROM pos_orders t
  JOIN canonical c
    ON c.location_id    = t.location_id
   AND c.business_date  = t.business_date
   AND c.bill_number    = t.bill_number
  WHERE t.is_duplicate = true
    AND t.bill_number IS NOT NULL
    AND t.payment_status = 'PAID'
    AND c.canonical_channel IS DISTINCT FROM t.channel
)
UPDATE pos_orders po
SET is_duplicate = false
FROM to_restore r
WHERE po.id = r.id
RETURNING po.id, po.location_id, po.business_date::text AS business_date,
          po.bill_number, po.channel, po.gross_sales::numeric AS gross_sales,
          po.net_sales::numeric AS net_sales, po.paid_at::text AS paid_at;

COMMIT;
"""


def get_token() -> str:
    CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
    r = subprocess.run(
        ["doppler", "secrets", "get", "SUPABASE_MGMT_TOKEN", "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Doppler fetch failed: {r.stderr}")
    return r.stdout.strip()


def main() -> int:
    token = get_token()
    out_dir = Path("output/s242/migration")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "restored_rows_ledger.csv"

    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[S242 migrate] started_at={started_at}")
    print(f"[S242 migrate] target: {PROJECT_REF}")

    with httpx.Client() as client:
        r = client.post(
            MGMT_SQL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": MIGRATION_SQL},
            timeout=120,
        )
        if r.status_code not in (200, 201):
            print(f"[STOP] Migration FAILED ({r.status_code}): {r.text[:500]}",
                  file=sys.stderr)
            return 2

        # The Management API returns the result of the LAST statement before
        # COMMIT — which is the UPDATE ... RETURNING. Each returned row is a
        # restored tombstone.
        result = r.json()
        # Result may be a list of rows directly, or {data: [...]} depending
        # on the API version. Handle both.
        if isinstance(result, dict) and "data" in result:
            restored_rows = result["data"]
        elif isinstance(result, list):
            restored_rows = result
        else:
            print(f"[WARN] Unexpected response shape: {type(result)}: "
                  f"{json.dumps(result, default=str)[:200]}", file=sys.stderr)
            restored_rows = []

    finished_at = datetime.now(timezone.utc).isoformat()
    restored_count = len(restored_rows)
    print(f"[S242 migrate] restored_count={restored_count}")
    print(f"[S242 migrate] finished_at={finished_at}")

    # Write the ledger
    if restored_rows:
        # Stable column order
        cols = [
            "id", "location_id", "business_date", "bill_number", "channel",
            "gross_sales", "net_sales", "paid_at",
        ]
        with ledger_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in restored_rows:
                w.writerow({c: row.get(c, "") for c in cols})
        print(f"[S242 migrate] ledger written to {ledger_path} "
              f"({len(restored_rows)} rows)")
    else:
        # Empty ledger — header only (idempotent re-run case)
        cols = [
            "id", "location_id", "business_date", "bill_number", "channel",
            "gross_sales", "net_sales", "paid_at",
        ]
        with ledger_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
        print(f"[S242 migrate] ledger written to {ledger_path} (0 rows — "
              f"either first run had nothing to restore, or this is a re-run)")

    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "restored_count": restored_count,
        "ledger_path": str(ledger_path),
    }
    summary_path = out_dir / "migration_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[OK] Summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
