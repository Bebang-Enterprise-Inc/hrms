#!/usr/bin/env python3
"""S227 phase completion verifier — filesystem-grounded.

Runs after each phase. Exits non-zero on any miss. Self-assessment is not
trustworthy (see S154 incident); evidence comes from git diff and grep.

Usage:
  python output/s227/verify_phase_completion.py            # run all phases
  python output/s227/verify_phase_completion.py P1 P2      # run specific phases
"""
import subprocess
import sys
from pathlib import Path

REPO_HRMS = Path("F:/Dropbox/Projects/BEI-ERP-s227-store-partner-analytics")
REPO_BT = Path("F:/Dropbox/Projects/bei-tasks-s227-store-partner-analytics")

failures: list[str] = []
passes: list[str] = []


def must_modify(repo: Path, files: list[str], phase: str, base: str = "origin/production"):
    if "bei-tasks" in str(repo):
        base = "origin/main"
    # Tracked + new files vs base. `git diff` doesn't show untracked files,
    # but it does show files staged or committed on the branch — which is what
    # we care about (the eventual PR diff). Combine with `ls-files --others`
    # to also catch unstaged-but-present new files in the worktree, so the
    # verifier passes between phase commits without forcing a stage step.
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", base],
        capture_output=True, text=True,
    ).stdout
    untracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True,
    ).stdout
    visible = diff + "\n" + untracked
    for f in files:
        if f in visible:
            passes.append(f"[{phase}] MUST_MODIFY ok: {f}")
        else:
            failures.append(f"[{phase}] MUST_MODIFY missed: {f}")


def must_contain(repo: Path, file: str, pattern: str, count: int, phase: str):
    p = repo / file
    if not p.exists():
        failures.append(f"[{phase}] MUST_CONTAIN file missing: {file}")
        return
    text = p.read_text(encoding="utf-8", errors="ignore")
    found = text.count(pattern)
    if found >= count:
        passes.append(f"[{phase}] MUST_CONTAIN ok: '{pattern}' in {file} ({found} >= {count})")
    else:
        failures.append(
            f"[{phase}] MUST_CONTAIN '{pattern}' in {file}: expected >= {count}, found {found}"
        )


def must_not_contain(repo: Path, file: str, pattern: str, phase: str):
    p = repo / file
    if not p.exists():
        # absence-of-file is fine for must_not_contain
        return
    text = p.read_text(encoding="utf-8", errors="ignore")
    if pattern in text:
        failures.append(f"[{phase}] MUST_NOT_CONTAIN '{pattern}' in {file}: found")
    else:
        passes.append(f"[{phase}] MUST_NOT_CONTAIN ok: '{pattern}' absent from {file}")


def must_exist(path: Path, phase: str, min_bytes: int = 0):
    if not path.exists():
        failures.append(f"[{phase}] MUST_EXIST: {path}")
        return
    if path.is_file() and path.stat().st_size < min_bytes:
        failures.append(f"[{phase}] file too small: {path} ({path.stat().st_size} < {min_bytes} bytes)")
    else:
        passes.append(f"[{phase}] MUST_EXIST ok: {path}")


def must_not_exist(path: Path, phase: str):
    if path.exists():
        failures.append(f"[{phase}] MUST_NOT_EXIST: {path} (forbidden Frappe convention)")
    else:
        passes.append(f"[{phase}] MUST_NOT_EXIST ok: {path}")


# ---------- Phase 0 ----------
def verify_p0():
    base = REPO_HRMS / "output" / "s227" / "library"
    must_exist(base / "AUDIT.md", "P0", min_bytes=100)
    must_exist(base / "CONTRIBUTIONS.md", "P0", min_bytes=100)
    must_exist(base / "FAILURE_RESPONSE.md", "P0", min_bytes=100)
    must_exist(REPO_HRMS / "output" / "s227" / "verify_phase_completion.py", "P0", min_bytes=100)


# ---------- Phase 1 ----------
def verify_p1():
    must_modify(
        REPO_HRMS,
        [
            "hrms/api/sales_dashboard.py",
            "hrms/api/test_sales_dashboard_partner.py",
            "hrms/on_demand/seed_store_partner_role.py",
        ],
        "P1",
    )
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "ROLE_STORE_PARTNER", 4, "P1")
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "_should_strip_fleet_context", 1, "P1")
    must_not_exist(REPO_HRMS / "hrms" / "hr" / "role" / "store_partner" / "store_partner.json", "P1")
    # The plan's literal example uses the string form; the implementation may
    # alias "Store Partner" to a ROLE_NAME constant. Either is acceptable so
    # long as the existence check is present and the role string is present.
    must_contain(REPO_HRMS, "hrms/on_demand/seed_store_partner_role.py", 'frappe.db.exists("Role"', 1, "P1")
    must_contain(REPO_HRMS, "hrms/on_demand/seed_store_partner_role.py", "Store Partner", 1, "P1")


# ---------- Phase 2 ----------
def verify_p2():
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "_should_strip_fleet_context", 5, "P2")
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "_strip_fleet_context_from_", 2, "P2")
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "copy.deepcopy", 4, "P2")
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "is_partner_view", 9, "P2")
    must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "fleet-safe by schema", 1, "P2")


# ---------- Phase 3 ----------
def verify_p3():
    must_modify(REPO_BT, ["lib/roles.ts", "lib/navigation-personas.ts"], "P3")
    must_contain(REPO_BT, "lib/roles.ts", "STORE_PARTNER", 5, "P3")
    must_contain(REPO_BT, "lib/navigation-personas.ts", "STORE_PARTNER", 2, "P3")
    # Negative: there must be NO new ROLE_PERSONA_MAP export
    must_not_contain(REPO_BT, "lib/navigation-personas.ts", "export const ROLE_PERSONA_MAP", "P3")
    must_not_contain(REPO_BT, "lib/navigation-personas.ts", "export {  ROLE_PERSONA_MAP", "P3")


# ---------- Phase 4 ----------
def verify_p4():
    must_contain(
        REPO_BT,
        "app/dashboard/analytics/product/page.tsx",
        "fleet_rank != null",
        1,
        "P4",
    )
    must_contain(
        REPO_BT,
        "app/dashboard/analytics/product/page.tsx",
        "assortment_gap_count != null",
        1,
        "P4",
    )
    must_not_contain(
        REPO_BT,
        "app/dashboard/analytics/product/page.tsx",
        "assortment_gap_count ?? 0",
        "P4",
    )
    must_contain(REPO_BT, "app/dashboard/analytics/sales/page.tsx", "S227", 1, "P4")


# ---------- Phase 5 ----------
def verify_p5():
    base = Path("output/s227/L3")
    for f in [
        "form_submissions.json",
        "api_mutations.json",
        "state_verification.json",
        "api_response_shape_partner.json",
        "api_response_shape_admin.json",
    ]:
        must_exist(REPO_HRMS / base / f, "P5")


# ---------- Phase 6 ----------
def verify_p6():
    base = REPO_HRMS / "output" / "s227"
    must_exist(base / "SUMMARY.md", "P6", min_bytes=100)
    must_exist(base / "DEFECTS.md", "P6", min_bytes=20)
    must_exist(base / "PHASE_COMPLETION_LEDGER.md", "P6", min_bytes=100)
    must_exist(base / "verification" / "state_after.json", "P6")


PHASES = {
    "P0": verify_p0,
    "P1": verify_p1,
    "P2": verify_p2,
    "P3": verify_p3,
    "P4": verify_p4,
    "P5": verify_p5,
    "P6": verify_p6,
}


def main():
    args = sys.argv[1:]
    phases = args if args else list(PHASES.keys())
    for phase in phases:
        if phase not in PHASES:
            print(f"Unknown phase: {phase}. Valid: {list(PHASES.keys())}")
            sys.exit(2)
        PHASES[phase]()

    if passes:
        print("\n".join(passes))
    if failures:
        print("\nVERIFICATION FAILED:\n" + "\n".join(failures))
        sys.exit(1)
    print(f"\nAll {len(passes)} assertions passed for phases: {phases}")


if __name__ == "__main__":
    main()
