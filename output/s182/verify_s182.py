#!/usr/bin/env python3
"""S182 verification script — checks filesystem, not agent self-report. v3."""
import subprocess
import sys
import pathlib

BEITASKS = pathlib.Path(r"F:/Dropbox/Projects/bei-tasks")
HRMS = pathlib.Path(r"F:/Dropbox/Projects/BEI-ERP")
FAILS: list[str] = []


def file_contains(repo: pathlib.Path, path: str, pattern: str) -> bool:
    p = repo / path
    if not p.exists():
        return False
    return pattern in p.read_text(encoding="utf-8", errors="ignore")


def file_not_contains(repo: pathlib.Path, path: str, pattern: str) -> bool:
    p = repo / path
    if not p.exists():
        return False
    return pattern not in p.read_text(encoding="utf-8", errors="ignore")


def assert_contains(repo, path, pattern, task):
    if not file_contains(repo, path, pattern):
        FAILS.append(f"{task}: {pattern!r} not found in {path}")


def assert_not_contains(repo, path, pattern, task):
    if not file_not_contains(repo, path, pattern):
        FAILS.append(f"{task}: {pattern!r} MUST NOT appear in {path} but does")


# Phase 0 — baseline + MV column verification
for f in ("BASELINE.md", "mv_column_verification.md"):
    if not (HRMS / "output" / "s182" / f).exists():
        FAILS.append(f"Phase 0: {f} missing")

# Phase B — Backend
hrms_file = "hrms/api/sales_dashboard.py"
for pat, task in [
    ("_get_store_channel_split_map", "Phase B.3"),
    ("_get_store_website_split_map", "Phase B.4"),
    ("channel_mix", "Phase B.6"),
    ("daily_series", "Phase B.7"),
    ("pickup_share", "Phase B.6"),
    ('set_backend_observability_context(\n\t\tmodule="sales",\n\t\taction="get_sales_dashboard_store_rankings"', "Phase B.8"),
    ("channel_mix.values()", "Phase B.9"),
]:
    assert_contains(HRMS, hrms_file, pat, task)

# Phase B — frontend type extension
ts = "lib/sales-dashboard.ts"
for pat, task in [
    ("channel_mix?:", "Phase B.0 (TS extension)"),
    ("daily_series?:", "Phase B.0 (TS extension)"),
    ("pickup_share?:", "Phase B.0 (TS extension)"),
]:
    assert_contains(BEITASKS, ts, pat, task)

# Phase 1 — Top-8 grid + formatters
for pat, task in [
    ("lg:grid-cols-4", "Phase 1.1"),
    ("handleStoreClick", "Phase 1.2"),
    ("aria-label", "Phase 1.4"),
]:
    assert_contains(BEITASKS, "app/dashboard/analytics/sales/page.tsx", pat, task)

formatters = "app/dashboard/analytics/sales/_formatters.ts"
if not (BEITASKS / formatters).exists():
    FAILS.append(f"Phase 1.0: {formatters} missing")

# Phase 2 — Ranking table
page = "app/dashboard/analytics/sales/page.tsx"
for pat, task in [
    ("sortKey", "Phase 2.1"),
    ("sortedStores", "Phase 2.2"),
    ("maxRowNet", "Phase 2.3"),
    ("toggleSort", "Phase 2.4"),
    ("aria-sort", "Phase 2.4"),
    ("Gross", "Phase 2.5"),
    ("Pickup %", "Phase 2.5"),
    ("Disruptive Days", "Phase 2.5"),
    ("bg-primary/10", "Phase 2.6"),
    ("closest", "Phase 2.7"),
    ("data-stop", "Phase 2.7"),
    ("onKeyDown", "Phase 2.7"),
    ("text-primary hover:underline", "Phase 2.8"),
]:
    assert_contains(BEITASKS, page, pat, task)

# Phase 3 — Reset pill + breadcrumb + useCallback + selectedStoreName
for pat, task in [
    ("useCallback", "Phase 3.1"),
    ("selectedStoreName", "Phase 3.2"),
    ("scrollTo", "Phase 3.1"),
    ("Viewing:", "Phase 3.3"),
    ("All stores", "Phase 3.3"),
    ("aria-live", "Phase 3.3"),
    ("Breadcrumb", "Phase 3.4"),
]:
    assert_contains(BEITASKS, page, pat, task)

# Phase 4 — Dialog
dialog = "app/dashboard/analytics/sales/store-detail-dialog.tsx"
if not (BEITASKS / dialog).exists():
    FAILS.append(f"Phase 4.1: {dialog} does not exist")
else:
    for pat, task in [
        ('"use client"', "Phase 4.1"),
        ("export function StoreDetailDialog", "Phase 4.2"),
        ("SalesDashboardStoreRanking", "Phase 4.2"),
        ("sm:max-w-[1200px] max-h-[90vh]", "Phase 4.3"),
        ("fetchSalesOverview", "Phase 4.4"),
        ("stores: [store.warehouse]", "Phase 4.4"),
        ("<Skeleton", "Phase 4.5"),
        ("destructive", "Phase 4.6"),
        ("Retry", "Phase 4.6"),
        ("Net w/o VAT", "Phase 4.7"),
        ("Channel Mix", "Phase 4.7"),
        ("Daily Signals", "Phase 4.7"),
        ("No sales in this date range", "Phase 4.7a"),
        ("Open Full View", "Phase 4.8"),
        ("store.location_id", "Phase 4.8"),
        ("DialogTitle", "Phase 4.9"),
        ("Store Detail", "Phase 4.9"),
    ]:
        assert_contains(BEITASKS, dialog, pat, task)
    # MUST NOT contain StoreLeader (wrong type name)
    assert_not_contains(BEITASKS, dialog, "StoreLeader", "Phase 4.2 (wrong type name)")

# Phase 4.3a — fetch wrapper
api_helper = "lib/api/sales-dashboard.ts"
if not (BEITASKS / api_helper).exists():
    FAILS.append(f"Phase 4.3a: {api_helper} missing")
else:
    assert_contains(BEITASKS, api_helper, "fetchSalesOverview", "Phase 4.3a")
assert_contains(BEITASKS, page, "fetchSalesOverview", "Phase 4.3a (page uses shared helper)")

# Phase 5 — Dialog wiring
for pat, task in [
    ("detailStore", "Phase 5.1"),
    ("<StoreDetailDialog", "Phase 5.3"),
]:
    assert_contains(BEITASKS, page, pat, task)

# Phase 6 — Leaderboard
leaderboard = "app/dashboard/analytics/sales/stores/page.tsx"
if not (BEITASKS / leaderboard).exists():
    FAILS.append(f"Phase 6.1: {leaderboard} does not exist")
else:
    for pat, task in [
        ('"use client"', "Phase 6.1"),
        ("force-dynamic", "Phase 6.2"),
        ("Breadcrumb", "Phase 6.4"),
        ("Search stores", "Phase 6.5"),
        ("Comfortable", "Phase 6.6"),
        ("Compact", "Phase 6.6"),
        ("toCsv", "Phase 6.7"),
        ("store-leaderboard-", "Phase 6.7"),
        ("POS", "Phase 6.8"),
        ("GrabFood", "Phase 6.8"),
        ("FoodPanda", "Phase 6.8"),
        ("daily_series", "Phase 6.8/6.12"),
        ("sticky left-0", "Phase 6.9"),
        ("pointer-events-none absolute", "Phase 6.10"),
        ("bg-primary/10", "Phase 6.11"),
        ("polyline", "Phase 6.12"),
        ("bg-emerald-500", "Phase 6.13"),
        ("bg-rose-500", "Phase 6.13"),
        ("toggleSort", "Phase 6.14"),
        ("aria-sort", "Phase 6.14"),
        ("<Skeleton", "Phase 6.15"),
        ("destructive", "Phase 6.15a"),
        ("No stores accessible", "Phase 6.16"),
        ("md:hidden", "Phase 6.17"),
        ("hidden md:block", "Phase 6.17"),
        ("StoreDetailDialog", "Phase 6.18"),
        ("/dashboard/analytics/sales", "Phase 6.19"),
    ]:
        assert_contains(BEITASKS, leaderboard, pat, task)
    # MUST NOT use ToggleGroup (not installed)
    assert_not_contains(BEITASKS, leaderboard, "ToggleGroup", "Phase 6.6 (forbidden component)")
    # MUST NOT use useMediaQuery (hook does not exist)
    assert_not_contains(BEITASKS, leaderboard, "useMediaQuery", "Phase 6.17 (forbidden hook)")

# Phase 6 — Mobile fallback
mobile = "app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx"
if not (BEITASKS / mobile).exists():
    FAILS.append(f"Phase 6.17: {mobile} does not exist")

# Phase 7 — Dynamic route
dyn = "app/dashboard/analytics/sales/stores/[locationId]/page.tsx"
if not (BEITASKS / dyn).exists():
    FAILS.append(f"Phase 7.1: {dyn} does not exist")
else:
    for pat, task in [
        ('"use client"', "Phase 7.1"),
        ("useParams", "Phase 7.2"),
        ("useSearchParams", "Phase 7.2"),
        ("Number(params", "Phase 7.3"),
        ("Number.isNaN", "Phase 7.3"),
        ("get_sales_dashboard_access_context", "Phase 7.3"),
        ("Store not found", "Phase 7.4"),
        ("fetchSalesOverview", "Phase 7.5"),
        ("destructive", "Phase 7.5a"),
        ("Breadcrumb", "Phase 7.6"),
        ("DateRangePicker", "Phase 7.7"),
        ("<Skeleton", "Phase 7.8"),
        ("force-dynamic", "Phase 7.9"),
    ]:
        assert_contains(BEITASKS, dyn, pat, task)
    # MUST NOT reference the wrong API name
    assert_not_contains(BEITASKS, dyn, 'get_dashboard_access"', "Phase 7.3 (wrong API name)")

# Phase 8 — Buttons
assert_contains(BEITASKS, page, "Open Full Leaderboard", "Phase 8.1")

# Phase B — backend timing artifact
timing = HRMS / "output" / "s182" / "backend_timing.md"
if not timing.exists():
    FAILS.append("Phase B.10: backend_timing.md missing")

# Protected surface check — no workflow file modified
result = subprocess.run(
    ["git", "-C", str(HRMS), "diff", "--name-only", "origin/production"],
    capture_output=True,
    text=True,
)
changed = result.stdout.strip().split("\n") if result.stdout.strip() else []
for f in changed:
    if f.startswith(".github/workflows/"):
        FAILS.append(f"Protected-surface violation: {f} must not be modified")

if FAILS:
    print("VERIFY: FAIL")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("VERIFY: PASS (all S182 assertions green except L3 evidence which runs in fresh session)")
    sys.exit(0)
