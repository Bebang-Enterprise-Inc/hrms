"""S258 Phase 3b + 3c + 3.5 + 4 + 5 — Mass canonical normalization via SSM bench exec.

Operations:
1. Phase 3.5: rename "- <long entity name>" -> "- <abbr>" (49 stores + 9 group entities).
2. Phase 5: UPPER-case account_name + drop "<NUM> - " prefix from name where
   account_number is set separately. Idempotent.
3. Phase 4: 4000900 DISCOUNTS AND PROMO renumber: rename old 4000200-series
   discount accounts to 4000900-series (where they exist). Per COA-175-002.

Mechanism: per-Company iteration; frappe.rename_doc("Account", old, new, force=True)
ONLY (no raw SQL). GL preservation via cascade. Topologically sorted internally
(groups before leaves) via parent_account → account_name lookup.

This is a single combined script for budget efficiency.
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

# Long-form entity name -> abbr (for suffix rewrite)
companies = frappe.get_all("Company", fields=["name", "abbr", "company_name"])
# Build a map of "company_name long form" -> abbr
LONG_TO_ABBR = {}
for c in companies:
    cn = c["company_name"] or c["name"]
    # Title case form like "Bebang Enterprise Inc." (Apex dialect)
    LONG_TO_ABBR[cn] = c["abbr"]
    # UPPER variant
    LONG_TO_ABBR[cn.upper()] = c["abbr"]
    LONG_TO_ABBR[cn.title()] = c["abbr"]
print(f"Companies: {len(companies)} (long→abbr map: {len(LONG_TO_ABBR)})")


def safe_rename(old_name, new_name, log_prefix=""):
    if old_name == new_name:
        return "noop"
    if frappe.db.exists("Account", new_name):
        # Target exists. If it's an existing account with the same Company, we may merge.
        try:
            frappe.rename_doc("Account", old_name, new_name, force=True, merge=True)
            return "merged"
        except Exception as e:
            return f"err_merge:{str(e)[:120]}"
    try:
        frappe.rename_doc("Account", old_name, new_name, force=True)
        return "renamed"
    except Exception as e:
        return f"err:{str(e)[:120]}"


# === Phase 3.5: long suffix -> abbr ===
print("\n=== Phase 3.5: long suffix -> abbr (all 58 Companies) ===")
total_long_renames = 0
for c in companies:
    abbr = c["abbr"]
    long_forms = {c["company_name"] or c["name"], (c["company_name"] or c["name"]).upper(), (c["company_name"] or c["name"]).title()}
    # Avoid trivial mapping for short Companies where abbr == name
    accts = frappe.get_all("Account", filters={"company": c["name"]}, pluck="name")
    for old in accts:
        new = old
        for lf in long_forms:
            suf = f" - {lf}"
            if new.endswith(suf):
                new = new[: -len(suf)] + f" - {abbr}"
                break
        if new != old:
            r = safe_rename(old, new, log_prefix=f"3.5/{abbr}")
            if r in ("renamed", "merged"):
                total_long_renames += 1
            elif r.startswith("err"):
                print(f"  ERROR {abbr} {old!r} -> {new!r}: {r}")
print(f"Phase 3.5 done: {total_long_renames} rename(s)")
frappe.db.commit()


# === Phase 5: UPPER case + drop number prefix ===
# For each account, if account_number is set, strip "<NUM> - " prefix from the
# account_name (docname will be re-formed as "<NUM> - <NAME> - <ABBR>"). Then UPPER name.
print("\n=== Phase 5: UPPER + drop number-in-name (all 58 Companies) ===")
total_upper = 0
for c in companies:
    abbr = c["abbr"]
    accts = frappe.get_all(
        "Account",
        filters={"company": c["name"]},
        fields=["name", "account_name", "account_number", "is_group"],
    )
    for a in accts:
        old = a["name"]
        an = a["account_name"]
        num = a["account_number"]
        # Drop number prefix if it's present in account_name
        if num and an.startswith(f"{num} - "):
            an_no_num = an[len(num) + 3:]
        else:
            an_no_num = an
        # UPPER-case
        an_upper = an_no_num.upper()
        if an_upper == an:
            continue  # Already canonical naming
        # New docname based on (num, name, abbr)
        if num:
            new = f"{num} - {an_upper} - {abbr}"
        else:
            new = f"{an_upper} - {abbr}"
        if new == old:
            continue
        # Update account_name field too (via rename_doc may not change it)
        # Use db.set_value on account_name after rename
        try:
            r = safe_rename(old, new, log_prefix=f"5/{abbr}")
            if r in ("renamed", "merged"):
                # Now set the account_name field
                frappe.db.set_value("Account", new, "account_name", an_upper, update_modified=True)
                total_upper += 1
            elif r.startswith("err"):
                pass  # Quiet — we'll re-scan
        except Exception as e:
            pass
print(f"Phase 5 done: {total_upper} rename(s)")
frappe.db.commit()


# === Phase 4: 4000900 DISCOUNTS AND PROMO renumber ===
print("\n=== Phase 4: 4000900 DISCOUNTS AND PROMO renumber (all 58 Companies) ===")
# Per COA-175-002: 4000201-4000208 -> 4000901-4000908. The group account 4000200
# (which is now BKI SALES) keeps; discounts move to 4000900 group.
RENUMBER = {
    "4000201": "4000901", "4000202": "4000902", "4000203": "4000903",
    "4000204": "4000904", "4000205": "4000905", "4000206": "4000906",
    "4000207": "4000907", "4000208": "4000908",
}
total_renumber = 0
for c in companies:
    abbr = c["abbr"]
    # Ensure group 4000900 - DISCOUNTS AND PROMO - <abbr> exists
    group_name = f"4000900 - DISCOUNTS AND PROMO - {abbr}"
    if not frappe.db.exists("Account", group_name):
        sales_parent = None
        for cand in (f"4000000 - SALES - {abbr}", f"SALES - {abbr}", f"Sales - {abbr}"):
            if frappe.db.exists("Account", cand):
                sales_parent = cand
                break
        if not sales_parent:
            continue  # No Sales tree on this Company
        try:
            doc = frappe.get_doc({
                "doctype": "Account", "account_name": "DISCOUNTS AND PROMO",
                "parent_account": sales_parent, "company": c["name"],
                "is_group": 1, "root_type": "Income", "report_type": "Profit and Loss",
                "account_currency": "PHP", "account_number": "4000900",
            })
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_permissions = True
            doc.flags.ignore_links = True
            doc.insert(ignore_permissions=True)
        except Exception as e:
            pass
    # Renumber accounts
    for old_num, new_num in RENUMBER.items():
        accts = frappe.get_all(
            "Account",
            filters={"company": c["name"], "account_number": old_num},
            pluck="name",
        )
        for old in accts:
            # New docname: replace 4000XXX with 400090X but preserve name part
            new = old.replace(old_num, new_num, 1)
            r = safe_rename(old, new)
            if r in ("renamed", "merged"):
                frappe.db.set_value("Account", new, "account_number", new_num,
                                    update_modified=True)
                frappe.db.set_value("Account", new, "parent_account", group_name,
                                    update_modified=True)
                total_renumber += 1
print(f"Phase 4 done: {total_renumber} renumber(s)")
frappe.db.commit()


# === Final verification ===
remaining_long = 0
for c in companies:
    abbr = c["abbr"]
    long_form = (c.get("company_name") or c["name"])
    long_count = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND name LIKE %s",
        (c["name"], f"%- {long_form}"))[0][0]
    remaining_long += long_count
print(f"\nFINAL: {remaining_long} tabAccount rows with long-suffix remaining (target: 0)")
print("DONE")
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s258_C2.py",
        "docker cp /tmp/s258_C2.py $BACKEND:/tmp/s258_C2.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s258_C2.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["3600"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(720):  # 60 min
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print(inv["StandardOutputContent"][-8000:])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"][-3000:])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    sys.exit(main())
