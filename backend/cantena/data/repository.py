"""Cost data repository for looking up cost data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cantena.data.city_cost_index import (
    CITY_COST_INDEXES,
    DEFAULT_COST_INDEX,
    STATE_COST_INDEXES,
)
from cantena.data.csi_divisions import DIVISION_BREAKDOWNS

if TYPE_CHECKING:
    from cantena.data.building_costs import SquareFootCostEntry
    from cantena.data.room_costs import RoomTypeCost
    from cantena.models.enums import BuildingType, ExteriorWall, StructuralSystem


class CostDataRepository:
    """Repository for looking up cost data.

    Wraps in-memory cost data and provides lookup methods with
    exact matching and fuzzy fallback logic.
    """

    def __init__(self, entries: list[SquareFootCostEntry]) -> None:
        self._entries = list(entries)

    def get_sf_cost(
        self,
        building_type: BuildingType,
        structural_system: StructuralSystem,
        exterior_wall: ExteriorWall,
        stories: int,
    ) -> SquareFootCostEntry | None:
        """Look up an exact match for the given parameters.

        Returns None if no exact match is found.
        """
        for entry in self._entries:
            if (
                entry.building_type == building_type
                and entry.structural_system == structural_system
                and entry.exterior_wall == exterior_wall
                and entry.stories_range[0] <= stories <= entry.stories_range[1]
            ):
                return entry
        return None

    def get_best_match_sf_cost(
        self,
        building_type: BuildingType,
        structural_system: StructuralSystem,
        exterior_wall: ExteriorWall,
        stories: int,
    ) -> tuple[SquareFootCostEntry, list[str]]:
        """Look up the best matching cost entry with fallback logic.

        Tries exact match first, then progressively relaxes constraints:
        1. Exact match on all parameters
        2. Match building_type + structural_system (relax exterior wall)
        3. Match building_type + exterior_wall (relax structural system)
        4. Match building_type only (relax both)

        Returns a tuple of (entry, fallback_reasons) where fallback_reasons
        is a list of strings describing which parameters were relaxed.

        Raises ValueError if no match is found at all (not even by building type).
        """
        # 1. Exact match
        exact = self.get_sf_cost(
            building_type, structural_system, exterior_wall, stories
        )
        if exact is not None:
            return exact, []

        fallback_reasons: list[str] = []

        # 2. Relax exterior wall
        for entry in self._entries:
            if (
                entry.building_type == building_type
                and entry.structural_system == structural_system
                and entry.stories_range[0] <= stories <= entry.stories_range[1]
            ):
                fallback_reasons.append(
                    f"Exterior wall '{exterior_wall}' not found for "
                    f"{building_type}/{structural_system}; "
                    f"used '{entry.exterior_wall}' instead"
                )
                return entry, fallback_reasons

        # 3. Relax structural system
        for entry in self._entries:
            if (
                entry.building_type == building_type
                and entry.exterior_wall == exterior_wall
                and entry.stories_range[0] <= stories <= entry.stories_range[1]
            ):
                fallback_reasons.append(
                    f"Structural system '{structural_system}' not found for "
                    f"{building_type}/{exterior_wall}; "
                    f"used '{entry.structural_system}' instead"
                )
                return entry, fallback_reasons

        # 4. Relax both — match building type only
        for entry in self._entries:
            if (
                entry.building_type == building_type
                and entry.stories_range[0] <= stories <= entry.stories_range[1]
            ):
                fallback_reasons.append(
                    f"No match for {building_type}/{structural_system}/{exterior_wall}; "
                    f"used {entry.structural_system}/{entry.exterior_wall} instead"
                )
                return entry, fallback_reasons

        # 5. Relax stories range too — match building type only, ignore stories
        for entry in self._entries:
            if entry.building_type == building_type:
                fallback_reasons.append(
                    f"No match for {building_type}/{structural_system}/{exterior_wall} "
                    f"at {stories} stories; used closest match "
                    f"({entry.stories_range[0]}-{entry.stories_range[1]} stories) instead"
                )
                return entry, fallback_reasons

        msg = (
            f"No cost data found for building type '{building_type}' "
            f"with any combination of parameters"
        )
        raise ValueError(msg)

    def get_division_breakdown(
        self, building_type: BuildingType
    ) -> dict[str, float]:
        """Get the typical CSI division percentage breakdown for a building type.

        Returns a dict mapping CSI division number -> percentage of total cost.
        """
        breakdown = DIVISION_BREAKDOWNS.get(building_type)
        if breakdown is None:
            msg = f"No division breakdown found for building type '{building_type}'"
            raise ValueError(msg)
        return dict(breakdown)

    def get_city_cost_index(self, city: str, state: str) -> float:
        """Get the city cost index for location-based adjustment.

        Lookup order:
        1. Exact city + state match (case-insensitive)
        2. State-level average
        3. National average (1.00)
        """
        city_lower = city.lower().strip()
        state_lower = state.lower().strip()

        # Try city + state
        index = CITY_COST_INDEXES.get((city_lower, state_lower))
        if index is not None:
            return index

        # Fallback to state average
        state_index = STATE_COST_INDEXES.get(state_lower)
        if state_index is not None:
            return state_index

        return DEFAULT_COST_INDEX

    def get_room_type_costs(
        self, building_type: BuildingType
    ) -> list[RoomTypeCost]:
        """Get room-type-level cost data for a building type.

        Returns residential costs for residential building types,
        commercial for commercial, etc.  Always includes an OTHER
        fallback entry.
        """
        from cantena.data.room_costs import get_room_costs_for_building_type

        return get_room_costs_for_building_type(building_type)
