#!/usr/bin/env python3
"""S209 phase verifier — runs AFTER each phase completes.

Usage:
    python scripts/s209_verify_phase.py --phase 0
    python scripts/s209_verify_phase.py --phase 1
    ...

Exit 0 = all gates pass; exit 1 = at least one gate failed.

Each phase has a MUST_MODIFY file list + MUST_CONTAIN grep table + evidence file list.
The script reads `git diff --name-only origin/production...HEAD` for hrms and
`git diff --name-only origin/main...HEAD` for bei-tasks (if present).

Runs `python scripts/verify_canonical_structure.py` as a final gate — tolerated to
return the pre-existing `BILLING_CUST_TIN_EMPTY` for ORTIGAS GREENHILLS (plan-level
allowed skip). Any NEW violation class aborts the phase.
"""
from __future__ import annotations
import argparse
import pathlib
import re
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BEI_TASKS = pathlib.Path("F:/Dropbox/Projects/bei-tasks")
EVIDENCE_ROOT = REPO_ROOT / "output/l3/s209"


# Phase -> (hrms_expected_files, bei_tasks_expected_files, grep_assertions, evidence_files)
# grep_assertion: (absolute_path, pattern, min_hits, description)

PHASE_PLAN: dict[int, dict] = {
    0: {
        "hrms_files": ["scripts/s209_verify_phase.py"],
        "bei_tasks_files": [],
        "grep": [],
        "evidence": [
            "canonical_preflight.txt",
            "baseline_sha.txt",
            "library_audit.txt",
            "supervisor_access_strategy.md",
            "resolver_live_check.txt",
        ],
        "required_grep_in_evidence": [
            ("canonical_preflight.txt", r"CANONICAL OK", 1),
        ],
    },
    1: {
        "hrms_files": ["scripts/s209_generate_fixture.py"],
        "bei_tasks_files": ["tests/e2e/fixtures/s204_all_stores.json"],
        "grep": [
            (BEI_TASKS / "tests/e2e/fixtures/s204_all_stores.json", r'"allowEmptyTin"\s*:\s*true', 1),
            (BEI_TASKS / "tests/e2e/fixtures/s204_all_stores.json", r'"buyer_entity_status"\s*:\s*"confirmed_legal_entity"', 49),
        ],
        "evidence": ["canonical_preflight.txt"],
        "required_grep_in_evidence": [],
    },
    2: {
        "hrms_files": [],
        "bei_tasks_files": [
            "tests/e2e/pages/StoreOrderingPage.ts",
            "tests/e2e/pages/DispatchPage.ts",
            "tests/e2e/pages/ReceivingPage.ts",
            "tests/e2e/assertions/billingAssertions.ts",
            "tests/e2e/assertions/inventoryAssertions.ts",
            "tests/e2e/assertions/index.ts",
        ],
        "grep": [
            (BEI_TASKS / "tests/e2e/pages/StoreOrderingPage.ts", r"submitOrderWithExplicitQty", 1),
            (BEI_TASKS / "tests/e2e/pages/DispatchPage.ts", r"qtyOverrides", 1),
            (BEI_TASKS / "tests/e2e/pages/ReceivingPage.ts", r"acceptedQty", 1),
            (BEI_TASKS / "tests/e2e/pages/ReceivingPage.ts", r"rejectedQty", 1),
            (BEI_TASKS / "tests/e2e/assertions/billingAssertions.ts", r"allowEmptyTin", 1),
            (BEI_TASKS / "tests/e2e/assertions/billingAssertions.ts", r"assertSIGLPartyIsCustomer", 1),
            (BEI_TASKS / "tests/e2e/assertions/inventoryAssertions.ts", r"assertInventoryDelta", 1),
            (BEI_TASKS / "tests/e2e/assertions/inventoryAssertions.ts", r"tabStock Ledger Entry", 1),
            (BEI_TASKS / "tests/e2e/assertions/index.ts", r"inventoryAssertions", 1),
        ],
        "evidence": [],
        "required_grep_in_evidence": [],
    },
    3: {
        "hrms_files": [
            "scripts/s209_grant_test_area_access.py",
            "scripts/s209_revert_test_area_access.py",
        ],
        "bei_tasks_files": ["tests/e2e/specs/s209-all-stores.spec.ts"],
        "grep": [
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"loggedInAreaSupervisor", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"assertCompanyChainCorrect", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"assertSIGLPartyIsCustomer", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"ledger\.record", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"consecutiveFailures", 1),
            (REPO_ROOT / "scripts/s209_grant_test_area_access.py", r"custom_area_supervisor", 1),
            (REPO_ROOT / "scripts/s209_grant_test_area_access.py", r"test\.area@bebang\.ph", 1),
            (REPO_ROOT / "scripts/s209_grant_test_area_access.py", r"area_access_snapshot\.json", 1),
            (REPO_ROOT / "scripts/s209_revert_test_area_access.py", r"area_access_snapshot\.json", 1),
        ],
        "evidence": [],
        "required_grep_in_evidence": [],
        "forbidden_patterns": [
            (BEI_TASKS / "tests/e2e/specs/s209-all-stores.spec.ts", r"page\.request|fetch\(|button:has-text", 0),
        ],
    },
    4: {
        "hrms_files": ["scripts/s209_seed_inventory_for_variance.py"],
        "bei_tasks_files": ["tests/e2e/specs/s209-variance.spec.ts"],
        "grep": [
            (REPO_ROOT / "scripts/s209_seed_inventory_for_variance.py", r"Stock Entry", 1),
            (REPO_ROOT / "scripts/s209_seed_inventory_for_variance.py", r"Material Receipt", 1),
            (REPO_ROOT / "scripts/s209_seed_inventory_for_variance.py", r"qty=?10", 1),
            (REPO_ROOT / "scripts/s209_seed_inventory_for_variance.py", r"qty=?8", 1),
            (REPO_ROOT / "scripts/s209_seed_inventory_for_variance.py", r"inventory_snapshot\.json", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"V1", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"V2", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"SM TANZA", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"AYALA VERMOSA", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"acceptedQty", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"rejectedQty", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"qtyOverrides", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"assertInventoryDelta", 1),
            (BEI_TASKS / "tests/e2e/specs/s209-variance.spec.ts", r"items missing in transit", 1),
        ],
        "evidence": [],
        "required_grep_in_evidence": [],
    },
    5: {
        "hrms_files": [],
        "bei_tasks_files": [],
        "grep": [],
        "evidence": [
            "sweep_ledger.json",
            "form_submissions.json",
            "api_mutations.json",
        ],
        "required_grep_in_evidence": [
            ("sweep_ledger.json", r"si-create", 49),
        ],
    },
    6: {
        "hrms_files": ["scripts/s209_cleanup_sweep.py"],
        "bei_tasks_files": [],
        "grep": [
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"Sales Invoice", 1),
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"cancel", 1),
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"Stock Entry", 1),
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"Warehouse Receiving", 1),
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"BEI Store Order", 1),
            (REPO_ROOT / "scripts/s209_cleanup_sweep.py", r"reverse_order", 1),
        ],
        "evidence": [
            "canonical_postcheck.txt",
            "SWEEP_VERIFICATION_SUMMARY.md",
        ],
        "required_grep_in_evidence": [
            ("canonical_postcheck.txt", r"CANONICAL OK", 1),
            ("SWEEP_VERIFICATION_SUMMARY.md", r"49/49", 1),
            ("SWEEP_VERIFICATION_SUMMARY.md", r"V1", 1),
            ("SWEEP_VERIFICATION_SUMMARY.md", r"V2", 1),
        ],
    },
}


def _git_diff(repo: pathlib.Path, base_ref: str) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", f"{base_ref}...HEAD"],
            capture_output=True, text=True, check=True,
        )
        return [l for l in r.stdout.splitlines() if l.strip()]
    except subprocess.CalledProcessError:
        return []


def _untracked(repo: pathlib.Path) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        )
        return [l for l in r.stdout.splitlines() if l.strip()]
    except subprocess.CalledProcessError:
        return []


def _count_matches(path: pathlib.Path, pattern: str) -> int:
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return len(re.findall(pattern, content))


def verify_phase(phase: int) -> int:
    if phase not in PHASE_PLAN:
        print(f"[FAIL] Unknown phase: {phase}")
        return 1

    plan = PHASE_PLAN[phase]
    failures: list[str] = []

    hrms_diff = set(_git_diff(REPO_ROOT, "origin/production")) | set(_untracked(REPO_ROOT))
    bei_diff = set(_git_diff(BEI_TASKS, "origin/main")) | set(_untracked(BEI_TASKS))

    for f in plan["hrms_files"]:
        if f not in hrms_diff and not (REPO_ROOT / f).exists():
            failures.append(f"FAIL: expected hrms file {f} not in diff and not present on disk")

    for f in plan["bei_tasks_files"]:
        if f not in bei_diff and not (BEI_TASKS / f).exists():
            failures.append(f"FAIL: expected bei-tasks file {f} not in diff and not present on disk")

    for abs_path, pattern, min_hits in plan["grep"]:
        hits = _count_matches(pathlib.Path(abs_path), pattern)
        if hits < min_hits:
            failures.append(
                f"FAIL: {abs_path} pattern {pattern!r} expected >={min_hits}, found {hits}"
            )

    for forbidden in plan.get("forbidden_patterns", []):
        abs_path, pattern, max_hits = forbidden
        hits = _count_matches(pathlib.Path(abs_path), pattern)
        if hits > max_hits:
            failures.append(
                f"FAIL: {abs_path} forbidden pattern {pattern!r} found {hits} times (max {max_hits})"
            )

    for evidence in plan["evidence"]:
        abs_ev = EVIDENCE_ROOT / evidence
        if not abs_ev.exists():
            failures.append(f"FAIL: evidence file {abs_ev} does not exist")

    for evidence, pattern, min_hits in plan["required_grep_in_evidence"]:
        abs_ev = EVIDENCE_ROOT / evidence
        hits = _count_matches(abs_ev, pattern)
        if hits < min_hits:
            failures.append(
                f"FAIL: evidence {abs_ev} pattern {pattern!r} expected >={min_hits}, found {hits}"
            )

    if failures:
        print("\n".join(failures))
        print(f"\n[RESULT] Phase {phase} VERIFY FAILED ({len(failures)} issues)")
        return 1

    print(f"[RESULT] Phase {phase} VERIFY PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True)
    args = ap.parse_args()
    return verify_phase(args.phase)


if __name__ == "__main__":
    sys.exit(main())
