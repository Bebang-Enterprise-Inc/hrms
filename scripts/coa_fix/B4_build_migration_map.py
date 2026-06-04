"""S258 Phase 2.0 — Build per-Company Apex→canonical migration map for BEI/BKI/III.

Reads live tabAccount via REST. Joins with canonical templates + Butch's 27-account
Sales tree. Maps each Apex row to a canonical name (account_number match where set;
Appendix E derivation rule otherwise). Topologically sorted via graphlib.
"""
from __future__ import annotations
import csv
import graphlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import api_get


COMPANIES = {
    "BEI": "BEBANG ENTERPRISE INC.",
    "BKI": "BEBANG KITCHEN INC.",
    "III": "IRRESISTIBLE INFUSIONS INC.",
}

ROLE_TEMPLATE = {
    "BEI": "data/_FINAL/COA_TEMPLATE_HEAD_OFFICE.csv",
    "BKI": "data/_FINAL/COA_TEMPLATE_COMMISSARY.csv",
    "III": "data/_FINAL/COA_HEALTHY_REFERENCE.csv",  # III as holdco uses bare 5-root + standard
}


def load_template(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_live_accounts(company: str):
    fields = json.dumps(["name", "account_name", "account_number",
                         "parent_account", "is_group", "root_type",
                         "account_type", "disabled"])
    res = api_get(
        "/api/resource/Account",
        params={"fields": fields,
                "filters": json.dumps([["company", "=", company]]),
                "limit_page_length": 0,
                "order_by": "name asc"},
    )
    return res.get("data") or []


def derive_canonical_name(apex_name: str, apex_number: str | None, abbr: str,
                          company_long: str, template_by_num: dict, template_by_name: dict) -> str | None:
    """Apex name → canonical stem. Returns the canonical_name (stem) or None if unmatched.

    Rule 1: if account_number is set + matches a canonical template row → use that stem.
    Rule 2 (Appendix E): strip ` - <long company name>` suffix → use as stem, find match.
    Rule 3: leave stem = original (we'll just suffix it with abbr later).
    """
    if apex_number and apex_number in template_by_num:
        return template_by_num[apex_number]["account_name"]
    # Strip suffix
    suffix_long = f" - {company_long.title()}"  # 'Bebang Enterprise Inc.'
    suffix_long_alt = f" - {company_long}"  # 'BEBANG ENTERPRISE INC.'
    suffix_abbr = f" - {abbr}"
    stem = apex_name
    for s in (suffix_long, suffix_long_alt, suffix_abbr):
        if stem.endswith(s):
            stem = stem[: -len(s)]
            break
    # Drop number prefix if any (e.g. "1100000 - CURRENT ASSETS")
    if " - " in stem:
        parts = stem.split(" - ", 1)
        if parts[0].isdigit() or (parts[0].replace(".", "").isdigit()):
            stem = parts[1]
    # Try direct match in template
    if stem in template_by_name:
        return stem
    # UPPER case fallback
    upper = stem.upper()
    if upper in template_by_name:
        return upper
    # Title case fallback
    title = stem.title()
    if title in template_by_name:
        return title
    return stem  # Use as-is; downstream will mark UNRESOLVED if needed


def build_for_company(abbr: str, company_long: str, template_rows: list[dict], out_path: str):
    print(f"\n=== {abbr} = {company_long} ===")
    live = load_live_accounts(company_long)
    print(f"  Live accounts: {len(live)}")
    template_by_num = {r["account_number"]: r for r in template_rows
                       if r.get("account_number")}
    template_by_name = {r["account_name"]: r for r in template_rows}

    rows = []
    unresolved = 0
    for a in live:
        if a.get("disabled"):
            continue
        canonical_stem = derive_canonical_name(
            a["account_name"], a.get("account_number"), abbr, company_long,
            template_by_num, template_by_name,
        )
        canonical_name = f"{canonical_stem} - {abbr}"
        if a["name"] == canonical_name:
            action = "NOOP"
        elif canonical_stem in template_by_name:
            action = "RENAME"
        else:
            action = "UNRESOLVED"
            unresolved += 1
        # Determine canonical parent
        canonical_parent_stem = None
        if canonical_stem in template_by_name:
            tpl = template_by_name[canonical_stem]
            canonical_parent_stem = tpl.get("parent_account_stem") or None
        canonical_parent = (f"{canonical_parent_stem} - {abbr}"
                            if canonical_parent_stem else "")
        rows.append({
            "old_name": a["name"],
            "old_parent": a.get("parent_account") or "",
            "old_account_number": a.get("account_number") or "",
            "canonical_name": canonical_name,
            "canonical_parent": canonical_parent,
            "canonical_account_number": (template_by_name.get(canonical_stem) or {}).get("account_number", ""),
            "canonical_root_type": a.get("root_type") or "",
            "canonical_account_type": a.get("account_type") or "",
            "migration_action": action,
            "is_group": a.get("is_group") or 0,
        })

    # Topological sort
    ts = graphlib.TopologicalSorter()
    by_canonical = {r["canonical_name"]: r for r in rows}
    for r in rows:
        if r["canonical_parent"] and r["canonical_parent"] in by_canonical:
            ts.add(r["canonical_name"], r["canonical_parent"])
        else:
            ts.add(r["canonical_name"])
    try:
        order = list(ts.static_order())
    except graphlib.CycleError as e:
        print(f"  CYCLE detected: {e}; falling back to insertion order")
        order = [r["canonical_name"] for r in rows]
    rows_sorted = []
    seen = set()
    for n in order:
        if n in by_canonical and n not in seen:
            rows_sorted.append(by_canonical[n])
            seen.add(n)
    for r in rows:  # any not in topo order
        if r["canonical_name"] not in seen:
            rows_sorted.append(r)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "old_name", "old_parent", "old_account_number",
            "canonical_name", "canonical_parent", "canonical_account_number",
            "canonical_root_type", "canonical_account_type",
            "migration_action", "is_group",
        ])
        w.writeheader()
        w.writerows(rows_sorted)
    by_action = {a: sum(1 for r in rows if r["migration_action"] == a)
                 for a in ("NOOP", "RENAME", "UNRESOLVED")}
    print(f"  {by_action} → {out_path}")
    return rows_sorted, by_action


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    Path("tmp/s258").mkdir(parents=True, exist_ok=True)
    for abbr, long in COMPANIES.items():
        template = load_template(ROLE_TEMPLATE[abbr])
        out = f"tmp/s258/migration_map_{abbr}.csv"
        build_for_company(abbr, long, template, out)


if __name__ == "__main__":
    main()
