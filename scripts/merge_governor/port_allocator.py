"""Port allocator for staging containers."""
from __future__ import annotations

import structlog

from .state_manager import StateManager

logger = structlog.get_logger("governor.ports")


class PortAllocator:
    """Allocates ports from a configurable range for staging containers."""

    def __init__(self, state_mgr: StateManager, port_min: int = 8001, port_max: int = 8010):
        self.state_mgr = state_mgr
        self.port_min = port_min
        self.port_max = port_max
        # Initialize port registry if empty
        if not state_mgr.state.port_registry:
            state_mgr.state.port_registry = {
                str(p): None for p in range(port_min, port_max + 1)
            }
            state_mgr.save()

    def allocate(self, pr_number: int) -> int | None:
        """Allocate a free port for a PR. Returns port or None if full."""
        registry = self.state_mgr.state.port_registry

        # Check if PR already has a port
        for port_str, assigned_pr in registry.items():
            if assigned_pr == pr_number:
                logger.info("port_already_assigned", pr=pr_number, port=int(port_str))
                return int(port_str)

        # Find first free port
        for port in range(self.port_min, self.port_max + 1):
            port_str = str(port)
            if registry.get(port_str) is None:
                registry[port_str] = pr_number
                self.state_mgr.save()
                logger.info("port_allocated", pr=pr_number, port=port)
                return port

        logger.warning("no_free_ports", pr=pr_number)
        return None

    def release(self, pr_number: int) -> int | None:
        """Release the port assigned to a PR. Returns freed port or None."""
        registry = self.state_mgr.state.port_registry
        for port_str, assigned_pr in registry.items():
            if assigned_pr == pr_number:
                registry[port_str] = None
                self.state_mgr.save()
                logger.info("port_released", pr=pr_number, port=int(port_str))
                return int(port_str)
        return None

    def get_port(self, pr_number: int) -> int | None:
        """Get the port assigned to a PR, or None."""
        for port_str, assigned_pr in self.state_mgr.state.port_registry.items():
            if assigned_pr == pr_number:
                return int(port_str)
        return None

    def active_count(self) -> int:
        """Count of currently allocated ports."""
        return sum(
            1 for v in self.state_mgr.state.port_registry.values() if v is not None
        )

    def max_capacity(self) -> int:
        return self.port_max - self.port_min + 1

    def is_full(self) -> bool:
        return self.active_count() >= self.max_capacity()

    def get_all_assignments(self) -> dict[int, int]:
        """Return {port: pr_number} for all assigned ports."""
        return {
            int(k): v
            for k, v in self.state_mgr.state.port_registry.items()
            if v is not None
        }
