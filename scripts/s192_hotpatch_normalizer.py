#!/usr/bin/env python3
"""S192 hot-patch `_normalize_store_name_for_route` in hrms/api/store.py
on every running frappe_backend replica."""
import base64, time, boto3

SSM_INSTANCE = "i-026b7477d27bd46d6"

PATCH = r'''
p = "/home/frappe/frappe-bench/apps/hrms/hrms/api/store.py"
with open(p) as f:
    src = f.read()

sentinel = '# S192: S188 child prefix'
if sentinel in src:
    print("ALREADY_PATCHED")
else:
    old = (
        "def _normalize_store_name_for_route(warehouse_name):\n"
        "\t\"\"\"Normalize a Frappe warehouse name to match the Central Warehouse route map.\"\"\"\n"
        "\tname = (warehouse_name or \"\").upper()\n"
        "\t# Strip company suffixes\n"
        "\tfor suffix in (\n"
        "\t\t\" - BEBANG ENTERPRISE INC.\", \" - BEI\", \" - BKI\",\n"
        "\t\t\" - BEBANG KITCHEN INC.\",\n"
        "\t):\n"
        "\t\tname = name.replace(suffix, \"\")\n"
        "\treturn name.strip()"
    )
    new = (
        "def _normalize_store_name_for_route(warehouse_name):\n"
        "\t\"\"\"Normalize a Frappe warehouse name to match the Central Warehouse route map.\n\n"
        "\tHandles S188 per-store child warehouses whose docnames follow the pattern\n"
        "\t``Bebang Enterprise Inc. - <Store> - BEI-<ABBR>``.\n"
        "\t\"\"\"\n"
        "\timport re\n"
        "\tname = (warehouse_name or \"\").upper()\n\n"
        "\t# S192: S188 child prefix\n"
        "\tif name.startswith(\"BEBANG ENTERPRISE INC. - \"):\n"
        "\t\tname = name[len(\"BEBANG ENTERPRISE INC. - \"):]\n\n"
        "\t# S192: Trailing BEI-XXX / BKI-XXX S188 abbreviation suffixes\n"
        "\tname = re.sub(r\" - BEI-[A-Z0-9]+$\", \"\", name)\n"
        "\tname = re.sub(r\" - BKI-[A-Z0-9]+$\", \"\", name)\n\n"
        "\tfor suffix in (\n"
        "\t\t\" - BEBANG ENTERPRISE INC.\", \" - BEI\", \" - BKI\",\n"
        "\t\t\" - BEBANG KITCHEN INC.\",\n"
        "\t):\n"
        "\t\tname = name.replace(suffix, \"\")\n"
        "\treturn name.strip()"
    )
    if old in src:
        src = src.replace(old, new, 1)
        with open(p, "w") as f:
            f.write(src)
        print("PATCHED")
    else:
        print("NEEDLE_NOT_FOUND")

with open(p) as f:
    post = f.read()
print("FINAL_SENTINEL:", sentinel in post)
'''
enc = base64.b64encode(PATCH.encode()).decode()

cmds = [
    "for BACKEND in $(docker ps --filter name=frappe_backend --format '{{.ID}}'); do "
    f"echo BACKEND=$BACKEND; "
    f"echo '{enc}' | base64 -d > /tmp/s192_patch_norm.py; "
    "docker cp /tmp/s192_patch_norm.py $BACKEND:/tmp/s192_patch_norm.py; "
    "docker exec $BACKEND python /tmp/s192_patch_norm.py; "
    "docker exec $BACKEND bash -c 'find /home/frappe/frappe-bench/apps/hrms -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true'; "
    "docker kill -s HUP $BACKEND 2>/dev/null || true; "
    "done",
    "sleep 8",
    "docker ps --filter name=frappe_backend --format '{{.Names}} {{.Status}}'",
]

ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(
    InstanceIds=[SSM_INSTANCE],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["300"]},
)
cid = r["Command"]["CommandId"]
print("CommandId:", cid)
for _ in range(100):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId=SSM_INSTANCE)
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print("STATUS:", inv["Status"])
        print(inv["StandardOutputContent"])
        if inv["StandardErrorContent"]:
            print("STDERR:", inv["StandardErrorContent"][-1500:])
        break
