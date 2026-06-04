"""S258 Phase 1.3 (A3) — Dedupe ROUND OFF Liability dupes on ROBDA + XMM.

Per probe (tmp/s258/probe_round_off.json):
- ROBDA: legacy `2120000 - ROUND OFF - ROBDA` is Liability w/ 2 GL postings
  (sum 0.80 Dr / 0.00 Cr = net -0.80 PHP on Liability convention).
  Path: JE transfer 0.80 from Liability to canonical Expense, then disable=1.
- XMM:   legacy `2120000 - ROUND OFF - XMM` is Liability w/ 0 GL postings.
  Path: just point tabCompany.round_off_account at canonical Expense, then disable=1.

Both companies have tabCompany.round_off_account currently = the Liability dupe.
Must UPDATE first, otherwise disabling would break the Company.

**DEVIATION FROM PLAN v1.2 P0-3 (logged D1-1):** Plan called for DELETE with
`flags.ignore_links=True`. In practice, `frappe.delete_doc` cannot delete an
Account that has GL Entries, even with `force=True` + `ignore_links=True` —
the GL Entry check is a separate validation. Canonical model Rule 2 also
mandates disable-don't-delete for records with transactional history. We
follow Rule 2: zero out balance via JE, then SET disabled=1. GL Entries
preserved (audit trail integrity).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (api_get, api_post, api_put, account_exists, set_company_field,
                  write_rollback_sql, log_action, sql_quote)


TARGETS = {
    "ROBDA": {
        "company": "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
        "legacy_liability": "2120000 - ROUND OFF - ROBDA",
        "canonical_expense": "Round Off - ROBDA",
        "cost_center": "Main - ROBDA",
    },
    "XMM": {
        "company": "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
        "legacy_liability": "2120000 - ROUND OFF - XMM",
        "canonical_expense": "Round Off - XMM",
        "cost_center": "Main - XMM",
    },
}


def gl_balance(account_name: str) -> tuple[float, float, int]:
    """Returns (debit_total, credit_total, active_count)."""
    res = api_get(
        "/api/resource/GL Entry",
        params={"fields": json.dumps(["debit", "credit", "is_cancelled"]),
                "filters": json.dumps([["account", "=", account_name]]),
                "limit_page_length": 0},
    )
    rows = res.get("data") or []
    active = [r for r in rows if not r.get("is_cancelled")]
    return (sum(float(r["debit"] or 0) for r in active),
            sum(float(r["credit"] or 0) for r in active),
            len(active))


def submit_je(company: str, expense_acc: str, liability_acc: str,
              amount: float, cost_center: str, remark: str) -> str:
    """Create + submit a Journal Entry. Returns voucher name."""
    payload = {
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": company,
        "posting_date": time.strftime("%Y-%m-%d"),
        "user_remark": remark,
        "accounts": [
            {"account": expense_acc,
             "debit_in_account_currency": amount,
             "credit_in_account_currency": 0,
             "cost_center": cost_center,
             "user_remark": remark},
            {"account": liability_acc,
             "debit_in_account_currency": 0,
             "credit_in_account_currency": amount,
             "cost_center": cost_center,
             "user_remark": remark},
        ],
    }
    # Insert draft
    res = api_post("/api/resource/Journal Entry", payload)
    data = res.get("data") or res
    je_name = data["name"]
    # Submit
    api_post(
        "/api/method/frappe.client.submit",
        {"doc": json.dumps({"doctype": "Journal Entry", "name": je_name})},
    )
    return je_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    summary = {"captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "dry_run": args.dry_run, "actions": []}
    rollback_lines = ["-- A3 rollback for ROBDA + XMM round-off dedup:"]

    for abbr, cfg in TARGETS.items():
        company = cfg["company"]
        legacy = cfg["legacy_liability"]
        canonical = cfg["canonical_expense"]
        cc = cfg["cost_center"]

        print(f"\n=== {abbr} = {company} ===")
        assert account_exists(legacy), f"FAIL: {legacy} missing"
        assert account_exists(canonical), f"FAIL: {canonical} missing"
        d, c, n = gl_balance(legacy)
        balance = c - d  # Liability convention: credit-debit
        print(f"  Legacy {legacy!r}: {n} active entries, Dr={d}, Cr={c}, balance={balance}")

        # Step 1 — capture current Company.round_off_account for rollback
        cur = api_get(f"/api/resource/Company/{company}",
                      params={"fields": json.dumps(["round_off_account"])})
        cur_pointer = (cur.get("data") or {}).get("round_off_account")
        print(f"  Company.round_off_account currently = {cur_pointer!r}")

        rollback_lines.append(
            f"UPDATE `tabCompany` SET round_off_account = {sql_quote(cur_pointer)} WHERE name = {sql_quote(company)};"
        )
        rollback_lines.append(
            f"UPDATE `tabAccount` SET disabled = 0 WHERE name = {sql_quote(legacy)};"
        )

        # Step 2 — point Company at canonical Expense FIRST
        if args.dry_run:
            print(f"  [DRY] SET tabCompany.round_off_account = {canonical!r}")
        else:
            set_company_field(company, "round_off_account", canonical)
            print(f"  SET tabCompany.round_off_account = {canonical}")
            log_action("1", "SET_FIELD", company, cur_pointer, canonical,
                       extras={"field": "round_off_account"})

        # Step 3 — JE transfer if balance != 0
        je_name = None
        if abs(balance) > 0.005:  # 1/2 cent threshold
            # Liability has net credit balance OR net debit balance.
            # If balance > 0 (more Cr than Dr): the Liability holds value — transfer Cr to Expense as a credit.
            # If balance < 0 (more Dr than Cr): the Liability is "negative" (overspent) — transfer the Dr position out.
            # Either way, mirror the imbalance back into canonical Expense:
            #   To zero out a Liability with net credit C: Dr Liability C, Cr Expense C? No — we want Expense to ABSORB the loss.
            # Practical: the legacy account currently has the rounding amount sitting there. We want canonical Expense to carry it.
            # ROBDA has 0.80 Dr on Liability (net = -0.80). Closing entry: Cr Liability 0.80, Dr Expense 0.80 → both zero out (mirrors original posting direction onto Expense).
            # Equivalently for net Cr balance: Dr Liability X, Cr Expense X.
            if balance < 0:
                # Net debit: close by Cr Liability + Dr Expense
                amount = abs(balance)
                je_lines = "Dr Expense / Cr Liability"
                expense_dr = amount
                expense_cr = 0
                liability_dr = 0
                liability_cr = amount
            else:
                # Net credit: close by Dr Liability + Cr Expense
                amount = balance
                je_lines = "Cr Expense / Dr Liability"
                expense_dr = 0
                expense_cr = amount
                liability_dr = amount
                liability_cr = 0
            print(f"  JE needed: amount={amount}, mode={je_lines}")
            remark = (f"S258 Phase 1.3 — close legacy Apex Liability ROUND OFF dupe; "
                      f"transfer {amount} PHP to canonical Expense Round Off. Per v1.2 P0-3 + canonical Rule 2 (disable-not-delete).")
            if args.dry_run:
                print(f"  [DRY] would submit JE: amount={amount} on company={company}")
            else:
                # Build payload manually since amount direction varies
                payload = {
                    "doctype": "Journal Entry",
                    "voucher_type": "Journal Entry",
                    "company": company,
                    "posting_date": time.strftime("%Y-%m-%d"),
                    "user_remark": remark,
                    "accounts": [
                        {"account": canonical,
                         "debit_in_account_currency": expense_dr,
                         "credit_in_account_currency": expense_cr,
                         "cost_center": cc,
                         "user_remark": remark},
                        {"account": legacy,
                         "debit_in_account_currency": liability_dr,
                         "credit_in_account_currency": liability_cr,
                         "cost_center": cc,
                         "user_remark": remark},
                    ],
                }
                res = api_post("/api/resource/Journal Entry", payload)
                data = res.get("data") or res
                je_name = data["name"]
                # Submit
                api_post(
                    "/api/method/frappe.client.submit",
                    {"doc": json.dumps({"doctype": "Journal Entry", "name": je_name})},
                )
                print(f"  SUBMITTED JE {je_name}")
                log_action("1", "SUBMIT_JE", je_name,
                           legacy, canonical,
                           extras={"amount": amount, "remark": remark})
                rollback_lines.append(
                    f"-- To rollback, cancel + amend JE {je_name} manually (cannot cancel submitted JE via SQL safely)"
                )
        else:
            print(f"  No JE needed (balance ~0)")

        # Step 4 — disable=1 the legacy Liability dupe
        if args.dry_run:
            print(f"  [DRY] SET tabAccount.disabled = 1 on {legacy}")
        else:
            api_put(f"/api/resource/Account/{legacy}", {"disabled": 1})
            print(f"  SET disabled=1 on {legacy}")
            log_action("1", "DISABLE_ACCOUNT", legacy, "active", "disabled",
                       extras={"reason": "Apex Liability ROUND OFF dupe; closed via JE; canonical Expense now used"})

        summary["actions"].append({
            "abbr": abbr, "company": company, "legacy": legacy, "canonical": canonical,
            "balance_before_je": balance, "je_voucher": je_name,
            "deviation_from_plan": "Followed canonical Rule 2 (disable-don't-delete) instead of v1.2 P0-3 DELETE-with-ignore_links",
        })

    if not args.dry_run:
        write_rollback_sql(1, rollback_lines)

    out = "tmp/s258/A3_dry_run.json" if args.dry_run else "output/s258/A3_summary.json"
    open(out, "w").write(json.dumps(summary, indent=2))
    print(f"\n[OK] Summary: {out}")


if __name__ == "__main__":
    main()
