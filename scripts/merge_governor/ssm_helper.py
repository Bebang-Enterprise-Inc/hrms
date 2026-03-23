"""SSM helper — runs commands on EC2 via AWS SSM."""
from __future__ import annotations

import asyncio
import json

import structlog

logger = structlog.get_logger("governor.ssm")

STAGING_INSTANCE_ID = "i-0a9a6ed652533d6c4"
PRODUCTION_INSTANCE_ID = "i-026b7477d27bd46d6"


async def ssm_run(
    command: str,
    instance_id: str = STAGING_INSTANCE_ID,
    timeout_s: float = 300,
) -> tuple[bool, str, str]:
    """Run a command on EC2 via SSM. Returns (success, stdout, stderr)."""

    # Send command
    send_proc = await asyncio.create_subprocess_exec(
        "aws", "ssm", "send-command",
        "--instance-ids", instance_id,
        "--document-name", "AWS-RunShellScript",
        "--parameters", json.dumps({"commands": [command]}),
        "--output", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    send_stdout, send_stderr = await send_proc.communicate()

    if send_proc.returncode != 0:
        err = send_stderr.decode()
        logger.error("ssm_send_failed", command=command[:100], error=err)
        return False, "", err

    cmd_data = json.loads(send_stdout.decode())
    cmd_id = cmd_data["Command"]["CommandId"]
    logger.info("ssm_command_sent", command_id=cmd_id, command=command[:100])

    # Poll for completion
    elapsed = 0
    poll_interval = 3
    while elapsed < timeout_s:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        poll_proc = await asyncio.create_subprocess_exec(
            "aws", "ssm", "get-command-invocation",
            "--command-id", cmd_id,
            "--instance-id", instance_id,
            "--output", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        poll_stdout, poll_stderr = await poll_proc.communicate()

        if poll_proc.returncode != 0:
            # May not be ready yet
            if b"InvocationDoesNotExist" in poll_stderr:
                continue
            logger.warning("ssm_poll_error", error=poll_stderr.decode()[:200])
            continue

        result = json.loads(poll_stdout.decode())
        status = result.get("Status", "")

        if status in ("Success",):
            stdout = result.get("StandardOutputContent", "")
            stderr = result.get("StandardErrorContent", "")
            logger.info("ssm_command_success", command_id=cmd_id, elapsed=elapsed)
            return True, stdout, stderr

        if status in ("Failed", "Cancelled", "TimedOut"):
            stdout = result.get("StandardOutputContent", "")
            stderr = result.get("StandardErrorContent", "")
            logger.error("ssm_command_failed", command_id=cmd_id, status=status, stderr=stderr[:500])
            return False, stdout, stderr

        # Still running
        if elapsed % 30 == 0:
            logger.info("ssm_waiting", command_id=cmd_id, elapsed=elapsed, status=status)

    logger.error("ssm_timeout", command_id=cmd_id, timeout_s=timeout_s)
    return False, "", f"SSM command timed out after {timeout_s}s"
