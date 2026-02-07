"""Tests for the cost data layer."""

from __future__ import annotations

import pytest

from cantena.data.building_costs import SquareFootCostEntry
from cantena.data.city_cost_index import CITY_COST_INDEXES, STATE_COST_INDEXES
from cantena.data.csi_divisions import CSI_DIVISIONS, DIVISION_BREAKDOWNS
from cantena.data.repository import CostDataRepository
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.models.enums import (
    BuildingType,
    ExteriorWall,
    StructuralSystem,
)
from cantena.models.estimate import CostRange

# ---------------------------------------------------------------------------
# Seed data integrity
# ---------------------------------------------------------------------------


class TestSeedData:
    def test_has_at_least_15_entries(self) -> None:
        assert len(SEED_COST_ENTRIES) >= 15

    def test_no_duplicate_entries(self) -> None:
        """Each combination of type, structure, wall, stories should be unique."""
        keys = [
            (e.building_type, e.structural_system, e.exterior_wall, e.stories_range)
            for e in SEED_COST_ENTRIES
        ]
        assert len(keys) == len(set(keys)), "Duplicate seed entries found"

    def test_all_entries_are_valid(self) -> None:
        """Every seed entry should be a valid SquareFootCostEntry."""
        for entry in SEED_COST_ENTRIES:
            assert isinstance(entry, SquareFootCostEntry)
            assert entry.cost_per_sf.low > 0
            assert entry.cost_per_sf.expected > 0
            assert entry.cost_per_sf.high > 0
            assert entry.stories_range[0] >= 1
            assert entry.stories_range[1] >= entry.stories_range[0]

    def test_cost_ranges_are_ordered(self) -> None:
        for entry in SEED_COST_ENTRIES:
            assert entry.cost_per_sf.low <= entry.cost_per_sf.expected
            assert entry.cost_per_sf.expected <= entry.cost_per_sf.high

    def test_covers_multiple_building_types(self) -> None:
        types = {e.building_type for e in SEED_COST_ENTRIES}
        assert len(types) >= 6, f"Only covers {len(types)} building types"


# ---------------------------------------------------------------------------
# CSI Divisions
# ---------------------------------------------------------------------------


class TestCSIDivisions:
    def test_divisions_list_not_empty(self) -> None:
        assert len(CSI_DIVISIONS) > 0

    def test_breakdowns_cover_all_building_types(self) -> None:
        for bt in BuildingType:
            assert bt in DIVISION_BREAKDOWNS, f"Missing breakdown for {bt}"

    def test_division_percentages_sum_to_approximately_100(self) -> None:
        for bt, breakdown in DIVISION_BREAKDOWNS.items():
            total = sum(breakdown.values())
            assert 95.0 <= total <= 105.0, (
                f"Division breakdown for {bt} sums to {total}%, "
                f"expected ~100%"
            )

    def test_no_negative_percentages(self) -> None:
        for bt, breakdown in DIVISION_BREAKDOWNS.items():
            for div, pct in breakdown.items():
                assert pct >= 0, f"Negative percentage for {bt} div {div}: {pct}"


# ---------------------------------------------------------------------------
# City Cost Index
# ---------------------------------------------------------------------------


class TestCityCostIndex:
    def test_has_at_least_30_cities(self) -> None:
        assert len(CITY_COST_INDEXES) >= 30

    def test_known_cities(self) -> None:
        assert CITY_COST_INDEXES[("new york", "ny")] == 1.30
        assert CITY_COST_INDEXES[("houston", "tx")] == 0.88
        assert CITY_COST_INDEXES[("san francisco", "ca")] == 1.35

    def test_state_indexes_not_empty(self) -> None:
        assert len(STATE_COST_INDEXES) > 0

    def test_indexes_are_reasonable(self) -> None:
        for key, index in CITY_COST_INDEXES.items():
            assert 0.5 <= index <= 2.0, (
                f"City cost index for {key} is {index}, outside reasonable range"
            )


# ---------------------------------------------------------------------------
# CostDataRepository
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo() -> CostDataRepository:
    return CostDataRepository(SEED_COST_ENTRIES)


class TestExactMatchLookup:
    def test_exact_match_apartment_low_rise(self, repo: CostDataRepository) -> None:
        result = repo.get_sf_cost(
            BuildingType.APARTMENT_LOW_RISE,
            StructuralSystem.WOOD_FRAME,
            ExteriorWall.BRICK_VENEER,
            stories=2,
        )
        assert result is not None
        assert result.building_type == BuildingType.APARTMENT_LOW_RISE
        assert result.cost_per_sf.expected == 195.0

    def test_exact_match_warehouse(self, repo: CostDataRepository) -> None:
        result = repo.get_sf_cost(
            BuildingType.WAREHOUSE,
            StructuralSystem.STEEL_FRAME,
            ExteriorWall.METAL_PANEL,
            stories=1,
        )
        assert result is not None
        assert result.building_type == BuildingType.WAREHOUSE

    def test_no_exact_match_returns_none(self, repo: CostDataRepository) -> None:
        result = repo.get_sf_cost(
            BuildingType.HOSPITAL,
            StructuralSystem.WOOD_FRAME,  # no wood-frame hospital in seed
            ExteriorWall.STUCCO,
            stories=3,
        )
        assert result is None

    def test_stories_outside_range_returns_none(
        self, repo: CostDataRepository
    ) -> None:
        result = repo.get_sf_cost(
            BuildingType.APARTMENT_LOW_RISE,
            StructuralSystem.WOOD_FRAME,
            ExteriorWall.BRICK_VENEER,
            stories=10,  # out of 1-3 range
        )
        assert result is None


class TestFuzzyMatchLookup:
    def test_fuzzy_match_relaxes_exterior_wall(
        self, repo: CostDataRepository
    ) -> None:
        """Apartment low-rise with stucco should fall back to brick/wood siding."""
        entry, reasons = repo.get_best_match_sf_cost(
            BuildingType.APARTMENT_LOW_RISE,
            StructuralSystem.WOOD_FRAME,
            ExteriorWall.STUCCO,  # not in seed for this combo
            stories=2,
        )
        assert entry is not None
        assert entry.building_type == BuildingType.APARTMENT_LOW_RISE
        assert len(reasons) > 0
        assert "Exterior wall" in reasons[0]

    def test_fuzzy_match_relaxes_structural_system(
        self, repo: CostDataRepository
    ) -> None:
        """Office low-rise with concrete should fall back to steel or wood."""
        entry, reasons = repo.get_best_match_sf_cost(
            BuildingType.OFFICE_LOW_RISE,
            StructuralSystem.CONCRETE_FRAME,  # no concrete low-rise office
            ExteriorWall.BRICK_VENEER,
            stories=2,
        )
        assert entry is not None
        assert entry.building_type == BuildingType.OFFICE_LOW_RISE
        assert len(reasons) > 0
        assert "Structural system" in reasons[0]

    def test_fuzzy_match_relaxes_both(self, repo: CostDataRepository) -> None:
        """Should find some match for the building type even with all wrong params."""
        entry, reasons = repo.get_best_match_sf_cost(
            BuildingType.RETAIL,
            StructuralSystem.WOOD_FRAME,  # no wood-frame retail in seed
            ExteriorWall.CURTAIN_WALL,  # no curtain wall retail in seed
            stories=1,
        )
        assert entry is not None
        assert entry.building_type == BuildingType.RETAIL
        assert len(reasons) > 0

    def test_exact_match_returns_no_reasons(
        self, repo: CostDataRepository
    ) -> None:
        entry, reasons = repo.get_best_match_sf_cost(
            BuildingType.APARTMENT_LOW_RISE,
            StructuralSystem.WOOD_FRAME,
            ExteriorWall.BRICK_VENEER,
            stories=2,
        )
        assert entry is not None
        assert len(reasons) == 0

    def test_raises_for_totally_unknown_type(self) -> None:
        """Empty repository should raise ValueError."""
        empty_repo = CostDataRepository([])
        with pytest.raises(ValueError, match="No cost data found"):
            empty_repo.get_best_match_sf_cost(
                BuildingType.HOSPITAL,
                StructuralSystem.STEEL_FRAME,
                ExteriorWall.CURTAIN_WALL,
                stories=5,
            )


class TestDivisionBreakdown:
    def test_get_division_breakdown(self, repo: CostDataRepository) -> None:
        breakdown = repo.get_division_breakdown(BuildingType.OFFICE_LOW_RISE)
        assert isinstance(breakdown, dict)
        assert len(breakdown) > 0
        total = sum(breakdown.values())
        assert 95.0 <= total <= 105.0

    def test_all_building_types_have_breakdown(
        self, repo: CostDataRepository
    ) -> None:
        for bt in BuildingType:
            breakdown = repo.get_division_breakdown(bt)
            assert len(breakdown) > 5


class TestCityCostIndexLookup:
    def test_known_city(self, repo: CostDataRepository) -> None:
        assert repo.get_city_cost_index("New York", "NY") == 1.30

    def test_case_insensitive(self, repo: CostDataRepository) -> None:
        assert repo.get_city_cost_index("new york", "ny") == 1.30
        assert repo.get_city_cost_index("NEW YORK", "NY") == 1.30

    def test_unknown_city_falls_back_to_state(
        self, repo: CostDataRepository
    ) -> None:
        # "Springfield" is not in city index, but "il" has a state index
        index = repo.get_city_cost_index("Springfield", "IL")
        assert index == STATE_COST_INDEXES["il"]

    def test_unknown_city_and_state_returns_default(
        self, repo: CostDataRepository
    ) -> None:
        index = repo.get_city_cost_index("Unknown City", "ZZ")
        assert index == 1.00

    def test_nyc_vs_houston_difference(self, repo: CostDataRepository) -> None:
        nyc = repo.get_city_cost_index("New York", "NY")
        houston = repo.get_city_cost_index("Houston", "TX")
        # NYC should be significantly more expensive than Houston
        ratio = nyc / houston
        assert ratio > 1.3, f"NYC/Houston ratio {ratio} should be > 1.3"


# ---------------------------------------------------------------------------
# SquareFootCostEntry model
# ---------------------------------------------------------------------------


class TestSquareFootCostEntry:
    def test_valid_construction(self) -> None:
        entry = SquareFootCostEntry(
            building_type=BuildingType.RETAIL,
            structural_system=StructuralSystem.STEEL_FRAME,
            exterior_wall=ExteriorWall.EIFS,
            stories_range=(1, 2),
            cost_per_sf=CostRange(low=100.0, expected=130.0, high=160.0),
            year=2025,
            notes="Test entry",
        )
        assert entry.building_type == BuildingType.RETAIL
        assert entry.stories_range == (1, 2)

    def test_json_round_trip(self) -> None:
        entry = SEED_COST_ENTRIES[0]
        json_str = entry.model_dump_json()
        restored = SquareFootCostEntry.model_validate_json(json_str)
        assert restored == entry
