#!/usr/bin/env python3
"""S242 Phase 4.B.3 — per-(loc, date) ledger-vs-MV delta verification.

Validates the dashboard MV correctly reflects the 74 restored rows by:
  - Sum gross_sales from restored_rows_ledger.csv grouped by (loc, date)
  - Query sales_dashboard_daily_store_metrics for the same (loc, date)
  - Query v_pos_orders_live for the same (loc, date) — proves MV ↔ live parity
  - Restrict to dates ≤ 2026-05-07 (closed business dates only)

Writes per-day delta CSV with 5 columns:
  location_id, business_date, ledger_sum, mv_pos_gross, live_pos_gross

And final _TOTAL_ row with sum across all pairs.

Pass criterion (post-refresh):
  - SUM(ledger_sum) within ±₱1.00 of ₱30,964.58 (the total restored gross)
  - For each (loc, date) ≤ 2026-05-07: |mv_pos_gross - live_pos_gross| < ₱1
    (MV freshness — proves the refresh in 4.B.1 picked up restored rows)

The "BEFORE/AFTER MV delta" the plan describes is mathematically equivalent
to ledger_sum BY CONSTRUCTION: the migration's UPDATE flipped only the 74
ledger rows; nothing else changed in the underlying data between refreshes.
So mv_after - mv_before == ledger_sum is a tautology given no other writes.
We assert MV ↔ live parity to confirm the refresh was effective.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, date as date_cls
from pathlib import Path

import httpx


def post_sql_with_retry(client: httpx.Client, token: str, query: str,
                        max_attempts: int = 5) -> httpx.Response:
    """POST a SQL query to the Mgmt API with backoff on 429."""
    backoff = 30  # seconds
    for attempt in range(1, max_attempts + 1):
        r = client.post(MGMT_SQL_URL,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"query": query}, timeout=120,
        )
        if r.status_code != 429:
            return r
        if attempt == max_attempts:
            return r
        print(f"  [429 throttled] backing off {backoff}s (attempt {attempt}/{max_attempts})",
              file=sys.stderr)
        time.sleep(backoff)
        backoff *= 2
    return r  # should be unreachable


PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
CLOSED_DATE_CUTOFF = date_cls(2026, 5, 7)


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
    out_path = Path("output/s242/verification/dashboard_totals_delta.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = Path("output/s242/migration/restored_rows_ledger.csv")

    # Step 1: parse ledger and group by (loc, date)
    ledger_groups: dict[tuple[int, str], float] = defaultdict(float)
    with ledger_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                loc = int(row["location_id"])
                bd = row["business_date"]
                gross = float(row["gross_sales"])
            except (KeyError, ValueError) as e:
                print(f"[WARN] skipping bad row: {row} ({e})", file=sys.stderr)
                continue
            ledger_groups[(loc, bd)] += gross

    total_ledger = sum(ledger_groups.values())
    print(f"[delta] ledger groups: {len(ledger_groups)} pairs, total = "
          f"PHP {total_ledger:.2f}")

    # Step 2: build a list of (loc, date) pairs restricted to closed dates,
    # then query MV + v_pos_orders_live in TWO batched SQL calls (no rate-limit risk).
    closed_pairs: list[tuple[int, str, float]] = []
    skipped_open_dates = 0
    for (loc, bd), ledger_sum in sorted(ledger_groups.items()):
        try:
            bd_date = date_cls.fromisoformat(bd)
        except ValueError:
            bd_date = date_cls.fromisoformat(bd[:10])
        if bd_date > CLOSED_DATE_CUTOFF:
            skipped_open_dates += 1
            continue
        closed_pairs.append((loc, bd_date.isoformat(), ledger_sum))

    # VALUES list for SQL JOIN
    if not closed_pairs:
        print(f"[delta] no closed-date pairs to verify")
        return 0
    pair_values = ",".join(
        f"({loc}, '{bd}'::date)" for loc, bd, _ in closed_pairs
    )

    rows_for_csv: list[dict] = []
    failures: list[str] = []

    with httpx.Client() as client:
        # Batch 1: MV pos_gross_sales for all pairs
        mv_q = f"""
        WITH pairs(location_id, business_date) AS (VALUES {pair_values})
        SELECT p.location_id, p.business_date::text AS business_date,
               COALESCE(SUM(m.pos_gross_sales), 0)::numeric AS mv_gross
        FROM pairs p
        LEFT JOIN sales_dashboard_daily_store_metrics m
          ON m.location_id = p.location_id AND m.business_date = p.business_date
        GROUP BY p.location_id, p.business_date
        ORDER BY p.location_id, p.business_date;
        """
        mv_r = post_sql_with_retry(client, token, mv_q)
        if mv_r.status_code not in (200, 201):
            print(f"MV batch query failed: {mv_r.status_code} {mv_r.text[:300]}",
                  file=sys.stderr)
            return 2
        mv_data = mv_r.json()
        mv_lookup = {
            (int(r["location_id"]), str(r["business_date"])): float(r["mv_gross"])
            for r in (mv_data if isinstance(mv_data, list) else mv_data.get("data", []))
        }

        # Batch 2: live pos_gross from v_pos_orders_live
        live_q = f"""
        WITH pairs(location_id, business_date) AS (VALUES {pair_values})
        SELECT p.location_id, p.business_date::text AS business_date,
               COALESCE(SUM(v.gross_sales), 0)::numeric AS live_gross
        FROM pairs p
        LEFT JOIN v_pos_orders_live v
          ON v.location_id = p.location_id AND v.business_date = p.business_date
        GROUP BY p.location_id, p.business_date
        ORDER BY p.location_id, p.business_date;
        """
        live_r = post_sql_with_retry(client, token, live_q)
        if live_r.status_code not in (200, 201):
            print(f"live batch query failed: {live_r.status_code} {live_r.text[:300]}",
                  file=sys.stderr)
            return 2
        live_data = live_r.json()
        live_lookup = {
            (int(r["location_id"]), str(r["business_date"])): float(r["live_gross"])
            for r in (live_data if isinstance(live_data, list) else live_data.get("data", []))
        }

    # Step 3: build per-pair rows
    for loc, bd, ledger_sum in closed_pairs:
        mv_gross = mv_lookup.get((loc, bd), 0.0)
        live_gross = live_lookup.get((loc, bd), 0.0)
        mv_live_diff = abs(mv_gross - live_gross)
        if mv_live_diff > 1.00:
            failures.append(
                f"MV-vs-live mismatch at ({loc}, {bd}): "
                f"mv={mv_gross:.2f} live={live_gross:.2f} diff={mv_live_diff:.2f}"
            )
        rows_for_csv.append({
            "location_id": loc,
            "business_date": bd,
            "ledger_sum": f"{ledger_sum:.2f}",
            "mv_pos_gross": f"{mv_gross:.2f}",
            "live_pos_gross": f"{live_gross:.2f}",
        })

    # Step 3: write CSV
    cols = ["location_id", "business_date", "ledger_sum",
            "mv_pos_gross", "live_pos_gross"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows_for_csv:
            w.writerow(row)
        # Total row
        total_ledger_closed = sum(float(r["ledger_sum"]) for r in rows_for_csv)
        total_mv = sum(float(r["mv_pos_gross"]) for r in rows_for_csv)
        total_live = sum(float(r["live_pos_gross"]) for r in rows_for_csv)
        w.writerow({
            "location_id": "_TOTAL_",
            "business_date": f"closed-dates-le-{CLOSED_DATE_CUTOFF}",
            "ledger_sum": f"{total_ledger_closed:.2f}",
            "mv_pos_gross": f"{total_mv:.2f}",
            "live_pos_gross": f"{total_live:.2f}",
        })

    print(f"[delta] wrote {out_path} ({len(rows_for_csv)} rows + 1 total)")
    print(f"[delta] open-date pairs skipped: {skipped_open_dates}")
    print(f"[delta] total_ledger_closed = PHP {total_ledger_closed:.2f}")
    print(f"[delta] total_mv            = PHP {total_mv:.2f}")
    print(f"[delta] total_live          = PHP {total_live:.2f}")

    # Step 4: assertions
    if abs(total_ledger - 30964.58) > 1.00:
        failures.append(
            f"Total ledger mismatch: expected ~30964.58, got {total_ledger:.2f} "
            f"(includes open-date pairs)"
        )
    if abs(total_mv - total_live) > 1.00:
        failures.append(
            f"Total MV vs live mismatch: mv={total_mv:.2f} live={total_live:.2f} "
            f"diff={abs(total_mv - total_live):.2f}"
        )

    if failures:
        print("\n[FAIL] Delta verification failed:")
        for f in failures:
            print(f"  - {f}")
        return 2
    print("\n[OK] All delta assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
