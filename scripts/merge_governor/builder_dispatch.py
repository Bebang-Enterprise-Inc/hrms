"""Builder subagent dispatch — spawns Claude Agent SDK agents to fix rejected PRs and resolve conflicts."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import structlog

from .ai_backend_base import ReviewResult
from .state_manager import PRRecord

logger = structlog.get_logger("governor.builder")

MAX_DISPATCHES_PER_PR = 2
BUILDER_BUDGET_USD = 2.00
BUILDER_MAX_TURNS = 20


async def dispatch_rejection_fixer(
    pr: PRRecord,
    review_result: ReviewResult,
    repo_root: str,
) -> bool:
    """Spawn a builder subagent to fix issues found in a rejected review.

    Returns True if the builder pushed a fix (SHA will change on next poll).
    """
    if not review_result.suggested_fix and not review_result.reasoning:
        logger.info("builder_skip_no_fix", pr=pr.number)
        return False

    if pr.builder_dispatch_count >= MAX_DISPATCHES_PER_PR:
        logger.warning("builder_circuit_breaker", pr=pr.number, count=pr.builder_dispatch_count)
        return False

    pr.builder_dispatched = True
    pr.builder_dispatch_count += 1

    prompt = (
        f"You are a BEI ERP builder agent. Fix the issue below in PR #{pr.number} "
        f"on branch `{pr.head_ref}`.\n\n"
        f"**Review Decision:** {review_result.decision}\n"
        f"**Reasoning:** {review_result.reasoning}\n"
    )
    if review_result.suggested_fix:
        prompt += f"**Suggested Fix:** {review_result.suggested_fix}\n"
    if review_result.conflicting_files:
        prompt += f"**Files to check:** {', '.join(review_result.conflicting_files)}\n"
    prompt += (
        "\n**Instructions:**\n"
        "1. Read the relevant files and understand the issue\n"
        "2. Fix the code\n"
        "3. Run `git add` and `git commit` with a descriptive message\n"
        "4. Run `git push origin HEAD` to push the fix\n"
        "The governor will auto-re-review when it detects the new SHA.\n"
    )

    return await _run_builder_in_worktree(pr, prompt, repo_root, label="rejection_fix")


async def dispatch_conflict_resolver(
    pr: PRRecord,
    repo_root: str,
) -> bool:
    """Spawn a builder subagent to resolve merge conflicts.

    Returns True if the builder resolved conflicts and pushed.
    """
    if pr.builder_dispatch_count >= MAX_DISPATCHES_PER_PR:
        logger.warning("builder_circuit_breaker", pr=pr.number, count=pr.builder_dispatch_count)
        return False

    pr.builder_dispatched = True
    pr.builder_dispatch_count += 1

    prompt = (
        f"You are a BEI ERP builder agent. PR #{pr.number} on branch `{pr.head_ref}` "
        f"has merge conflicts with production.\n\n"
        f"**Instructions:**\n"
        "1. Run `git fetch origin production`\n"
        "2. Run `git rebase origin/production`\n"
        "3. Resolve any merge conflicts in the files\n"
        "4. Run `git rebase --continue` after resolving each conflict\n"
        "5. Run `git push origin HEAD --force-with-lease`\n"
        "The governor will auto-re-review when it detects the new SHA.\n"
    )

    return await _run_builder_in_worktree(pr, prompt, repo_root, label="conflict_resolve")


async def dispatch_ci_fixer(
    pr: PRRecord,
    failed_jobs: list[str],
    ci_log: str,
    repo_root: str,
) -> bool:
    """Spawn a builder subagent to fix CI failures.

    Reads the CI error log and fixes the code so CI passes.
    Returns True if the builder pushed a fix.
    """
    if pr.builder_dispatch_count >= MAX_DISPATCHES_PER_PR:
        logger.warning("builder_circuit_breaker", pr=pr.number, count=pr.builder_dispatch_count)
        return False

    pr.builder_dispatched = True
    pr.builder_dispatch_count += 1

    prompt = (
        f"You are a BEI ERP builder agent. PR #{pr.number} on branch `{pr.head_ref}` "
        f"has FAILING CI checks. Your job is to fix the code so CI passes.\n\n"
        f"**Failed jobs:** {', '.join(failed_jobs)}\n\n"
        f"**CI Error Log (key lines):**\n```\n{ci_log[:3000]}\n```\n\n"
        f"**Instructions:**\n"
        "1. Analyze the error log above to identify the root cause\n"
        "2. Read the relevant files and fix the issue\n"
        "3. Common CI failures:\n"
        "   - LinkValidationError: A DocType Link field has a `default` value referencing "
        "data that doesn't exist in CI's test database. Remove the `default` from the JSON.\n"
        "   - SyntaxError: Check for decorators on non-functions, missing imports, etc.\n"
        "   - ImportError: Missing module or wrong import path.\n"
        "   - Linter failures: Fix code style issues.\n"
        "4. Run `git add` the changed files and `git commit` with message starting with 'fix(ci):'\n"
        "5. Run `git push origin HEAD` to push the fix\n"
        "The governor will auto-re-review when it detects the new SHA.\n"
    )

    return await _run_builder_in_worktree(pr, prompt, repo_root, label="ci_fix")


async def _run_builder_in_worktree(
    pr: PRRecord,
    prompt: str,
    repo_root: str,
    label: str,
) -> bool:
    """Run a builder agent in an isolated git worktree."""
    # Ensure CLAUDECODE is unset so Agent SDK works
    os.environ.pop("CLAUDECODE", None)
    os.environ.pop("CLAUDE_CODE", None)

    worktree_path = Path(repo_root) / f".builder-worktree-{pr.number}"
    branch = pr.head_ref

    try:
        # Create worktree
        logger.info("builder_worktree_create", pr=pr.number, path=str(worktree_path))
        print(f"[{time.strftime('%H:%M:%S')}] Spawning builder for PR #{pr.number} ({label})...", flush=True)

        # Clean up stale worktree if exists
        if worktree_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=repo_root, capture_output=True, timeout=30,
                stdin=subprocess.DEVNULL,
            )

        # Create fresh worktree on the PR branch
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch],
            cwd=repo_root, capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            # Branch might not exist locally — try fetching first
            subprocess.run(
                ["git", "fetch", "origin", f"{branch}:{branch}"],
                cwd=repo_root, capture_output=True, timeout=30,
                stdin=subprocess.DEVNULL,
            )
            result = subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch],
                cwd=repo_root, capture_output=True, text=True, timeout=30,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                logger.error("builder_worktree_failed", pr=pr.number, stderr=result.stderr[:200])
                print(f"[{time.strftime('%H:%M:%S')}] Builder worktree creation failed for PR #{pr.number}", flush=True)
                return False

        # Run the Agent SDK builder in the worktree
        success = await _execute_builder_agent(pr, prompt, str(worktree_path), label)

        return success

    except Exception as e:
        logger.error("builder_dispatch_error", pr=pr.number, error=str(e))
        print(f"[{time.strftime('%H:%M:%S')}] Builder error for PR #{pr.number}: {e}", flush=True)
        return False

    finally:
        # Always clean up worktree
        try:
            if worktree_path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    cwd=repo_root, capture_output=True, timeout=30,
                    stdin=subprocess.DEVNULL,
                )
                logger.info("builder_worktree_removed", pr=pr.number)
        except Exception:
            pass


async def _execute_builder_agent(
    pr: PRRecord,
    prompt: str,
    cwd: str,
    label: str,
) -> bool:
    """Execute the builder agent via Claude Agent SDK."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
            disallowed_tools=["Agent", "NotebookEdit"],
            max_turns=BUILDER_MAX_TURNS,
            max_budget_usd=BUILDER_BUDGET_USD,
            model="sonnet",
            system_prompt=(
                "You are a BEI ERP builder agent. Your job is to fix code issues "
                "and push the fix. Work in the current directory. Be precise and minimal — "
                "fix only what's described, don't refactor unrelated code."
            ),
            cwd=cwd,
        )

        result_msg = await asyncio.wait_for(
            _run_query(prompt, options),
            timeout=300,  # 5 min max for builder
        )

        if result_msg:
            cost = getattr(result_msg, "total_cost_usd", 0.0)
            logger.info(
                "builder_complete",
                pr=pr.number,
                label=label,
                cost_usd=cost,
                result=str(result_msg.result or "")[:200],
            )
            print(f"[{time.strftime('%H:%M:%S')}] Builder for PR #{pr.number} complete (${cost:.2f})", flush=True)

            # Log cost
            _log_builder_cost(cost, f"builder_{label}_pr_{pr.number}")

            # Check if builder actually pushed (look for push-related text)
            result_text = str(result_msg.result or "").lower()
            pushed = any(word in result_text for word in ["pushed", "push origin", "push complete", "force-with-lease"])
            return pushed

        logger.warning("builder_no_result", pr=pr.number)
        return False

    except asyncio.TimeoutError:
        logger.error("builder_timeout", pr=pr.number, label=label)
        print(f"[{time.strftime('%H:%M:%S')}] Builder timed out for PR #{pr.number}", flush=True)
        return False
    except ImportError:
        logger.error("builder_sdk_not_installed")
        return False
    except Exception as e:
        logger.error("builder_agent_error", pr=pr.number, error=str(e))
        return False


async def _run_query(prompt, options):
    """Run Agent SDK query and return ResultMessage."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, query

    result_msg = None
    last_text = ""
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if hasattr(block, "text"):
                    last_text += block.text
        if isinstance(msg, ResultMessage):
            result_msg = msg

    if result_msg and not result_msg.result and last_text:
        result_msg.result = last_text

    return result_msg


def _log_builder_cost(cost_usd: float, label: str) -> None:
    """Log builder cost to the shared cost log."""
    import json

    cost_log = Path.home() / ".governor" / "logs" / "cost_log.jsonl"
    cost_log.parent.mkdir(parents=True, exist_ok=True)
    try:
        entry = {
            "timestamp": time.time(),
            "cost_usd": cost_usd,
            "label": label,
            "backend": "agent-sdk-builder",
        }
        with open(cost_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
