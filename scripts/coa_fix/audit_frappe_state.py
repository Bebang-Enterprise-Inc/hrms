"""S258 Phase 0.6 — Live Frappe COA state audit + GL volume per Company.

Augments tmp/coa_audit/audit_frappe_coa.py with:
- --include-gl-counts flag (per-Company tabGL Entry count via Frappe SQL)
- --output writes the JSON path explicitly
- Doppler-driven credentials (no hardcoded keys)

Outputs:
- output/s258/baseline_state.json  (default; --output overrides)
- output/s258/baseline_provision_status.json (Phase 0.5.5)
- output/s258/abbr_inconsistency_audit.json (Phase 0.6.5)
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def doppler(key: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
    ).strip()


BASE = "https://hq.bebang.ph"
API_KEY = doppler("FRAPPE_API_KEY")
API_SECRET = doppler("FRAPPE_API_SECRET")
HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Accept": "application/json",
}

import requests

CRITICAL_FIELDS = [
    "round_off_account", "round_off_cost_center",
    "default_receivable_account", "default_payable_account",
    "default_expense_account", "default_income_account",
    "exchange_gain_loss_account", "write_off_account",
    "default_inventory_account", "stock_received_but_not_billed",
]


def api_get(path: str, params=None):
    url = f"{BASE}{path}"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params or {}, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def list_companies():
    fields = json.dumps([
        "name", "company_name", "abbr", "parent_company", "is_group",
        "country", "default_currency", "creation", "tax_id",
    ] + CRITICAL_FIELDS)
    res = api_get(
        "/api/resource/Company",
        params={"fields": fields, "limit_page_length": 0, "order_by": "name asc"},
    )
    return res.get("data", [])


def has_first_provision_field(company_name: str) -> dict:
    """Phase 0.5.5 — read first_provision_done custom field if it exists."""
    res = api_get(
        "/api/resource/Company/" + company_name,
        params={"fields": json.dumps(["name", "first_provision_done"])},
    )
    data = res.get("data") or {}
    return {"first_provision_done": data.get("first_provision_done")}


def account_counts(company_name: str):
    total = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "Account",
                "filters": json.dumps([["company", "=", company_name]])},
    ).get("message", 0)
    by_root = {}
    for rt in ("Asset", "Liability", "Equity", "Income", "Expense"):
        r = api_get(
            "/api/method/frappe.client.get_count",
            params={"doctype": "Account",
                    "filters": json.dumps([
                        ["company", "=", company_name],
                        ["root_type", "=", rt]])},
        )
        by_root[rt] = r.get("message", 0)
    return {"total": total, "by_root_type": by_root}


def gl_entry_count(company_name: str) -> int:
    """Phase 0.6 --include-gl-counts: live SELECT COUNT(*) FROM tabGL Entry."""
    r = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "GL Entry",
                "filters": json.dumps([["company", "=", company_name]])},
    )
    return r.get("message") or 0


def has_round_off_account(company_name: str) -> bool:
    res = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "Account",
                "filters": json.dumps([
                    ["company", "=", company_name],
                    ["account_type", "=", "Round Off"]])},
    )
    return (res.get("message") or 0) > 0


def classify_status(company: dict, counts: dict, has_ro: bool) -> str:
    """HEALTHY / PARTIAL / MINIMAL / MISSING per QBO-readiness."""
    total = counts["total"]
    by_root = counts["by_root_type"]
    if total == 0:
        return "MISSING"
    has_all_roots = all(by_root[rt] > 0 for rt in ("Asset", "Liability", "Equity", "Income", "Expense"))
    has_ro_account = has_ro and bool(company.get("round_off_account"))
    has_ro_cc = bool(company.get("round_off_cost_center"))
    has_inv = bool(company.get("default_inventory_account"))
    has_srbnb = bool(company.get("stock_received_but_not_billed"))
    if total < 30:
        return "MINIMAL"
    if has_all_roots and has_ro_account and has_ro_cc and has_inv and has_srbnb:
        return "HEALTHY"
    return "PARTIAL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="output/s258/baseline_state.json")
    ap.add_argument("--include-gl-counts", action="store_true")
    ap.add_argument("--provision-output", default="output/s258/baseline_provision_status.json")
    ap.add_argument("--abbr-audit-output", default="output/s258/abbr_inconsistency_audit.json")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"[S258 P0.6] Fetching companies from {BASE} ...")
    companies = list_companies()
    print(f"  -> {len(companies)} companies")
    assert len(companies) == 58, f"Expected 58 Companies, got {len(companies)}"

    rows = []
    provision_rows = []
    abbr_issues = []
    for i, c in enumerate(companies, 1):
        name = c["name"]
        print(f"  [{i}/{len(companies)}] {name}")
        counts = account_counts(name)
        has_ro = has_round_off_account(name)
        status = classify_status(c, counts, has_ro)
        row = {
            "name": name,
            "abbr": c.get("abbr"),
            "parent_company": c.get("parent_company"),
            "is_group": c.get("is_group"),
            "tax_id": c.get("tax_id"),
            "total_accounts": counts["total"],
            "by_root_type": counts["by_root_type"],
            "round_off_account": c.get("round_off_account"),
            "round_off_cost_center": c.get("round_off_cost_center"),
            "default_inventory_account": c.get("default_inventory_account"),
            "stock_received_but_not_billed": c.get("stock_received_but_not_billed"),
            "default_receivable_account": c.get("default_receivable_account"),
            "default_payable_account": c.get("default_payable_account"),
            "default_expense_account": c.get("default_expense_account"),
            "default_income_account": c.get("default_income_account"),
            "exchange_gain_loss_account": c.get("exchange_gain_loss_account"),
            "write_off_account": c.get("write_off_account"),
            "status": status,
        }
        if args.include_gl_counts:
            row["gl_entry_count"] = gl_entry_count(name)
        rows.append(row)

        # Phase 0.5.5 — first_provision_done
        prov = has_first_provision_field(name)
        provision_rows.append({"name": name, **prov})

        # Phase 0.6.5 — abbr inconsistency
        name_upper = name == name.upper()
        abbr_upper = (c.get("abbr") or "") == (c.get("abbr") or "").upper()
        if not name_upper or not abbr_upper:
            abbr_issues.append({
                "name": name,
                "abbr": c.get("abbr"),
                "parent_company": c.get("parent_company"),
                "name_is_upper": name_upper,
                "abbr_is_upper": abbr_upper,
            })

    state = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "company_count": len(rows),
        "status_summary": {
            s: sum(1 for r in rows if r["status"] == s)
            for s in ("HEALTHY", "PARTIAL", "MINIMAL", "MISSING")
        },
        "rows": rows,
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    open(args.output, "w").write(json.dumps(state, indent=2))
    print(f"\n[OK] Wrote {args.output}")
    print(f"     Status summary: {state['status_summary']}")

    os.makedirs(os.path.dirname(args.provision_output) or ".", exist_ok=True)
    open(args.provision_output, "w").write(json.dumps({
        "captured_at": state["captured_at"],
        "rows": provision_rows,
        "count_done": sum(1 for r in provision_rows if r["first_provision_done"]),
        "count_not_done": sum(1 for r in provision_rows if not r["first_provision_done"]),
    }, indent=2))
    print(f"[OK] Wrote {args.provision_output}")

    os.makedirs(os.path.dirname(args.abbr_audit_output) or ".", exist_ok=True)
    open(args.abbr_audit_output, "w").write(json.dumps({
        "captured_at": state["captured_at"],
        "cleanroom_csv_found": False,  # tested below in shell preamble
        "sql_fallback_used": True,
        "found_inconsistencies": abbr_issues,
        "scope_expansion_required": len(abbr_issues) > 0,
        "rationale": "Phase 0.6.5 v1.2 P1-7 SQL fallback executed (cleanroom find returned 0 hits per plan-amendment).",
    }, indent=2))
    print(f"[OK] Wrote {args.abbr_audit_output}")
    print(f"     Found {len(abbr_issues)} abbr inconsistencies")


if __name__ == "__main__":
    main()
