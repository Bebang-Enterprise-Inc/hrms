"""Patch Documenso's session-cookies.js to fix a stale-closure cookie Expires bug.

PROBLEM
-------
In `packages/auth/server/lib/session/session-cookies.ts`, the module exports a
`sessionCookieOptions` object whose `expires` field is computed at module load:

    const sessionCookieOptions = {
      ...,
      expires: new Date(Date.now() + AUTH_SESSION_LIFETIME)
    };

Node imports the module ONCE when the container boots. The `expires` is frozen
to (boot_time + 30 days) and never recomputed. After 30 days of uptime, every
cookie issued has `Expires=<past>` in the response header.

Per RFC 6265, `Max-Age` should override `Expires` when both are present, but
in practice:
  - curl drops cookies with past Expires outright
  - Safari is strict and may drop them
  - Some corporate proxies strip them
  - Some Chromium edge cases reject them

The result: users complete the Google OAuth flow, return to /api/auth/callback/google,
but the server can't find the state/code_verifier cookies (browser dropped them)
→ 500 INVALID_REQUEST or OAuth2RequestError: invalid_grant.

INCIDENT
--------
Discovered 2026-05-18 when all users were unable to sign in via Google to
sign.bebang.ph. Container had been up since 2026-04-17 (30 days, 5 hours), so the
frozen Expires date was already in the past (2026-05-17 01:55 UTC).

FIX
---
Replace the static `expires` field with `maxAge`, which the browser computes on
receipt instead of trusting a server-baked timestamp.

    expires: new Date(Date.now() + AUTH_SESSION_LIFETIME)   # WRONG
    maxAge: Math.floor(AUTH_SESSION_LIFETIME / 1000)         # RIGHT

Hono cookie helper accepts `maxAge` in seconds. AUTH_SESSION_LIFETIME is in ms.

USAGE
-----
    python scripts/documenso/patch_session_cookie_stale_closure.py
    python scripts/documenso/patch_session_cookie_stale_closure.py --verify-only
    python scripts/documenso/patch_session_cookie_stale_closure.py --no-restart
    python scripts/documenso/patch_session_cookie_stale_closure.py --no-commit

After a successful patch, restarts the container so Node re-imports the module,
then commits the patched container to documenso/documenso:v2.8.1-bei-patched
(deleting the old tag first per the documenso-fields-size skill hygiene rule).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
CONTAINER = "documenso"
PATCH_TARGET = (
    "/app/apps/remix/build/server/hono/packages/auth/server/lib/session/session-cookies.js"
)
OLD_LINE = "expires: new Date(Date.now() + AUTH_SESSION_LIFETIME)"
NEW_LINE = "maxAge: Math.floor(AUTH_SESSION_LIFETIME / 1000)"
PATCHED_IMAGE = "documenso/documenso:v2.8.1-bei-patched"
COMMIT_MSG = (
    "BEI: fix stale-closure expires bug in session-cookies.js + prior CC/Resend/field-size patches"
)


def ssm_run(commands: list[str], timeout: int = 240) -> dict[str, Any]:
    """Execute a list of shell commands on the EC2 host via SSM."""
    params = json.dumps({"commands": commands, "executionTimeout": [str(timeout)]})
    send = subprocess.run(
        [
            "aws", "ssm", "send-command",
            "--instance-ids", INSTANCE_ID,
            "--document-name", "AWS-RunShellScript",
            "--parameters", params,
            "--region", AWS_REGION,
            "--output", "json",
        ],
        capture_output=True, text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    if send.returncode != 0:
        raise RuntimeError(f"ssm send-command failed: {send.stderr}")
    cid = json.loads(send.stdout)["Command"]["CommandId"]
    deadline = time.time() + timeout + 60
    while time.time() < deadline:
        time.sleep(4)
        inv = subprocess.run(
            [
                "aws", "ssm", "get-command-invocation",
                "--command-id", cid,
                "--instance-id", INSTANCE_ID,
                "--region", AWS_REGION,
                "--output", "json",
            ],
            capture_output=True, text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if inv.returncode != 0:
            continue
        data = json.loads(inv.stdout)
        if data["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            return {
                "status": data["Status"],
                "stdout": data.get("StandardOutputContent", ""),
                "stderr": data.get("StandardErrorContent", ""),
                "command_id": cid,
            }
    raise TimeoutError(f"SSM command {cid} did not finish within {timeout + 60}s")


def check_patch_state() -> str:
    """Return 'patched', 'unpatched', or 'unknown'."""
    cmds = [
        f"docker exec {CONTAINER} grep -F '{NEW_LINE}' {PATCH_TARGET} >/dev/null 2>&1 "
        f"&& echo STATE=patched "
        f"|| (docker exec {CONTAINER} grep -F '{OLD_LINE}' {PATCH_TARGET} >/dev/null 2>&1 "
        f"&& echo STATE=unpatched || echo STATE=unknown)"
    ]
    r = ssm_run(cmds, timeout=60)
    for line in r["stdout"].splitlines():
        if line.startswith("STATE="):
            return line.split("=", 1)[1].strip()
    return "unknown"


def apply_patch() -> dict[str, Any]:
    """Apply the sed patch to the running container."""
    cmds = [
        f"docker exec {CONTAINER} cp {PATCH_TARGET} {PATCH_TARGET}.bak",
        # `|` delimiter since OLD/NEW contain `/`
        f"docker exec {CONTAINER} sed -i 's|{OLD_LINE}|{NEW_LINE}|' {PATCH_TARGET}",
        # Verify
        f"docker exec {CONTAINER} grep -F '{NEW_LINE}' {PATCH_TARGET} "
        f"&& echo PATCH_VERIFIED || echo PATCH_VERIFICATION_FAILED",
    ]
    return ssm_run(cmds, timeout=60)


def restart_container() -> dict[str, Any]:
    """Restart documenso container and wait for /signin to return 200."""
    cmds = [
        f"docker restart {CONTAINER}",
        "for i in $(seq 1 30); do",
        "  code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' https://sign.bebang.ph/signin 2>/dev/null)",
        "  if [ \"$code\" = \"200\" ]; then echo HEALTHY_AFTER_${i}_ATTEMPTS; break; fi",
        "  sleep 3",
        "done",
    ]
    return ssm_run(cmds, timeout=180)


def verify_cookies_have_no_expires() -> dict[str, Any]:
    """Confirm the response no longer carries an `Expires=` cookie attribute."""
    cmds = [
        "curl -sS -m 10 -X POST -i https://sign.bebang.ph/api/auth/oauth/authorize/google "
        "2>&1 | grep -i 'set-cookie:' | head -5",
    ]
    return ssm_run(cmds, timeout=30)


def commit_patched_image() -> dict[str, Any]:
    """Delete old patched tag, commit the running container as the new patched image."""
    cmds = [
        f"docker rmi {PATCHED_IMAGE} 2>&1 || echo 'rmi failed (container may still hold ref - usually ok)'",
        f"docker commit -m '{COMMIT_MSG}' {CONTAINER} {PATCHED_IMAGE}",
        f"docker images {PATCHED_IMAGE} --format 'id={{{{.ID}}}} created={{{{.CreatedAt}}}}'",
    ]
    return ssm_run(cmds, timeout=180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only report the current patch state; do not modify anything.",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Apply the patch but do not restart the container (no runtime effect until restart).",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Apply + restart but do not commit a new Docker image. Patch will be lost if the container is ever recreated.",
    )
    args = parser.parse_args()

    print(f"[1/5] Checking patch state on {CONTAINER}@{INSTANCE_ID}...")
    state = check_patch_state()
    print(f"      state = {state}")

    if args.verify_only:
        return 0 if state == "patched" else 1

    if state == "patched":
        print("Patch already applied. Nothing to do.")
        print("If you want to force re-commit anyway, run with --no-restart removed.")
        return 0
    if state == "unknown":
        print("ERROR: Could not detect patch state. Source file may have changed shape upstream.")
        print(f"Inspect manually: docker exec {CONTAINER} cat {PATCH_TARGET}")
        return 2

    print("[2/5] Applying patch...")
    r = apply_patch()
    if "PATCH_VERIFIED" not in r["stdout"]:
        print("ERROR: patch verification failed")
        print(r["stdout"])
        print(r["stderr"])
        return 3
    print("      OK: patch applied + verified in /app/...")

    if args.no_restart:
        print("--no-restart given. Patch is on disk but not in memory until container restart.")
        return 0

    print("[3/5] Restarting container so Node re-imports the patched module...")
    r = restart_container()
    if "HEALTHY_AFTER_" not in r["stdout"]:
        print("ERROR: container did not become healthy after restart")
        print(r["stdout"])
        return 4
    print(f"      {next(l for l in r['stdout'].splitlines() if 'HEALTHY_AFTER_' in l)}")

    print("[4/5] Smoke-testing cookies on /api/auth/oauth/authorize/google...")
    r = verify_cookies_have_no_expires()
    if "Expires=" in r["stdout"]:
        print("ERROR: response still carries Expires= attribute on cookies. Patch may not have taken effect.")
        print(r["stdout"])
        return 5
    if "Max-Age=" not in r["stdout"]:
        print("ERROR: response does not carry Max-Age= attribute. Endpoint may be returning unexpected shape.")
        print(r["stdout"])
        return 6
    print("      OK: cookies have Max-Age= and NO Expires= attribute.")

    if args.no_commit:
        print("--no-commit given. Patch is live in the running container but NOT in the image.")
        print("If the container is recreated, the patch will be lost.")
        return 0

    print(f"[5/5] Committing patched container to {PATCHED_IMAGE}...")
    r = commit_patched_image()
    print(r["stdout"])
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
