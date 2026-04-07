"""S169 — Tombstone S169 test orders in Supabase so they don't pollute analytics.

Targets rows where bill_number LIKE '99999%' AND business_date is within the
last 7 days. Marks them as cancelled with a [s169_test_cleanup] tag appended
to cancellation_reason. Does NOT delete -- preserves audit trail.

Usage:
    python scripts/s169_cleanup_test_orders.py [--dry-run]

Code only -- safe to run with --dry-run. Without --dry-run hits Supabase Mgmt API.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPABASE_PROJECT_REF = "csnniykjrychgajfrgua"
SUPABASE_MGMT_SQL_URL = (
    f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
)

REQUEST_TIMEOUT = 60


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Doppler
# ---------------------------------------------------------------------------


def get_doppler_secret(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            [
                "C:/Users/Sam/bin/doppler.exe",
                "secrets",
                "get",
                key,
                "--plain",
                "--project",
                "bei-erp",
                "--config",
                "dev",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=creationflags,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        log(f"  [DOPPLER_ERROR] {key}: {exc}")
    return ""


# ---------------------------------------------------------------------------
# Supabase Mgmt API
# ---------------------------------------------------------------------------


def supabase_query(sql: str, mgmt_token: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {mgmt_token}",
        "Content-Type": "application/json",
        "X-Source": "s169",
    }
    r = requests.post(
        SUPABASE_MGMT_SQL_URL,
        headers=headers,
        json={"query": sql},
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Supabase Mgmt API error {r.status_code}: {r.text[:300]}")
    body = r.json()
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "result" in body:
        return body["result"]
    return []


SELECT_SQL = """
SELECT id, location_id, bill_number, business_date, cancelled_at
  FROM pos_orders
 WHERE bill_number LIKE '99999%'
   AND business_date >= CURRENT_DATE - INTERVAL '7 days'
 ORDER BY business_date DESC, id DESC
 LIMIT 500
""".strip()

UPDATE_SQL_TEMPLATE = """
UPDATE pos_orders
   SET cancellation_reason = COALESCE(cancellation_reason, '') || ' [s169_test_cleanup]',
       cancelled_at = COALESCE(cancelled_at, NOW()),
       order_status = 'CANCELLED'
 WHERE id = ANY(ARRAY[{ids}]::bigint[])
RETURNING id, cancelled_at, cancellation_reason
""".strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="S169 cleanup test orders")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mgmt_token = get_doppler_secret("SUPABASE_MGMT_TOKEN")
    if not mgmt_token:
        log("FATAL: SUPABASE_MGMT_TOKEN unavailable")
        return 2

    log("Querying for S169 test rows (bill_number LIKE '99999%', last 7 days)")
    try:
        rows = supabase_query(SELECT_SQL, mgmt_token)
    except Exception as exc:
        log(f"FATAL: select failed: {exc}")
        return 2

    if not rows:
        log("No S169 test rows found. Nothing to clean up.")
        return 0

    log(f"Found {len(rows)} candidate row(s):")
    for row in rows:
        log(
            f"  id={row.get('id')} loc={row.get('location_id')} "
            f"bill={row.get('bill_number')} date={row.get('business_date')} "
            f"cancelled_at={row.get('cancelled_at')}"
        )

    if args.dry_run:
        log("DRY-RUN: no UPDATE will be issued.")
        return 0

    ids = [str(row["id"]) for row in rows if row.get("id") is not None]
    if not ids:
        log("No usable IDs to update.")
        return 0

    update_sql = UPDATE_SQL_TEMPLATE.format(ids=",".join(ids))
    log(f"Updating {len(ids)} row(s)...")
    try:
        result = supabase_query(update_sql, mgmt_token)
    except Exception as exc:
        log(f"FATAL: update failed: {exc}")
        return 2

    log(f"Tombstoned {len(result)} row(s):")
    log(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
