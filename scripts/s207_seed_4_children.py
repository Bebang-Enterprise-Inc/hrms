"""S207 P6-T3 — Run the S206 seeder, targeted at the 4 BEBANG ENTERPRISE children.

After P6-T2 created Asset root groups (and Liability roots were already
present), ``hrms.on_demand.s206_seed_intercompany_accounts`` can now produce
Due From / Due To accounts + internal Customer / Supplier for each child via
its ``_find_parent_group`` fallback.

We call ``execute()`` which iterates all Companies (idempotent — it returns
``existed`` for the 45 already-complete ones and ``created`` / ``updated`` for
the 4 children).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

FOUR_CHILDREN = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]

SCRIPT = r"""
import json, os
from hrms.on_demand import s206_seed_intercompany_accounts as seeder

# Call the seeder's execute() — idempotent across all in-scope Companies
full = seeder.execute()

# Save the full report to the container's site files (retrieved later if needed)
os.makedirs("/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files", exist_ok=True)
fullpath = "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files/s207_seed_full_report.json"
with open(fullpath, "w") as f:
    json.dump(full, f, default=str)

# Compact summary only — SSM stdout has a ~24KB limit, so the full per-company
# detail stays on the container. We surface counts + the 4 children's rows only.
targets = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]

def summarize_row(row):
    return {
        "company": row.get("company"),
        "accounts_created": len(row.get("accounts_created", [])),
        "accounts_existed": len(row.get("accounts_existed", [])),
        "accounts_errored": len(row.get("accounts_errored", [])),
        "customer": row.get("customer"),
        "supplier": row.get("supplier"),
        "errors": row.get("errors", []),
    }

four_children_compact = {}
for row in full.get("companies", []):
    if row.get("company") in targets:
        four_children_compact[row["company"]] = summarize_row(row)

top_level = {k: v for k, v in full.items() if not isinstance(v, list) or k in ("errors",)}

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "top_level_counts": top_level,
    "four_children": four_children_compact,
    "full_report_path": fullpath,
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "evidence" / "4_children_seed_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=600)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:2000]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:2000]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[OK] Seeder top-level counts:")
    for k, v in result.get("top_level_counts", {}).items():
        print(f"    {k}: {v if not isinstance(v, list) else len(v)}")
    print("[OK] 4 BEBANG ENTERPRISE children:")
    for co, row in result.get("four_children", {}).items():
        print(f"  {co}: created={row['accounts_created']}, existed={row['accounts_existed']}, errored={row['accounts_errored']}, customer={row['customer']}, supplier={row['supplier']}")
    print(f"[OK] Full report on container: {result.get('full_report_path')}")
    errs = [co for co, row in result["four_children"].items() if row.get("errors")]
    if errs:
        print(f"[WARN] {len(errs)} child(ren) returned errors — inspect evidence file")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
