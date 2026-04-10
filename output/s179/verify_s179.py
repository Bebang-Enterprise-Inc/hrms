"""S179 verification script — all MUST_CONTAIN / MUST_EXIST assertions."""
import subprocess, sys, os

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

print("\n==================== S179 VERIFICATION ====================\n")

# Phase 1: skipped (hotfix #6 already merged)
sd = open("hrms/api/sales_dashboard.py", encoding="utf-8").read()
check("P1: _get_channel_cups_from_mosaic exists", "_get_channel_cups_from_mosaic" in sd)
check("P1: foodpanda_cups in cups helper", "foodpanda_cups" in sd)
check("P1: grabfood_cups in cups helper", "grabfood_cups" in sd)

# Phase 2: MV + indexes + RPC (verified at creation time, check DDL file)
check("P2: supabase_ddl.sql exists", os.path.exists("output/s179/supabase_ddl.sql"))
check("P2: mv_initial_refresh.md exists", os.path.exists("output/s179/mv_initial_refresh.md"))

# Phase 3: GHA workflow
gha = open(".github/workflows/daily-pos-sync.yml", encoding="utf-8").read()
check("P3: refresh_product_channel_daily_mix in GHA", "refresh_product_channel_daily_mix" in gha)
check("P3: continue-on-error for MV refresh", "continue-on-error: true" in gha)

# Phase 4: API endpoint
check("P4: get_product_mix_analytics defined", "def get_product_mix_analytics" in sd)
check("P4: @frappe.whitelist before endpoint", '@frappe.whitelist()' in sd)
check("P4: Sentry context with action", 'action="get_product_mix_analytics"' in sd)
check("P4: api_response_sample.json exists", os.path.exists("output/s179/api_response_sample.json"))

# Phase 5: Frontend
page_path = "../bei-tasks/app/dashboard/analytics/product/page.tsx"
if os.path.exists(page_path):
    page = open(page_path, encoding="utf-8").read()
    check("P5: Product Analytics title", "Product Analytics" in page)
    check("P5: No ComingSoonAnalyticsShell", "ComingSoonAnalyticsShell" not in page)
    check("P5: Product Name column", "Product Name" in page)
    check("P5: Cups column", "Cups" in page)
    check("P5: Avg Price column", "Avg Price" in page)
    check("P5: Store Coverage column", "Store Coverage" in page)
    check("P5: FoodPanda tab", "FoodPanda" in page)
    check("P5: GrabFood tab", "GrabFood" in page)
    check("P5: Sort handler", "handleSort" in page or "sortBy" in page)
    check("P5: DateRangePicker", "DateRangePicker" in page)
    check("P5: fromDate prop", "fromDate" in page)
    check("P5: Total Products KPI", "Total Products" in page)
    check("P5: Total Cups KPI", "Total Cups" in page)
    check("P5: Export button", "Export" in page)
    check("P5: CSV download", ".csv" in page or "text/csv" in page)
    check("P5: Empty state", "No product data available" in page)
    check("P5: Skeleton loading", "Skeleton" in page or "skeleton" in page)
    check("P5: Error destructive", "destructive" in page)
    check("P5: Retry button", "Retry" in page or "retry" in page)
    check("P5: overflow-x-auto", "overflow-x-auto" in page)
else:
    check("P5: page.tsx exists", False, f"not found at {page_path}")

# Phase 5: API route
route_path = "../bei-tasks/app/api/analytics/sales/[endpoint]/route.ts"
if os.path.exists(route_path):
    route = open(route_path, encoding="utf-8").read()
    check("P5: product-mix endpoint in route", "product-mix" in route)
    check("P5: get_product_mix_analytics in route", "get_product_mix_analytics" in route)
    check("P5: sort_by param forwarded", "sort_by" in route)
    check("P5: limit param forwarded", '"limit"' in route)
else:
    check("P5: route.ts exists", False, f"not found at {route_path}")

# Phase 6: Artifacts
check("P6: REQUIREMENTS_REGRESSION_CHECK.md", os.path.exists("output/s179/REQUIREMENTS_REGRESSION_CHECK.md"))
check("P6: REMOTE_TRUTH_BASELINE.json", os.path.exists("output/s179/REMOTE_TRUTH_BASELINE.json"))

# Summary
fails = [r for r in results if not r[1]]
print(f"\n{'='*60}")
print(f"  {len(results) - len(fails)} PASS, {len(fails)} FAIL out of {len(results)} checks")
print(f"{'='*60}")
if fails:
    print("\nFailed checks:")
    for name, _, detail in fails:
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))
sys.exit(1 if fails else 0)
