"""Dispatch s199_company_rename_allcaps.py via SSM.

Usage:
  doppler run --project bei-erp --config dev -- python scripts/s199_ssm_dispatch.py --dry-run
  doppler run --project bei-erp --config dev -- python scripts/s199_ssm_dispatch.py --confirm
"""
import argparse, base64, os, sys, time, boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
SCRIPT = "scripts/s199_company_rename_allcaps.py"
OUTPUT_DIR = "output/s199/state"

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--confirm", action="store_true")
args = parser.parse_args()
if not args.dry_run and not args.confirm:
    print("ERROR: --dry-run or --confirm required"); sys.exit(2)

os.environ.setdefault("AWS_REGION", "ap-southeast-1")
ssm = boto3.client("ssm", region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])

with open(SCRIPT, "r", encoding="utf-8") as f: script = f.read()
encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"
script_args = "--dry-run" if args.dry_run else ""

commands = [
    f"BACKEND=$({find_cmd})",
    'if [ -z "$BACKEND" ]; then echo "NO BACKEND CONTAINER"; exit 1; fi',
    'echo "Backend: $BACKEND"',
    f"echo '{encoded}' | base64 -d > /tmp/s199_rename.py",
    "docker cp /tmp/s199_rename.py $BACKEND:/tmp/s199_rename.py",
    f"docker exec -e CONFIRM={'yes' if args.confirm else ''} $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s199_rename.py {script_args}",
    "docker cp $BACKEND:/tmp/s199_rename_actions.csv /tmp/s199_rename_actions.csv 2>/dev/null || true",
    "cat /tmp/s199_rename_actions.csv 2>/dev/null | head -100 || echo '(no log)'",
]

print(f"Sending to {INSTANCE_ID} ({'DRY-RUN' if args.dry_run else 'LIVE'})...")
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["1800"]})
cmd_id = resp["Command"]["CommandId"]
print(f"Command ID: {cmd_id}")

os.makedirs(OUTPUT_DIR, exist_ok=True)
out_path = os.path.join(OUTPUT_DIR, f"rename_{'dryrun' if args.dry_run else 'live'}_stdout.txt")

for i in range(180):
    time.sleep(10)
    inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    status = inv["Status"]
    print(f"  [{i*10:4d}s] {status}")
    if status not in ("Pending", "InProgress", "Delayed"):
        stdout = inv.get("StandardOutputContent", "")
        stderr = inv.get("StandardErrorContent", "")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(stdout)
            if stderr: f.write("\n--- STDERR ---\n" + stderr)
        try:
            print(stdout[-10000:] if len(stdout) > 10000 else stdout)
        except Exception:
            print("(stdout not printable; see file)")
        if stderr:
            try: print("STDERR:", stderr[-2000:])
            except Exception: pass
        print(f"\nSaved: {out_path}")
        print(f"Final: {status} (exit {inv.get('ResponseCode')})")
        sys.exit(0 if status == "Success" else 1)

print("TIMEOUT"); sys.exit(2)
