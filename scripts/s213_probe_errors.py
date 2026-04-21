#!/usr/bin/env python3
"""Probe Frappe errors during the S213 sweep window."""
import base64, gzip, json, pathlib, sys, time
AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s213" / "error_probe.json"

SCRIPT = '''
import base64, gzip, json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Sweep window: 2026-04-21 11:55 PHT (= 03:55 UTC) to now
errs = frappe.db.sql("""
    SELECT creation, method, LEFT(error, 800) AS error_head
    FROM `tabError Log`
    WHERE creation >= '2026-04-21 03:50:00'
      AND method NOT LIKE '%brain_sync%'
    ORDER BY creation DESC LIMIT 40
""", as_dict=True)

compressed = gzip.compress(json.dumps(errs, default=str).encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''

def run(timeout=60):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s213_err.py",
        "docker cp /tmp/s213_err.py $BACKEND:/tmp/s213_err.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s213_err.py",
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
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", ""))
            return out
    raise TimeoutError()

out = run()
s = out.find("__B64_START__"); e = out.find("__B64_END__")
b64 = out[s+len("__B64_START__"):e].strip()
errs = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
OUT.write_text(json.dumps(errs, indent=2, default=str), encoding="utf-8")
print(f"Errors: {len(errs)}")
from collections import Counter
methods = Counter(e["method"] for e in errs)
print("Method distribution:")
for m, c in methods.most_common():
    print(f"  {c:3d} | {m}")
print()
print("Samples:")
seen = set()
for err in errs:
    m = err["method"]
    if m in seen: continue
    seen.add(m)
    print(f"\n--- {err['creation']} | {m} ---")
    print((err["error_head"] or "")[:400])
