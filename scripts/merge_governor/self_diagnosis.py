"""Self-diagnosis monitor — auto-investigates when governor is stuck.

Background task checking pipeline every 60s. If stuck >5min, investigates
CI/GHA/production and takes auto-recovery actions.
All subprocess calls use asyncio.create_subprocess_exec (non-blocking).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from .event_bus import EventBus
    from .merge_serializer import MergeSerializer

logger = structlog.get_logger("governor.self_diagnosis")

_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0
REPO = "Bebang-Enterprise-Inc/hrms"
STUCK_THRESHOLD_S = 300
CHECK_INTERVAL_S = 60


async def self_diagnosis_loop(
    stop_event: asyncio.Event,
    merge_serializer: "MergeSerializer",
    event_bus: "EventBus | None" = None,
) -> None:
    """Background loop checking for stuck pipeline."""
    logger.info("self_diagnosis_started")
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL_S)
            break
        except asyncio.TimeoutError:
            pass

        if merge_serializer.pipeline_status == "idle":
            continue

        elapsed = time.time() - merge_serializer.pipeline_started_at
        if elapsed < STUCK_THRESHOLD_S:
            continue

        pr_num = merge_serializer.pipeline_pr
        step = merge_serializer.pipeline_step
        elapsed_min = int(elapsed / 60)
        ts = time.strftime("%H:%M:%S")

        print(f"[{ts}] SELF-DIAGNOSIS: Pipeline stuck on '{step}' for {elapsed_min}min (PR #{pr_num})", flush=True)

        if event_bus:
            event_bus.emit("governor.stuck", {"pr": pr_num, "step": step, "elapsed_s": int(elapsed)})

        diagnosis = await _investigate(pr_num, step)
        for line in diagnosis.get("findings", []):
            print(f"[{ts}]   {line}", flush=True)

        action = diagnosis.get("action", "wait")
        print(f"[{ts}]   Action: {action}", flush=True)

        if event_bus:
            event_bus.emit("governor.diagnosis", {"pr": pr_num, "action": action})

        if action != "wait" and pr_num:
            await _post_diagnosis_comment(pr_num, step, elapsed_min, diagnosis)


async def _investigate(pr_num: int | None, step: str) -> dict[str, Any]:
    findings = []
    action = "wait"

    if not pr_num:
        return {"findings": ["No PR number"], "action": action}

    if "ci" in step.lower() or "check" in step.lower():
        r = await _check_ci(pr_num)
        findings.extend(r["findings"])
        action = r.get("action", "wait")
    elif "deploy" in step.lower() or "build" in step.lower() or "gha" in step.lower():
        r = await _check_gha()
        findings.extend(r["findings"])
        action = r.get("action", "wait")
    elif "l1" in step.lower() or "ping" in step.lower() or "smoke" in step.lower():
        r = await _check_production()
        findings.extend(r["findings"])
        action = r.get("action", "wait")
    else:
        for check in [_check_ci(pr_num), _check_gha(), _check_production()]:
            r = await check
            findings.extend(r["findings"])
            if r.get("action", "wait") != "wait":
                action = r["action"]

    return {"findings": findings, "action": action}


async def _check_ci(pr_num: int) -> dict[str, Any]:
    findings = []
    action = "wait"
    output = await _run_cmd(
        "gh", "pr", "view", str(pr_num), "--repo", REPO,
        "--json", "statusCheckRollup",
        "--jq", '.statusCheckRollup[] | [.name, .status, .conclusion] | @tsv',
    )
    if not output:
        findings.append("Could not fetch CI status")
        return {"findings": findings, "action": action}
    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            name, status, conclusion = parts[0], parts[1], parts[2]
            if conclusion == "FAILURE":
                findings.append(f"CI FAILED: {name}")
                action = "ci_failed"
            elif status == "IN_PROGRESS":
                findings.append(f"CI in progress: {name}")
            else:
                findings.append(f"CI {conclusion}: {name}")
    return {"findings": findings, "action": action}


async def _check_gha() -> dict[str, Any]:
    findings = []
    action = "wait"
    output = await _run_cmd(
        "gh", "run", "list", "--repo", REPO,
        "--workflow=build-and-deploy.yml", "--limit", "1",
        "--json", "status,conclusion,databaseId",
    )
    if not output:
        findings.append("Could not fetch GHA runs")
        return {"findings": findings, "action": action}
    try:
        runs = json.loads(output)
        if runs:
            run = runs[0]
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion", "")
            run_id = run.get("databaseId", "?")
            if status == "completed" and conclusion == "failure":
                findings.append(f"GHA #{run_id}: FAILED — undetected deploy failure")
                action = "deploy_failed"
            elif status == "in_progress":
                findings.append(f"GHA #{run_id}: still building")
            elif status == "completed" and conclusion == "success":
                findings.append(f"GHA #{run_id}: success — should have been detected")
                action = "deploy_complete_undetected"
            else:
                findings.append(f"GHA #{run_id}: {status}/{conclusion}")
    except json.JSONDecodeError:
        findings.append(f"Could not parse GHA output")
    return {"findings": findings, "action": action}


async def _check_production() -> dict[str, Any]:
    findings = []
    action = "wait"
    output = await _run_cmd("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://hq.bebang.ph/api/method/ping")
    if output and output.strip() == "200":
        findings.append("Production ping: OK (200)")
    elif output:
        findings.append(f"Production ping: HTTP {output.strip()}")
        action = "production_unhealthy"
    else:
        findings.append("Production ping: failed")
        action = "production_down"
    return {"findings": findings, "action": action}


async def _post_diagnosis_comment(pr_num: int, step: str, elapsed_min: int, diagnosis: dict) -> None:
    findings_text = "\n".join(f"- {f}" for f in diagnosis.get("findings", []))
    comment = (
        f"**Governor Self-Diagnosis Report**\n\n"
        f"Pipeline stuck on \"{step}\" for {elapsed_min} minutes.\n\n"
        f"**Findings:**\n{findings_text}\n\n"
        f"**Action:** {diagnosis.get('action', 'unknown')}\n\n"
        f"*Posted by governor-erp (self-diagnosis)*"
    )
    await _run_cmd("gh", "pr", "comment", str(pr_num), "--repo", REPO, "--body", comment)


async def _run_cmd(*args: str) -> str | None:
    """Run a command asynchronously. Resolves executable path via shutil.which on Windows."""
    import shutil

    # Resolve executable to full path (asyncio.create_subprocess_exec needs it on Windows)
    exe = shutil.which(args[0])
    if not exe:
        logger.warning("self_diagnosis_cmd_not_found", cmd=args[0])
        return None
    resolved_args = (exe,) + args[1:]

    try:
        kwargs: dict[str, Any] = {"stdout": asyncio.subprocess.PIPE, "stderr": asyncio.subprocess.PIPE}
        if sys.platform == "win32":
            kwargs["creationflags"] = _WIN_FLAGS
        proc = await asyncio.create_subprocess_exec(*resolved_args, **kwargs)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0 and stdout:
            return stdout.decode("utf-8", errors="replace").strip()
    except Exception as e:
        logger.warning("self_diagnosis_cmd_failed", cmd=args[0], error=str(e))
    return None
