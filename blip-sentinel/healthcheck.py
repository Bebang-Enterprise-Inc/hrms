"""Lightweight HTTP health check server for Blip Sentinel."""
import json
import logging
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

log = logging.getLogger("sentinel.healthcheck")


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""

    # Class variable to store DB path
    db_path: str = ""

    def log_message(self, format, *args):
        """Override to use Python logging instead of stderr."""
        log.debug("%s - - [%s] %s", self.address_string(),
                 self.log_date_time_string(), format % args)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self._send_response(404, {"error": "Not found"})

    def _handle_health(self):
        """GET /health — Returns JSON with system health status."""
        try:
            # Import here to avoid circular dependency
            from metrics import get_health_status

            # Test DB connection
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.row_factory = sqlite3.Row

            # Get health status
            health = get_health_status(conn)
            conn.close()

            # Add DB connection status
            response = {
                "db_connected": True,
                **health
            }

            # Return 200 if healthy, 503 if degraded
            status_code = 200 if health.get("status") == "healthy" else 503
            self._send_response(status_code, response)

        except Exception as e:
            log.error("Health check failed: %s", e)
            self._send_response(503, {
                "status": "unhealthy",
                "db_connected": False,
                "error": str(e)
            })

    def _handle_metrics(self):
        """GET /metrics — Returns JSON system metrics summary."""
        try:
            from metrics import get_metrics_summary

            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.row_factory = sqlite3.Row

            # Get 24-hour metrics summary
            summary = get_metrics_summary(conn, hours=24)
            conn.close()

            self._send_response(200, {
                "period_hours": 24,
                "jobs": summary
            })

        except Exception as e:
            log.error("Metrics endpoint failed: %s", e)
            self._send_response(500, {"error": str(e)})

    def _send_response(self, status_code: int, data: dict):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())


def start_health_check_server(db_path: str, port: Optional[int] = None):
    """Start health check server in a background thread.

    Args:
        db_path: Path to the SQLite database
        port: Port to listen on (default from HEALTH_CHECK_PORT env var or 8080)
    """
    if port is None:
        port = int(os.environ.get("HEALTH_CHECK_PORT", "8080"))

    # Set DB path on handler class
    HealthCheckHandler.db_path = db_path

    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)

    def serve():
        log.info("Health check server listening on port %d", port)
        try:
            server.serve_forever()
        except Exception as e:
            log.error("Health check server error: %s", e)

    thread = threading.Thread(target=serve, daemon=True, name="HealthCheckServer")
    thread.start()
    log.info("Health check server started in background thread")
