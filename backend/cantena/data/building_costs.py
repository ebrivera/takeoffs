"""Schema for square-foot cost data entries."""

from __future__ import annotations

from pydantic import BaseModel

from cantena.models.enums import BuildingType, ExteriorWall, StructuralSystem
from cantena.models.estimate import CostRange


class SquareFootCostEntry(BaseModel):
    """A single square-foot cost data point.

    Represents the cost per square foot for a specific combination of
    building type, structural system, and exterior wall system.
    """

    building_type: BuildingType
    structural_system: StructuralSystem
    exterior_wall: ExteriorWall
    stories_range: tuple[int, int]
    cost_per_sf: CostRange
    year: int
    notes: str
