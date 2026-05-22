"""Patch (c) — capture Resend message id into the DocumentAuditLog.

PROBLEM
-------
Documenso writes one `EMAIL_SENT` audit-log row per outgoing email but does NOT
store the provider message id. When a "CC didn't get the email" claim comes in,
the only way to confirm delivery is to hand-search Resend's dashboard. Slow
and brittle.

FIX
---
Capture the object returned by `mailer.sendMail(...)` and write its id field
into the audit-log `data.resendMessageId`. Two transformations are required at
every send site:

  (1) Wrap the await call:
      await mailer.sendMail({...})
        ->
      const __resendResult = await mailer.sendMail({...})

  (2) Append the captured id to the audit-log payload:
      isResending: false
        ->
      isResending: false,
        resendMessageId: __resendResult?.id ?? __resendResult?.messageId ?? null

This applies to both `send-completed-email*.js` (the completion notification
sent to all signers) and `send-signing-email.handler-*.js` (the initial signing
request sent to each signer). Each file has its own send sites; we patch all
sites in the chosen file.

After patching, every EMAIL_SENT row has a `resendMessageId` field that can be
GET'd against `https://api.resend.com/emails/<id>` to confirm delivery status.

USAGE
-----
    python patch_resend_id_logging.py --target /path/to/send-completed-email.js
    python patch_resend_id_logging.py --target /path/to/file --verify-only
    python patch_resend_id_logging.py --search-root /app/apps/remix/build/server --kind completed
    python patch_resend_id_logging.py --search-root /app/apps/remix/build/server --kind signing

The `--kind` flag selects which file pattern to discover (`completed` or `signing`).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

KIND_GLOBS: dict[str, str] = {
    "completed": "send-completed-email*.js",
    "signing": "send-signing-email.handler-*.js",
}

# (1) Wrap the mailer call.
SEND_OLD = "await mailer.sendMail({"
SEND_NEW = "const __resendResult = await mailer.sendMail({"

# (2) Append the captured id to the audit-log payload.
# In both files the `isResending: false` line is the last entry of the data block,
# so appending a comma + new field is safe.
LOG_OLD = "isResending: false"
LOG_NEW = (
    "isResending: false,\n"
    "          resendMessageId: __resendResult?.id ?? __resendResult?.messageId ?? null"
)

# Marker that the patch is already applied
PATCH_MARKER = "__resendResult"


def detect_state(content: str) -> str:
    if PATCH_MARKER in content and "resendMessageId" in content:
        return "patched"
    if SEND_OLD in content and LOG_OLD in content:
        return "unpatched"
    if SEND_OLD in content or LOG_OLD in content:
        return "partial"  # one of the two markers — manual investigation needed
    return "unknown"


def apply_patch(content: str) -> tuple[str, int]:
    """Apply both replacements. Returns (new_content, total_replacements_made)."""
    # Count how many sites we have BEFORE replacement so we can verify after.
    n_send_old = content.count(SEND_OLD)
    n_log_old = content.count(LOG_OLD)

    new_content = content.replace(SEND_OLD, SEND_NEW)
    new_content = new_content.replace(LOG_OLD, LOG_NEW)

    n_send_new = new_content.count(SEND_NEW)
    n_log_new = new_content.count("resendMessageId: __resendResult")

    if n_send_new != n_send_old:
        raise ValueError(
            f"sendMail wrap mismatch: expected {n_send_old} replacements, got {n_send_new}"
        )
    if n_log_new != n_log_old:
        raise ValueError(
            f"audit-log append mismatch: expected {n_log_old} replacements, got {n_log_new}"
        )

    return new_content, n_send_old + n_log_old


def resolve_target(target: str | None, search_root: str | None, kind: str | None) -> pathlib.Path:
    if target:
        p = pathlib.Path(target)
        if not p.is_file():
            raise FileNotFoundError(f"--target file not found: {target}")
        return p
    if not search_root or not kind:
        raise ValueError("Must give either --target FILE or both --search-root DIR and --kind {completed,signing}.")
    glob_pattern = KIND_GLOBS[kind]
    root = pathlib.Path(search_root)
    if not root.is_dir():
        raise FileNotFoundError(f"--search-root not a directory: {search_root}")
    matches = sorted(p for p in root.rglob(glob_pattern) if not p.name.endswith(".map"))
    if not matches:
        raise FileNotFoundError(f"No {glob_pattern} under {search_root}.")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple matches for {glob_pattern} under {search_root}: {[str(p) for p in matches]}. "
            "Pass --target explicitly."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", help="Path to the email-sending file to patch.")
    parser.add_argument(
        "--search-root",
        help="Directory to rglob inside (e.g. /app/apps/remix/build/server).",
    )
    parser.add_argument(
        "--kind",
        choices=sorted(KIND_GLOBS.keys()),
        help="Which file family to patch when using --search-root.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Report current state, exit 0 if patched / 1 otherwise. No modifications.",
    )
    args = parser.parse_args()

    try:
        target = resolve_target(args.target, args.search_root, args.kind)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    content = target.read_text(encoding="utf-8")
    state = detect_state(content)
    print(f"target: {target}")
    print(f"state:  {state}")

    if args.verify_only:
        return 0 if state == "patched" else 1

    if state == "patched":
        print("Already patched. No changes made.")
        return 0
    if state == "unknown":
        print(
            "ERROR: file does not contain expected mailer.sendMail / isResending markers. "
            "Documenso may have refactored the email-sending code upstream.",
            file=sys.stderr,
        )
        return 3
    if state == "partial":
        print(
            "ERROR: file has SOME but not ALL of the expected markers. "
            "Manual inspection required — won't patch automatically.",
            file=sys.stderr,
        )
        return 3

    try:
        new_content, n = apply_patch(content)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    target.write_text(new_content, encoding="utf-8")
    print(f"OK: applied {n} total replacements at {n // 2} send sites")
    print(f"wrote: {target} ({len(new_content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
