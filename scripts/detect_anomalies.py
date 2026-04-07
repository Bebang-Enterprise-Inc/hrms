#!/usr/bin/env python3
"""POS Data Anomaly Detection with Google Chat Alerting.

Compares daily POS order counts against store baselines and alerts
the BEI notification space when anomalies are detected.

Usage:
    python scripts/detect_anomalies.py                    # Yesterday, full run
    python scripts/detect_anomalies.py --date 2026-02-13  # Specific date
    python scripts/detect_anomalies.py --dry-run           # Print alert, don't send
    python scripts/detect_anomalies.py --no-chat           # Log to DB, skip Chat
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Try to import the Frappe-side chat lockdown helper. In CI (where the `hrms`
# package is not on PYTHONPATH) the import fails and we fall back to a no-op
# router that always returns the hardcoded BLIP_NOTIFICATION_SPACE below.
# Per Sam directive 2026-04-07: NO Blip notifications anywhere except
# "! Blip Notifications" (spaces/AAQABiNmpBg).
try:
    from hrms.utils.chat_space_lockdown import route_outbound_chat_space  # type: ignore
except ImportError:  # CI / standalone runtime
    def route_outbound_chat_space(requested_space, *, logger=None, context=None, family=None):
        return "spaces/AAQABiNmpBg"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("anomaly-detect")

# --- Configuration ---
SUPABASE_URL = "https://csnniykjrychgajfrgua.supabase.co"
CHAT_SPACE = "spaces/AAQABiNmpBg"  # ! Blip Notifications. Per Sam directive 2026-04-07: NO Blip notifications anywhere else.
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "credentials" / "task-manager-service.json"
DOPPLER_BIN = r"C:\Users\Sam\bin\doppler.exe"

# Anomaly thresholds
MIN_WEEKS_FOR_BASELINE = 4
CUTOFF_EARLY_HOUR = 18  # Before 6 PM = LIKELY_CUTOFF
CUTOFF_LATE_HOUR = 20   # 6-8 PM = POSSIBLE_CUTOFF
MARKET_EVENT_THRESHOLD = 10
REGIONAL_ISSUE_THRESHOLD = 4

PHT = timezone(timedelta(hours=8))


def get_supabase_key() -> str:
    """Fetch Supabase service role key from Doppler."""
    try:
        result = subprocess.run(
            [DOPPLER_BIN, "secrets", "get", "SUPABASE_SERVICE_ROLE_KEY",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, check=True, timeout=15,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Fallback to environment variable
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not key:
            log.error("Cannot get SUPABASE_SERVICE_ROLE_KEY from Doppler or env: %s", e)
            sys.exit(1)
        return key


def supabase_get(key: str, table: str, params: dict | None = None) -> list[dict]:
    """GET from Supabase REST API."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def supabase_upsert(key: str, table: str, rows: list[dict], on_conflict: str) -> list[dict]:
    """UPSERT rows into Supabase REST API."""
    if not rows:
        return []
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}",
        headers=headers, json=rows, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def supabase_patch(key: str, table: str, filters: str, data: dict) -> list[dict]:
    """PATCH rows in Supabase REST API with filter query string."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?{filters}",
        headers=headers, json=data, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_baselines(key: str, day_of_week: int) -> dict:
    """Fetch store baselines for the given day of week.
    Returns dict keyed by location_id.
    """
    rows = supabase_get(key, "store_daily_baselines", {
        "day_of_week": f"eq.{day_of_week}",
    })
    return {r["location_id"]: r for r in rows}


def fetch_chain_median(key: str, day_of_week: int) -> float:
    """Calculate chain-wide median for new store fallback."""
    rows = supabase_get(key, "store_daily_baselines", {
        "day_of_week": f"eq.{day_of_week}",
        "select": "median_orders",
    })
    if not rows:
        return 100.0  # safe fallback
    medians = sorted(r["median_orders"] for r in rows)
    n = len(medians)
    if n % 2 == 0:
        return (medians[n // 2 - 1] + medians[n // 2]) / 2
    return medians[n // 2]


def fetch_active_stores(key: str) -> dict:
    """Fetch all active stores. Returns dict keyed by location_id."""
    rows = supabase_get(key, "stores", {
        "is_active": "eq.true",
        "select": "location_id,store_name",
    })
    return {r["location_id"]: r["store_name"] for r in rows}


def fetch_daily_actuals(key: str, business_date: str) -> dict:
    """Fetch order count and last billed_at per store for the date.

    Uses Supabase RPC or aggregation. Since REST API doesn't support
    GROUP BY, we fetch all orders for the date and aggregate in Python.
    We only need location_id and billed_at — select minimal columns.
    """
    # Paginate through all orders for the date (could be 5K-10K rows)
    all_orders = []
    offset = 0
    page_size = 5000
    while True:
        rows = supabase_get(key, "pos_orders", {
            "business_date": f"eq.{business_date}",
            "payment_status": "eq.PAID",
            "select": "location_id,billed_at",
            "order": "location_id",
            "limit": str(page_size),
            "offset": str(offset),
        })
        all_orders.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    # Aggregate: count and max billed_at per location_id
    actuals = {}
    for row in all_orders:
        loc = row["location_id"]
        billed = row["billed_at"]
        if loc not in actuals:
            actuals[loc] = {"count": 0, "last_billed_at": billed}
        actuals[loc]["count"] += 1
        if billed and billed > actuals[loc]["last_billed_at"]:
            actuals[loc]["last_billed_at"] = billed

    return actuals


def fetch_unresolved_anomalies(key: str) -> list[dict]:
    """Fetch previously logged anomalies that are still unresolved."""
    return supabase_get(key, "sync_anomalies", {
        "resolved": "eq.false",
        "select": "id,location_id,business_date,anomaly_type,order_count",
    })


def classify_anomaly(
    actual_count: int,
    baseline: dict | None,
    chain_median: float,
    last_billed_at: str | None,
) -> dict | None:
    """Apply Layer 1 + Layer 2 anomaly detection.

    Returns anomaly dict or None if normal.
    """
    # Determine effective baseline
    if baseline and baseline.get("weeks_of_data", 0) >= MIN_WEEKS_FOR_BASELINE:
        p10 = float(baseline["p10_orders"])
        median = float(baseline["median_orders"])
    else:
        # New store fallback: use chain-wide median
        p10 = chain_median * 0.4  # approximate P10 as 40% of chain median
        median = chain_median

    # Layer 1: Statistical check
    if actual_count >= p10:
        return None  # Normal

    # Layer 2: Last order timestamp analysis
    if actual_count == 0:
        anomaly_type = "OFFLINE_ALL_DAY"
        diagnosis = "No orders received"
        last_order_time = None
    elif last_billed_at:
        # Parse the timestamp (ISO format with timezone)
        try:
            last_dt = datetime.fromisoformat(last_billed_at)
            # Convert to PHT for business logic
            last_pht = last_dt.astimezone(PHT)
            last_hour = last_pht.hour
            last_order_time = last_pht.strftime("%H:%M")
        except (ValueError, TypeError):
            last_hour = 23
            last_order_time = "unknown"

        if last_hour < CUTOFF_EARLY_HOUR:
            anomaly_type = "LIKELY_CUTOFF"
            diagnosis = f"Last order at {last_order_time} (before 18:00)"
        elif last_hour < CUTOFF_LATE_HOUR:
            anomaly_type = "POSSIBLE_CUTOFF"
            diagnosis = f"Last order at {last_order_time} (18:00-20:00 window)"
        else:
            anomaly_type = "LOW_VOLUME"
            diagnosis = f"Last order at {last_order_time} (after 20:00, genuine slow day?)"
    else:
        anomaly_type = "LOW_VOLUME"
        diagnosis = "Below P10, no timestamp available"
        last_order_time = None

    pct_of_median = int((actual_count / median * 100)) if median > 0 else 0

    return {
        "anomaly_type": anomaly_type,
        "order_count": actual_count,
        "median_orders": round(median, 1),
        "pct_of_median": pct_of_median,
        "last_order_time": last_order_time,
        "diagnosis": diagnosis,
    }


def classify_cross_store(anomalies: list[dict]) -> str:
    """Layer 3: Cross-store correlation."""
    count = len(anomalies)
    if count >= MARKET_EVENT_THRESHOLD:
        return "MARKET_EVENT"
    elif count >= REGIONAL_ISSUE_THRESHOLD:
        return "REGIONAL_ISSUE"
    else:
        return "INDIVIDUAL_SYNC_ISSUE"


def self_heal(key: str, actuals: dict, business_date: str) -> list[dict]:
    """Check if previously anomalous stores now have normal data.
    Returns list of resolved anomaly records.
    """
    unresolved = fetch_unresolved_anomalies(key)
    resolved = []

    for anomaly in unresolved:
        loc = anomaly["location_id"]
        old_count = anomaly.get("order_count", 0) or 0
        current = actuals.get(loc, {})
        current_count = current.get("count", 0)

        # If current count is significantly more than what was recorded, mark resolved
        if current_count > old_count and current_count > 0:
            now_str = datetime.now(timezone.utc).isoformat()
            supabase_patch(
                key, "sync_anomalies",
                f"id=eq.{anomaly['id']}",
                {"resolved": True, "resolved_at": now_str},
            )
            resolved.append({
                "location_id": loc,
                "business_date": anomaly["business_date"],
                "old_count": old_count,
                "new_count": current_count,
            })
            log.info("Self-healed anomaly id=%s loc=%s: %d -> %d orders",
                     anomaly["id"], loc, old_count, current_count)

    return resolved


def build_alert_message(
    date_str: str,
    anomalies: list[dict],
    cross_store: str,
    resolved: list[dict],
    store_names: dict,
) -> str:
    """Build the Google Chat alert message."""
    date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")

    if not anomalies and not resolved:
        return f"POS Data Health Check -- {date_display}: All {len(store_names)} stores reporting normally."

    lines = [f"POS Data Anomaly Report -- {date_display}", ""]

    # Group anomalies by severity
    critical = [a for a in anomalies if a["anomaly_type"] in ("OFFLINE_ALL_DAY", "LIKELY_CUTOFF")]
    monitoring = [a for a in anomalies if a["anomaly_type"] in ("POSSIBLE_CUTOFF", "LOW_VOLUME")]

    if critical:
        lines.append("LIKELY INCOMPLETE (IT action needed):")
        for a in critical:
            name = store_names.get(a["location_id"], f"Store {a['location_id']}")
            if a["anomaly_type"] == "OFFLINE_ALL_DAY":
                lines.append(f"  {name} -- 0 orders (median: {a['median_orders']}), no data received")
            else:
                lines.append(f"  {name} -- {a['order_count']} orders (median: {a['median_orders']}), last order {a['last_order_time']}")
        lines.append("")

    if monitoring:
        lines.append("MONITORING (no action yet):")
        for a in monitoring:
            name = store_names.get(a["location_id"], f"Store {a['location_id']}")
            time_str = a.get("last_order_time", "N/A")
            lines.append(f"  {name} -- {a['order_count']} orders (median: {a['median_orders']}), last order {time_str}")
        lines.append("")

    # Cross-store classification
    if cross_store == "MARKET_EVENT":
        lines.append(f"MARKET EVENT: {len(anomalies)} stores affected -- possible holiday/system-wide issue")
    elif cross_store == "REGIONAL_ISSUE":
        lines.append(f"REGIONAL ISSUE: {len(anomalies)} stores affected -- possible area-level outage")
    else:
        lines.append("MARKET EVENT: None detected")
    lines.append("")

    if resolved:
        lines.append("RESOLVED since last check:")
        for r in resolved:
            name = store_names.get(r["location_id"], f"Store {r['location_id']}")
            lines.append(f"  {name} -- data recovered ({r['new_count']} orders now)")
        lines.append("")

    return "\n".join(lines)


def send_google_chat(message: str) -> bool:
    """Send alert to Google Chat space using bot credentials."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        log.error("google-auth / google-api-python-client not installed. Run: pip install google-auth google-api-python-client")
        return False

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_PATH),
            scopes=["https://www.googleapis.com/auth/chat.bot"],
        )
        chat = build("chat", "v1", credentials=creds)
        result = chat.spaces().messages().create(
            parent=route_outbound_chat_space(
                CHAT_SPACE,
                logger=log,
                context="scripts.detect_anomalies.send_google_chat",
            ),
            body={"text": message},
        ).execute()
        log.info("Chat message sent: %s", result.get("name", "unknown"))
        return True
    except Exception as e:
        log.error("Failed to send Google Chat message: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(description="POS Data Anomaly Detection")
    parser.add_argument("--date", type=str, default=None,
                        help="Business date to check (YYYY-MM-DD). Default: yesterday.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print alert but don't send to Chat or write to DB")
    parser.add_argument("--no-chat", action="store_true",
                        help="Write to DB but skip Chat alert")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only re-check previously logged anomalies. "
                             "Resolves recovered stores, alerts only on persistent failures.")
    args = parser.parse_args()

    # Determine target date
    if args.date:
        target_date = args.date
    else:
        yesterday = datetime.now(PHT) - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    # Python: Monday=0, Sunday=6. PostgreSQL EXTRACT(DOW): Sunday=0, Monday=1, ..., Saturday=6
    py_dow = target_dt.weekday()  # Monday=0
    pg_dow = (py_dow + 1) % 7     # Convert to PostgreSQL DOW (Sunday=0)

    log.info("Anomaly detection for %s (DOW=%d)%s", target_date, pg_dow,
             " [VERIFY-ONLY]" if args.verify_only else "")

    # Fetch Supabase key
    key = get_supabase_key()

    store_names = fetch_active_stores(key)
    log.info("Active stores: %d", len(store_names))

    log.info("Fetching actual orders for %s...", target_date)
    actuals = fetch_daily_actuals(key, target_date)
    log.info("Got actuals for %d stores", len(actuals))

    if args.verify_only:
        # ── VERIFY-ONLY MODE ──────────────────────────────────────────
        # Only re-check previously logged anomalies. Resolve recovered
        # stores, alert only on persistent failures. No fresh detection.
        log.info("Verify-only: checking previously logged anomalies...")
        resolved = self_heal(key, actuals, target_date) if not args.dry_run else []
        log.info("Resolved %d previously anomalous stores", len(resolved))

        # Fetch what's STILL unresolved after self-healing
        still_unresolved = [
            a for a in fetch_unresolved_anomalies(key)
            if a.get("business_date") == target_date
        ]
        log.info("Still unresolved: %d stores", len(still_unresolved))

        if not still_unresolved:
            # Everything recovered — send all-clear or nothing
            if resolved:
                alert_msg = (
                    f"POS Data Recovery -- {datetime.strptime(target_date, '%Y-%m-%d').strftime('%b %d, %Y')}\n\n"
                    f"All {len(resolved)} previously flagged stores have recovered.\n"
                    "No action needed."
                )
                log.info("All anomalies resolved, sending recovery notice")
            else:
                alert_msg = None
                log.info("No anomalies to verify, nothing to send")
        else:
            # Some stores still broken — build a focused alert
            lines = [
                f"POS Data Anomaly Report -- {datetime.strptime(target_date, '%Y-%m-%d').strftime('%b %d, %Y')}",
                f"(Verified at 9 AM, {len(still_unresolved)} stores still missing data)",
                "",
                "PERSISTENT ISSUES (IT action needed):",
            ]
            for a in still_unresolved:
                name = store_names.get(a["location_id"], f"Store {a['location_id']}")
                lines.append(f"  {name} -- {a.get('order_count', 0)} orders (type: {a['anomaly_type']})")
            lines.append("")

            if resolved:
                lines.append(f"RECOVERED since midnight ({len(resolved)} stores):")
                for r in resolved:
                    name = store_names.get(r["location_id"], f"Store {r['location_id']}")
                    lines.append(f"  {name} -- data recovered ({r['new_count']} orders now)")
                lines.append("")

            alert_msg = "\n".join(lines)

        if alert_msg:
            print("\n" + "=" * 60)
            print(alert_msg)
            print("=" * 60 + "\n")

            if args.dry_run:
                log.info("DRY RUN: Alert not sent")
            elif args.no_chat:
                log.info("--no-chat: Skipping Chat")
            else:
                send_google_chat(alert_msg)

        summary = {
            "date": target_date,
            "mode": "verify-only",
            "still_unresolved": len(still_unresolved),
            "resolved_count": len(resolved),
            "alert_sent": alert_msg is not None and not args.dry_run and not args.no_chat,
        }
        log.info("Summary: %s", json.dumps(summary, indent=2))
        return summary

    # ── FULL DETECTION MODE (midnight) ────────────────────────────────
    log.info("Fetching baselines for DOW %d...", pg_dow)
    baselines = fetch_baselines(key, pg_dow)
    log.info("Got %d store baselines", len(baselines))

    chain_median = fetch_chain_median(key, pg_dow)
    log.info("Chain-wide median for DOW %d: %.1f", pg_dow, chain_median)

    # Layer 1+2: Classify anomalies per store
    anomalies = []
    for loc_id in store_names:
        actual_data = actuals.get(loc_id, {})
        actual_count = actual_data.get("count", 0)
        last_billed = actual_data.get("last_billed_at")
        baseline = baselines.get(loc_id)

        result = classify_anomaly(actual_count, baseline, chain_median, last_billed)
        if result:
            result["location_id"] = loc_id
            result["business_date"] = target_date
            anomalies.append(result)

    log.info("Detected %d anomalies across %d stores", len(anomalies), len(store_names))

    # Layer 3: Cross-store correlation
    cross_store = classify_cross_store(anomalies) if anomalies else "NONE"
    if anomalies:
        log.info("Cross-store classification: %s", cross_store)

    # Self-healing check
    log.info("Running self-healing check...")
    resolved = self_heal(key, actuals, target_date) if not args.dry_run else []
    log.info("Resolved %d previously anomalous stores", len(resolved))

    # Log anomalies to DB
    if anomalies and not args.dry_run:
        db_rows = []
        now_str = datetime.now(timezone.utc).isoformat()
        for a in anomalies:
            db_rows.append({
                "location_id": a["location_id"],
                "business_date": a["business_date"],
                "anomaly_type": a["anomaly_type"],
                "order_count": a["order_count"],
                "median_orders": a["median_orders"],
                "pct_of_median": a["pct_of_median"],
                "last_order_time": a.get("last_order_time"),
                "diagnosis": a.get("diagnosis"),
                "resolved": False,
                "notified_at": now_str,
            })
        upserted = supabase_upsert(key, "sync_anomalies", db_rows, "location_id,business_date")
        log.info("Upserted %d anomaly records to sync_anomalies", len(upserted))

    # Build alert message
    alert_msg = build_alert_message(target_date, anomalies, cross_store, resolved, store_names)

    # Output
    print("\n" + "=" * 60)
    print(alert_msg)
    print("=" * 60 + "\n")

    # Send to Google Chat
    if args.dry_run:
        log.info("DRY RUN: Alert not sent to Google Chat")
    elif args.no_chat:
        log.info("--no-chat: Skipping Google Chat alert")
    else:
        send_google_chat(alert_msg)

    # Summary
    summary = {
        "date": target_date,
        "mode": "full",
        "stores_checked": len(store_names),
        "anomalies_found": len(anomalies),
        "cross_store_class": cross_store,
        "resolved_count": len(resolved),
        "anomaly_types": {},
    }
    for a in anomalies:
        t = a["anomaly_type"]
        summary["anomaly_types"][t] = summary["anomaly_types"].get(t, 0) + 1

    log.info("Summary: %s", json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
