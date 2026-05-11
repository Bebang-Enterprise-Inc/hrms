#!/usr/bin/env python3
"""SSM-execute probe_per_store_readiness.py in production Frappe backend.

Read-only. Writes result JSON next to this script.
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
HERE = Path(__file__).parent
PROBE = HERE / "probe_per_store_readiness.py"
OUT = HERE / "probe_result.json"


def main() -> int:
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(PROBE.read_text(encoding="utf-8").encode()).decode()

    cmds = [
        "set -e",
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        'if [ -z "$BACKEND" ]; then echo "BACKEND_NOT_FOUND" && exit 1; fi',
        f"echo '{encoded}' | base64 -d > /tmp/s244_probe.py",
        "docker cp /tmp/s244_probe.py $BACKEND:/tmp/s244_probe.py",
        "docker exec $BACKEND bash -lc 'cd /home/frappe/frappe-bench && env/bin/python /tmp/s244_probe.py'",
        "docker cp $BACKEND:/tmp/s244_probe_result.json /tmp/s244_probe_result.json",
        "gzip -c /tmp/s244_probe_result.json > /tmp/s244_probe_result.json.gz",
        "echo S244_FILE_BEGIN",
        "base64 -w0 /tmp/s244_probe_result.json.gz; echo",
        "echo S244_FILE_END",
    ]

    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds},
        TimeoutSeconds=600,
    )
    cmd_id = resp["Command"]["CommandId"]
    print(f"command_id={cmd_id}", flush=True)

    while True:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=INSTANCE_ID)
        status = inv["Status"]
        if status in ("Pending", "InProgress", "Delayed"):
            print(f"  status={status}", flush=True)
            continue
        break

    print(f"final_status={status}")
    out_text = inv.get("StandardOutputContent", "")
    err_text = inv.get("StandardErrorContent", "")

    if "S244_FILE_BEGIN" in out_text and "S244_FILE_END" in out_text:
        b64_body = out_text.split("S244_FILE_BEGIN")[1].split("S244_FILE_END")[0].strip()
        try:
            import gzip
            decoded_gz = base64.b64decode(b64_body)
            decoded = gzip.decompress(decoded_gz).decode("utf-8")
            data = json.loads(decoded)
            OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            print(f"wrote {OUT} ({len(decoded)} bytes)")
            # Quick summary to stdout
            s = data.get("summary", {})
            print("\n=== SUMMARY ===")
            print(f"  total candidate buyer companies: {s.get('total_candidate_buyer_companies')}")
            print(f"  ready for PI generation        : {s.get('ready_for_pi_generation')}")
            for key in ("missing_customer", "missing_warehouse", "non_php_currency",
                        "missing_cost_center", "missing_any_acct", "missing_bki_supplier_acct"):
                lst = s.get(key, [])
                if lst:
                    print(f"  {key} ({len(lst)}): {lst[:8]}{'...' if len(lst) > 8 else ''}")
            return 0
        except Exception as e:
            print(f"PARSE_ERROR: {e}")
            OUT.write_text(out_text, encoding="utf-8")
            return 2

    print("--- STDOUT ---")
    print(out_text)
    print("--- STDERR ---")
    print(err_text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
