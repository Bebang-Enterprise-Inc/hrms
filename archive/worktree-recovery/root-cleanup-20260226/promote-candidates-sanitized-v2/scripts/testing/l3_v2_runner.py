#!/usr/bin/env python3
"""
L3 v2 orchestrator.

Reads docs/testing/scenarios/index.yaml and executes available module runners.
Combines:
- Python browser runners (scenario-specific)
- Playwright suites from tests/e2e (module smoke coverage)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = ROOT / "docs" / "testing" / "scenarios" / "index.yaml"
SCENARIO_ID_RE = r"^#{3,6}\s+([A-Z][A-Z0-9-]+-\d{3}):"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
NPX_BIN = "npx.cmd" if sys.platform == "win32" else "npx"

# Runner config by module key.
MODULE_RUNNERS = {
    "maintenance": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-013"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-014"},
            {"file": "tests/e2e/negative.spec.ts", "grep": "NEG-MAINT-001"},
            {"file": "tests/e2e/negative.spec.ts", "grep": "NEG-MAINT-002"},
        ],
    },
    "store-ops": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-001"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-002"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-011"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-012"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-015"},
            {"file": "tests/e2e/store-staff.spec.ts", "grep": "TC-STAFF-017"},
        ],
    },
    "hr": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/cross-role/leave-approval.spec.ts", "grep": "CR-LEAVE-001"},
            {"file": "tests/e2e/cross-role/leave-approval.spec.ts", "grep": "CR-LEAVE-002"},
            {"file": "tests/e2e/cross-role/leave-approval.spec.ts", "grep": "CR-LEAVE-003"},
        ],
    },
    "expense": {
        "kind": "python",
        "cmd": [sys.executable, "scripts/testing/l3_expense_runner.py"],
    },
    "communication": {
        "kind": "python",
        "cmd": [sys.executable, "scripts/testing/l3_comm_support_runner.py"],
    },
    "biometric": {
        "kind": "python",
        "cmd": [sys.executable, "scripts/testing/l3_biometric_runner.py"],
    },
    "finance": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D1"},
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D2"},
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D6"},
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D12"},
        ],
    },
    "billing": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D6"},
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D7"},
            {"file": "tests/e2e/flow_d.spec.ts", "grep": "D8"},
        ],
    },
    "scm": {
        "kind": "playwright",
        "suites": [
            {"file": "tests/e2e/flow_b.spec.ts", "grep": "B6"},
            {"file": "tests/e2e/flow_b.spec.ts", "grep": "B8"},
            {"file": "tests/e2e/flow_b.spec.ts", "grep": "B9"},
            {"file": "tests/e2e/flow_b.spec.ts", "grep": "B11"},
            {"file": "tests/e2e/flow_b.spec.ts", "grep": "B12"},
            {"file": "tests/e2e/warehouse.spec.ts", "grep": "TC-WH-004"},
        ],
    },
    "stock-counting": {
        "kind": "python",
        "cmd": [sys.executable, "scripts/testing/l3_stock_counting_runner.py"],
    },
}


@dataclass
class ModuleTarget:
    key: str
    status: str
    scenario_files: list[Path]
    scenario_count: int
    command: str


@dataclass
class PlaywrightSuiteResult:
    file: str
    grep: str | None
    expected: int
    unexpected: int
    flaky: int
    skipped: int
    duration_ms: float
    failed_tests: list[str]
    raw_report_file: str


def _load_index() -> dict[str, Any]:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"Missing index file: {INDEX_FILE}")
    raw = yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("index.yaml is not a map.")
    return raw


def _extract_scenario_count(paths: list[Path]) -> int:
    import re

    count = 0
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        count += len(re.findall(SCENARIO_ID_RE, text, flags=re.M))
    return count


def _collect_modules(index: dict[str, Any]) -> list[ModuleTarget]:
    modules: list[ModuleTarget] = []
    for row in index.get("modules", []):
        files = []
        for p in row.get("scenario_files", []):
            path = Path(p)
            if not path.is_absolute():
                path = ROOT / path
            files.append(path)

        key = str(row.get("key"))
        status = str(row.get("status", "ready"))
        command = str(row.get("command", key))
        modules.append(
            ModuleTarget(
                key=key,
                status=status,
                scenario_files=files,
                scenario_count=_extract_scenario_count(files),
                command=command,
            )
        )
    return modules


def _playwright_env() -> dict[str, str]:
    env = dict(os.environ)
    appdata = env.get("APPDATA")
    if appdata:
        node_path = str(Path(appdata) / "npm" / "node_modules")
        env["NODE_PATH"] = node_path
    return env


def _parse_playwright_json(raw: str) -> dict[str, Any]:
    # reporter=json writes a full JSON payload to stdout.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Unable to locate Playwright JSON payload in stdout.")
    blob = raw[start : end + 1]
    return json.loads(blob)


def _iter_specs(suites: list[dict[str, Any]]):
    for suite in suites:
        for spec in suite.get("specs", []):
            yield spec
        yield from _iter_specs(suite.get("suites", []))


def _extract_failed_tests(report: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for spec in _iter_specs(report.get("suites", [])):
        title = spec.get("title", "<unknown>")
        file_name = spec.get("file", "")
        for test in spec.get("tests", []):
            for res in test.get("results", []):
                if res.get("status") in {"failed", "timedOut", "interrupted"}:
                    out.append(f"{file_name}: {title}")
                    break
            else:
                continue
            break
    return out


def _run_playwright_module(
    module_key: str,
    suites: list[dict[str, str]],
    run_id: str,
) -> tuple[str, str, list[str]]:
    suite_results: list[PlaywrightSuiteResult] = []
    module_fail = False
    artifact_files: list[str] = []

    for idx, suite in enumerate(suites, start=1):
        test_file = suite["file"]
        grep = suite.get("grep")
        out_dir = ROOT / "output" / "l3" / "playwright" / run_id / module_key / f"suite_{idx}"
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            NPX_BIN,
            "playwright",
            "test",
            test_file,
            "--reporter=json",
            "--output",
            str(out_dir),
        ]
        if grep:
            cmd.extend(["--grep", grep])

        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            env=_playwright_env(),
            check=False,
            timeout=20 * 60,  # 20 min per suite
        )
        raw = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

        raw_report_file = out_dir / "playwright_report_raw.json"
        raw_report_file.write_text(raw, encoding="utf-8", errors="ignore")
        artifact_files.append(str(raw_report_file.relative_to(ROOT)).replace("\\", "/"))

        try:
            report = _parse_playwright_json(raw)
        except Exception as exc:
            module_fail = True
            suite_results.append(
                PlaywrightSuiteResult(
                    file=test_file,
                    grep=grep,
                    expected=0,
                    unexpected=1,
                    flaky=0,
                    skipped=0,
                    duration_ms=0.0,
                    failed_tests=[f"{test_file}: unable to parse report ({exc})"],
                    raw_report_file=str(raw_report_file.relative_to(ROOT)).replace("\\", "/"),
                )
            )
            continue

        stats = report.get("stats", {})
        expected = int(stats.get("expected", 0))
        unexpected = int(stats.get("unexpected", 0))
        flaky = int(stats.get("flaky", 0))
        skipped = int(stats.get("skipped", 0))
        duration_ms = float(stats.get("duration", 0.0))
        failed_tests = _extract_failed_tests(report)

        if unexpected > 0:
            module_fail = True

        summary_report_file = out_dir / "playwright_report_summary.json"
        summary_payload = {
            "module": module_key,
            "file": test_file,
            "grep": grep,
            "stats": stats,
            "failed_tests": failed_tests,
        }
        summary_report_file.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
        artifact_files.append(str(summary_report_file.relative_to(ROOT)).replace("\\", "/"))

        suite_results.append(
            PlaywrightSuiteResult(
                file=test_file,
                grep=grep,
                expected=expected,
                unexpected=unexpected,
                flaky=flaky,
                skipped=skipped,
                duration_ms=duration_ms,
                failed_tests=failed_tests,
                raw_report_file=str(raw_report_file.relative_to(ROOT)).replace("\\", "/"),
            )
        )

    total_expected = sum(s.expected for s in suite_results)
    total_unexpected = sum(s.unexpected for s in suite_results)
    total_flaky = sum(s.flaky for s in suite_results)
    total_skipped = sum(s.skipped for s in suite_results)
    total_duration = sum(s.duration_ms for s in suite_results)
    status = "PASS" if not module_fail else "FAIL"

    lines = [
        f"playwright_suites={len(suite_results)}",
        (
            f"expected={total_expected} unexpected={total_unexpected} "
            f"flaky={total_flaky} skipped={total_skipped} duration_ms={int(total_duration)}"
        ),
    ]
    for s in suite_results:
        suite_line = (
            f"- {s.file} grep={s.grep or '<none>'} "
            f"exp={s.expected} unexp={s.unexpected} skip={s.skipped}"
        )
        lines.append(suite_line)
        if s.failed_tests:
            lines.extend(f"  * {ft}" for ft in s.failed_tests[:5])

    return status, "\n".join(lines), artifact_files


def _run_python_module(cmd: list[str]) -> tuple[str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode == 0:
        return "PASS", output.strip()
    return "FAIL", output.strip()


def _run_module(key: str, run_id: str) -> tuple[str, str, list[str]]:
    runner = MODULE_RUNNERS.get(key)
    if not runner:
        return "NOT_IMPLEMENTED", "No runner mapped for this module.", []

    kind = runner.get("kind")
    if kind == "python":
        status, detail = _run_python_module(runner["cmd"])
        return status, detail, []

    if kind == "playwright":
        return _run_playwright_module(
            module_key=key,
            suites=runner.get("suites", []),
            run_id=run_id,
        )

    return "NOT_IMPLEMENTED", f"Unsupported runner kind: {kind}", []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run L3 v2 module runners from scenario index.")
    parser.add_argument(
        "--module",
        default="all",
        help="Module key from index.yaml, or 'all'.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List modules and scenario counts, then exit.",
    )
    args = parser.parse_args()

    index = _load_index()
    modules = _collect_modules(index)
    by_key = {m.key: m for m in modules}

    if args.list:
        print("L3 v2 modules:")
        for m in modules:
            print(
                f"- {m.key:14} status={m.status:7} command={m.command:12} scenarios={m.scenario_count}"
            )
        return 0

    targets: list[ModuleTarget]
    if args.module == "all":
        targets = modules
    else:
        if args.module not in by_key:
            print(f"Unknown module: {args.module}")
            print("Use --list to inspect available module keys.")
            return 2
        targets = [by_key[args.module]]

    out_dir = ROOT / "output" / "l3" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_file = out_dir / f"l3_v2_run_{stamp}.json"

    results: list[dict[str, Any]] = []
    hard_fail = False
    for target in targets:
        row: dict[str, Any] = {
            "module": target.key,
            "status": "",
            "command": target.command,
            "module_status": target.status,
            "scenario_count": target.scenario_count,
            "detail": "",
            "artifacts": [],
        }
        if target.status != "ready":
            row["status"] = "GAP"
            row["detail"] = f"Module status is '{target.status}' in manifest."
            results.append(row)
            hard_fail = True
            continue

        status, detail, artifacts = _run_module(target.key, run_id=stamp)
        row["status"] = status
        row["detail"] = detail
        row["artifacts"] = artifacts
        if status != "PASS":
            hard_fail = True
        results.append(row)

    summary = {
        "ran_at": datetime.now().isoformat(),
        "index_file": str(INDEX_FILE.relative_to(ROOT)).replace("\\", "/"),
        "requested_module": args.module,
        "results": results,
    }
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"RESULT_FILE={out_file.relative_to(ROOT)}")
    for row in results:
        print(
            f"{row['status']:15} {row['module']:14} scenarios={row['scenario_count']:3} "
            f"manifest={row['module_status']}"
        )
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
