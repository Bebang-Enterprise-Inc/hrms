"""Deterministic pre-check layer for governor code reviews.

Runs BEFORE the AI review. Zero cost, instant, catches known failure patterns.
Checks: py_compile, Link field defaults, decorator placement, lesson pattern matching.
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from .lessons import MEMORY_DIR, _parse_frontmatter

logger = structlog.get_logger("governor.pre_check")


@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str


@dataclass
class PreCheckResult:
    passed: bool
    checks: list[CheckItem] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary_for_prompt(self) -> str:
        """Format pre-check results for inclusion in AI review prompt."""
        lines = ["## Pre-Check Results (deterministic, zero-cost)\n"]
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(f"- [{status}] {c.name}: {c.detail}")
        if self.blocking_issues:
            lines.append("\n### BLOCKING Issues (auto-REJECT)")
            for issue in self.blocking_issues:
                lines.append(f"- {issue}")
        if self.warnings:
            lines.append("\n### Warnings (investigate further)")
            for w in self.warnings:
                lines.append(f"- {w}")
        return "\n".join(lines)


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def run_all(changed_files: list[str], repo_root: str) -> PreCheckResult:
    """Run all deterministic pre-checks on the changed files.

    Args:
        changed_files: List of file paths relative to repo root.
        repo_root: Absolute path to the repository root.

    Returns:
        PreCheckResult with all check outcomes.
    """
    result = PreCheckResult(passed=True)

    py_files = [f for f in changed_files if f.endswith(".py")]
    json_files = [f for f in changed_files if f.endswith(".json") and "doctype/bei_" in f]

    # Check 1: py_compile
    check = _check_py_compile(py_files, repo_root)
    result.checks.append(check)
    if not check.passed:
        result.passed = False
        result.blocking_issues.append(check.detail)
    print(f"[{_ts()}]   Pre-checks: py_compile ({len(py_files)} files)... {'OK' if check.passed else 'FAIL'}", flush=True)

    # Check 2: Link field defaults
    check = _check_link_defaults(json_files, repo_root)
    result.checks.append(check)
    if not check.passed:
        result.passed = False
        result.blocking_issues.append(check.detail)
    print(f"[{_ts()}]   Pre-checks: Link defaults ({len(json_files)} files)... {'OK' if check.passed else 'FAIL'}", flush=True)

    # Check 3: Decorator placement
    check = _check_decorator_placement(py_files, repo_root)
    result.checks.append(check)
    if not check.passed:
        result.passed = False
        result.blocking_issues.append(check.detail)
    print(f"[{_ts()}]   Pre-checks: Decorators ({len(py_files)} files)... {'OK' if check.passed else 'FAIL'}", flush=True)

    # Check 4: Lesson pattern match
    check, matched_lessons = _check_lesson_patterns(changed_files, repo_root)
    result.checks.append(check)
    if matched_lessons:
        result.warnings.extend(matched_lessons)
    print(f"[{_ts()}]   Pre-checks: Lesson match... {len(matched_lessons)} triggered", flush=True)

    # Print blocking details
    for issue in result.blocking_issues:
        print(f"[{_ts()}]     BLOCKING: {issue}", flush=True)
    for warning in result.warnings:
        print(f"[{_ts()}]     WARNING: {warning}", flush=True)

    return result


def get_changed_files(repo_root: str) -> list[str]:
    """Get list of changed files vs origin/production."""
    try:
        proc = subprocess.run(
            ["git", "diff", "origin/production...HEAD", "--name-only"],
            capture_output=True, text=True, timeout=30,
            cwd=repo_root,
        )
        if proc.returncode == 0:
            return [f.strip() for f in proc.stdout.strip().splitlines() if f.strip()]
    except Exception as e:
        logger.warning("get_changed_files_failed", error=str(e))
    return []


# --- Individual checks ---


def _check_py_compile(py_files: list[str], repo_root: str) -> CheckItem:
    """Compile-check all changed Python files."""
    if not py_files:
        return CheckItem(name="py_compile", passed=True, detail="No Python files changed")

    failures = []
    for f in py_files:
        filepath = os.path.join(repo_root, f)
        if not os.path.isfile(filepath):
            continue
        try:
            py_compile.compile(filepath, doraise=True)
        except py_compile.PyCompileError as e:
            failures.append(f"{f}: {e.msg}")

    if failures:
        detail = "; ".join(failures[:3])
        if len(failures) > 3:
            detail += f" ... and {len(failures) - 3} more"
        return CheckItem(name="py_compile", passed=False, detail=detail)

    return CheckItem(name="py_compile", passed=True, detail=f"{len(py_files)} files OK")


def _check_link_defaults(json_files: list[str], repo_root: str) -> CheckItem:
    """Check DocType JSONs for Link fields with defaults."""
    if not json_files:
        return CheckItem(name="link_defaults", passed=True, detail="No DocType JSONs changed")

    issues = []
    for f in json_files:
        filepath = os.path.join(repo_root, f)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, encoding="utf-8") as fh:
                data = json.load(fh)
            for fld in data.get("fields", []):
                if fld.get("fieldtype") == "Link" and fld.get("default"):
                    fieldname = fld.get("fieldname", "unknown")
                    default_val = fld["default"]
                    issues.append(f"{f}: Link field '{fieldname}' has default '{default_val}'")
        except (json.JSONDecodeError, KeyError):
            continue

    if issues:
        detail = "; ".join(issues[:3])
        if len(issues) > 3:
            detail += f" ... and {len(issues) - 3} more"
        return CheckItem(name="link_defaults", passed=False, detail=detail)

    return CheckItem(name="link_defaults", passed=True, detail=f"{len(json_files)} files OK")


def _check_decorator_placement(py_files: list[str], repo_root: str) -> CheckItem:
    """Check that decorators are only on function/class definitions."""
    if not py_files:
        return CheckItem(name="decorator_placement", passed=True, detail="No Python files changed")

    issues = []
    for f in py_files:
        filepath = os.path.join(repo_root, f)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=f)
        except SyntaxError:
            # py_compile already catches this
            continue

        for node in ast.walk(tree):
            # Decorators are valid on FunctionDef, AsyncFunctionDef, ClassDef
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            # Check for decorator_list on unexpected node types
            if hasattr(node, "decorator_list") and node.decorator_list:
                for dec in node.decorator_list:
                    dec_name = _get_decorator_name(dec)
                    issues.append(
                        f"{f}:{dec.lineno} — decorator @{dec_name} on {type(node).__name__}"
                    )

    if issues:
        detail = "; ".join(issues[:3])
        return CheckItem(name="decorator_placement", passed=False, detail=detail)

    return CheckItem(name="decorator_placement", passed=True, detail=f"{len(py_files)} files OK")


def _get_decorator_name(node: ast.AST) -> str:
    """Extract human-readable name from a decorator AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{_get_decorator_name(node.func)}()"
    return "?"


def _check_lesson_patterns(changed_files: list[str], repo_root: str) -> tuple[CheckItem, list[str]]:
    """Check changed files against lesson trigger patterns."""
    lessons = _load_lesson_triggers()
    if not lessons:
        return CheckItem(name="lesson_match", passed=True, detail="No lessons loaded"), []

    # Only check code files — skip docs, plans, tests, markdown
    _SKIP_PREFIXES = ("docs/", "output/", "data/", ".claude/", "tmp/")
    _SKIP_EXTENSIONS = (".md", ".csv", ".txt", ".png", ".jpg", ".pdf")
    code_files = [
        f for f in changed_files
        if not any(f.startswith(p) for p in _SKIP_PREFIXES)
        and not any(f.endswith(e) for e in _SKIP_EXTENSIONS)
    ]

    matched = []
    for lesson_id, trigger_text in lessons:
        for f in code_files:
            file_path = os.path.join(repo_root, f)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read(50000).lower()

                if _trigger_matches_content(trigger_text.lower(), content, f.lower()):
                    matched.append(f"Lesson '{lesson_id}' triggered on {f}: {trigger_text[:80]}")
                    break
            except Exception:
                continue

    detail = f"{len(matched)} of {len(lessons)} lessons matched" if matched else f"0 of {len(lessons)} lessons triggered"
    return CheckItem(name="lesson_match", passed=True, detail=detail), matched


def _trigger_matches_content(trigger: str, content: str, filename: str) -> bool:
    """Check if a lesson trigger pattern matches file content."""
    # Match specific known patterns
    if "link" in trigger and "default" in trigger and "fieldtype" in content and '"default"' in content:
        return True
    if "decorator" in trigger and "whitelist" in trigger:
        if "@frappe.whitelist" in content:
            # Check if decorator is on a non-function (already caught by ast check, but flag for AI)
            return False  # Let the decorator check handle this directly
    if "duplicate import" in trigger and content.count("import ") > 1:
        # Check for actual duplicate imports
        import_lines = [line.strip() for line in content.splitlines() if line.strip().startswith(("import ", "from "))]
        if len(import_lines) != len(set(import_lines)):
            return True
    return False


def _load_lesson_triggers() -> list[tuple[str, str]]:
    """Load lesson IDs and triggers from governor memory."""
    results = []
    if not MEMORY_DIR.exists():
        return results

    for f in MEMORY_DIR.glob("lesson-*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if meta and meta.get("trigger"):
                results.append((meta.get("id", f.stem), meta["trigger"]))
        except Exception:
            continue

    return results
