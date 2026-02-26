#!/usr/bin/env python3
"""
Generate markdown report from an l3_v2_runner JSON output file.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = ROOT / "docs" / "testing" / "reports"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _run_id_from_file(path: Path) -> str:
    stem = path.stem
    marker = "l3_v2_run_"
    if marker in stem:
        return stem.split(marker, 1)[1]
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in results:
        status = str(row.get("status", "UNKNOWN"))
        out[status] = out.get(status, 0) + 1
    return out


def render_report(run_file: Path, payload: dict[str, Any]) -> str:
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    counts = _status_counts(results)

    lines: list[str] = []
    lines.append("# L3 v2 Full Module Run Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat()}")
    lines.append(f"- Run file: `{_rel(run_file)}`")
    lines.append(f"- Ran at: `{payload.get('ran_at')}`")
    lines.append(f"- Requested module: `{payload.get('requested_module')}`")
    lines.append(f"- Scenario index: `{payload.get('index_file')}`")
    lines.append(
        "- Status counts: "
        + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if counts
        else "- Status counts: none"
    )
    lines.append("")
    lines.append("## Module Summary")
    lines.append("")
    lines.append("| Module | Status | Scenarios | Manifest |")
    lines.append("|---|---:|---:|---:|")
    for row in results:
        lines.append(
            f"| {row.get('module')} | {row.get('status')} | {row.get('scenario_count', 0)} | {row.get('module_status')} |"
        )

    lines.append("")
    lines.append("## Module Details")
    lines.append("")
    for row in results:
        module = row.get("module")
        status = row.get("status")
        lines.append(f"### {module} [{status}]")
        lines.append("")
        detail = str(row.get("detail", "")).strip()
        if detail:
            lines.append("```text")
            lines.append(detail)
            lines.append("```")
        artifacts = row.get("artifacts", [])
        if artifacts:
            lines.append("Artifacts:")
            for artifact in artifacts:
                lines.append(f"- `{artifact}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate L3 markdown report from run JSON.")
    parser.add_argument(
        "--run-file",
        required=True,
        help="Path to output/l3/runs/l3_v2_run_*.json",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output markdown path. Default: docs/testing/reports/l3_v2_run_<id>.md",
    )
    args = parser.parse_args()

    run_file = Path(args.run_file)
    if not run_file.is_absolute():
        run_file = ROOT / run_file
    if not run_file.exists():
        raise SystemExit(f"Run file not found: {run_file}")

    payload = json.loads(run_file.read_text(encoding="utf-8"))
    run_id = _run_id_from_file(run_file)
    out_file = Path(args.out) if args.out else DEFAULT_REPORT_DIR / f"l3_v2_run_{run_id}.md"
    if not out_file.is_absolute():
        out_file = ROOT / out_file
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(render_report(run_file, payload), encoding="utf-8")

    print(f"REPORT_FILE={_rel(out_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
