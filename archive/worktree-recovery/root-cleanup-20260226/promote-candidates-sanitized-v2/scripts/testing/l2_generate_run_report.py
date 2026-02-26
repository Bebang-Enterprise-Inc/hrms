#!/usr/bin/env python3
"""
Generate markdown report from an l2_page_check_runner JSON output file.
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
    marker = "l2_run_"
    if marker in stem:
        return stem.split(marker, 1)[1]
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in results:
        status = str(row.get("status", "UNKNOWN"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def render_report(run_file: Path, payload: dict[str, Any]) -> str:
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    summary = payload.get("summary", {})
    by_module = summary.get("by_module", {}) if isinstance(summary, dict) else {}
    counts = _status_counts(results)
    failed = [r for r in results if r.get("status") == "FAIL"]

    lines: list[str] = []
    lines.append("# L2 Page Check Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat()}")
    lines.append(f"- Run file: `{_rel(run_file)}`")
    lines.append(f"- Ran at: `{payload.get('ran_at')}`")
    lines.append(f"- Requested module: `{payload.get('requested_module')}`")
    lines.append(f"- Route registry: `{payload.get('route_registry')}`")
    lines.append(
        "- Status counts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        if counts
        else "- Status counts: none"
    )

    lines.append("")
    lines.append("## Module Summary")
    lines.append("")
    lines.append("| Module | Total | PASS | FAIL |")
    lines.append("|---|---:|---:|---:|")
    for module in sorted(by_module.keys()):
        row = by_module[module]
        lines.append(
            f"| {module} | {row.get('total', 0)} | {row.get('passed', 0)} | {row.get('failed', 0)} |"
        )

    lines.append("")
    lines.append("## Failed Routes")
    lines.append("")
    if not failed:
        lines.append("- None")
    else:
        for row in failed:
            lines.append(
                f"- `{row.get('module')}` `{row.get('route')}` role={row.get('role')} detail={row.get('detail')} screenshot=`{row.get('screenshot')}`"
            )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate L2 markdown report from run JSON.")
    parser.add_argument("--run-file", required=True, help="Path to output/l2/runs/l2_run_*.json")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path. Default: docs/testing/reports/l2_run_<id>.md",
    )
    args = parser.parse_args()

    run_file = Path(args.run_file)
    if not run_file.is_absolute():
        run_file = ROOT / run_file
    if not run_file.exists():
        raise SystemExit(f"Run file not found: {run_file}")

    payload = json.loads(run_file.read_text(encoding="utf-8"))
    run_id = _run_id_from_file(run_file)
    out_file = Path(args.out) if args.out else DEFAULT_REPORT_DIR / f"l2_run_{run_id}.md"
    if not out_file.is_absolute():
        out_file = ROOT / out_file
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(render_report(run_file, payload), encoding="utf-8")
    print(f"REPORT_FILE={_rel(out_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

