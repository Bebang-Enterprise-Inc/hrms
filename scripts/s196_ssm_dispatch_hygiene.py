"""Dispatch s196_data_hygiene.py to the Frappe backend container via SSM.

Usage:
  # Dry run (no mutations):
  doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch_hygiene.py --dry-run

  # Live run (requires CONFIRM=yes passed to container):
  doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch_hygiene.py --confirm
"""
import argparse
import base64
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
MIGRATION_SCRIPT = "scripts/s196_data_hygiene.py"
OUTPUT_DIR = "output/s196/state"

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--confirm", action="store_true")
args = parser.parse_args()

if not args.dry_run and not args.confirm:
    print("ERROR: must pass --dry-run or --confirm")
    sys.exit(2)

os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client(
    "ssm",
    region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)

with open(MIGRATION_SCRIPT, "r", encoding="utf-8") as f:
    script = f.read()
encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")

find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"
script_args = "--dry-run" if args.dry_run else ""

commands = [
    f"BACKEND=$({find_cmd})",
    'if [ -z "$BACKEND" ]; then echo "NO BACKEND CONTAINER FOUND"; exit 1; fi',
    'echo "Backend container: $BACKEND"',
    f"echo '{encoded}' | base64 -d > /tmp/s196_data_hygiene.py",
    "docker cp /tmp/s196_data_hygiene.py $BACKEND:/tmp/s196_data_hygiene.py",
    (
        f"docker exec -e CONFIRM={'yes' if args.confirm else ''} "
        f"$BACKEND /home/frappe/frappe-bench/env/bin/python "
        f"/tmp/s196_data_hygiene.py {script_args}"
    ),
    "docker cp $BACKEND:/tmp/s196_data_hygiene_actions.csv /tmp/s196_data_hygiene_actions.csv 2>/dev/null || true",
    "docker cp $BACKEND:/tmp/s196_data_hygiene_audit.json /tmp/s196_data_hygiene_audit.json 2>/dev/null || true",
    "cat /tmp/s196_data_hygiene_actions.csv 2>/dev/null | head -80 || echo '(no action log)'",
    "echo '--- AUDIT ---'",
    "cat /tmp/s196_data_hygiene_audit.json 2>/dev/null | head -60 || echo '(no audit)'",
]

print(f"Sending {len(commands)} commands to {INSTANCE_ID} ({'DRY-RUN' if args.dry_run else 'LIVE'})...")
resp = ssm.send_command(
    InstanceIds=[INSTANCE_ID],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["1800"]},
)
cmd_id = resp["Command"]["CommandId"]
print(f"Command ID: {cmd_id}")
print("Polling for completion...")

os.makedirs(OUTPUT_DIR, exist_ok=True)
stdout_path = os.path.join(
    OUTPUT_DIR,
    f"hygiene_{'dryrun' if args.dry_run else 'live'}_stdout.txt",
)

for i in range(180):
    time.sleep(10)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    status = inv["Status"]
    print(f"  [{i*10:4d}s] status={status}")
    if status not in ("Pending", "InProgress", "Delayed"):
        stdout = inv.get("StandardOutputContent", "")
        stderr = inv.get("StandardErrorContent", "")
        with open(stdout_path, "w", encoding="utf-8") as f:
            f.write(stdout)
            if stderr:
                f.write("\n--- STDERR ---\n")
                f.write(stderr)
        # Also echo the key sections to console (safely)
        try:
            print(stdout[-8000:] if len(stdout) > 8000 else stdout)
        except Exception:
            print("(stdout contains characters not printable on this terminal; see file)")
        if stderr:
            try:
                print("=== STDERR ===")
                print(stderr[-2000:] if len(stderr) > 2000 else stderr)
            except Exception:
                print("(stderr contains characters not printable on this terminal; see file)")
        print(f"\nStdout saved to: {stdout_path}")
        print(f"Final status: {status} (exit code {inv.get('ResponseCode')})")
        sys.exit(0 if status == "Success" else 1)

print("TIMEOUT after 30 minutes")
sys.exit(2)
