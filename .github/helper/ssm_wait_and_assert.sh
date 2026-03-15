#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <command-id> <instance-id> <label> [waiter-delay] [waiter-max-attempts]" >&2
  exit 2
fi

COMMAND_ID="$1"
INSTANCE_ID="$2"
LABEL="$3"
WAITER_DELAY="${4:-5}"
WAITER_MAX_ATTEMPTS="${5:-120}"

echo "⏳ Waiting for ${LABEL} (command ${COMMAND_ID})..."

wait_rc=0
aws ssm wait command-executed \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --waiter-delay "$WAITER_DELAY" \
  --waiter-max-attempts "$WAITER_MAX_ATTEMPTS" || wait_rc=$?

INVOCATION_JSON=$(aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --output json)

STATUS=$(echo "$INVOCATION_JSON" | jq -r '.Status')
STDOUT=$(echo "$INVOCATION_JSON" | jq -r '.StandardOutputContent // ""')
STDERR=$(echo "$INVOCATION_JSON" | jq -r '.StandardErrorContent // ""')

if [ -n "$STDOUT" ]; then
  printf '%s\n' "$STDOUT"
fi

if [ -n "$STDERR" ]; then
  printf '%s\n' "$STDERR" >&2
fi

if [ "$STATUS" != "Success" ] || [ "$wait_rc" -ne 0 ]; then
  echo "❌ ${LABEL} failed with status: ${STATUS}" >&2
  exit 1
fi

echo "✅ ${LABEL} succeeded."
