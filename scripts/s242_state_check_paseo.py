#!/usr/bin/env python3
"""S242 Phase 1.B.2: read-only state check of Paseo bill 39966 on 2026-04-21.

Confirms baseline before schema migration:
- FoodPanda 39966 PHP 704 — currently is_duplicate=false (canonical)
- POS 39966 PHP 228 — currently is_duplicate=true (tombstoned)

After Phase 3 schema migration + restoration, BOTH should be is_duplicate=false.

Output: output/s242/verification/paseo_pre_migration_state.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx


PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


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
    out = Path("output/s242/verification/paseo_pre_migration_state.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        r = client.post(
            MGMT_SQL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "query": (
                    "SELECT id, channel, payment_status, "
                    "       gross_sales::numeric AS gross_sales, "
                    "       net_sales::numeric AS net_sales, "
                    "       paid_at::text AS paid_at, "
                    "       is_duplicate "
                    "FROM pos_orders "
                    "WHERE location_id = 2177 "
                    "  AND business_date = '2026-04-21' "
                    "  AND bill_number = '39966' "
                    "ORDER BY paid_at;"
                )
            },
            timeout=30,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"SQL exec failed ({r.status_code}): {r.text[:300]}")
        rows = r.json()

    state = {
        "store": "Megaworld Paseo Center",
        "location_id": 2177,
        "business_date": "2026-04-21",
        "bill_number": "39966",
        "phase": "pre_migration",
        "rows": rows,
        "live_count": sum(1 for x in rows if not x["is_duplicate"]),
        "tombstone_count": sum(1 for x in rows if x["is_duplicate"]),
    }
    out.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

    # Sanity: expect exactly 1 live + 1 tombstone (FoodPanda canonical, POS dupe)
    print(f"[OK] Wrote {out}")
    print(f"     live_count={state['live_count']} tombstone_count={state['tombstone_count']}")
    for row in rows:
        print(f"     id={row['id']} channel={row['channel']!s:>10} "
              f"status={row['payment_status']!s:>6} "
              f"gross={float(row['gross_sales']):>8.2f} "
              f"is_duplicate={row['is_duplicate']}")

    if state["live_count"] != 1 or state["tombstone_count"] != 1:
        print("\n[STOP] Unexpected baseline state — expected 1 live + 1 tombstone")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
