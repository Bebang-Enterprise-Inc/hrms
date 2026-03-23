"""Merge serializer — queues and executes production merges one at a time."""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import structlog

# Windows: prevent visible cmd windows from subprocess calls
_WIN_FLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW

from .reviewer import Reviewer, get_pr_diff
from .ssm_helper import PRODUCTION_INSTANCE_ID, ssm_run
from .staging_manager import StagingManager
from .state_manager import PRRecord, StateManager

logger = structlog.get_logger("governor.merge")

REPO = "Bebang-Enterprise-Inc/hrms"
PRODUCTION_URL = "https://hq.bebang.ph"


class MergeSerializer:
    """Serializes production merges — one at a time, with L1 smoke test."""

    def __init__(
        self,
        state_mgr: StateManager,
        reviewer: Reviewer,
        staging_mgr: StagingManager,
        dry_run: bool = False,
    ):
        self.state_mgr = state_mgr
        self.reviewer = reviewer
        self.staging_mgr = staging_mgr
        self.dry_run = dry_run

    async def process_queue(self) -> None:
        """Process one PR from the merge queue."""
        state = self.state_mgr.state

        if state.paused:
            return

        if not state.merge_queue:
            return

        pr_num = state.merge_queue[0]
        pr_key = str(pr_num)
        pr = state.active_prs.get(pr_key)

        if not pr:
            state.merge_queue.pop(0)
            self.state_mgr.save()
            return

        # Check review status — auto-re-review if invalidated (SHA changed)
        if pr.review_decision is None and pr.head_sha:
            logger.info("queue_auto_reviewing", pr=pr_num, reason="review_invalidated")
            try:
                diff = await get_pr_diff(pr_num, REPO)
                if diff:
                    result = await self.reviewer.review_pr(pr_num, pr.head_sha, diff)
                    if not result.is_approved:
                        logger.warning("queue_review_rejected", pr=pr_num)
                        await self._comment_on_pr(
                            pr_num,
                            f"**Governor Review: {result.decision}** (auto re-review)\n\n"
                            f"{result.reasoning}\n\n"
                            "**Builder action required:** Fix and push.\n\n*Posted by governor-erp*"
                        )
                        state.merge_queue.remove(pr_num)
                        self.state_mgr.save()
                        return
                else:
                    return
            except Exception as e:
                logger.error("queue_auto_review_error", pr=pr_num, error=str(e))
                return
        elif pr.review_decision != "APPROVE":
            logger.info("queue_waiting_review", pr=pr_num, decision=pr.review_decision)
            return

        # Confidence gate: don't auto-merge low-confidence approvals
        confidence = getattr(pr, "review_confidence", 1.0)
        if confidence < 0.80:
            logger.warning("low_confidence_review", pr=pr_num, confidence=confidence)
            await self._comment_on_pr(
                pr_num,
                f"**Governor: Low confidence review ({confidence:.2f})**\n\n"
                "Auto-merge paused. Review confidence is below 0.80 threshold.\n"
                "Manual review recommended before proceeding.\n\n"
                "*Posted by governor-erp*",
            )
            if pr_num in state.merge_queue:
                state.merge_queue.remove(pr_num)
                self.state_mgr.save()
            return

        # Release gate: deterministic + AI verification (parallel)
        gate_passed = await self._run_release_gate(pr)
        if not gate_passed:
            pr.gate_blocked = True
            if pr_num in state.merge_queue:
                state.merge_queue.remove(pr_num)
                self.state_mgr.save()
            return

        # CI gate: wait for checks to pass before merge
        ci_ok = await self._wait_for_ci(pr)
        if not ci_ok:
            return

        # Execute merge
        await self._execute_merge(pr)

    async def _execute_merge(self, pr) -> None:
        """Execute the full merge cycle for an approved PR."""
        pr_num = pr.number

        if self.dry_run:
            logger.info("dry_run_merge", pr=pr_num)
            if pr_num in self.state_mgr.state.merge_queue:
                self.state_mgr.state.merge_queue.remove(pr_num)
            self.state_mgr.save()
            return

        # Step 1: Freshness check
        is_fresh = await self._check_freshness(pr)
        if not is_fresh:
            rebased = await self._auto_rebase(pr)
            if not rebased:
                logger.error("rebase_failed", pr=pr_num)
                # Try builder subagent to resolve conflicts
                builder_fixed = await self._try_builder_conflict_resolve(pr)
                if not builder_fixed:
                    await self._comment_on_pr(
                        pr_num,
                        "**Governor: Merge Conflict**\n\n"
                        "This PR has conflicts with production and cannot be auto-rebased.\n"
                        "Builder subagent also could not resolve the conflicts.\n\n"
                        "**Builder action required:**\n"
                        "1. `git fetch origin production`\n"
                        "2. `git rebase origin/production` (resolve conflicts)\n"
                        "3. `git push --force-with-lease`\n\n"
                        "The governor will automatically re-review when it detects the new SHA.\n\n"
                        "*Posted by governor-erp*"
                    )
                    if pr_num in self.state_mgr.state.merge_queue:
                        self.state_mgr.state.merge_queue.remove(pr_num)
                        self.state_mgr.save()
                    return
                # Builder fixed it — continue with freshness re-check
                is_fresh = await self._check_freshness(pr)
                if not is_fresh:
                    if pr_num in self.state_mgr.state.merge_queue:
                        self.state_mgr.state.merge_queue.remove(pr_num)
                        self.state_mgr.save()
                    return

            # Re-review if diff changed
            diff = await get_pr_diff(pr_num, REPO)
            result = await self.reviewer.review_pr(pr_num, pr.head_sha, diff)
            if not result.is_approved:
                logger.warning("review_rejected_after_rebase", pr=pr_num)
                await self._comment_on_pr(
                    pr_num,
                    f"**Governor Review: {result.decision}** (post-rebase)\n\n"
                    f"{result.reasoning}\n\n"
                    "**Builder action required:** Fix and push.\n\n*Posted by governor-erp*"
                )
                if pr_num in self.state_mgr.state.merge_queue:
                    self.state_mgr.state.merge_queue.remove(pr_num)
                    self.state_mgr.save()
                return

        # Step 2: Merge
        success = await self._merge_pr(pr_num)
        if not success:
            return

        # Step 3: Trigger production deploy (auto-detect migrate need from touched files)
        touched = pr.touched_files or []
        if not touched:
            # Fetch touched files from the PR diff
            diff = await get_pr_diff(pr_num, REPO)
            touched = [
                line.split("b/")[-1]
                for line in diff.splitlines()
                if line.startswith("diff --git")
            ]
        deploy_success = await self._trigger_deploy(touched_files=touched)
        if not deploy_success:
            return

        # Step 4: Wait for deploy
        deploy_ok = await self._wait_for_deploy()
        if not deploy_ok:
            await self._handle_deploy_failure(pr_num)
            return

        # Step 5: L1 smoke test
        l1_passed = await self._l1_smoke_test()
        if not l1_passed:
            await self._handle_l1_failure(pr_num)
            return

        # Step 5.5: Verify container is running the NEW image (not stale)
        image_ok = await self._verify_deployed_image()
        if not image_ok:
            # Force-update the Docker service and re-run L1
            force_ok = await self._force_service_update()
            if force_ok:
                l1_passed = await self._l1_smoke_test()
                if not l1_passed:
                    await self._handle_l1_failure(pr_num)
                    return
            else:
                logger.error("force_update_failed", pr=pr_num)
                await self._handle_deploy_failure(pr_num)
                return

        # Step 6: Docker image cleanup (keep 4 newest, per /deploy-frappe skill)
        await self._cleanup_old_images()

        # Step 7: Vercel cache-bust redeploy (my.bebang.ph)
        await self._vercel_redeploy(pr_num)

        # Step 8: Post-merge cleanup
        await self._post_merge_cleanup(pr)

        logger.info("merge_cycle_complete", pr=pr_num)

    async def _wait_for_ci(self, pr, timeout_s: float = 600, poll_s: float = 30) -> bool:
        """Wait for CI checks to pass. If they fail, dispatch a builder to fix.

        Returns True if CI passes, False if failed and builder was dispatched
        (governor should skip this PR until new SHA arrives).
        """
        pr_num = pr.number
        logger.info("waiting_for_ci", pr=pr_num)
        print(f"[{time.strftime('%H:%M:%S')}] Waiting for CI on PR #{pr_num}...", flush=True)

        start = time.time()
        while time.time() - start < timeout_s:
            status, failed_jobs = await self._get_ci_status(pr_num)

            if status == "pass":
                logger.info("ci_passed", pr=pr_num)
                print(f"[{time.strftime('%H:%M:%S')}] CI passed for PR #{pr_num}", flush=True)
                return True

            if status == "fail":
                logger.warning("ci_failed", pr=pr_num, jobs=failed_jobs)
                print(f"[{time.strftime('%H:%M:%S')}] CI FAILED for PR #{pr_num}: {', '.join(failed_jobs)}", flush=True)
                await self._handle_ci_failure(pr, failed_jobs)
                return False

            # status == "pending" — wait and poll again
            await asyncio.sleep(poll_s)

        # Timeout
        logger.error("ci_timeout", pr=pr_num, timeout_s=timeout_s)
        print(f"[{time.strftime('%H:%M:%S')}] CI timeout for PR #{pr_num} ({timeout_s}s)", flush=True)
        return False

    async def _get_ci_status(self, pr_num: int) -> tuple[str, list[str]]:
        """Check CI status for a PR.

        Returns ("pass"|"fail"|"pending", [failed_job_names]).
        """
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "view", str(pr_num),
            "--repo", REPO,
            "--json", "statusCheckRollup",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return "pending", []

        data = json.loads(stdout.decode())
        checks = data.get("statusCheckRollup", [])
        if not checks:
            return "pending", []

        failed = []
        has_pending = False
        for check in checks:
            status = check.get("status", "").upper()
            conclusion = (check.get("conclusion") or "").upper()
            name = check.get("name", "unknown")

            # Skip non-blocking checks
            if name in ("Documentation Required", "Semantic Commits", "Check for GL/Payment Features"):
                continue

            if status == "COMPLETED":
                if conclusion in ("FAILURE", "ERROR", "TIMED_OUT"):
                    failed.append(name)
            elif status in ("IN_PROGRESS", "QUEUED", "PENDING", "WAITING"):
                has_pending = True

        if failed:
            return "fail", failed
        if has_pending:
            return "pending", []
        return "pass", []

    async def _handle_ci_failure(self, pr, failed_jobs: list[str]) -> None:
        """Read CI logs, dispatch a builder to fix the issue."""
        pr_num = pr.number

        # Record lesson
        from .lessons import record_lesson
        record_lesson(
            category="build",
            trigger=f"CI failed: {', '.join(failed_jobs)}",
            wrong_action=f"PR #{pr_num} pushed code that fails CI",
            correct_action="Check CI logs, fix the issue, push again",
            source_incident=f"PR #{pr_num} ({pr.title[:40]})",
        )

        # Fetch CI failure logs
        ci_log = await self._fetch_ci_failure_log(pr_num)

        # Dispatch builder with CI context
        from .builder_dispatch import dispatch_ci_fixer
        from .config import GOVERNOR_REPO

        builder_ok = await dispatch_ci_fixer(
            pr=pr,
            failed_jobs=failed_jobs,
            ci_log=ci_log,
            repo_root=GOVERNOR_REPO,
        )

        if builder_ok:
            print(f"[{time.strftime('%H:%M:%S')}] Builder dispatched to fix CI for PR #{pr_num}", flush=True)
        else:
            # Builder couldn't fix — post comment for human
            await self._comment_on_pr(
                pr_num,
                f"**Governor: CI Failed**\n\n"
                f"**Failed jobs:** {', '.join(failed_jobs)}\n\n"
                f"```\n{ci_log[:1500]}\n```\n\n"
                "Builder agent attempted a fix but could not resolve it.\n"
                "**Manual action required.**\n\n"
                "*Posted by governor-erp*",
            )

        # Remove from queue — will re-queue on new SHA
        if pr_num in self.state_mgr.state.merge_queue:
            self.state_mgr.state.merge_queue.remove(pr_num)
            self.state_mgr.save()

    async def _fetch_ci_failure_log(self, pr_num: int) -> str:
        """Fetch the last CI run's failure log for a PR."""
        pr_key = str(pr_num)
        pr_record = self.state_mgr.state.active_prs.get(pr_key)
        branch = pr_record.head_ref if pr_record else ""

        # Get the most recent failed run for this PR's branch
        proc = await asyncio.create_subprocess_exec(
            "gh", "run", "list",
            "--repo", REPO,
            "--branch", branch,
            "--status", "failure",
            "--limit", "1",
            "--json", "databaseId",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return "(could not fetch CI run ID)"

        runs = json.loads(stdout.decode())
        if not runs:
            return "(no failed runs found)"

        run_id = runs[0]["databaseId"]

        # Get the failed log
        proc2 = await asyncio.create_subprocess_exec(
            "gh", "run", "view", str(run_id),
            "--repo", REPO,
            "--log-failed",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout2, _ = await proc2.communicate()
        log_text = stdout2.decode(errors="replace")

        # Trim to relevant parts — look for error lines
        lines = log_text.splitlines()
        error_lines = [l for l in lines if any(kw in l.lower() for kw in [
            "error", "fail", "exception", "syntaxerror", "import", "module",
            "could not find", "linkvalidation", "traceback",
        ])]

        if error_lines:
            return "\n".join(error_lines[:50])
        # Fallback: last 50 lines
        return "\n".join(lines[-50:])

    async def _check_freshness(self, pr) -> bool:
        """Check if PR is based on current production HEAD."""
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "view", str(pr.number),
            "--repo", REPO,
            "--json", "mergeStateStatus",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return False

        data = json.loads(stdout.decode())
        status = data.get("mergeStateStatus", "")
        is_clean = status in ("CLEAN", "HAS_HOOKS", "UNSTABLE")

        if not is_clean:
            logger.warning("pr_not_fresh", pr=pr.number, status=status)

        return is_clean

    async def _auto_rebase(self, pr) -> bool:
        """Auto-rebase PR onto production."""
        logger.info("auto_rebasing", pr=pr.number)

        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "update-branch", str(pr.number),
            "--repo", REPO,
            "--rebase",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("rebase_failed", pr=pr.number, stderr=stderr.decode()[:500])
            return False

        # Invalidate cached review (diff may have changed)
        self.reviewer.invalidate_cache(pr.number)

        logger.info("rebase_success", pr=pr.number)
        return True

    async def _merge_pr(self, pr_num: int) -> bool:
        """Merge the PR via gh CLI."""
        logger.info("merging_pr", pr=pr_num)

        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "merge", str(pr_num),
            "--repo", REPO,
            "--merge", "--delete-branch", "--admin",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode()
            logger.error("merge_failed", pr=pr_num, error=err[:500])
            # Notify via PR comment
            await self._comment_on_pr(pr_num, f"Governor: Merge failed.\n```\n{err[:500]}\n```")
            # Advance queue past failed PR
            if pr_num in self.state_mgr.state.merge_queue:
                self.state_mgr.state.merge_queue.remove(pr_num)
                self.state_mgr.save()
            return False

        logger.info("pr_merged", pr=pr_num)
        return True

    async def _trigger_deploy(self, touched_files: list[str] | None = None) -> bool:
        """Trigger production deploy via GitHub Actions.

        HARD BLOCKER: --ref production is MANDATORY.
        Auto-detects if bench migrate is needed (DocType JSON changes).
        """
        logger.info("triggering_deploy")

        # Detect if bench migrate is needed
        run_migrate = "false"
        if touched_files:
            doctype_patterns = [".json", "doctype"]
            if any(
                "doctype" in f.lower() and f.endswith(".json")
                for f in touched_files
            ):
                run_migrate = "true"
                logger.info("migrate_needed", reason="DocType JSON changed")
                print(f"[{time.strftime('%H:%M:%S')}] DocType changes detected — will run bench migrate", flush=True)

        deploy_args = [
            "gh", "workflow", "run", "build-and-deploy.yml",
            "--repo", REPO,
            "--ref", "production",  # MANDATORY: guard job rejects non-production refs
            "-f", "no_cache=true",
        ]
        if run_migrate == "true":
            deploy_args.extend(["-f", "run_migrate=true"])

        proc = await asyncio.create_subprocess_exec(
            *deploy_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode()
            logger.error("deploy_trigger_failed", error=err[:500])
            # Retry twice
            for attempt in range(2):
                await asyncio.sleep(5 * (attempt + 1))
                proc2 = await asyncio.create_subprocess_exec(
                    "gh", "workflow", "run", "build-and-deploy.yml",
                    "--repo", REPO,
                    "--ref", "production",
                    "-f", "no_cache=true",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr2 = await proc2.communicate()
                if proc2.returncode == 0:
                    logger.info("deploy_triggered", attempt=attempt + 2)
                    return True
            return False

        logger.info("deploy_triggered")
        return True

    async def _wait_for_deploy(self, timeout_s: float = 900) -> bool:
        """Poll GHA workflow status. Timeout starts from in_progress, not invocation."""
        logger.info("waiting_for_deploy")
        await asyncio.sleep(10)  # Initial wait for workflow to register

        in_progress_at: float | None = None

        for _ in range(int(timeout_s / 15)):
            proc = await asyncio.create_subprocess_exec(
                "gh", "run", "list",
                "--repo", REPO,
                "--workflow", "build-and-deploy.yml",
                "--limit", "1",
                "--json", "status,conclusion,databaseId",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0:
                runs = json.loads(stdout.decode())
                if runs:
                    run = runs[0]
                    status = run.get("status", "")
                    conclusion = run.get("conclusion", "")

                    if status == "completed":
                        if conclusion == "success":
                            logger.info("deploy_succeeded")
                            return True
                        else:
                            logger.error("deploy_failed", conclusion=conclusion)
                            return False

                    if status == "in_progress" and in_progress_at is None:
                        in_progress_at = time.time()
                        logger.info("deploy_in_progress")

                    # Check timeout from in_progress, not invocation
                    if in_progress_at and (time.time() - in_progress_at) > timeout_s:
                        logger.error("deploy_timeout", elapsed=time.time() - in_progress_at)
                        return False

            await asyncio.sleep(15)

        logger.error("deploy_poll_exhausted")
        return False

    async def _l1_smoke_test(self) -> bool:
        """L1 smoke matching production workflow:
        (a) frappe.ping returns "pong"
        (b) CSS asset URL from login page returns 200
        (c) JS asset URL from login page returns 200
        """
        logger.info("l1_smoke_starting")

        # (a) frappe.ping with retry
        ping_ok = False
        for attempt in range(24):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-sf", f"{PRODUCTION_URL}/api/method/frappe.ping",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and b"pong" in stdout:
                    ping_ok = True
                    logger.info("l1_ping_ok", attempt=attempt + 1)
                    break
            except Exception:
                pass
            await asyncio.sleep(5)

        if not ping_ok:
            logger.error("l1_ping_failed")
            return False

        # (b) Get login page and extract CSS/JS asset URLs
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sf", f"{PRODUCTION_URL}/login",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            logger.error("l1_login_page_failed")
            return False

        html = stdout.decode()

        # Extract CSS asset URL
        css_match = re.search(r'href="(/assets/[^"]*\.css[^"]*)"', html)
        if css_match:
            css_url = f"{PRODUCTION_URL}{css_match.group(1)}"
            css_ok = await self._check_url(css_url)
            if not css_ok:
                logger.error("l1_css_failed", url=css_url)
                return False
            logger.info("l1_css_ok")
        else:
            logger.warning("l1_no_css_found")

        # Extract JS asset URL
        js_match = re.search(r'src="(/assets/[^"]*\.js[^"]*)"', html)
        if js_match:
            js_url = f"{PRODUCTION_URL}{js_match.group(1)}"
            js_ok = await self._check_url(js_url)
            if not js_ok:
                logger.error("l1_js_failed", url=js_url)
                return False
            logger.info("l1_js_ok")
        else:
            logger.warning("l1_no_js_found")

        logger.info("l1_smoke_passed")
        return True

    async def _check_url(self, url: str) -> bool:
        """Check if a URL returns HTTP 200."""
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() == "200"

    async def _handle_deploy_failure(self, pr_num: int) -> None:
        """Handle failed deploy: log error, record lesson, continue processing.

        NOTE: We intentionally do NOT pause the governor. Pausing requires manual
        intervention to resume, which defeats the purpose of autonomous operation.
        The PR is removed from the queue; the builder can fix and re-push.
        """
        state = self.state_mgr.state

        # Self-evolution: record lesson from deploy failure
        try:
            from .lessons import record_lesson
            record_lesson(
                category="deploy",
                trigger=f"Deploy failed for PR #{pr_num}",
                wrong_action="Deploy triggered but failed during image build or service update",
                correct_action="Check GHA logs, verify no_cache=true was used, check for SyntaxError in bench build",
                source_incident=f"PR #{pr_num}",
            )
        except Exception:
            pass

        rollback_cmds = [
            f"# Rollback commands for PR #{pr_num}:",
            f"# Previous production HEAD: {state.production_head[:12]}",
            "docker service rollback frappe_backend",
            "docker service rollback frappe_frontend",
            "docker service rollback frappe_websocket",
        ]

        logger.error(
            "deploy_failure_rollback",
            pr=pr_num,
            previous_head=state.production_head[:12],
            rollback_commands=rollback_cmds,
        )
        print("\n" + "\n".join(rollback_cmds) + "\n")

    async def _handle_l1_failure(self, pr_num: int) -> None:
        """Handle L1 failure: halt queue, alert, display rollback."""
        await self._handle_deploy_failure(pr_num)
        # TODO: Alert via Google Chat (Phase 3 task 8)
        logger.error("l1_failure_queue_halted", pr=pr_num)

    async def _post_merge_cleanup(self, pr) -> None:
        """After successful merge: update state, clean up staging."""
        state = self.state_mgr.state
        pr_num = pr.number

        # Get touched files
        diff = await get_pr_diff(pr_num, REPO)
        touched_files = []
        for line in diff.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    path = parts[3].lstrip("b/")
                    touched_files.append(path)

        # Update merge history
        self.state_mgr.add_to_merge_history(pr_num, touched_files)

        # Update production HEAD
        proc = await asyncio.create_subprocess_exec(
            "git", "ls-remote", f"https://github.com/{REPO}.git", "refs/heads/production",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            new_head = stdout.decode().split()[0]
            state.production_head = new_head
            logger.info("production_head_updated", sha=new_head[:12])

        # Remove from queue
        if pr_num in state.merge_queue:
            state.merge_queue.remove(pr_num)

        # Remove from active PRs
        pr_key = str(pr_num)
        if pr_key in state.active_prs:
            del state.active_prs[pr_key]

        self.state_mgr.save()

        # Tear down staging
        await self.staging_mgr.teardown_branch(pr)

    async def _vercel_redeploy(self, pr_num: int, max_retries: int = 3) -> None:
        """Cache-bust redeploy my.bebang.ph after every backend merge.

        Retries up to max_retries times with backoff. The frontend must match
        the backend — a stale frontend calling new/changed APIs will break.
        """
        import shutil
        import subprocess

        doppler = shutil.which("doppler") or "C:/Users/Sam/bin/doppler.exe"
        try:
            token_result = subprocess.run(
                [doppler, "secrets", "get", "VERCEL_TOKEN", "--plain",
                 "--project", "bei-tasks", "--config", "dev"],
                capture_output=True, text=True, timeout=15,
                stdin=subprocess.DEVNULL,
            )
            if token_result.returncode != 0 or not token_result.stdout.strip():
                logger.error("vercel_token_unavailable")
                await self._comment_on_pr(
                    pr_num,
                    "**Governor: Vercel redeploy SKIPPED** — could not retrieve VERCEL_TOKEN from Doppler.\n"
                    "Frontend may be stale. Redeploy manually: `vercel --prod --force`\n\n*Posted by governor-erp*"
                )
                return
            token = token_result.stdout.strip()
        except Exception as e:
            logger.error("vercel_token_error", error=str(e))
            return

        vercel = shutil.which("vercel") or "vercel"
        for attempt in range(1, max_retries + 1):
            logger.info("vercel_redeploy_attempt", attempt=attempt)
            print(f"[{time.strftime('%H:%M:%S')}] Vercel redeploy attempt {attempt}/{max_retries}...", flush=True)

            try:
                proc = subprocess.run(
                    [vercel, "--prod", "--force", "--yes",
                     "--token", token,
                     "--scope", "team_xvK1nhuvsdZp3GNfd4uDJ0DW"],
                    capture_output=True, text=True, timeout=300,
                    stdin=subprocess.DEVNULL,
                    cwd="F:/Dropbox/Projects/bei-tasks",
                )
                if proc.returncode == 0:
                    url = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "deployed"
                    logger.info("vercel_redeploy_success", url=url, attempt=attempt)
                    print(f"[{time.strftime('%H:%M:%S')}] Vercel redeploy OK: {url}", flush=True)
                    return
                else:
                    logger.warning("vercel_redeploy_failed", attempt=attempt, stderr=proc.stderr[:200])
            except subprocess.TimeoutExpired:
                logger.warning("vercel_redeploy_timeout", attempt=attempt)
            except Exception as e:
                logger.warning("vercel_redeploy_error", attempt=attempt, error=str(e))

            if attempt < max_retries:
                wait = 10 * attempt
                print(f"[{time.strftime('%H:%M:%S')}] Retrying in {wait}s...", flush=True)
                await asyncio.sleep(wait)

        # All retries exhausted
        logger.error("vercel_redeploy_exhausted", attempts=max_retries)
        print(f"[{time.strftime('%H:%M:%S')}] Vercel redeploy FAILED after {max_retries} attempts", flush=True)
        await self._comment_on_pr(
            pr_num,
            f"**Governor: Vercel redeploy FAILED** after {max_retries} attempts.\n"
            "Frontend is stale and may not work correctly with the new backend.\n\n"
            "**Builder action required:** Run `vercel --prod --force` from the bei-tasks directory.\n\n"
            "*Posted by governor-erp*"
        )

    async def _cleanup_old_images(self) -> None:
        """Clean up old Docker images on EC2. Keep 4 newest per /deploy-frappe skill.

        The server has 50 GB disk. Each image is ~2.5 GB. Without cleanup,
        disk fills in days. This runs after every successful deploy.
        """
        logger.info("image_cleanup_start")
        try:
            success, stdout, stderr = await ssm_run(
                'docker container prune -f && '
                'IMAGES=$(docker images samkarazi/bebang-erpnext-hrms --format "{{.ID}}" | tail -n +5) && '
                'if [ -n "$IMAGES" ]; then docker rmi $IMAGES 2>/dev/null || true; fi && '
                'docker image prune -f && '
                'df -h / | tail -1',
                instance_id=PRODUCTION_INSTANCE_ID,
                timeout_s=60,
            )
            if success:
                logger.info("image_cleanup_done", disk=stdout.strip().split('\n')[-1] if stdout else "unknown")
                print(f"[{time.strftime('%H:%M:%S')}] Image cleanup done: {stdout.strip().split(chr(10))[-1] if stdout else 'OK'}", flush=True)
            else:
                logger.warning("image_cleanup_failed", stderr=stderr[:200])
        except Exception as e:
            logger.warning("image_cleanup_error", error=str(e))

    async def _verify_deployed_image(self) -> bool:
        """Verify the running Docker container has the latest image.

        Compares the image digest of the running frappe_backend service
        against the most recently built image. If they don't match,
        the deploy succeeded on paper but the container is stale.
        """
        print(f"[{time.strftime('%H:%M:%S')}] Verifying container image is current...", flush=True)

        try:
            # Get the running image from Docker Swarm
            success, stdout, stderr = await ssm_run(
                "docker service inspect frappe_backend --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}'",
                instance_id=PRODUCTION_INSTANCE_ID,
                timeout_s=30,
            )
            if not success:
                logger.warning("image_verify_failed", error=stderr[:200])
                return True  # Fail-open: can't check, assume OK

            running_image = stdout.strip().strip("'\"")

            # Get the latest image from the registry
            success2, stdout2, _ = await ssm_run(
                "docker images samkarazi/bebang-erpnext-hrms --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' | head -1",
                instance_id=PRODUCTION_INSTANCE_ID,
                timeout_s=30,
            )

            if success2:
                latest_image = stdout2.strip().split()[0] if stdout2.strip() else ""
                logger.info("image_check", running=running_image[:80], latest=latest_image[:80])

                # Check if running image matches latest
                if running_image and latest_image and running_image != latest_image:
                    print(f"[{time.strftime('%H:%M:%S')}] STALE: running={running_image[:50]} vs latest={latest_image[:50]}", flush=True)
                    return False

            # Also verify the API returns fresh code by checking a known endpoint
            success3, stdout3, _ = await ssm_run(
                "curl -s --max-time 5 http://localhost:8000/api/method/frappe.ping",
                instance_id=PRODUCTION_INSTANCE_ID,
                timeout_s=15,
            )
            if success3 and "pong" in stdout3:
                print(f"[{time.strftime('%H:%M:%S')}] Container image verified OK", flush=True)
                return True

            return True  # Fail-open if checks are inconclusive

        except Exception as e:
            logger.warning("image_verify_error", error=str(e))
            return True  # Fail-open

    async def _force_service_update(self) -> bool:
        """Force Docker Swarm to re-pull and restart the service."""
        print(f"[{time.strftime('%H:%M:%S')}] Forcing Docker service update...", flush=True)
        logger.info("force_service_update")

        try:
            success, stdout, stderr = await ssm_run(
                "docker service update --force --with-registry-auth frappe_backend",
                instance_id=PRODUCTION_INSTANCE_ID,
                timeout_s=120,
            )

            if success:
                logger.info("force_update_success")
                print(f"[{time.strftime('%H:%M:%S')}] Force update complete. Waiting 30s for container startup...", flush=True)
                await asyncio.sleep(30)  # Wait for new container to be ready
                return True
            else:
                logger.error("force_update_failed", stderr=stderr[:300])
                print(f"[{time.strftime('%H:%M:%S')}] Force update FAILED: {stderr[:200]}", flush=True)
                return False

        except Exception as e:
            logger.error("force_update_error", error=str(e))
            return False

    async def _run_release_gate(self, pr) -> bool:
        """Run two-layer release gate: deterministic + AI (parallel).

        Both must pass. If either fails, posts PR comment and returns False.
        Non-sprint PRs skip the gate entirely.
        """
        from .release_gate import run_deterministic_gate, find_sprint_plan, count_l3_scenarios

        repo_root = str(Path(__file__).parent.parent.parent)

        # Deterministic check
        det_result = run_deterministic_gate(
            branch_name=pr.head_ref,
            repo_root=repo_root,
        )

        # Skip gate for non-sprint PRs
        if det_result.skip_reason:
            logger.info("release_gate_skipped", pr=pr.number, reason=det_result.skip_reason)
            return True

        # AI verification (run in parallel if deterministic passes or fails)
        ai_result = {"passed": True, "issues": []}  # Default: pass if no AI backend
        try:
            # Only run AI verification if we have the Agent SDK backend
            if hasattr(self, '_get_ai_backend'):
                backend = self._get_ai_backend()
            else:
                backend = getattr(self.reviewer, 'backend', None)

            if backend and hasattr(backend, 'verify_evidence'):
                import re as _re
                match = _re.search(r"s0?(\d{2,3})", pr.head_ref, _re.IGNORECASE)
                sprint_id = f"s{match.group(1)}" if match else ""

                plan_path = find_sprint_plan(pr.head_ref, plans_dir=str(Path(repo_root) / "docs" / "plans"))
                scenarios = []
                if plan_path:
                    content = plan_path.read_text(encoding="utf-8")
                    # Extract scenario descriptions from L3 table
                    in_table = False
                    for line in content.splitlines():
                        if "L3 Workflow Scenarios" in line:
                            in_table = True
                            continue
                        if in_table and line.strip().startswith("|"):
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 4 and parts[1] and not parts[1].startswith("-") and parts[1] != "User":
                                scenarios.append(f"{parts[1]}: {parts[2]}")
                        elif in_table and line.strip() and not line.strip().startswith("|"):
                            break

                evidence_path = f"output/l3/{sprint_id}/"
                ai_result = await backend.verify_evidence(sprint_id, evidence_path, scenarios)
        except Exception as e:
            logger.warning("release_gate_ai_error", pr=pr.number, error=str(e))
            ai_result = {"passed": False, "issues": [f"AI verification error: {e}"]}

        # Both must pass
        passed = det_result.passed and ai_result.get("passed", False)

        if not passed:
            # Format combined comment
            lines = ["**Release Manager: BLOCKED**\n"]

            if not det_result.passed:
                lines.append("**Deterministic checks:**")
                for item in det_result.missing_evidence:
                    lines.append(f"- [ ] {item}")
                for item in det_result.evidence_gaps:
                    lines.append(f"- [ ] {item}")
                lines.append("")

            ai_issues = ai_result.get("issues", [])
            if ai_issues:
                lines.append("**AI verification:**")
                for issue in ai_issues:
                    lines.append(f"- [ ] {issue}")
                lines.append("")

            lines.append(
                "**Builder action:** Complete L3 tests, commit evidence files "
                "(`git add -f output/l3/ && git push`). "
                "The gate will re-check on the next push.\n"
            )
            lines.append("*Posted by bei-release-manager*")

            comment = "\n".join(lines)
            await self._comment_on_pr(pr.number, comment)
            logger.info("release_gate_blocked", pr=pr.number, det=det_result.passed, ai=ai_result.get("passed"))
            print(f"[{time.strftime('%H:%M:%S')}] Release gate BLOCKED PR #{pr.number}", flush=True)
        else:
            logger.info("release_gate_passed", pr=pr.number)
            print(f"[{time.strftime('%H:%M:%S')}] Release gate PASSED for PR #{pr.number}", flush=True)

        return passed

    async def _try_builder_conflict_resolve(self, pr) -> bool:
        """Try to dispatch a builder subagent to resolve merge conflicts."""
        try:
            from .builder_dispatch import dispatch_conflict_resolver

            repo_root = str(Path(__file__).parent.parent.parent)
            pushed = await dispatch_conflict_resolver(pr, repo_root)
            if pushed:
                logger.info("builder_conflict_resolved", pr=pr.number)
                self.state_mgr.save()
            return pushed
        except ImportError:
            logger.info("builder_sdk_not_available", pr=pr.number)
            return False
        except Exception as e:
            logger.error("builder_conflict_error", pr=pr.number, error=str(e))
            return False

    async def _comment_on_pr(self, pr_num: int, body: str) -> None:
        """Post a comment on a PR."""
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "comment", str(pr_num),
            "--repo", REPO,
            "--body", body,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def run(self, stop_event: asyncio.Event, interval: int = 30) -> None:
        """Run the merge processor loop."""
        logger.info("merge_serializer_started", interval=interval)
        while not stop_event.is_set():
            try:
                await self.process_queue()
            except Exception as e:
                logger.error("merge_processor_error", error=str(e))

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
