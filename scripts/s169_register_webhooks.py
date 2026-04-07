"""S169 T7.1 — Register Mosaic webhooks for order.cancelled events.

Iterates over UNIQUE credential groups in MOSAIC_POS_API_KEYS.csv (12 groups).
For each group:
  1. OAuth client_credentials -> access_token
  2. GET /api/v1/webhooks (list existing)
  3. If our webhook URL is already registered with events=["order.cancelled"], SKIP
  4. Otherwise POST /api/v1/webhooks
  5. Append registration to MOSAIC_WEBHOOK_REGISTRATIONS.csv

Usage:
    python scripts/s169_register_webhooks.py [--dry-run] [--group <name>]

Code only -- safe to run with --dry-run. Without --dry-run it hits live Mosaic.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOSAIC_BASE_URL = "https://api.mosaic-pos.com"
MOSAIC_TOKEN_URL = f"{MOSAIC_BASE_URL}/oauth/token"
MOSAIC_WEBHOOKS_URL = f"{MOSAIC_BASE_URL}/api/v1/webhooks"

WEBHOOK_URL = "https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive"
WEBHOOK_EVENTS = ["order.cancelled"]

REPO_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_CSV = REPO_ROOT / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"
REGISTRATIONS_CSV = REPO_ROOT / "data" / "POS_Extraction" / "MOSAIC_WEBHOOK_REGISTRATIONS.csv"

REGISTRATIONS_HEADERS = [
    "credential_group",
    "client_id",
    "webhook_id",
    "url",
    "events",
    "registered_at",
]

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "BEI-S169-WebhookRegistrar/1.0",
    "X-Source": "s169",
}

REQUEST_TIMEOUT = 30


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------


def load_credential_groups(csv_path: Path) -> list[dict]:
    """Return list of unique credential groups, deduped by Mosaic Client ID."""
    groups: dict[str, dict] = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("Mosaic Client ID") or "").strip()
            if not cid:
                continue
            if cid not in groups:
                groups[cid] = {
                    "client_id": cid,
                    "client_secret": (row.get("Mosaic Client Secret") or "").strip(),
                    "group_name": (row.get("Credential Group") or "").strip(),
                    "location_count": 0,
                }
            groups[cid]["location_count"] += 1
    return list(groups.values())


# ---------------------------------------------------------------------------
# Mosaic API helpers
# ---------------------------------------------------------------------------


def get_access_token(client_id: str, client_secret: str) -> str:
    """OAuth client_credentials grant -> access_token."""
    r = requests.post(
        MOSAIC_TOKEN_URL,
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        headers=DEFAULT_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    payload = r.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"OAuth response missing access_token: {payload}")
    return token


def list_webhooks(token: str) -> list[dict]:
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    r = requests.get(MOSAIC_WEBHOOKS_URL, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and "data" in body:
        return list(body["data"])
    if isinstance(body, list):
        return body
    return []


def webhook_already_registered(existing: list[dict]) -> dict | None:
    """Return the existing webhook dict if our URL+event is present."""
    for hook in existing:
        url = hook.get("url") or hook.get("endpoint") or ""
        events = hook.get("events") or hook.get("event_types") or []
        if url == WEBHOOK_URL and "order.cancelled" in events:
            return hook
    return None


def register_webhook(token: str) -> dict:
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    r = requests.post(
        MOSAIC_WEBHOOKS_URL,
        headers=headers,
        json={"url": WEBHOOK_URL, "events": WEBHOOK_EVENTS},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


# ---------------------------------------------------------------------------
# Registrations CSV
# ---------------------------------------------------------------------------


def ensure_registrations_csv() -> None:
    if REGISTRATIONS_CSV.exists():
        return
    REGISTRATIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRATIONS_CSV, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(REGISTRATIONS_HEADERS)


def append_registration(
    group_name: str,
    client_id: str,
    webhook_id: str,
    url: str,
    events: list[str],
) -> None:
    ensure_registrations_csv()
    with open(REGISTRATIONS_CSV, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(
            [
                group_name,
                client_id,
                webhook_id,
                url,
                "|".join(events),
                datetime.now(timezone.utc).isoformat(),
            ]
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Register Mosaic order.cancelled webhooks")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only; do not call Mosaic")
    parser.add_argument("--group", type=str, default=None, help="Filter to a specific Credential Group name")
    args = parser.parse_args()

    if not CREDENTIALS_CSV.exists():
        log(f"FATAL: credentials CSV not found at {CREDENTIALS_CSV}")
        return 2

    groups = load_credential_groups(CREDENTIALS_CSV)
    if args.group:
        groups = [g for g in groups if g["group_name"] == args.group]
        if not groups:
            log(f"No credential groups match --group {args.group!r}")
            return 2

    log(f"Loaded {len(groups)} unique credential groups from {CREDENTIALS_CSV.name}")
    log(f"Webhook URL: {WEBHOOK_URL}")
    log(f"Events: {WEBHOOK_EVENTS}")
    if args.dry_run:
        log("DRY-RUN MODE -- no live API calls will be made")

    registered_new = 0
    skipped_existing = 0
    failed = 0

    for group in groups:
        group_label = f"{group['group_name']} ({group['client_id'][:8]}...)"
        log(f"--- {group_label} [{group['location_count']} locations]")

        if args.dry_run:
            log(f"  [DRY-RUN] would OAuth, list webhooks, register if missing")
            continue

        try:
            token = get_access_token(group["client_id"], group["client_secret"])
            existing = list_webhooks(token)
            already = webhook_already_registered(existing)
            if already:
                webhook_id = str(already.get("id") or already.get("webhook_id") or "unknown")
                log(f"  SKIP: webhook already registered (id={webhook_id})")
                skipped_existing += 1
                continue

            new_hook = register_webhook(token)
            webhook_id = str(new_hook.get("id") or new_hook.get("webhook_id") or "unknown")
            append_registration(
                group_name=group["group_name"],
                client_id=group["client_id"],
                webhook_id=webhook_id,
                url=WEBHOOK_URL,
                events=WEBHOOK_EVENTS,
            )
            log(f"  REGISTERED: webhook id={webhook_id}")
            registered_new += 1

            # Polite spacing between groups
            time.sleep(1.0)

        except Exception as exc:
            log(f"  [REGISTRATION_ERROR] {group_label}: {exc}")
            failed += 1
            continue

    log("=" * 60)
    log(f"Summary: Registered {registered_new} new, skipped {skipped_existing} existing, failed {failed}")
    log(f"Registration log: {REGISTRATIONS_CSV}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
