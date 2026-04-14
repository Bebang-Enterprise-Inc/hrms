"""S191 Phase 0 baseline audit — run standalone via doppler.

Usage:
  doppler run --project bei-erp --config dev -- python output/s191/baseline_audit.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import requests

PROJECT_ID = os.environ.get("SUPABASE_PROJECT_ID", "csnniykjrychgajfrgua")
TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
OUT_DIR = Path(__file__).parent
URL = f"https://api.supabase.com/v1/projects/{PROJECT_ID}/database/query"


def q(sql: str) -> list[dict]:
    if not TOKEN:
        raise SystemExit("SUPABASE_MGMT_TOKEN missing. Run via `doppler run -- python ...`.")
    r = requests.post(
        URL,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=120,
    )
    if r.status_code not in (200, 201):
        raise SystemExit(f"Supabase SQL failed ({r.status_code}): {r.text[:600]}")
    payload = r.json()
    if isinstance(payload, list):
        return payload
    return payload.get("result", []) or []


PER_STORE_DAY_SQL = """
WITH fp_mosaic AS (
    SELECT location_id, business_date,
           SUM(gross_sales)::numeric(14,2) AS mosaic_gross,
           SUM(net_sales)::numeric(14,2)   AS mosaic_net,
           COUNT(*)::int                    AS mosaic_orders
    FROM public.v_pos_orders_live
    WHERE channel = 'FoodPanda' AND payment_status = 'PAID'
      AND business_date BETWEEN '2026-02-01' AND '2026-04-30'
    GROUP BY location_id, business_date
),
fp_legacy AS (
    SELECT location_id, business_date,
           SUM(subtotal)::numeric(14,2)           AS legacy_gross,
           (SUM(subtotal)/1.12)::numeric(14,2)    AS legacy_net,
           COUNT(*)::int                           AS legacy_orders
    FROM public.foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
      AND business_date BETWEEN '2026-02-01' AND '2026-04-30'
    GROUP BY location_id, business_date
)
SELECT
    COALESCE(m.location_id, l.location_id)     AS location_id,
    COALESCE(m.business_date, l.business_date) AS business_date,
    COALESCE(m.mosaic_gross, 0)  AS mosaic_gross,
    COALESCE(m.mosaic_net, 0)    AS mosaic_net,
    COALESCE(m.mosaic_orders, 0) AS mosaic_orders,
    COALESCE(l.legacy_gross, 0)  AS legacy_gross,
    COALESCE(l.legacy_net, 0)    AS legacy_net,
    COALESCE(l.legacy_orders, 0) AS legacy_orders,
    CASE WHEN m.location_id IS NOT NULL AND l.location_id IS NOT NULL THEN 1 ELSE 0 END AS overlap
FROM fp_mosaic m
FULL OUTER JOIN fp_legacy l
    ON m.location_id = l.location_id AND m.business_date = l.business_date
ORDER BY location_id, business_date;
"""

DEDUP_SQL = """
SELECT COUNT(*) AS dupe_order_count
FROM (
    SELECT order_id
    FROM public.foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
      AND business_date BETWEEN '2026-02-01' AND '2026-03-31'
    GROUP BY order_id
    HAVING COUNT(*) > 1
) t;
"""

DEDUP_SAMPLE_SQL = """
SELECT order_id, COUNT(*) AS dupes
FROM public.foodpanda_orders
WHERE LOWER(order_status) = 'delivered'
  AND business_date BETWEEN '2026-02-01' AND '2026-03-31'
GROUP BY order_id
HAVING COUNT(*) > 1
LIMIT 20;
"""


def main() -> int:
    print(f"[S191 Phase 0] Project {PROJECT_ID}; token={'set' if TOKEN else 'MISSING'}")

    # 1. Per-(store, day) audit
    print("Running per-(store,day) audit SQL...")
    rows = q(PER_STORE_DAY_SQL)
    print(f"  rows: {len(rows)}")

    csv_path = OUT_DIR / "baseline_audit.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"  wrote {csv_path}")

    # Aggregates
    def to_f(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    total_legacy_gross = sum(to_f(r["legacy_gross"]) for r in rows)
    total_legacy_net = sum(to_f(r["legacy_net"]) for r in rows)
    total_mosaic_gross = sum(to_f(r["mosaic_gross"]) for r in rows)
    total_mosaic_net = sum(to_f(r["mosaic_net"]) for r in rows)
    total_legacy_orders = sum(int(r["legacy_orders"]) for r in rows)
    total_mosaic_orders = sum(int(r["mosaic_orders"]) for r in rows)

    # By month
    def month_key(r):
        d = str(r["business_date"])[:7]
        return d

    by_month: dict[str, dict] = {}
    for r in rows:
        mk = month_key(r)
        m = by_month.setdefault(
            mk,
            dict(
                legacy_gross=0.0,
                legacy_net=0.0,
                legacy_orders=0,
                mosaic_gross=0.0,
                mosaic_net=0.0,
                mosaic_orders=0,
            ),
        )
        m["legacy_gross"] += to_f(r["legacy_gross"])
        m["legacy_net"] += to_f(r["legacy_net"])
        m["legacy_orders"] += int(r["legacy_orders"])
        m["mosaic_gross"] += to_f(r["mosaic_gross"])
        m["mosaic_net"] += to_f(r["mosaic_net"])
        m["mosaic_orders"] += int(r["mosaic_orders"])

    # Overlap variance (absolute gross/net differences on overlap days)
    overlap_rows = [r for r in rows if int(r["overlap"]) == 1]
    overlap_gross_variance = sum(abs(to_f(r["mosaic_gross"]) - to_f(r["legacy_gross"])) for r in overlap_rows)
    overlap_net_variance = sum(abs(to_f(r["mosaic_net"]) - to_f(r["legacy_net"])) for r in overlap_rows)
    max_single_day_gross_variance = max(
        (abs(to_f(r["mosaic_gross"]) - to_f(r["legacy_gross"])) for r in overlap_rows), default=0.0
    )

    # Per-store first-mosaic-day / last-legacy-day
    per_store: dict[int, dict] = {}
    for r in rows:
        sid = int(r["location_id"])
        s = per_store.setdefault(sid, dict(first_mosaic=None, last_legacy=None))
        d = str(r["business_date"])
        if int(r["mosaic_orders"]) > 0:
            if s["first_mosaic"] is None or d < s["first_mosaic"]:
                s["first_mosaic"] = d
        if int(r["legacy_orders"]) > 0:
            if s["last_legacy"] is None or d > s["last_legacy"]:
                s["last_legacy"] = d
    total_stores = len(per_store)

    unified_gross_march = 0.0
    unified_net_march = 0.0
    unified_orders_march = 0
    for r in rows:
        if str(r["business_date"]).startswith("2026-03"):
            mg = to_f(r["mosaic_gross"])
            mn = to_f(r["mosaic_net"])
            mo = int(r["mosaic_orders"])
            lg = to_f(r["legacy_gross"])
            ln = to_f(r["legacy_net"])
            lo = int(r["legacy_orders"])
            # completeness-guard logic
            if mg == 0 and lg == 0 and mo == 0 and lo == 0:
                continue
            if mg == 0:
                g, n, o = lg, ln, lo
            elif lg == 0:
                g, n, o = mg, mn, mo
            elif mo >= 0.5 * lo or mg >= 0.5 * lg:
                g, n, o = mg, mn, mo
            else:
                g, n, o = lg, ln, lo
            unified_gross_march += g
            unified_net_march += n
            unified_orders_march += o

    # 2. Dedup check
    print("Running dedup check...")
    d_rows = q(DEDUP_SQL)
    dupes = int(d_rows[0]["dupe_order_count"]) if d_rows else 0
    sample = q(DEDUP_SAMPLE_SQL) if dupes else []

    dedup_path = OUT_DIR / "baseline_dedup_check.md"
    dedup_lines = [
        "# S191 Phase 0.4 — Legacy `foodpanda_orders` Dedup Check",
        "",
        f"- Duplicate `order_id` count (Feb 1 – Mar 31, delivered): **{dupes}**",
        "",
        f"- HARD BLOCKER 0-2 decision: **{'DISTINCT ON (order_id) required' if dupes > 10 else 'straight SUM allowed (no dedup needed)'}**",
        "",
    ]
    if sample:
        dedup_lines.append("## Sample duplicates (up to 20):")
        dedup_lines.append("")
        dedup_lines.append("| order_id | dupes |")
        dedup_lines.append("|---|---|")
        for s in sample:
            dedup_lines.append(f"| {s['order_id']} | {s['dupes']} |")
    dedup_path.write_text("\n".join(dedup_lines), encoding="utf-8")
    print(f"  wrote {dedup_path}")

    # 3. Summary
    summary_path = OUT_DIR / "BASELINE_SUMMARY.md"
    summary = [
        "# S191 Phase 0 — Baseline Summary",
        "",
        "## Verified totals by month",
        "",
        "| Month | Legacy gross | Legacy net | Legacy orders | Mosaic gross | Mosaic net | Mosaic orders |",
        "|---|---|---|---|---|---|---|",
    ]
    for mk in sorted(by_month):
        m = by_month[mk]
        summary.append(
            f"| {mk} | ₱{m['legacy_gross']:,.2f} | ₱{m['legacy_net']:,.2f} | {m['legacy_orders']:,} | "
            f"₱{m['mosaic_gross']:,.2f} | ₱{m['mosaic_net']:,.2f} | {m['mosaic_orders']:,} |"
        )
    summary += [
        "",
        "## Aggregate metrics",
        "",
        f"- Total stores in audit: **{total_stores}**",
        f"- Total overlap (store,day) rows: **{len(overlap_rows)}**",
        f"- Total GROSS overlap variance (Σ|mosaic-legacy| on overlap days): **₱{overlap_gross_variance:,.2f}**",
        f"- Total NET overlap variance: **₱{overlap_net_variance:,.2f}**",
        f"- Max single (store,day) GROSS variance: **₱{max_single_day_gross_variance:,.2f}**",
        f"- Unified March 2026 GROSS (completeness-guard applied): **₱{unified_gross_march:,.2f}**",
        f"- Unified March 2026 NET: **₱{unified_net_march:,.2f}**",
        f"- Unified March 2026 orders: **{unified_orders_march:,}**",
        "",
        "## HARD BLOCKER 0-1 decision",
        "",
        f"- March unified GROSS ≥ ₱20M? **{'PASS' if unified_gross_march >= 20_000_000 else 'FAIL'}** (₱{unified_gross_march:,.0f})",
        f"- Overlap GROSS variance ≤ ₱2M total? **{'PASS' if overlap_gross_variance <= 2_000_000 else 'FAIL'}** (₱{overlap_gross_variance:,.0f})",
        f"- Max single-day GROSS variance ≤ ₱150K? **{'PASS' if max_single_day_gross_variance <= 150_000 else 'FAIL'}** (₱{max_single_day_gross_variance:,.0f})",
        f"- Dedup check resolved? **{'PASS (0 dupes — straight SUM)' if dupes == 0 else ('PASS (' + str(dupes) + ' dupes — DISTINCT ON required)' if dupes <= 10 else 'FAIL — >10 dupes; SQL MUST use DISTINCT ON (order_id)')}**",
        "",
        "## Per-store transition pattern (first Mosaic day / last legacy day)",
        "",
        "| location_id | first_mosaic | last_legacy |",
        "|---|---|---|",
    ]
    for sid in sorted(per_store):
        s = per_store[sid]
        summary.append(f"| {sid} | {s['first_mosaic'] or '—'} | {s['last_legacy'] or '—'} |")
    summary_path.write_text("\n".join(summary), encoding="utf-8")
    print(f"  wrote {summary_path}")

    # Write a machine-readable stamp
    (OUT_DIR / "baseline_metrics.json").write_text(
        json.dumps(
            dict(
                total_stores=total_stores,
                overlap_rows=len(overlap_rows),
                overlap_gross_variance=overlap_gross_variance,
                overlap_net_variance=overlap_net_variance,
                max_single_day_gross_variance=max_single_day_gross_variance,
                unified_gross_march=unified_gross_march,
                unified_net_march=unified_net_march,
                unified_orders_march=unified_orders_march,
                legacy_orders_total=total_legacy_orders,
                mosaic_orders_total=total_mosaic_orders,
                dupes=dupes,
                by_month=by_month,
            ),
            default=str,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
