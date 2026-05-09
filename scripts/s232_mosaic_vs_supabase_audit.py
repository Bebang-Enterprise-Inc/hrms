"""
s232_mosaic_vs_supabase_audit.py — forensic comparison between Mosaic POS API
and Supabase pos_orders for sample store-days.

For each (store, business_date) sample, we:
  1. Authenticate to Mosaic POS via OAuth client_credentials
  2. Paginate through ALL orders for that store-day
  3. Compute aggregates: order count, distinct bill numbers, sum gross_sales,
     sum net_sales, payment_status mix, paid_at min/max
  4. Query the same aggregates from Supabase pos_orders
  5. Compare side-by-side and surface any deltas

Output:
  output/s232/audit_report.md   — human-readable comparison
  output/s232/audit_data.json   — full machine-readable details

Coverage strategy:
  - Span all credential groups (Shared Pool, Araneta, Dedicated, etc.)
  - Hit the worst-recovered days (5/3, 5/7) and a normal day (5/4)
  - Include high-volume stores (SM Manila, SM Megamall, SM North EDSA) and small ones
  - Include store-days that triggered synthetic-id collision resolution
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

REPO = Path(__file__).resolve().parents[1]
# S242 v1.1 W3: --output-dir CLI flag redirects output to s242 namespace
# (preserves S232 historical audit_report.md intact when reused post-migration).
_arg_out = None
for i, a in enumerate(sys.argv):
    if a == "--output-dir" and i + 1 < len(sys.argv):
        _arg_out = sys.argv[i + 1]
        break
OUT_DIR = (REPO / _arg_out) if _arg_out else (REPO / "output" / "s232")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CREDENTIALS_CSV = REPO / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"

MOSAIC_BASE = "https://api.mosaic-pos.com"
SUPABASE_URL = "https://csnniykjrychgajfrgua.supabase.co"
PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

# Sample selection — diverse coverage across credential groups, days, and recovery profiles.
SAMPLE: list[tuple[int, str, str]] = [
    # (location_id, business_date, scenario_label)
    (2339, "2026-05-03", "SM Manila — peak weekend (Sun)"),
    (2338, "2026-05-07", "SM Megamall — recovered 149 missing bills"),
    (2284, "2026-05-07", "SM North EDSA — recovered 101 missing bills"),
    (2547, "2026-05-07", "Ayala Solenad — recovered 95 missing bills"),
    (2250, "2026-05-02", "The Grid Rockwell — synthetic-id collision case"),
    (2557, "2026-05-03", "Araneta Gateway — credential group + collision"),
    (2217, "2026-05-03", "BF Homes — recovered 106 missing bills"),
    (2766, "2026-05-05", "D'Verde Calamba — small store + early-cutoff day"),
    (2412, "2026-05-05", "SM Bicutan — control mid-volume Tue"),
    (2464, "2026-05-04", "SM Caloocan — control normal Mon"),
    (2179, "2026-05-02", "Megawide PITX — control weekend"),
    (2287, "2026-05-05", "Ayala Market Market — was 61 missing bills"),
]


def get_secret(env_name: str) -> str:
    val = os.environ.get(env_name, "")
    if val:
        return val
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Could not fetch {env_name}")
    return result.stdout.strip()


def load_credentials() -> dict[int, dict]:
    """Load Mosaic credentials keyed by location_id."""
    creds: dict[int, dict] = {}
    with open(CREDENTIALS_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                lid = int(row["Mosaic Location ID"])
            except (ValueError, KeyError):
                continue
            creds[lid] = {
                "store_name": row.get("Store Name", "?"),
                "client_id": row["Mosaic Client ID"],
                "client_secret": row["Mosaic Client Secret"],
                "credential_group": row.get("Credential Group", "?"),
            }
    return creds


_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def get_mosaic_token(client_id: str, client_secret: str) -> str:
    """OAuth client_credentials. Cache for 55 minutes."""
    cached = _TOKEN_CACHE.get(client_id)
    if cached and (time.time() - cached[1]) < 55 * 60:
        return cached[0]
    r = requests.post(
        f"{MOSAIC_BASE}/oauth/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Mosaic auth failed ({r.status_code}): {r.text[:200]}")
    token = r.json()["access_token"]
    _TOKEN_CACHE[client_id] = (token, time.time())
    return token


def fetch_all_orders_from_mosaic(token: str, location_id: int, business_date: str) -> list[dict]:
    """Paginate Mosaic API to retrieve every order for the (loc, date)."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    all_orders: list[dict] = []
    page = 1
    while True:
        params = {
            "filter[business_date]": business_date,
            "filter[location_id]": location_id,
            "page[number]": page,
            "page[size]": 100,
        }
        r = requests.get(
            f"{MOSAIC_BASE}/api/v1/orders",
            headers=headers, params=params, timeout=30,
        )
        if r.status_code == 429:
            time.sleep(15)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Mosaic fetch failed ({r.status_code}): {r.text[:200]}")
        body = r.json()
        data = body.get("data", [])
        all_orders.extend(data)
        last_page = (body.get("meta") or {}).get("last_page", page)
        if page >= last_page:
            break
        page += 1
        time.sleep(0.6)  # be polite
    return all_orders


def aggregate_mosaic(orders: list[dict]) -> dict:
    """Compute aggregates from Mosaic orders.

    Mosaic occasionally returns the same bill_number twice in one fetch (a
    known quirk — see the sync script's _dedupe_incoming_by_natural_key).
    The sync correctly stores ONE row per bill (canonical pick). For an
    apples-to-apples comparison vs Supabase, we dedupe by bill_number here
    too: keep the row with highest canonical score (PAID > VOIDED, higher
    gross, latest paid_at).
    """
    # Dedupe by bill_number using the same canonical-pick rule as the sync.
    by_bill: dict[str, dict] = {}
    raw_count = len(orders)
    for o in orders:
        bn = o.get("bill_number")
        if bn is None:
            continue
        existing = by_bill.get(str(bn))
        if existing is None:
            by_bill[str(bn)] = o
            continue
        # Score: PAID > VOIDED > other; non-cancelled > cancelled; higher gross; latest paid_at
        def score(x: dict) -> tuple:
            ps = (x.get("payment_status") or "").upper()
            paid_rank = 1 if ps == "PAID" else (0 if ps == "VOIDED" else -1)
            not_cx = 1 if not x.get("cancelled_at") else 0
            pb = x.get("price_breakdown") or {}
            gross = float(pb.get("gross_sales") or 0)
            return (paid_rank, not_cx, gross, str(x.get("paid_at") or ""))
        if score(o) > score(existing):
            by_bill[str(bn)] = o
    deduped = list(by_bill.values())
    dupes_in_fetch = raw_count - len(deduped)

    # Now aggregate from deduped set
    bills: set[str] = set()
    paid_bills: set[str] = set()
    payment_status_counts: Counter = Counter()
    sum_gross = 0.0
    sum_net = 0.0
    paid_ats: list[str] = []
    cancelled = 0
    for o in deduped:
        bn = o.get("bill_number")
        if bn is not None:
            bills.add(str(bn))
        ps = (o.get("payment_status") or "").upper()
        payment_status_counts[ps] += 1
        if ps == "PAID":
            if bn is not None:
                paid_bills.add(str(bn))
            pb = o.get("price_breakdown") or {}
            sum_gross += float(pb.get("gross_sales") or 0)
            sum_net += float(pb.get("net_sales") or 0)
        if o.get("cancelled_at"):
            cancelled += 1
        pa = o.get("paid_at")
        if pa:
            paid_ats.append(pa)
    return {
        "raw_orders": raw_count,
        "deduped_orders": len(deduped),
        "dupes_in_fetch": dupes_in_fetch,
        "distinct_bills": len(bills),
        "distinct_paid_bills": len(paid_bills),
        "payment_status_mix": dict(payment_status_counts),
        "cancelled_count": cancelled,
        "sum_gross_paid": round(sum_gross, 2),
        "sum_net_paid": round(sum_net, 2),
        "first_paid_at": min(paid_ats) if paid_ats else None,
        "last_paid_at": max(paid_ats) if paid_ats else None,
    }


def query_supabase(token: str, location_id: int, business_date: str) -> dict:
    """Aggregate Supabase pos_orders for (loc, date), using only LIVE rows
    (is_duplicate=false). v_pos_orders_live also excludes cancelled/duplicate
    rows — we use it as the canonical 'what the dashboard sees' lens."""
    sql = f"""
        SELECT
            COUNT(*)::int AS raw_orders,
            COUNT(DISTINCT bill_number)::int AS distinct_bills,
            COUNT(DISTINCT bill_number) FILTER (WHERE payment_status='PAID')::int AS distinct_paid_bills,
            COUNT(*) FILTER (WHERE payment_status='PAID')::int AS paid_count,
            COUNT(*) FILTER (WHERE payment_status='VOIDED')::int AS voided_count,
            COUNT(*) FILTER (WHERE payment_status NOT IN ('PAID','VOIDED') OR payment_status IS NULL)::int AS other_count,
            COUNT(*) FILTER (WHERE cancelled_at IS NOT NULL)::int AS cancelled_count,
            ROUND(SUM(gross_sales) FILTER (WHERE payment_status='PAID')::numeric, 2)::text AS sum_gross_paid,
            ROUND(SUM(net_sales) FILTER (WHERE payment_status='PAID')::numeric, 2)::text AS sum_net_paid,
            MIN(paid_at)::text AS first_paid_at,
            MAX(paid_at)::text AS last_paid_at
        FROM pos_orders
        WHERE location_id = {location_id}
          AND business_date = '{business_date}'
          AND is_duplicate = false
    """
    r = requests.post(
        MGMT_SQL_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": sql}, timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Supabase query failed ({r.status_code}): {r.text[:300]}")
    row = r.json()[0]
    return {
        "raw_orders": int(row["raw_orders"] or 0),
        "distinct_bills": int(row["distinct_bills"] or 0),
        "distinct_paid_bills": int(row["distinct_paid_bills"] or 0),
        "payment_status_mix": {
            "PAID": int(row["paid_count"] or 0),
            "VOIDED": int(row["voided_count"] or 0),
            "OTHER": int(row["other_count"] or 0),
        },
        "cancelled_count": int(row["cancelled_count"] or 0),
        "sum_gross_paid": float(row["sum_gross_paid"] or 0),
        "sum_net_paid": float(row["sum_net_paid"] or 0),
        "first_paid_at": row["first_paid_at"],
        "last_paid_at": row["last_paid_at"],
    }


def compare(mosaic: dict, supabase: dict) -> dict:
    """Diff mosaic vs supabase. Returns dict of deltas + verdict."""
    def delta(a, b):
        try:
            return round(float(a) - float(b), 2)
        except (TypeError, ValueError):
            return None

    deltas = {
        "distinct_paid_bills_delta": (mosaic["distinct_paid_bills"] - supabase["distinct_paid_bills"]),
        "sum_gross_paid_delta": delta(mosaic["sum_gross_paid"], supabase["sum_gross_paid"]),
        "sum_net_paid_delta": delta(mosaic["sum_net_paid"], supabase["sum_net_paid"]),
    }
    # Verdict
    bill_ok = deltas["distinct_paid_bills_delta"] == 0
    gross_ok = abs(deltas["sum_gross_paid_delta"] or 0) < 1.0  # within 1 peso (rounding)
    net_ok = abs(deltas["sum_net_paid_delta"] or 0) < 1.0
    verdict = "MATCH" if (bill_ok and gross_ok and net_ok) else "MISMATCH"
    return {**deltas, "verdict": verdict}


def main() -> None:
    print("Loading credentials...", flush=True)
    creds = load_credentials()
    mgmt_token = get_secret("SUPABASE_MGMT_TOKEN")

    rows: list[dict] = []
    print(f"Auditing {len(SAMPLE)} store-days...", flush=True)
    for i, (loc_id, bd, label) in enumerate(SAMPLE, 1):
        c = creds.get(loc_id)
        if not c:
            print(f"  [{i}/{len(SAMPLE)}] SKIP {loc_id} {bd}: no credentials", flush=True)
            continue
        store_name = c["store_name"]
        print(f"  [{i}/{len(SAMPLE)}] {store_name} ({loc_id}) {bd} — {label}", flush=True)

        try:
            mosaic_token = get_mosaic_token(c["client_id"], c["client_secret"])
            mosaic_orders = fetch_all_orders_from_mosaic(mosaic_token, loc_id, bd)
            mosaic_agg = aggregate_mosaic(mosaic_orders)
            supabase_agg = query_supabase(mgmt_token, loc_id, bd)
            cmp = compare(mosaic_agg, supabase_agg)
            print(
                f"      Mosaic: {mosaic_agg['distinct_paid_bills']} paid bills, "
                f"PHP {mosaic_agg['sum_gross_paid']:,.2f}  | "
                f"Supabase: {supabase_agg['distinct_paid_bills']} paid bills, "
                f"PHP {supabase_agg['sum_gross_paid']:,.2f}  | "
                f"VERDICT={cmp['verdict']}",
                flush=True,
            )
            rows.append({
                "location_id": loc_id,
                "store_name": store_name,
                "business_date": bd,
                "scenario": label,
                "mosaic": mosaic_agg,
                "supabase": supabase_agg,
                "compare": cmp,
            })
        except Exception as e:
            print(f"      ERROR: {e}", flush=True)
            rows.append({
                "location_id": loc_id,
                "store_name": store_name,
                "business_date": bd,
                "scenario": label,
                "error": str(e),
            })

    # Persist
    data_path = OUT_DIR / "audit_data.json"
    with data_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    # Markdown report
    lines: list[str] = []
    lines.append("# Mosaic API ↔ Supabase Forensic Audit")
    lines.append(f"_Generated: {datetime.now().isoformat()}_\n")

    matches = [r for r in rows if r.get("compare", {}).get("verdict") == "MATCH"]
    mismatches = [r for r in rows if r.get("compare", {}).get("verdict") == "MISMATCH"]
    errors = [r for r in rows if "error" in r]
    lines.append(f"**Sample: {len(rows)} store-days. "
                 f"MATCH: {len(matches)}, MISMATCH: {len(mismatches)}, ERROR: {len(errors)}**\n")

    lines.append("## Per-store-day comparison\n")
    lines.append("| Store | Date | Scenario | Mosaic Bills (PAID) | Supabase Bills (PAID) | Mosaic ₱ Gross | Supabase ₱ Gross | Δ Bills | Δ ₱ | Verdict |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['store_name']} | {r['business_date']} | {r['scenario']} | — | — | — | — | — | — | **ERROR**: {r['error'][:60]} |")
            continue
        m, s, c = r["mosaic"], r["supabase"], r["compare"]
        lines.append(
            f"| {r['store_name']} | {r['business_date']} | {r['scenario'][:40]} | "
            f"{m['distinct_paid_bills']} | {s['distinct_paid_bills']} | "
            f"{m['sum_gross_paid']:,.2f} | {s['sum_gross_paid']:,.2f} | "
            f"{c['distinct_paid_bills_delta']:+d} | "
            f"{c['sum_gross_paid_delta']:+,.2f} | "
            f"**{c['verdict']}** |"
        )

    lines.append("\n## Per-store-day full detail (Mosaic + Supabase)\n")
    for r in rows:
        if "error" in r:
            continue
        m, s, c = r["mosaic"], r["supabase"], r["compare"]
        lines.append(f"### {r['store_name']} ({r['location_id']}) — {r['business_date']}")
        lines.append(f"_{r['scenario']}_\n")
        lines.append("| Metric | Mosaic | Supabase | Δ |")
        lines.append("|---|---:|---:|---:|")
        lines.append(f"| Raw orders returned | {m['raw_orders']} | {s['raw_orders']} | {m['raw_orders']-s['raw_orders']:+d} |")
        lines.append(f"| Distinct bill numbers | {m['distinct_bills']} | {s['distinct_bills']} | {m['distinct_bills']-s['distinct_bills']:+d} |")
        lines.append(f"| Distinct PAID bills | {m['distinct_paid_bills']} | {s['distinct_paid_bills']} | {c['distinct_paid_bills_delta']:+d} |")
        lines.append(f"| Sum PAID gross | {m['sum_gross_paid']:,.2f} | {s['sum_gross_paid']:,.2f} | {c['sum_gross_paid_delta']:+,.2f} |")
        lines.append(f"| Sum PAID net | {m['sum_net_paid']:,.2f} | {s['sum_net_paid']:,.2f} | {c['sum_net_paid_delta']:+,.2f} |")
        lines.append(f"| Cancelled count | {m['cancelled_count']} | {s['cancelled_count']} | {m['cancelled_count']-s['cancelled_count']:+d} |")
        lines.append(f"| First paid_at | {m['first_paid_at']} | {s['first_paid_at']} | — |")
        lines.append(f"| Last paid_at | {m['last_paid_at']} | {s['last_paid_at']} | — |")
        lines.append(f"| Payment status mix (Mosaic) | {m['payment_status_mix']} | | |")
        lines.append(f"| Payment status mix (Supabase) | | {s['payment_status_mix']} | |")
        lines.append(f"\n**Verdict: {c['verdict']}**\n")

    report_path = OUT_DIR / "audit_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report_path}", flush=True)
    print(f"Data:   {data_path}", flush=True)
    print(f"\nSummary: MATCH={len(matches)}/{len(rows)}, MISMATCH={len(mismatches)}, ERROR={len(errors)}",
          flush=True)


if __name__ == "__main__":
    main()
