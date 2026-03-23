"""Staging manager — orchestrates per-branch containers on staging EC2 via SSM."""
from __future__ import annotations

import asyncio

import structlog

from .port_allocator import PortAllocator
from .ssm_helper import STAGING_INSTANCE_ID, ssm_run
from .state_manager import PRRecord, StateManager

logger = structlog.get_logger("governor.staging")

# Scripts are deployed to staging EC2 at /home/ubuntu/governor-staging/
STAGING_SCRIPTS_DIR = "/home/ubuntu/governor-staging"


class StagingManager:
    """Manages per-branch staging containers on the staging EC2."""

    def __init__(self, state_mgr: StateManager, port_allocator: PortAllocator, dry_run: bool = False):
        self.state_mgr = state_mgr
        self.port_allocator = port_allocator
        self.dry_run = dry_run

    async def deploy_branch(self, pr: PRRecord, no_cache: bool = False) -> bool:
        """Deploy a branch to a staging container. Returns True on success."""
        port = self.port_allocator.get_port(pr.number)
        if port is None:
            port = self.port_allocator.allocate(pr.number)
            if port is None:
                logger.error("staging_deploy_no_port", pr=pr.number)
                return False

        pr.staging_port = port
        self.state_mgr.save()

        if self.dry_run:
            logger.info("dry_run_deploy", pr=pr.number, branch=pr.head_ref, port=port)
            return True

        no_cache_flag = "true" if no_cache else "false"
        cmd = f"bash {STAGING_SCRIPTS_DIR}/staging_deploy.sh '{pr.head_ref}' {port} {no_cache_flag}"

        logger.info("staging_deploying", pr=pr.number, branch=pr.head_ref, port=port, no_cache=no_cache)
        success, stdout, stderr = await ssm_run(cmd, timeout_s=300)

        if success:
            logger.info("staging_deployed", pr=pr.number, port=port)
        else:
            logger.error("staging_deploy_failed", pr=pr.number, stderr=stderr[:500])
            # Reclaim port on failure
            self.port_allocator.release(pr.number)
            pr.staging_port = None
            self.state_mgr.save()

        return success

    async def teardown_branch(self, pr: PRRecord) -> bool:
        """Tear down a branch's staging container. Returns True on success."""
        if self.dry_run:
            logger.info("dry_run_teardown", pr=pr.number, branch=pr.head_ref)
            self.port_allocator.release(pr.number)
            return True

        cmd = f"bash {STAGING_SCRIPTS_DIR}/staging_teardown.sh '{pr.head_ref}'"

        logger.info("staging_tearing_down", pr=pr.number, branch=pr.head_ref)
        success, stdout, stderr = await ssm_run(cmd, timeout_s=120)

        # Release port regardless (teardown is idempotent)
        self.port_allocator.release(pr.number)
        pr.staging_port = None
        self.state_mgr.save()

        if success:
            logger.info("staging_torn_down", pr=pr.number)
        else:
            logger.warning("staging_teardown_warning", pr=pr.number, stderr=stderr[:500])

        return success

    async def health_check(self, pr: PRRecord) -> bool:
        """Check if a branch's staging container is healthy."""
        port = self.port_allocator.get_port(pr.number)
        if port is None:
            return False

        if self.dry_run:
            return True

        cmd = f"bash {STAGING_SCRIPTS_DIR}/staging_health.sh '{pr.head_ref}' {port}"
        success, stdout, _ = await ssm_run(cmd, timeout_s=30)

        healthy = success and "HEALTHY" in stdout
        if not healthy:
            logger.warning("staging_unhealthy", pr=pr.number, port=port, output=stdout[:200])
        return healthy

    async def health_check_all(self) -> dict[int, bool]:
        """Check health of all active staging containers."""
        results = {}
        for pr_key, pr in self.state_mgr.state.active_prs.items():
            if pr.staging_port:
                results[pr.number] = await self.health_check(pr)
        return results

    async def reconcile_ports(self) -> None:
        """On startup, reconcile port registry against actual containers on staging."""
        if self.dry_run:
            return

        logger.info("reconciling_ports")
        success, stdout, _ = await ssm_run(
            "docker ps --format '{{.Names}} {{.Ports}}' | grep governor-",
            timeout_s=30,
        )

        if not success:
            logger.warning("port_reconciliation_failed")
            return

        # Parse running governor containers
        running_branches = set()
        for line in stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            name = parts[0] if parts else ""
            if name.startswith("governor-") and name.endswith("-backend"):
                branch = name.replace("governor-", "").replace("-backend", "")
                running_branches.add(branch)

        # Check for orphaned port assignments
        registry = self.state_mgr.state.port_registry
        for port_str, assigned_pr in list(registry.items()):
            if assigned_pr is not None:
                pr_key = str(assigned_pr)
                pr = self.state_mgr.state.active_prs.get(pr_key)
                if pr:
                    safe_branch = pr.head_ref.replace("/", "-")
                    if safe_branch not in running_branches:
                        logger.warning(
                            "orphaned_port",
                            port=port_str,
                            pr=assigned_pr,
                            branch=pr.head_ref,
                        )

        self.state_mgr.save()
        logger.info("port_reconciliation_complete", running=len(running_branches))

    async def push_scripts_to_staging(self) -> bool:
        """Upload staging scripts to the EC2 instance."""
        if self.dry_run:
            logger.info("dry_run_push_scripts")
            return True

        # Create directory and upload scripts inline via SSM
        from pathlib import Path
        scripts_dir = Path(__file__).parent

        scripts = {
            "staging_deploy.sh": (scripts_dir / "staging_deploy.sh").read_text(),
            "staging_teardown.sh": (scripts_dir / "staging_teardown.sh").read_text(),
            "staging_health.sh": (scripts_dir / "staging_health.sh").read_text(),
        }

        cmd_parts = [f"mkdir -p {STAGING_SCRIPTS_DIR}"]
        for filename, content in scripts.items():
            # Escape for shell heredoc
            escaped = content.replace("'", "'\\''")
            cmd_parts.append(
                f"cat > {STAGING_SCRIPTS_DIR}/{filename} << 'SCRIPT_EOF'\n{content}\nSCRIPT_EOF"
            )
            cmd_parts.append(f"chmod +x {STAGING_SCRIPTS_DIR}/{filename}")

        full_cmd = " && ".join(cmd_parts)
        success, stdout, stderr = await ssm_run(full_cmd, timeout_s=30)

        if success:
            logger.info("scripts_pushed_to_staging")
        else:
            logger.error("scripts_push_failed", stderr=stderr[:500])

        return success

    def should_no_cache(self, touched_files: list[str]) -> bool:
        """Check if branch changes require no_cache build (HARD BLOCKER B-06)."""
        for f in touched_files:
            if f.endswith(".py") or f.endswith(".json"):
                return True
        return False
