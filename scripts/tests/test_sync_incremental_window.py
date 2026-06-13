"""Offline sanity checks for the incremental watermark + paging fix (D-1).

Proves, with NO network and NO production access (httpx + SSM are stubbed):
  1. UTC->PHT watermark conversion math is correct (the original TZ bug).
  2. The paging loop returns ALL rows across multiple SSM pages and drops the
     inclusive-boundary duplicate (the original truncation/ASC drop bug).

Run: SUPABASE_SERVICE_ROLE_KEY=dummy python scripts/tests/test_sync_incremental_window.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Avoid the import-time Doppler lookup; this test never touches Supabase/SSM.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy-offline-test-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_adms_to_supabase as s  # noqa: E402

PHT = timezone(timedelta(hours=8))


def test_watermark_utc_to_pht():
    """A Supabase MAX in UTC must become +8h PHT-naive (the core TZ contract).

    The fixture is dated in the future so the MAX (not the NOW-2h floor) wins,
    isolating the UTC->PHT conversion that the original bug got wrong.
    """
    future_utc = datetime.now(timezone.utc) + timedelta(days=2)
    future_utc = future_utc.replace(microsecond=0)
    expected_pht = future_utc.astimezone(PHT).replace(tzinfo=None)

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"event_time": future_utc.isoformat()}]

    orig = s.httpx.get
    s.httpx.get = lambda *a, **k: _Resp()
    try:
        wm = s._incremental_watermark()
    finally:
        s.httpx.get = orig

    assert wm.tzinfo is None, "watermark must be PHT-naive for the ADMS column"
    assert wm == expected_pht, (wm, expected_pht)
    assert (wm - future_utc.replace(tzinfo=None)) == timedelta(hours=8), "must be +8h"
    print(f"  [OK] watermark {future_utc.isoformat()} -> {wm.isoformat(sep=' ')} PHT (+8h)")


def test_watermark_floor_when_empty():
    """Empty Supabase -> floor at NOW(PHT)-2h, never the epoch / whole table."""
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    orig = s.httpx.get
    s.httpx.get = lambda *a, **k: _Resp()
    try:
        wm = s._incremental_watermark()
    finally:
        s.httpx.get = orig

    expected = datetime.now(PHT).replace(tzinfo=None) - timedelta(hours=2)
    assert abs((wm - expected).total_seconds()) < 5, (wm, expected)
    print(f"  [OK] empty Supabase -> {s.INCREMENTAL_FLOOR_HOURS}h floor {wm.isoformat(sep=' ')}")


def test_paging_returns_all_rows_no_loss():
    """625 rows across 3 SSM pages of 250 are ALL returned (no silent drop)."""
    page_size = s.INCREMENTAL_PAGE_SIZE  # 250
    total = 2 * page_size + 125  # 625 -> pages of 250, 250, 125
    base = datetime(2026, 6, 13, 9, 0, 0)
    universe = [
        {
            "adms_id": str(i),
            "pin": "9000001",
            "event_time": (base + timedelta(seconds=i)).isoformat(sep=" "),
            "status_code": 0,
            "verify_code": 1,
            "device_sn": "UDP3251200195",
        }
        for i in range(total)
    ]

    def fake_query(_ssm, sql, _desc):
        # Extract the inclusive lower bound from the WHERE clause.
        bound = sql.split("event_time >= '")[1].split("'")[0]
        rows = [r for r in universe if r["event_time"] >= bound]
        rows = rows[:page_size]  # ADMS LIMIT
        # Re-encode to pipe-delimited SSM output the parser expects.
        return "\n".join(
            f"{r['adms_id']}|{r['pin']}|{r['event_time']}|{r['status_code']}|{r['verify_code']}|{r['device_sn']}"
            for r in rows
        )

    # Watermark pinned below all rows so the loop pages the full universe.
    orig_wm = s._incremental_watermark
    orig_q = s._run_ssm_query
    s._incremental_watermark = lambda: base - timedelta(hours=1)
    s._run_ssm_query = fake_query
    try:
        out = s._fetch_incremental(ssm_client=None)
    finally:
        s._incremental_watermark = orig_wm
        s._run_ssm_query = orig_q

    ids = [r["adms_id"] for r in out]
    assert len(out) == total, f"expected {total}, got {len(out)} (rows lost!)"
    assert len(set(ids)) == total, "duplicate rows leaked past boundary dedup"
    assert ids == [str(i) for i in range(total)], "rows out of order / missing"
    print(f"  [OK] paged {total} rows across 3 SSM pages, zero loss, zero dup")


def test_ssm_failure_propagates_none():
    """A failed SSM query must still return None (caller distinguishes failure)."""
    orig_wm = s._incremental_watermark
    orig_q = s._run_ssm_query
    s._incremental_watermark = lambda: datetime(2026, 6, 13, 8, 0, 0)
    s._run_ssm_query = lambda *a, **k: None
    try:
        out = s._fetch_incremental(ssm_client=None)
    finally:
        s._incremental_watermark = orig_wm
        s._run_ssm_query = orig_q
    assert out is None, out
    print("  [OK] SSM failure -> None preserved")


def test_same_second_cluster_does_not_loop():
    """>PAGE_SIZE rows sharing one timestamp must break (no infinite loop)."""
    page_size = s.INCREMENTAL_PAGE_SIZE
    ts = datetime(2026, 6, 13, 9, 0, 0).isoformat(sep=" ")
    universe = [
        {
            "adms_id": str(i),
            "pin": "9000001",
            "event_time": ts,  # all identical second
            "status_code": 0,
            "verify_code": 1,
            "device_sn": "UDP3251200195",
        }
        for i in range(page_size + 50)
    ]

    def fake_query(_ssm, sql, _desc):
        bound = sql.split("event_time >= '")[1].split("'")[0]
        rows = [r for r in universe if r["event_time"] >= bound][:page_size]
        return "\n".join(
            f"{r['adms_id']}|{r['pin']}|{r['event_time']}|{r['status_code']}|{r['verify_code']}|{r['device_sn']}"
            for r in rows
        )

    orig_wm = s._incremental_watermark
    orig_q = s._run_ssm_query
    s._incremental_watermark = lambda: datetime(2026, 6, 13, 8, 0, 0)
    s._run_ssm_query = fake_query
    try:
        out = s._fetch_incremental(ssm_client=None)  # must return, not hang
    finally:
        s._incremental_watermark = orig_wm
        s._run_ssm_query = orig_q
    assert len(out) == page_size, len(out)  # first page captured, tail deferred
    print(f"  [OK] same-second cluster broke cleanly ({len(out)} captured, tail deferred)")


if __name__ == "__main__":
    test_watermark_utc_to_pht()
    test_watermark_floor_when_empty()
    test_paging_returns_all_rows_no_loss()
    test_ssm_failure_propagates_none()
    test_same_second_cluster_does_not_loop()
    print("\nALL OFFLINE SANITY CHECKS PASSED")
