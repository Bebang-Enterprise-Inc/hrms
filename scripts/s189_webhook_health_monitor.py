"""S189 webhook health monitor — delivery-based observability.

The sustainable source of truth is NOT Mosaic's GET /api/v1/webhooks (broken
500 for most groups). The source of truth is whether webhooks actually DELIVER
to our endpoint.

Checks:
  1. Delivery coverage — webhook_orders / total_orders in v_webhook_coverage
  2. Silence detection — zero webhook rows in last 24h but >0 poll rows
  3. Per-store coverage — v_store_internet_health anomalies
  4. Reconciliation gap — rows with cancellation_reason='reconciled_from_mosaic_gap'
     should be zero on a healthy day (means webhook caught it first)
  5. Endpoint reachability — POST ping to our receiver

Output:
  - JSON report to tmp/s189_webhook_health/YYYY-MM-DD.json
  - Non-zero exit code if OVERALL=FAIL
  - Optional Google Chat alert on degradation (BLIP_NOTIFICATIONS_SPACE)

Usage:
    python scripts/s189_webhook_health_monitor.py
    python scripts/s189_webhook_health_monitor.py --alert  # post Google Chat alert on FAIL/WARN
    python scripts/s189_webhook_health_monitor.py --days 3 # check last 3 days
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT_DIR = Path("tmp/s189_webhook_health")
CHAT_SPACE = os.environ.get("BLIP_NOTIFICATIONS_SPACE", "spaces/AAQABiNmpBg")

# Thresholds — tune as the system stabilizes. Starting conservative.
COVERAGE_WARN_PCT = 5.0      # below this → WARN (webhook barely firing)
COVERAGE_FAIL_PCT = 1.0      # below this for 48h → FAIL (webhook dark)
SILENCE_FAIL_HOURS = 24      # zero webhook in this window → FAIL


def doppler_get(key: str) -> str | None:
    r = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key,
         "--project", "bei-erp", "--config", "dev", "--plain"],
        capture_output=True, text=True, timeout=15,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def get_token() -> str:
    token = (os.environ.get("SUPABASE_MGMT_TOKEN") or "").strip()
    if token:
        return token
    token = doppler_get("SUPABASE_MGMT_TOKEN")
    if not token:
        raise SystemExit("SUPABASE_MGMT_TOKEN not available")
    return token


def sql(query: str, token: str) -> list:
    r = requests.post(
        "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query}, timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"SQL failed ({r.status_code}): {r.text[:300]}")
    return r.json() if r.text else []


def check_delivery_coverage(token: str, days: int) -> dict:
    rows = sql(
        f"""
        SELECT business_date, webhook_orders, poll_only_orders, total_orders, webhook_coverage_pct
        FROM v_webhook_coverage
        WHERE business_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY business_date DESC
        """,
        token,
    )
    if not rows:
        return {"check": "delivery_coverage", "status": "NO_DATA", "details": "no rows"}

    # Worst day
    worst = min(rows, key=lambda r: float(r.get("webhook_coverage_pct") or 0))
    avg_pct = sum(float(r.get("webhook_coverage_pct") or 0) for r in rows) / len(rows)

    status = "PASS"
    if avg_pct < COVERAGE_FAIL_PCT:
        status = "FAIL"
    elif avg_pct < COVERAGE_WARN_PCT:
        status = "WARN"

    return {
        "check": "delivery_coverage",
        "status": status,
        "days_checked": len(rows),
        "avg_coverage_pct": round(avg_pct, 2),
        "worst_day": worst.get("business_date"),
        "worst_pct": float(worst.get("webhook_coverage_pct") or 0),
        "samples": rows[:5],
    }


def check_silence(token: str) -> dict:
    rows = sql(
        f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE ingestion_source = 'webhook') AS webhook_rows,
               COUNT(*) FILTER (WHERE ingestion_source = 'poll') AS poll_rows
        FROM pos_orders
        WHERE updated_at >= NOW() - INTERVAL '{SILENCE_FAIL_HOURS} hours'
        """,
        token,
    )
    r = rows[0] if rows else {}
    total = int(r.get("total", 0))
    webhook = int(r.get("webhook_rows", 0))
    poll = int(r.get("poll_rows", 0))

    status = "PASS"
    if total > 100 and webhook == 0:
        status = "FAIL"
    return {
        "check": "silence",
        "status": status,
        "window_hours": SILENCE_FAIL_HOURS,
        "total_recent_orders": total,
        "webhook_rows": webhook,
        "poll_rows": poll,
    }


def check_store_internet_health(token: str) -> dict:
    rows = sql(
        "SELECT COUNT(DISTINCT location_id) AS flagged FROM v_store_internet_health",
        token,
    )
    flagged = int(rows[0].get("flagged", 0)) if rows else 0
    # All 46 stores flagged = systemic (not store-specific) issue
    status = "PASS"
    if flagged >= 46:
        status = "FAIL"  # systemic
    elif flagged >= 10:
        status = "WARN"
    return {
        "check": "store_internet_health",
        "status": status,
        "stores_flagged_poor_coverage": flagged,
        "systemic": flagged >= 46,
    }


def check_reconciliation_gap(token: str) -> dict:
    """If webhooks are healthy, reconciliation should find few gaps."""
    rows = sql(
        """
        SELECT COUNT(*) AS gaps,
               MAX(cancelled_at) AS last_gap
        FROM pos_orders
        WHERE cancellation_reason = 'reconciled_from_mosaic_gap'
          AND cancelled_at >= NOW() - INTERVAL '7 days'
        """,
        token,
    )
    r = rows[0] if rows else {}
    gaps = int(r.get("gaps", 0))
    # Many reconciliation gaps in last 7d = webhooks are missing cancels
    status = "PASS" if gaps < 10 else "WARN" if gaps < 100 else "FAIL"
    return {
        "check": "reconciliation_gap",
        "status": status,
        "gaps_last_7_days": gaps,
        "last_gap_at": r.get("last_gap"),
    }


def check_pos_sync_freshness(token: str) -> dict:
    """S197: POS sync 5-min health — newest pos_orders row within last 10 min."""
    rows = sql("SELECT MAX(updated_at) AS latest FROM pos_orders", token)
    latest = rows[0].get("latest") if rows else None
    if not latest:
        return {"check": "pos_sync_freshness", "status": "NO_DATA"}
    from datetime import datetime as dt
    try:
        ts = dt.fromisoformat(str(latest).replace("Z", "+00:00"))
        lag_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
    except Exception:
        return {"check": "pos_sync_freshness", "status": "ERROR", "raw_latest": str(latest)}
    status = "PASS" if lag_min <= 10 else "WARN" if lag_min <= 30 else "FAIL"
    return {
        "check": "pos_sync_freshness",
        "status": status,
        "lag_minutes": round(lag_min, 1),
        "latest_updated_at": str(latest),
    }


def check_endpoint_reachability() -> dict:
    try:
        r = requests.post(
            "https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive",
            json={"event": "ping"}, timeout=15,
        )
        ok = r.status_code == 200 and "ping" in r.text
        return {
            "check": "endpoint_reachability",
            "status": "PASS" if ok else "FAIL",
            "http_status": r.status_code,
            "body_snippet": r.text[:150],
        }
    except Exception as e:
        return {
            "check": "endpoint_reachability",
            "status": "FAIL",
            "error": str(e)[:200],
        }


def post_chat_alert(report: dict) -> bool:
    """Post health report to Google Chat via service account.

    Requires credentials/task-manager-service.json and googleapiclient.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("  (google-api-python-client not installed; skipping chat alert)")
        return False

    creds_path = Path("credentials/task-manager-service.json")
    if not creds_path.exists():
        print(f"  (credentials file missing at {creds_path}; skipping chat alert)")
        return False

    status = report["overall"]
    icon = {"PASS": "\U00002705", "WARN": "\U0001F7E1", "FAIL": "\U0001F534",
            "NO_DATA": "\U000026AA"}.get(status, "\U00002753")

    fails = [c["check"] for c in report["checks"] if c["status"] == "FAIL"]
    warns = [c["check"] for c in report["checks"] if c["status"] == "WARN"]

    lines = [
        f"{icon} S189 Webhook Health: {status}",
        f"Run at: {report['run_at']}",
    ]
    if fails:
        lines.append(f"FAIL: {', '.join(fails)}")
    if warns:
        lines.append(f"WARN: {', '.join(warns)}")

    # Add the delivery coverage since that's the headline metric
    coverage = next((c for c in report["checks"] if c["check"] == "delivery_coverage"), None)
    if coverage:
        lines.append(f"Delivery coverage: {coverage.get('avg_coverage_pct', 0)}% (over {coverage.get('days_checked', 0)} days)")

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(creds_path), scopes=["https://www.googleapis.com/auth/chat.bot"],
        )
        chat = build("chat", "v1", credentials=creds, cache_discovery=False)
        chat.spaces().messages().create(
            parent=CHAT_SPACE,
            body={"text": "\n".join(lines)},
        ).execute()
        return True
    except Exception as e:
        print(f"  Chat alert failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="S189 webhook health monitor")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--alert", action="store_true",
                        help="Post Google Chat alert on WARN or FAIL")
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    args = parser.parse_args()

    token = get_token()
    now = datetime.now(timezone.utc)

    report = {
        "run_at": now.isoformat(),
        "days_checked": args.days,
        "checks": [],
    }

    for fn, kwargs in [
        (check_endpoint_reachability, {}),
        (check_delivery_coverage, {"days": args.days}),
        (check_silence, {}),
        (check_store_internet_health, {}),
        (check_reconciliation_gap, {}),
        (check_pos_sync_freshness, {}),  # S197: 5-min sync freshness
    ]:
        try:
            if fn is check_endpoint_reachability:
                result = fn()
            else:
                result = fn(token, **kwargs)
            report["checks"].append(result)
            icon = {"PASS": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]",
                    "NO_DATA": "[--]"}.get(result["status"], "[?]")
            print(f"  {icon} {result['check']}: {result['status']}")
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {e}")
            report["checks"].append({"check": fn.__name__, "status": "ERROR", "error": str(e)[:300]})

    statuses = [c["status"] for c in report["checks"]]
    if "FAIL" in statuses:
        report["overall"] = "FAIL"
    elif "ERROR" in statuses:
        report["overall"] = "ERROR"
    elif "WARN" in statuses:
        report["overall"] = "WARN"
    else:
        report["overall"] = "PASS"

    print(f"\nOverall: {report['overall']}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{now.date()}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"Report: {out_path}")

    if args.alert and report["overall"] in ("FAIL", "WARN", "ERROR"):
        posted = post_chat_alert(report)
        print(f"Chat alert: {'POSTED' if posted else 'SKIPPED'}")

    return 1 if report["overall"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
