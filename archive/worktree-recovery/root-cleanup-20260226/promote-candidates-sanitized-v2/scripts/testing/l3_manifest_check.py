#!/usr/bin/env python3
"""
Validate docs/testing/scenarios/index.yaml integrity and coverage.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = ROOT / "docs" / "testing" / "scenarios" / "index.yaml"
SCENARIO_ID_RE = re.compile(r"^#{3,6}\s+([A-Z][A-Z0-9-]+-\d{3}):", re.M)
PLAN_DOMAIN_RE = re.compile(r"hrms\.api\.([a-z_]+)")


@dataclass
class EntryCheck:
    kind: str
    key: str
    status: str
    command: str | None
    files: list[Path]
    prefixes_expected: list[str]
    ids: list[str]

    @property
    def prefixes_observed(self) -> set[str]:
        out: set[str] = set()
        for sid in self.ids:
            out.add(sid.rsplit("-", 1)[0])
        return out


def _as_path(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else ROOT / p


def _collect_ids(paths: Iterable[Path]) -> list[str]:
    ids: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        ids.extend(SCENARIO_ID_RE.findall(text))
    return ids


def _load_index() -> dict:
    if not INDEX_FILE.exists():
        raise SystemExit(f"Missing manifest: {INDEX_FILE}")
    return yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8"))


def _entry_checks(index: dict) -> list[EntryCheck]:
    checks: list[EntryCheck] = []
    for kind in ("modules", "flows"):
        for row in index.get(kind, []):
            files = [_as_path(p) for p in row.get("scenario_files", [])]
            ids = _collect_ids(files) if files else []
            checks.append(
                EntryCheck(
                    kind=kind,
                    key=row.get("key", ""),
                    status=row.get("status", "ready"),
                    command=row.get("command"),
                    files=files,
                    prefixes_expected=row.get("prefixes", []),
                    ids=ids,
                )
            )
    return checks


def main() -> int:
    index = _load_index()
    errors: list[str] = []
    warnings: list[str] = []

    checks = _entry_checks(index)
    all_ids: dict[str, str] = {}
    ready_commands: list[str] = []

    for item in checks:
        label = f"{item.kind}:{item.key}"
        for path in item.files:
            if not path.exists():
                errors.append(f"{label} missing file: {path.relative_to(ROOT)}")

        if item.command and item.status == "ready":
            ready_commands.append(item.command)

        if item.status == "ready" and not item.ids:
            errors.append(f"{label} is ready but has no scenario IDs.")
        if item.status in {"partial", "gap"} and not item.ids:
            warnings.append(f"{label} has no executable scenario IDs yet (status={item.status}).")

        observed = item.prefixes_observed
        for prefix in item.prefixes_expected:
            if prefix not in observed:
                if item.status == "ready":
                    errors.append(
                        f"{label} expects prefix '{prefix}' but no matching scenario ID found."
                    )
                else:
                    warnings.append(
                        f"{label} expects prefix '{prefix}' but no matching scenario ID found."
                    )

        for sid in item.ids:
            owner = f"{item.kind}:{item.key}"
            if sid in all_ids:
                errors.append(f"Duplicate scenario ID {sid} in {owner} and {all_ids[sid]}")
            else:
                all_ids[sid] = owner

    declared_commands = set(index.get("commands", []))
    for cmd in ready_commands:
        if cmd not in declared_commands:
            errors.append(f"Ready command '{cmd}' missing from top-level commands list.")
    if "all" not in declared_commands:
        errors.append("Top-level commands must include 'all'.")

    # Coverage checks against required domains.
    coverage = index.get("coverage", {})
    domain_prefix_reqs: dict[str, list[str]] = coverage.get("domain_prefix_requirements", {})
    required_domains: list[str] = coverage.get("required_domains", [])
    global_prefixes = {sid.rsplit("-", 1)[0] for sid in all_ids}

    for domain in required_domains:
        required_prefixes = domain_prefix_reqs.get(domain, [])
        if not required_prefixes:
            warnings.append(f"Domain '{domain}' has no required prefixes (gap by design).")
            continue
        if not any(p in global_prefixes for p in required_prefixes):
            errors.append(
                f"Domain '{domain}' uncovered: none of {required_prefixes} found in scenario IDs."
            )

    compare_plan = coverage.get("compare_plan")
    if compare_plan:
        plan_path = _as_path(compare_plan)
        if not plan_path.exists():
            errors.append(f"compare_plan file missing: {plan_path.relative_to(ROOT)}")
        else:
            plan_text = plan_path.read_text(encoding="utf-8")
            plan_domains = set(PLAN_DOMAIN_RE.findall(plan_text))
            missing_declared = sorted(
                d for d in required_domains if d not in plan_domains and d != "warehouse"
            )
            # "warehouse" is a flow concept and may not appear as hrms.api.warehouse.
            if missing_declared:
                warnings.append(
                    "Required domains not present in plan API domain list: "
                    + ", ".join(missing_declared)
                )

    if errors:
        print("L3 MANIFEST CHECK: FAIL")
        print("")
        for msg in errors:
            print(f"[ERROR] {msg}")
        if warnings:
            print("")
            for msg in warnings:
                print(f"[WARN]  {msg}")
        return 1

    print("L3 MANIFEST CHECK: PASS")
    print(f"- total scenario IDs: {len(all_ids)}")
    print(f"- commands: {', '.join(sorted(declared_commands))}")
    if warnings:
        print("- warnings:")
        for msg in warnings:
            print(f"  - {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
