#!/usr/bin/env python3
"""
Run L1 -> L2 -> L3 gate sequence and write a consolidated gate report.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    result_file: str
    status: str


def _run_step(name: str, command: list[str], timeout_s: int) -> StepResult:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
        timeout=timeout_s,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    result_file = ""
    for line in stdout.splitlines():
        if line.startswith("RESULT_FILE="):
            result_file = line.split("=", 1)[1].strip().replace("\\", "/")
            break
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return StepResult(
        name=name,
        command=command,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        result_file=result_file,
        status=status,
    )


def _load_json(rel_path: str) -> dict[str, Any]:
    if not rel_path:
        return {}
    path = ROOT / rel_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _l3_manifest_ok(stdout: str) -> bool:
    return "L3 MANIFEST CHECK: PASS" in stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full L1/L2/L3 gate and write consolidated report.")
    parser.add_argument("--headed-l2", action="store_true", help="Run L2 in headed mode.")
    args = parser.parse_args()

    steps: list[StepResult] = []
    steps.append(
        _run_step(
            name="l1",
            command=[sys.executable, "scripts/testing/l1_api_check_runner.py", "--module", "all"],
            timeout_s=20 * 60,
        )
    )
    l2_cmd = [sys.executable, "scripts/testing/l2_page_check_runner.py", "--module", "all"]
    if args.headed_l2:
        l2_cmd.append("--headed")
    steps.append(_run_step(name="l2", command=l2_cmd, timeout_s=45 * 60))
    manifest = _run_step(
        name="l3_manifest",
        command=[sys.executable, "scripts/testing/l3_manifest_check.py"],
        timeout_s=3 * 60,
    )
    steps.append(manifest)
    steps.append(
        _run_step(
            name="l3",
            command=[sys.executable, "scripts/testing/l3_v2_runner.py", "--module", "all"],
            timeout_s=70 * 60,
        )
    )

    l1_payload = _load_json(next((s.result_file for s in steps if s.name == "l1"), ""))
    l2_payload = _load_json(next((s.result_file for s in steps if s.name == "l2"), ""))
    l3_payload = _load_json(next((s.result_file for s in steps if s.name == "l3"), ""))

    l1_failed = int(l1_payload.get("summary", {}).get("failed", 999999))
    l2_failed = int(l2_payload.get("summary", {}).get("failed", 999999))
    l3_failed = len([r for r in l3_payload.get("results", []) if r.get("status") != "PASS"])
    manifest_ok = _l3_manifest_ok(manifest.stdout)

    gate_ok = manifest_ok and l1_failed == 0 and l2_failed == 0 and l3_failed == 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_dir = ROOT / "output" / "testing" / "gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"e2e_gate_run_{stamp}.json"

    payload = {
        "ran_at": datetime.now().isoformat(),
        "gate_ok": gate_ok,
        "summary": {
            "l1_failed": l1_failed,
            "l2_failed": l2_failed,
            "l3_failed": l3_failed,
            "l3_manifest_ok": manifest_ok,
        },
        "steps": [
            {
                "name": s.name,
                "status": s.status,
                "returncode": s.returncode,
                "command": s.command,
                "result_file": s.result_file,
                "stdout_tail": "\n".join(s.stdout.splitlines()[-25:]),
                "stderr_tail": "\n".join(s.stderr.splitlines()[-25:]),
            }
            for s in steps
        ],
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"GATE_FILE={out_file.relative_to(ROOT)}")
    print(
        "GATE_STATUS="
        + ("PASS" if gate_ok else "FAIL")
        + f" l1_failed={l1_failed} l2_failed={l2_failed} l3_failed={l3_failed} manifest_ok={manifest_ok}"
    )
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

