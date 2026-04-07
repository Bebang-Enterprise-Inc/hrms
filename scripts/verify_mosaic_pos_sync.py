"""S165 — Mosaic POS Sync Verification

Ground-truth reconciliation of Mosaic POS API vs Supabase pos_orders.

For every store-day in the window (default: last 7 days ending at yesterday PHT):
  1. Call Mosaic with page[size]=1 to get meta.total
  2. Run SELECT COUNT(*) FROM pos_orders via PostgREST count=exact header
  3. If mismatch and --no-heal not set, call sync_store_day() to re-sync
  4. Re-verify; mark row in sync_verification table
  5. Send ONE consolidated Chat alert listing unresolved discrepancies

Rate-limit: 1 thread per credential group (12 concurrent), ~1.2s per call
  => 45 stores x 7 days / 12 groups ~= 34s per group, ~60s total

Env vars (MUST be set):
  SUPABASE_SERVICE_ROLE_KEY   Supabase service role key
  SUPABASE_MGMT_TOKEN         Supabase Management API token (for sync_store_day)
  SENTRY_DSN                  Sentry DSN for bei-hrms project (fail-fast if missing)

Exit codes:
  0  success (even if discrepancies found -- Chat alert handles those)
  2  SENTRY_DSN missing (CB5 fail-fast)
  3  all credential groups failed
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import requests
import sentry_sdk

# ---------------------------------------------------------------------------
# CB3 — module-alias import + global propagation
#
# HARD BLOCKER: must use `import ... as` form so the verify script can mutate
# globals on the imported module. `from sync_pos_to_supabase import sync_store_day`
# binds the function name but does NOT propagate later SUPABASE_KEY writes.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_pos_to_supabase as sps  # noqa: E402
from sync_pos_to_supabase import (  # noqa: E402
    load_credentials,
    ensure_token,
    sync_store_day,
    set_sync_progress,
    fetch_orders_page,           # reused for retry/rate-limit pattern (MW2)
    MOSAIC_ORDERS_URL,           # MW4 — explicit import
    REQUEST_INTERVAL,
    MAX_RETRIES,
    RATE_LIMIT_WAIT,
    RETRY_WAIT,
    CREDENTIALS_CSV,
    SUPABASE_URL,
)

# CB3: Propagate secrets to imported module BEFORE calling any function that
# touches Supabase. Empty globals produce 401 on every heal.
# Use Doppler fallback if env vars are not set (local dev convenience).
def _resolve_secret(env_name: str) -> str:
    val = os.environ.get(env_name, "").strip()
    if val:
        return val
    try:
        import subprocess
        result = subprocess.run(
            ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


sps.SUPABASE_KEY = _resolve_secret("SUPABASE_SERVICE_ROLE_KEY")
sps.SUPABASE_MGMT_TOKEN = _resolve_secret("SUPABASE_MGMT_TOKEN")

# ---------------------------------------------------------------------------
# MW1 — reinstall own SIGINT handler (sync_pos_to_supabase.py:102 already
# registered one at import time; we need our own to exit the verify loop).
# ---------------------------------------------------------------------------
_shutdown = False


def _handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("Shutdown requested -- finishing current store-day then exiting.", flush=True)


signal.signal(signal.SIGINT, _handle_sigint)

# ---------------------------------------------------------------------------
# CB5 — Sentry fail-fast
# ---------------------------------------------------------------------------
_sentry_dsn = _resolve_secret("SENTRY_DSN")
if not _sentry_dsn:
    print(
        "ERROR: SENTRY_DSN is missing/empty -- refusing to run observability sprint without observability.",
        file=sys.stderr,
    )
    sys.exit(2)  # CB5: observability sprint cannot silently disable observability

sentry_sdk.init(
    dsn=_sentry_dsn,
    environment="production",
    release="s165-mosaic-sync-verification",
    traces_sample_rate=0.0,
    server_name="verify_mosaic_pos_sync",
)
sentry_sdk.set_tag("module", "sync_verification")
sentry_sdk.set_tag("action", "verify_mosaic_pos_sync")

PHT = timezone(timedelta(hours=8))
CHAT_SPACE_ANOMALY = "spaces/AAQABiNmpBg"  # ! Blip Notifications (sam@bebang.ph private). Per Sam directive 2026-04-07: NO Blip notifications anywhere else.


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="S165 Mosaic Sync Verification")
    p.add_argument("--date", help="Single YYYY-MM-DD date (overrides --days)")
    p.add_argument("--days", type=int, default=7,
                   help="Verify last N days ending at yesterday PHT (default: 7)")
    p.add_argument("--store", type=int, help="Single location_id for debug")
    p.add_argument("--no-heal", action="store_true",
                   help="Detect only; do not auto re-sync")
    p.add_argument("--no-chat", action="store_true", help="Skip Chat alert")
    p.add_argument("--dry-run", action="store_true",
                   help="Print but do not write to sync_verification")
    return p.parse_args()


def compute_window(args) -> list[str]:
    """Return list of YYYY-MM-DD strings to verify.

    HW4: Window ENDS at yesterday PHT (not today). A midnight run must not
    verify the day that just started.
    """
    if args.date:
        return [args.date]  # explicit single date override
    end_date = datetime.now(PHT).date() - timedelta(days=1)  # HW4: yesterday
    start_date = end_date - timedelta(days=args.days - 1)
    return [(start_date + timedelta(days=i)).isoformat() for i in range(args.days)]


# ---------------------------------------------------------------------------
# Mosaic count-only fetch (MW2 — reuses retry/429/5xx semantics)
# ---------------------------------------------------------------------------

def _fetch_page_size_1(client: httpx.Client, token: str,
                      location_id: int, business_date: str) -> dict:
    """Count-only fetch using fetch_orders_page's retry semantics with size=1.

    httpx bracket-encoding of filter[location_id] is known-working -- see
    sync_pos_to_supabase.py:315 for the existing production call pattern. (MW10)
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "filter[business_date]": business_date,
        "filter[location_id]": location_id,
        "page[number]": 1,
        "page[size]": 1,  # count-only, no data rows needed
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(MOSAIC_ORDERS_URL, headers=headers,
                           params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(RATE_LIMIT_WAIT)
                continue
            if r.status_code >= 500:
                time.sleep(RETRY_WAIT)
                continue
            raise RuntimeError(f"Mosaic API error {r.status_code}: {r.text[:200]}")
        except httpx.RequestError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            raise
    raise RuntimeError("Max retries exceeded fetching count")


def fetch_mosaic_count(client: httpx.Client, cred: dict,
                       location_id: int, business_date: str) -> int:
    """Return Mosaic's meta.total for a store-day.

    Reuses the full retry/429/5xx pattern from sync_pos_to_supabase.fetch_orders_page
    (line 310-351). See MW2.
    """
    token = ensure_token(client, cred)
    data = _fetch_page_size_1(client, token, location_id, business_date)
    return int(data.get("meta", {}).get("total", 0))


# ---------------------------------------------------------------------------
# Supabase count via PostgREST count=exact (HW1 — MW5 inlined)
# ---------------------------------------------------------------------------

def supabase_count(location_id: int, business_date: str) -> int:
    """SELECT COUNT(*) FROM pos_orders via PostgREST count=exact header.

    Cheaper than Management SQL; no rate limit concern.
    """
    headers = {
        "apikey": sps.SUPABASE_KEY,
        "Authorization": f"Bearer {sps.SUPABASE_KEY}",
        "Prefer": "count=exact",
        "Range-Unit": "items",
        "Range": "0-0",  # 0 rows, only the content-range count header
    }
    params = {
        "location_id": f"eq.{location_id}",
        "business_date": f"eq.{business_date}",
        "cancelled_at": "is.null",
        "select": "id",
    }
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pos_orders",
        headers=headers, params=params, timeout=15,
    )
    # PostgREST returns 206 Partial Content for Range-restricted requests
    if r.status_code not in (200, 206):
        r.raise_for_status()
    # Content-Range header format: "0-0/NNN" or "*/NNN"
    content_range = r.headers.get("content-range", "*/0")
    return int(content_range.split("/")[-1])


# ---------------------------------------------------------------------------
# S169 Phase 6 — Tombstone reconciliation helpers
# ---------------------------------------------------------------------------

SUPABASE_PROJECT_REF = "csnniykjrychgajfrgua"
SUPABASE_MGMT_QUERY_URL = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"


def supabase_ids(client: httpx.Client, location_id: int, business_date: str) -> set[int]:
    """Paginated GET pos_orders.id (cancelled_at IS NULL) via PostgREST."""
    headers = {
        "apikey": sps.SUPABASE_KEY,
        "Authorization": f"Bearer {sps.SUPABASE_KEY}",
        "Accept": "application/json",
    }
    out: set[int] = set()
    page_size = 1000
    offset = 0
    while True:
        params = {
            "location_id": f"eq.{location_id}",
            "business_date": f"eq.{business_date}",
            "cancelled_at": "is.null",
            "select": "id",
            "order": "id.asc",
            "limit": str(page_size),
            "offset": str(offset),
        }
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/pos_orders",
            headers=headers, params=params, timeout=30,
        )
        if r.status_code not in (200, 206):
            r.raise_for_status()
        rows = r.json() or []
        for row in rows:
            try:
                out.add(int(row["id"]))
            except (KeyError, TypeError, ValueError):
                continue
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def mosaic_ids(client: httpx.Client, cred: dict,
               location_id: int, business_date: str) -> set[int]:
    """Paginated fetch of all Mosaic order IDs for a store-day."""
    token = ensure_token(client, cred)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    out: set[int] = set()
    page_number = 1
    page_size = 200
    while True:
        params = {
            "filter[business_date]": business_date,
            "filter[location_id]": location_id,
            "page[number]": page_number,
            "page[size]": page_size,
        }
        last_exc: Exception | None = None
        data = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = client.get(MOSAIC_ORDERS_URL, headers=headers,
                               params=params, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    break
                if r.status_code == 429:
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                if r.status_code >= 500:
                    time.sleep(RETRY_WAIT)
                    continue
                raise RuntimeError(f"Mosaic API error {r.status_code}: {r.text[:200]}")
            except httpx.RequestError as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT)
                    continue
                raise
        if data is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("mosaic_ids: max retries exceeded")
        rows = data.get("data") or []
        for row in rows:
            try:
                out.add(int(row.get("id")))
            except (TypeError, ValueError):
                continue
        if len(rows) < page_size:
            break
        page_number += 1
        time.sleep(REQUEST_INTERVAL)
    return out


def _supabase_query_sql(sql: str, params: tuple = ()) -> dict:
    """Execute SQL via Supabase Management API. Naive %s substitution."""
    token = _resolve_secret("SUPABASE_MGMT_TOKEN")
    if not token:
        raise RuntimeError("SUPABASE_MGMT_TOKEN missing — cannot run management SQL")

    def _quote(v):
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, (list, tuple)):
            inner = ",".join(_quote(x) for x in v)
            return f"ARRAY[{inner}]"
        s = str(v).replace("'", "''")
        return f"'{s}'"

    rendered = sql
    for p in params:
        rendered = rendered.replace("%s", _quote(p), 1)

    r = requests.post(
        SUPABASE_MGMT_QUERY_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": rendered},
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Supabase mgmt query failed ({r.status_code}): {r.text[:300]}")
    try:
        return r.json()
    except Exception:
        return {}


def tombstone_extras(
    client: httpx.Client,
    cred: dict,
    loc_id: int,
    ds: str,
    supabase_ids_set: set[int],
    mosaic_ids_set: set[int],
    dry_run: bool = False,
) -> tuple[list[int], list[tuple[int, str]]]:
    """Confirm extras gone from Mosaic, then tombstone in Supabase.

    Returns (confirmed_ids, unconfirmed_with_reasons).
    """
    extras = sorted(supabase_ids_set - mosaic_ids_set)
    confirmed: list[int] = []
    unconfirmed: list[tuple[int, str]] = []

    if not extras:
        return confirmed, unconfirmed

    token = ensure_token(client, cred)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    for order_id in extras:
        url = f"{MOSAIC_ORDERS_URL}/{order_id}"
        status_code: int | None = None
        last_err: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = client.get(url, headers=headers, timeout=30)
                status_code = r.status_code
                if r.status_code == 429:
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                if r.status_code >= 500:
                    time.sleep(RETRY_WAIT)
                    continue
                break
            except httpx.RequestError as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT)
                    continue
                status_code = None
                break
        time.sleep(REQUEST_INTERVAL)

        if status_code == 404:
            confirmed.append(order_id)
        elif status_code == 200:
            unconfirmed.append((order_id, "still_present"))
        else:
            reason = f"lookup_failed:{status_code or 'request_error'}"
            if last_err and status_code is None:
                reason = "lookup_failed:request_error"
            unconfirmed.append((order_id, reason))

    if not confirmed:
        return confirmed, unconfirmed

    if dry_run:
        print(
            f"  [TOMBSTONE_DRYRUN] loc={loc_id} {ds}: would tombstone "
            f"{len(confirmed)} extras (ids sample={confirmed[:5]})"
        )
        return confirmed, unconfirmed

    sql = (
        "UPDATE pos_orders SET cancelled_at=NOW(), "
        "cancellation_reason='reconciled_from_mosaic_gap', "
        "order_status='CANCELLED' "
        "WHERE id = ANY(%s::int[]) AND cancelled_at IS NULL"
    )
    try:
        _supabase_query_sql(sql, (confirmed,))
        print(
            f"  [TOMBSTONE_OK] loc={loc_id} {ds}: tombstoned {len(confirmed)} extras"
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(
            f"  [TOMBSTONE_ERROR] loc={loc_id} {ds}: {e}",
            file=sys.stderr,
        )
        raise

    return confirmed, unconfirmed


# ---------------------------------------------------------------------------
# sync_verification upsert
# ---------------------------------------------------------------------------

def upsert_verification_rows(rows: list[dict]) -> None:
    """POST rows to sync_verification via PostgREST."""
    if not rows:
        return
    headers = {
        "apikey": sps.SUPABASE_KEY,
        "Authorization": f"Bearer {sps.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    # Stamp verified_at so primary key (loc_id, biz_date, verified_at) is unique per run
    stamp = datetime.now(timezone.utc).isoformat()
    payload = []
    for row in rows:
        p = {
            "location_id": row["location_id"],
            "business_date": row["business_date"],
            "mosaic_total": row.get("mosaic_total"),
            "supabase_total": row.get("supabase_total"),
            "status": row["status"],
            "verified_at": row.get("verified_at") or stamp,
            "heal_attempted": row.get("heal_attempted", False),
            "error_message": row.get("error_message"),
        }
        payload.append(p)
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/sync_verification",
        headers=headers, json=payload, timeout=30,
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"sync_verification upsert failed ({r.status_code}): {r.text[:200]}")


# ---------------------------------------------------------------------------
# Google Chat alerts (MW6 — inlined)
# ---------------------------------------------------------------------------

def _build_chat_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = Path(__file__).resolve().parents[1] / "credentials" / "task-manager-service.json"
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/chat.bot"],
    )
    return build("chat", "v1", credentials=creds, cache_discovery=False)


def send_chat_alert(unresolved: list[tuple], total_verified: int) -> None:
    """Post consolidated discrepancy list to the anomaly Chat space."""
    chat = _build_chat_service()
    lines = [
        f"🔴 Sync Verification — {datetime.now(PHT).strftime('%Y-%m-%d %H:%M')} PHT",
        f"Verified: {total_verified} store-days",
        f"Unresolved: {len(unresolved)}",
        "",
        "DISCREPANCIES:",
    ]
    for store_name, ds, row in unresolved[:30]:
        m = row.get("mosaic_total")
        s = row.get("supabase_total")
        status = row["status"]
        if status == "api_error":
            err = (row.get("error_message") or "")[:80]
            lines.append(f"  {store_name} {ds}: API ERROR — {err}")
        else:
            lines.append(f"  {store_name} {ds}: Mosaic={m}, Supabase={s}, status={status}")
    if len(unresolved) > 30:
        lines.append(f"  ... and {len(unresolved) - 30} more")

    chat.spaces().messages().create(
        parent=CHAT_SPACE_ANOMALY,
        body={"text": "\n".join(lines)},
    ).execute()


def send_chat_summary(total_verified: int, window: list[str]) -> None:
    """Post green summary when all OK."""
    chat = _build_chat_service()
    chat.spaces().messages().create(
        parent=CHAT_SPACE_ANOMALY,
        body={"text": f"✅ Sync verification: all {total_verified} store-days OK (window {window[0]} → {window[-1]})"},
    ).execute()


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

def _process_group(cred: dict, dates: list[str], args) -> tuple[list[dict], list[tuple]]:
    """Worker: one thread per credential group. Owns its own httpx.Client."""
    results: list[dict] = []
    unresolved: list[tuple] = []

    client = httpx.Client(timeout=30)
    try:
        locations = cred["locations"]
        if args.store:
            locations = [loc for loc in locations if loc["location_id"] == args.store]
            if not locations:
                return results, unresolved

        for loc in locations:
            loc_id = loc["location_id"]
            store_name = loc["store_name"]
            for ds in dates:
                if _shutdown:
                    break
                row: dict = {
                    "location_id": loc_id,
                    "business_date": ds,
                    "heal_attempted": False,
                }
                try:
                    mosaic_total = fetch_mosaic_count(client, cred, loc_id, ds)
                    time.sleep(REQUEST_INTERVAL)  # MW2: per-request rate limit
                    sb_total = supabase_count(loc_id, ds)
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    row.update(
                        status="api_error",
                        mosaic_total=None,
                        supabase_total=None,
                        error_message=str(e)[:500],
                    )
                    results.append(row)
                    unresolved.append((store_name, ds, row))
                    continue

                row.update(mosaic_total=mosaic_total, supabase_total=sb_total)

                line = f"{store_name} ({loc_id}) {ds}: Mosaic={mosaic_total}, Supabase={sb_total}"

                if mosaic_total == sb_total:
                    row["status"] = "ok"
                    print(f"  [OK] {line}")
                elif mosaic_total > sb_total:
                    if args.no_heal:
                        row["status"] = "missing"
                        unresolved.append((store_name, ds, row))
                        print(f"  [MISSING] {line}, delta={mosaic_total - sb_total} (no-heal mode)")
                    else:
                        print(f"  [MISSING] {line}, healing...")
                        # HW2: set pending marker BEFORE heal (audit trail only;
                        # sync_store_day does not consult sync_progress).
                        try:
                            set_sync_progress(client, loc_id, ds, "pending")
                        except Exception as e:
                            sentry_sdk.capture_exception(e)
                            # non-fatal: pending marker is cosmetic
                        try:
                            sync_store_day(client, cred, loc_id, store_name, ds)
                            row["heal_attempted"] = True
                            new_sb = supabase_count(loc_id, ds)
                            row["supabase_total"] = new_sb
                            if new_sb == mosaic_total:
                                row["status"] = "healed"
                                print(f"  [HEALED] {line} -> {new_sb}")
                            else:
                                row["status"] = "unresolved"
                                unresolved.append((store_name, ds, row))
                                print(f"  [UNRESOLVED] {line} -> still {new_sb}")
                        except Exception as e:
                            sentry_sdk.capture_exception(e)
                            row["status"] = "unresolved"
                            row["heal_attempted"] = True
                            row["error_message"] = str(e)[:500]
                            unresolved.append((store_name, ds, row))
                            print(f"  [HEAL_ERROR] {line} -> {e}")
                else:  # mosaic_total < sb_total — S169 Phase 6 tombstone path
                    print(f"  [EXTRA] {line}, delta={sb_total - mosaic_total}, reconciling...")
                    try:
                        sb_id_set = supabase_ids(client, loc_id, ds)
                        mo_id_set = mosaic_ids(client, cred, loc_id, ds)
                        confirmed, unconfirmed_pairs = tombstone_extras(
                            client, cred, loc_id, ds,
                            sb_id_set, mo_id_set,
                            dry_run=args.dry_run,
                        )
                        row["heal_attempted"] = True
                        if unconfirmed_pairs or not confirmed:
                            row["status"] = "unresolved"
                            row["error_message"] = (
                                f"extras unconfirmed: {len(unconfirmed_pairs)}; "
                                f"sample={unconfirmed_pairs[:5]}"
                            )[:500]
                            unresolved.append((store_name, ds, row))
                            print(
                                f"  [UNRESOLVED] {line}: {len(confirmed)} tombstoned, "
                                f"{len(unconfirmed_pairs)} unconfirmed"
                            )
                        else:
                            new_sb = supabase_count(loc_id, ds)
                            row["supabase_total"] = new_sb
                            if new_sb == mosaic_total:
                                row["status"] = "extras_tombstoned"
                                print(
                                    f"  [EXTRAS_TOMBSTONED] {line} -> {new_sb} "
                                    f"({len(confirmed)} reconciled)"
                                )
                            else:
                                row["status"] = "unresolved"
                                row["error_message"] = (
                                    f"recount mismatch after tombstone: "
                                    f"sb={new_sb}, mosaic={mosaic_total}"
                                )[:500]
                                unresolved.append((store_name, ds, row))
                                print(
                                    f"  [UNRESOLVED] {line} -> recount {new_sb} "
                                    f"!= mosaic {mosaic_total}"
                                )
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                        row["status"] = "unresolved"
                        row["heal_attempted"] = True
                        row["error_message"] = str(e)[:500]
                        unresolved.append((store_name, ds, row))
                        print(f"  [TOMBSTONE_FAIL] {line} -> {e}", file=sys.stderr)

                results.append(row)
    finally:
        client.close()
    return results, unresolved


def main() -> int:
    args = parse_args()
    creds = load_credentials(CREDENTIALS_CSV)
    dates = compute_window(args)

    print(f"S165 verify: window = {dates[0]} -> {dates[-1]} ({len(dates)} days)", flush=True)
    print(f"S165 verify: {len(creds)} credential groups, dry_run={args.dry_run}, no_heal={args.no_heal}, no_chat={args.no_chat}", flush=True)

    all_results: list[dict] = []
    all_unresolved: list[tuple] = []
    group_failures = 0

    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_process_group, cred, dates, args): cred for cred in creds}
        for fut in as_completed(futures):
            cred = futures[fut]
            try:
                results, unresolved = fut.result()
                all_results.extend(results)
                all_unresolved.extend(unresolved)
            except Exception as e:
                group_failures += 1
                sentry_sdk.capture_exception(e)
                print(f"Credential group {cred.get('group_name')} failed: {e}", file=sys.stderr)

    print(f"\nVerified {len(all_results)} store-days; {len(all_unresolved)} unresolved", flush=True)

    # Upsert to sync_verification
    if not args.dry_run:
        try:
            upsert_verification_rows(all_results)
            print(f"Wrote {len(all_results)} rows to sync_verification")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"sync_verification upsert failed: {e}", file=sys.stderr)

    # Send ONE consolidated Chat alert
    if not args.no_chat and not args.dry_run:
        try:
            if all_unresolved:
                send_chat_alert(all_unresolved, total_verified=len(all_results))
                print("Chat alert sent (discrepancies)")
            else:
                send_chat_summary(total_verified=len(all_results), window=dates)
                print("Chat summary sent (all OK)")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Chat send failed: {e}", file=sys.stderr)

    # MW9: Exit semantics -- exit 0 unless infra failure.
    # Unresolved discrepancies are expected output handled by Chat, NOT a failure.
    if group_failures == len(creds):
        return 3  # all groups failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
