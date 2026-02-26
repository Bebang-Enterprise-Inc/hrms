#!/usr/bin/env python3
"""
L3 Browser Guard

Hard gates to ensure L3 tests behave like real users in a browser.

Modes:
1) scan      - Static scan for API-first anti-patterns in L3 tests.
2) validate  - Validate a runtime evidence JSON from a browser-driven L3 run.

Examples:
  python scripts/testing/l3_browser_guard.py scan
  python scripts/testing/l3_browser_guard.py validate \
    --evidence output/l3/evidence/MAINT-001.json \
    --expected-endpoint hrms.api.store.submit_maintenance_request \
    --requires-upload
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Violation:
    file: Path
    line: int
    code: str
    message: str
    excerpt: str

    def format(self) -> str:
        rel = self.file.relative_to(ROOT)
        return f"{rel}:{self.line}: {self.code} {self.message}\n  {self.excerpt.strip()}"


def _iter_candidate_files() -> Iterable[Path]:
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return []

    candidates: List[Path] = []
    for pattern in ("**/*.py", "**/*.ts", "**/*.tsx"):
        candidates.extend(tests_dir.glob(pattern))
    return candidates


def _is_l3_file(path: Path, text: str) -> bool:
    name = path.name.lower()
    if "l3" in name:
        return True
    markers = (
        "level: l3",
        "l3 test",
        "submit + verify",
        "scenario-driven",
    )
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def scan_l3_files() -> List[Violation]:
    violations: List[Violation] = []

    # Pattern list: (regex, code, message)
    checks: List[Tuple[re.Pattern[str], str, str]] = [
        (
            re.compile(r"\brequests\.(get|post|put|patch|delete)\(", re.IGNORECASE),
            "L3G001",
            "Direct requests.* call found in L3 test. Use browser UI actions for submission.",
        ),
        (
            re.compile(r"page\.request\.(post|put|patch)\(", re.IGNORECASE),
            "L3G002",
            "Playwright APIRequestContext mutation found. L3 submit must come from UI clicks.",
        ),
        (
            re.compile(r"fetch\(\s*['\"]/?api/method/", re.IGNORECASE),
            "L3G003",
            "In-browser fetch('/api/method/...') found. This bypasses form interaction.",
        ),
        (
            re.compile(r"page\.goto\(\s*['\"][^'\"]*/dashboard/", re.IGNORECASE),
            "L3G004",
            "Direct dashboard route navigation found. L3 should navigate via sidebar clicks.",
        ),
    ]

    for file_path in _iter_candidate_files():
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not _is_l3_file(file_path, text):
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            # Allow login goto
            if "page.goto" in line and "/login" in line:
                continue
            for pattern, code, message in checks:
                if pattern.search(line):
                    violations.append(
                        Violation(
                            file=file_path,
                            line=line_no,
                            code=code,
                            message=message,
                            excerpt=line,
                        )
                    )

    return violations


def _exists(path_str: str | None) -> bool:
    if not path_str:
        return False
    p = Path(path_str)
    if not p.is_absolute():
        p = ROOT / p
    return p.exists()


def validate_evidence(
    evidence_path: Path, expected_endpoint: str | None, requires_upload: bool
) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    try:
        raw = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"Unable to parse evidence JSON: {exc}"]

    actions = raw.get("actions", [])
    network = raw.get("network", [])
    artifacts = raw.get("artifacts", {})

    action_types = [a.get("type", "") for a in actions if isinstance(a, dict)]
    count = {t: action_types.count(t) for t in set(action_types)}

    if count.get("nav_sidebar", 0) < 1:
        errors.append("Missing sidebar navigation proof (`nav_sidebar` action).")
    if count.get("click", 0) < 1:
        errors.append("Missing click proof (`click` action).")
    if count.get("fill", 0) < 1:
        errors.append("Missing form input proof (`fill` action).")
    if count.get("submit", 0) < 1:
        errors.append("Missing submit proof (`submit` action).")
    if requires_upload and count.get("upload", 0) < 1:
        errors.append("Missing upload proof (`upload` action) for required-upload scenario.")

    mutating_calls = [
        n
        for n in network
        if isinstance(n, dict)
        and str(n.get("method", "")).upper() in {"POST", "PUT", "PATCH", "DELETE"}
        and "/api/" in str(n.get("url", ""))
    ]
    if not mutating_calls:
        errors.append("No mutating /api/ network call captured from browser session.")

    if expected_endpoint:
        expected_hits = [
            n
            for n in mutating_calls
            if expected_endpoint in str(n.get("url", ""))
        ]
        if not expected_hits:
            errors.append(
                f"Expected endpoint not seen in browser network log: {expected_endpoint}"
            )

    trace = artifacts.get("trace")
    if not _exists(trace):
        errors.append("Missing Playwright trace artifact.")

    screenshots = artifacts.get("screenshots", [])
    if not isinstance(screenshots, list) or not screenshots:
        errors.append("Missing screenshots list in artifacts.")
    else:
        if not any(_exists(s) for s in screenshots):
            errors.append("Screenshots declared but files do not exist.")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="L3 browser realism guard")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="Scan L3 tests for API-first anti-patterns.")

    validate = sub.add_parser("validate", help="Validate one L3 evidence JSON.")
    validate.add_argument("--evidence", required=True, help="Path to evidence JSON.")
    validate.add_argument(
        "--expected-endpoint",
        required=False,
        default=None,
        help="Expected Frappe method, e.g. hrms.api.store.submit_maintenance_request",
    )
    validate.add_argument(
        "--requires-upload",
        action="store_true",
        help="Require at least one upload action in evidence.",
    )

    args = parser.parse_args()

    if args.cmd == "scan":
        violations = scan_l3_files()
        if not violations:
            print("PASS: No L3 browser guard violations found.")
            return 0
        print(f"FAIL: Found {len(violations)} L3 browser guard violation(s):")
        for v in violations:
            print(v.format())
        return 1

    evidence_path = Path(args.evidence)
    if not evidence_path.is_absolute():
        evidence_path = ROOT / evidence_path
    if not evidence_path.exists():
        print(f"FAIL: Evidence file not found: {evidence_path}")
        return 1

    ok, errors = validate_evidence(
        evidence_path=evidence_path,
        expected_endpoint=args.expected_endpoint,
        requires_upload=args.requires_upload,
    )
    if ok:
        print("PASS: Evidence satisfies browser-realism requirements.")
        return 0

    print("FAIL: Evidence validation failed:")
    for err in errors:
        print(f"- {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
