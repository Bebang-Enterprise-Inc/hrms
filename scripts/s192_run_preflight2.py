#!/usr/bin/env python3
"""S192 preflight v2 — bypass welcome mail, probe real SM Tanza env."""
import base64
import json
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

BOILER = r'''
import os, sys, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
'''

def send(script_body, tag, timeout=300):
    full = BOILER + "\n" + script_body + "\nfrappe.db.commit()\nfrappe.destroy()\n"
    enc = base64.b64encode(full.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s192_{tag}.py",
        f"docker cp /tmp/s192_{tag}.py $BACKEND:/tmp/s192_{tag}.py",
        f"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s192_{tag}.py",
    ]
    ssm = boto3.client("ssm", region_name=REGION)
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    for _ in range(int(timeout/3)+10):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success","Failed","TimedOut","Cancelled"):
            return {"ok": inv["Status"]=="Success",
                    "stdout": inv.get("StandardOutputContent",""),
                    "stderr": inv.get("StandardErrorContent",""),
                    "status": inv["Status"]}
    return {"ok": False, "stdout":"", "stderr":"timeout"}

def extract(stdout, m="RESULT:"):
    i = stdout.find(m)
    if i==-1: return None
    return json.loads(stdout[i+len(m):].split("\n")[0])

def cmd(name):
    return {
        "users": USERS_SCRIPT,
        "probe": PROBE_SCRIPT,
        "cleanup": CLEANUP_SCRIPT,
    }[name]

USERS_SCRIPT = '''
targets = [
    ("test.area@bebang.ph", "Test", "Area", ["Area Supervisor", "Employee"]),
    ("test.scm@bebang.ph", "Test", "SCM", ["Supply Chain Manager", "Employee"]),
    ("test.supervisor@bebang.ph", "Test", "Supervisor", ["Store Supervisor", "Employee"]),
]
# Disable welcome mail globally for this run
frappe.flags.in_patch = True
frappe.flags.mute_messages = True
frappe.flags.mute_emails = True
result = []
for email, first, last, roles in targets:
    existed = frappe.db.exists("User", email)
    try:
        if not existed:
            u = frappe.new_doc("User")
            u.email = email
            u.first_name = first
            u.last_name = last
            u.enabled = 1
            u.user_type = "System User"
            u.send_welcome_email = 0
            u.flags.ignore_permissions = True
            u.flags.mute_emails = True
            u.flags.no_welcome_mail = True
            u.insert(ignore_permissions=True)
            # Set password directly via Auth (bypass mail)
            from frappe.utils.password import update_password
            update_password(email, "BeiTest2026!")
        doc = frappe.get_doc("User", email)
        existing = {r.role for r in doc.roles}
        added = []
        for r in roles:
            if r not in existing and frappe.db.exists("Role", r):
                doc.append("roles", {"role": r})
                added.append(r)
        if added:
            doc.flags.ignore_permissions = True
            doc.flags.mute_emails = True
            doc.save(ignore_permissions=True)
        # Make sure user is enabled
        if not doc.enabled:
            frappe.db.set_value("User", email, "enabled", 1)
        result.append({"email": email, "created": not existed, "roles_added": added,
                       "all_roles": [r.role for r in doc.roles]})
    except Exception as e:
        import traceback
        result.append({"email": email, "error": str(e)[:200], "trace": traceback.format_exc()[-500:]})
print("RESULT:" + json.dumps(result))
'''

PROBE_SCRIPT = '''
out = {}

# Stores matching SM Tanza
out["tanza"] = frappe.get_all("Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%Tanza%"]},
    fields=["name", "company", "warehouse_type"])

# Stores matching SM Megamall
out["megamall"] = frappe.get_all("Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%Megamall%"]},
    fields=["name", "company"])

# The Grid
out["grid"] = frappe.get_all("Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%Grid%"]},
    fields=["name", "company"])

# Ayala Evo
out["evo"] = frappe.get_all("Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%Evo%"]},
    fields=["name", "company"])

# Sources (Shaw, Commissary, BKI)
out["sources"] = frappe.get_all("Warehouse",
    filters={"disabled": 0, "is_group": 0, "name": ["like", "%BKI%"]},
    fields=["name", "company"], limit=10)

# Items: FG-*-DRY
out["dry_items"] = frappe.get_all("Item",
    filters={"disabled": 0, "item_code": ["like", "FG-%-DRY"]},
    fields=["item_code", "item_name"], limit=10)

# If no FG-*-DRY, fallback to Finished Good
if not out["dry_items"]:
    out["dry_items"] = frappe.get_all("Item",
        filters={"disabled": 0, "item_group": ["like", "%Finished%"]},
        fields=["item_code", "item_name"], limit=5)

# Does BEI Store Delivery Schedule DocType exist?
out["has_bsds"] = bool(frappe.db.exists("DocType", "BEI Store Delivery Schedule"))
if out["has_bsds"]:
    try:
        cols = frappe.db.get_table_columns("BEI Store Delivery Schedule")
        out["bsds_columns"] = cols
    except Exception as e:
        out["bsds_columns_err"] = str(e)[:200]
    try:
        out["bsds_for_tanza"] = frappe.db.sql("""
            SELECT name, store FROM `tabBEI Store Delivery Schedule`
            WHERE store LIKE %s LIMIT 5
        """, ("%SM Tanza%",), as_dict=True)
    except Exception as e:
        out["bsds_err"] = str(e)[:200]

# Does BEI Route DocType exist?
out["has_route"] = bool(frappe.db.exists("DocType", "BEI Route"))
if out["has_route"]:
    try:
        out["route_cols"] = frappe.db.get_table_columns("BEI Route")
        out["sample_routes"] = frappe.db.sql("SELECT name FROM `tabBEI Route` LIMIT 5", as_dict=True)
    except Exception as e:
        out["route_err"] = str(e)[:200]

# Bin check — first DRY item in first source warehouse
if out["dry_items"] and out["sources"]:
    it = out["dry_items"][0]["item_code"]
    for s in out["sources"]:
        qty = frappe.db.get_value("Bin", {"item_code": it, "warehouse": s["name"]}, "actual_qty")
        if qty and qty > 0:
            out["sample_bin"] = {"item": it, "warehouse": s["name"], "qty": qty}
            break
    if "sample_bin" not in out:
        out["sample_bin"] = {"item": it, "warehouse": out["sources"][0]["name"], "qty": 0}

print("RESULT:" + json.dumps(out, default=str))
'''

CLEANUP_SCRIPT = '''
# placeholder — takes names parameter, replaced at runtime
'''

def main():
    if len(sys.argv) < 2:
        print("usage: users|probe|cleanup ...")
        sys.exit(1)
    op = sys.argv[1]
    if op == "users":
        res = send(USERS_SCRIPT, "users", timeout=180)
    elif op == "probe":
        res = send(PROBE_SCRIPT, "probe", timeout=120)
    elif op == "cleanup":
        names = sys.argv[2:]
        script = f'''
order_names = {names!r}
rev = []; failed = []
for oname in order_names:
    try:
        if not frappe.db.exists("BEI Store Order", oname): continue
        o = frappe.get_doc("BEI Store Order", oname)
        mrs = frappe.get_all("Material Request",
            filters={{"custom_store_order": oname}}, pluck="name")
        sis = frappe.get_all("Sales Invoice",
            filters={{"custom_bei_store_order": oname}}, pluck="name")
        for si in sis:
            try:
                d = frappe.get_doc("Sales Invoice", si)
                if d.docstatus==1: d.cancel()
                rev.append({{"type":"SI","name":si}})
            except Exception as e: failed.append({{"type":"SI","name":si,"err":str(e)[:150]}})
        for mr in mrs:
            ses = frappe.get_all("Stock Entry", filters={{"material_request":mr}}, pluck="name")
            for se in ses:
                try:
                    d = frappe.get_doc("Stock Entry", se)
                    if d.docstatus==1: d.cancel()
                    rev.append({{"type":"SE","name":se}})
                except Exception as e: failed.append({{"type":"SE","name":se,"err":str(e)[:150]}})
            try:
                d = frappe.get_doc("Material Request", mr)
                if d.docstatus==1: d.cancel()
                rev.append({{"type":"MR","name":mr}})
            except Exception as e: failed.append({{"type":"MR","name":mr,"err":str(e)[:150]}})
        if o.docstatus==1: o.cancel()
        rev.append({{"type":"Order","name":oname}})
        frappe.db.commit()
    except Exception as e:
        failed.append({{"type":"Order","name":oname,"err":str(e)[:200]}})
print("RESULT:" + json.dumps({{"reversed":rev,"failed":failed}}))
'''
        res = send(script, "cleanup", timeout=300)
    else:
        print("unknown"); sys.exit(1)

    print("STATUS:", res["status"])
    if res["stderr"]:
        print("STDERR:", res["stderr"][-2000:])
    result = extract(res["stdout"])
    if result is None:
        print("STDOUT tail:", res["stdout"][-3000:])
    else:
        print(json.dumps(result, indent=2, default=str))

if __name__=="__main__":
    main()
