"""Tests for room-type cost data and repository integration."""

from __future__ import annotations

from cantena.data.repository import CostDataRepository
from cantena.data.room_costs import (
    HOSPITAL_ROOM_COSTS,
    OFFICE_ROOM_COSTS,
    RESIDENTIAL_ROOM_COSTS,
    SCHOOL_ROOM_COSTS,
    RoomTypeCost,
    get_room_costs_for_building_type,
)
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.models.enums import BuildingType, RoomType


class TestRoomCostData:
    """Verify seed data completeness and correctness."""

    def test_office_has_at_least_5_room_types(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.OFFICE_LOW_RISE)
        room_types = {c.room_type for c in costs}
        assert len(room_types) >= 5

    def test_residential_has_at_least_6_room_types(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.APARTMENT_LOW_RISE)
        room_types = {c.room_type for c in costs}
        assert len(room_types) >= 6

    def test_kitchen_more_expensive_than_utility(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.APARTMENT_LOW_RISE)
        by_type = {c.room_type: c for c in costs}
        kitchen = by_type[RoomType.KITCHEN]
        utility = by_type[RoomType.UTILITY]
        assert kitchen.base_cost_per_sf.expected > utility.base_cost_per_sf.expected

    def test_residential_percentages_sum_90_to_110(self) -> None:
        total = sum(c.typical_percent_of_building for c in RESIDENTIAL_ROOM_COSTS)
        assert 90.0 <= total <= 110.0, f"Residential percentages sum to {total}"

    def test_office_percentages_sum_90_to_110(self) -> None:
        total = sum(c.typical_percent_of_building for c in OFFICE_ROOM_COSTS)
        assert 90.0 <= total <= 110.0, f"Office percentages sum to {total}"

    def test_school_percentages_sum_90_to_110(self) -> None:
        total = sum(c.typical_percent_of_building for c in SCHOOL_ROOM_COSTS)
        assert 90.0 <= total <= 110.0, f"School percentages sum to {total}"

    def test_hospital_percentages_sum_90_to_110(self) -> None:
        total = sum(c.typical_percent_of_building for c in HOSPITAL_ROOM_COSTS)
        assert 90.0 <= total <= 110.0, f"Hospital percentages sum to {total}"

    def test_all_room_types_have_nonempty_cost_drivers(self) -> None:
        all_costs: list[RoomTypeCost] = (
            RESIDENTIAL_ROOM_COSTS
            + OFFICE_ROOM_COSTS
            + SCHOOL_ROOM_COSTS
            + HOSPITAL_ROOM_COSTS
        )
        for cost in all_costs:
            assert len(cost.cost_drivers) > 0, (
                f"{cost.room_type} in {cost.building_context} has empty cost_drivers"
            )

    def test_unknown_room_type_falls_back_to_other(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.APARTMENT_LOW_RISE)
        other_entries = [c for c in costs if c.room_type == RoomType.OTHER]
        assert len(other_entries) == 1
        assert other_entries[0].base_cost_per_sf.expected > 0


class TestCostDataRepositoryRoomTypes:
    """Verify repository integration with room cost data."""

    def test_repository_returns_room_costs_for_office(self) -> None:
        repo = CostDataRepository(SEED_COST_ENTRIES)
        costs = repo.get_room_type_costs(BuildingType.OFFICE_LOW_RISE)
        room_types = {c.room_type for c in costs}
        assert RoomType.LOBBY in room_types
        assert RoomType.OPEN_OFFICE in room_types
        assert len(room_types) >= 5

    def test_repository_returns_room_costs_for_residential(self) -> None:
        repo = CostDataRepository(SEED_COST_ENTRIES)
        costs = repo.get_room_type_costs(BuildingType.APARTMENT_LOW_RISE)
        room_types = {c.room_type for c in costs}
        assert RoomType.KITCHEN in room_types
        assert RoomType.BATHROOM in room_types
        assert len(room_types) >= 6

    def test_repository_returns_room_costs_for_hospital(self) -> None:
        repo = CostDataRepository(SEED_COST_ENTRIES)
        costs = repo.get_room_type_costs(BuildingType.HOSPITAL)
        room_types = {c.room_type for c in costs}
        assert RoomType.PATIENT_ROOM in room_types
        assert RoomType.OPERATING_ROOM in room_types

    def test_repository_returns_room_costs_for_school(self) -> None:
        repo = CostDataRepository(SEED_COST_ENTRIES)
        costs = repo.get_room_type_costs(BuildingType.SCHOOL_ELEMENTARY)
        room_types = {c.room_type for c in costs}
        assert RoomType.CLASSROOM in room_types
        assert RoomType.CORRIDOR in room_types


class TestBuildingTypeMapping:
    """Verify correct building type -> room cost category mapping."""

    def test_mid_rise_office_gets_office_costs(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.OFFICE_MID_RISE)
        room_types = {c.room_type for c in costs}
        assert RoomType.LOBBY in room_types

    def test_high_rise_apartment_gets_residential_costs(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.APARTMENT_HIGH_RISE)
        room_types = {c.room_type for c in costs}
        assert RoomType.KITCHEN in room_types
        assert RoomType.BEDROOM in room_types

    def test_hotel_gets_residential_costs(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.HOTEL)
        room_types = {c.room_type for c in costs}
        assert RoomType.LIVING_ROOM in room_types

    def test_retail_gets_office_costs(self) -> None:
        costs = get_room_costs_for_building_type(BuildingType.RETAIL)
        room_types = {c.room_type for c in costs}
        assert RoomType.OPEN_OFFICE in room_types

    def test_all_categories_include_other_fallback(self) -> None:
        for bt in BuildingType:
            costs = get_room_costs_for_building_type(bt)
            other_entries = [c for c in costs if c.room_type == RoomType.OTHER]
            assert len(other_entries) >= 1, (
                f"Building type {bt} has no OTHER fallback entry"
            )
