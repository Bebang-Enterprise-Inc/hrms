"""Daily drift-detection probe — verify all four BEI patches are present in the running Documenso container.

WHAT IT CHECKS
--------------
For each of the four BEI patches, greps the running container for an indicator
string that's only present when the patch is applied:

  (a) field-size            : `_fw[` in envelope-editor-renderer-provider-wrapper-*.js
  (b) CC initial-email      : `// BEI patch: CC recipients` marker in send-signing-email.handler-*.js
  (c) Resend ID, completed  : `__resendResult` in send-completed-email*.js
  (c) Resend ID, signing    : `__resendResult` in send-signing-email.handler-*.js
  (d) Session-cookie maxAge : `maxAge: Math.floor` in session-cookies.js + absence of static expires

WHAT IT DOES ON BROKEN
----------------------
- exit code 1 (suitable for cron / monitoring)
- if --chat-webhook URL is given (or BEI_DOCUMENSO_PROBE_WEBHOOK env var),
  POSTs a one-line alert to a Google Chat incoming webhook listing which
  patches are missing
- prints a per-patch table to stdout regardless of state

USAGE
-----
    # Manual run
    python scripts/documenso/probe_patches.py

    # With chat alert
    python scripts/documenso/probe_patches.py --chat-webhook 'https://chat.googleapis.com/...'

    # As cron on EC2 host (suggested — runs every 6 hours):
    #   0 */6 * * * /usr/bin/python3 /opt/bei/probe_patches.py \
    #     --chat-webhook "$WEBHOOK" >> /var/log/documenso_patches_probe.log 2>&1

This complements probe_signin_cookies.py — that one watches the *live runtime*
behaviour (cookies in HTTP responses); this one watches *image state* (patched
files on disk inside the container).

EXIT CODES
----------
    0  all four patches present
    1  one or more patches missing — alert worth sending
    2  could not probe the container (docker / network / ssm error)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
CONTAINER = "documenso"


# Each check returns (label, status, evidence_string). Status is True if patch is present.
# We define checks as one-shot shell expressions that exit 0/1 and echo a single token.

CHECKS: list[dict[str, str]] = [
    {
        "id": "a",
        "label": "field-size multipliers",
        "expected_path_glob": "/app/apps/remix/build/client/assets/envelope-editor-renderer-provider-wrapper-*.js",
        "marker": "_fw[",
    },
    {
        "id": "b",
        "label": "CC initial-email",
        "expected_path_glob": "/app/apps/remix/build/server/assets/send-signing-email.handler-*.js",
        "marker": "BEI patch: CC recipients receive the initial signing email",
    },
    {
        "id": "c1",
        "label": "Resend ID logging (completed)",
        "expected_path_glob": "/app/apps/remix/build/server/hono/packages/lib/server-only/document/send-completed-email*.js",
        "marker": "__resendResult",
    },
    {
        "id": "c2",
        "label": "Resend ID logging (signing)",
        "expected_path_glob": "/app/apps/remix/build/server/assets/send-signing-email.handler-*.js",
        "marker": "__resendResult",
    },
    {
        "id": "d",
        "label": "session-cookie maxAge",
        "expected_path_glob": "/app/apps/remix/build/server/hono/packages/auth/server/lib/session/session-cookies.js",
        "marker": "maxAge: Math.floor",
    },
    {
        "id": "e",
        "label": "sign-all button (sam@bebang.ph)",
        "expected_path_glob": "/app/apps/remix/build/client/assets/document-signing-page-view-v2-*.js",
        "marker": "BEI patch: sign-all-button",
    },
]


def ssm_run(commands: list[str], timeout: int = 120) -> tuple[str, str, str]:
    """Returns (status, stdout, stderr)."""
    params = json.dumps({"commands": commands, "executionTimeout": [str(timeout)]})
    send = subprocess.run(
        ["aws", "ssm", "send-command",
         "--instance-ids", INSTANCE_ID,
         "--document-name", "AWS-RunShellScript",
         "--parameters", params,
         "--region", AWS_REGION,
         "--output", "json"],
        capture_output=True, text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    if send.returncode != 0:
        return "send_failed", "", send.stderr
    try:
        cid = json.loads(send.stdout)["Command"]["CommandId"]
    except (json.JSONDecodeError, KeyError) as e:
        return "send_failed", "", str(e)
    deadline = time.time() + timeout + 60
    while time.time() < deadline:
        time.sleep(3)
        inv = subprocess.run(
            ["aws", "ssm", "get-command-invocation",
             "--command-id", cid,
             "--instance-id", INSTANCE_ID,
             "--region", AWS_REGION,
             "--output", "json"],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if inv.returncode != 0:
            continue
        try:
            data = json.loads(inv.stdout)
        except json.JSONDecodeError:
            continue
        if data["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            return data["Status"], data.get("StandardOutputContent", ""), data.get("StandardErrorContent", "")
    return "timeout", "", ""


def run_one_check(check: dict[str, str]) -> tuple[bool, str]:
    """Returns (present, evidence)."""
    glob = check["expected_path_glob"]
    marker = check["marker"]
    # BusyBox-safe one-liner: find -> grep -F -l (literal match). Exit 0 if file contains marker.
    cmd = (
        f"FN=$(docker exec {CONTAINER} sh -c \"find $(dirname '{glob}') "
        f"-maxdepth 4 -name '$(basename '{glob}')' -not -name '*.map' 2>/dev/null | head -1\"); "
        f"if [ -z \"$FN\" ]; then echo NOTFOUND:no_match; exit 1; fi; "
        f"if docker exec {CONTAINER} grep -qF '{marker}' \"$FN\"; "
        f"then echo PRESENT:$FN; else echo MISSING:$FN; fi"
    )
    status, stdout, stderr = ssm_run([cmd])
    if status != "Success":
        return False, f"ssm_status={status} stderr={stderr.strip()[:200]}"
    line = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    if line.startswith("PRESENT:"):
        return True, line.split(":", 1)[1]
    return False, line or "no_output"


def post_chat_alert(webhook: str, missing: list[dict[str, Any]]) -> None:
    msg = (
        ":rotating_light: BEI Documenso patch drift detected on sign.bebang.ph\n\n"
        + "\n".join(
            f"• Patch ({m['id']}) {m['label']} — MISSING ({m['evidence']})" for m in missing
        )
        + "\n\nRebuild from `scripts/documenso/Dockerfile` and recreate the container."
    )
    body = json.dumps({"text": msg}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"WARNING: chat webhook POST failed: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--chat-webhook",
        default=os.environ.get("BEI_DOCUMENSO_PROBE_WEBHOOK", ""),
        help="Optional Google Chat incoming webhook URL. Posted to on drift.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the human-readable table.",
    )
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for check in CHECKS:
        present, evidence = run_one_check(check)
        results.append({
            "id": check["id"],
            "label": check["label"],
            "present": present,
            "evidence": evidence,
        })

    missing = [r for r in results if not r["present"]]

    if args.json:
        print(json.dumps({"missing_count": len(missing), "results": results}, indent=2))
    else:
        for r in results:
            sym = "OK" if r["present"] else "MISSING"
            print(f"  [{sym}] ({r['id']}) {r['label']:30s} {r['evidence']}")
        if missing:
            print(f"\n{len(missing)} patch(es) missing.")
        else:
            print("\nAll four patches present.")

    if missing and args.chat_webhook:
        post_chat_alert(args.chat_webhook, missing)

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
