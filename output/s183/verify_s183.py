#!/usr/bin/env python3
"""S183 verification script — checks backend + frontend patterns."""
import re
import sys
from pathlib import Path

BACKEND = Path("F:/Dropbox/Projects/BEI-ERP/hrms/api/sales_dashboard.py")
FRONTEND = Path("F:/Dropbox/Projects/bei-tasks/app/dashboard/analytics/product/page.tsx")

errors: list[str] = []


def check(condition: bool, msg: str):
    if not condition:
        errors.append(msg)
    print(f"  {'PASS' if condition else 'FAIL'}: {msg}")


def count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


# ── Backend checks ──────────────────────────────────────────────────────

print("=== Backend checks ===")
be = BACKEND.read_text(encoding="utf-8")

check(count(be, "daily_series") >= 2, "daily_series appears >=2 times")
check(count(be, "fleet_rank") >= 2, "fleet_rank appears >=2 times")
check(count(be, "fleet_product_map") >= 2, "fleet_product_map appears >=2 times")
check(count(be, "allowed_location_ids") >= 2, "allowed_location_ids appears >=2 times (B-2)")
check(count(be, "trend_slope") >= 2, "trend_slope appears >=2 times")
check(count(be, "trend_label") >= 2, "trend_label appears >=2 times")
check(count(be, "contribution_pct") >= 1, "contribution_pct appears >=1 time")
check(count(be, "wow_delta") >= 2, "wow_delta appears >=2 times")
check(count(be, "assortment_gap") >= 2, "assortment_gap appears >=2 times")
check(count(be, "per_store_breakdown") >= 2, "per_store_breakdown appears >=2 times")
check(count(be, "is_single_store") >= 1, "is_single_store appears >=1 time")
check(count(be, "drop_candidate") >= 1, "drop_candidate appears >=1 time")
check(count(be, "denominator > 0") >= 1, "denominator > 0 guard present (B-3)")
check(count(be, "_supabase_query_sql") >= 2, "_supabase_query_sql used in fleet query (B-1)")
check(count(be, "_cache_get_or_set") >= 2, "_cache_get_or_set used for fleet caching (B-1)")
check("velocity" in be, "velocity field present")

# ── Frontend checks ─────────────────────────────────────────────────────

print("\n=== Frontend checks ===")
fe = FRONTEND.read_text(encoding="utf-8")

check(count(fe, "selectedStore") >= 2, "selectedStore state present")
check("selectedStore.warehouse" in fe or "selectedStore?.warehouse" in fe, "selectedStore.warehouse used (B-5)")
check(count(fe, "sortMode") >= 2, "sortMode state present (B-4)")
check(count(fe, "polyline") >= 1, "Sparkline polyline present")
check("bg-emerald" in fe, "bg-emerald signal color present")
check("bg-rose" in fe, "bg-rose signal color present")
check("cups/day" in fe, "cups/day velocity label present")
check("fleet_rank" in fe or "Fleet Rank" in fe or "FleetRank" in fe, "fleet_rank present")
check("wow_delta" in fe or "WoW Delta" in fe, "wow_delta present")
check("contribution" in fe, "contribution present")
check("Signal Summary" in fe or "signal-summary" in fe, "Signal Summary tile present")
check("assortment" in fe.lower() or "Assortment" in fe, "Assortment gap present")
check(count(fe, "expandedProduct") >= 2, "expandedProduct state for drill-down")
check(count(fe, "per_store_breakdown") >= 1, "per_store_breakdown present")
check("Not sold here" in fe, "Not sold here badge present")
check(count(fe, "showGapProducts") >= 2, "showGapProducts toggle state")
check("access-context" in fe, "access-context endpoint called")

# ── Protected surface checks ────────────────────────────────────────────

print("\n=== Protected surface checks ===")
check("ToggleGroup" not in fe, "No ToggleGroup (not installed)")
check("useMediaQuery" not in fe, "No useMediaQuery (doesn't exist)")

# Verify no workflow files modified
import subprocess
result = subprocess.run(
    ["git", "diff", "--name-only", "origin/production"],
    capture_output=True, text=True, cwd="F:/Dropbox/Projects/BEI-ERP"
)
modified = result.stdout.strip().split("\n") if result.stdout.strip() else []
workflow_files = [f for f in modified if ".github/workflows/" in f]
check(len(workflow_files) == 0, f"No workflow files modified (found: {workflow_files})")

# ── Summary ─────────────────────────────────────────────────────────────

print(f"\n{'=' * 50}")
if errors:
    print(f"FAIL: {len(errors)} check(s) failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("PASS: All checks passed.")
    sys.exit(0)
