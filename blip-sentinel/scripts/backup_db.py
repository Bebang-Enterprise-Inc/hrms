#!/usr/bin/env python3
"""Database backup to S3 with weekly restore drill."""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone


DB_PATH = os.environ.get("SENTINEL_DB_PATH", "/app/blip-sentinel/data/sentinel.db")
S3_BUCKET = os.environ.get("BACKUP_S3_BUCKET", "bei-backups")
S3_PREFIX = os.environ.get("BACKUP_S3_PREFIX", "blip-sentinel")


def backup():
    """Backup SQLite database to S3."""
    print(f"[{datetime.utcnow().isoformat()}] Starting backup of {DB_PATH}")

    # 1. WAL checkpoint
    print("Step 1/4: WAL checkpoint")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    # 2. SQLite .backup to temp file
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    backup_path = f"/tmp/sentinel-backup-{timestamp}.db"
    print(f"Step 2/4: Creating backup at {backup_path}")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    backup_conn = sqlite3.connect(backup_path)
    with backup_conn:
        conn.backup(backup_conn)
    backup_conn.close()
    conn.close()

    # 3. Upload to S3
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    s3_key = f"s3://{S3_BUCKET}/{S3_PREFIX}/sentinel-{date_str}.db"
    print(f"Step 3/4: Uploading to {s3_key}")

    try:
        subprocess.run(
            ["aws", "s3", "cp", backup_path, s3_key],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✓ Backup uploaded successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ S3 upload failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)

    # 4. Cleanup
    print("Step 4/4: Cleanup")
    os.remove(backup_path)

    # 5. Weekly restore drill (Sunday only)
    if datetime.utcnow().weekday() == 6:
        print("Sunday detected — running restore drill")
        restore_drill(s3_key)

    print(f"[{datetime.utcnow().isoformat()}] Backup completed successfully")


def restore_drill(s3_key: str):
    """Download backup and verify integrity."""
    print(f"Restore drill: Downloading {s3_key}")

    drill_path = "/tmp/sentinel-restore-drill.db"

    try:
        # Download from S3
        subprocess.run(
            ["aws", "s3", "cp", s3_key, drill_path],
            check=True,
            capture_output=True,
            text=True
        )

        # Verify integrity
        conn = sqlite3.connect(drill_path, timeout=10)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()

        if result == "ok":
            print("✓ Restore drill PASSED: Integrity check OK")
        else:
            print(f"✗ Restore drill FAILED: {result}", file=sys.stderr)
            sys.exit(1)

        # Cleanup
        os.remove(drill_path)

    except subprocess.CalledProcessError as e:
        print(f"✗ Restore drill FAILED: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"✗ Restore drill FAILED: SQLite error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        backup()
    except Exception as e:
        print(f"✗ Backup failed: {e}", file=sys.stderr)
        sys.exit(1)
