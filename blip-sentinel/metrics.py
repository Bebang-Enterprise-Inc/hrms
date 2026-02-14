"""System metrics for observability."""
import logging
import time
from contextlib import contextmanager
from typing import Optional
import sqlite3

log = logging.getLogger("sentinel.metrics")

# system_metrics table DDL (added to db.py schema too)
METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    job_name TEXT NOT NULL,
    duration_ms INTEGER,
    messages_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    api_calls_used INTEGER DEFAULT 0,
    notes TEXT
);
"""


@contextmanager
def track_job(conn: sqlite3.Connection, job_name: str):
    """Context manager to track job execution metrics."""
    start = time.monotonic()
    metrics = {"messages_processed": 0, "errors": 0, "api_calls_used": 0, "notes": ""}
    try:
        yield metrics
    except Exception as e:
        metrics["errors"] += 1
        metrics["notes"] = str(e)[:200]
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        log_metric(conn, job_name, duration_ms, **metrics)


def log_metric(conn: sqlite3.Connection, job_name: str, duration_ms: int,
               messages_processed: int = 0, errors: int = 0,
               api_calls_used: int = 0, notes: str = ""):
    """Record a job execution metric to the database."""
    try:
        conn.execute(
            """INSERT INTO system_metrics
               (job_name, duration_ms, messages_processed, errors, api_calls_used, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_name, duration_ms, messages_processed, errors, api_calls_used, notes)
        )
        conn.commit()
        log.debug("Logged metric for %s: %dms, %d processed, %d errors",
                 job_name, duration_ms, messages_processed, errors)
    except sqlite3.Error as e:
        log.error("Failed to log metric for %s: %s", job_name, e)


def get_metrics_summary(conn: sqlite3.Connection, hours: int = 24) -> dict:
    """Get metrics summary for last N hours."""
    try:
        cutoff = f"-{hours} hours"
        rows = conn.execute(
            """SELECT job_name,
                      COUNT(*) as executions,
                      AVG(duration_ms) as avg_duration_ms,
                      MAX(duration_ms) as max_duration_ms,
                      SUM(messages_processed) as total_messages,
                      SUM(errors) as total_errors,
                      SUM(api_calls_used) as total_api_calls
               FROM system_metrics
               WHERE timestamp > datetime('now', ?)
               GROUP BY job_name
               ORDER BY job_name""",
            (cutoff,)
        ).fetchall()

        summary = {}
        for row in rows:
            summary[row["job_name"]] = {
                "executions": row["executions"],
                "avg_duration_ms": round(row["avg_duration_ms"] or 0, 1),
                "max_duration_ms": row["max_duration_ms"],
                "total_messages": row["total_messages"],
                "total_errors": row["total_errors"],
                "total_api_calls": row["total_api_calls"]
            }

        return summary
    except sqlite3.Error as e:
        log.error("Failed to get metrics summary: %s", e)
        return {}


def get_health_status(conn: sqlite3.Connection) -> dict:
    """Check system health: last sweep < 10 min, last classify < 10 min."""
    try:
        # Check last sweep time
        last_sweep = conn.execute(
            """SELECT MAX(timestamp) as last_time FROM system_metrics
               WHERE job_name LIKE '%_sweep'"""
        ).fetchone()

        # Check last classify time
        last_classify = conn.execute(
            """SELECT MAX(timestamp) as last_time FROM system_metrics
               WHERE job_name = 'classify'"""
        ).fetchone()

        # Check recent error rate
        error_rate = conn.execute(
            """SELECT
                   COUNT(*) as total,
                   SUM(CASE WHEN errors > 0 THEN 1 ELSE 0 END) as failed
               FROM system_metrics
               WHERE timestamp > datetime('now', '-1 hour')"""
        ).fetchone()

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        # Parse last times
        def time_diff_minutes(ts_str: Optional[str]) -> Optional[float]:
            if not ts_str:
                return None
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            return (now - ts).total_seconds() / 60

        last_sweep_mins = time_diff_minutes(last_sweep["last_time"] if last_sweep else None)
        last_classify_mins = time_diff_minutes(last_classify["last_time"] if last_classify else None)

        # Determine health
        sweep_ok = last_sweep_mins is not None and last_sweep_mins < 10
        classify_ok = last_classify_mins is not None and last_classify_mins < 10

        total = error_rate["total"] if error_rate else 0
        failed = error_rate["failed"] if error_rate else 0
        error_rate_pct = (failed / total * 100) if total > 0 else 0

        healthy = sweep_ok and classify_ok and error_rate_pct < 20

        return {
            "status": "healthy" if healthy else "degraded",
            "last_sweep_minutes_ago": round(last_sweep_mins, 1) if last_sweep_mins else None,
            "last_classify_minutes_ago": round(last_classify_mins, 1) if last_classify_mins else None,
            "error_rate_last_hour_pct": round(error_rate_pct, 1),
            "checks": {
                "sweep_recent": sweep_ok,
                "classify_recent": classify_ok,
                "error_rate_ok": error_rate_pct < 20
            }
        }
    except Exception as e:
        log.error("Failed to get health status: %s", e)
        return {
            "status": "unknown",
            "error": str(e)
        }
