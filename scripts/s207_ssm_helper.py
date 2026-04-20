"""Shared SSM helper for S207 scripts (Appendix A boilerplate inlined).

Every S207 script that runs Python inside the production Frappe container
uses :func:`run_via_ssm` to execute a script string end-to-end.

Constants:
    INSTANCE_ID = i-026b7477d27bd46d6  (BEI production Frappe EC2)
    REGION      = ap-southeast-1       (Singapore)

Returns (exit_code, stdout, stderr). Poll timeout is 15 minutes.
"""

from __future__ import annotations

import base64
import sys
import time


INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

# Appendix A Frappe Init Boilerplate — pre-create log dirs before any frappe import
# because Frappe's logger crashes on missing rotation-handler paths. Keep this
# string as the preamble to every Python script rendered into run_via_ssm.
FRAPPE_PREAMBLE = r'''
import os, sys, json, traceback
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
'''.strip()


def run_via_ssm(script_body: str, timeout_seconds: int = 900) -> tuple[int, str, str]:
    """Execute `FRAPPE_PREAMBLE + script_body` inside the prod container.

    Callers don't need to include the preamble — this helper prepends it.
    `script_body` must be self-contained Python (no shell escapes); stdout is
    captured as the output. To emit structured data, print JSON between the
    markers ===RESULT_JSON_BEGIN=== and ===RESULT_JSON_END=== so downstream
    parsers can extract it deterministically even if Frappe logs noise.

    Returns (exit_code, stdout, stderr). On SSM timeout, returns (2, "", "timeout").
    """
    try:
        import boto3
    except ImportError:
        return 3, "", "boto3 not installed; pip install boto3"

    full_script = FRAPPE_PREAMBLE + "\n\n" + script_body + "\n\nfrappe.destroy()\n"
    encoded = base64.b64encode(full_script.encode()).decode()

    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{encoded}' | base64 -d > /tmp/s207_task.py",
        "docker cp /tmp/s207_task.py $BACKEND:/tmp/s207_task.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s207_task.py",
    ]

    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout_seconds)]},
    )
    cid = resp["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)

    # Poll every 3s; cap at timeout_seconds (default 15 min).
    max_iters = max(10, timeout_seconds // 3)
    for _ in range(max_iters):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        if status in ("Success", "Failed", "TimedOut", "Cancelled"):
            exit_code = 0 if status == "Success" else 1
            return exit_code, inv["StandardOutputContent"], inv["StandardErrorContent"]
    return 2, "", f"poll timeout after {timeout_seconds}s"


def extract_result_json(stdout: str) -> dict | None:
    """Pull the JSON block between ===RESULT_JSON_BEGIN=== and ===RESULT_JSON_END===.

    Returns None if markers not found (so callers can detect script failure vs.
    empty result). Matches the convention used by scripts/s206_verify_all.py.
    """
    begin = "===RESULT_JSON_BEGIN==="
    end = "===RESULT_JSON_END==="
    if begin not in stdout or end not in stdout:
        return None
    body = stdout.split(begin, 1)[1].split(end, 1)[0].strip()
    import json as _json
    try:
        return _json.loads(body)
    except _json.JSONDecodeError:
        return None


if __name__ == "__main__":
    # Smoke test: print the site name
    body = '''
print("===RESULT_JSON_BEGIN===")
print(json.dumps({"site": frappe.local.site, "user": frappe.session.user}))
print("===RESULT_JSON_END===")
'''
    rc, out, err = run_via_ssm(body)
    print(f"rc={rc}")
    print(f"stdout:\n{out}")
    if err:
        print(f"stderr:\n{err}")
    sys.exit(rc)
