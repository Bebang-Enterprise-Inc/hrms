#!/usr/bin/env python3
from __future__ import annotations
import base64, gzip, json, sys, time
from pathlib import Path
import boto3
INSTANCE_ID = "i-026b7477d27bd46d6"
HERE = Path(__file__).parent
SCRIPT = HERE / "cleanup_phase6_v2_linked_se.py"
OUT = Path(__file__).parent.parent.parent / "output/l3/s247/verification/phase6_v2_result.json"
ssm = boto3.client("ssm", region_name="ap-southeast-1")
encoded = base64.b64encode(SCRIPT.read_text(encoding="utf-8").encode()).decode()
cmds = [
    "set -e",
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{encoded}' | base64 -d > /tmp/s247_p6v2.py",
    "docker cp /tmp/s247_p6v2.py $BACKEND:/tmp/s247_p6v2.py",
    "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s247_p6v2.py'",
    "docker cp $BACKEND:/tmp/s247_p6v2.json /tmp/s247_p6v2.json",
    "gzip -c /tmp/s247_p6v2.json > /tmp/s247_p6v2.json.gz",
    "echo S247_FILE_BEGIN",
    "base64 -w0 /tmp/s247_p6v2.json.gz; echo",
    "echo S247_FILE_END",
]
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds}, TimeoutSeconds=1800)
cmd_id = resp["Command"]["CommandId"]
print(f"command_id={cmd_id}")
while True:
    time.sleep(10)
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
print(f"summary={json.dumps(data.get('summary', {}), indent=2)}")
sys.exit(0)
