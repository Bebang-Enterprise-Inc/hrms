"""S204 F3 runner: rename → playwright F3 → restore (ALWAYS).

F3 cannot safely run inline inside Playwright because rename + restore
must bracket the test execution and the restore MUST happen even if
Playwright crashes mid-run. This wrapper enforces that via try/finally.

Invocation:
    python scripts/s204_run_f3.py

Requirements:
  - bei-tasks checked out at F:/Dropbox/Projects/bei-tasks
  - Doppler + FRAPPE_API_KEY/SECRET available in env (same as other L3 runs)
  - S204 F3 test block present in
    bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts

Exit code: 0 if both rename AND test AND restore succeeded.
          1 otherwise. restore is attempted regardless.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BEI_TASKS = Path("F:/Dropbox/Projects/bei-tasks")
CREATION_FLAGS = 0x08000000 if sys.platform == "win32" else 0


def _resolve_npx() -> str | None:
    """Find npx executable. On Windows, shutil.which returns npx.cmd which
    subprocess.run can invoke directly; PATH lookup fails on raw 'npx'."""
    for candidate in ("npx", "npx.cmd", "npx.exe"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        creationflags=CREATION_FLAGS,
    )
    return proc.returncode


def main() -> int:
    rename_script = REPO_ROOT / "scripts" / "s204_f3_rename_customer.py"
    restore_script = REPO_ROOT / "scripts" / "s204_f3_restore_customer.py"

    if not rename_script.exists() or not restore_script.exists():
        print("ERROR: rename/restore scripts missing under scripts/")
        return 1

    # 1. Rename
    print("=== S204 F3: rename customer ===")
    rc_rename = _run([sys.executable, str(rename_script)], cwd=REPO_ROOT)
    if rc_rename != 0:
        print("RENAME FAILED — skipping playwright, not attempting restore (nothing to restore)")
        return 1

    # 2. Playwright (wrapped in try so restore always runs)
    rc_test = 1
    try:
        print("\n=== S204 F3: playwright test ===")
        env = os.environ.copy()
        env["S192_EVIDENCE_ROOT"] = str(REPO_ROOT / "output" / "l3" / "s204")
        # We deliberately DO NOT clear auth cache here — the caller decides.
        # We also DO NOT set FRAPPE_API_KEY/SECRET — they must be in env.
        if not env.get("FRAPPE_API_KEY") or not env.get("FRAPPE_API_SECRET"):
            print(
                "WARNING: FRAPPE_API_KEY/FRAPPE_API_SECRET not in env — queryDocs will fail. "
                "Source them from Doppler before invoking this script."
            )
        npx_path = _resolve_npx()
        if not npx_path:
            print("ERROR: npx not found on PATH (tried npx, npx.cmd, npx.exe)")
            rc_test = 127
        else:
            rc_test = _run(
                [
                    npx_path, "playwright", "test",
                    "tests/e2e/specs/s198-l3-retry.spec.ts",
                    "--grep", "S204 F3",
                    "--reporter=list",
                    "--timeout=1500000",
                ],
                cwd=BEI_TASKS,
                env=env,
            )
    finally:
        # 3. Restore — ALWAYS
        print("\n=== S204 F3: restore customer (always) ===")
        rc_restore = _run([sys.executable, str(restore_script)], cwd=REPO_ROOT)
        if rc_restore != 0:
            print(
                "CRITICAL: RESTORE FAILED. "
                "Run `python scripts/s204_f3_restore_customer.py` manually IMMEDIATELY — "
                "otherwise SM Tanza + Ayala Evo dispatches will billing-hold on every order."
            )
            return rc_restore

    return 0 if rc_test == 0 else rc_test


if __name__ == "__main__":
    sys.exit(main())
