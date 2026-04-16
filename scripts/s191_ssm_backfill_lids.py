"""Dispatch s191_backfill_location_ids.py via SSM."""
import base64, os, sys, time, boto3
INSTANCE_ID = "i-026b7477d27bd46d6"
SCRIPT = "scripts/s191_backfill_location_ids.py"
os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client("ssm", region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
with open(SCRIPT, "r", encoding="utf-8") as f: script = f.read()
encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"
commands = [
    f"BACKEND=$({find_cmd})",
    'if [ -z "$BACKEND" ]; then echo "NO BACKEND CONTAINER FOUND"; exit 1; fi',
    'echo "Backend container: $BACKEND"',
    f"echo '{encoded}' | base64 -d > /tmp/s191_backfill_lids.py",
    "docker cp /tmp/s191_backfill_lids.py $BACKEND:/tmp/s191_backfill_lids.py",
    "docker exec -e CONFIRM=yes $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s191_backfill_lids.py",
]
print(f"Sending to {INSTANCE_ID}...")
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["300"]})
cmd_id = resp["Command"]["CommandId"]
for i in range(60):
    time.sleep(5)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    if inv["Status"] not in ("Pending","InProgress","Delayed"):
        print(inv.get("StandardOutputContent",""))
        if inv.get("StandardErrorContent"): print("STDERR:", inv["StandardErrorContent"][-1000:])
        print(f"Final: {inv['Status']} (exit {inv.get('ResponseCode')})")
        sys.exit(0 if inv["Status"]=="Success" else 1)
print("TIMEOUT"); sys.exit(2)
