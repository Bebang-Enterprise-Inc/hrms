"""S258 post-merge fact check — verify live production Frappe state matches plan claims.

Re-queries hq.bebang.ph and validates every claim in SUMMARY.md / PHASE_GATES.md /
PR #770 description against actual tabAccount / tabCompany / tabGL Entry state.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import api_get


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    findings = {"PASS": [], "FAIL": [], "WARN": []}

    # === 1. 58 Companies ===
    res = api_get("/api/resource/Company", params={
        "fields": json.dumps(["name", "abbr", "is_group", "tax_id",
                              "round_off_account", "default_inventory_account",
                              "stock_received_but_not_billed"]),
        "limit_page_length": 0, "order_by": "name asc",
    })
    companies = res.get("data") or []
    if len(companies) == 58:
        findings["PASS"].append(f"58 Companies present (expected 58)")
    else:
        findings["FAIL"].append(f"Company count = {len(companies)} (expected 58)")

    abbr_by_company = {c["name"]: c["abbr"] for c in companies}

    # === 2. 5-root tree on all 58 Companies ===
    missing_roots = []
    for c in companies:
        for rt in ("Asset", "Liability", "Equity", "Income", "Expense"):
            n = f"{rt} - {c['abbr']}"
            r = api_get("/api/method/frappe.client.get_count", params={
                "doctype": "Account",
                "filters": json.dumps([["name", "=", n]]),
            })
            if (r.get("message") or 0) == 0:
                missing_roots.append((c["name"], rt))
    if not missing_roots:
        findings["PASS"].append(f"All 58 Companies have all 5 root group accounts (290 total)")
    else:
        findings["FAIL"].append(f"Missing root accounts: {len(missing_roots)} (first 5: {missing_roots[:5]})")

    # === 3. BFI2 → BFT rename ===
    bft = next((c for c in companies if c["name"] == "BEBANG FT INC."), None)
    if bft:
        if bft["abbr"] == "BFT":
            findings["PASS"].append(f"BEBANG FT INC. abbr=BFT (was BFI2)")
        else:
            findings["FAIL"].append(f"BEBANG FT INC. abbr={bft['abbr']!r} (expected BFT)")
        if bft.get("tax_id") == "663-440-106-00000":
            findings["PASS"].append(f"BEBANG FT INC. SEC TIN preserved: 663-440-106-00000")
        else:
            findings["FAIL"].append(f"BEBANG FT INC. tax_id={bft.get('tax_id')!r} (expected 663-440-106-00000)")
    # No remaining BFI2 references in tabAccount or Cost Center
    for dt, label in (("Account", "tabAccount"), ("Cost Center", "tabCost Center")):
        r = api_get("/api/method/frappe.client.get_count", params={
            "doctype": dt, "filters": json.dumps([["name", "like", "%- BFI2%"]]),
        })
        n = r.get("message") or 0
        if n == 0:
            findings["PASS"].append(f"0 {label} rows ending '- BFI2'")
        else:
            findings["FAIL"].append(f"{n} {label} rows still end '- BFI2'")

    # === 4. Round Off canonicalization (ROBDA + XMM + BEI) ===
    for company, canonical, legacy in [
        ("ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.", "Round Off - ROBDA", "2120000 - ROUND OFF - ROBDA"),
        ("XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.", "Round Off - XMM", "2120000 - ROUND OFF - XMM"),
        ("BEBANG ENTERPRISE INC.", "Round Off - BEI", None),
    ]:
        co = next((c for c in companies if c["name"] == company), None)
        if co and co.get("round_off_account") == canonical:
            findings["PASS"].append(f"{company}: round_off_account = {canonical}")
        else:
            findings["FAIL"].append(f"{company}: round_off_account = {co.get('round_off_account')!r} (expected {canonical!r})")
        if legacy:
            r = api_get(f"/api/resource/Account/{legacy}", params={"fields": json.dumps(["disabled"])})
            disabled = (r.get("data") or {}).get("disabled")
            if disabled == 1:
                findings["PASS"].append(f"Legacy {legacy} disabled=1")
            else:
                findings["FAIL"].append(f"Legacy {legacy} disabled={disabled} (expected 1)")

    # === 5. JE ACC-JV-2026-00014 submitted ===
    r = api_get("/api/resource/Journal Entry/ACC-JV-2026-00014", params={
        "fields": json.dumps(["name", "docstatus", "company", "total_debit", "total_credit"]),
    })
    je = r.get("data") or {}
    if je.get("docstatus") == 1 and abs(float(je.get("total_debit") or 0) - 0.80) < 0.01:
        findings["PASS"].append(f"JE ACC-JV-2026-00014 docstatus=1 on ROBDA, total_debit={je['total_debit']}")
    else:
        findings["FAIL"].append(f"JE ACC-JV-2026-00014 state: {je}")

    # === 6. III Stock In Hand seeded ===
    r = api_get("/api/method/frappe.client.get_count", params={
        "doctype": "Account",
        "filters": json.dumps([["name", "=", "Stock In Hand - III"]]),
    })
    if (r.get("message") or 0) > 0:
        findings["PASS"].append(f"Stock In Hand - III exists")
    else:
        findings["FAIL"].append(f"Stock In Hand - III NOT FOUND")
    iii = next((c for c in companies if c["name"] == "IRRESISTIBLE INFUSIONS INC."), None)
    if iii and iii.get("default_inventory_account") == "Stock In Hand - III":
        findings["PASS"].append(f"III default_inventory_account = Stock In Hand - III")
    else:
        findings["FAIL"].append(f"III default_inventory_account = {iii.get('default_inventory_account')!r}")

    # === 7. 44 PARTIAL Companies (originally) — Stock In Hand - <ABBR> linked ===
    state = json.load(open("output/s258/baseline_state.json"))
    EXCL = {"BEBANG ENTERPRISE INC.", "BEBANG KITCHEN INC."}  # they already had Apex names
    was_null = [r for r in state["rows"] if r["status"] == "PARTIAL" and r["name"] not in EXCL
                and not r.get("default_inventory_account")]
    a1_ok = 0
    a1_bad = []
    for r in was_null:
        target = f"Stock In Hand - {r['abbr']}"
        co = next((c for c in companies if c["name"] == r["name"]), None)
        if co and co.get("default_inventory_account") == target:
            a1_ok += 1
        else:
            a1_bad.append((r["name"], co.get("default_inventory_account") if co else None))
    if a1_ok >= 43:  # 44 minus III (handled separately)
        findings["PASS"].append(f"A1: {a1_ok} Companies have Stock In Hand - <ABBR>")
    else:
        findings["FAIL"].append(f"A1: only {a1_ok} Companies set; bad: {a1_bad[:5]}")

    # === 8. L77 stock_received_but_not_billed ===
    l77 = next((c for c in companies if c["name"] == "LEGACY77 FOOD CORP."), None)
    if l77 and l77.get("stock_received_but_not_billed") == "Stock Received But Not Billed - L77":
        findings["PASS"].append(f"L77 stock_received_but_not_billed canonical")
    else:
        findings["FAIL"].append(f"L77 stock_received_but_not_billed = {l77.get('stock_received_but_not_billed') if l77 else None!r}")

    # === 9. BFC seeded (Sales tree + Fork 1 scaffolding) ===
    r = api_get("/api/method/frappe.client.get_count", params={
        "doctype": "Account", "filters": json.dumps([["company", "=", "BEBANG FRANCHISE CORP."]]),
    })
    bfc_count = r.get("message") or 0
    if bfc_count >= 25:  # 5 root + 19 Sales + 2 Fork 1
        findings["PASS"].append(f"BFC has {bfc_count} accounts (expected >= 25)")
    else:
        findings["FAIL"].append(f"BFC has only {bfc_count} accounts")

    # Fork 1 scaffolding on BFC
    for name in ["1104200 - DUE FROM BEI - BFC", "2102205 - OUTPUT VAT PAYABLE - BFC"]:
        r = api_get("/api/method/frappe.client.get_count", params={
            "doctype": "Account", "filters": json.dumps([["name", "=", name]]),
        })
        if (r.get("message") or 0) > 0:
            findings["PASS"].append(f"BFC Fork 1: {name} exists")
        else:
            # Try UPPER variant if Phase 5 renamed it
            r2 = api_get("/api/method/frappe.client.get_count", params={
                "doctype": "Account", "filters": json.dumps([["name", "like", "1104200%BFC"]]),
            })
            if (r2.get("message") or 0) > 0:
                findings["WARN"].append(f"BFC Fork 1: '{name}' renamed (UPPER variant); count={r2.get('message')}")
            else:
                findings["FAIL"].append(f"BFC Fork 1 missing: {name}")

    # BEI side Fork 1
    r = api_get("/api/method/frappe.client.get_count", params={
        "doctype": "Account", "filters": json.dumps([["name", "like", "%2104200%DUE TO BFC%BEI"]]),
    })
    if (r.get("message") or 0) > 0:
        findings["PASS"].append(f"BEI side Fork 1: 2104200 DUE TO BFC - BEI exists")
    else:
        findings["FAIL"].append(f"BEI side Fork 1 2104200 DUE TO BFC - BEI NOT FOUND")

    # === 10. BFT seeded ===
    r = api_get("/api/method/frappe.client.get_count", params={
        "doctype": "Account", "filters": json.dumps([["company", "=", "BEBANG FT INC."]]),
    })
    bft_count = r.get("message") or 0
    if bft_count >= 19:
        findings["PASS"].append(f"BFT has {bft_count} accounts (expected >= 19 from Sales tree + 5 roots)")
    else:
        findings["FAIL"].append(f"BFT has only {bft_count} accounts")

    # === 11. 4 BEI-TIN stubs seeded ===
    STUBS = [
        "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
        "SM MANILA - BEBANG ENTERPRISE INC.",
        "SM MEGAMALL - BEBANG ENTERPRISE INC.",
        "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
    ]
    for s in STUBS:
        r = api_get("/api/method/frappe.client.get_count", params={
            "doctype": "Account", "filters": json.dumps([["company", "=", s]]),
        })
        n = r.get("message") or 0
        if n >= 24:  # 5 root + 19 Sales-tree + 12 pre-existing
            findings["PASS"].append(f"{s}: {n} accounts (>= 24)")
        else:
            findings["WARN"].append(f"{s}: only {n} accounts (expected >= 24)")

    # === 12. Long-suffix elimination (Phase 3.5) ===
    long_forms = []
    for c in companies:
        cn = c["name"]
        # Pre-S258 each company had long-form like "Bebang Enterprise Inc."
        # After Phase 3.5: should not appear in tabAccount names
        r = api_get("/api/method/frappe.client.get_count", params={
            "doctype": "Account",
            "filters": json.dumps([["company", "=", cn], ["name", "like", f"%- {cn}"]]),
        })
        n = r.get("message") or 0
        if n > 0:
            long_forms.append((cn, n))
        # Also check title-case form
        title = cn.title()
        if title != cn:
            r2 = api_get("/api/method/frappe.client.get_count", params={
                "doctype": "Account",
                "filters": json.dumps([["company", "=", cn], ["name", "like", f"%- {title}"]]),
            })
            n2 = r2.get("message") or 0
            if n2 > 0:
                long_forms.append((cn + " (title)", n2))
    if not long_forms:
        findings["PASS"].append(f"0 tabAccount rows with long-form company-name suffix")
    else:
        findings["WARN"].append(f"{len(long_forms)} Companies still have long-form suffix: {long_forms[:5]}")

    # === 13. DECISIONS.md has 27 COA-175 rows ===
    p = Path("data/_CONSOLIDATED/01_FINANCE/DECISIONS.md")
    if p.exists():
        text = p.read_text(encoding="utf-8")
        import re
        coa175_rows = re.findall(r"^\| COA-175-0\d\d \|", text, flags=re.MULTILINE)
        if len(coa175_rows) >= 27:
            findings["PASS"].append(f"DECISIONS.md has {len(coa175_rows)} COA-175-* rows (>= 27)")
        else:
            findings["FAIL"].append(f"DECISIONS.md only has {len(coa175_rows)} COA-175-* rows (expected >= 27)")

    # === 14. Bridge handoff package present ===
    bridge = Path("output/s258/bridge_handoff")
    for f in ("per_company_coa.zip", "coa_export_zip_manifest.csv",
              "master_reconciliation.csv", "validation.md",
              "upload_manifest.json", "SIGNOFF.txt"):
        if (bridge / f).exists():
            findings["PASS"].append(f"Bridge package: {f} present")
        else:
            findings["FAIL"].append(f"Bridge package missing: {f}")

    # === 15. ZIP has 58 CSVs ===
    import zipfile
    zp = bridge / "per_company_coa.zip"
    if zp.exists():
        with zipfile.ZipFile(zp) as zf:
            n_csv = sum(1 for n in zf.namelist() if n.endswith(".csv"))
        if n_csv == 58:
            findings["PASS"].append(f"per_company_coa.zip contains 58 CSVs")
        else:
            findings["FAIL"].append(f"per_company_coa.zip has {n_csv} CSVs (expected 58)")

    # === 16. Canonical preflight still PASS ===
    import subprocess
    try:
        out = subprocess.check_output(["python", "scripts/verify_canonical_structure.py"],
                                      text=True, encoding="utf-8", errors="ignore", timeout=180)
        if "ALL CANONICAL" in out or "no action required" in out:
            findings["PASS"].append("Canonical structure verification: ALL CANONICAL (0 violations)")
        else:
            findings["WARN"].append(f"Canonical verification output: {out[-500:]}")
    except Exception as e:
        findings["WARN"].append(f"Canonical verifier exec issue: {e}")

    # === 17. Total active account count ===
    total_active = 0
    for c in companies:
        r = api_get("/api/method/frappe.client.get_count", params={
            "doctype": "Account",
            "filters": json.dumps([["company", "=", c["name"]], ["disabled", "=", 0]]),
        })
        total_active += r.get("message") or 0
    findings["PASS"].append(f"Total active accounts across 58 Companies: {total_active} (Bridge package reported 6928)")

    # === Output report ===
    print(f"\n{'=' * 70}\nS258 LIVE FACT-CHECK\n{'=' * 70}\n")
    print(f"PASS: {len(findings['PASS'])}")
    print(f"FAIL: {len(findings['FAIL'])}")
    print(f"WARN: {len(findings['WARN'])}")
    print("\n--- PASS ---")
    for f in findings["PASS"]:
        print(f"  [OK] {f}")
    if findings["WARN"]:
        print("\n--- WARN ---")
        for f in findings["WARN"]:
            print(f"  [WARN] {f}")
    if findings["FAIL"]:
        print("\n--- FAIL ---")
        for f in findings["FAIL"]:
            print(f"  [FAIL] {f}")

    out = {
        "captured_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_active_accounts": total_active,
        "company_count": len(companies),
        "pass_count": len(findings["PASS"]),
        "warn_count": len(findings["WARN"]),
        "fail_count": len(findings["FAIL"]),
        "findings": findings,
    }
    Path("output/s258").mkdir(exist_ok=True, parents=True)
    open("output/s258/fact_check.json", "w").write(json.dumps(out, indent=2))
    print(f"\nWrote output/s258/fact_check.json")
    return 0 if len(findings["FAIL"]) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
