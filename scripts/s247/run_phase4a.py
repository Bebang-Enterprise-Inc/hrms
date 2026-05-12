#!/usr/bin/env python3
"""SSM wrapper for phase4a_cost_center.py."""
from __future__ import annotations

import base64, gzip, json, sys, time
from pathlib import Path
import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
HERE = Path(__file__).parent
SCRIPT = HERE / "phase4a_cost_center.py"
OUT = Path(__file__).parent.parent.parent / "output/l3/s247/verification/phase4a_result.json"

ssm = boto3.client("ssm", region_name=REGION)
encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
cmds = [
    "set -e",
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{encoded}' | base64 -d > /tmp/s247_p4a.py",
    "docker cp /tmp/s247_p4a.py $BACKEND:/tmp/s247_p4a.py",
    "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s247_p4a.py'",
    "docker cp $BACKEND:/tmp/s247_p4a_result.json /tmp/s247_p4a_result.json",
    "gzip -c /tmp/s247_p4a_result.json > /tmp/s247_p4a_result.json.gz",
    "echo S247_FILE_BEGIN",
    "base64 -w0 /tmp/s247_p4a_result.json.gz; echo",
    "echo S247_FILE_END",
]
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds}, TimeoutSeconds=300)
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
if "S247_FILE_BEGIN" not in out_text:
    print(out_text); print(inv.get("StandardErrorContent", ""))
    sys.exit(1)
b64 = out_text.split("S247_FILE_BEGIN")[1].split("S247_FILE_END")[0].strip()
decoded = gzip.decompress(base64.b64decode(b64)).decode("utf-8")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(decoded, encoding="utf-8")
print(f"wrote {OUT}")
data = json.loads(decoded)
print(f"\nstatus={data.get('status')}")
for r in data.get("results", []):
    print(f"  {r['abbr']}: {r.get('status')} cost_center={r.get('new_cost_center', r.get('old_cost_center'))}")
sys.exit(0 if data.get("status") == "OK" else 1)
