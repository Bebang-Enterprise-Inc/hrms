"""S258 Phase 1.1 (A1) — Seed default_inventory_account on PARTIAL companies.

Pattern per company with default_inventory_account=NULL:
1. Locate the Current Assets group account (preferring "Current Assets - <ABBR>"
   then "1100000 - CURRENT ASSETS - <ABBR>" then any is_group=1 account whose
   account_name starts with "Current Assets" / "CURRENT ASSETS"). If not found,
   log to DEFECTS and skip.
2. Pre-check tabBin row count for warehouses of this company (W9 — log if non-zero
   but still proceed: Bins track movement; Company-level default is independent).
3. CREATE leaf account "Stock In Hand - <ABBR>" with root_type=Asset, account_type=Stock,
   account_currency=PHP, is_group=0, parent_account = located group.
4. SET tabCompany.default_inventory_account = the new account's docname.
5. Append rollback SQL to tmp/s258/rollback_phase1.sql.

BEI + BKI excluded (they have non-canonical Apex names already; Phase 3b/3c rewrites them).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (api_get, api_post, account_exists, create_account,
                  set_company_field, get_companies_by_status, write_rollback_sql,
                  log_action, sql_quote)

EXCLUDED = {"BEBANG ENTERPRISE INC.", "BEBANG KITCHEN INC."}


def find_current_assets_group(company: str, abbr: str) -> str | None:
    candidates = [
        f"Current Assets - {abbr}",
        f"CURRENT ASSETS - {abbr}",
        f"1100000 - Current Assets - {abbr}",
        f"1100000 - CURRENT ASSETS - {abbr}",
    ]
    for c in candidates:
        if account_exists(c):
            return c
    # Fall back: search for is_group=1 with name starting "Current Assets" or "CURRENT ASSETS"
    for pattern in ("Current Assets%", "CURRENT ASSETS%"):
        res = api_get("/api/resource/Account",
                      params={"fields": json.dumps(["name", "account_name", "is_group"]),
                              "filters": json.dumps([
                                  ["company", "=", company],
                                  ["account_name", "like", pattern.replace("%", "")],
                                  ["is_group", "=", 1],
                              ]),
                              "limit_page_length": 5})
        rows = res.get("data") or []
        if rows:
            return rows[0]["name"]
    return None


def warehouse_bin_count(company: str) -> int:
    """W9 — count tabBin rows where warehouse.company = this company."""
    wh_res = api_get(
        "/api/resource/Warehouse",
        params={"fields": json.dumps(["name"]),
                "filters": json.dumps([["company", "=", company]]),
                "limit_page_length": 0})
    wh_names = [w["name"] for w in (wh_res.get("data") or [])]
    if not wh_names:
        return 0
    bin_res = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "Bin",
                "filters": json.dumps([["warehouse", "in", wh_names]])})
    return bin_res.get("message") or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    partial = [r for r in get_companies_by_status("PARTIAL")
               if r["name"] not in EXCLUDED]
    null_default = [r for r in partial if not r.get("default_inventory_account")]
    print(f"[A1] {len(partial)} PARTIAL companies (excluding BEI + BKI)")
    print(f"     {len(null_default)} have default_inventory_account=NULL → will seed")
    print(f"     {len(partial) - len(null_default)} have non-canonical value (e.g. Apex names) → SKIPPED in A1; Phase 3 handles\n")

    defects = []
    rollback_lines = []
    actions = []

    for i, c in enumerate(null_default, 1):
        company = c["name"]
        abbr = c["abbr"]
        target_name = f"Stock In Hand - {abbr}"
        print(f"  [{i}/{len(null_default)}] {company} (abbr={abbr})")

        parent = find_current_assets_group(company, abbr)
        if not parent:
            msg = f"NO Current Assets group on {company}"
            print(f"      DEFECT: {msg}")
            defects.append({"company": company, "abbr": abbr, "reason": msg})
            continue

        bins = warehouse_bin_count(company)
        if bins > 0:
            note = f"tabBin count={bins} (W9 — proceeding; Bins track movement independently)"
            print(f"      [W9] {note}")
            defects.append({"company": company, "abbr": abbr, "bins_nonzero": bins, "note": note})

        exists_already = account_exists(target_name)
        if args.dry_run:
            print(f"      [DRY] parent={parent!r} → CREATE {target_name!r} (exists_already={exists_already}); SET tabCompany.default_inventory_account")
            actions.append({"company": company, "abbr": abbr, "parent": parent,
                            "target": target_name, "exists_already": exists_already})
            continue

        # ROLLBACK SQL captured BEFORE mutation
        rollback_lines.append(
            f"-- Rollback for {company} ({abbr}):"
        )
        rollback_lines.append(
            f"UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = {sql_quote(company)};"
        )
        if not exists_already:
            rollback_lines.append(
                f"DELETE FROM `tabAccount` WHERE name = {sql_quote(target_name)};"
            )
        rollback_lines.append("")

        # CREATE the leaf (idempotent)
        if not exists_already:
            try:
                resp = create_account(
                    name=target_name,
                    account_name="Stock In Hand",
                    parent_account=parent,
                    company=company,
                    is_group=0,
                    account_type="Stock",
                    root_type="Asset",
                    account_currency=c.get("default_currency") or "PHP",
                    account_number=None,
                )
                print(f"      CREATED {target_name}")
                log_action("1", "CREATE_ACCOUNT", target_name, "(absent)", target_name,
                           extras={"parent": parent, "company": company})
            except Exception as e:
                msg = f"CREATE failed: {e}"
                print(f"      ERROR: {msg}")
                defects.append({"company": company, "abbr": abbr, "reason": msg})
                continue
        else:
            print(f"      {target_name} already exists — skipping CREATE")

        # SET the Company field
        try:
            set_company_field(company, "default_inventory_account", target_name)
            print(f"      SET tabCompany.default_inventory_account = {target_name}")
            log_action("1", "SET_FIELD", company, "(NULL)", target_name,
                       extras={"field": "default_inventory_account"})
        except Exception as e:
            msg = f"SET failed: {e}"
            print(f"      ERROR: {msg}")
            defects.append({"company": company, "abbr": abbr, "reason": msg})
            continue

    if not args.dry_run and rollback_lines:
        write_rollback_sql(1, rollback_lines)
        print(f"\n[OK] Wrote {len(rollback_lines)} rollback lines to tmp/s258/rollback_phase1.sql")

    summary = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dry_run": args.dry_run,
        "partial_total": len(partial),
        "null_default_count": len(null_default),
        "defects": defects,
        "actions": actions if args.dry_run else None,
    }
    out = "tmp/s258/A1_dry_run.json" if args.dry_run else "output/s258/A1_summary.json"
    open(out, "w").write(json.dumps(summary, indent=2))
    print(f"\n[OK] Summary: {out}")
    print(f"     Defects: {len(defects)}")


if __name__ == "__main__":
    main()
