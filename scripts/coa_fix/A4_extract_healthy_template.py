"""S258 Phase 1.4 (A4) — Extract canonical store template from 6 HEALTHY Companies.

Read-only. Union the account names (with -<ABBR> suffix stripped) across the 6
HEALTHY Companies. Output: data/_FINAL/COA_HEALTHY_REFERENCE.csv with columns
(account_name, account_number, root_type, account_type, parent_account_stem, is_group,
appears_in_count, appears_in_companies). This becomes the standard store template
consumed by Phase 2.6 (4 BEI-TIN stub seed).
"""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests


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

# The 6 HEALTHY Companies per Phase 0.6 baseline_state.json (status==HEALTHY).
# We compute them dynamically from the baseline (more robust than hardcoding).


def api_get(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def load_healthy_companies():
    state = json.load(open("output/s258/baseline_state.json"))
    healthy = [r for r in state["rows"] if r["status"] == "HEALTHY"]
    return healthy


def fetch_accounts(company: str):
    fields = json.dumps(["name", "account_name", "account_number",
                         "root_type", "account_type", "is_group",
                         "parent_account", "disabled"])
    res = api_get(
        "/api/resource/Account",
        params={"fields": fields,
                "filters": json.dumps([["company", "=", company]]),
                "limit_page_length": 0,
                "order_by": "name asc"},
    )
    return res.get("data", [])


def strip_company_suffix(s: str, abbr: str) -> str:
    """Strip ' - ABBR' suffix from account name/parent."""
    if s is None:
        return None
    suffix = f" - {abbr}"
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    healthy = load_healthy_companies()
    print(f"[A4] {len(healthy)} HEALTHY Companies:")
    for h in healthy:
        print(f"  - {h['name']} (abbr={h['abbr']}, accts={h['total_accounts']})")

    union = defaultdict(lambda: {"appears_in_companies": []})
    per_company = {}
    for h in healthy:
        accts = fetch_accounts(h["name"])
        per_company[h["abbr"]] = len(accts)
        for a in accts:
            stem = strip_company_suffix(a["account_name"], h["abbr"])
            parent_stem = strip_company_suffix(a.get("parent_account"), h["abbr"])
            row = union[stem]
            row["account_name"] = stem
            # First occurrence wins for canonical fields; collisions logged.
            for k in ("account_number", "root_type", "account_type", "is_group"):
                if k not in row:
                    row[k] = a.get(k)
                elif row[k] != a.get(k):
                    row.setdefault("collisions", []).append(
                        {"abbr": h["abbr"], "field": k, "this_value": a.get(k), "first_value": row[k]}
                    )
            row.setdefault("parent_account_stem", parent_stem)
            row["appears_in_companies"].append(h["abbr"])

    out_rows = []
    for stem, r in sorted(union.items(), key=lambda x: (x[1].get("account_number") or "zzz", x[0])):
        out_rows.append({
            "account_name": stem,
            "account_number": r.get("account_number") or "",
            "root_type": r.get("root_type") or "",
            "account_type": r.get("account_type") or "",
            "parent_account_stem": r.get("parent_account_stem") or "",
            "is_group": r.get("is_group") if r.get("is_group") is not None else "",
            "appears_in_count": len(r["appears_in_companies"]),
            "appears_in_companies": ";".join(r["appears_in_companies"]),
        })

    os.makedirs("data/_FINAL", exist_ok=True)
    out_path = "data/_FINAL/COA_HEALTHY_REFERENCE.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "account_name", "account_number", "root_type", "account_type",
            "parent_account_stem", "is_group", "appears_in_count",
            "appears_in_companies",
        ])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\n[OK] Wrote {out_path} ({len(out_rows)} unique account stems)")
    print(f"     Per-company account counts: {per_company}")
    print(f"     Stems appearing in ALL {len(healthy)} HEALTHY companies: "
          f"{sum(1 for r in out_rows if r['appears_in_count'] == len(healthy))}")


if __name__ == "__main__":
    main()
