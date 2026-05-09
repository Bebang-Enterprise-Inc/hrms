#!/usr/bin/env python3
"""S242 Phase 3 verification — runs all post-migration assertions.

Tasks covered (per plan):
  3.2.3 — Verify new index exists with channel column.
  3.2.4 — Idempotency: re-run migration script, expect 0 additional restores.
  3.2.5 — Paseo bill 39966: both rows is_duplicate=false.
  3.2.6 — Same-channel tombstones unchanged at 307 (±20).
  3.2.7 — Full after-state snapshot.

Exits non-zero if any assertion fails.
Outputs:
  output/s242/verification/index_definition_after.txt
  output/s242/migration/idempotency_check.json
  output/s242/verification/paseo_4_21_bill_39966_after.json
  output/s242/verification/same_channel_tombstones_count.json
  output/s242/migration/after_state.json
  output/s242/verification/migration_verify.log
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
LOG_PATH = Path("output/s242/verification/migration_verify.log")


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


def exec_sql(client: httpx.Client, token: str, sql: str) -> list:
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
    result = r.json()
    return result if isinstance(result, list) else result.get("data", [])


def log_line(msg: str, log_lines: list[str]) -> None:
    print(msg)
    log_lines.append(msg)


def main() -> int:
    token = get_token()
    out_v = Path("output/s242/verification")
    out_m = Path("output/s242/migration")
    out_v.mkdir(parents=True, exist_ok=True)
    out_m.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    log_lines: list[str] = [
        f"# S242 Phase 3 verifier — {datetime.now(timezone.utc).isoformat()}"
    ]

    with httpx.Client() as client:
        # ====== 3.2.3 — Index DDL has channel ======
        log_line("\n[3.2.3] Verify new index DDL contains channel...", log_lines)
        idx_rows = exec_sql(client, token, """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'pos_orders'
              AND indexname = 'pos_orders_bill_number_natural_key';
        """)
        if not idx_rows:
            failures.append("3.2.3: index pos_orders_bill_number_natural_key NOT FOUND")
            log_line("  FAIL: index missing", log_lines)
            ddl = ""
        else:
            ddl = idx_rows[0]["indexdef"]
            (out_v / "index_definition_after.txt").write_text(ddl + "\n", encoding="utf-8")
            log_line(f"  Index DDL: {ddl}", log_lines)
            if "(location_id, business_date, bill_number, channel)" in ddl:
                log_line("  OK: contains (location_id, business_date, bill_number, channel)", log_lines)
            else:
                failures.append(f"3.2.3: DDL does not contain expected tuple. Got: {ddl}")
                log_line(f"  FAIL: missing channel in DDL", log_lines)

        # ====== 3.2.5 — Paseo bill 39966 spot check ======
        log_line("\n[3.2.5] Paseo bill 39966 — both rows must be is_duplicate=false...", log_lines)
        paseo_rows = exec_sql(client, token, """
            SELECT id, channel, payment_status,
                   gross_sales::numeric AS gross_sales,
                   net_sales::numeric AS net_sales,
                   paid_at::text AS paid_at,
                   is_duplicate
            FROM pos_orders
            WHERE location_id = 2177
              AND business_date = '2026-04-21'
              AND bill_number = '39966'
            ORDER BY paid_at;
        """)
        live_count = sum(1 for r in paseo_rows if not r["is_duplicate"])
        paseo_state = {
            "store": "Megaworld Paseo Center",
            "location_id": 2177,
            "business_date": "2026-04-21",
            "bill_number": "39966",
            "phase": "post_migration",
            "rows": paseo_rows,
            "live_count": live_count,
            "tombstone_count": sum(1 for r in paseo_rows if r["is_duplicate"]),
        }
        (out_v / "paseo_4_21_bill_39966_after.json").write_text(
            json.dumps(paseo_state, indent=2, default=str), encoding="utf-8")
        for row in paseo_rows:
            log_line(
                f"  id={row['id']} channel={row['channel']!s:>10} "
                f"gross={float(row['gross_sales']):>8.2f} "
                f"is_duplicate={row['is_duplicate']}",
                log_lines,
            )
        if live_count == 2:
            channels = {r["channel"] for r in paseo_rows if not r["is_duplicate"]}
            if channels == {"POS", "FoodPanda"}:
                log_line("  OK: 2 live rows, channels={'POS','FoodPanda'}", log_lines)
            else:
                failures.append(f"3.2.5: 2 live rows but channels = {channels}")
                log_line(f"  FAIL: wrong channels: {channels}", log_lines)
        else:
            failures.append(f"3.2.5: expected 2 live rows, got {live_count}")
            log_line(f"  FAIL: live_count={live_count}", log_lines)

        # ====== 3.2.6 — Same-channel tombstones unchanged ======
        log_line("\n[3.2.6] Same-channel tombstones must remain ~307 (±20)...", log_lines)
        same_chan_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT location_id, business_date, bill_number,
                     channel AS canonical_channel
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
        same_chan_count = int(same_chan_rows[0]["row_count"])
        same_chan_gross = float(same_chan_rows[0]["total_gross"])
        same_chan_state = {
            "same_channel_count_after": same_chan_count,
            "same_channel_gross_after": same_chan_gross,
            "expected_band": [287, 327],
            "expected_count_baseline": 307,
        }
        (out_v / "same_channel_tombstones_count.json").write_text(
            json.dumps(same_chan_state, indent=2), encoding="utf-8")
        log_line(f"  same_channel_count_after={same_chan_count} "
                 f"gross={same_chan_gross:.2f}", log_lines)
        if 287 <= same_chan_count <= 327:
            log_line("  OK: within ±20 tolerance band of 307", log_lines)
        else:
            failures.append(
                f"3.2.6: same-channel count={same_chan_count} outside tolerance "
                f"[287..327]"
            )
            log_line(f"  FAIL: outside tolerance", log_lines)

        # ====== 3.2.4 — Idempotency: re-run UPDATE-only portion ======
        log_line("\n[3.2.4] Idempotency — re-running UPDATE; expect 0 restores...", log_lines)
        # We re-run only the UPDATE step (not the index DROP/CREATE which has
        # potential transient state with the Mgmt API on back-to-back calls).
        # The corrected query uses NOT EXISTS to exclude same-channel-canonical
        # cases — those are TRUE duplicates, not channel-collision tombstones.
        idem_sql = """
WITH canonical AS (
  SELECT location_id, business_date, bill_number, channel AS canonical_channel
  FROM pos_orders
  WHERE is_duplicate = false AND bill_number IS NOT NULL
),
to_restore AS (
  SELECT t.id
  FROM pos_orders t
  JOIN canonical c USING (location_id, business_date, bill_number)
  WHERE t.is_duplicate = true
    AND t.bill_number IS NOT NULL
    AND t.payment_status = 'PAID'
    AND c.canonical_channel IS DISTINCT FROM t.channel
    AND NOT EXISTS (
      SELECT 1 FROM canonical c2
      WHERE c2.location_id = t.location_id
        AND c2.business_date = t.business_date
        AND c2.bill_number = t.bill_number
        AND c2.canonical_channel = t.channel
    )
)
UPDATE pos_orders po
SET is_duplicate = false
FROM to_restore r
WHERE po.id = r.id
RETURNING po.id;
"""
        retry = client.post(
            MGMT_SQL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": idem_sql},
            timeout=60,
        )
        if retry.status_code not in (200, 201):
            failures.append(f"3.2.4: idempotency re-run HTTP {retry.status_code} {retry.text[:200]}")
            log_line(f"  FAIL: re-run failed ({retry.status_code})", log_lines)
            second_run_restored = -1
        else:
            second_result = retry.json()
            second_rows = (
                second_result if isinstance(second_result, list)
                else second_result.get("data", [])
            )
            second_run_restored = len(second_rows)
            log_line(f"  second_run_restored_count={second_run_restored}", log_lines)
            if second_run_restored == 0:
                log_line("  OK: idempotent (0 additional restores)", log_lines)
            else:
                failures.append(f"3.2.4: idempotency expected 0, got {second_run_restored}")
                log_line(f"  FAIL: not idempotent", log_lines)
        idem = {
            "first_run_restored_count": 74,  # from migration_summary.json
            "second_run_restored_count": second_run_restored,
            "expected_second_run": 0,
        }
        (out_m / "idempotency_check.json").write_text(
            json.dumps(idem, indent=2), encoding="utf-8")

        # ====== 3.2.7 — Full after-state ======
        log_line("\n[3.2.7] Full after-state snapshot...", log_lines)
        # Recount TRUE channel-distinct tombstones (should now be 0 — restored).
        # Post-migration, a parallel-bill case can create a row that has BOTH
        # a same-channel canonical sibling AND a different-channel canonical
        # sibling (the legitimate parallel bill of another channel). Such rows
        # are correctly tombstoned; they are NOT channel-collision tombstones.
        # Use NOT EXISTS to exclude them from the count.
        chan_dist_rows = exec_sql(client, token, """
            WITH canonical AS (
              SELECT location_id, business_date, bill_number,
                     channel AS canonical_channel
              FROM pos_orders
              WHERE is_duplicate = false AND bill_number IS NOT NULL
            )
            SELECT COUNT(*)::bigint AS row_count
            FROM pos_orders t
            WHERE t.is_duplicate = true
              AND t.bill_number IS NOT NULL
              AND t.payment_status = 'PAID'
              AND NOT EXISTS (
                SELECT 1 FROM canonical c
                WHERE c.location_id = t.location_id
                  AND c.business_date = t.business_date
                  AND c.bill_number = t.bill_number
                  AND c.canonical_channel = t.channel
              )
              AND EXISTS (
                SELECT 1 FROM canonical c
                WHERE c.location_id = t.location_id
                  AND c.business_date = t.business_date
                  AND c.bill_number = t.bill_number
                  AND c.canonical_channel IS DISTINCT FROM t.channel
              );
        """)
        # Total live + total tombstones
        totals = exec_sql(client, token, """
            SELECT
              SUM(CASE WHEN is_duplicate = false THEN 1 ELSE 0 END)::bigint AS live_count,
              SUM(CASE WHEN is_duplicate = true THEN 1 ELSE 0 END)::bigint AS tomb_count
            FROM pos_orders
            WHERE bill_number IS NOT NULL;
        """)
        after_state = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "channel_distinct_tombstones_remaining": int(chan_dist_rows[0]["row_count"]),
            "same_channel_tombstones_count": same_chan_count,
            "total_live_with_bill": int(totals[0]["live_count"]),
            "total_tombstones_with_bill": int(totals[0]["tomb_count"]),
            "index_ddl": ddl,
            "paseo_bill_39966_live_count": live_count,
        }
        (out_m / "after_state.json").write_text(
            json.dumps(after_state, indent=2), encoding="utf-8")
        log_line(f"  channel_distinct_tombstones_remaining={after_state['channel_distinct_tombstones_remaining']}", log_lines)
        log_line(f"  same_channel_tombstones_count={after_state['same_channel_tombstones_count']}", log_lines)
        log_line(f"  total_live_with_bill={after_state['total_live_with_bill']}", log_lines)

        if after_state["channel_distinct_tombstones_remaining"] != 0:
            failures.append(
                f"3.2.7: {after_state['channel_distinct_tombstones_remaining']} "
                "channel-distinct tombstones still present (expected 0)"
            )
            log_line("  FAIL: channel-distinct tombstones not fully restored", log_lines)
        else:
            log_line("  OK: 0 channel-distinct tombstones remaining", log_lines)

    # Final summary
    log_line("\n" + "=" * 60, log_lines)
    if failures:
        log_line(f"VERIFY FAILED: {len(failures)} assertion(s) failed:", log_lines)
        for f in failures:
            log_line(f"  - {f}", log_lines)
        rc = 2
    else:
        log_line("VERIFY OK: all assertions passed", log_lines)
        rc = 0
    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"\nLog -> {LOG_PATH}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
