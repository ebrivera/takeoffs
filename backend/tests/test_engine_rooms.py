"""Tests for the room-type-aware CostEngine — US-403."""

from __future__ import annotations

import pytest

from cantena.data.repository import CostDataRepository
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.engine import CostEngine
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    RoomType,
    StructuralSystem,
)
from cantena.models.space_program import Space, SpaceProgram, SpaceSource


@pytest.fixture()
def repo() -> CostDataRepository:
    return CostDataRepository(SEED_COST_ENTRIES)


@pytest.fixture()
def engine(repo: CostDataRepository) -> CostEngine:
    return CostEngine(repo)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _residential_building(
    gross_sf: float = 2_000.0,
    city: str = "Baltimore",
    state: str = "MD",
) -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        building_use="Multifamily residential",
        gross_sf=gross_sf,
        stories=1,
        story_height_ft=10.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.BRICK_VENEER,
        location=Location(city=city, state=state),
        complexity_scores=ComplexityScores(),
    )


def _office_building(
    gross_sf: float = 10_000.0,
    city: str = "Houston",
    state: str = "TX",
) -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.OFFICE_LOW_RISE,
        building_use="Commercial office",
        gross_sf=gross_sf,
        stories=1,
        story_height_ft=12.0,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall_system=ExteriorWall.BRICK_VENEER,
        location=Location(city=city, state=state),
        complexity_scores=ComplexityScores(),
    )


def _residential_space_program() -> SpaceProgram:
    """Residential space program with kitchen, utility, and living room."""
    return SpaceProgram(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        spaces=[
            Space(
                room_type=RoomType.KITCHEN,
                name="Kitchen",
                area_sf=200.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.UTILITY,
                name="Utility",
                area_sf=100.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.LIVING_ROOM,
                name="Living Room",
                area_sf=400.0,
                source=SpaceSource.LLM,
                confidence=Confidence.MEDIUM,
            ),
        ],
    )


def _office_space_program() -> SpaceProgram:
    """Office space program with lobby, open office, and corridor."""
    return SpaceProgram(
        building_type=BuildingType.OFFICE_LOW_RISE,
        spaces=[
            Space(
                room_type=RoomType.LOBBY,
                name="Main Lobby",
                area_sf=500.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.OPEN_OFFICE,
                name="Open Office",
                area_sf=4_500.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.CORRIDOR,
                name="Corridor",
                area_sf=1_200.0,
                source=SpaceSource.ASSUMED,
                confidence=Confidence.LOW,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Residential room-type pricing
# ---------------------------------------------------------------------------


class TestResidentialRoomPricing:
    """Kitchen should be priced higher per SF than utility."""

    def test_kitchen_more_expensive_than_utility(
        self, engine: CostEngine
    ) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Residential", space_program=program)

        assert estimate.space_breakdown is not None
        costs_by_type = {
            sc.room_type: sc for sc in estimate.space_breakdown
        }
        assert costs_by_type["kitchen"].cost_per_sf.expected > (
            costs_by_type["utility"].cost_per_sf.expected
        )

    def test_space_breakdown_has_all_rooms(
        self, engine: CostEngine
    ) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Residential", space_program=program)

        assert estimate.space_breakdown is not None
        assert len(estimate.space_breakdown) == 3

    def test_room_areas_match_program(
        self, engine: CostEngine
    ) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Residential", space_program=program)

        assert estimate.space_breakdown is not None
        areas = {sc.room_type: sc.area_sf for sc in estimate.space_breakdown}
        assert areas["kitchen"] == 200.0
        assert areas["utility"] == 100.0
        assert areas["living_room"] == 400.0


# ---------------------------------------------------------------------------
# Office room-type pricing
# ---------------------------------------------------------------------------


class TestOfficeRoomPricing:
    """Lobby should be most expensive per SF vs open office and corridor."""

    def test_lobby_most_expensive(self, engine: CostEngine) -> None:
        program = _office_space_program()
        building = _office_building(gross_sf=6_200.0)
        estimate = engine.estimate(building, "Office", space_program=program)

        assert estimate.space_breakdown is not None
        costs_by_type = {
            sc.room_type: sc for sc in estimate.space_breakdown
        }
        lobby_rate = costs_by_type["lobby"].cost_per_sf.expected
        office_rate = costs_by_type["open_office"].cost_per_sf.expected
        corridor_rate = costs_by_type["corridor"].cost_per_sf.expected
        assert lobby_rate > office_rate
        assert lobby_rate > corridor_rate


# ---------------------------------------------------------------------------
# Total cost consistency
# ---------------------------------------------------------------------------


class TestTotalCostConsistency:
    """Sum of space_breakdown costs should match total_cost within 1%."""

    def test_residential_breakdown_sums_to_total(
        self, engine: CostEngine
    ) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Test", space_program=program)

        assert estimate.space_breakdown is not None
        breakdown_sum = sum(
            sc.total_cost.expected for sc in estimate.space_breakdown
        )
        assert breakdown_sum == pytest.approx(
            estimate.total_cost.expected, rel=0.01
        )

    def test_office_breakdown_sums_to_total(
        self, engine: CostEngine
    ) -> None:
        program = _office_space_program()
        building = _office_building(gross_sf=6_200.0)
        estimate = engine.estimate(building, "Test", space_program=program)

        assert estimate.space_breakdown is not None
        breakdown_sum = sum(
            sc.total_cost.expected for sc in estimate.space_breakdown
        )
        assert breakdown_sum == pytest.approx(
            estimate.total_cost.expected, rel=0.01
        )

    def test_low_and_high_also_sum(self, engine: CostEngine) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Test", space_program=program)

        assert estimate.space_breakdown is not None
        low_sum = sum(sc.total_cost.low for sc in estimate.space_breakdown)
        high_sum = sum(sc.total_cost.high for sc in estimate.space_breakdown)
        assert low_sum == pytest.approx(estimate.total_cost.low, rel=0.01)
        assert high_sum == pytest.approx(estimate.total_cost.high, rel=0.01)

    def test_percent_of_total_sums_to_100(self, engine: CostEngine) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Test", space_program=program)

        assert estimate.space_breakdown is not None
        pct_sum = sum(sc.percent_of_total for sc in estimate.space_breakdown)
        assert pct_sum == pytest.approx(100.0, rel=0.01)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Without SpaceProgram, existing behavior preserved unchanged."""

    def test_no_space_program_no_breakdown(self, engine: CostEngine) -> None:
        building = _residential_building()
        estimate = engine.estimate(building, "No Rooms")
        assert estimate.space_breakdown is None

    def test_no_space_program_total_unchanged(self, engine: CostEngine) -> None:
        building = _residential_building(gross_sf=36_000.0)
        estimate = engine.estimate(building, "Test")

        # Baltimore index 0.95, default complexity 1.0, base 195 $/SF
        expected_per_sf = 195.0 * 0.95
        assert estimate.cost_per_sf.expected == pytest.approx(
            expected_per_sf, rel=0.01
        )

    def test_existing_fields_present(self, engine: CostEngine) -> None:
        building = _residential_building()
        estimate = engine.estimate(building, "Test")
        assert estimate.breakdown  # CSI divisions present
        assert estimate.building_summary.building_type == "apartment_low_rise"
        assert estimate.metadata.engine_version == "0.1.0"


# ---------------------------------------------------------------------------
# Fallback for unmapped room types
# ---------------------------------------------------------------------------


class TestOtherRoomTypeFallback:
    """RoomType.OTHER should fall back to whole-building $/SF rate."""

    def test_other_uses_building_rate(self, engine: CostEngine) -> None:
        program = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=200.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
                Space(
                    room_type=RoomType.LOADING_DOCK,
                    name="Loading Dock",
                    area_sf=300.0,
                    source=SpaceSource.ASSUMED,
                    confidence=Confidence.LOW,
                ),
            ],
        )
        building = _residential_building(gross_sf=500.0)
        estimate = engine.estimate(building, "Fallback", space_program=program)

        assert estimate.space_breakdown is not None
        costs_by_type = {
            sc.room_type: sc for sc in estimate.space_breakdown
        }
        # LOADING_DOCK has no residential room cost data — uses building rate
        dock_cost = costs_by_type["loading_dock"]
        # Kitchen uses room-specific rate (higher than building average)
        kitchen_cost = costs_by_type["kitchen"]
        # Just verify both produced valid costs
        assert dock_cost.total_cost.expected > 0
        assert kitchen_cost.total_cost.expected > 0
        # Kitchen at $300/SF should be higher per SF than building average ~$195
        assert kitchen_cost.cost_per_sf.expected > dock_cost.cost_per_sf.expected


# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------


class TestSourceTracking:
    """SpaceCost.source should match Space.source from SpaceProgram."""

    def test_source_populated_correctly(self, engine: CostEngine) -> None:
        program = _residential_space_program()
        building = _residential_building(gross_sf=700.0)
        estimate = engine.estimate(building, "Sources", space_program=program)

        assert estimate.space_breakdown is not None
        sources = {sc.name: sc.source for sc in estimate.space_breakdown}
        assert sources["Kitchen"] == "geometry"
        assert sources["Utility"] == "geometry"
        assert sources["Living Room"] == "llm"

    def test_user_override_source(self, engine: CostEngine) -> None:
        program = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.BEDROOM,
                    name="Master Bedroom",
                    area_sf=300.0,
                    source=SpaceSource.USER_OVERRIDE,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        building = _residential_building(gross_sf=300.0)
        estimate = engine.estimate(building, "Override", space_program=program)

        assert estimate.space_breakdown is not None
        assert estimate.space_breakdown[0].source == "user_override"


# ---------------------------------------------------------------------------
# Space count multiplier
# ---------------------------------------------------------------------------


class TestSpaceCountMultiplier:
    """Space.count > 1 should multiply the area correctly."""

    def test_count_multiplies_area(self, engine: CostEngine) -> None:
        program = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.BEDROOM,
                    name="Bedroom",
                    area_sf=150.0,
                    count=3,
                    source=SpaceSource.ASSUMED,
                    confidence=Confidence.LOW,
                ),
            ],
        )
        building = _residential_building(gross_sf=450.0)
        estimate = engine.estimate(building, "Count", space_program=program)

        assert estimate.space_breakdown is not None
        assert estimate.space_breakdown[0].area_sf == 450.0
