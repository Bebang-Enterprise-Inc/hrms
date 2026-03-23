"""Merge serializer — queues and executes production merges one at a time."""
from __future__ import annotations

import asyncio
import json
import re
import time

import structlog

from .reviewer import Reviewer, get_pr_diff
from .ssm_helper import PRODUCTION_INSTANCE_ID, ssm_run
from .staging_manager import StagingManager
from .state_manager import StateManager

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
                await self._comment_on_pr(
                    pr_num,
                    "**Governor: Merge Conflict**\n\n"
                    "This PR has conflicts with production and cannot be auto-rebased.\n\n"
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

        # Step 3: Trigger production deploy
        deploy_success = await self._trigger_deploy()
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

        # Step 6: Vercel cache-bust redeploy (my.bebang.ph)
        await self._vercel_redeploy(pr_num)

        # Step 7: Post-merge cleanup
        await self._post_merge_cleanup(pr)

        logger.info("merge_cycle_complete", pr=pr_num)

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

    async def _trigger_deploy(self) -> bool:
        """Trigger production deploy via GitHub Actions.

        HARD BLOCKER: --ref production is MANDATORY.
        """
        logger.info("triggering_deploy")

        proc = await asyncio.create_subprocess_exec(
            "gh", "workflow", "run", "build-and-deploy.yml",
            "--repo", REPO,
            "--ref", "production",  # MANDATORY: guard job rejects non-production refs
            "-f", "no_cache=true",
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
        """Handle failed deploy: halt queue, display rollback commands."""
        state = self.state_mgr.state
        state.paused = True
        self.state_mgr.save()

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
