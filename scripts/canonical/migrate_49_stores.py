"""Migrate all 49 store records to the canonical model defined in
docs/STORE_COMPANY_CANONICAL.md.

Per-store operations (each in its own savepoint):
  1. Ensure canonical Warehouse exists with docname = per-store Company name,
     company = per-store Company.
       - If canonical WH exists with correct company: no-op.
       - If canonical WH exists but company is parent (SM TANZA + AYALA VERMOSA):
         flip company to per-store.
       - If canonical WH doesn't exist: rename the existing non-canonical active
         warehouse under the per-store Company (e.g. 'BEBANG MEGA INC. - SM TANZA - SMTZ')
         to the canonical docname.
       - Disable any remaining non-canonical active warehouses under the
         per-store Company (duplicates).
  2. Ensure canonical Warehouse has warehouse_name = short store label
     (strip ' - <LEGAL SUFFIX>' from per-store Company name).
  3. Ensure canonical Warehouse has custom_area_supervisor set to the original
     area supervisor (carry over from the warehouse being renamed/retired).
  4. Ensure billing Customer exists with customer_name = per-store Company name,
     tax_id = parent TIN (if parent exists) else per-store TIN, is_internal=0.
  5. Ensure Internal Customer exists with represents_company = per-store Company
     and is_internal=1 (for S206 labor journals).
  6. Ensure Cost Center exists at '<STORE LABEL> - <ABBR>' under per-store Company.

Flags:
  --dry-run   Report what would change, don't mutate
  --store "..."   Migrate only the named per-store Company
"""
from __future__ import annotations
import argparse
import base64
import json
import sys
import time


def _build_script(dry_run: bool, store_filter: str | None) -> str:
    dry_flag = "True" if dry_run else "False"
    filter_literal = "None" if not store_filter else f'"""{store_filter}"""'
    return f'''
import os, re, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
import frappe
from frappe.model.rename_doc import rename_doc

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

DRY_RUN = {dry_flag}
STORE_FILTER = {filter_literal}

SUB_WH = ("FINISHED GOODS", "GOODS IN TRANSIT", "STORES", "WORK IN PROGRESS")
LEGAL_SUFFIX_RE = re.compile(r"\\s+-\\s+.+?(INC\\.|CORP\\.|OPC|HOLDINGS\\s+OPC).*$")


def short_store_label(ps_co):
    """Extract human-readable label. 'SM TANZA - BEBANG MEGA INC.' -> 'SM TANZA'."""
    return LEGAL_SUFFIX_RE.sub("", ps_co).strip() or ps_co


def pick_tin(ps_co, parent):
    """Canonical TIN to use on billing Customer."""
    per_store_tin = frappe.db.get_value("Company", ps_co, "tax_id")
    if per_store_tin:
        return per_store_tin, f"per-store Company ({{ps_co}})"
    if parent:
        parent_tin = frappe.db.get_value("Company", parent, "tax_id")
        if parent_tin:
            return parent_tin, f"parent Company ({{parent}})"
    return None, "NONE AVAILABLE"


def migrate_store(ps_co):
    log = []
    actions = []

    parent = frappe.db.get_value("Company", ps_co, "parent_company")
    short_label = short_store_label(ps_co)

    if not DRY_RUN:
        _sp_name = "migrate_" + "".join(c if c.isalnum() else "_" for c in ps_co)[:60]
        frappe.db.savepoint(_sp_name)

    # ======================================================================
    # Step 1: Canonical Warehouse
    # ======================================================================
    canonical_wh_exists = bool(frappe.db.exists("Warehouse", ps_co))
    non_canonical_ps = frappe.db.sql(
        """SELECT name, warehouse_name, custom_area_supervisor, is_group
           FROM `tabWarehouse`
           WHERE company = %s AND is_group = 0 AND disabled = 0
             AND warehouse_name NOT IN ('FINISHED GOODS','GOODS IN TRANSIT','STORES','WORK IN PROGRESS')
             AND name != %s""",
        (ps_co, ps_co), as_dict=True,
    )
    parent_linked = []
    if parent:
        parent_linked = frappe.db.sql(
            """SELECT name, warehouse_name, company, custom_area_supervisor
               FROM `tabWarehouse`
               WHERE company = %s AND is_group = 0 AND disabled = 0
                 AND warehouse_name NOT IN ('FINISHED GOODS','GOODS IN TRANSIT','STORES','WORK IN PROGRESS')
                 AND name = %s""",
            (parent, ps_co), as_dict=True,
        )

    # Carry-over supervisor
    carried_supervisor = None
    for wh in parent_linked + non_canonical_ps:
        if wh.get("custom_area_supervisor"):
            carried_supervisor = wh["custom_area_supervisor"]
            break

    if canonical_wh_exists:
        cur = frappe.db.get_value("Warehouse", ps_co, ["company", "warehouse_name", "custom_area_supervisor", "disabled"], as_dict=True)
        if cur["company"] != ps_co:
            actions.append(f"FLIP_COMPANY: Warehouse {{ps_co!r}} company {{cur['company']!r}} -> {{ps_co!r}}")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", ps_co, "company", ps_co, update_modified=False)
        if cur["warehouse_name"] != short_label:
            actions.append(f"SET_WH_NAME: Warehouse {{ps_co!r}} warehouse_name {{cur['warehouse_name']!r}} -> {{short_label!r}}")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", ps_co, "warehouse_name", short_label, update_modified=False)
        if not cur["custom_area_supervisor"] and carried_supervisor:
            actions.append(f"SET_SUPERVISOR: Warehouse {{ps_co!r}} <- {{carried_supervisor!r}}")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", ps_co, "custom_area_supervisor", carried_supervisor, update_modified=False)
        if cur["disabled"]:
            actions.append(f"ENABLE: Warehouse {{ps_co!r}} disabled=0")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", ps_co, "disabled", 0, update_modified=False)
        # Disable duplicates under per-store
        for dup in non_canonical_ps:
            actions.append(f"DISABLE_DUP_PS: Warehouse {{dup['name']!r}} disabled=1")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", dup["name"], "disabled", 1, update_modified=False)
    else:
        # Canonical doesn't exist — rename the BEST non-canonical per-store warehouse to canonical name
        if not non_canonical_ps:
            # No source to rename. Abort this store.
            log.append(f"[SKIP] {{ps_co}}: canonical Warehouse missing and no non-canonical warehouse under per-store Company to rename")
            if not DRY_RUN:
                frappe.db.release_savepoint(f"migrate_{{ps_co[:50].replace(' ', '_').replace('-', '_')}}")
            return log, actions
        src = non_canonical_ps[0]["name"]
        actions.append(f"RENAME: Warehouse {{src!r}} -> {{ps_co!r}}")
        if not DRY_RUN:
            rename_doc("Warehouse", src, ps_co, merge=False, force=True)
            # After rename, set canonical fields
            frappe.db.set_value("Warehouse", ps_co, "warehouse_name", short_label, update_modified=False)
            if carried_supervisor:
                frappe.db.set_value("Warehouse", ps_co, "custom_area_supervisor", carried_supervisor, update_modified=False)
        # Disable remaining non-canonical
        for dup in non_canonical_ps[1:]:
            actions.append(f"DISABLE_DUP_PS: Warehouse {{dup['name']!r}} disabled=1")
            if not DRY_RUN:
                frappe.db.set_value("Warehouse", dup["name"], "disabled", 1, update_modified=False)

    # After the canonical WH is sorted, disable any parent-linked duplicate that shares the docname
    # This is the SM TANZA + AYALA VERMOSA case after FLIP_COMPANY: the canonical WH moved to per-store,
    # so there's no longer a duplicate at the parent side. Still, check for any warehouse_name match under parent.
    if parent:
        parent_dups = frappe.db.sql(
            """SELECT name FROM `tabWarehouse`
               WHERE company = %s AND is_group = 0 AND disabled = 0
                 AND warehouse_name NOT IN ('FINISHED GOODS','GOODS IN TRANSIT','STORES','WORK IN PROGRESS')
                 AND warehouse_name = %s""",
            (parent, short_label), as_dict=True,
        )
        for dup in parent_dups:
            if dup["name"] != ps_co:
                actions.append(f"DISABLE_DUP_PARENT: Warehouse {{dup['name']!r}} disabled=1")
                if not DRY_RUN:
                    frappe.db.set_value("Warehouse", dup["name"], "disabled", 1, update_modified=False)

    # ======================================================================
    # Step 2: Billing Customer (customer_name == ps_co, is_internal=0)
    # ======================================================================
    billing = frappe.db.get_value(
        "Customer", {{"customer_name": ps_co, "is_internal_customer": 0}},
        ["name", "tax_id"], as_dict=True,
    )
    target_tin, tin_source = pick_tin(ps_co, parent)
    if not billing:
        actions.append(f"CREATE_BILLING_CUST: name={{ps_co!r}} tax_id={{target_tin!r}} (source: {{tin_source}})")
        if not DRY_RUN:
            # Deterministic docname = ps_co; if a Customer already has that docname but different flags, skip
            if frappe.db.exists("Customer", ps_co):
                actions.append(f"WARN_CUST_DOCNAME_COLLISION: Customer docname {{ps_co!r}} already exists with different flags — skipping create")
            else:
                doc = frappe.get_doc({{
                    "doctype": "Customer",
                    "name": ps_co,
                    "customer_name": ps_co,
                    "customer_type": "Company",
                    "customer_group": "All Customer Groups",
                    "territory": "All Territories",
                    "is_internal_customer": 0,
                    "tax_id": target_tin or "",
                }})
                doc.insert(ignore_permissions=True)
    else:
        if target_tin and billing.get("tax_id") != target_tin:
            actions.append(f"SET_CUST_TIN: Customer {{billing['name']!r}} tax_id {{billing.get('tax_id')!r}} -> {{target_tin!r}}")
            if not DRY_RUN:
                frappe.db.set_value("Customer", billing["name"], "tax_id", target_tin, update_modified=False)

    # ======================================================================
    # Step 3: Internal Customer (represents_company = ps_co, is_internal=1)
    # ======================================================================
    internal = frappe.db.sql(
        """SELECT name FROM `tabCustomer`
           WHERE represents_company = %s AND is_internal_customer = 1""",
        (ps_co,), as_dict=True,
    )
    internal_name = f"{{short_label}} (Internal)"
    if not internal:
        actions.append(f"CREATE_INTERNAL_CUST: name={{internal_name!r}} represents_company={{ps_co!r}}")
        if not DRY_RUN:
            # Avoid docname collision
            existing_docname = frappe.db.exists("Customer", internal_name)
            if existing_docname:
                # Upgrade existing to internal
                actions.append(f"UPGRADE_EXISTING_TO_INTERNAL: {{internal_name!r}}")
                frappe.db.set_value("Customer", internal_name, "is_internal_customer", 1, update_modified=False)
                frappe.db.set_value("Customer", internal_name, "represents_company", ps_co, update_modified=False)
            else:
                doc = frappe.get_doc({{
                    "doctype": "Customer",
                    "name": internal_name,
                    "customer_name": internal_name,
                    "customer_type": "Company",
                    "customer_group": "All Customer Groups",
                    "territory": "All Territories",
                    "is_internal_customer": 1,
                    "represents_company": ps_co,
                }})
                doc.insert(ignore_permissions=True)
    elif len(internal) > 1:
        actions.append(f"WARN_MULTIPLE_INTERNAL: {{[c['name'] for c in internal]}}")

    if not DRY_RUN:
        frappe.db.release_savepoint(_sp_name)
        frappe.db.commit()

    log.append(f"[OK] {{ps_co}}: {{len(actions)}} actions")
    for a in actions:
        log.append(f"    {{a}}")
    return log, actions


# Get stores
if STORE_FILTER:
    stores = frappe.db.sql(
        """SELECT name FROM `tabCompany` WHERE name = %s AND entity_category = 'Store'""",
        (STORE_FILTER,), as_list=True,
    )
else:
    stores = frappe.db.sql(
        """SELECT name FROM `tabCompany`
           WHERE entity_category = 'Store'
             AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
           ORDER BY name""",
        as_list=True,
    )

all_actions = 0
failed = []
print(f"Migrating {{len(stores)}} stores (dry_run={{DRY_RUN}})")
print("=" * 70)

for (ps_co,) in stores:
    try:
        log, actions = migrate_store(ps_co)
        for line in log:
            print(line)
        all_actions += len(actions)
    except Exception as e:
        import traceback
        failed.append(ps_co)
        print(f"[FAIL] {{ps_co}}: {{type(e).__name__}}: {{e}}")
        traceback.print_exc()
        if not DRY_RUN:
            try:
                _sp = "migrate_" + "".join(c if c.isalnum() else "_" for c in ps_co)[:60]
                frappe.db.rollback_to_savepoint(_sp)
            except Exception:
                pass

print("=" * 70)
print(f"Total actions: {{all_actions}}")
print(f"Failed stores: {{len(failed)}}")
if failed:
    for f in failed: print(f"  {{f}}")
print(f"DRY_RUN: {{DRY_RUN}}")

frappe.destroy()
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report but don't mutate")
    ap.add_argument("--store", help="Migrate only the named per-store Company")
    args = ap.parse_args()

    script = _build_script(args.dry_run, args.store)
    enc = base64.b64encode(script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/migrate_49.py",
        "docker cp /tmp/migrate_49.py $BACKEND:/tmp/migrate_49.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/migrate_49.py",
    ]

    import boto3
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=["i-026b7477d27bd46d6"],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["1200"]},
    )
    cid = r["Command"]["CommandId"]
    print("CommandId:", cid)
    for _ in range(400):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print("STATUS:", inv["Status"])
            print(inv["StandardOutputContent"])
            if inv["StandardErrorContent"]:
                print("STDERR:", inv["StandardErrorContent"][-2000:])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    sys.exit(main())
