"""/healthz HTTP endpoint for governor-erp."""
from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = structlog.get_logger("governor.health")


class HealthServer:
    """Lightweight HTTP server on localhost:8000 providing /healthz."""

    def __init__(self, state_mgr: "StateManager", host: str = "127.0.0.1", port: int = 8000):
        self.state_mgr = state_mgr
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            request_line = data.decode().split("\r\n")[0] if data else ""

            if "GET /healthz" in request_line:
                state = self.state_mgr.state
                body = json.dumps({
                    "status": "ok",
                    "queue_depth": len(state.merge_queue),
                    "active_prs": len(state.active_prs),
                    "paused": state.paused,
                    "uptime_s": round(time.time() - state.started_at, 1) if state.started_at else 0,
                })
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )
            else:
                body = '{"error": "not found"}'
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
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

    async def start(self) -> None:
        try:
            self._server = await asyncio.start_server(self._handle, self.host, self.port)
            logger.info("health_server_started", host=self.host, port=self.port)
        except OSError as e:
            logger.warning("health_server_port_in_use", port=self.port, error=str(e))
            # Try alternate port
            alt_port = self.port + 1
            try:
                self._server = await asyncio.start_server(self._handle, self.host, alt_port)
                self.port = alt_port
                logger.info("health_server_started", host=self.host, port=alt_port, note="alternate_port")
            except OSError:
                logger.warning("health_server_disabled", reason="no available port")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("health_server_stopped")
