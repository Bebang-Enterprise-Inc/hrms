"""S258 batched SSM: 1.3.5 BEI round_off + A1-III retry + Phase 2.4 BFC + Phase 2.5 BFT
+ Phase 2.6 4-stub seeds. All under the now-seeded canonical 5-root tree.
"""
from __future__ import annotations
import base64
import sys
import time

import boto3


SCRIPT = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files"]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True
frappe.flags.in_migrate = True


def create_account(name, account_name, parent_account, company, is_group,
                   account_type, root_type, account_currency="PHP",
                   account_number=""):
    if frappe.db.exists("Account", name):
        return "exists"
    doc = frappe.get_doc({
        "doctype": "Account", "account_name": account_name,
        "parent_account": parent_account or "",
        "company": company, "is_group": int(is_group),
        "root_type": root_type, "account_type": account_type or "",
        "account_currency": account_currency,
        "account_number": account_number or "",
    })
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_permissions = True
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    return "created"


REPORT = {"Asset":"Balance Sheet","Liability":"Balance Sheet","Equity":"Balance Sheet",
          "Income":"Profit and Loss","Expense":"Profit and Loss"}


# === Step 1: Stock In Hand - III (A1-III retry) ===
print("=== A1-III ===")
r = create_account(
    name="Stock In Hand - III", account_name="Stock In Hand",
    parent_account="Asset - III", company="IRRESISTIBLE INFUSIONS INC.",
    is_group=0, account_type="Stock", root_type="Asset",
)
print(f"  Stock In Hand - III: {r}")
if r == "created":
    frappe.db.set_value("Company", "IRRESISTIBLE INFUSIONS INC.", "default_inventory_account",
                        "Stock In Hand - III", update_modified=True)
    print("  SET tabCompany.default_inventory_account on III")


# === Step 2: Round Off - BEI (1.3.5 retry) ===
print("\n=== 1.3.5 BEI Round Off canonical ===")
r = create_account(
    name="Round Off - BEI", account_name="Round Off",
    parent_account="Expense - BEI", company="BEBANG ENTERPRISE INC.",
    is_group=0, account_type="Round Off", root_type="Expense",
)
print(f"  Round Off - BEI: {r}")
frappe.db.set_value("Company", "BEBANG ENTERPRISE INC.", "round_off_account",
                    "Round Off - BEI", update_modified=True)
print("  SET tabCompany.round_off_account = 'Round Off - BEI' on BEI")


# === Step 3: BFC seed (Phase 2.4 B1) — Franchisor template ===
print("\n=== 2.4 BFC seed ===")
BFC = "BEBANG FRANCHISE CORP."
# Mark first_provision_done = 1 to bypass auto_provision hook (D0-3 mitigation already in flags)
created_bfc = 0
# Income tree (Butch's 27-account Sales tree) — only 4000230 FEES sub-tree populates for BFC
sales_tree = [
    ("4000000","SALES",1,None,"Income",""),
    ("4000100","STORE SALES",1,"4000000 - SALES - BFC","Income",""),
    ("4000110","IN-STORE SALES",0,"4000100 - STORE SALES - BFC","Income","Income Account"),
    ("4000120","ONLINE SALES",1,"4000100 - STORE SALES - BFC","Income",""),
    ("4000121","BEI WEBSITE",0,"4000120 - ONLINE SALES - BFC","Income","Income Account"),
    ("4000122","FOOD PANDA",0,"4000120 - ONLINE SALES - BFC","Income","Income Account"),
    ("4000123","GRAB",0,"4000120 - ONLINE SALES - BFC","Income","Income Account"),
    ("4000200","BKI SALES",1,"4000000 - SALES - BFC","Income",""),
    ("4000210","DELIVERIES",0,"4000200 - BKI SALES - BFC","Income","Income Account"),
    ("4000220","LOGISTICS",1,"4000200 - BKI SALES - BFC","Income",""),
    ("4000221","DELIVERY INCOME",0,"4000220 - LOGISTICS - BFC","Income","Income Account"),
    ("4000222","LOGISTICS INCOME",0,"4000220 - LOGISTICS - BFC","Income","Income Account"),
    ("4000230","FEES",1,"4000000 - SALES - BFC","Income",""),
    ("4000231","ROYALTY FEES",0,"4000230 - FEES - BFC","Income","Income Account"),
    ("4000232","MANAGEMENT FEES",0,"4000230 - FEES - BFC","Income","Income Account"),
    ("4000233","FRANCHISE FEES",0,"4000230 - FEES - BFC","Income","Income Account"),
    ("4000234","MARKETING FEES",0,"4000230 - FEES - BFC","Income","Income Account"),
    ("4000235","E-COMMERCE FEES",0,"4000230 - FEES - BFC","Income","Income Account"),
    ("4000900","DISCOUNTS AND PROMO",1,"4000000 - SALES - BFC","Income",""),
]
# Sort: groups first, then leaves with parents already in place
for num, name, is_grp, parent, rt, atype in sales_tree:
    # Account name pattern: "<NUM> - <NAME>" (with abbr suffix automatic on docname)
    docname = f"{num} - {name} - BFC"
    r = create_account(
        name=docname, account_name=name,
        parent_account=parent or "Income - BFC", company=BFC,
        is_group=is_grp, account_type=atype, root_type=rt,
        account_number=num,
    )
    if r == "created":
        created_bfc += 1
print(f"  BFC Sales tree: created {created_bfc}")

# Fork 1 scaffolding (per COA-175-013/015)
fork1_bfc = [
    ("1104200","DUE FROM BEI","Asset","Receivable","Asset - BFC"),
    ("2102205","OUTPUT VAT PAYABLE","Liability","Tax","Liability - BFC"),
]
for num, name, rt, atype, parent in fork1_bfc:
    docname = f"{num} - {name} - BFC"
    r = create_account(
        name=docname, account_name=name,
        parent_account=parent, company=BFC, is_group=0,
        account_type=atype, root_type=rt, account_number=num,
    )
    if r == "created":
        created_bfc += 1
print(f"  BFC Fork 1 scaffolding done; total created: {created_bfc}")

# BEI-side Fork 1 scaffolding: 2104200 DUE TO BFC - BEI
r = create_account(
    name="2104200 - DUE TO BFC - BEI", account_name="DUE TO BFC",
    parent_account="Liability - BEI", company="BEBANG ENTERPRISE INC.",
    is_group=0, account_type="Payable", root_type="Liability", account_number="2104200",
)
print(f"  2104200 - DUE TO BFC - BEI: {r}")


# === Step 4: BFT seed (Phase 2.5 B2) — Head Office variant ===
print("\n=== 2.5 BFT seed ===")
BFT = "BEBANG FT INC."
# BFT now has abbr=BFT (post Phase 1.5 A5). Apply Head Office Sales tree.
sales_tree_bft = [
    ("4000000","SALES",1,None,"Income",""),
    ("4000100","STORE SALES",1,"4000000 - SALES - BFT","Income",""),
    ("4000110","IN-STORE SALES",0,"4000100 - STORE SALES - BFT","Income","Income Account"),
    ("4000120","ONLINE SALES",1,"4000100 - STORE SALES - BFT","Income",""),
    ("4000121","BEI WEBSITE",0,"4000120 - ONLINE SALES - BFT","Income","Income Account"),
    ("4000122","FOOD PANDA",0,"4000120 - ONLINE SALES - BFT","Income","Income Account"),
    ("4000123","GRAB",0,"4000120 - ONLINE SALES - BFT","Income","Income Account"),
    ("4000200","BKI SALES",1,"4000000 - SALES - BFT","Income",""),
    ("4000210","DELIVERIES",0,"4000200 - BKI SALES - BFT","Income","Income Account"),
    ("4000220","LOGISTICS",1,"4000200 - BKI SALES - BFT","Income",""),
    ("4000221","DELIVERY INCOME",0,"4000220 - LOGISTICS - BFT","Income","Income Account"),
    ("4000222","LOGISTICS INCOME",0,"4000220 - LOGISTICS - BFT","Income","Income Account"),
    ("4000230","FEES",1,"4000000 - SALES - BFT","Income",""),
    ("4000231","ROYALTY FEES",0,"4000230 - FEES - BFT","Income","Income Account"),
    ("4000232","MANAGEMENT FEES",0,"4000230 - FEES - BFT","Income","Income Account"),
    ("4000233","FRANCHISE FEES",0,"4000230 - FEES - BFT","Income","Income Account"),
    ("4000234","MARKETING FEES",0,"4000230 - FEES - BFT","Income","Income Account"),
    ("4000235","E-COMMERCE FEES",0,"4000230 - FEES - BFT","Income","Income Account"),
    ("4000900","DISCOUNTS AND PROMO",1,"4000000 - SALES - BFT","Income",""),
]
created_bft = 0
for num, name, is_grp, parent, rt, atype in sales_tree_bft:
    docname = f"{num} - {name} - BFT"
    r = create_account(
        name=docname, account_name=name,
        parent_account=parent or "Income - BFT", company=BFT,
        is_group=is_grp, account_type=atype, root_type=rt, account_number=num,
    )
    if r == "created":
        created_bft += 1
print(f"  BFT Sales tree: created {created_bft}")


# === Step 5: 4 BEI-TIN stub seeds (Phase 2.6 B3) ===
print("\n=== 2.6 4 BEI-TIN stub seeds ===")
STUBS = [
    ("ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.", "ROA"),
    ("SM MANILA - BEBANG ENTERPRISE INC.", "SMM"),
    ("SM MEGAMALL - BEBANG ENTERPRISE INC.", "SMMM"),
    ("SM SOUTHMALL - BEBANG ENTERPRISE INC.", "SMS"),
]
for company, abbr in STUBS:
    print(f"\n  --- {abbr} = {company} ---")
    # Apply same Sales tree as Head Office (each stub gets its own per-store P&L)
    created_stub = 0
    for num, name, is_grp, parent, rt, atype in sales_tree_bft:
        # Parent name remap to current abbr
        parent_remap = (parent.replace(" - BFT", f" - {abbr}") if parent else f"Income - {abbr}")
        docname = f"{num} - {name} - {abbr}"
        r = create_account(
            name=docname, account_name=name,
            parent_account=parent_remap, company=company,
            is_group=is_grp, account_type=atype, root_type=rt, account_number=num,
        )
        if r == "created":
            created_stub += 1
    print(f"    Created {created_stub} Sales-tree accounts on {abbr}")

frappe.db.commit()
print("\n=== ALL DONE ===")
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s258_C1.py",
        "docker cp /tmp/s258_C1.py $BACKEND:/tmp/s258_C1.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s258_C1.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["900"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(180):
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print(inv["StandardOutputContent"])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"][-3000:])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    sys.exit(main())
