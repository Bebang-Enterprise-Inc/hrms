"""Daily health probe — verify sign.bebang.ph cookies are NOT born already expired.

Detects regressions of the stale-closure Expires bug fixed on 2026-05-18.

WHAT IT CHECKS
--------------
POSTs to https://sign.bebang.ph/api/auth/oauth/authorize/google and validates
the Set-Cookie headers on the response:

  HEALTHY (any of these):
    - cookie has Max-Age=NNN and NO Expires= attribute (the patched state)
    - cookie has Max-Age=NNN and Expires=<future date>

  BROKEN (must alert):
    - cookie has Expires=<past date>      ← the stale-closure bug recurring
    - endpoint returns non-200             ← deeper service failure
    - response has no JSON redirectUrl     ← provider config drift
    - cookie is missing entirely           ← auth module unloaded

WHAT IT DOES ON BROKEN
----------------------
- exit code 1 (suitable for cron / monitoring)
- if --chat-webhook URL is given (or BEI_DOCUMENSO_PROBE_WEBHOOK env var),
  POSTs an alert payload to a Google Chat incoming webhook
- prints a one-line diagnosis to stdout

USAGE
-----
    # Manual run
    python scripts/documenso/probe_signin_cookies.py

    # With chat alert
    python scripts/documenso/probe_signin_cookies.py --chat-webhook 'https://chat.googleapis.com/...'

    # As cron on EC2 host (suggested):
    #   */60 * * * * /usr/bin/python3 /opt/bei/probe_signin_cookies.py --chat-webhook "$WEBHOOK" >> /var/log/documenso_signin_probe.log 2>&1

EXIT CODES
----------
    0  cookie state is healthy
    1  cookie state is broken — alert worth sending
    2  could not probe (network/dns/timeout) — does not mean broken, but worth knowing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://sign.bebang.ph/api/auth/oauth/authorize/google"
TIMEOUT_S = 15
EXPECTED_COOKIES = ("google_oauth_state", "google_code_verifier")


def probe() -> tuple[int, str, dict]:
    """Returns (exit_code, message, evidence)."""
    req = urllib.request.Request(
        ENDPOINT,
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "bei-signin-probe/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            headers = list(resp.getheaders())
            status = resp.status
    except urllib.error.HTTPError as e:
        return 2, f"HTTP {e.code} from authorize endpoint", {"http_code": e.code}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 2, f"could not reach authorize endpoint: {e}", {"error": str(e)}

    evidence: dict = {
        "http_code": status,
        "endpoint": ENDPOINT,
        "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        "set_cookie_headers": [v for k, v in headers if k.lower() == "set-cookie"],
        "body_snippet": body[:200],
    }

    if status != 200:
        return 1, f"endpoint returned HTTP {status} (expected 200)", evidence

    try:
        parsed = json.loads(body)
        redirect_url = parsed.get("redirectUrl", "")
    except ValueError:
        return 1, "response is not valid JSON", evidence
    if "accounts.google.com" not in redirect_url:
        return 1, "response JSON does not contain a Google redirect URL", evidence

    set_cookies = [v for k, v in headers if k.lower() == "set-cookie"]
    if not set_cookies:
        return 1, "no Set-Cookie headers in response — auth module not setting cookies", evidence

    findings = []
    cookies_seen: set[str] = set()
    for sc in set_cookies:
        name = sc.split("=", 1)[0].strip()
        cookies_seen.add(name)
        attrs = {}
        for part in sc.split(";")[1:]:
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                attrs[k.strip().lower()] = v.strip()
            else:
                attrs[part.lower()] = True
        has_max_age = "max-age" in attrs
        expires_value = attrs.get("expires")
        finding: dict = {"name": name, "has_max_age": has_max_age, "expires": expires_value}
        if expires_value:
            # Parse RFC 7231 IMF-fixdate, e.g. "Sun, 17 May 2026 01:55:00 GMT"
            try:
                exp_dt = datetime.strptime(expires_value, "%a, %d %b %Y %H:%M:%S GMT").replace(
                    tzinfo=timezone.utc
                )
                finding["expires_dt"] = exp_dt.isoformat()
                if exp_dt < datetime.now(timezone.utc):
                    finding["fault"] = "EXPIRES_IN_PAST"
            except ValueError:
                finding["fault"] = "EXPIRES_UNPARSEABLE"
        findings.append(finding)

    evidence["cookie_findings"] = findings

    missing = [c for c in EXPECTED_COOKIES if c not in cookies_seen]
    if missing:
        return 1, f"missing expected cookies: {missing}", evidence

    bad = [f for f in findings if f.get("fault")]
    if bad:
        names = ", ".join(f["name"] for f in bad)
        return 1, f"cookies with past/unparseable Expires: {names}", evidence

    healthy_state = (
        "patched (Max-Age only)"
        if not any(f.get("expires") for f in findings)
        else "unpatched-but-functional (Max-Age + future Expires)"
    )
    return 0, f"OK - {healthy_state}", evidence


def send_chat_alert(webhook: str, message: str, evidence: dict) -> None:
    """POST a Google Chat incoming-webhook message about a broken probe."""
    text = (
        "*sign.bebang.ph sign-in probe FAILED*\n"
        f"`{message}`\n"
        f"Probed at: {evidence.get('probed_at_utc')}\n"
        f"HTTP: {evidence.get('http_code')}\n"
        "Suggested first steps:\n"
        "1. `docker restart documenso` on EC2 i-026b7477d27bd46d6 (30-day temp fix)\n"
        "2. `python scripts/documenso/patch_session_cookie_stale_closure.py` (permanent fix)\n"
        "3. Check that the running image is `documenso/documenso:v2.8.1-bei-patched`"
    )
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        webhook,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f"alert delivery failed: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--chat-webhook",
        default=os.environ.get("BEI_DOCUMENSO_PROBE_WEBHOOK"),
        help="Google Chat incoming webhook URL. Defaults to $BEI_DOCUMENSO_PROBE_WEBHOOK env var.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full evidence dict as JSON to stdout (in addition to the one-liner).",
    )
    args = parser.parse_args()

    code, message, evidence = probe()
    print(f"[{('OK' if code == 0 else 'FAIL' if code == 1 else 'WARN')}] {message}")
    if args.json:
        print(json.dumps(evidence, indent=2, default=str))

    if code == 1 and args.chat_webhook:
        send_chat_alert(args.chat_webhook, message, evidence)

    return code


if __name__ == "__main__":
    sys.exit(main())
