"""S258 Phase 2.1 + 2.2 + 2.3 — Build 3 NEW canonical COA templates.

Inputs:
- data/_FINAL/COA_HEALTHY_REFERENCE.csv (the 114-stem store template from A4)
- Butch's 27-account Sales tree (Appendix C of the plan; cleanroom locked)
- Plan §"3-pattern" sub-tree population per role

Outputs:
- data/_FINAL/COA_TEMPLATE_HEAD_OFFICE.csv  (BEI Head Office pattern)
- data/_FINAL/COA_TEMPLATE_COMMISSARY.csv   (BKI Commissary pattern)
- data/_FINAL/COA_TEMPLATE_FRANCHISOR.csv   (BFC Franchisor pattern)

These templates are STRUCTURAL — agents in Phase 2.4/2.5/2.6/3 read these to know
which accounts to create on each Company. CSV columns match A4's HEALTHY template
plus a `role_populated` column flagging whether the row receives postings in this role.
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path


# Butch's 27-account canonical Sales tree (Appendix C of plan; cleanroom COA-175-001)
SALES_TREE = [
    # (account_number, account_name, is_group, parent_stem)
    ("4000000", "SALES", 1, None),
    ("4000100", "STORE SALES", 1, "SALES"),
    ("4000110", "IN-STORE SALES", 0, "STORE SALES"),
    ("4000120", "ONLINE SALES", 1, "STORE SALES"),
    ("4000121", "BEI WEBSITE", 0, "ONLINE SALES"),
    ("4000122", "FOOD PANDA", 0, "ONLINE SALES"),
    ("4000123", "GRAB", 0, "ONLINE SALES"),
    ("4000200", "BKI SALES", 1, "SALES"),
    ("4000210", "DELIVERIES", 0, "BKI SALES"),
    ("4000220", "LOGISTICS", 1, "BKI SALES"),
    ("4000221", "DELIVERY INCOME", 0, "LOGISTICS"),
    ("4000222", "LOGISTICS INCOME", 0, "LOGISTICS"),
    ("4000230", "FEES", 1, "SALES"),
    ("4000231", "ROYALTY FEES", 0, "FEES"),
    ("4000232", "MANAGEMENT FEES", 0, "FEES"),
    ("4000233", "FRANCHISE FEES", 0, "FEES"),
    ("4000234", "MARKETING FEES", 0, "FEES"),
    ("4000235", "E-COMMERCE FEES", 0, "FEES"),
    # Discount group + children per COA-175-002 (renumber)
    ("4000900", "DISCOUNTS AND PROMO", 1, "SALES"),
    ("4000901", "SALES DISCOUNT DUE TO FREE HALOHALO", 0, "DISCOUNTS AND PROMO"),
    ("4000902", "SALES DISCOUNTS OF PWDS", 0, "DISCOUNTS AND PROMO"),
    ("4000903", "SALES DISCOUNTS OF SENIOR CITIZENS", 0, "DISCOUNTS AND PROMO"),
    ("4000904", "SALES DISCOUNTS - PROMO", 0, "DISCOUNTS AND PROMO"),
    ("4000905", "SALES DISCOUNTS - EMPLOYEE", 0, "DISCOUNTS AND PROMO"),
    ("4000906", "SALES DISCOUNTS - REFUND", 0, "DISCOUNTS AND PROMO"),
    ("4000907", "SALES DISCOUNTS - GIFT CARDS", 0, "DISCOUNTS AND PROMO"),
    ("4000908", "SALES DISCOUNTS - OTHERS", 0, "DISCOUNTS AND PROMO"),
]


def write_template(out_path: str, role: str, populated_leaves: set[str], extras: list[tuple]):
    """Write a template CSV. populated_leaves = account_name stems that get postings.
    extras = list of (account_number, account_name, root_type, account_type, parent_stem, is_group)
    for role-specific accounts (e.g. Fork 1 scaffolding for Franchisor)."""
    rows = []
    # Common: 5-root tree
    for rt in ("Asset", "Liability", "Equity", "Income", "Expense"):
        rows.append({
            "account_number": "", "account_name": rt,
            "root_type": rt, "account_type": "",
            "parent_account_stem": "", "is_group": 1,
            "role_populated": "yes (root group; all roles)",
        })
    # Sales tree
    for num, name, is_grp, parent in SALES_TREE:
        rows.append({
            "account_number": num, "account_name": name,
            "root_type": "Income", "account_type": "Income Account" if not is_grp else "",
            "parent_account_stem": parent or "Income",
            "is_group": is_grp,
            "role_populated": ("yes" if name in populated_leaves or is_grp else "no — group/leaf reserved per Butch COA-175-003"),
        })
    # Role-specific extras
    for num, name, root, atype, parent, is_grp in extras:
        rows.append({
            "account_number": num, "account_name": name,
            "root_type": root, "account_type": atype,
            "parent_account_stem": parent, "is_group": is_grp,
            "role_populated": f"yes — {role} scaffolding",
        })
    # Asset/Liability/Equity/Expense stems from HEALTHY template (carry minimum store pattern)
    # For role-specific tweaks, downstream Phase 2.x/3.x scripts adapt.
    healthy_csv = Path("data/_FINAL/COA_HEALTHY_REFERENCE.csv")
    if healthy_csv.exists():
        with open(healthy_csv, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                # Skip Income tree (we have it inline above) + 5-root duplicates
                if r["root_type"] == "Income":
                    continue
                if r["account_name"] in ("Asset", "Liability", "Equity", "Income", "Expense"):
                    continue
                rows.append({
                    "account_number": r["account_number"],
                    "account_name": r["account_name"],
                    "root_type": r["root_type"],
                    "account_type": r["account_type"],
                    "parent_account_stem": r["parent_account_stem"],
                    "is_group": int(r["is_group"]) if r["is_group"] != "" else 0,
                    "role_populated": "yes (inherited from HEALTHY store template)",
                })
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "account_number", "account_name", "root_type", "account_type",
            "parent_account_stem", "is_group", "role_populated",
        ])
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # Head Office (BEI): populates 4000100 STORE SALES + 4000110 IN-STORE SALES
    # (BEI HQ may have its own walk-in) + 4000230 FEES sub-tree + 4000005 BRAND GROWTH
    # (kept per COA-175-016 as BEI-specific extension OUTSIDE canonical, added as extra)
    ho_populated = {"IN-STORE SALES", "MARKETING FEES", "E-COMMERCE FEES"}
    ho_extras = [
        ("4000005", "BRAND GROWTH FEE INCOME", "Income", "Income Account",
         "Income", 0),
    ]
    n_ho = write_template("data/_FINAL/COA_TEMPLATE_HEAD_OFFICE.csv",
                          "Head Office", ho_populated, ho_extras)
    print(f"  Head Office template: {n_ho} rows")

    # Commissary (BKI): populates ONLY 4000200 BKI SALES sub-tree (per COA-175-011)
    com_populated = {"DELIVERIES", "DELIVERY INCOME", "LOGISTICS INCOME"}
    com_extras = []  # No commissary-specific scaffolding beyond Sales tree
    n_com = write_template("data/_FINAL/COA_TEMPLATE_COMMISSARY.csv",
                           "Commissary", com_populated, com_extras)
    print(f"  Commissary template: {n_com} rows")

    # Franchisor (BFC): populates ONLY 4000230 FEES sub-tree (Royalty/Mgmt/Franchise/Mktg/E-Com)
    # + Fork 1 scaffolding per COA-175-013/015: 1104200 DUE FROM BEI on BFC + 2102205 OUTPUT VAT PAYABLE
    fr_populated = {"ROYALTY FEES", "MANAGEMENT FEES", "FRANCHISE FEES",
                    "MARKETING FEES", "E-COMMERCE FEES"}
    fr_extras = [
        ("1104200", "DUE FROM BEI", "Asset", "Receivable", "Asset", 0),
        ("2102205", "OUTPUT VAT PAYABLE", "Liability", "Tax", "Liability", 0),
    ]
    n_fr = write_template("data/_FINAL/COA_TEMPLATE_FRANCHISOR.csv",
                          "Franchisor", fr_populated, fr_extras)
    print(f"  Franchisor template: {n_fr} rows")

    print(f"\nAll 3 templates written to data/_FINAL/")


if __name__ == "__main__":
    main()
