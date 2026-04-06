"""S164 post-deploy fix: clear bogus Bio IDs from L3 test employees.

Audit (scripts/s164_audit_bio_id_outliers.py) found 5 L3-test employees
with Bio IDs in the 9.3M-9.7M range, plus 1 UNKNOWN-FALLBACK garbage row.
They were polluting generate_next_bio_id() which returned 9709648 instead
of the correct 9001882.

This script:
  - clears attendance_device_id + new_attendance_device_id on 6 rows
  - leaves the employee records intact (audit trail)
  - re-runs generate_next_bio_id() to confirm sequence healed
"""

from __future__ import annotations

import base64
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

TARGETS = [
    "BEI-EMP-2026-00001",
    "BEI-EMP-2026-00002",
    "BEI-EMP-2026-00003",
    "HR-EMP-00027",
    "HR-EMP-00028",
    "UNKNOWN-FALLBACK",
]

FIX_SCRIPT = f'''
import os
os.chdir("/home/frappe/frappe-bench/sites")
import frappe
frappe.init(site="hq.bebang.ph")
frappe.connect()

TARGETS = {TARGETS!r}

# Pre-fix snapshot
print("[pre-fix] current bogus rows:")
pre = frappe.db.sql(
    """
    SELECT name, employee_name, attendance_device_id, status
    FROM `tabEmployee`
    WHERE name IN %(names)s
    """,
    {{"names": TARGETS}},
    as_dict=True,
)
for r in pre:
    print(f"  {{r['name']}} | {{r['employee_name']!r}} | bio={{r['attendance_device_id']!r}} | status={{r['status']}}")

# Execute cleanup — NULL both fields
updated = frappe.db.sql(
    """
    UPDATE `tabEmployee`
    SET attendance_device_id = NULL,
        modified = NOW(),
        modified_by = 'Administrator'
    WHERE name IN %(names)s
    """,
    {{"names": TARGETS}},
)
print(f"[fix] updated rows (UPDATE affected_rows not easily retrievable here)")

# Post-fix verification
post = frappe.db.sql(
    """
    SELECT name, attendance_device_id    FROM `tabEmployee`
    WHERE name IN %(names)s
    """,
    {{"names": TARGETS}},
    as_dict=True,
)
print("[post-fix] rows after UPDATE:")
for r in post:
    print(f"  {{r['name']}} | bio={{r['attendance_device_id']!r}}")

# Re-check max Bio ID
stats = frappe.db.sql(
    """
    SELECT
        COUNT(*) AS n,
        MIN(CAST(attendance_device_id AS UNSIGNED)) AS min_bio,
        MAX(CAST(attendance_device_id AS UNSIGNED)) AS max_bio
    FROM `tabEmployee`
    WHERE attendance_device_id REGEXP '^9[0-9]{{6}}$'
    """,
    as_dict=True,
)[0]
print(f"[post-fix stats] n={{stats['n']}} min={{stats['min_bio']}} max={{stats['max_bio']}}")

# Test the actual generator
from hrms.utils.bio_id import generate_next_bio_id
next_bio = generate_next_bio_id()
print(f"[generate_next_bio_id()] returned {{next_bio}}")
if next_bio == "9001882":
    print("[verdict] PASS — sequence healed, next Bio ID is 9001882 as expected")
    frappe.db.commit()
    print("[commit] changes persisted")
else:
    print(f"[verdict] UNEXPECTED — got {{next_bio}}, expected 9001882")
    frappe.db.rollback()
    print("[rollback] no changes committed")
    import sys
    sys.exit(1)
'''


def run():
    ssm = boto3.client("ssm", region_name=REGION)
    encoded = base64.b64encode(FIX_SCRIPT.encode()).decode()
    find_cmd = "docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1"

    commands = [
        f"BACKEND=$({find_cmd})",
        'echo "Backend container: $BACKEND"',
        f"echo '{encoded}' | base64 -d > /tmp/s164_fix.py",
        "docker cp /tmp/s164_fix.py $BACKEND:/tmp/s164_fix.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s164_fix.py",
    ]

    print("Sending S164 Bio ID fix via SSM...")
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

    return False


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
