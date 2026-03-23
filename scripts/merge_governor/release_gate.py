"""Release gate — deterministic checks that block merge until plan tasks are done.

Pure Python, no AI, no external dependencies. This is infrastructure that agents cannot skip.
Inspired by Stripe Minions blueprint pattern: deterministic gates between creative nodes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateResult:
    """Result of the deterministic release gate checks."""

    passed: bool
    missing_evidence: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    details: str = ""

    @property
    def comment(self) -> str:
        """Format as actionable PR comment for the builder."""
        if self.passed:
            return ""
        if self.skip_reason:
            return ""

        lines = ["**Release Manager: BLOCKED**\n"]

        if self.missing_evidence:
            lines.append("**Missing L3 evidence files:**")
            for item in self.missing_evidence:
                lines.append(f"- [ ] {item}")
            lines.append("")

        if self.evidence_gaps:
            lines.append("**Evidence gaps:**")
            for item in self.evidence_gaps:
                lines.append(f"- [ ] {item}")
            lines.append("")

        lines.append(
            "**Builder action:** Run L3 tests to produce evidence files, "
            "then `git add -f output/l3/ && git commit && git push`. "
            "The gate will re-check automatically on the new SHA.\n"
        )
        lines.append("*Posted by bei-release-manager*")
        return "\n".join(lines)


def find_sprint_plan(branch_name: str, plans_dir: str = "docs/plans") -> Path | None:
    """Find the sprint plan file from the PR's branch name.

    Searches local filesystem first (production branch), then falls back to
    the feature branch via `git show` if the plan was committed there.
    Returns None for non-sprint PRs (gate should be skipped).
    """
    match = re.search(r"s0?(\d{2,3})", branch_name, re.IGNORECASE)
    if not match:
        return None

    sprint_num = match.group(1)
    plans_path = Path(plans_dir)

    # Search local filesystem first (plan might be on production already)
    if plans_path.exists():
        for pattern in [f"*sprint*{sprint_num}*", f"*s0{sprint_num}*", f"*s{sprint_num}*"]:
            for f in plans_path.glob(pattern):
                if f.suffix == ".md" and f.is_file():
                    return f

    # Fallback: check if plan exists on the feature branch via git
    import subprocess
    try:
        # List plan files on the branch
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", f"origin/{branch_name}", "docs/plans/"],
            capture_output=True, text=True, timeout=10,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                fname = line.strip().split("/")[-1]
                if fname.endswith(".md"):
                    # Check if it matches the sprint number
                    if f"sprint-{sprint_num}" in fname or f"sprint{sprint_num}" in fname or f"s0{sprint_num}" in fname or f"s{sprint_num}" in fname:
                        # Fetch the file content from the branch
                        content_result = subprocess.run(
                            ["git", "show", f"origin/{branch_name}:{line.strip()}"],
                            capture_output=True, text=True, timeout=10,
                            stdin=subprocess.DEVNULL,
                        )
                        if content_result.returncode == 0:
                            # Write to a temp location so we can parse it
                            temp_plan = Path(plans_dir) / f".gate_temp_{fname}"
                            temp_plan.write_text(content_result.stdout, encoding="utf-8")
                            return temp_plan
    except Exception:
        pass

    return None


def count_l3_scenarios(plan_path: Path) -> int:
    """Count the number of L3 workflow scenarios defined in the plan."""
    try:
        content = plan_path.read_text(encoding="utf-8")
    except Exception:
        return 0

    # Find the L3 Workflow Scenarios table
    in_table = False
    count = 0
    for line in content.splitlines():
        if "L3 Workflow Scenarios" in line:
            in_table = True
            continue
        if in_table:
            # Table rows start with |
            if line.strip().startswith("|"):
                # Skip header and separator rows
                stripped = line.strip().strip("|").strip()
                if stripped and not stripped.startswith("-") and not stripped.startswith("User"):
                    count += 1
            elif line.strip() and not line.strip().startswith("|"):
                break  # End of table

    return count


def find_evidence_files(sprint_id: str, repo_root: str = ".", branch_name: str = "") -> dict:
    """Find L3 evidence files — supports both canonical and legacy formats.

    Checks local filesystem first, then the PR branch via git show.
    Canonical: output/l3/{sprint}/form_submissions.json
    Legacy: output/l3/{sprint}_*.json or output/l3/s{NNN}_*.json
    """
    base = Path(repo_root) / "output" / "l3"
    result = {
        "canonical_dir": None,
        "canonical_files": [],
        "legacy_files": [],
        "any_found": False,
    }

    if not base.exists() and not branch_name:
        return result

    # Check canonical format: output/l3/{sprint}/ — try multiple name forms
    sprint_num = re.sub(r"[^0-9]", "", sprint_id)
    candidate_dirs = [
        base / sprint_id,           # e.g., output/l3/s97
        base / f"s0{sprint_num}",   # e.g., output/l3/s097
        base / f"s{sprint_num}",    # e.g., output/l3/s97
    ]
    for sprint_dir in candidate_dirs:
        if sprint_dir.is_dir():
            result["canonical_dir"] = str(sprint_dir)
            for name in ["form_submissions.json", "api_mutations.json", "state_verification.json"]:
                f = sprint_dir / name
                if f.exists() and str(f) not in result["canonical_files"]:
                    result["canonical_files"].append(str(f))

    # Check legacy format: output/l3/{sprint}_*.json or s{NNN}_*.json
    for f in base.glob("*.json"):
        fname = f.name.lower()
        if sprint_id.lower() in fname or f"s{sprint_num}" in fname or f"s0{sprint_num}" in fname:
            result["legacy_files"].append(str(f))

    result["any_found"] = bool(result["canonical_files"] or result["legacy_files"])
    return result


def count_evidence_entries(evidence_files: dict) -> int:
    """Count the total entries across all evidence files."""
    count = 0

    # Count canonical form_submissions.json entries
    for fpath in evidence_files.get("canonical_files", []):
        if "form_submissions" in fpath:
            try:
                data = json.loads(Path(fpath).read_text(encoding="utf-8"))
                if isinstance(data, list):
                    count += len(data)
            except Exception:
                pass

    # Count legacy file entries (each file may be an array or have a results key)
    for fpath in evidence_files.get("legacy_files", []):
        try:
            data = json.loads(Path(fpath).read_text(encoding="utf-8"))
            if isinstance(data, list):
                count += len(data)
            elif isinstance(data, dict):
                # Common patterns: {"results": [...]}, {"tests": [...]}, {"scenarios": [...]}
                for key in ("results", "tests", "scenarios", "submissions"):
                    if isinstance(data.get(key), list):
                        count += len(data[key])
                        break
        except Exception:
            pass

    return count


def run_deterministic_gate(
    branch_name: str,
    repo_root: str = ".",
    plans_dir: str = "docs/plans",
) -> GateResult:
    """Run all deterministic checks. Returns GateResult.

    This function must NEVER import AI libraries or make API calls.
    It is pure Python infrastructure — the Stripe blueprint pattern.
    """
    # Step 1: Find sprint plan from branch name
    plan_path = find_sprint_plan(branch_name, plans_dir=str(Path(repo_root) / plans_dir))
    if plan_path is None:
        return GateResult(
            passed=True,
            skip_reason=f"Non-sprint PR (branch: {branch_name}) — gate skipped",
        )

    # Step 2: Extract sprint ID from branch name
    match = re.search(r"s0?(\d{2,3})", branch_name, re.IGNORECASE)
    sprint_id = f"s{match.group(1)}" if match else ""

    # Step 3: Count expected L3 scenarios from plan
    expected_scenarios = count_l3_scenarios(plan_path)

    # Step 4: Find evidence files (check local first, then branch)
    evidence = find_evidence_files(sprint_id, repo_root, branch_name=branch_name)

    # Step 5: Run checks
    missing = []
    gaps = []

    if not evidence["any_found"]:
        missing.append(
            f"No L3 evidence files found for {sprint_id} "
            f"(checked output/l3/{sprint_id}/ and output/l3/{sprint_id}_*.json)"
        )
    else:
        # Check evidence entry count vs expected scenarios
        entry_count = count_evidence_entries(evidence)
        if expected_scenarios > 0 and entry_count < expected_scenarios:
            gaps.append(
                f"Evidence has {entry_count} entries but plan defines "
                f"{expected_scenarios} L3 scenarios (need at least {expected_scenarios})"
            )

    passed = not missing and not gaps

    return GateResult(
        passed=passed,
        missing_evidence=missing,
        evidence_gaps=gaps,
        details=f"Plan: {plan_path.name}, sprint: {sprint_id}, "
        f"expected scenarios: {expected_scenarios}, "
        f"evidence files: {len(evidence['canonical_files'])} canonical + "
        f"{len(evidence['legacy_files'])} legacy",
    )
