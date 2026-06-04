"""S258 Phase 1.3.5 pre-check — BEI's round_off_account state.

Plan: currently tabCompany.round_off_account = "Stock Adjustment - Bebang Enterprise Inc."
(non-canonical Apex name). Want to canonicalize to "Round Off - BEI" Expense.

Need: confirm current value, find/create Round Off - BEI, check whether the existing
'Stock Adjustment - Bebang Enterprise Inc.' account has GL postings (would need JE transfer).
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


def api_get(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    res = api_get("/api/resource/Company/BEBANG ENTERPRISE INC.",
                  params={"fields": json.dumps([
                      "name", "abbr", "round_off_account", "round_off_cost_center",
                      "default_expense_account", "stock_received_but_not_billed",
                  ])})
    c = res.get("data") or {}
    print(json.dumps(c, indent=2))
    cur = c.get("round_off_account")
    print(f"\nCurrent round_off_account on BEI: {cur}")

    # Look at all accounts on BEI that contain "Round Off" / "ROUND OFF" / "Stock Adjustment"
    for kw in ("Round Off", "ROUND OFF", "Stock Adjustment", "STOCK ADJUSTMENT"):
        fields = json.dumps(["name", "account_name", "root_type",
                             "account_type", "is_group", "parent_account",
                             "disabled"])
        filters = json.dumps([
            ["company", "=", "BEBANG ENTERPRISE INC."],
            ["account_name", "like", f"%{kw}%"],
        ])
        accts = api_get("/api/resource/Account",
                        params={"fields": fields, "filters": filters,
                                "limit_page_length": 0}).get("data", [])
        for a in accts:
            cnt = api_get(
                "/api/method/frappe.client.get_count",
                params={"doctype": "GL Entry",
                        "filters": json.dumps([["account", "=", a["name"]]])},
            ).get("message") or 0
            print(f"  {a['name']!r}  root={a['root_type']} type={a['account_type']} GL={cnt} disabled={a.get('disabled')}")

    # Final decision summary
    out = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "current_round_off_account": cur,
        "canonical_target": "Round Off - BEI",
        "needs_canonical_create": True,  # confirmed later
        "needs_je_transfer": True,
    }
    open("tmp/s258/probe_bei_round_off.json", "w").write(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
