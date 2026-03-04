"""
Supabase → Frappe Bridge: Sync attendance punches to Employee Checkin

Reads enriched attendance punches from Supabase (where is_known_employee=true),
creates Employee Checkin records in Frappe via the add_log_based_on_employee_field API.

Uses a watermark table (frappe_sync_watermark) to track sync progress.
Designed to run every 5 minutes via GitHub Actions.

Usage:
    python scripts/sync_supabase_to_frappe.py
    python scripts/sync_supabase_to_frappe.py --dry-run
    python scripts/sync_supabase_to_frappe.py --batch-size 100
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
FRAPPE_API_KEY = os.environ["FRAPPE_API_KEY"]
FRAPPE_API_SECRET = os.environ["FRAPPE_API_SECRET"]

BATCH_SIZE = 500
SAFETY_BUFFER_MINUTES = 2  # Don't read punches newer than this
WATERMARK_SYNC_NAME = "attendance_checkin"

# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def get_watermark(client: httpx.Client) -> str:
    """Read last_event_time from watermark table."""
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/frappe_sync_watermark",
        params={"sync_name": f"eq.{WATERMARK_SYNC_NAME}", "select": "last_event_time"},
        headers=supabase_headers(),
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        print("ERROR: No watermark row found. Run setup first.", file=sys.stderr)
        sys.exit(1)
    return rows[0]["last_event_time"]


def update_watermark(client: httpx.Client, new_time: str):
    """Advance watermark to new_time."""
    r = client.patch(
        f"{SUPABASE_URL}/rest/v1/frappe_sync_watermark",
        params={"sync_name": f"eq.{WATERMARK_SYNC_NAME}"},
        headers={**supabase_headers(), "Prefer": "return=minimal"},
        json={
            "last_event_time": new_time,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    r.raise_for_status()


def fetch_punches(client: httpx.Client, watermark: str, batch_size: int) -> list[dict]:
    """Fetch known-employee punches after watermark, with safety buffer.

    event_time in Supabase is properly stored in UTC (converted from PHT +08:00 by PostgreSQL).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SAFETY_BUFFER_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    # PostgREST: use 'and' operator for multiple conditions on same column
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/attendance_punches",
        params={
            "select": "id,pin,event_time,device_sn,employee_name,employee_id,store_name",
            "is_known_employee": "eq.true",
            "and": f"(event_time.gt.{watermark},event_time.lte.{cutoff})",
            "order": "event_time.asc",
            "limit": str(batch_size),
        },
        headers=supabase_headers(),
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Frappe helpers
# ---------------------------------------------------------------------------


def frappe_headers():
    return {"Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"}


def post_checkin(client: httpx.Client, pin: str, timestamp: str, device_id: str) -> dict:
    """Create Employee Checkin via Frappe API. Returns result dict."""
    r = client.post(
        f"{FRAPPE_URL}/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field",
        headers=frappe_headers(),
        json={
            "employee_field_value": pin,
            "timestamp": timestamp,
            "device_id": device_id or "",
            "employee_fieldname": "attendance_device_id",
        },
        timeout=30,
    )
    return {"status_code": r.status_code, "body": r.json() if r.status_code != 500 else r.text[:500]}


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------


def sync(dry_run: bool = False, batch_size: int = BATCH_SIZE):
    start = time.monotonic()

    with httpx.Client() as client:
        # 1. Read watermark
        watermark = get_watermark(client)
        print(f"Watermark: {watermark}")

        # 2. Fetch punches
        punches = fetch_punches(client, watermark, batch_size)
        print(f"Fetched {len(punches)} punches to sync")

        if not punches:
            print("Nothing to sync.")
            return {"synced": 0, "skipped": 0, "failed": 0, "duration_s": 0}

        if dry_run:
            print("DRY RUN — would sync these punches:")
            for p in punches[:10]:
                print(f"  {p['pin']} @ {p['event_time']} ({p.get('employee_name', '?')})")
            if len(punches) > 10:
                print(f"  ... and {len(punches) - 10} more")
            return {"synced": 0, "skipped": 0, "failed": 0, "duration_s": 0}

        # 3. Post each punch to Frappe
        synced = 0
        skipped = 0
        failed = 0
        last_successful_time = None
        skipped_details = []

        for i, punch in enumerate(punches):
            pin = punch["pin"]
            event_time = punch["event_time"]
            device_sn = punch.get("device_sn", "")

            # Convert ISO to Frappe format (YYYY-MM-DD HH:MM:SS) in PHT
            # event_time is in UTC, convert to PHT (+8) for Frappe
            try:
                dt = datetime.fromisoformat(event_time)
                pht = dt.astimezone(timezone(timedelta(hours=8)))
                frappe_ts = pht.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                frappe_ts = event_time

            result = post_checkin(client, pin, frappe_ts, device_sn)
            status = result["status_code"]

            if status == 200:
                synced += 1
                last_successful_time = event_time
            elif status == 417:
                # Frappe validation error — could be duplicate or missing employee
                body = result.get("body", {})
                exc_type = body.get("exc_type", "")
                message = str(body.get("_server_messages", body.get("message", "")))

                if "already" in message.lower() or "Duplicate" in message:
                    # Duplicate — count as OK, advance watermark past it
                    skipped += 1
                    last_successful_time = event_time
                elif "No Employee found" in message or "not found" in message.lower():
                    # Missing mapping — log and continue
                    skipped += 1
                    skipped_details.append(
                        f"  SKIP: pin={pin} time={event_time} reason=no_employee"
                    )
                    last_successful_time = event_time
                else:
                    # Unknown validation error — log and continue
                    skipped += 1
                    skipped_details.append(
                        f"  SKIP: pin={pin} time={event_time} reason={message[:100]}"
                    )
                    last_successful_time = event_time
            elif status in (401, 403):
                # Auth error — STOP immediately
                print(f"AUTH ERROR at punch {i + 1}/{len(punches)}: {result['body']}")
                failed += len(punches) - i
                break
            elif status >= 500:
                # Server error — STOP, don't advance watermark
                print(f"SERVER ERROR at punch {i + 1}/{len(punches)}: {result['body']}")
                failed += len(punches) - i
                break
            else:
                # Other error — log and continue
                failed += 1
                print(f"  ERROR: pin={pin} time={event_time} status={status}")
                # Still advance watermark past this punch to avoid infinite retry
                last_successful_time = event_time

            # Progress indicator every 50 punches
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{len(punches)} (synced={synced} skipped={skipped})")

        # 4. Update watermark
        if last_successful_time:
            update_watermark(client, last_successful_time)
            print(f"Watermark advanced to: {last_successful_time}")

        # 5. Summary
        duration = round(time.monotonic() - start, 1)
        print(f"\n{'='*50}")
        print(f"SYNC COMPLETE in {duration}s")
        print(f"  Synced:  {synced}")
        print(f"  Skipped: {skipped}")
        print(f"  Failed:  {failed}")
        print(f"{'='*50}")

        if skipped_details:
            print("\nSkipped details:")
            for d in skipped_details:
                print(d)

        stats = {"synced": synced, "skipped": skipped, "failed": failed, "duration_s": duration}

        # Non-zero exit if auth/server failure stopped the batch
        if failed > 0:
            sys.exit(1)

        return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Supabase attendance → Frappe Employee Checkin")
    parser.add_argument("--dry-run", action="store_true", help="Show what would sync without making changes")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Max punches per run (default: {BATCH_SIZE})")
    args = parser.parse_args()

    sync(dry_run=args.dry_run, batch_size=args.batch_size)
