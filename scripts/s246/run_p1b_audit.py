#!/usr/bin/env python3
"""SSM wrapper for audit_7_items_probe.py."""
from __future__ import annotations

import base64, gzip, json, sys, time
from pathlib import Path
import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
HERE = Path(__file__).parent
SCRIPT = HERE / "audit_7_items_probe.py"
OUT = Path(__file__).parent.parent.parent / "output/l3/s246/audit/p1b_audit_raw.json"

ssm = boto3.client("ssm", region_name=REGION)
encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
cmds = [
    "set -e",
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{encoded}' | base64 -d > /tmp/s246_p1b.py",
    "docker cp /tmp/s246_p1b.py $BACKEND:/tmp/s246_p1b.py",
    "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s246_p1b.py'",
    "docker cp $BACKEND:/tmp/s246_p1b_audit.json /tmp/s246_p1b_audit.json",
    "gzip -c /tmp/s246_p1b_audit.json > /tmp/s246_p1b_audit.json.gz",
    "echo S246_FILE_BEGIN",
    "base64 -w0 /tmp/s246_p1b_audit.json.gz; echo",
    "echo S246_FILE_END",
]
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds}, TimeoutSeconds=900)
cmd_id = resp["Command"]["CommandId"]
print(f"command_id={cmd_id}")
while True:
    time.sleep(5)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    if inv["Status"] in ("Pending", "InProgress", "Delayed"):
        continue
    break
print(f"final_status={inv['Status']}")
out_text = inv.get("StandardOutputContent", "")
if "S246_FILE_BEGIN" not in out_text:
    print(out_text); print(inv.get("StandardErrorContent", ""))
    sys.exit(1)
b64 = out_text.split("S246_FILE_BEGIN")[1].split("S246_FILE_END")[0].strip()
decoded = gzip.decompress(base64.b64decode(b64)).decode("utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(decoded, encoding="utf-8")
print(f"wrote {OUT}")
data = json.loads(decoded)
print(f"\nstatus={data.get('status')}")
sys.exit(0)
