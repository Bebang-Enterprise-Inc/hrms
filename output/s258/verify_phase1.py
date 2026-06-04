"""S258 Phase 1 verification — assert A1+A2+A3+A4+A5 final state via live API."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "coa_fix"))
from _lib import api_get  # type: ignore


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    state = json.load(open("output/s258/baseline_state.json"))
    failures = []

    # A1 — 43 PARTIAL Companies (excluding BEI + BKI + III) now have default_inventory_account
    # III is a is_group=1 root holdco; creating a leaf there cascades to all 57 children
    # and a sibling child's docname differs (`CURRENT ASSETS` cascade rule). Phase 3a will
    # create canonical inventory on III via bench-execute with ignore_root_company_validation.
    EXCL = {"BEBANG ENTERPRISE INC.", "BEBANG KITCHEN INC.", "IRRESISTIBLE INFUSIONS INC."}
    partial_was_null = [r for r in state["rows"]
                        if r["status"] == "PARTIAL" and r["name"] not in EXCL
                        and not r.get("default_inventory_account")]
    print(f"A1: checking {len(partial_was_null)} Companies that had default_inventory_account=NULL (excludes BEI+BKI+III)")
    a1_pass = 0
    for r in partial_was_null:
        target = f"Stock In Hand - {r['abbr']}"
        live = api_get(f"/api/resource/Company/{r['name']}",
                       params={"fields": json.dumps(["default_inventory_account"])})
        cur = (live.get("data") or {}).get("default_inventory_account")
        if cur == target:
            a1_pass += 1
        else:
            failures.append(f"A1: {r['name']} default_inventory_account={cur!r} (want {target!r})")
    assert a1_pass == len(partial_was_null), f"A1: {a1_pass}/{len(partial_was_null)} set correctly"
    print(f"  A1 PASS: {a1_pass}/{len(partial_was_null)} (III deferred to Phase 3a)")

    # A2 — L77 stock_received_but_not_billed
    live = api_get("/api/resource/Company/LEGACY77 FOOD CORP.",
                   params={"fields": json.dumps(["stock_received_but_not_billed"])})
    cur = (live.get("data") or {}).get("stock_received_but_not_billed")
    assert cur == "Stock Received But Not Billed - L77", f"A2 FAIL: L77 srbnb={cur!r}"
    print(f"  A2 PASS: L77 stock_received_but_not_billed = {cur!r}")

    # A3 — ROBDA + XMM round_off pointers + legacy disabled
    for abbr, company, canonical, legacy in [
        ("ROBDA", "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.", "Round Off - ROBDA", "2120000 - ROUND OFF - ROBDA"),
        ("XMM",   "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",    "Round Off - XMM",   "2120000 - ROUND OFF - XMM"),
    ]:
        co = api_get(f"/api/resource/Company/{company}",
                     params={"fields": json.dumps(["round_off_account"])})
        cur = (co.get("data") or {}).get("round_off_account")
        assert cur == canonical, f"A3 FAIL: {abbr} round_off_account={cur!r} (want {canonical!r})"
        legacy_doc = api_get(f"/api/resource/Account/{legacy}",
                             params={"fields": json.dumps(["disabled"])})
        legacy_disabled = (legacy_doc.get("data") or {}).get("disabled")
        assert legacy_disabled == 1, f"A3 FAIL: {legacy!r} disabled={legacy_disabled}"
        print(f"  A3 PASS: {abbr} canonical pointer + legacy disabled=1")

    # A4 — COA_HEALTHY_REFERENCE.csv with at least 100 rows
    p = Path("data/_FINAL/COA_HEALTHY_REFERENCE.csv")
    assert p.exists(), f"A4 FAIL: {p} missing"
    rows = p.read_text(encoding="utf-8").splitlines()
    assert len(rows) >= 100, f"A4 FAIL: only {len(rows)} lines"
    print(f"  A4 PASS: {p} has {len(rows) - 1} data rows")

    # A5 — BEBANG FT INC. abbr = BFT; zero tabAccount '- BFI2' rows
    bft = api_get("/api/resource/Company/BEBANG FT INC.",
                  params={"fields": json.dumps(["abbr", "tax_id"])})
    abbr = (bft.get("data") or {}).get("abbr")
    tax = (bft.get("data") or {}).get("tax_id")
    assert abbr == "BFT", f"A5 FAIL: BEBANG FT INC. abbr={abbr!r}"
    assert tax == "663-440-106-00000", f"A5 FAIL: BEBANG FT INC. tax_id={tax!r} (SEC TIN preserved)"
    # Count remaining '- BFI2' rows in tabAccount
    bfi2_acc = api_get("/api/method/frappe.client.get_count",
                       params={"doctype": "Account",
                               "filters": json.dumps([["name", "like", "%- BFI2%"]])})
    assert (bfi2_acc.get("message") or 0) == 0, f"A5 FAIL: {bfi2_acc.get('message')} tabAccount rows still end in '- BFI2'"
    bfi2_cc = api_get("/api/method/frappe.client.get_count",
                      params={"doctype": "Cost Center",
                              "filters": json.dumps([["name", "like", "%- BFI2%"]])})
    assert (bfi2_cc.get("message") or 0) == 0, f"A5 FAIL: {bfi2_cc.get('message')} Cost Center rows still end in '- BFI2'"
    print(f"  A5 PASS: BEBANG FT INC. abbr={abbr}, tax_id preserved, 0 BFI2 references")

    if failures:
        print(f"\nFAIL ({len(failures)} issues):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nPASS: Phase 1 verification — all assertions met (A1+A2+A3+A4+A5)")
    print("NOTE: Phase 1.3.5 (BEI round_off canonicalization) DEFERRED to Phase 3c")
    print("      — REST API cannot bypass root_company_validation; Phase 3c rewrite handles it")
    print("        natively after Phase 3a seeds canonical 5-root tree on all 58 Companies.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
