"""Offline sanity checks for the backfill all-devices-per-window fix.

Proves, with NO network and NO production access (SSM is stubbed), that the
backfill path no longer fans out one SSM query per device per window:

  1. The window list is built correctly (count + [start,end) coverage).
  2. A simulated SSM truncation marker halves the window and retries.
  3. A 19-day all-store range issues O(windows) queries, NOT O(devices x
     windows) — assert the query count dropped by ~50x.

This is the backfill complement to test_sync_incremental_window.py (PR #772).

Run: SUPABASE_SERVICE_ROLE_KEY=dummy python scripts/tests/test_sync_backfill_fanout.py
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Avoid the import-time Doppler lookup; this test never touches Supabase/SSM.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy-offline-test-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_adms_to_supabase as s  # noqa: E402


def test_window_list_built_correctly():
    """A 19-day range splits into ceil(19*24 / WINDOW_HOURS) contiguous windows."""
    start, end = date(2026, 1, 1), date(2026, 1, 19)
    windows = s._build_backfill_windows(start, end)

    total_hours = 19 * 24  # inclusive end -> 19 full days
    expected = -(-total_hours // s.BACKFILL_WINDOW_HOURS)  # ceil division
    assert len(windows) == expected, (len(windows), expected)

    # First window starts at midnight day 1; last ends at midnight day 20.
    assert windows[0][0] == datetime(2026, 1, 1, 0, 0, 0)
    assert windows[-1][1] == datetime(2026, 1, 20, 0, 0, 0)

    # Windows are contiguous and non-overlapping: each end == next start.
    for (_, a_end), (b_start, _) in zip(windows, windows[1:]):
        assert a_end == b_start, (a_end, b_start)
    print(f"  [OK] 19-day range -> {len(windows)} contiguous {s.BACKFILL_WINDOW_HOURS}h windows")


def test_adaptive_subsplit_halves_on_truncation():
    """A truncated window is split in half and each half re-queried (2->3 calls)."""
    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    end_dt = datetime(2026, 1, 1, 4, 0, 0)  # 4h window
    mid = start_dt + (end_dt - start_dt) / 2  # 02:00

    calls = []

    def fake_query(_ssm, sql, _desc, return_truncation=False):
        # Record the [start, end) bounds this query asked for.
        lo = sql.split("event_time >= '")[1].split("'")[0]
        hi = sql.split("event_time < '")[1].split("'")[0]
        calls.append((lo, hi))
        # The full 4h window truncates; either half fits.
        full_lo = start_dt.isoformat(sep=" ")
        full_hi = end_dt.isoformat(sep=" ")
        truncated = (lo, hi) == (full_lo, full_hi)
        if truncated:
            return ("", True)  # output dropped by truncation handler
        # Each half returns one synthetic punch so we can count the result.
        row = f"1|9000001|{lo}|0|1|UDP3251200195"
        return (row, False)

    orig = s._run_ssm_query
    s._run_ssm_query = fake_query
    try:
        out = s._fetch_window(None, start_dt, end_dt, devices=None)
    finally:
        s._run_ssm_query = orig

    # 1 full (truncated) call + 2 half calls = 3 total.
    assert len(calls) == 3, calls
    assert calls[0] == (start_dt.isoformat(sep=" "), end_dt.isoformat(sep=" "))
    halves = {(lo, hi) for lo, hi in calls[1:]}
    assert (start_dt.isoformat(sep=" "), mid.isoformat(sep=" ")) in halves
    assert (mid.isoformat(sep=" "), end_dt.isoformat(sep=" ")) in halves
    assert len(out) == 2, f"both halves' rows should survive, got {len(out)}"
    print(f"  [OK] truncated 4h window -> 2 halves at {mid.time()}, {len(out)} rows recovered")


def test_query_count_is_windows_not_devices_times_windows():
    """19-day all-store range: O(windows), not O(devices x windows)."""
    start, end = date(2026, 1, 1), date(2026, 1, 19)
    n_windows = len(s._build_backfill_windows(start, end))
    n_devices = len(s.DEVICE_TO_STORE)

    query_count = {"n": 0}

    def fake_query(_ssm, sql, _desc, return_truncation=False):
        query_count["n"] += 1
        # No truncation, no rows — we only care about the call count here.
        return ("", False) if return_truncation else ""

    orig = s._run_ssm_query
    s._run_ssm_query = fake_query
    try:
        s._fetch_all_devices_range(None, start, end, store_filter=None)
    finally:
        s._run_ssm_query = orig

    old_model = n_devices * n_windows  # what the per-device loop would have done
    assert query_count["n"] == n_windows, (query_count["n"], n_windows)
    reduction = old_model / query_count["n"]
    assert reduction >= 45, f"expected ~{n_devices}x reduction, got {reduction:.1f}x"
    print(
        f"  [OK] {query_count['n']} queries (was {old_model} = {n_devices} devices "
        f"x {n_windows} windows) -> {reduction:.0f}x fewer SSM round-trips"
    )


def test_store_filter_uses_sn_in_clause():
    """A --store filter restricts to matching devices via a single sn IN (...) clause."""
    captured = {"sql": None}

    def fake_query(_ssm, sql, _desc, return_truncation=False):
        captured["sql"] = sql
        return ("", False)

    # FESTIVAL MALL -> exactly one device in the map.
    festival_devices = [d for d, st in s.DEVICE_TO_STORE.items() if "FESTIVAL" in st.upper()]
    assert len(festival_devices) == 1, festival_devices

    orig = s._run_ssm_query
    s._run_ssm_query = fake_query
    try:
        s._fetch_all_devices_range(None, date(2026, 1, 1), date(2026, 1, 1), store_filter="FESTIVAL")
    finally:
        s._run_ssm_query = orig

    assert "sn IN (" in captured["sql"], captured["sql"]
    assert festival_devices[0] in captured["sql"], captured["sql"]
    print(f"  [OK] --store FESTIVAL -> sn IN ('{festival_devices[0]}')")


if __name__ == "__main__":
    test_window_list_built_correctly()
    test_adaptive_subsplit_halves_on_truncation()
    test_query_count_is_windows_not_devices_times_windows()
    test_store_filter_uses_sn_in_clause()
    print("\nALL OFFLINE SANITY CHECKS PASSED")
