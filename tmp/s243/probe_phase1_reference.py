#!/usr/bin/env python3
"""S243 Phase 1-T1 probe — reference BARE-NAME stores.

Per v1.1-B1: XMM is a 2/45 outlier for AP+Current Assets. Use the dominant
43-store BARE-NAME convention. Sample 5 stores to confirm consistency.

For each sampled store, capture all is_group=1 group accounts to confirm:
- account_name BARE (no abbr suffix)
- account_number NULL or matching dominant pattern
- Title Case naming

Sampled abbrs: AMM, AFT, AYEVO, UPTC, AYSOL
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime

for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import frappe  # type: ignore

SAMPLE_ABBRS = ["AMM", "AFT", "AYEVO", "UPTC", "AYSOL"]
TARGET_GROUPS = ["Stock Assets", "Accounts Payable", "Current Assets"]


def main() -> None:
    payload: dict = {
        "sprint": "S243",
        "phase": "1-T1",
        "task": "BARE-NAME reference probe (5 stores)",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "sampled_abbrs": SAMPLE_ABBRS,
    }

    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        per_store: dict = {}
        for abbr in SAMPLE_ABBRS:
            company_row = frappe.db.sql(
                "SELECT name, parent_company FROM `tabCompany` WHERE abbr = %s",
                abbr,
                as_dict=True,
            )
            if not company_row:
                per_store[abbr] = {"error": f"No Company found for abbr={abbr}"}
                continue
            company = company_row[0]["name"]
            parent_company = company_row[0]["parent_company"]

            # All group accounts
            groups = frappe.db.sql(
                """
                SELECT name, account_name, account_number, parent_account, root_type
                FROM `tabAccount`
                WHERE company = %s AND is_group = 1
                ORDER BY root_type, account_number, account_name
                """,
                company,
                as_dict=True,
            )

            # For each TARGET_GROUP name, find matching group(s)
            target_match: dict = {}
            for tg in TARGET_GROUPS:
                # Match by account_name BARE (canonical pattern)
                bare_match = [g for g in groups if g["account_name"] == tg]
                # Match by account_name NUMBER PREFIX (XMM-style outlier)
                upper_match = [
                    g for g in groups
                    if isinstance(g["account_name"], str)
                    and g["account_name"].upper().startswith(tg.upper())
                    and g not in bare_match
                ]
                target_match[tg] = {
                    "bare_match_count": len(bare_match),
                    "bare_match": bare_match,
                    "upper_match_count": len(upper_match),
                    "upper_match": upper_match,
                }

            per_store[abbr] = {
                "company": company,
                "parent_company": parent_company,
                "abbr": abbr,
                "group_count": len(groups),
                "all_groups_sample": groups[:30],  # cap to keep file size sane
                "target_groups_resolved": target_match,
            }

        # Verify convention consistency: all 5 stores should have BARE matches for all 3 target groups
        consistent = True
        for abbr, store_data in per_store.items():
            if "error" in store_data:
                consistent = False
                break
            for tg in TARGET_GROUPS:
                resolved = store_data["target_groups_resolved"].get(tg, {})
                if resolved.get("bare_match_count", 0) != 1:
                    consistent = False
                    payload.setdefault("inconsistency_notes", []).append(
                        f"{abbr}: {tg} has bare_match_count={resolved.get('bare_match_count')} (expected 1)"
                    )

        payload["convention_consistent"] = consistent
        payload["stores"] = per_store

        # Reference parent_account chain — sample one store's BARE-NAME parent chains
        # (use first store with all 3 found)
        for abbr, store_data in per_store.items():
            if "error" in store_data:
                continue
            chains: dict = {}
            for tg in TARGET_GROUPS:
                bm = store_data["target_groups_resolved"][tg]["bare_match"]
                if bm:
                    chains[tg] = {
                        "name": bm[0]["name"],
                        "account_name": bm[0]["account_name"],
                        "account_number": bm[0]["account_number"],
                        "parent_account": bm[0]["parent_account"],
                        "root_type": bm[0]["root_type"],
                    }
            payload["sample_parent_chains_from"] = abbr
            payload["sample_parent_chains"] = chains
            break

        payload["status"] = "OK"

    except Exception as e:
        payload["status"] = "ERROR"
        payload["error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    # Write JSON to /tmp file inside container — runner does docker cp to extract.
    # SSM stdout has a ~24KB cap; writing to file avoids truncation.
    out_path = "/tmp/s243_phase1_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    sys.stdout.write(f"S243_PHASE1_OK status={payload.get('status')} consistent={payload.get('convention_consistent')} path={out_path}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
