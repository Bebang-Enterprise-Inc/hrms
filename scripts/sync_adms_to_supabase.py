"""
ADMS Attendance Sync: EC2 ADMS PostgreSQL → Supabase

Pulls biometric punch data from ADMS via AWS SSM, enriches with employee
data from Supabase employee_directory table, and upserts into
attendance_punches table. Supports incremental (hourly) and backfill modes.

Usage:
    python scripts/sync_adms_to_supabase.py --incremental
    python scripts/sync_adms_to_supabase.py --backfill --from 2026-01-01 --to 2026-01-31
    python scripts/sync_adms_to_supabase.py --backfill --from 2026-02-01 --store LCT
    python scripts/sync_adms_to_supabase.py --verify --date 2026-03-01
    python scripts/sync_adms_to_supabase.py --incremental --dry-run
"""

import argparse
import importlib.util
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Load device_mapping.py and roving_employees.py without triggering
# hrms/__init__.py (which imports frappe). Use importlib.util instead.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_device_mod = _load_module("device_mapping", _REPO_ROOT / "hrms" / "utils" / "device_mapping.py")
_roving_mod = _load_module("roving_employees", _REPO_ROOT / "hrms" / "utils" / "roving_employees.py")

DEVICE_TO_STORE: dict[str, str] = _device_mod.DEVICE_TO_STORE
get_store_name = _device_mod.get_store_name
is_roving = _roving_mod.is_roving

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INSTANCE_ID = "i-026b7477d27bd46d6"
DB_CONTAINER = "adms_receiver_adms-db_1"
REGION = "ap-southeast-1"
SSM_TIMEOUT = 60
SSM_POLL_INTERVAL = 2

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
UPSERT_BATCH_SIZE = 500
DEDUP_WINDOW_SECS = 60  # Near-duplicate suppression window


def _get_secret(env_name: str, doppler_name: str | None = None) -> str:
    """Get secret from env var, then Doppler fallback."""
    val = os.environ.get(env_name, "")
    if val:
        return val
    doppler_key = doppler_name or env_name
    doppler_exe = shutil.which("doppler") or "C:/Users/Sam/bin/doppler.exe"
    try:
        import subprocess
        result = subprocess.run(
            [doppler_exe, "secrets", "get", doppler_key,
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    print(f"ERROR: {env_name} not set and Doppler unavailable", flush=True)
    sys.exit(1)


SUPABASE_KEY = _get_secret("SUPABASE_SERVICE_ROLE_KEY")

# Shared headers
_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Employee Lookup (from Supabase employee_directory)
# ---------------------------------------------------------------------------

_employee_lookup: dict[str, dict] = {}


def _load_employee_lookup():
    """Load employee directory from Supabase table."""
    global _employee_lookup
    print("Loading employee directory from Supabase...", flush=True)

    rows = []
    offset = 0
    page_size = 1000
    while True:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/employee_directory"
            f"?select=bio_id,employee_name,employee_id,designation,department,store_location"
            f"&order=bio_id"
            f"&offset={offset}&limit={page_size}",
            headers=_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    for row in rows:
        bio_id = (row.get("bio_id") or "").strip()
        if bio_id:
            _employee_lookup[bio_id] = {
                "name": (row.get("employee_name") or "").strip(),
                "employee_id": (row.get("employee_id") or bio_id).strip(),
                "designation": (row.get("designation") or "").strip(),
                "department": (row.get("department") or "").strip(),
                "branch": (row.get("store_location") or "").strip(),
            }

    print(f"  Loaded {len(_employee_lookup)} employees from Supabase", flush=True)


def _enrich_punch(pin: str, device_sn: str) -> dict:
    """Enrich a raw punch with employee + device data."""
    store = DEVICE_TO_STORE.get(device_sn, f"UNKNOWN-{device_sn}")
    emp = _employee_lookup.get(pin, {})
    known = bool(emp.get("name"))
    roving = is_roving(pin)

    return {
        "store_name": store,
        "employee_name": emp.get("name") or None,
        "employee_id": emp.get("employee_id") or None,
        "designation": emp.get("designation") or None,
        "department": emp.get("department") or None,
        "home_store": emp.get("branch") or None,
        "is_known_employee": known,
        "is_roving": roving,
    }


# ---------------------------------------------------------------------------
# SSM Query Layer
# ---------------------------------------------------------------------------

def _get_ssm_client():
    import boto3
    return boto3.client("ssm", region_name=REGION)


def _run_ssm_query(ssm_client, sql: str, description: str = "query") -> str | None:
    """Execute SQL via SSM and return pipe-delimited output."""
    cmd = f"docker exec {DB_CONTAINER} psql -U adms -d adms -t -A -F'|' -c \"{sql}\""
    try:
        resp = ssm_client.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [cmd]},
        )
        command_id = resp["Command"]["CommandId"]

        elapsed = 0
        result = None
        while elapsed < SSM_TIMEOUT:
            time.sleep(SSM_POLL_INTERVAL)
            elapsed += SSM_POLL_INTERVAL
            try:
                result = ssm_client.get_command_invocation(
                    CommandId=command_id, InstanceId=INSTANCE_ID
                )
                if result["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
                    break
            except ssm_client.exceptions.InvocationDoesNotExist:
                continue

        if result and result["Status"] == "Success":
            output = result.get("StandardOutputContent", "").strip()
            # SSM truncates output at ~24KB, appending "--output truncated--"
            # which corrupts the last data line. Strip the marker and drop
            # the corrupted final line.
            if output.endswith("--output truncated--"):
                output = output[: -len("--output truncated--")]
                lines = output.strip().splitlines()
                if lines:
                    lines = lines[:-1]  # Drop last (partial) line
                output = "\n".join(lines)
                print(f"  SSM WARN [{description}]: output truncated, dropped last line", flush=True)
            return output
        else:
            status = result["Status"] if result else "NoResult"
            err = (result.get("StandardErrorContent", "") if result else "")[:300]
            print(f"  SSM FAILED [{description}]: {status} — {err}", flush=True)
            return None

    except Exception as e:
        print(f"  SSM ERROR [{description}]: {e}", flush=True)
        return None


def _parse_ssm_output(raw: str) -> list[dict]:
    """Parse pipe-delimited SSM output into punch records.

    ADMS attlog_raw columns: id | pin | event_time | status_code | verify_code | sn
    Pipe delimiter avoids comma issues with employee names in other queries.
    Note: status_code and verify_code are VARCHAR in ADMS, cast to INT here.
    """
    rows = []
    for line in raw.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 6:
            continue
        try:
            rows.append({
                "adms_id": parts[0].strip(),
                "pin": parts[1].strip(),
                "event_time": parts[2].strip(),
                "status_code": int(parts[3].strip()) if parts[3].strip().isdigit() else 0,
                "verify_code": int(parts[4].strip()) if parts[4].strip().isdigit() else 0,
                "device_sn": parts[5].strip(),
            })
        except (ValueError, IndexError):
            continue
    return rows


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_punches(punches: list[dict]) -> list[dict]:
    """Remove near-duplicate punches within DEDUP_WINDOW_SECS for same pin+device."""
    if not punches:
        return []

    # Sort by pin, device, time
    punches.sort(key=lambda p: (p["pin"], p["device_sn"], p["event_time"]))

    deduped = [punches[0]]
    for p in punches[1:]:
        prev = deduped[-1]
        if p["pin"] == prev["pin"] and p["device_sn"] == prev["device_sn"]:
            try:
                t_curr = datetime.fromisoformat(p["event_time"].replace("+08", "+08:00"))
                t_prev = datetime.fromisoformat(prev["event_time"].replace("+08", "+08:00"))
                if abs((t_curr - t_prev).total_seconds()) < DEDUP_WINDOW_SECS:
                    continue
            except (ValueError, TypeError):
                pass
        deduped.append(p)

    removed = len(punches) - len(deduped)
    if removed:
        print(f"  Dedup: removed {removed} near-duplicates ({len(deduped)} remaining)", flush=True)
    return deduped


# ---------------------------------------------------------------------------
# Supabase Upsert
# ---------------------------------------------------------------------------

def _upsert_punches(punches: list[dict], dry_run: bool = False) -> int:
    """Upsert punches to Supabase. Returns count of rows sent."""
    if not punches:
        return 0

    if dry_run:
        known = sum(1 for p in punches if p.get("is_known_employee"))
        ghost = len(punches) - known
        roving = sum(1 for p in punches if p.get("is_roving"))
        print(f"  DRY RUN: {len(punches)} records ({known} known, {ghost} ghost, {roving} roving)", flush=True)
        return len(punches)

    total = 0
    for i in range(0, len(punches), UPSERT_BATCH_SIZE):
        batch = punches[i:i + UPSERT_BATCH_SIZE]
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/attendance_punches?on_conflict=pin,event_time,device_sn",
            headers={**_HEADERS, "Prefer": "resolution=merge-duplicates"},
            json=batch,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            print(f"  UPSERT ERROR batch {i}: {r.status_code} {r.text[:300]}", flush=True)
        else:
            total += len(batch)

    return total


# ---------------------------------------------------------------------------
# Fetch Modes
# ---------------------------------------------------------------------------

def _fetch_device_week(ssm_client, device_sn: str, start: date, end: date) -> list[dict]:
    """Fetch punches for one device for a date range."""
    sql = (
        f"SELECT id, pin, event_time, status_code, verify_code, sn "
        f"FROM adms_attlog_raw "
        f"WHERE sn = '{device_sn}' "
        f"AND event_time >= '{start.isoformat()}' "
        f"AND event_time < '{(end + timedelta(days=1)).isoformat()}' "
        f"ORDER BY event_time"
    )
    raw = _run_ssm_query(ssm_client, sql, f"{device_sn} {start}..{end}")
    if not raw:
        return []
    return _parse_ssm_output(raw)


def _fetch_all_devices_range(ssm_client, start: date, end: date, store_filter: str | None = None) -> list[dict]:
    """Fetch punches from all devices for a date range, splitting into weekly chunks."""
    devices = list(DEVICE_TO_STORE.keys())
    if store_filter:
        store_upper = store_filter.upper()
        devices = [d for d, s in DEVICE_TO_STORE.items() if store_upper in s.upper()]
        if not devices:
            print(f"  No devices match store filter '{store_filter}'", flush=True)
            return []

    all_punches = []
    total_devices = len(devices)

    # Split into weekly chunks
    weeks = []
    w_start = start
    while w_start <= end:
        w_end = min(w_start + timedelta(days=6), end)
        weeks.append((w_start, w_end))
        w_start = w_end + timedelta(days=1)

    total_queries = total_devices * len(weeks)
    done = 0

    for w_start, w_end in weeks:
        for idx, device_sn in enumerate(devices):
            done += 1
            if done % 20 == 0 or done == total_queries:
                print(f"  SSM progress: {done}/{total_queries} queries ({len(all_punches)} rows so far)", flush=True)
            rows = _fetch_device_week(ssm_client, device_sn, w_start, w_end)
            all_punches.extend(rows)

    print(f"  Fetched {len(all_punches)} raw punches from {total_devices} devices", flush=True)
    return all_punches


def _fetch_incremental(ssm_client) -> list[dict]:
    """Fetch recent punches (last 2 hours) from all devices."""
    sql = (
        "SELECT id, pin, event_time, status_code, verify_code, sn "
        "FROM adms_attlog_raw "
        "WHERE event_time >= NOW() - INTERVAL '2 hours' "
        "ORDER BY event_time"
    )
    raw = _run_ssm_query(ssm_client, sql, "incremental-2h")
    if not raw:
        return []
    return _parse_ssm_output(raw)


# ---------------------------------------------------------------------------
# Enrich + Transform
# ---------------------------------------------------------------------------

def _transform_punches(raw_punches: list[dict]) -> list[dict]:
    """Enrich raw punches with employee + device data for Supabase upsert."""
    records = []
    for p in raw_punches:
        enrichment = _enrich_punch(p["pin"], p["device_sn"])
        records.append({
            "pin": p["pin"],
            "event_time": p["event_time"],
            "device_sn": p["device_sn"],
            "status_code": p["status_code"],
            "verify_code": p["verify_code"],
            "adms_id": p["adms_id"],
            **enrichment,
        })
    return records


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_backfill(args):
    """Backfill historical data."""
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date) if args.to_date else date.today()
    print(f"BACKFILL: {start} to {end} ({(end - start).days + 1} days)", flush=True)
    if args.store:
        print(f"  Store filter: {args.store}", flush=True)

    _load_employee_lookup()
    ssm = _get_ssm_client()

    raw = _fetch_all_devices_range(ssm, start, end, args.store)
    if not raw:
        print("  No data fetched.", flush=True)
        return

    deduped = _dedup_punches(raw)
    records = _transform_punches(deduped)
    count = _upsert_punches(records, dry_run=args.dry_run)
    print(f"BACKFILL COMPLETE: {count} records upserted", flush=True)


def cmd_incremental(args):
    """Incremental sync (last 2 hours)."""
    print("INCREMENTAL SYNC (last 2 hours)", flush=True)

    _load_employee_lookup()
    ssm = _get_ssm_client()

    raw = _fetch_incremental(ssm)
    if not raw:
        print("  No new punches.", flush=True)
        return

    deduped = _dedup_punches(raw)
    records = _transform_punches(deduped)
    count = _upsert_punches(records, dry_run=args.dry_run)
    print(f"INCREMENTAL COMPLETE: {count} records upserted", flush=True)


def cmd_verify(args):
    """Verify data counts between ADMS source and Supabase."""
    target_date = date.fromisoformat(args.date) if args.date else date.today()
    next_date = target_date + timedelta(days=1)
    print(f"VERIFY: {target_date}", flush=True)

    # Supabase count
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/attendance_punches"
        f"?select=id&event_time=gte.{target_date.isoformat()}T00:00:00"
        f"&event_time=lt.{next_date.isoformat()}T00:00:00",
        headers={**_HEADERS, "Prefer": "count=exact", "Range": "0-0"},
        timeout=30,
    )
    supa_count = r.headers.get("content-range", "?")
    print(f"  Supabase: {supa_count}", flush=True)

    # ADMS source count
    ssm = _get_ssm_client()
    sql = (
        f"SELECT COUNT(*) FROM adms_attlog_raw "
        f"WHERE event_time >= '{target_date.isoformat()}' "
        f"AND event_time < '{next_date.isoformat()}'"
    )
    raw = _run_ssm_query(ssm, sql, f"verify-count-{target_date}")
    adms_count = raw.strip() if raw else "ERROR"
    print(f"  ADMS source: {adms_count}", flush=True)

    # Parse for comparison
    try:
        supa_n = int(supa_count.split("/")[1])
        adms_n = int(adms_count)
        diff = adms_n - supa_n
        pct = (supa_n / adms_n * 100) if adms_n > 0 else 0
        print(f"  Coverage: {pct:.1f}% (diff={diff}, dedup removes ~{diff} near-duplicates)", flush=True)
    except (ValueError, IndexError):
        print("  Could not compare counts.", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ADMS Attendance → Supabase sync")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--incremental", action="store_true", help="Sync last 2 hours")
    group.add_argument("--backfill", action="store_true", help="Backfill date range")
    group.add_argument("--verify", action="store_true", help="Verify counts for a date")

    parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD")
    parser.add_argument("--date", help="Date for --verify YYYY-MM-DD")
    parser.add_argument("--store", help="Filter by store name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would sync")

    args = parser.parse_args()

    if args.backfill and not args.from_date:
        parser.error("--backfill requires --from")

    if args.backfill:
        cmd_backfill(args)
    elif args.incremental:
        cmd_incremental(args)
    elif args.verify:
        cmd_verify(args)


if __name__ == "__main__":
    main()
