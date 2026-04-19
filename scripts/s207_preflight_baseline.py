"""S207 P0-T1 — Baseline capture.

Writes ``output/s207/preflight/baseline.json`` with the production state that
S207 will transform. Each field is asserted by the Phase 0 gate:

  - production_head_sha               : current HEAD in the hrms remote
  - cron_entries                      : list of all scheduler_events.cron keys
  - salary_structures_frequency       : {payroll_frequency: count, ...}
  - labor_allocation_log_columns      : live DB columns in tabBEI Labor Allocation Log
  - labor_allocation_log_unique_keys  : list of unique index Key_names
  - coverage_before_count             : # Companies with full S206 COA (expected 47)
  - uncovered_companies_fully_qualified: list of 4 Company names (all end " - BEBANG ENTERPRISE INC.")

The script is idempotent — safe to rerun.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Local import — keep working dir at repo root
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json  # noqa: E402


FOUR_CHILDREN_EXPECTED = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]


SCRIPT = r"""
import json

# Salary Structures — active only, grouped by payroll_frequency
ss_rows = frappe.db.sql(
    "SELECT payroll_frequency, COUNT(*) AS n FROM `tabSalary Structure` WHERE is_active='Yes' GROUP BY payroll_frequency",
    as_dict=True,
)
salary_structures_frequency = {r["payroll_frequency"]: int(r["n"]) for r in ss_rows}

# tabBEI Labor Allocation Log — live DB schema
cols = frappe.db.sql(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'tabBEI Labor Allocation Log' "
    "ORDER BY ordinal_position",
    as_dict=True,
)
labor_allocation_log_columns = [r["column_name"] for r in cols]

uniq_rows = frappe.db.sql(
    "SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Non_unique = 0",
    as_dict=True,
)
# Collapse by Key_name to get unique index names
labor_allocation_log_unique_keys = sorted({r["Key_name"] for r in uniq_rows})

# S206 COA coverage — a Company is complete iff it has a Due From + Due To
# account, an internal Customer (is_internal_customer=1, represents_company=self),
# and an internal Supplier (is_internal_supplier=1, represents_company=self).
companies = frappe.db.sql(
    "SELECT name, abbr, parent_company FROM `tabCompany` "
    "WHERE entity_category='Store' AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant')) "
    "ORDER BY name",
    as_dict=True,
)

def complete_for(co):
    # S206 seeder sets account_name = "1104200 - DUE FROM GROUP ENTITIES"
    # and docname = "1104200 - DUE FROM GROUP ENTITIES - <abbr>".
    # The separate `account_number` column may be NULL depending on Frappe
    # auto-derivation — so match by name prefix which is the seeder contract.
    has_due_from = bool(frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND is_group=0 "
        "AND name LIKE '1104200 - DUE FROM GROUP ENTITIES%%' LIMIT 1",
        (co["name"],),
    ))
    has_due_to = bool(frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND is_group=0 "
        "AND name LIKE '2104200 - DUE TO GROUP ENTITIES%%' LIMIT 1",
        (co["name"],),
    ))
    has_customer = frappe.db.exists(
        "Customer",
        {"represents_company": co["name"], "is_internal_customer": 1},
    )
    has_supplier = frappe.db.exists(
        "Supplier",
        {"represents_company": co["name"], "is_internal_supplier": 1},
    )
    return all([has_due_from, has_due_to, has_customer, has_supplier])

complete = []
incomplete = []
for co in companies:
    if complete_for(co):
        complete.append(co["name"])
    else:
        incomplete.append(co["name"])

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "salary_structures_frequency": salary_structures_frequency,
    "labor_allocation_log_columns": labor_allocation_log_columns,
    "labor_allocation_log_unique_keys": labor_allocation_log_unique_keys,
    "total_companies": len(companies),
    "coverage_before_count": len(complete),
    "coverage_incomplete_count": len(incomplete),
    "complete_companies": complete,
    "incomplete_companies": incomplete,
}, indent=2))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out_path = REPO / "output" / "s207" / "preflight" / "baseline.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("[S207 P0-T1] Capturing production baseline via SSM…", flush=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=300)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}")
        print(f"STDERR:\n{stderr[:2000]}")
        return rc

    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Could not parse RESULT_JSON markers from stdout:\n{stdout[:2000]}")
        return 1

    # Derive uncovered_companies_fully_qualified from SSM result
    incomplete = result["incomplete_companies"]
    four_children = sorted(c for c in incomplete if c.endswith(" - BEBANG ENTERPRISE INC."))

    # Capture production HEAD SHA
    git_proc = subprocess.run(
        ["git", "rev-parse", "origin/production"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    production_head_sha = git_proc.stdout.strip() if git_proc.returncode == 0 else "UNKNOWN"

    # Capture cron entries as grep of hooks.py
    import re
    hooks_text = (REPO / "hrms" / "hooks.py").read_text(encoding="utf-8")
    cron_entries = re.findall(r'"([\d \*/,-]+)":\s*\[\s*"([\w\.]+)"', hooks_text)

    baseline = {
        "run_timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "production_head_sha": production_head_sha,
        "cron_entries": [{"schedule": s, "target": t} for s, t in cron_entries],
        "salary_structures_frequency": result["salary_structures_frequency"],
        "labor_allocation_log_columns": result["labor_allocation_log_columns"],
        "labor_allocation_log_unique_keys": result["labor_allocation_log_unique_keys"],
        "total_companies": result["total_companies"],
        "coverage_before_count": result["coverage_before_count"],
        "coverage_incomplete_count": result["coverage_incomplete_count"],
        "uncovered_companies_fully_qualified": four_children,
        "uncovered_companies_all": sorted(incomplete),
    }
    out_path.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] baseline written to {out_path}")
    print(f"  coverage_before_count = {baseline['coverage_before_count']}")
    print(f"  uncovered (4 BEBANG ENTERPRISE) = {len(four_children)}")
    print(f"  Structures frequency = {baseline['salary_structures_frequency']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
