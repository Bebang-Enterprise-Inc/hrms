"""S191 Phase 4.1 — verification script.

Runs grep + AST assertions against `hrms/api/sales_dashboard.py`. Exits 0 on pass,
non-zero with a failure summary on any assertion miss. Safe to run locally or in
CI before PR creation.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import io
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FILE = Path(__file__).resolve().parents[2] / "hrms" / "api" / "sales_dashboard.py"


def count(pattern: str) -> int:
    src = FILE.read_text(encoding="utf-8")
    return sum(1 for line in src.splitlines() if pattern in line)


def count_regex(pattern: str) -> int:
    src = FILE.read_text(encoding="utf-8")
    rx = re.compile(pattern)
    return sum(1 for line in src.splitlines() if rx.search(line))


def main() -> int:
    failures: list[str] = []

    def assert_eq(name: str, got: int, want: int) -> None:
        status = "OK" if got == want else "FAIL"
        line = f"[{status}] {name}: got={got} want={want}"
        print(line)
        if got != want:
            failures.append(line)

    def assert_ge(name: str, got: int, want: int) -> None:
        status = "OK" if got >= want else "FAIL"
        line = f"[{status}] {name}: got={got} want>={want}"
        print(line)
        if got < want:
            failures.append(line)

    # (a) Task 2.1: fp_bucket = split.pop pattern is GONE
    assert_eq("a. fp_bucket = split.pop count", count("fp_bucket = split.pop"), 0)
    # (b) Task 2.1: fp_bucket = fp_unified present
    assert_eq("b. fp_bucket = fp_unified count", count("fp_bucket = fp_unified"), 1)
    # (c) Task 1.1: cache prefix fp_unified_v2
    assert_ge("c. fp_unified_v2 cache prefix", count("fp_unified_v2"), 1)
    # (d) Task 2.5: outer cache prefix bumps
    assert_ge("d.1 overview_s191 outer cache prefix", count("overview_s191"), 1)
    assert_ge("d.2 summary_s191 outer cache prefix", count("summary_s191"), 1)
    # (e) Task 1.2: PostgREST fallback uses ilike.delivered
    assert_ge("e. ilike.delivered (PostgREST fallback)", count("ilike.delivered"), 1)
    # (f) Task 1.1: completeness guard marker
    assert_ge("f. legacy_partial_mosaic marker", count("legacy_partial_mosaic"), 1)
    # (g) Tasks 3.2/3.5/3.7 + helpers: _get_unified_foodpanda_totals called ≥ 4 times
    assert_ge("g. _get_unified_foodpanda_totals call count", count("_get_unified_foodpanda_totals"), 4)
    # (h) Phase 2.1 + Task 3.8: _get_unified_foodpanda_totals_aggregate ≥ 2
    assert_ge(
        "h. _get_unified_foodpanda_totals_aggregate count",
        count("_get_unified_foodpanda_totals_aggregate"),
        2,
    )
    # (i) Task 3.6: foodpanda_vat_deducted_sales REDUCED by 1 vs baseline (baseline=6 → expected=5)
    assert_eq(
        "i. foodpanda_vat_deducted_sales count (baseline 6 minus 1)",
        count("foodpanda_vat_deducted_sales"),
        5,
    )
    # (j) Sentry baseline unchanged
    assert_eq("j. set_backend_observability_context count", count("set_backend_observability_context"), 5)
    # (k) GrabFood anti-regression: count equals pre-S191 baseline of 28
    assert_eq("k. grabfood count (anti-regression)", count("grabfood"), 28)

    # Task 3.8: _rebase_fp_to_unified defined + called twice
    assert_ge("x.1 _rebase_fp_to_unified count (def + 2 calls)", count("_rebase_fp_to_unified"), 3)

    # Sanity: Python AST parses
    try:
        ast.parse(FILE.read_text(encoding="utf-8"))
        print("[OK] AST parse")
    except SyntaxError as exc:
        print(f"[FAIL] AST parse: {exc}")
        failures.append(f"AST parse: {exc}")

    # Protected surfaces: no workflow or bei-tasks file modified on this branch
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/production...HEAD"],
            cwd=FILE.resolve().parents[2],
            text=True,
        ).strip().splitlines()
    except Exception:
        diff = []
    bad = [f for f in diff if f.startswith(".github/workflows/") or f.startswith("bei-tasks/")]
    if bad:
        msg = f"[FAIL] Protected surfaces touched: {bad}"
        print(msg)
        failures.append(msg)
    else:
        print("[OK] Protected surfaces clean")

    print()
    if failures:
        print(f"FAILURES: {len(failures)}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All assertions PASS")
    return 0


# POST-DEPLOY DATA PROBE (commented — run manually against staged endpoint):
#
#   curl -s "https://hq.bebang.ph/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview" \
#       -H "Authorization: token <token>" \
#       -G --data-urlencode "start_date=2026-03-01" --data-urlencode "end_date=2026-03-31" \
#     | jq '.message.summary.foodpanda_sales_without_vat, .message.summary.foodpanda_orders'
#   # Expect foodpanda_sales_without_vat ≥ 18000000; foodpanda_orders ≥ 30000


if __name__ == "__main__":
    sys.exit(main())
