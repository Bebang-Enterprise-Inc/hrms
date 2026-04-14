"""S191 post-deploy validation — hit hq.bebang.ph endpoints and compare to baseline.

Usage:
  doppler run --project bei-erp --config dev -- python output/s191/validate_post_deploy.py
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph").rstrip("/")
KEY = os.environ.get("FRAPPE_API_KEY", "")
SECRET = os.environ.get("FRAPPE_API_SECRET", "")
OUT = Path(__file__).parent

if not KEY or not SECRET:
    raise SystemExit("FRAPPE_API_KEY / FRAPPE_API_SECRET missing. Run via doppler.")

AUTH = {"Authorization": f"token {KEY}:{SECRET}"}


def call(method: str, params: dict) -> dict:
    r = requests.get(f"{BASE}/api/method/{method}", headers=AUTH, params=params, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"{method} HTTP {r.status_code}: {r.text[:600]}")
    return r.json().get("message") or {}


def main() -> int:
    baseline = json.loads((OUT / "baseline_metrics.json").read_text(encoding="utf-8"))
    print(f"Base URL: {BASE}")
    print(f"Baseline march unified NET: ₱{baseline['unified_net_march']:,.0f}")
    print(f"Baseline march unified ORDERS: {baseline['unified_orders_march']:,}")
    print(f"Baseline feb legacy NET (approx): ₱{baseline['by_month']['2026-02']['legacy_net']:,.0f}")
    print()

    results = {}
    gates = []

    # Scenario 1: March 2026 FP ≥ ₱18M net, orders ≥ 30K
    print("== L3-191-01/02: March 2026 ==")
    mar = call(
        "hrms.api.sales_dashboard.get_sales_dashboard_overview",
        {"start_date": "2026-03-01", "end_date": "2026-03-31"},
    )
    s = mar.get("summary") or {}
    fp_net = float(s.get("foodpanda_sales_without_vat") or 0)
    fp_gross = float(s.get("foodpanda_sales") or 0)
    fp_orders = int(s.get("foodpanda_orders") or 0)
    gf_net = float(s.get("grabfood_sales_without_vat") or 0)
    pos_net = float(s.get("pickup_sales_without_vat") or 0)
    print(f"  foodpanda_sales_without_vat: ₱{fp_net:,.2f}")
    print(f"  foodpanda_sales (gross)    : ₱{fp_gross:,.2f}")
    print(f"  foodpanda_orders           : {fp_orders:,}")
    print(f"  grabfood_sales_without_vat : ₱{gf_net:,.2f}  (anti-regression)")
    print(f"  pickup_sales_without_vat   : ₱{pos_net:,.2f} (anti-regression)")
    results["march_2026"] = dict(
        fp_net=fp_net, fp_gross=fp_gross, fp_orders=fp_orders, gf_net=gf_net, pos_net=pos_net
    )
    gates.append(("L3-191-01 March FP net ≥ ₱18M", fp_net >= 18_000_000, fp_net))
    gates.append(("L3-191-02 March FP orders ≥ 30,000", fp_orders >= 30_000, fp_orders))

    # Scenario 3: Feb 2026 FP ≥ ₱8M net
    print()
    print("== L3-191-03: Feb 2026 ==")
    feb = call(
        "hrms.api.sales_dashboard.get_sales_dashboard_overview",
        {"start_date": "2026-02-01", "end_date": "2026-02-28"},
    )
    sf = feb.get("summary") or {}
    feb_fp_net = float(sf.get("foodpanda_sales_without_vat") or 0)
    feb_fp_orders = int(sf.get("foodpanda_orders") or 0)
    print(f"  foodpanda_sales_without_vat: ₱{feb_fp_net:,.2f}")
    print(f"  foodpanda_orders           : {feb_fp_orders:,}")
    results["feb_2026"] = dict(fp_net=feb_fp_net, fp_orders=feb_fp_orders)
    gates.append(("L3-191-03 Feb FP net ≥ ₱8M", feb_fp_net >= 8_000_000, feb_fp_net))

    # Scenario 4: Apr 1–12 (Mosaic-only window; legacy frozen)
    print()
    print("== L3-191-04: Apr 1–12 2026 (Mosaic-only) ==")
    apr = call(
        "hrms.api.sales_dashboard.get_sales_dashboard_overview",
        {"start_date": "2026-04-01", "end_date": "2026-04-12"},
    )
    sa = apr.get("summary") or {}
    apr_fp_net = float(sa.get("foodpanda_sales_without_vat") or 0)
    print(f"  foodpanda_sales_without_vat: ₱{apr_fp_net:,.2f}")
    results["apr_2026"] = dict(fp_net=apr_fp_net)
    # Apr should be ~Mosaic-only net (~₱3.5M for 12 days of ~₱9.5M/month)
    gates.append(("L3-191-04 Apr FP net between ₱1M and ₱12M (Mosaic-only band)", 1_000_000 <= apr_fp_net <= 12_000_000, apr_fp_net))

    # Scenario 9: GrabFood unchanged — should still be ₱0 for March
    gates.append(("L3-191-09 March GrabFood net ≈ ₱0 (unchanged)", gf_net < 100_000, gf_net))

    # Comparison panel — Feb baseline should show unified ~₱8M (not ₱0)
    print()
    print("== L3-191-14: Comparison panel (March request) ==")
    comp = mar.get("comparisons") or {}
    prev = comp.get("previous_period") or {}
    prev_fp_baseline = float(prev.get("baseline_gross_sales") or 0)
    # Note: comparison payload exposes gross_sales baseline, not FP-specific.
    # We check that a March request with include_comparisons=true has non-null previous_period.
    prev_available = bool(prev.get("available"))
    print(f"  previous_period.available      : {prev_available}")
    print(f"  previous_period baseline_gross : ₱{prev_fp_baseline:,.2f}")
    results["comparisons_march"] = dict(available=prev_available, baseline_gross=prev_fp_baseline)
    gates.append(("L3-191-14 comparison previous_period available", prev_available, prev_available))

    # Write full dump
    (OUT / "validate_post_deploy_result.json").write_text(
        json.dumps({"results": results, "gates": [(n, bool(ok), v) for n, ok, v in gates]}, default=str, indent=2),
        encoding="utf-8",
    )

    # Print gate summary
    print()
    print("== GATE RESULTS ==")
    fails = 0
    for name, ok, val in gates:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name} (value={val})")
        if not ok:
            fails += 1
    print()
    if fails:
        print(f"{fails} gate(s) FAIL")
        return 1
    print(f"All {len(gates)} gates PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
