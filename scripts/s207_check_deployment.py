"""S207 post-deploy validation: confirm the container has the new code."""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json, inspect

report = {}

# 1. S207 API presence
try:
    from hrms.api.labor_allocation import preview_allocation, post_allocation, preview_scheduled, PHT
    report["s207_api"] = {
        "preview_allocation_present": True,
        "post_allocation_present": True,
        "preview_scheduled_present": True,
        "pht_constant_present": True,
        "pht_offset_hours": PHT.utcoffset(None).total_seconds() / 3600,
    }
except ImportError as exc:
    report["s207_api"] = {"present": False, "error": str(exc)}

# 2. posting_date helper
try:
    from hrms.utils.labor_allocation import posting_date_for_slip
    from datetime import date
    report["posting_date_helper"] = {
        "present": True,
        "sample_first_half": str(posting_date_for_slip(date(2026, 4, 15))),
        "sample_second_half": str(posting_date_for_slip(date(2026, 4, 30))),
        "year_rollover": str(posting_date_for_slip(date(2026, 12, 31))),
    }
except ImportError as exc:
    report["posting_date_helper"] = {"present": False, "error": str(exc)}

# 3. DocType schema — year/month should be gone, slip_name should be reqd
cols = [r[0] for r in frappe.db.sql(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'tabBEI Labor Allocation Log'"
)]
index_rows = frappe.db.sql(
    "SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Non_unique = 0", as_dict=True
)
indexes = sorted({r["Key_name"] for r in index_rows})
report["labor_allocation_log_schema"] = {
    "columns": sorted(cols),
    "unique_indexes": sorted(indexes),
    "year_column_dropped": "year" not in cols,
    "month_column_dropped": "month" not in cols,
    "slip_name_column_present": "slip_name" in cols,
    "idx_slip_employee_present": "idx_slip_employee" in indexes,
    "idx_year_month_employee_absent": "idx_year_month_employee" not in indexes,
}

# 4. Salary Structures still Bimonthly
freqs = dict(frappe.db.sql(
    "SELECT payroll_frequency, COUNT(*) FROM `tabSalary Structure` WHERE is_active='Yes' GROUP BY payroll_frequency"
))
report["salary_structures"] = {
    "frequencies": freqs,
    "all_bimonthly": list(freqs.keys()) == ["Bimonthly"],
}

# 5. Hooks: new cron present, old cron absent — inspect the actual loaded module
import hrms.hooks as hrms_hooks
cron_events = getattr(hrms_hooks, "scheduler_events", {}).get("cron", {})
cron_0_22_daily = cron_events.get("0 22 * * *", [])
cron_0_22_1 = cron_events.get("0 22 1 * *", [])
report["hooks_cron"] = {
    "daily_0_22_targets": cron_0_22_daily,
    "preview_scheduled_in_daily": "hrms.api.labor_allocation.preview_scheduled" in cron_0_22_daily,
    "old_monthly_cron_absent": cron_0_22_1 == [] or "preview_monthly_allocation_scheduled" not in (cron_0_22_1 if isinstance(cron_0_22_1, list) else []),
    "old_monthly_cron_entries": cron_0_22_1,
}

# 6. Container HEAD SHA for traceability
import subprocess
try:
    sha_out = subprocess.check_output(
        ["git", "-C", "/home/frappe/frappe-bench/apps/hrms", "rev-parse", "HEAD"],
        stderr=subprocess.STDOUT,
    ).decode().strip()
    report["container_hrms_head"] = sha_out
except Exception as exc:
    report["container_hrms_head"] = f"error: {exc}"

print("===RESULT_JSON_BEGIN===")
print(json.dumps(report, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "l3" / "s207" / "deployment_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Pretty summary
    print("\n=== S207 DEPLOYMENT CHECK ===\n")
    for section, data in result.items():
        print(f"[{section}]")
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {data}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
