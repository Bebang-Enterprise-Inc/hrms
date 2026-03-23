"""Benchmark harness — runs both AI backends on the same frozen input."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog

from .ai_backend_base import ReviewBackend, ReviewResult

logger = structlog.get_logger("governor.benchmark")


@dataclass
class BenchmarkSnapshot:
    """Frozen input for reproducible benchmarking."""
    pr_number: int
    diff_text: str
    merge_context: dict[str, Any]
    input_sha: str = ""

    def __post_init__(self):
        if not self.input_sha:
            content = json.dumps({
                "pr": self.pr_number,
                "diff": self.diff_text,
                "context": self.merge_context,
            }, sort_keys=True)
            self.input_sha = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class BenchmarkResult:
    backend_name: str
    decision: str
    reasoning: str
    confidence: float
    latency_ms: float
    input_sha: str
    error: str | None = None


async def run_benchmark(
    snapshot: BenchmarkSnapshot,
    backends: dict[str, ReviewBackend],
    timeout_s: float = 120,
) -> list[BenchmarkResult]:
    """Run all backends on the same snapshot. Returns list of results."""
    results = []

    for name, backend in backends.items():
        start = time.monotonic()
        try:
            review = await asyncio.wait_for(
                backend.review(
                    pr_number=snapshot.pr_number,
                    diff_text=snapshot.diff_text,
                    merge_context=snapshot.merge_context,
                    timeout_s=timeout_s,
                ),
                timeout=timeout_s + 5,
            )
            elapsed = (time.monotonic() - start) * 1000
            results.append(BenchmarkResult(
                backend_name=name,
                decision=review.decision,
                reasoning=review.reasoning[:200],
                confidence=review.confidence,
                latency_ms=round(elapsed, 1),
                input_sha=snapshot.input_sha,
            ))
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            results.append(BenchmarkResult(
                backend_name=name,
                decision="ERROR",
                reasoning=str(e),
                confidence=0.0,
                latency_ms=round(elapsed, 1),
                input_sha=snapshot.input_sha,
                error=str(e),
            ))

        logger.info(
            "benchmark_run",
            backend=name,
            decision=results[-1].decision,
            latency_ms=results[-1].latency_ms,
            sha=snapshot.input_sha,
        )

    return results


def write_benchmark_report(
    results: list[list[BenchmarkResult]],
    output_path: Path,
) -> None:
    """Write a markdown benchmark report."""
    lines = [
        "# S091 Backend Benchmark Report\n",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Results\n",
        "| PR | Input SHA | Backend | Decision | Confidence | Latency (ms) | Error |",
        "|---|---|---|---|---|---|---|",
    ]

    for run_results in results:
        for r in run_results:
            lines.append(
                f"| #{r.input_sha[:8]} | {r.input_sha} | {r.backend_name} | "
                f"{r.decision} | {r.confidence:.2f} | {r.latency_ms:.0f} | "
                f"{r.error or '-'} |"
            )

    # Agreement analysis
    lines.append("\n## Agreement Analysis\n")
    agree = 0
    total = 0
    for run_results in results:
        decisions = [r.decision for r in run_results if r.decision != "ERROR"]
        if len(decisions) >= 2:
            total += 1
            if len(set(decisions)) == 1:
                agree += 1

    if total > 0:
        lines.append(f"Agreement rate: {agree}/{total} ({agree/total*100:.0f}%)\n")
    else:
        lines.append("No comparable runs available.\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("benchmark_report_written", path=str(output_path))
