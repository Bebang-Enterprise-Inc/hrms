#!/usr/bin/env python3
"""Verify the hot-patched _normalize_store_name_for_route works inside the
Frappe container."""
import base64, time, boto3

TEST = r'''
from hrms.api.store import _normalize_store_name_for_route as n
for w in [
    "Bebang Enterprise Inc. - SM Megamall - BEI-SMG",
    "SM Tanza - BEI",
    "The Grid - Rockwell - BEI",
    "Ayala Evo - BEI",
    "Araneta Gateway - BEI",
]:
    try:
        print(repr(w), "->", repr(n(w)))
    except Exception as e:
        print(repr(w), "EXC:", type(e).__name__, e)
'''
enc = base64.b64encode(TEST.encode()).decode()

cmds = [
    f"BACKEND=$(docker ps --filter name=frappe_backend --format '{{{{.ID}}}}' | head -1); "
    f"echo '{enc}' | base64 -d > /tmp/s192_verify.py; "
    "docker cp /tmp/s192_verify.py $BACKEND:/tmp/s192_verify.py; "
    "docker exec $BACKEND bash -c 'cd /home/frappe/frappe-bench && ./env/bin/python /tmp/s192_verify.py'",
]

ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=["i-026b7477d27bd46d6"],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(40):
    time.sleep(2)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print("STDOUT:")
        print(inv["StandardOutputContent"])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-800:])
        break
