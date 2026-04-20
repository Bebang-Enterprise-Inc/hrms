"""S207 P6-T1 — Pre-touch backup of the 4 BEBANG ENTERPRISE children's COA.

Writes ``output/s207/backups/4_children_coa_before.json`` so Phase 6 changes
are reversible if the seeder misfires.
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

SCRIPT_TEMPLATE = r"""
import json
targets = {targets}
by_company = {{}}
for co in targets:
    rows = frappe.db.sql(
        "SELECT name, account_name, account_number, root_type, parent_account, is_group, company, account_currency "
        "FROM `tabAccount` WHERE company = %s ORDER BY name",
        (co,), as_dict=True,
    )
    abbr = frappe.db.get_value("Company", co, "abbr")
    default_cur = frappe.db.get_value("Company", co, "default_currency")
    by_company[co] = {{"abbr": abbr, "default_currency": default_cur, "accounts": rows}}
print("===RESULT_JSON_BEGIN===")
print(json.dumps(by_company, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "backups" / "4_children_coa_before.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = SCRIPT_TEMPLATE.format(targets=json.dumps(FOUR_CHILDREN))
    rc, stdout, stderr = run_via_ssm(script, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for co, info in result.items():
        n = len(info.get("accounts", []))
        has_asset_root = any(a["is_group"] == 1 and a["root_type"] == "Asset" for a in info["accounts"])
        has_liab_root = any(a["is_group"] == 1 and a["root_type"] == "Liability" for a in info["accounts"])
        print(f"  {co}: {n} accounts, abbr={info.get('abbr')}, currency={info.get('default_currency')}, asset_root={has_asset_root}, liab_root={has_liab_root}")
    print(f"[OK] Backup written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
