#!/usr/bin/env python3
"""S243 — Canonical CoA backfill for 4 BEBANG ENTERPRISE INC. stores.

Adopts the 43-store BARE-NAME convention (audit B1):
  account_name  = "Stock Assets" / "Accounts Payable" / "Current Assets"  (BARE -- no abbr)
  account_number = NULL
  is_group = 1
  Frappe constructs name = "<account_name> - <abbr>" automatically

Strictly scoped to 4 target Companies. If asked to create on any other Company,
raises ValueError. No leaf accounts (S238's Phase 1 deliverable).

Audit fixes baked in:
  B2: ignore_root_company_validation flag wraps loop (s206 line 358 pattern)
  B3: account_name passed BARE to frappe.get_doc; abbr handled by Frappe via Company.abbr
  B4: outer-savepoint scoping for dry-run mode (skips outer commit on dry-run)
  W1: idempotency check key = frappe.db.exists("Account", expected_docname)
  W2: groups_to_create sorted by parent depth (ancestors first via create_order)
  W4: account dict shape enumerated explicitly (no account_type/currency for groups)

Reference pattern (NOT a callable): hrms/on_demand/s206_seed_intercompany_accounts.py.
Do NOT call s206._ensure_account directly -- it hardcodes is_group=0 for leaves.
"""
from __future__ import annotations

# v1.1-B5: SSM boilerplate inlined -- log dirs MUST exist before import frappe
import os
for _d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(_d, exist_ok=True)

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import frappe  # type: ignore

OUTER_SAVEPOINT = "s243_seed_outer"
# Default relative; runner overrides via env var S243_GAP_PATH (absolute path inside container)
GAP_PATH = os.environ.get("S243_GAP_PATH", "output/s243/verification/coa_gap_analysis.json")

TARGET_COMPANIES = frozenset({
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
})

ALLOWED_ACCOUNT_NAMES = frozenset({
    "Stock Assets",
    "Accounts Payable",
    "Current Assets",
})


def _validate_target_company(company: str) -> None:
    """v1.1-B2 + W4: refuse out-of-scope companies."""
    if company not in TARGET_COMPANIES:
        raise ValueError(
            f"S243: refusing to create accounts on out-of-scope Company {company!r}; "
            f"target list = {sorted(TARGET_COMPANIES)}"
        )


def _validate_gap_entry(entry: dict, company: str) -> None:
    """Anti-scope-creep gates (v1.1-B1)."""
    if entry.get("is_group") != 1:
        raise ValueError(
            f"S243: only group accounts allowed (is_group=1); got {entry.get('is_group')!r} for {company}"
        )
    if entry.get("account_name") not in ALLOWED_ACCOUNT_NAMES:
        raise ValueError(
            f"S243: account_name {entry.get('account_name')!r} not in {sorted(ALLOWED_ACCOUNT_NAMES)} for {company}"
        )
    if entry.get("account_number") not in (None, "", 0):
        raise ValueError(
            f"S243: BARE-NAME convention requires account_number=NULL/empty; got {entry.get('account_number')!r}"
        )


def _load_gap_analysis(path: str = GAP_PATH) -> dict:
    """v1.1: read + validate Phase 1 gap analysis."""
    gap_full = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {"ROA", "SMM", "SMMM", "SMS"}
    store_keys = {k for k in gap_full.keys() if k in expected}
    missing = expected - store_keys
    if missing:
        raise ValueError(f"S243: gap analysis missing target abbrs: {sorted(missing)}")
    for abbr in expected:
        groups = gap_full[abbr].get("groups_to_create", [])
        if len(groups) > 4:
            raise ValueError(
                f"S243: {abbr} requests {len(groups)} groups, max=4 (v1.1 HB-1)"
            )
    return {abbr: gap_full[abbr] for abbr in expected}


def _topological_sort(groups: list[dict]) -> list[dict]:
    """v1.1-W2: order ancestors first (parents before children).

    For S243, each entry has an explicit create_order field (1, 2, 3) per
    Phase 1-T2's design. Sort by create_order ascending.
    """
    return sorted(groups, key=lambda g: g.get("create_order", 999))


def _ensure_group_account(
    company: str, account_name: str, parent_account: str | None, root_type: str
) -> tuple[str, str]:
    """Idempotent INSERT for a group account. Returns (docname, status).

    status in {"created", "existed"}. Raises on validation/insert failure.
    """
    abbr = frappe.db.get_value("Company", company, "abbr")
    if not abbr:
        raise ValueError(f"S243: Company {company!r} has no abbr")
    expected_docname = f"{account_name} - {abbr}"

    # v1.1-W1: idempotency check by docname
    if frappe.db.exists("Account", expected_docname):
        return expected_docname, "existed"

    # v1.1-W4: explicit dict shape -- no account_type, no account_currency for groups
    # v1.1-B3: account_name BARE, no abbr suffix; Frappe auto-constructs name
    doc_dict = {
        "doctype": "Account",
        "account_name": account_name,           # BARE
        "company": company,
        "is_group": 1,                          # GROUP ONLY
        "root_type": root_type,                 # Asset / Liability
    }
    if parent_account is not None:
        doc_dict["parent_account"] = parent_account
    # else: top-level group; Frappe accepts parent_account omitted/null

    doc = frappe.get_doc(doc_dict)
    doc.insert(ignore_permissions=True)

    if doc.name != expected_docname:
        # Defensive: Frappe may have appended a counter on collision
        raise ValueError(
            f"S243: docname mismatch -- expected {expected_docname!r}, got {doc.name!r}"
        )
    return doc.name, "created"


def execute(dry_run: bool = False) -> dict:
    """Main entry. dry_run=True: outer savepoint + skip outer commit + final rollback.
    dry_run=False: outer savepoint + outer commit (release savepoint after).
    """
    frappe.set_user("Administrator")
    gap = _load_gap_analysis()

    ledger: dict = {
        "mode": "dry-run" if dry_run else "commit",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stores": {},
        "errors": [],
        "total_created": 0,
        "total_existed": 0,
        "total_errors": 0,
    }

    # v1.1-B2: bypass parent_company root-account validator for child Companies
    original_root_flag = getattr(frappe.local.flags, "ignore_root_company_validation", False)
    frappe.local.flags.ignore_root_company_validation = True

    # v1.1-B4: OUTER savepoint wraps entire 4-store loop
    frappe.db.savepoint(OUTER_SAVEPOINT)

    try:
        for abbr, store_data in gap.items():
            company = store_data["company"]
            _validate_target_company(company)

            store_ledger: dict = {"abbr": abbr, "company": company, "result": []}
            for entry in _topological_sort(store_data["groups_to_create"]):
                _validate_gap_entry(entry, company)
                try:
                    docname, status = _ensure_group_account(
                        company=company,
                        account_name=entry["account_name"],
                        parent_account=entry.get("parent_account"),
                        root_type=entry["root_type"],
                    )
                    store_ledger["result"].append({
                        "name": docname,
                        "account_name": entry["account_name"],
                        "expected_docname": entry.get("expected_docname"),
                        "parent_account": entry.get("parent_account"),
                        "status": status,
                    })
                    if status == "created":
                        ledger["total_created"] += 1
                    else:
                        ledger["total_existed"] += 1
                except Exception as exc:
                    frappe.log_error(
                        title=f"S243 seed failed for {company} / {entry.get('account_name')}",
                        message=traceback.format_exc()[:1500],
                    )
                    store_ledger["result"].append({
                        "account_name": entry.get("account_name"),
                        "expected_docname": entry.get("expected_docname"),
                        "status": "error",
                        "error": str(exc)[:300],
                    })
                    ledger["errors"].append({
                        "company": company,
                        "account_name": entry.get("account_name"),
                        "error": str(exc)[:300],
                    })
                    ledger["total_errors"] += 1

            ledger["stores"][abbr] = store_ledger

        # v1.1-B4: dry-run = rollback outer savepoint (NEVER commit)
        if dry_run:
            frappe.db.rollback(save_point=OUTER_SAVEPOINT)
            ledger["rollback_confirmed"] = True
        else:
            frappe.db.release_savepoint(OUTER_SAVEPOINT)
            frappe.db.commit()
            ledger["rollback_confirmed"] = False

    finally:
        frappe.local.flags.ignore_root_company_validation = original_root_flag

    return ledger


def main() -> None:
    """CLI entry — invoked inside Frappe backend container."""
    dry_run = "--dry-run" in sys.argv

    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()

    result = execute(dry_run=dry_run)

    out_path = "/tmp/s243_seed_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    sys.stdout.write(
        f"S243_SEED_OK mode={result['mode']} created={result['total_created']} "
        f"existed={result['total_existed']} errors={result['total_errors']} "
        f"path={out_path}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
