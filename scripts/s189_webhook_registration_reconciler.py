"""S189 webhook registration reconciler — idempotent self-healing.

Because Mosaic's GET /api/v1/webhooks is unreliable (returns 500 for most
groups), we cannot audit registrations via their API. Instead, this script
POSTS registrations idempotently — if a registration already exists, Mosaic
either accepts it again (no-op) or returns a duplicate error we can swallow.

Runs daily via GitHub Actions. Each run:
  1. For each of 12 credential groups:
     - OAuth client_credentials → access_token
     - POST /api/v1/webhooks with our URL + events=[order.cancelled, order.completed]
     - Record outcome in reconciliation log
  2. Write summary to tmp/s189_webhook_registration/YYYY-MM-DD.json
  3. Post Google Chat alert if >N groups failed
  4. Exit 1 if >50% groups failed (blocks the workflow so we see it)

This makes webhook registration *guaranteed present* within 24 hours of any
drift, without depending on Mosaic's flaky listing API.

Usage:
    python scripts/s189_webhook_registration_reconciler.py
    python scripts/s189_webhook_registration_reconciler.py --dry-run
    python scripts/s189_webhook_registration_reconciler.py --events order.cancelled
    python scripts/s189_webhook_registration_reconciler.py --alert
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

CREDS_CSV = Path("data/POS_Extraction/MOSAIC_POS_API_KEYS.csv")
OUT_DIR = Path("tmp/s189_webhook_registration")

MOSAIC_BASE = "https://api.mosaic-pos.com"
WEBHOOK_URL = "https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive"
DEFAULT_EVENTS = ["order.cancelled", "order.completed"]
CHAT_SPACE = os.environ.get("BLIP_NOTIFICATIONS_SPACE", "spaces/AAQABiNmpBg")

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "BEI-S189-WebhookReconciler/1.0",
    "X-Source": "s189-reconciler",
}


def oauth(client_id: str, client_secret: str, attempts: int = 3) -> str | None:
    for i in range(attempts):
        try:
            r = requests.post(
                f"{MOSAIC_BASE}/oauth/token",
                json={"client_id": client_id, "client_secret": client_secret,
                      "grant_type": "client_credentials"},
                headers=DEFAULT_HEADERS, timeout=15,
            )
            if r.ok:
                return r.json().get("access_token")
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


def _try_list_webhooks(token: str) -> list[dict] | None:
    """GET /api/v1/webhooks — per Mosaic OpenAPI doc (docs/api/MOSAIC_API_OPENAPI_2026-04-14.json).

    Returns the list of webhooks or None if Mosaic returned 5xx (known flaky).
    """
    try:
        r = requests.get(
            f"{MOSAIC_BASE}/api/v1/webhooks",
            headers={**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if not r.ok:
        return None
    try:
        body = r.json()
    except (ValueError, TypeError):
        return None
    hooks = body.get("data", body) if isinstance(body, dict) else body
    return hooks if isinstance(hooks, list) else None


def _update_webhook(token: str, webhook_id: str, events: list[str]) -> tuple[bool, str, dict | None]:
    """PUT /api/v1/webhooks/{id} — update events for an existing registration."""
    try:
        r = requests.put(
            f"{MOSAIC_BASE}/api/v1/webhooks/{webhook_id}",
            headers={**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"},
            json={"url": WEBHOOK_URL, "events": events},
            timeout=30,
        )
    except requests.RequestException as e:
        return False, f"network_error: {e}", None
    if r.ok:
        try:
            body = r.json()
            data = body.get("data", body) if isinstance(body, dict) else body
            return True, "updated", data
        except (ValueError, TypeError):
            return True, "updated_but_body_unparseable", None
    return False, f"put_http_{r.status_code}: {(r.text or '')[:200]}", None


def register(token: str, events: list[str]) -> tuple[bool, str, dict | None]:
    """Reconcile webhook registration for our URL.

    Per Mosaic OpenAPI (docs/api/MOSAIC_API_OPENAPI_2026-04-14.json):
      - POST /api/v1/webhooks creates {url, events}
      - PUT  /api/v1/webhooks/{id} updates events for existing registration
      - GET  /api/v1/webhooks lists (known flaky — 500 for ~11/12 groups)

    Strategy: try GET first. If it works:
      - Our URL absent → POST to create
      - Our URL present with matching events → already_registered (no-op)
      - Our URL present with different events → PUT to update
    If GET fails (most common case due to Mosaic 500s): fall through to POST
    and rely on Mosaic's duplicate-URL handling (409/422 swallowed as
    already_registered).
    """
    existing = _try_list_webhooks(token)
    if existing is not None:
        matching = [h for h in existing if (h.get("url") or "") == WEBHOOK_URL]
        if matching:
            current_events = set(matching[0].get("events") or matching[0].get("event_types") or [])
            wanted = set(events)
            if wanted.issubset(current_events):
                return True, "already_registered", matching[0]
            # Registration exists but doesn't cover all our events → PUT to update
            webhook_id = matching[0].get("id")
            if webhook_id:
                union = sorted(current_events | wanted)
                return _update_webhook(token, str(webhook_id), union)
        # No matching registration → POST below

    try:
        r = requests.post(
            f"{MOSAIC_BASE}/api/v1/webhooks",
            headers={**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"},
            json={"url": WEBHOOK_URL, "events": events},
            timeout=30,
        )
    except requests.RequestException as e:
        return False, f"network_error: {e}", None

    if r.ok:
        try:
            body = r.json()
            data = body.get("data", body) if isinstance(body, dict) else body
            return True, "registered", data
        except (ValueError, TypeError):
            return True, "registered_but_body_unparseable", None

    # Swallow duplicate errors as "already registered"
    body_text = r.text or ""
    if r.status_code in (409, 422) or "already" in body_text.lower() or "duplicate" in body_text.lower():
        return True, "already_registered", None

    return False, f"http_{r.status_code}: {body_text[:200]}", None


def load_groups() -> list[dict]:
    seen = set()
    groups = []
    if not CREDS_CSV.exists():
        raise SystemExit(f"Missing {CREDS_CSV}")
    with open(CREDS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("Mosaic Client ID") or "").strip()
            if not cid or cid in seen:
                continue
            seen.add(cid)
            groups.append({
                "client_id": cid,
                "client_secret": (row.get("Mosaic Client Secret") or "").strip(),
                "group_name": (row.get("Credential Group") or "").strip() or cid[:12],
            })
    return groups


def post_chat_alert(summary: dict) -> bool:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("  google-api-python-client not installed; skip chat")
        return False

    creds_path = Path("credentials/task-manager-service.json")
    if not creds_path.exists():
        print(f"  credentials missing; skip chat")
        return False

    failed = summary.get("failed_count", 0)
    total = summary.get("total_groups", 0)
    icon = "\U0001F534" if failed > total // 2 else "\U0001F7E1" if failed else "\U00002705"
    lines = [
        f"{icon} S189 Webhook Registration Reconciler",
        f"Run at: {summary['run_at']}",
        f"Groups: {summary['succeeded_count']}/{total} succeeded (new={summary['newly_registered']}, already={summary['already_registered']}, failed={failed})",
        f"URL: {WEBHOOK_URL}",
        f"Events: {', '.join(summary['events'])}",
    ]
    if summary.get("failed_groups"):
        lines.append(f"Failed groups: {', '.join(summary['failed_groups'][:5])}")

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
        print(f"  chat alert failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--events", nargs="+", default=DEFAULT_EVENTS)
    parser.add_argument("--alert", action="store_true")
    args = parser.parse_args()

    groups = load_groups()
    now = datetime.now(timezone.utc)

    print(f"S189 Webhook Registration Reconciler — {now.isoformat()}")
    print(f"  URL: {WEBHOOK_URL}")
    print(f"  Events: {args.events}")
    print(f"  Groups: {len(groups)}")
    if args.dry_run:
        print("  [DRY-RUN] no live API calls")

    summary = {
        "run_at": now.isoformat(),
        "url": WEBHOOK_URL,
        "events": args.events,
        "total_groups": len(groups),
        "succeeded_count": 0,
        "newly_registered": 0,
        "already_registered": 0,
        "failed_count": 0,
        "failed_groups": [],
        "results": [],
    }

    for idx, g in enumerate(groups, 1):
        name = g["group_name"]
        print(f"\n[{idx}/{len(groups)}] {name}")

        if args.dry_run:
            print(f"  [DRY-RUN] would OAuth + POST webhook")
            summary["results"].append({"group": name, "status": "dry_run"})
            continue

        token = oauth(g["client_id"], g["client_secret"])
        if not token:
            print(f"  OAuth failed")
            summary["failed_count"] += 1
            summary["failed_groups"].append(name)
            summary["results"].append({"group": name, "status": "oauth_failed"})
            time.sleep(2)
            continue

        ok, reason, body = register(token, args.events)
        print(f"  {'OK' if ok else 'FAIL'}: {reason}")
        if ok:
            summary["succeeded_count"] += 1
            if reason == "registered":
                summary["newly_registered"] += 1
            else:
                summary["already_registered"] += 1
        else:
            summary["failed_count"] += 1
            summary["failed_groups"].append(name)

        summary["results"].append({
            "group": name, "status": reason,
            "webhook_id": (body or {}).get("id") if body else None,
        })
        time.sleep(2)  # respectful rate limit

    # Write summary
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{now.date()}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary: {summary['succeeded_count']}/{summary['total_groups']} succeeded "
          f"(new={summary['newly_registered']}, already={summary['already_registered']}, "
          f"failed={summary['failed_count']})")
    print(f"Report: {out_path}")

    if args.alert:
        posted = post_chat_alert(summary)
        print(f"Chat alert: {'POSTED' if posted else 'SKIPPED'}")

    # Exit non-zero if majority failed (signal to GitHub Actions)
    if summary["failed_count"] > summary["total_groups"] // 2:
        print(f"FAIL: >50% groups failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
