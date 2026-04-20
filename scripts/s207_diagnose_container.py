"""Diagnose why S207 deploy hasn't landed on the container."""
from __future__ import annotations
import base64, sys, time
import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"

CMDS = r"""
echo "=== Docker services ==="
sudo docker service ls 2>&1 | head -20
echo ""
echo "=== backend container IDs ==="
sudo docker ps --filter 'name=frappe_backend' --format '{{.ID}} {{.Image}} {{.CreatedAt}} {{.Status}}'
echo ""
BACKEND=$(sudo docker ps --filter 'name=frappe_backend' --format '{{.ID}}' | head -1)
echo "=== backend container image inspect ==="
sudo docker inspect $BACKEND --format 'Image: {{.Image}} | Started: {{.State.StartedAt}}'
echo ""
echo "=== grep preview_allocation in container's labor_allocation.py ==="
sudo docker exec $BACKEND grep -c 'def preview_allocation\|def preview_monthly_allocation\|def post_allocation\|def post_monthly_allocation\|def posting_date_for_slip\|def preview_scheduled' /home/frappe/frappe-bench/apps/hrms/hrms/api/labor_allocation.py 2>&1
echo ""
echo "=== grep each function name ==="
for fn in preview_allocation post_allocation preview_scheduled posting_date_for_slip preview_monthly_allocation post_monthly_allocation; do
  n=$(sudo docker exec $BACKEND grep -c "def ${fn}" /home/frappe/frappe-bench/apps/hrms/hrms/api/labor_allocation.py 2>/dev/null || echo 0)
  echo "$fn: $n"
done
echo ""
echo "=== container's hrms git HEAD ==="
sudo docker exec $BACKEND git -C /home/frappe/frappe-bench/apps/hrms rev-parse HEAD 2>&1 || echo "no git metadata in container (expected)"
echo ""
echo "=== container's hrms labor_allocation.py first 3 lines ==="
sudo docker exec $BACKEND head -3 /home/frappe/frappe-bench/apps/hrms/hrms/api/labor_allocation.py
echo ""
echo "=== patches.txt tail (last 3) ==="
sudo docker exec $BACKEND tail -3 /home/frappe/frappe-bench/apps/hrms/hrms/patches.txt
echo ""
echo "=== posting_date_for_slip in utils ==="
sudo docker exec $BACKEND grep -c "def posting_date_for_slip" /home/frappe/frappe-bench/apps/hrms/hrms/utils/labor_allocation.py 2>&1
"""


def main():
    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [CMDS], "executionTimeout": ["120"]},
    )
    cid = resp["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            print("=== STATUS:", inv["Status"], "===")
            print(inv["StandardOutputContent"])
            if inv["StandardErrorContent"]:
                print("--- STDERR ---")
                print(inv["StandardErrorContent"][:2000])
            return 0 if inv["Status"] == "Success" else 1
    print("TIMEOUT waiting")
    return 2


if __name__ == "__main__":
    sys.exit(main())
