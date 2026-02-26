"""Canonical L3 browser-driven smoke for Communication Support (COMM-003).

This wrapper runs the production-grade runner in scripts/testing and exits non-zero on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.testing.l3_comm_support_runner import run_comm_003


def run_test() -> None:
    result = run_comm_003()
    print(f"L3 COMM-003 STATUS: {result['status']}")
    print(f"Evidence: {result['paths']['evidence']}")
    print(f"Result: {result['paths']['result']}")
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    run_test()

