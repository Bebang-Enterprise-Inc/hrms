#!/usr/bin/env python3
"""Like s167_ssm_run.py but passes sys.argv[2] as the first arg to the script."""
import base64, sys, time, os, boto3
SCRIPT = sys.argv[1]
ARG = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OPENAI_API_KEY", "")
ssm = boto3.client("ssm", region_name="ap-southeast-1")
INSTANCE_ID = "i-026b7477d27bd46d6"
with open(SCRIPT, "r", encoding="utf-8") as f: code = f.read()
encoded = base64.b64encode(code.encode()).decode()
# base64-encode the arg too to avoid shell-escaping issues
arg_encoded = base64.b64encode(ARG.encode()).decode()
commands = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    'echo "Backend: $BACKEND"',
    f"echo '{encoded}' | base64 -d > /tmp/s167_script.py",
    "docker cp /tmp/s167_script.py $BACKEND:/tmp/s167_script.py",
    f"ARG_DECODED=$(echo '{arg_encoded}' | base64 -d)",
    'docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s167_script.py "$ARG_DECODED"',
]
resp = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
    Parameters={"commands": commands, "executionTimeout": ["300"]})
cmd_id = resp["Command"]["CommandId"]
print(f"Cmd: {cmd_id}")
for i in range(60):
    time.sleep(2)
    r = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
    if r["Status"] in ("Success","Failed","Cancelled","TimedOut"):
        print(f"Status: {r['Status']}")
        print(r.get("StandardOutputContent","")[:5000])
        if r.get("StandardErrorContent"): print("STDERR:", r.get("StandardErrorContent","")[:2000])
        sys.exit(0 if r["Status"]=="Success" else 1)
sys.exit(2)
