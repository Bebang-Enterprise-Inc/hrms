#!/usr/bin/env python3
"""S165 follow-up: prevent regression of hardcoded Google Chat space literals.

Per Sam directive 2026-04-07: NO Blip notifications anywhere except
"! Blip Notifications" (spaces/AAQABiNmpBg).

This guard fails if any standalone script or workflow file contains a
hardcoded `spaces/<id>` literal that:
  1. is NOT spaces/AAQABiNmpBg (the Blip Notifications space), AND
  2. lives outside the allowlisted files (Frappe-side bei_config.py + tests)

Usage:
    python scripts/guards/check_chat_space_literals.py [paths...]
    python scripts/guards/check_chat_space_literals.py --all   # scan everything

Exit codes:
    0  no violations
    1  one or more violations found
    2  argument error

Wire it up as a pre-commit hook in .git/hooks/pre-commit:
    python scripts/guards/check_chat_space_literals.py $(git diff --cached --name-only --diff-filter=ACM)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The ONLY space ID allowed to appear as a hardcoded literal in production code
# (outside the allowlisted files). All other spaces must be expressed via the
# Frappe `bei_config.SPACE_*` constants and the chat_space_lockdown router.
ALLOWED_LITERAL = "spaces/AAQABiNmpBg"

# Files allowed to contain other space literals (sources of truth, tests, fixtures)
ALLOWLIST_PATTERNS = [
    "hrms/utils/bei_config.py",          # canonical SPACE_* constants
    "hrms/utils/notification_intelligence.py",  # references the constants
    "hrms/utils/chat_space_lockdown.py", # the lockdown itself
    "hrms/tests/",                       # test fixtures may pin old IDs
    "hrms/test_utils/",
    ".claude/skills/",                   # skill docs / references
    ".agent/skills/",
    ".agents/skills/",
    "archive/",                          # historical scratchpads
    "docs/",                             # historical docs
    ".planning/",                        # historical planning
    ".builder-worktree-",                # historical worktree snapshots
    "scripts/guards/check_chat_space_literals.py",  # this file
    "node_modules/",
    ".git/",
    "recruitment/",                      # one-off data files
]

# Files that MUST be scanned even if they're under an allowlisted prefix
SCAN_FILES_EXTENSIONS = {".py", ".yml", ".yaml", ".ts", ".tsx", ".js", ".mjs", ".sh"}

LITERAL_RE = re.compile(r"spaces/[A-Z][A-Za-z0-9_-]{6,}")


def is_allowlisted(rel_path: str) -> bool:
    rel_path_norm = rel_path.replace("\\", "/")
    return any(rel_path_norm.startswith(p) or p in rel_path_norm for p in ALLOWLIST_PATTERNS)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, line, literal) violations in *path*."""
    violations: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError):
        return violations
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in LITERAL_RE.findall(line):
            if match != ALLOWED_LITERAL:
                violations.append((lineno, line.strip()[:160], match))
    return violations


def collect_files(args: list[str]) -> list[Path]:
    if not args:
        return []
    if args == ["--all"]:
        out: list[Path] = []
        for ext in SCAN_FILES_EXTENSIONS:
            out.extend(REPO.rglob(f"*{ext}"))
        return out
    out = []
    for a in args:
        p = Path(a)
        if not p.is_absolute():
            p = REPO / p
        if p.is_file():
            out.append(p)
    return out


def main(argv: list[str]) -> int:
    files = collect_files(argv)
    if not files:
        # No files to check (e.g. pre-commit ran with no staged files)
        return 0

    total_violations = 0
    for f in files:
        rel = f.relative_to(REPO).as_posix() if f.is_absolute() and REPO in f.parents else str(f)
        if is_allowlisted(rel):
            continue
        if f.suffix not in SCAN_FILES_EXTENSIONS:
            continue
        for lineno, snippet, literal in scan_file(f):
            print(f"{rel}:{lineno}: hardcoded {literal} (only {ALLOWED_LITERAL} allowed)")
            print(f"    {snippet}")
            total_violations += 1

    if total_violations:
        print()
        print(f"FAIL: {total_violations} forbidden space literal(s) found.")
        print(f"Per Sam directive 2026-04-07: only {ALLOWED_LITERAL} may be hardcoded.")
        print("All other Chat sends must route through hrms.utils.chat_space_lockdown.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
