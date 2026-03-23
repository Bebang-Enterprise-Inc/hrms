"""governor-erp: AI Merge Governor for BEI-ERP.

Main entrypoint. Runs as a single async Python process on the operator's machine.
Watches PRs, manages staging containers, reviews code with AI, serializes merges.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import structlog

# Configure structlog before any logging
_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "governor.jsonl"


def _activity_renderer(logger, method_name, event_dict):
    """Render governor activity as clean terminal output.

    Translates structured log events into operator-friendly messages.
    Noisy or internal events are suppressed from the terminal.
    """
    import datetime

    event = event_dict.get("event", "")
    ts = datetime.datetime.now().strftime("%H:%M:%S")

    # Map events to clean terminal messages
    messages = {
        "new_pr_detected": lambda _: None,  # Handled by direct print in pr_watcher
        "port_allocated": lambda _: None,   # Handled by direct print in governor
        "port_released": lambda _: None,    # Handled by direct print in governor
        "pr_closed": lambda _: None,        # Handled by direct print in pr_watcher
        "reviewing_pr": lambda d: f"  Reviewing PR #{d.get('pr','')}...",
        "review_complete": lambda d: f"  PR #{d.get('pr','')} -> {d.get('decision','')} (confidence: {d.get('confidence',''):.2f})",
        "sdk_review_cost": lambda d: f"  Review cost: ${d.get('cost_usd',0):.4f} (total: ${d.get('total_cost_usd',0):.4f})",
        "sdk_chat_cost": lambda d: f"  Chat cost: ${d.get('cost_usd',0):.4f} ({d.get('history_len',0)} messages)",
        "staging_deploying": lambda d: f"  Deploying PR #{d.get('pr','')} to staging :{d.get('port','')}...",
        "staging_deployed": lambda d: f"  PR #{d.get('pr','')} deployed to staging",
        "staging_tearing_down": lambda d: f"  Tearing down staging for PR #{d.get('pr','')}...",
        "merging_pr": lambda d: f"  Merging PR #{d.get('pr','')} to production...",
        "pr_merged": lambda d: f"  PR #{d.get('pr','')} merged!",
        "deploy_triggered": lambda d: f"  Production deploy triggered",
        "l1_smoke_passed": lambda d: f"  L1 smoke test PASSED",
        "l1_ping_ok": lambda d: f"  L1 ping OK (attempt {d.get('attempt','')})",
        "merge_cycle_complete": lambda d: f"  Merge cycle complete for PR #{d.get('pr','')}",
        "governor_initialized": lambda _: None,  # Suppress (shown in status board)
        "state_loaded": lambda _: None,
        "state_saved": lambda _: None,
        "chat_keyword": lambda _: None,  # Suppress (user sees the response directly)
        "chat_llm": lambda _: None,
        "pr_watcher_started": lambda _: None,
        "health_server_started": lambda _: None,
        "health_server_port_in_use": lambda _: None,
        "chat_ready": lambda _: None,
        "ai_backend_ready": lambda _: None,
        "ai_review_skipped": lambda _: None,
    }

    renderer = messages.get(event)
    if renderer is not None:
        msg = renderer(event_dict)
        if msg is None:
            # Suppressed event — still write to file, skip terminal
            raise structlog.DropEvent
        # Clean terminal output
        event_dict["_rendered"] = f"[{ts}]{msg}"
    else:
        # Unknown events: show as-is for debugging
        level = event_dict.get("level", "info")
        if level in ("debug",):
            raise structlog.DropEvent
        event_dict["_rendered"] = f"[{ts}] {event}"

    return event_dict


def _terminal_printer(logger, method_name, event_dict):
    """Print the rendered message to stdout and drop the event (don't double-print)."""
    rendered = event_dict.pop("_rendered", None)
    if rendered:
        try:
            print(rendered, flush=True)
        except UnicodeEncodeError:
            safe = rendered.encode("ascii", errors="replace").decode()
            print(safe, flush=True)
    raise structlog.DropEvent


def _configure_logging(log_file: Path = _LOG_FILE) -> None:
    """Configure structlog: clean activity feed to terminal, JSON to file."""
    structlog.reset_defaults()  # Clear any cached loggers from import-time
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _json_file_processor,  # Write JSON to file first
            _activity_renderer,    # Transform to clean terminal message
            _terminal_printer,     # Print and drop
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,  # Never cache — always use current config
    )


def _json_file_processor(logger, method_name, event_dict):
    """Write every event to the JSON log file before terminal rendering."""
    try:
        _json_logger.write(dict(event_dict))
    except Exception:
        pass  # Never let log writes kill PR processing
    return event_dict


# JSON file logger
class _JsonFileLogger:
    def __init__(self, path: Path, max_bytes: int = 10 * 1024 * 1024):
        self.path = path
        self.max_bytes = max_bytes

    def write(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            rotated = self.path.with_suffix(".jsonl.1")
            if rotated.exists():
                rotated.unlink()
            self.path.rename(rotated)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")


_json_logger = _JsonFileLogger(_LOG_FILE)

from .chat_handler import ChatHandler
from .health_server import HealthServer
from .port_allocator import PortAllocator
from .pr_watcher import PRWatcher
from .state_manager import PRRecord, StateManager

logger = structlog.get_logger("governor")


class GovernorERP:
    """Main governor process."""

    def __init__(
        self,
        dry_run: bool = False,
        ai_backend_type: str = "cli",
        skip_review: bool = False,
        state_dir: Path | None = None,
    ):
        self.dry_run = dry_run
        self.ai_backend_type = ai_backend_type
        self.skip_review = skip_review

        # State
        base_dir = state_dir or (Path(__file__).parent / "state")
        self.state_mgr = StateManager(base_dir)
        self.port_allocator: PortAllocator | None = None
        self.pr_watcher: PRWatcher | None = None
        self.chat_handler: ChatHandler | None = None
        self.health_server: HealthServer | None = None
        self.ai_backend = None

        # Control
        self._stop_event = asyncio.Event()
        self._running = False

    async def initialize(self) -> None:
        """Load state, set up components."""
        # Load or create state
        try:
            self.state_mgr.load()
            logger.info("state_loaded", file=str(self.state_mgr.state_file))
        except ValueError as e:
            logger.error("state_corrupt", error=str(e))
            print(f"\nFATAL: {e}")
            print("Delete the state file and restart, or restore from backup.")
            sys.exit(1)

        if not self.state_mgr.state.started_at:
            self.state_mgr.state.started_at = time.time()

        # Load baseline context (production HEAD + recent merges)
        await self._load_baseline_context()

        # Port allocator
        self.port_allocator = PortAllocator(self.state_mgr)

        # PR watcher
        self.pr_watcher = PRWatcher(self.state_mgr)
        self.pr_watcher.on_new_pr(self._handle_new_pr)
        self.pr_watcher.on_closed_pr(self._handle_closed_pr)

        # AI backend (lazy — will be initialized in Phase 2a)
        self.ai_backend = await self._init_ai_backend()

        # Chat handler
        self.chat_handler = ChatHandler(ai_backend=self.ai_backend)

        # Staging manager + Merge serializer (automated merge pipeline)
        from .reviewer import Reviewer
        from .staging_manager import StagingManager
        from .merge_serializer import MergeSerializer
        self.staging_mgr = StagingManager(
            state_mgr=self.state_mgr,
            port_allocator=self.port_allocator,
            dry_run=self.dry_run,
        )
        self.merge_serializer = MergeSerializer(
            state_mgr=self.state_mgr,
            reviewer=Reviewer(backend=self.ai_backend, state_mgr=self.state_mgr),
            staging_mgr=self.staging_mgr,
            dry_run=self.dry_run,
        )

        # Health server
        self.health_server = HealthServer(self.state_mgr)

        # Log structured event
        _json_logger.write({
            "event": "governor_initialized",
            "dry_run": self.dry_run,
            "ai_backend": self.ai_backend_type,
            "timestamp": time.time(),
        })

    async def _init_ai_backend(self):
        """Initialize the selected AI backend. Returns None if not available."""
        if self.skip_review:
            logger.info("ai_review_skipped", reason="--skip-review flag")
            return None

        try:
            if self.ai_backend_type == "cli":
                from .ai_backend_cli import CLIBackend
                backend = CLIBackend()
                if await backend.health_check():
                    logger.info("ai_backend_ready", type="cli")
                    return backend
                else:
                    logger.warning("cli_backend_unavailable", hint="Falling back to no AI review")
                    return None
            elif self.ai_backend_type == "sdk":
                from .ai_backend_sdk import SDKBackend
                backend = SDKBackend()
                if await backend.health_check():
                    logger.info("ai_backend_ready", type="sdk")
                    return backend
                else:
                    logger.warning("sdk_backend_unavailable")
                    return None
            elif self.ai_backend_type == "agent-sdk":
                from .ai_backend_agent_sdk import AgentSDKBackend
                backend = AgentSDKBackend()
                if await backend.health_check():
                    logger.info("ai_backend_ready", type="agent-sdk")
                    return backend
                else:
                    logger.warning(
                        "agent_sdk_backend_unavailable",
                        hint="Check ANTHROPIC_API_KEY and claude-agent-sdk install",
                    )
                    return None
        except ImportError as e:
            logger.warning("ai_backend_import_error", error=str(e))
            return None
        except Exception as e:
            logger.warning("ai_backend_init_error", error=str(e))
            return None

    async def _load_baseline_context(self) -> None:
        """Load production HEAD and recent merge history on startup."""
        import subprocess
        import shutil
        state = self.state_mgr.state
        gh = shutil.which("gh") or "gh"
        repo = "Bebang-Enterprise-Inc/hrms"

        # 1. Get production HEAD
        if not state.production_head:
            try:
                result = subprocess.run(
                    ["git", "ls-remote", f"https://github.com/{repo}.git", "refs/heads/production"],
                    capture_output=True, text=True, timeout=15,
                    stdin=subprocess.DEVNULL,
                )
                if result.returncode == 0 and result.stdout.strip():
                    state.production_head = result.stdout.split()[0]
                    print(f"[{time.strftime('%H:%M:%S')}] Production HEAD: {state.production_head[:12]}", flush=True)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Could not fetch production HEAD: {e}", flush=True)

        # 2. Load recent merged PRs (last 10) — always refresh on startup
        try:
            result = subprocess.run(
                [gh, "pr", "list", "--repo", repo, "--state", "merged",
                 "--limit", "10", "--json", "number,title,headRefName,files"],
                capture_output=True, text=True, timeout=30,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                import json as _json
                merged_prs = _json.loads(result.stdout)
                state.merge_history = []  # Replace, don't append
                for pr in merged_prs:
                    touched = [f.get("path", "") for f in pr.get("files", [])]
                    state.merge_history.append({
                        "number": pr["number"],
                        "title": pr.get("title", ""),
                        "touched_files": touched,
                    })
                if merged_prs:
                    print(f"\n  Recent merges:", flush=True)
                    for pr in merged_prs:
                        title = pr.get("title", "untitled")
                        print(f"    PR #{pr['number']}: {title}", flush=True)
                    print(flush=True)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Could not load merge history: {e}", flush=True)

        # 3. Inject lean baseline into AI chat memory (titles only — details fetched on demand)
        if self.ai_backend and hasattr(self.ai_backend, "_chat_history"):
            summary_lines = [
                f"[Governor baseline context]",
                f"Production HEAD: {state.production_head[:12] if state.production_head else 'unknown'}",
                f"Recent merges ({len(state.merge_history)}):",
            ]
            for m in state.merge_history:
                summary_lines.append(f"  PR #{m['number']}: {m.get('title', '')}")
            summary_lines.append(
                "\nTo get details about any PR, I can fetch it live from GitHub. "
                "Just ask about a specific PR number."
            )
            self.ai_backend._chat_history.append({
                "role": "assistant",
                "content": "\n".join(summary_lines),
            })

        self.state_mgr.save()

    async def _handle_new_pr(self, pr: PRRecord) -> None:
        """Called when a new PR is detected. Allocates port and auto-reviews."""
        # Allocate staging port
        port = self.port_allocator.allocate(pr.number)
        if port:
            pr.staging_port = port
            self.state_mgr.save()
            print(f"[{time.strftime('%H:%M:%S')}] Port :{port} assigned to PR #{pr.number}", flush=True)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] WARNING: No ports available for PR #{pr.number}", flush=True)

        # Auto-review if AI backend is available
        if self.ai_backend and not self.skip_review:
            await self._auto_review_pr(pr)

        _json_logger.write({
            "event": "new_pr_handled",
            "pr": pr.number,
            "port": port,
            "dry_run": self.dry_run,
            "timestamp": time.time(),
        })

    async def _auto_review_pr(self, pr: PRRecord) -> None:
        """Automatically review a PR when detected."""
        from .reviewer import Reviewer, get_pr_diff

        print(f"[{time.strftime('%H:%M:%S')}] Reviewing PR #{pr.number}...", flush=True)

        try:
            reviewer = Reviewer(backend=self.ai_backend, state_mgr=self.state_mgr)
            # Only fetch diff if the backend needs it (raw SDK does, Agent SDK doesn't)
            diff = ""
            if self.ai_backend and self.ai_backend.needs_diff:
                diff = await get_pr_diff(pr.number)
                if not diff:
                    print(f"[{time.strftime('%H:%M:%S')}] WARNING: Could not fetch diff for PR #{pr.number}", flush=True)
                    return

            result = await reviewer.review_pr(pr.number, pr.head_sha, diff)

            # Display result
            decision = result.decision
            confidence = result.confidence
            reasoning = result.reasoning[:150]

            try:
                print(f"[{time.strftime('%H:%M:%S')}] PR #{pr.number} -> {decision} (confidence: {confidence:.2f})", flush=True)
                print(f"    Reason: {reasoning}", flush=True)
            except UnicodeEncodeError:
                safe_reasoning = reasoning.encode("ascii", errors="replace").decode()
                print(f"[{time.strftime('%H:%M:%S')}] PR #{pr.number} -> {decision} (confidence: {confidence:.2f})", flush=True)
                print(f"    Reason: {safe_reasoning}", flush=True)

            if result.conflicting_files:
                print(f"    Conflicts: {', '.join(result.conflicting_files[:5])}", flush=True)

            # Auto-enqueue approved PRs for merge
            if decision == "APPROVE" and pr.number not in self.state_mgr.state.merge_queue:
                self.state_mgr.state.merge_queue.append(pr.number)
                self.state_mgr.save()
                print(f"[{time.strftime('%H:%M:%S')}] PR #{pr.number} added to merge queue (position {len(self.state_mgr.state.merge_queue)})", flush=True)
            elif decision in ("REJECT", "NEEDS_FIX"):
                # Post feedback on PR so the builder agent can fix it
                body = (
                    f"**Governor Review: {decision}** (confidence: {confidence:.2f})\n\n"
                    f"**Issues found:**\n{result.reasoning}\n\n"
                )
                if result.conflicting_files:
                    body += f"**Conflicting files:** {', '.join(result.conflicting_files)}\n\n"
                if hasattr(result, 'suggested_fix') and result.suggested_fix:
                    body += f"**Suggested fix:** {result.suggested_fix}\n\n"
                body += (
                    "---\n"
                    "**Builder action required:** Fix the issues above and push to this branch. "
                    "The governor will automatically re-review when it detects the new SHA.\n\n"
                    "*Posted by governor-erp*"
                )
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "gh", "pr", "comment", str(pr.number),
                        "--repo", "Bebang-Enterprise-Inc/hrms",
                        "--body", body,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                    print(f"[{time.strftime('%H:%M:%S')}] Posted review feedback on PR #{pr.number}", flush=True)
                except Exception:
                    pass

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Review error for PR #{pr.number}: {e}", flush=True)

    async def _handle_closed_pr(self, pr: PRRecord) -> None:
        """Called when a PR is closed/merged."""
        # Release port
        freed_port = self.port_allocator.release(pr.number)
        if freed_port:
            print(f"[{time.strftime('%H:%M:%S')}] Port :{freed_port} freed from PR #{pr.number}", flush=True)

        _json_logger.write({
            "event": "closed_pr_handled",
            "pr": pr.number,
            "freed_port": freed_port,
            "timestamp": time.time(),
        })

    async def _chat_loop(self) -> None:
        """Read operator input from stdin using a dedicated thread."""
        import queue
        input_queue: queue.Queue[str | None] = queue.Queue()

        def _stdin_reader():
            """Runs in a daemon thread — reads stdin without blocking the event loop."""
            try:
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        input_queue.put(None)
                        break
                    input_queue.put(line.strip())
            except Exception:
                input_queue.put(None)

        import threading
        reader_thread = threading.Thread(target=_stdin_reader, daemon=True)
        reader_thread.start()

        while not self._stop_event.is_set():
            try:
                # Poll the queue without blocking the event loop
                try:
                    line = input_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    continue

                if line is None:
                    break
                if not line:
                    continue

                response = await self.chat_handler.handle(line, self.state_mgr.state)
                try:
                    print(f"\n{response.text}\n", flush=True)
                except UnicodeEncodeError:
                    safe = response.text.encode("ascii", errors="replace").decode()
                    print(f"\n{safe}\n", flush=True)

                _json_logger.write({
                    "event": "chat_interaction",
                    "input": line,
                    "source": response.source,
                    "timestamp": time.time(),
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Chat error: {e}", flush=True)

    def _print_status_board(self) -> None:
        """Print a status summary to terminal."""
        state = self.state_mgr.state
        active = len(state.active_prs)
        queued = len(state.merge_queue)
        ports_used = self.port_allocator.active_count() if self.port_allocator else 0
        mode = "DRY-RUN" if self.dry_run else "LIVE"
        paused = " [PAUSED]" if state.paused else ""

        # 24h cost
        cost_line = ""
        if self.ai_backend and hasattr(self.ai_backend, "get_cost_last_24h"):
            cost_24h, calls_24h = self.ai_backend.get_cost_last_24h()
            cost_line = f"  Cost (24h): ${cost_24h:.4f} ({calls_24h} calls)"

        print(f"\n{'='*60}")
        print(f"  governor-erp [{mode}]{paused}")
        print(f"  PRs: {active} active | Queue: {queued} | Ports: {ports_used}/10")
        print(f"  AI: {self.ai_backend_type} | Production: {state.production_head[:8] if state.production_head else '?'}")
        if cost_line:
            print(cost_line)
        print(f"{'='*60}")
        print("  Type 'help' for commands, or ask a question.\n")

    async def run(self) -> None:
        """Main run loop."""
        await self.initialize()
        self._running = True
        self._print_status_board()

        try:
            # Start health server
            await self.health_server.start()

            # Run tasks concurrently with error isolation
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.pr_watcher.run(self._stop_event))
                tg.create_task(self.merge_serializer.run(self._stop_event))
                tg.create_task(self._chat_loop())

        except* KeyboardInterrupt:
            logger.info("keyboard_interrupt")
        except* Exception as eg:
            for exc in eg.exceptions:
                logger.error("task_group_error", error=str(exc))
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Graceful shutdown — save state, stop servers."""
        logger.info("shutting_down")
        self._stop_event.set()

        # Save state (don't tear down containers — they persist)
        self.state_mgr.save()
        logger.info("state_saved")

        # Stop health server
        if self.health_server:
            await self.health_server.stop()

        _json_logger.write({
            "event": "governor_shutdown",
            "timestamp": time.time(),
        })
        self._running = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="governor-erp",
        description="AI Merge Governor for BEI-ERP — serializes production merges with AI review",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without touching staging/production (logs actions only)",
    )
    parser.add_argument(
        "--ai-backend",
        choices=["cli", "sdk", "agent-sdk"],
        default="cli",
        help="AI backend: 'cli' uses claude --print (Max subscription, $0), 'sdk' uses API key (pay-per-token). Default: cli",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip AI review (emergency merges only)",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="State directory (default: scripts/merge_governor/state/)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="PR poll interval in seconds (default: 30)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    _configure_logging()

    if args.ai_backend == "sdk":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("WARNING: --ai-backend sdk requires ANTHROPIC_API_KEY environment variable.")
            print("This backend uses pay-per-token billing. Set the key or use --ai-backend cli.")
            sys.exit(1)
        print("WARNING: SDK backend active. API calls will be billed to your Anthropic account.")

    governor = GovernorERP(
        dry_run=args.dry_run,
        ai_backend_type=args.ai_backend,
        skip_review=args.skip_review,
        state_dir=args.state_dir,
    )

    # Signal handling
    def _signal_handler(sig, frame):
        print("\nShutting down gracefully (saving state, containers preserved)...")
        governor._stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    asyncio.run(governor.run())


if __name__ == "__main__":
    main()
