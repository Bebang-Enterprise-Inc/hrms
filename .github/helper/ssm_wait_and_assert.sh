#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <command-id> <instance-id> <label> [poll-interval-seconds] [max-polls]" >&2
  exit 2
fi

COMMAND_ID="$1"
INSTANCE_ID="$2"
LABEL="$3"
POLL_INTERVAL="${4:-5}"
MAX_POLLS="${5:-120}"

echo "⏳ Waiting for ${LABEL} (command ${COMMAND_ID})..."

STATUS="Pending"
INVOCATION_JSON=""
POLL=1

while [ "$POLL" -le "$MAX_POLLS" ]; do
  if INVOCATION_JSON=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --output json 2>/dev/null); then
    STATUS=$(echo "$INVOCATION_JSON" | jq -r '.Status')
    case "$STATUS" in
      Success|Cancelled|TimedOut|Failed|Cancelling)
        break
        ;;
    esac
  fi

  sleep "$POLL_INTERVAL"
  POLL=$((POLL + 1))
done

if [ -z "$INVOCATION_JSON" ]; then
  echo "❌ ${LABEL} never produced an invocation record." >&2
  exit 1
fi

STDOUT=$(echo "$INVOCATION_JSON" | jq -r '.StandardOutputContent // ""')
STDERR=$(echo "$INVOCATION_JSON" | jq -r '.StandardErrorContent // ""')

if [ -n "$STDOUT" ]; then
  printf '%s\n' "$STDOUT"
fi

if [ -n "$STDERR" ]; then
  printf '%s\n' "$STDERR" >&2
fi

if [ "$STATUS" = "Pending" ] || [ "$STATUS" = "InProgress" ] || [ "$STATUS" = "Delayed" ]; then
  echo "❌ ${LABEL} did not finish within ${MAX_POLLS} polls." >&2
  exit 1
fi

if [ "$STATUS" != "Success" ]; then
  echo "❌ ${LABEL} failed with status: ${STATUS}" >&2
  exit 1
fi

echo "✅ ${LABEL} succeeded."
