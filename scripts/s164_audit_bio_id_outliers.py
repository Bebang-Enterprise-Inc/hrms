"""S164 post-deploy audit: Bio ID outliers

Investigates why `generate_next_bio_id()` returned 9709648 on production
when MEMORY.md says max should be 9001881.

Read-only. Uses SSM to run a Python script inside the frappe backend
container that inspects tabEmployee.attendance_device_id.
"""

from __future__ import annotations

import base64
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

AUDIT_SCRIPT = '''
import os
os.chdir("/home/frappe/frappe-bench/sites")
import frappe
frappe.init(site="hq.bebang.ph")
frappe.connect()

# 1) Overall range of 9XXXXXX format Bio IDs
stats = frappe.db.sql(
    """
    SELECT
        COUNT(*) AS n,
        MIN(CAST(attendance_device_id AS UNSIGNED)) AS min_bio,
        MAX(CAST(attendance_device_id AS UNSIGNED)) AS max_bio
    FROM `tabEmployee`
    WHERE attendance_device_id REGEXP '^9[0-9]{6}$'
    """,
    as_dict=True,
)[0]
print(f"[stats] n={stats['n']} min={stats['min_bio']} max={stats['max_bio']}")

# 2) Top 20 Bio IDs above 9001881 — find the outliers
outliers = frappe.db.sql(
    """
    SELECT name, employee_name, status, attendance_device_id, branch, creation, modified
    FROM `tabEmployee`
    WHERE attendance_device_id REGEXP '^9[0-9]{6}$'
      AND CAST(attendance_device_id AS UNSIGNED) > 9001881
    ORDER BY CAST(attendance_device_id AS UNSIGNED) DESC
    LIMIT 20
    """,
    as_dict=True,
)
print(f"[outliers_above_9001881] count={len(outliers)}")
for row in outliers:
    print(f"  {row['attendance_device_id']} | {row['name']} | {row['employee_name']!r} | status={row['status']} | branch={row['branch']!r} | created={row['creation']}")

# 3) Distribution by 100K bucket
dist = frappe.db.sql(
    """
    SELECT
        FLOOR(CAST(attendance_device_id AS UNSIGNED) / 100000) * 100000 AS bucket,
        COUNT(*) AS n
    FROM `tabEmployee`
    WHERE attendance_device_id REGEXP '^9[0-9]{6}$'
    GROUP BY bucket
    ORDER BY bucket
    """,
    as_dict=True,
)
print(f"[distribution]")
for row in dist:
    print(f"  {row['bucket']:>8}+  n={row['n']}")

# 4) Count any non-9XXXXXX garbage that could confuse the generator regex
garbage_count = frappe.db.sql(
    """
    SELECT COUNT(*) AS n
    FROM `tabEmployee`
    WHERE attendance_device_id IS NOT NULL
      AND attendance_device_id != ''
      AND attendance_device_id NOT REGEXP '^9[0-9]{6}$'
    """,
    as_dict=True,
)[0]
print(f"[non_9xxxxxx_count] {garbage_count['n']}")

# 5) Sample of non-conforming values
non_conforming = frappe.db.sql(
    """
    SELECT name, attendance_device_id, status
    FROM `tabEmployee`
    WHERE attendance_device_id IS NOT NULL
      AND attendance_device_id != ''
      AND attendance_device_id NOT REGEXP '^9[0-9]{6}$'
    LIMIT 10
    """,
    as_dict=True,
)
print(f"[non_conforming_samples]")
for row in non_conforming:
    print(f"  {row['attendance_device_id']!r} | {row['name']} | {row['status']}")

frappe.db.rollback()
print("[done] rollback committed")
'''


def run():
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(AUDIT_SCRIPT.encode()).decode()
    find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"

    commands = [
        f"BACKEND=$({find_cmd})",
        'echo "Backend container: $BACKEND"',
        f"echo '{encoded}' | base64 -d > /tmp/s164_audit.py",
        "docker cp /tmp/s164_audit.py $BACKEND:/tmp/s164_audit.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s164_audit.py",
    ]

    print("Sending S164 Bio ID outlier audit via SSM...")
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands, "executionTimeout": ["300"]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"SSM Command ID: {command_id}")

    for i in range(60):
        time.sleep(5)
        try:
            result = ssm.get_command_invocation(
                CommandId=command_id, InstanceId=INSTANCE_ID
            )
            status = result["Status"]
            if status in ("Success", "Failed", "TimedOut", "Cancelled"):
                print(f"\nStatus: {status}")
                print("\n--- STDOUT ---")
                print(result.get("StandardOutputContent", "(empty)"))
                if result.get("StandardErrorContent"):
                    print("\n--- STDERR ---")
                    print(result["StandardErrorContent"])
                return status == "Success"
        except ssm.exceptions.InvocationDoesNotExist:
            pass
        print(f"  [{i*5}s] Still running...")

    print("TIMEOUT waiting for SSM command")
    return False


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
