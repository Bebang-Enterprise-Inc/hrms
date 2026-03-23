"""Tests for port allocator."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.merge_governor.port_allocator import PortAllocator
from scripts.merge_governor.state_manager import StateManager


@pytest.fixture
def mgr(tmp_path):
    return StateManager(tmp_path / "state")


@pytest.fixture
def alloc(mgr):
    return PortAllocator(mgr, port_min=8001, port_max=8003)


class TestPortAllocator:
    def test_allocate_returns_first_free(self, alloc):
        port = alloc.allocate(pr_number=101)
        assert port == 8001

    def test_allocate_second_pr(self, alloc):
        alloc.allocate(101)
        port = alloc.allocate(102)
        assert port == 8002

    def test_same_pr_gets_same_port(self, alloc):
        p1 = alloc.allocate(101)
        p2 = alloc.allocate(101)
        assert p1 == p2

    def test_full_returns_none(self, alloc):
        alloc.allocate(101)
        alloc.allocate(102)
        alloc.allocate(103)
        assert alloc.allocate(104) is None

    def test_release_frees_port(self, alloc):
        alloc.allocate(101)
        alloc.allocate(102)
        alloc.allocate(103)
        assert alloc.is_full()

        freed = alloc.release(102)
        assert freed == 8002
        assert not alloc.is_full()

        # New PR gets the freed port
        port = alloc.allocate(104)
        assert port == 8002

    def test_release_nonexistent_returns_none(self, alloc):
        assert alloc.release(999) is None

    def test_get_port(self, alloc):
        alloc.allocate(101)
        assert alloc.get_port(101) == 8001
        assert alloc.get_port(999) is None

    def test_active_count(self, alloc):
        assert alloc.active_count() == 0
        alloc.allocate(101)
        assert alloc.active_count() == 1
        alloc.allocate(102)
        assert alloc.active_count() == 2
        alloc.release(101)
        assert alloc.active_count() == 1

    def test_get_all_assignments(self, alloc):
        alloc.allocate(101)
        alloc.allocate(102)
        assignments = alloc.get_all_assignments()
        assert assignments == {8001: 101, 8002: 102}

    def test_state_persists(self, mgr):
        alloc1 = PortAllocator(mgr, port_min=8001, port_max=8003)
        alloc1.allocate(101)

        # New allocator with same state manager
        alloc2 = PortAllocator(mgr, port_min=8001, port_max=8003)
        assert alloc2.get_port(101) == 8001
        assert alloc2.active_count() == 1
