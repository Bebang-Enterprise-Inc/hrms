"""REST API for governor-erp — status, control, inter-agent communication.

Endpoints:
  GET  /healthz, /status, /pr, /pr/{num}, /pr/{num}/log, /queue, /lessons
  POST /wake, /pr/{num}/review, /pr/{num}/merge

Uses component injection — no GovernorERP import (avoids circular deps).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import structlog

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = structlog.get_logger("governor.health")

_LIVE_LOG_DIR = Path.home() / ".governor" / "live"


class HealthServer:
    """HTTP API server on localhost:8000 for governor status and control."""

    def __init__(
        self,
        state_mgr: "StateManager",
        host: str = "127.0.0.1",
        port: int = 8000,
        merge_serializer: Any = None,
        wake_event: asyncio.Event | None = None,
        review_callback: Callable[..., Coroutine] | None = None,
    ):
        self.state_mgr = state_mgr
        self.host = host
        self.port = port
        self.merge_serializer = merge_serializer
        self.wake_event = wake_event
        self._review_callback = review_callback
        self._server: asyncio.Server | None = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            request_line = data.decode("utf-8", errors="replace").split("\r\n")[0] if data else ""
            parts = request_line.split(" ")
            method = parts[0] if len(parts) >= 2 else "GET"
            path = parts[1] if len(parts) >= 2 else "/"

            status_code, body = await self._route(method, path)
            response = (
                f"HTTP/1.1 {status_code}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
                f"{body}"
            )
            writer.write(response.encode())
            await writer.drain()
        except Exception as e:
            logger.error("health_request_error", error=str(e))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _route(self, method: str, path: str) -> tuple[str, str]:
        if method == "GET":
            if path == "/healthz":
                return self._handle_healthz()
            if path == "/status":
                return self._handle_status()
            if path == "/pr":
                return self._handle_pr_list()
            if path == "/queue":
                return self._handle_queue()
            if path == "/lessons":
                return self._handle_lessons()
            m = re.match(r"^/pr/(\d+)$", path)
            if m:
                return self._handle_pr_detail(int(m.group(1)))
            m = re.match(r"^/pr/(\d+)/log$", path)
            if m:
                return self._handle_pr_log(int(m.group(1)))
        if method == "POST":
            if path == "/wake":
                return self._handle_wake()
            m = re.match(r"^/pr/(\d+)/review$", path)
            if m:
                return await self._handle_force_review(int(m.group(1)))
            m = re.match(r"^/pr/(\d+)/merge$", path)
            if m:
                return self._handle_force_merge(int(m.group(1)))
        return "404 Not Found", json.dumps({"error": "not found", "path": path})

    def _handle_healthz(self) -> tuple[str, str]:
        state = self.state_mgr.state
        return "200 OK", json.dumps({
            "status": "ok", "queue_depth": len(state.merge_queue),
            "active_prs": len(state.active_prs), "paused": state.paused,
            "uptime_s": round(time.time() - state.started_at, 1) if state.started_at else 0,
        })

    def _handle_status(self) -> tuple[str, str]:
        state = self.state_mgr.state
        pipeline = self.merge_serializer.get_pipeline_summary() if self.merge_serializer else ""
        return "200 OK", json.dumps({
            "status": "paused" if state.paused else "running",
            "uptime_s": round(time.time() - state.started_at, 1) if state.started_at else 0,
            "active_pr_count": len(state.active_prs), "merge_queue": state.merge_queue,
            "production_head": state.production_head, "pipeline": pipeline,
            "active_prs": {
                k: {"number": pr.number, "title": pr.title, "head_ref": pr.head_ref,
                     "review_decision": pr.review_decision, "review_confidence": pr.review_confidence,
                     "staging_port": pr.staging_port, "gate_blocked": getattr(pr, "gate_blocked", False)}
                for k, pr in state.active_prs.items()
            },
        })

    def _handle_pr_list(self) -> tuple[str, str]:
        state = self.state_mgr.state
        prs = []
        for k, pr in state.active_prs.items():
            q = state.merge_queue.index(pr.number) + 1 if pr.number in state.merge_queue else None
            prs.append({"number": pr.number, "title": pr.title, "head_ref": pr.head_ref,
                        "review_decision": pr.review_decision, "queue_position": q})
        return "200 OK", json.dumps({"prs": prs})

    def _handle_pr_detail(self, pr_num: int) -> tuple[str, str]:
        pr = self.state_mgr.state.active_prs.get(str(pr_num))
        if not pr:
            return "404 Not Found", json.dumps({"error": f"PR #{pr_num} not found"})
        state = self.state_mgr.state
        q = state.merge_queue.index(pr.number) + 1 if pr.number in state.merge_queue else None
        step = ""
        if self.merge_serializer and self.merge_serializer.pipeline_pr == pr_num:
            step = self.merge_serializer.pipeline_step
        return "200 OK", json.dumps({
            "number": pr.number, "title": pr.title, "head_ref": pr.head_ref,
            "head_sha": pr.head_sha, "review_decision": pr.review_decision,
            "review_confidence": pr.review_confidence, "queue_position": q,
            "pipeline_step": step, "gate_blocked": getattr(pr, "gate_blocked", False),
            "builder_dispatch_count": pr.builder_dispatch_count,
        })

    def _handle_pr_log(self, pr_num: int) -> tuple[str, str]:
        log_file = _LIVE_LOG_DIR / f"pr_{pr_num}.jsonl"
        if not log_file.exists():
            return "200 OK", json.dumps({"events": []})
        events = []
        try:
            for line in log_file.read_text(encoding="utf-8").strip().splitlines()[-100:]:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return "200 OK", json.dumps({"events": events})

    def _handle_queue(self) -> tuple[str, str]:
        state = self.state_mgr.state
        queue = [{"position": i + 1, "pr_number": n,
                  "title": state.active_prs.get(str(n), None) and state.active_prs[str(n)].title or "unknown"}
                 for i, n in enumerate(state.merge_queue)]
        return "200 OK", json.dumps({"queue": queue, "total": len(queue)})

    def _handle_lessons(self) -> tuple[str, str]:
        try:
            from .lessons import get_memory_stats, load_memory
            return "200 OK", json.dumps({"stats": get_memory_stats(), "lessons_text": load_memory()[:5000]})
        except Exception as e:
            return "500 Internal Server Error", json.dumps({"error": str(e)})

    def _handle_wake(self) -> tuple[str, str]:
        if self.wake_event:
            self.wake_event.set()
            print(f"[{time.strftime('%H:%M:%S')}] API: force-wake triggered", flush=True)
            return "200 OK", json.dumps({"status": "woke"})
        return "503 Service Unavailable", json.dumps({"error": "Wake event not configured"})

    async def _handle_force_review(self, pr_num: int) -> tuple[str, str]:
        pr = self.state_mgr.state.active_prs.get(str(pr_num))
        if not pr:
            return "404 Not Found", json.dumps({"error": f"PR #{pr_num} not found"})
        pr.review_decision = None
        pr.review_sha = None
        self.state_mgr.save()
        print(f"[{time.strftime('%H:%M:%S')}] API: force-review PR #{pr_num}", flush=True)
        if self._review_callback:
            asyncio.create_task(self._review_callback(pr))
        if self.wake_event:
            self.wake_event.set()
        return "200 OK", json.dumps({"status": "review_queued", "pr": pr_num})

    def _handle_force_merge(self, pr_num: int) -> tuple[str, str]:
        state = self.state_mgr.state
        pr = state.active_prs.get(str(pr_num))
        if not pr:
            return "404 Not Found", json.dumps({"error": f"PR #{pr_num} not found"})
        if pr_num not in state.merge_queue:
            state.merge_queue.append(pr_num)
            self.state_mgr.save()
        pos = state.merge_queue.index(pr_num) + 1
        print(f"[{time.strftime('%H:%M:%S')}] API: force-merge PR #{pr_num} (pos {pos})", flush=True)
        if self.wake_event:
            self.wake_event.set()
        return "200 OK", json.dumps({"status": "merge_queued", "pr": pr_num, "position": pos})

    async def start(self) -> None:
        self._cleanup_old_logs()
        try:
            self._server = await asyncio.start_server(self._handle, self.host, self.port)
            logger.info("health_server_started", host=self.host, port=self.port)
        except OSError:
            try:
                self._server = await asyncio.start_server(self._handle, self.host, self.port + 1)
                self.port += 1
                logger.info("health_server_started", host=self.host, port=self.port, note="alternate")
            except OSError:
                logger.warning("health_server_disabled", reason="no available port")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("health_server_stopped")

    @staticmethod
    def _cleanup_old_logs() -> None:
        if not _LIVE_LOG_DIR.exists():
            return
        cutoff = time.time() - 86400
        for f in _LIVE_LOG_DIR.glob("*.jsonl"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
