"""Pull /tmp/s196_warehouse_snapshot.csv via gzip+base64 to avoid SSM output truncation."""
import os
import sys
import time
import base64
import gzip
import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
OUTPUT = "output/s196/state/warehouse_snapshot.csv"

os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client("ssm", region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])

commands = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    "docker cp $BACKEND:/tmp/s196_warehouse_snapshot.csv /tmp/snap.csv",
    "gzip -c /tmp/snap.csv | base64 -w0",
]

resp = ssm.send_command(InstanceIds=[INSTANCE_ID],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["300"]})
cid = resp["Command"]["CommandId"]
for i in range(60):
    time.sleep(5)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
    if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
        stdout = inv.get("StandardOutputContent", "").strip()
        # Last line is the base64+gzip payload
        lines = stdout.split("\n")
        b64 = lines[-1]
        data = gzip.decompress(base64.b64decode(b64))
        os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
        with open(OUTPUT, "wb") as f:
            f.write(data)
        print(f"Pulled {len(data)} bytes to {OUTPUT}")
        sys.exit(0 if inv["Status"] == "Success" else 1)
print("timeout")
sys.exit(2)
