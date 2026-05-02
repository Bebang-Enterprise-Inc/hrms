"""S232 shared phase verifier framework (Phase 0.8 deliverable).

Resolves audit blocker C1: every phase's verifier uses this filesystem-based
template instead of prose self-assessment. Prose checklists have a 100% lie
rate under context pressure (S154 incident — 6/6 incomplete tasks marked DONE).

Usage from phase verifiers:
    from scripts.s232_verify_phase_template import verify_phase
    verify_phase(
        phase_num=1,
        required_files=[
            "scripts/sync_pos_to_supabase.py",
            "hrms/utils/pos_dedup.py",
            ...
        ],
        required_strings=[
            ("hrms/utils/pos_dedup.py", "def find_bill_number_twin"),
            ...
        ],
        extra_checks=[
            lambda: my_extra_check(),
        ],
    )

Each phase must call verify_phase() AFTER completing all tasks, and the script
exits non-zero on any failure. Do NOT proceed to Phase N+1 until verifier exits 0.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

# All paths are relative to repo root; cwd should be the worktree root.
REPO_ROOT = Path(__file__).resolve().parents[1]


def _git_diff_files(base: str = "origin/production") -> set[str]:
    """Return the set of files changed in the current branch vs base."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base],
        cwd=REPO_ROOT,
        text=True,
    )
    return set(line.strip() for line in out.splitlines() if line.strip())


def _git_status_files() -> set[str]:
    """Return the set of files in `git status` (untracked + modified)."""
    out = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        text=True,
    )
    files = set()
    for line in out.splitlines():
        if line:
            # Strip status code (first 3 chars) to get path
            files.add(line[3:].strip())
    return files


def verify_phase(
    phase_num: int,
    required_files: list[str],
    required_strings: list[tuple[str, str]],
    extra_checks: list[Callable[[], tuple[bool, str]]] | None = None,
    base: str = "origin/production",
) -> None:
    """Verify a phase completed by checking the filesystem, not prose.

    Args:
        phase_num: phase number for log messages
        required_files: list of file paths (relative to repo root) that must
            appear in `git diff --name-only` (i.e., were modified or created)
        required_strings: list of (file_path, substring) tuples — the substring
            must exist in the file's content
        extra_checks: list of zero-arg callables returning (success: bool, msg: str)
        base: git base reference (default origin/production)

    Exits non-zero on any failure.
    """
    print(f"\n{'='*70}")
    print(f"S232 PHASE {phase_num} VERIFIER")
    print(f"{'='*70}")

    failures: list[str] = []

    # Check 1: every required file is in git diff (or status, for new untracked)
    print(f"\n[Check 1] Required files in git diff vs {base}:")
    diff_files = _git_diff_files(base)
    status_files = _git_status_files()
    all_changed = diff_files | status_files
    for f in required_files:
        # Normalize path separators
        f_norm = f.replace("\\", "/")
        if any(f_norm in cf.replace("\\", "/") for cf in all_changed):
            print(f"  PASS  {f}")
        else:
            print(f"  FAIL  {f} not in diff/status")
            failures.append(f"required_file_missing: {f}")

    # Check 2: every required string is in its target file
    print(f"\n[Check 2] Required strings in target files:")
    for f, s in required_strings:
        path = REPO_ROOT / f
        if not path.exists():
            print(f"  FAIL  {f} does not exist")
            failures.append(f"target_file_missing: {f}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  FAIL  {f} unreadable: {e}")
            failures.append(f"target_file_unreadable: {f}")
            continue
        if s in content:
            print(f"  PASS  {f}: {s!r}")
        else:
            print(f"  FAIL  {f}: {s!r} not found")
            failures.append(f"required_string_missing: {f} -> {s!r}")

    # Check 3: extra checks
    if extra_checks:
        print(f"\n[Check 3] Extra checks:")
        for i, check in enumerate(extra_checks):
            try:
                ok, msg = check()
                marker = "PASS" if ok else "FAIL"
                print(f"  {marker}  extra[{i}]: {msg}")
                if not ok:
                    failures.append(f"extra_check_failed: {msg}")
            except Exception as e:
                print(f"  FAIL  extra[{i}] threw: {e}")
                failures.append(f"extra_check_threw: {e}")

    # Final
    print(f"\n{'='*70}")
    if failures:
        print(f"PHASE {phase_num} VERIFIER: FAIL ({len(failures)} failures)")
        for f in failures:
            print(f"  - {f}")
        print(f"\nDO NOT proceed to Phase {phase_num + 1}. Fix failures above and re-run.")
        sys.exit(1)
    else:
        print(f"PHASE {phase_num} VERIFIER: PASS")
        print(f"{'='*70}")
