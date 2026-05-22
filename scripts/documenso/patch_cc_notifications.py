"""Patch (b) — let CC recipients receive the initial signing email.

PROBLEM
-------
In `apps/remix/build/server/assets/send-signing-email.handler-<hash>.js` the
initial-email handler has an early return for CC recipients:

    if (recipient.role === RecipientRole.CC) {
      return;
    }

That means CCs get the document completion email later but never see the
initial "you have been CC'd on document X" notification. BEI's HR + supplier
flows expect CCs to know about the document at the start, not just at the end.

FIX
---
Comment out the body of the if-branch so the function falls through and the
rest of the send routine runs for CC recipients too. The `if` condition is
left in place (commented) for human readability — anyone reading the patched
code sees both the original Documenso intent AND the BEI override.

USAGE
-----
    python patch_cc_notifications.py --target /path/to/send-signing-email.handler.js
    python patch_cc_notifications.py --target /path/to/file --verify-only
    python patch_cc_notifications.py --search-root /app/apps/remix/build/server

Designed to run inside the Documenso container during image build, or against
an extracted file on the developer host.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

BUNDLE_GLOB = "send-signing-email.handler-*.js"

# Original block — needs to match the exact bytes the bundler emits.
# Documenso v2.8.1 emits this single-line-friendly form (with 2-space indent + LF).
UNPATCHED_BLOCK = (
    "  if (recipient.role === RecipientRole.CC) {\n"
    "    return;\n"
    "  }\n"
)
PATCHED_BLOCK = (
    "  // BEI patch: CC recipients receive the initial signing email.\n"
    "  // Upstream skip kept commented for traceability.\n"
    "  // if (recipient.role === RecipientRole.CC) {\n"
    "  //   return;\n"
    "  // }\n"
)
PATCH_MARKER = "// BEI patch: CC recipients receive the initial signing email."


def detect_state(content: str) -> str:
    if PATCH_MARKER in content:
        return "patched"
    if UNPATCHED_BLOCK in content:
        return "unpatched"
    # Tolerate single-line emitted form (no newline before the brace):
    if re.search(r"if \(recipient\.role === RecipientRole\.CC\) \{\s*return;\s*\}", content):
        return "unpatched_alt"
    return "unknown"


def apply_patch(content: str) -> tuple[str, str]:
    state = detect_state(content)
    if state == "unpatched":
        return content.replace(UNPATCHED_BLOCK, PATCHED_BLOCK, 1), "OK: standard form replaced"
    if state == "unpatched_alt":
        # Single-line variant — replace the whole regex hit with the multi-line patched form.
        pattern = re.compile(
            r"if \(recipient\.role === RecipientRole\.CC\) \{\s*return;\s*\}"
        )
        return pattern.sub(PATCHED_BLOCK.rstrip("\n"), content, count=1), "OK: alt form replaced"
    raise ValueError(f"unexpected state for apply_patch: {state}")


def resolve_target(target: str | None, search_root: str | None) -> pathlib.Path:
    if target:
        p = pathlib.Path(target)
        if not p.is_file():
            raise FileNotFoundError(f"--target file not found: {target}")
        return p
    if not search_root:
        raise ValueError("Must give either --target FILE or --search-root DIR.")
    root = pathlib.Path(search_root)
    if not root.is_dir():
        raise FileNotFoundError(f"--search-root not a directory: {search_root}")
    matches = sorted(p for p in root.rglob(BUNDLE_GLOB) if not p.name.endswith(".map"))
    if not matches:
        raise FileNotFoundError(f"No {BUNDLE_GLOB} under {search_root}.")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple matches under {search_root}: {[str(p) for p in matches]}. "
            "Pass --target explicitly."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", help="Path to the send-signing-email.handler file.")
    parser.add_argument(
        "--search-root",
        help="Directory to rglob for the handler bundle (e.g. /app/apps/remix/build/server).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Report current state, exit 0 if patched / 1 otherwise. No modifications.",
    )
    args = parser.parse_args()

    try:
        target = resolve_target(args.target, args.search_root)
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
            "ERROR: handler does not match either expected unpatched form. "
            "Documenso may have changed the CC-skip code shape upstream.",
            file=sys.stderr,
        )
        return 3

    try:
        new_content, msg = apply_patch(content)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    target.write_text(new_content, encoding="utf-8")
    print(msg)
    print(f"wrote: {target} ({len(new_content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
