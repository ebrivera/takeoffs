"""Tests for takeoff traceability — geometry refs, payload, and engine mapping."""

from __future__ import annotations

import pytest

from cantena.data.repository import CostDataRepository
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.engine import CostEngine
from cantena.geometry.extractor import Point2D
from cantena.geometry.rooms import DetectedRoom
from cantena.geometry.walls import WallSegment
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    ExteriorWall,
    StructuralSystem,
)
from cantena.models.estimate import (
    CostRange,
    DivisionCost,
    GeometryPayload,
    GeometryRef,
    SerializedRoom,
    SerializedWallSegment,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo() -> CostDataRepository:
    return CostDataRepository(SEED_COST_ENTRIES)


@pytest.fixture()
def engine(repo: CostDataRepository) -> CostEngine:
    return CostEngine(repo)


def _sample_building() -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        building_use="Multifamily residential",
        gross_sf=2000.0,
        stories=1,
        story_height_ft=10.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.WOOD_SIDING,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(),
        confidence={},
    )


def _make_rooms() -> list[DetectedRoom]:
    """Create a couple of fake rooms."""
    return [
        DetectedRoom(
            polygon_pts=[
                (0.0, 0.0),
                (100.0, 0.0),
                (100.0, 100.0),
                (0.0, 100.0),
            ],
            area_pts=10000.0,
            area_sf=500.0,
            perimeter_pts=400.0,
            perimeter_lf=50.0,
            centroid=Point2D(50.0, 50.0),
            label="KITCHEN",
            room_index=0,
        ),
        DetectedRoom(
            polygon_pts=[
                (100.0, 0.0),
                (200.0, 0.0),
                (200.0, 100.0),
                (100.0, 100.0),
            ],
            area_pts=10000.0,
            area_sf=500.0,
            perimeter_pts=400.0,
            perimeter_lf=50.0,
            centroid=Point2D(150.0, 50.0),
            label="LIVING ROOM",
            room_index=1,
        ),
    ]


def _make_walls() -> list[WallSegment]:
    """Create some fake wall segments."""
    from cantena.geometry.walls import Orientation

    return [
        WallSegment(
            start=Point2D(0.0, 0.0),
            end=Point2D(200.0, 0.0),
            thickness_pts=4.0,
            orientation=Orientation.HORIZONTAL,
            length_pts=200.0,
        ),
        WallSegment(
            start=Point2D(200.0, 0.0),
            end=Point2D(200.0, 100.0),
            thickness_pts=4.0,
            orientation=Orientation.VERTICAL,
            length_pts=100.0,
        ),
        WallSegment(
            start=Point2D(200.0, 100.0),
            end=Point2D(0.0, 100.0),
            thickness_pts=4.0,
            orientation=Orientation.HORIZONTAL,
            length_pts=200.0,
        ),
        WallSegment(
            start=Point2D(0.0, 100.0),
            end=Point2D(0.0, 0.0),
            thickness_pts=4.0,
            orientation=Orientation.VERTICAL,
            length_pts=100.0,
        ),
    ]


def _make_boundary() -> list[tuple[float, float]]:
    return [
        (0.0, 0.0),
        (200.0, 0.0),
        (200.0, 100.0),
        (0.0, 100.0),
    ]


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestGeometryRef:
    def test_serialize_deserialize(self) -> None:
        ref = GeometryRef(
            ref_id="room-0",
            ref_type="room_polygon",
            coordinates=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
            label="Kitchen",
        )
        data = ref.model_dump(mode="json")
        restored = GeometryRef.model_validate(data)
        assert restored.ref_id == "room-0"
        assert restored.ref_type == "room_polygon"
        assert restored.label == "Kitchen"
        assert len(restored.coordinates) == 3

    def test_default_page(self) -> None:
        ref = GeometryRef(
            ref_id="wall-0",
            ref_type="wall_segment",
            coordinates=[[0.0, 0.0], [10.0, 10.0]],
        )
        assert ref.page == 1
        assert ref.label is None


class TestGeometryPayload:
    def test_serialize_deserialize(self) -> None:
        payload = GeometryPayload(
            page_width_pts=612.0,
            page_height_pts=792.0,
            rooms=[
                SerializedRoom(
                    room_index=0,
                    polygon_pts=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
                    area_sf=100.0,
                    label="Kitchen",
                    centroid=[5.0, 5.0],
                ),
            ],
            wall_segments=[
                SerializedWallSegment(
                    start=[0.0, 0.0],
                    end=[10.0, 0.0],
                    thickness_pts=3.0,
                    length_lf=5.0,
                ),
            ],
            outer_boundary=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            scale_factor=48.0,
        )
        data = payload.model_dump(mode="json")
        restored = GeometryPayload.model_validate(data)
        assert restored.page_width_pts == 612.0
        assert len(restored.rooms) == 1
        assert len(restored.wall_segments) == 1
        assert restored.rooms[0].label == "Kitchen"

    def test_empty_defaults(self) -> None:
        payload = GeometryPayload(
            page_width_pts=612.0,
            page_height_pts=792.0,
        )
        assert payload.rooms == []
        assert payload.wall_segments == []
        assert payload.outer_boundary is None
        assert payload.page_image_base64 is None


class TestDivisionCostBackwardCompat:
    """DivisionCost works with and without new traceability fields."""

    def test_without_traceability_fields(self) -> None:
        dc = DivisionCost(
            csi_division="03",
            division_name="Concrete",
            cost=CostRange(low=100.0, expected=150.0, high=200.0),
            percent_of_total=15.0,
            source="RSMeans 2025",
        )
        assert dc.quantity is None
        assert dc.unit is None
        assert dc.unit_cost is None
        assert dc.total_cost is None
        assert dc.geometry_refs == []

    def test_with_traceability_fields(self) -> None:
        ref = GeometryRef(
            ref_id="footprint",
            ref_type="building_footprint",
            coordinates=[[0.0, 0.0], [10.0, 0.0]],
        )
        dc = DivisionCost(
            csi_division="03",
            division_name="Concrete",
            cost=CostRange(low=100.0, expected=150.0, high=200.0),
            percent_of_total=15.0,
            source="RSMeans 2025",
            quantity=2000.0,
            unit="SF",
            unit_cost=0.075,
            total_cost=150.0,
            geometry_refs=[ref],
        )
        assert dc.quantity == 2000.0
        assert dc.unit == "SF"
        assert len(dc.geometry_refs) == 1

    def test_json_round_trip_with_refs(self) -> None:
        ref = GeometryRef(
            ref_id="room-0",
            ref_type="room_polygon",
            coordinates=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
            label="Kitchen",
        )
        dc = DivisionCost(
            csi_division="09",
            division_name="Finishes",
            cost=CostRange(low=100.0, expected=150.0, high=200.0),
            percent_of_total=10.0,
            source="RSMeans 2025",
            quantity=1000.0,
            unit="SF",
            unit_cost=0.15,
            total_cost=150.0,
            geometry_refs=[ref],
        )
        data = dc.model_dump(mode="json")
        restored = DivisionCost.model_validate(data)
        assert restored.geometry_refs[0].label == "Kitchen"
        assert restored.quantity == 1000.0


# ---------------------------------------------------------------------------
# Engine tests — _attach_geometry_refs
# ---------------------------------------------------------------------------


class TestAttachGeometryRefs:
    def test_maps_room_divisions_to_rooms(
        self, engine: CostEngine
    ) -> None:
        building = _sample_building()
        estimate = engine.estimate(
            building,
            "Test",
            rooms=_make_rooms(),
            wall_segments=_make_walls(),
            outer_boundary=_make_boundary(),
            perimeter_lf=100.0,
        )
        # Room-based divisions: 06, 09, 23 (all rooms)
        for div in estimate.breakdown:
            if div.csi_division in ("06", "09", "23"):
                assert len(div.geometry_refs) > 0, (
                    f"Div {div.csi_division} should have room refs"
                )
                assert div.geometry_refs[0].ref_type == "room_polygon"
                assert div.unit == "SF"
                # room_area_sf = 500 + 500 = 1000
                assert div.quantity == pytest.approx(1000.0)

    def test_plumbing_maps_to_wet_rooms_only(
        self, engine: CostEngine
    ) -> None:
        """Division 22 (Plumbing) maps to wet rooms only."""
        building = _sample_building()
        estimate = engine.estimate(
            building,
            "Test",
            rooms=_make_rooms(),
            wall_segments=_make_walls(),
            outer_boundary=_make_boundary(),
            perimeter_lf=100.0,
        )
        for div in estimate.breakdown:
            if div.csi_division == "22":
                # Only KITCHEN is a wet room (LIVING ROOM is not)
                assert len(div.geometry_refs) == 1
                assert div.geometry_refs[0].label == "KITCHEN"
                assert div.unit == "SF"
                assert div.quantity == pytest.approx(500.0)

    def test_maps_wall_divisions_to_walls(
        self, engine: CostEngine
    ) -> None:
        building = _sample_building()
        estimate = engine.estimate(
            building,
            "Test",
            rooms=_make_rooms(),
            wall_segments=_make_walls(),
            outer_boundary=_make_boundary(),
            perimeter_lf=100.0,
        )
        # Wall-based divisions: 04, 07
        for div in estimate.breakdown:
            if div.csi_division in ("04", "07"):
                assert len(div.geometry_refs) > 0, (
                    f"Div {div.csi_division} should have wall refs"
                )
                assert div.geometry_refs[0].ref_type == "wall_segment"
                assert div.unit == "LF"
                assert div.quantity == pytest.approx(100.0)

    def test_maps_footprint_divisions_to_boundary(
        self, engine: CostEngine
    ) -> None:
        building = _sample_building()
        estimate = engine.estimate(
            building,
            "Test",
            rooms=_make_rooms(),
            wall_segments=_make_walls(),
            outer_boundary=_make_boundary(),
            perimeter_lf=100.0,
        )
        # Footprint divisions: 03, 26, 31
        for div in estimate.breakdown:
            if div.csi_division in ("03", "26", "31"):
                assert len(div.geometry_refs) > 0, (
                    f"Div {div.csi_division} should have footprint refs"
                )
                assert div.geometry_refs[0].ref_type == "building_footprint"
                assert div.unit == "SF"
                assert div.quantity == pytest.approx(2000.0)

    def test_unit_cost_computed(
        self, engine: CostEngine
    ) -> None:
        building = _sample_building()
        estimate = engine.estimate(
            building,
            "Test",
            rooms=_make_rooms(),
            wall_segments=_make_walls(),
            outer_boundary=_make_boundary(),
            perimeter_lf=100.0,
        )
        for div in estimate.breakdown:
            if div.quantity and div.quantity > 0:
                assert div.unit_cost is not None
                assert div.total_cost is not None
                assert div.unit_cost == pytest.approx(
                    div.total_cost / div.quantity
                )

    def test_no_geometry_leaves_refs_empty(
        self, engine: CostEngine
    ) -> None:
        """Without geometry, all refs are empty (backward-compatible)."""
        building = _sample_building()
        estimate = engine.estimate(building, "Test")
        for div in estimate.breakdown:
            assert div.geometry_refs == []
            assert div.quantity is None
            assert div.unit is None
