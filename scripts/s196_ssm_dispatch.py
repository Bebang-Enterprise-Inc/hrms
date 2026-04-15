"""Dispatch s196_data_migration.py to the Frappe backend container via SSM.

Usage:
  # Dry run (no mutations):
  doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch.py --dry-run

  # Live run (requires CONFIRM=yes passed to container):
  doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch.py --confirm

  # With pre-Phase-2 bench backup (CR-3):
  doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch.py --confirm --backup
"""
import argparse
import base64
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
MIGRATION_SCRIPT = "scripts/s196_data_migration.py"

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="Preview planned ops without executing")
parser.add_argument("--confirm", action="store_true", help="Pass CONFIRM=yes to container (live run)")
parser.add_argument("--backup", action="store_true", help="Run bench backup BEFORE migration (CR-3)")
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

commands = [
    f"BACKEND=$({find_cmd})",
    'if [ -z "$BACKEND" ]; then echo "NO BACKEND CONTAINER FOUND"; exit 1; fi',
    'echo "Backend container: $BACKEND"',
]

if args.backup and not args.dry_run:
    # CR-3: Pre-Phase-2 bench backup via explicit docker exec (Python dispatcher can't run bench CLI)
    commands.extend([
        'echo "=== Pre-Phase-2 bench backup (CR-3) ==="',
        "BACKUP_OUTPUT=$(docker exec $BACKEND /home/frappe/frappe-bench/env/bin/bench --site hq.bebang.ph backup --with-files 2>&1)",
        'echo "$BACKUP_OUTPUT"',
        'BACKUP_PATH=$(echo "$BACKUP_OUTPUT" | grep -oE "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/backups/[^ ]*" | head -1)',
        'if [ -z "$BACKUP_PATH" ]; then echo "BACKUP FAILED — path not captured; ABORTING"; exit 1; fi',
        'echo "Backup path: $BACKUP_PATH"',
        'echo "$BACKUP_PATH" > /tmp/s196_backup_path.txt',
    ])

# Upload + execute migration script
env_prefix = "CONFIRM=yes " if args.confirm else ""
script_args = "--dry-run" if args.dry_run else ""
commands.extend([
    f"echo '{encoded}' | base64 -d > /tmp/s196_data_migration.py",
    "docker cp /tmp/s196_data_migration.py $BACKEND:/tmp/s196_data_migration.py",
    f"docker exec -e CONFIRM={'yes' if args.confirm else ''} $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s196_data_migration.py {script_args}",
    "docker cp $BACKEND:/tmp/s196_phase_2_rename_matrix_executed.csv /tmp/s196_phase_2_rename_matrix_executed.csv 2>/dev/null || true",
    "cat /tmp/s196_phase_2_rename_matrix_executed.csv 2>/dev/null | head -60 || echo '(no action log)'",
])

print(f"Sending {len(commands)} commands to {INSTANCE_ID} ({'DRY-RUN' if args.dry_run else 'LIVE'})...")
resp = ssm.send_command(
    InstanceIds=[INSTANCE_ID],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["1200"]},
)
cmd_id = resp["Command"]["CommandId"]
print(f"Command ID: {cmd_id}")
print("Polling for completion...")

for i in range(120):  # up to 20 minutes
    time.sleep(10)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    status = inv["Status"]
    print(f"  [{i*10:4d}s] status={status}")
    if status not in ("Pending", "InProgress", "Delayed"):
        print(f"\n=== STDOUT ===\n{inv.get('StandardOutputContent', '')}")
        if inv.get("StandardErrorContent"):
            print(f"\n=== STDERR ===\n{inv.get('StandardErrorContent', '')}")
        print(f"\nFinal status: {status} (exit code {inv.get('ResponseCode')})")
        sys.exit(0 if status == "Success" else 1)

print("TIMEOUT after 20 minutes")
sys.exit(2)
