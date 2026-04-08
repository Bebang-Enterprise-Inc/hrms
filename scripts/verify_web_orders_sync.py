"""S171 - web_orders sync verification (Phase 6).

Mirror of `verify_mosaic_pos_sync.py` shape, for the website pipeline.

Source-of-truth: Superadmin API (`https://superadmin.bebang.ph/api/online-orders`)
authenticated via `x-api-key` header. Schema and auth match `sync_web_to_supabase.py`.

For each store-day in the window:
  1. Page through Superadmin to collect the set of order IDs (or reference_ids) from
     the source-of-truth.
  2. Read the matching set from Supabase `web_orders`.
  3. Compute extras (in Supabase, not in SoT) and missing (in SoT, not in Supabase).
  4. Categorize per (store, business_date) and emit a drift report.

This script does NOT tombstone web_orders rows -- there is no precedent for the
web_orders tombstone pattern yet (deferred to S172). It only reports.

CLI:
  python scripts/verify_web_orders_sync.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] \
                                            [--store STORE_ID] [--dry-run] [--no-chat]

Exit codes:
  0  success (drift report written)
  2  SENTRY_DSN missing (CB5 fail-fast)
  3  SUPERADMIN_API_KEY missing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import sentry_sdk

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _resolve_secret(env_name: str, fallback_name: str | None = None) -> str:
    val = os.environ.get(env_name, "").strip()
    if val:
        return val
    for name in (env_name, fallback_name):
        if not name:
            continue
        try:
            import subprocess
            result = subprocess.run(
                ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", name,
                 "--plain", "--project", "bei-erp", "--config", "dev"],
                capture_output=True, text=True, timeout=15,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    return ""


SENTRY_DSN = _resolve_secret("SENTRY_DSN")
if not SENTRY_DSN:
    print("ERROR: SENTRY_DSN missing -- refusing to run web_orders verifier without observability.",
          file=sys.stderr)
    sys.exit(2)

sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=0.0,
    profiles_sample_rate=0.0,
    release="s171-verify-web-orders",
)
sentry_sdk.set_tag("module", "sync_verification")
sentry_sdk.set_tag("action", "verify_web_orders_sync")

SUPERADMIN_URL = "https://superadmin.bebang.ph"
SUPERADMIN_API_KEY = _resolve_secret("SUPERADMIN_API_KEY", "SUPERADMIN_STORES_API_KEY")
if not SUPERADMIN_API_KEY:
    print("ERROR: SUPERADMIN_API_KEY missing.", file=sys.stderr)
    sys.exit(3)

SUPABASE_KEY = _resolve_secret("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_URL = "https://csnniykjrychgajfrgua.supabase.co"
PHT = timezone(timedelta(hours=8))
SA_RATE_LIMIT_SLEEP = 1.0
OUT_DIR = ROOT.parent / "output" / "l3" / "s171"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Use S169 helpers from verify_mosaic_pos_sync via _supabase_query_sql for raw SQL.
import verify_mosaic_pos_sync as v169  # noqa: E402
_supabase_query_sql = v169._supabase_query_sql


# ---------------------------------------------------------------------------
# Source-of-truth fetch
# ---------------------------------------------------------------------------
def fetch_web_order_ids(from_date: str, to_date: str, store_id: int | None = None) -> list[dict]:
    """Page through Superadmin /api/online-orders and return a flat list of orders.

    Each entry minimally has: id, reference_id, store_id, business_date, gross.
    """
    out: list[dict] = []
    page = 1
    while True:
        params = {"from": from_date, "to": to_date, "page": page, "per_page": 100}
        if store_id:
            params["store_id"] = store_id
        headers = {"x-api-key": SUPERADMIN_API_KEY, "Accept": "application/json"}
        try:
            r = requests.get(f"{SUPERADMIN_URL}/api/online-orders",
                             headers=headers, params=params, timeout=60)
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
            print(f"  SA request error page={page}: {e}", file=sys.stderr)
            break
        if r.status_code == 429:
            time.sleep(30)
            continue
        if r.status_code != 200:
            print(f"  SA error {r.status_code}: {r.text[:200]}", file=sys.stderr)
            break
        body = r.json() or {}
        data = body.get("data") or []
        for o in data:
            out.append({
                "id": o.get("id"),
                "reference_id": o.get("reference_id") or o.get("orderId") or o.get("number"),
                "store_id": o.get("store_id") or (o.get("store") or {}).get("id"),
                "business_date": o.get("delivery_date") or o.get("deliver_on")
                                 or o.get("business_date") or o.get("created_at"),
                "gross": o.get("total") or o.get("gross_total") or o.get("total_amount"),
            })
        last_page = body.get("last_page", 1)
        if page >= last_page or not data:
            break
        page += 1
        time.sleep(SA_RATE_LIMIT_SLEEP)
    return out


def supabase_web_ids(from_date: str, to_date: str) -> dict:
    """Return {(location_id, business_date): [reference_ids,...]} from web_orders."""
    sql = (
        "SELECT location_id, business_date, reference_id "
        f"FROM web_orders WHERE business_date >= '{from_date}' "
        f"AND business_date <= '{to_date}'"
    )
    rows = _supabase_query_sql(sql) or []
    grouped: dict[tuple, list[str]] = {}
    for r in rows:
        key = (r.get("location_id"), str(r.get("business_date"))[:10])
        grouped.setdefault(key, []).append(str(r.get("reference_id") or ""))
    return grouped


def _load_tenant_map() -> dict:
    """slug -> location_id mapping (matches scripts/sync_web_to_supabase.py)."""
    p = ROOT.parent / "data" / "POS_Extraction" / "mosaic_tenants.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for slug, info in raw.items():
        if isinstance(info, dict) and info.get("location_id"):
            out[slug] = int(info["location_id"])
    return out


def source_of_truth_count(from_date: str, to_date: str) -> dict:
    """Return {(location_id, business_date): [reference_ids,...]} from Superadmin.

    Translates Superadmin store slug -> Supabase location_id via mosaic_tenants.json
    so the keys match supabase_web_ids() and drift compute is meaningful.
    """
    tenant_map = _load_tenant_map()
    raw = fetch_web_order_ids(from_date, to_date)
    grouped: dict[tuple, list[str]] = {}
    unmapped_slugs: set[str] = set()
    for o in raw:
        bd = o.get("business_date") or ""
        if isinstance(bd, str) and len(bd) >= 10:
            bd = bd[:10]
        slug = o.get("store_id")
        loc_id = tenant_map.get(slug) if isinstance(slug, str) else None
        if loc_id is None:
            unmapped_slugs.add(str(slug))
            continue
        key = (loc_id, bd)
        grouped.setdefault(key, []).append(str(o.get("reference_id") or o.get("id") or ""))
    if unmapped_slugs:
        print(f"  WARN: {len(unmapped_slugs)} unmapped slugs (no location_id): "
              f"{sorted(unmapped_slugs)[:10]}", file=sys.stderr)
    return grouped


# ---------------------------------------------------------------------------
# Drift compute
# ---------------------------------------------------------------------------
def compute_drift(sot: dict, sup: dict) -> list[dict]:
    """Count-level parity per (location_id, business_date).

    NOTE: Superadmin and Supabase store DIFFERENT identifier conventions for
    the same order (Superadmin returns a small int order id like '158217';
    Supabase stores a composite reference_id like
    '19a9ce32-575b-461e-8fde-c6ba18550b03-1775033908'). Until a stable join key
    is established between the two surfaces, S171 can only assert count parity
    per (store, date). ID-level set-diff is reported as N/A.

    This is itself a Phase 6 finding worth recording in the defect register.
    """
    rows: list[dict] = []
    keys = set(sot.keys()) | set(sup.keys())
    for key in sorted(keys, key=lambda k: (str(k[1]), str(k[0]))):
        s_count = len(sot.get(key, []))
        u_count = len(sup.get(key, []))
        delta = u_count - s_count
        rows.append({
            "location_id": key[0],
            "business_date": key[1],
            "sot_count": s_count,
            "supabase_count": u_count,
            "count_delta": delta,
            "drift": abs(delta),
            "id_join_key_resolved": False,
        })
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S171 web_orders verifier")
    today = datetime.now(PHT).date()
    p.add_argument("--from", dest="date_from",
                   default=(today - timedelta(days=30)).isoformat())
    p.add_argument("--to", dest="date_to",
                   default=(today - timedelta(days=1)).isoformat())
    p.add_argument("--store", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-chat", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"S171 web_orders verifier: {args.date_from} -> {args.date_to}")
    try:
        sot = source_of_truth_count(args.date_from, args.date_to)
        sup = supabase_web_ids(args.date_from, args.date_to)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"FATAL: {e}", file=sys.stderr)
        return 1
    drift = compute_drift(sot, sup)
    summary = {
        "sot_tuples": len(sot),
        "supabase_tuples": len(sup),
        "drift_rows": sum(1 for r in drift if r["drift"] > 0),
        "tuples_count_match": sum(1 for r in drift if r["count_delta"] == 0
                                  and r["sot_count"] > 0),
        "tuples_supabase_over": sum(1 for r in drift if r["count_delta"] > 0),
        "tuples_supabase_under": sum(1 for r in drift if r["count_delta"] < 0),
        "total_count_delta_abs": sum(abs(r["count_delta"]) for r in drift),
        "id_join_key_resolved": False,
        "id_join_key_finding": (
            "Superadmin and Supabase use different reference_id conventions; "
            "ID-level set-diff not feasible without resolving the join key. "
            "S171 reports COUNT parity only. Recorded as a Phase 6 finding."
        ),
    }
    out = {"summary": summary, "rows": drift,
           "window": {"from": args.date_from, "to": args.date_to}}
    (OUT_DIR / "web_orders_drift.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"  summary: {summary}")
    print(f"  -> output/l3/s171/web_orders_drift.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
