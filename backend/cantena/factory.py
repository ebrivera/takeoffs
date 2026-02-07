"""Factory functions for creating pre-configured CostEngine instances."""

from __future__ import annotations

from cantena.data.repository import CostDataRepository
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.engine import CostEngine


def create_default_engine() -> CostEngine:
    """Create a CostEngine wired up with the default seed cost data.

    This is the recommended way to create a CostEngine for typical usage.
    It wires up a CostDataRepository with the built-in seed data (2025
    national averages) so callers don't need to understand the internal
    wiring.

    Returns:
        A CostEngine ready to produce estimates.

    Example::

        from cantena import create_default_engine, BuildingModel

        engine = create_default_engine()
        estimate = engine.estimate(building, "My Project")
    """
    repository = CostDataRepository(SEED_COST_ENTRIES)
    return CostEngine(repository)
