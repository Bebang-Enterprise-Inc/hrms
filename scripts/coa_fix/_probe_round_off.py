"""S258 Phase 1.3 pre-check — read live ROUND OFF accounts on ROBDA + XMM.

Phase 1.3 v1.2 P0-3 decides: cross-root_type? JE fallback. Same-root? merge rename.
We need: for each of (ROBDA, XMM) — (a) the actual account names matching ROUND OFF,
(b) their root_type/account_type, (c) their GL posting count, (d) whether canonical
"Round Off - <ABBR>" Expense already exists.
"""
from __future__ import annotations
import json
import subprocess
import sys
import time

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

TARGETS = {
    "ROBDA": "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
    "XMM":   "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
}


def api_get(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def list_accounts_like(company: str, name_like: str):
    fields = json.dumps(["name", "account_name", "account_number",
                         "root_type", "account_type", "is_group",
                         "parent_account", "disabled"])
    filters = json.dumps([
        ["company", "=", company],
        ["account_name", "like", f"%{name_like}%"],
    ])
    res = api_get("/api/resource/Account",
                  params={"fields": fields, "filters": filters,
                          "limit_page_length": 0})
    return res.get("data", [])


def gl_count_for_account(account_name: str) -> int:
    r = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "GL Entry",
                "filters": json.dumps([["account", "=", account_name]])},
    )
    return r.get("message") or 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {"captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "companies": {}}
    for abbr, company in TARGETS.items():
        print(f"\n--- {abbr} = {company} ---")
        # Look for any account_name containing ROUND OFF (UPPER) or Round Off (Title)
        rows = list_accounts_like(company, "ROUND OFF") + list_accounts_like(company, "Round Off")
        # Deduplicate by name
        seen = set()
        accts = []
        for r in rows:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            r["gl_entry_count"] = gl_count_for_account(r["name"])
            accts.append(r)
            print(f"  {r['name']} root={r['root_type']} type={r['account_type']} GL={r['gl_entry_count']} disabled={r.get('disabled')}")
        out["companies"][abbr] = {"company": company, "round_off_accounts": accts}
        # Decision per row
        upper = [r for r in accts if "ROUND OFF" in r["account_name"].upper() and r["account_name"] == r["account_name"].upper()]
        canonical = [r for r in accts if r["account_name"] == "Round Off"]
        out["companies"][abbr]["upper_form_count"] = len(upper)
        out["companies"][abbr]["canonical_form_count"] = len(canonical)
        out["companies"][abbr]["fallback_path"] = (
            "JE+DELETE" if any(r["root_type"] != "Expense" for r in upper)
            else "MERGE_RENAME"
        )
    open("tmp/s258/probe_round_off.json", "w").write(json.dumps(out, indent=2))
    print("\nWritten tmp/s258/probe_round_off.json")
    for abbr, c in out["companies"].items():
        print(f"  {abbr} fallback_path = {c['fallback_path']}; upper={c['upper_form_count']}, canonical={c['canonical_form_count']}")


if __name__ == "__main__":
    main()
