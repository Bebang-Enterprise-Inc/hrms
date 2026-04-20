"""S207 P6-T2 — Create Asset (+ Liability where missing) root groups on the
4 BEBANG ENTERPRISE children's OWN COA.

After this step the S206 seeder's ``_find_parent_group`` fallback succeeds on
each child, allowing ``_ensure_account`` to create the Due From / Due To
intercompany accounts.

Diagnostic baseline (output/s207/backups/4_children_coa_before.json):
  Each child has a LIABILITY root (``2104000 - INTERCOMPANY PAYABLES - <abbr>``)
  already — created during earlier setup. No child has an ASSET root, so
  ``_find_parent_group`` for asset receivables fails. We create the missing
  Asset root per child (at account_number 1100000 — matches the BEI canonical
  COA template for top-level asset groups).

Uses ``/frappe-bulk-edits`` SSM pattern + ``ignore_root_company_validation``
flag (S181 precedent). Idempotent: if the Asset root already exists, skipped.
Per-company savepoint.
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

def ensure_root(company, abbr, currency, label, root_type, account_number):
    # Canonical docname pattern: "<num> - <LABEL> - <abbr>"
    docname = f"{{account_number}} - {{label}} - {{abbr}}"
    if frappe.db.exists("Account", docname):
        return {{"action": "existed", "name": docname}}
    # Also accept a pre-existing is_group=1 root of the same root_type, regardless of number
    existing_any = frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND is_group=1 AND root_type=%s AND parent_account IS NULL LIMIT 1",
        (company, root_type), as_dict=True,
    )
    if existing_any:
        return {{"action": "existed_other_name", "name": existing_any[0]["name"]}}
    # Mirror the S206 seeder shape: account_name carries the number prefix; we do
    # NOT set account_number separately (Frappe auto-derives and would
    # double-number otherwise). ignore_mandatory lets us insert a root account
    # where parent_account is genuinely None (S181 pattern).
    doc = frappe.get_doc({{
        "doctype": "Account",
        "account_name": f"{{account_number}} - {{label}}",
        "parent_account": None,
        "is_group": 1,
        "root_type": root_type,
        "report_type": "Balance Sheet",
        "company": company,
        "account_currency": currency or "PHP",
    }})
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return {{"action": "created", "name": doc.name}}

report = {{}}
for company in targets:
    abbr = frappe.db.get_value("Company", company, "abbr")
    currency = frappe.db.get_value("Company", company, "default_currency") or "PHP"
    sp = f"s207_rootgroups_{{abbr}}"
    original_flag = getattr(frappe.local.flags, "ignore_root_company_validation", False)
    try:
        frappe.local.flags.ignore_root_company_validation = True
        frappe.db.savepoint(sp)
        asset = ensure_root(company, abbr, currency, "ASSETS", "Asset", "1100000")
        liab = ensure_root(company, abbr, currency, "LIABILITIES", "Liability", "2100000")
        frappe.db.release_savepoint(sp)
        report[company] = {{"abbr": abbr, "asset_root": asset, "liability_root": liab, "status": "ok"}}
    except Exception as exc:
        try:
            frappe.db.rollback(save_point=sp)
        except Exception:
            pass
        import traceback as _tb
        report[company] = {{"abbr": abbr, "status": "error", "error": str(exc), "trace": _tb.format_exc()[:1500]}}
    finally:
        frappe.local.flags.ignore_root_company_validation = original_flag

frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional: per-company savepoint commits roll up here

print("===RESULT_JSON_BEGIN===")
print(json.dumps(report, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "evidence" / "4_children_root_groups.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = SCRIPT_TEMPLATE.format(targets=json.dumps(FOUR_CHILDREN))
    rc, stdout, stderr = run_via_ssm(script, timeout_seconds=240)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    all_ok = all(info.get("status") == "ok" for info in result.values())
    for co, info in result.items():
        if info.get("status") == "ok":
            a = info["asset_root"]
            l = info["liability_root"]
            print(f"  [{info['abbr']}] Asset: {a['action']} ({a['name']}) | Liability: {l['action']} ({l['name']})")
        else:
            print(f"  [{info.get('abbr')}] ERROR: {info.get('error')}")
    if not all_ok:
        print(f"[FAIL] Some companies errored — see {out}")
        return 1
    print(f"[OK] Root groups ensured for 4 children. Evidence: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
