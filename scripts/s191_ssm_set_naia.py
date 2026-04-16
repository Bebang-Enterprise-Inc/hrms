"""Dispatch s191_set_naia_location_id.py to production via SSM."""
import base64
import os
import sys
import time
import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
SCRIPT = "scripts/s191_set_naia_location_id.py"

os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client("ssm", region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])

with open(SCRIPT, "r", encoding="utf-8") as f:
    script = f.read()
encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")

find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"
commands = [
    f"BACKEND=$({find_cmd})",
    'if [ -z "$BACKEND" ]; then echo "NO BACKEND CONTAINER FOUND"; exit 1; fi',
    'echo "Backend container: $BACKEND"',
    f"echo '{encoded}' | base64 -d > /tmp/s191_set_naia.py",
    "docker cp /tmp/s191_set_naia.py $BACKEND:/tmp/s191_set_naia.py",
    "docker exec -e CONFIRM=yes $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s191_set_naia.py",
]

print(f"Sending {len(commands)} commands to {INSTANCE_ID}...")
resp = ssm.send_command(InstanceIds=[INSTANCE_ID],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["300"]})
cmd_id = resp["Command"]["CommandId"]
print(f"Command ID: {cmd_id}")

for i in range(60):
    time.sleep(5)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    status = inv["Status"]
    print(f"  [{i*5:4d}s] status={status}")
    if status not in ("Pending", "InProgress", "Delayed"):
        stdout = inv.get("StandardOutputContent", "")
        print(stdout)
        if inv.get("StandardErrorContent"):
            print("=== STDERR ===")
            print(inv["StandardErrorContent"][-2000:])
        print(f"\nFinal: {status} (exit {inv.get('ResponseCode')})")
        sys.exit(0 if status == "Success" else 1)

print("TIMEOUT")
sys.exit(2)
