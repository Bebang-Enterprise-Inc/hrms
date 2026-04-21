#!/usr/bin/env python3
"""Probe full error text length."""
import base64, gzip, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "s203_full.txt"

SCRIPT = '''
import base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
errs = frappe.db.sql("""
    SELECT LENGTH(error) as len, error
    FROM `tabError Log`
    WHERE name = (SELECT name FROM `tabError Log`
                  WHERE method LIKE '%S203%'
                  ORDER BY creation DESC LIMIT 1)
""", as_dict=True)
txt = (errs[0]["error"] if errs else "") or ""
print("__LEN__", errs[0]["len"] if errs else 0)
compressed = gzip.compress(txt.encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''

def run(script, timeout=60):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_fullerr.py",
        "docker cp /tmp/s212_fullerr.py $BACKEND:/tmp/s212_fullerr.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_fullerr.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(err)
                raise RuntimeError(f"SSM {inv['Status']}")
            return out
    raise TimeoutError()

out = run(SCRIPT)
print("[len line]", [l for l in out.splitlines() if "__LEN__" in l])
s = out.find("__B64_START__")
e = out.find("__B64_END__")
b64 = out[s+len("__B64_START__"):e].strip()
txt = gzip.decompress(base64.b64decode(b64)).decode()
OUT.write_text(txt, encoding="utf-8")
print(f"Wrote {OUT} ({len(txt)} chars)")
print()
print(txt[:5000])
