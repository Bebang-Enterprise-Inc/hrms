#!/bin/bash
# S237 regression-detection verifier
# Run anytime to confirm the L3 test pollution cleanup is intact.
# Usage: bash verify_s237_state.sh
# Exit codes:
#   0 = state intact (ZERO test rows on 9xxxxxx, expected 6 rows on 3xxxxxx, ATC has no test rows)
#   1 = regression detected — at least one assertion failed
#   2 = SSM/Frappe environment unreachable
#
# Requires: AWS CLI + SSM access to i-026b7477d27bd46d6 + the deploy password.
# Run with: bash verify_s237_state.sh # 2289454

set -e
INSTANCE="i-026b7477d27bd46d6"

cat > /tmp/s237_check.sh <<'INNER'
#!/bin/bash
FB=$(docker ps --format '{{.Names}}' | grep frappe_backend | head -1)
echo "=== S237 STATE VERIFICATION ==="

# Check 1: ZERO test rows still on 9xxxxxx
N_TEST_9X=$(docker exec $FB bash -lc "cd /home/frappe/frappe-bench && bench --site hq.bebang.ph mariadb -N -e \"SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}\$' AND (UPPER(employee_name) LIKE '%L3%' OR UPPER(employee_name) LIKE '%TEST%' OR UPPER(employee_name) LIKE '%RETEST%' OR UPPER(employee_name) LIKE '%CONFLICT%' OR UPPER(employee_name) LIKE '%MARIA SANTOS%' OR UPPER(employee_name) LIKE '%BROWSERTEST%' OR UPPER(employee_name) LIKE '%APPROVETEST%');\"")
echo "test rows on 9xxxxxx: $N_TEST_9X (expect 0)"

# Check 2: 6 test rows on 3xxxxxx
N_TEST_3X=$(docker exec $FB bash -lc "cd /home/frappe/frappe-bench && bench --site hq.bebang.ph mariadb -N -e \"SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id LIKE '3%';\"")
echo "test rows on 3xxxxxx: $N_TEST_3X (expect 6)"

# Check 3: ATC has zero test rows in 3xxxxxx
N_TEST_3X_ATC=$(docker exec $FB bash -lc "cd /home/frappe/frappe-bench && bench --site hq.bebang.ph mariadb -N -e \"SELECT COUNT(*) FROM tabEmployee WHERE branch='ALABANG TOWN CENTER' AND attendance_device_id LIKE '3%';\"")
echo "3xxxxxx test rows still at ALABANG TOWN CENTER: $N_TEST_3X_ATC (expect 0)"

# Check 4: Real Bio IDs 9001893 + 9001903 NOT held by ghosts
GHOST_BIOS=$(docker exec $FB bash -lc "cd /home/frappe/frappe-bench && bench --site hq.bebang.ph mariadb -N -e \"SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id IN ('9001893','9001903') AND (UPPER(employee_name) LIKE '%TEST%' OR UPPER(employee_name) LIKE '%L3%' OR UPPER(employee_name) LIKE '%MARIA SANTOS%');\"")
echo "real Bio IDs still held by ghosts (9001893/9001903): $GHOST_BIOS (expect 0)"

# Verdict
if [[ "$N_TEST_9X" == "0" && "$N_TEST_3X" == "6" && "$N_TEST_3X_ATC" == "0" && "$GHOST_BIOS" == "0" ]]; then
  echo "VERDICT: PASS (S237 state intact)"
  exit 0
else
  echo "VERDICT: FAIL (regression detected)"
  exit 1
fi
INNER

B64=$(base64 -w 0 /tmp/s237_check.sh)
PARAMS=$(printf '{"commands":["echo %s | base64 -d > /tmp/s237_check.sh && bash /tmp/s237_check.sh"]}' "$B64")
echo "$PARAMS" > /tmp/s237_ssm_params.json

CMDID=$(aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript --parameters file:///tmp/s237_ssm_params.json --region ap-southeast-1 --query 'Command.CommandId' --output text)

# Poll until complete
until aws ssm get-command-invocation --command-id "$CMDID" --instance-id "$INSTANCE" --region ap-southeast-1 --query 'Status' --output text 2>/dev/null | grep -qE "^(Success|Failed|TimedOut)$"; do
  sleep 3
done

STATUS=$(aws ssm get-command-invocation --command-id "$CMDID" --instance-id "$INSTANCE" --region ap-southeast-1 --query 'Status' --output text)
aws ssm get-command-invocation --command-id "$CMDID" --instance-id "$INSTANCE" --region ap-southeast-1 --query 'StandardOutputContent' --output text

if [[ "$STATUS" != "Success" ]]; then
  echo "SSM call failed: $STATUS"
  exit 2
fi
