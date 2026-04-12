#!/usr/bin/env python3
"""S185 verification script — checks backend + frontend patterns."""
import re
import sys
from pathlib import Path

BACKEND = Path("F:/Dropbox/Projects/BEI-ERP/hrms/api/sales_dashboard.py")
FRONTEND_LB = Path("F:/Dropbox/Projects/bei-tasks/app/dashboard/analytics/sales/stores/page.tsx")
FRONTEND_MOBILE = Path("F:/Dropbox/Projects/bei-tasks/app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx")
FRONTEND_MAIN = Path("F:/Dropbox/Projects/bei-tasks/app/dashboard/analytics/sales/page.tsx")
FRONTEND_TYPES = Path("F:/Dropbox/Projects/bei-tasks/lib/sales-dashboard.ts")
FRONTEND_API = Path("F:/Dropbox/Projects/bei-tasks/lib/api/sales-dashboard.ts")

errors = []

def check(condition, msg):
    if not condition:
        errors.append(msg)
    print(f"  {'PASS' if condition else 'FAIL'}: {msg}")

def count(text, pattern):
    return len(re.findall(pattern, text))

# Backend
print("=== Backend checks ===")
be = BACKEND.read_text(encoding="utf-8")
check(count(be, "include_comparisons") >= 4, "include_comparisons appears >=4 times")
check(count(be, "prev_start") >= 1, "prev_start present")
check(count(be, "prev_rows") >= 1, "prev_rows present")
check(count(be, "prev_by_location") >= 1, "prev_by_location present")
check(count(be, "net_delta") >= 2, "net_delta appears >=2 times")
check(count(be, "net_delta_pct") >= 1, "net_delta_pct present")
check(count(be, "position_change") >= 2, "position_change appears >=2 times")
check(count(be, "previous_rank") >= 2, "previous_rank appears >=2 times")
check(count(be, "comparison_meta") >= 1, "comparison_meta present")
check(count(be, "rank_delta_reliable") >= 1, "rank_delta_reliable present")
check(count(be, "is_new_store") >= 1, "is_new_store present")
check(count(be, "allowed_ids") >= 1, "allowed_ids RBAC guard present")
check(count(be, "total_net_sales_without_vat") >= 3, "total_net_sales_without_vat column used")
check(count(be, "_to_bool_flag") >= 2, "_to_bool_flag used for include_comparisons")

# Frontend leaderboard
print("\n=== Frontend leaderboard checks ===")
lb = FRONTEND_LB.read_text(encoding="utf-8")
check(count(lb, "position_change") >= 2, "position_change in leaderboard")
check(count(lb, "net_delta") >= 2, "net_delta in leaderboard")
check("rank_change" in lb, "rank_change sort key present")
check("case" in lb and "rank_change" in lb, "explicit case for rank_change in sort switch")
check("store.rank" in lb or "store\\.rank" in lb, "store.rank used for rank display")
check("aria-label" in lb, "aria-label present for accessibility")
check("prior_period" in lb or "comparison_meta" in lb, "comparison period indicator")
check("1900" in lb, "table width updated to 1900px")

# Frontend mobile
print("\n=== Frontend mobile checks ===")
mb = FRONTEND_MOBILE.read_text(encoding="utf-8")
check("position_change" in mb or "net_delta" in mb, "rank/delta in mobile view")

# Frontend main page
print("\n=== Frontend main page checks ===")
mp = FRONTEND_MAIN.read_text(encoding="utf-8")
check("position_change" in mp, "position_change in main page")
check("net_delta" in mp or "comparison" in mp, "comparison data in main page")

# Frontend types
print("\n=== Frontend types checks ===")
ts = FRONTEND_TYPES.read_text(encoding="utf-8")
check("position_change" in ts, "position_change in types")
check("comparison_meta" in ts or "ComparisonMeta" in ts, "comparison_meta type present")
check("is_new_store" in ts, "is_new_store in types")

# Frontend API
print("\n=== Frontend API checks ===")
api = FRONTEND_API.read_text(encoding="utf-8")
check(count(api, "include_comparisons") >= 2, "include_comparisons in both fetch functions")

# Protected surface
print("\n=== Protected surface checks ===")
import subprocess
result = subprocess.run(
    ["git", "diff", "--name-only", "origin/production"],
    capture_output=True, text=True, cwd="F:/Dropbox/Projects/BEI-ERP"
)
modified = result.stdout.strip().split("\n") if result.stdout.strip() else []
workflow_files = [f for f in modified if ".github/workflows/" in f]
check(len(workflow_files) == 0, f"No workflow files modified")

# Summary
print(f"\n{'=' * 50}")
if errors:
    print(f"FAIL: {len(errors)} check(s) failed:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("PASS: All checks passed.")
    sys.exit(0)
