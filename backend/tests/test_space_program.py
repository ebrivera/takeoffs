"""Tests for SpaceProgram model and DetectedRoom bridge."""

from __future__ import annotations

from cantena.geometry.extractor import Point2D
from cantena.geometry.rooms import DetectedRoom
from cantena.models.building import BuildingModel, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    RoomType,
    StructuralSystem,
)
from cantena.models.space_program import Space, SpaceProgram, SpaceSource
from cantena.services.llm_geometry_interpreter import (
    LlmInterpretation,
    LlmRoomInterpretation,
)


def _make_room(
    label: str | None,
    area_sf: float,
    room_index: int = 0,
) -> DetectedRoom:
    """Create a minimal DetectedRoom for testing."""
    return DetectedRoom(
        polygon_pts=[(0, 0), (10, 0), (10, 10), (0, 10)],
        area_pts=100.0,
        area_sf=area_sf,
        perimeter_pts=40.0,
        perimeter_lf=10.0,
        centroid=Point2D(x=5.0, y=5.0),
        label=label,
        room_index=room_index,
    )


def _make_building_model(
    gross_sf: float = 2000.0,
    building_type: BuildingType = BuildingType.APARTMENT_LOW_RISE,
) -> BuildingModel:
    """Create a minimal BuildingModel for testing."""
    return BuildingModel(
        building_type=building_type,
        building_use="Residential",
        gross_sf=gross_sf,
        stories=1,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.WOOD_SIDING,
        location=Location(city="Denver", state="CO"),
    )


# -------------------------------------------------------------------
# from_detected_rooms
# -------------------------------------------------------------------


class TestFromDetectedRoomsBasic:
    """from_detected_rooms with 3 labeled rooms produces 3 Spaces with GEOMETRY."""

    def test_three_labeled_rooms(self) -> None:
        rooms = [
            _make_room("LIVING ROOM", 400.0, room_index=0),
            _make_room("KITCHEN", 200.0, room_index=1),
            _make_room("DINING", 150.0, room_index=2),
        ]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)

        assert len(prog.spaces) == 3
        for space in prog.spaces:
            assert space.source == SpaceSource.GEOMETRY
            assert space.confidence == Confidence.HIGH

    def test_room_types_mapped_correctly(self) -> None:
        rooms = [
            _make_room("LIVING ROOM", 400.0, room_index=0),
            _make_room("KITCHEN", 200.0, room_index=1),
            _make_room("DINING", 150.0, room_index=2),
        ]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)

        assert prog.spaces[0].room_type == RoomType.LIVING_ROOM
        assert prog.spaces[1].room_type == RoomType.KITCHEN
        assert prog.spaces[2].room_type == RoomType.DINING


class TestLabelMappings:
    """Maps specific label strings to correct RoomType."""

    def test_living_room(self) -> None:
        rooms = [_make_room("LIVING ROOM", 400.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.LIVING_ROOM

    def test_wc(self) -> None:
        rooms = [_make_room("WC", 50.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.WC

    def test_coats_maps_to_closet(self) -> None:
        rooms = [_make_room("COATS", 30.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.CLOSET

    def test_front_porch(self) -> None:
        rooms = [_make_room("FRONT PORCH", 100.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.PORCH

    def test_back_porch(self) -> None:
        rooms = [_make_room("BACK PORCH", 80.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.PORCH


class TestUnlabeledRoom:
    """Unlabeled DetectedRoom maps to OTHER."""

    def test_none_label(self) -> None:
        rooms = [_make_room(None, 100.0, room_index=5)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.OTHER
        assert prog.spaces[0].name == "Room 5"

    def test_unknown_label(self) -> None:
        rooms = [_make_room("MYSTERY ROOM", 100.0)]
        prog = SpaceProgram.from_detected_rooms(rooms, BuildingType.APARTMENT_LOW_RISE)
        assert prog.spaces[0].room_type == RoomType.OTHER


# -------------------------------------------------------------------
# from_building_model
# -------------------------------------------------------------------


class TestFromBuildingModel:
    """from_building_model generates reasonable residential distribution."""

    def test_generates_spaces(self) -> None:
        model = _make_building_model(gross_sf=2000.0)
        prog = SpaceProgram.from_building_model(model)

        assert len(prog.spaces) > 0
        assert prog.building_type == BuildingType.APARTMENT_LOW_RISE

    def test_all_assumed_source(self) -> None:
        model = _make_building_model(gross_sf=2000.0)
        prog = SpaceProgram.from_building_model(model)

        for space in prog.spaces:
            assert space.source == SpaceSource.ASSUMED
            assert space.confidence == Confidence.LOW

    def test_area_distribution_reasonable(self) -> None:
        model = _make_building_model(gross_sf=2000.0)
        prog = SpaceProgram.from_building_model(model)

        total = prog.total_area_sf
        # typical_percent_of_building sums to 90-110% per category
        assert 1800.0 <= total <= 2200.0


# -------------------------------------------------------------------
# from_llm_interpretation
# -------------------------------------------------------------------


class TestFromLlmInterpretation:
    """from_llm_interpretation maps LLM room types correctly."""

    def test_maps_room_types(self) -> None:
        interp = LlmInterpretation(
            building_type="APARTMENT_LOW_RISE",
            structural_system="WOOD_FRAME",
            rooms=[
                LlmRoomInterpretation(
                    room_index=0,
                    confirmed_label="Living Room",
                    room_type_enum="LIVING_ROOM",
                    notes="",
                ),
                LlmRoomInterpretation(
                    room_index=1,
                    confirmed_label="Kitchen",
                    room_type_enum="KITCHEN",
                    notes="",
                ),
            ],
        )
        prog = SpaceProgram.from_llm_interpretation(
            interp, total_area_sf=1000.0, building_type=BuildingType.APARTMENT_LOW_RISE,
        )

        assert len(prog.spaces) == 2
        assert prog.spaces[0].room_type == RoomType.LIVING_ROOM
        assert prog.spaces[1].room_type == RoomType.KITCHEN

    def test_all_llm_source(self) -> None:
        interp = LlmInterpretation(
            building_type="APARTMENT_LOW_RISE",
            structural_system="WOOD_FRAME",
            rooms=[
                LlmRoomInterpretation(
                    room_index=0,
                    confirmed_label="Lobby",
                    room_type_enum="LOBBY",
                    notes="",
                ),
            ],
        )
        prog = SpaceProgram.from_llm_interpretation(
            interp, total_area_sf=500.0, building_type=BuildingType.OFFICE_LOW_RISE,
        )

        assert prog.spaces[0].source == SpaceSource.LLM
        assert prog.spaces[0].confidence == Confidence.MEDIUM

    def test_unknown_type_falls_back_to_other(self) -> None:
        interp = LlmInterpretation(
            building_type="APARTMENT_LOW_RISE",
            structural_system="WOOD_FRAME",
            rooms=[
                LlmRoomInterpretation(
                    room_index=0,
                    confirmed_label="Weird Room",
                    room_type_enum="NONEXISTENT_TYPE",
                    notes="",
                ),
            ],
        )
        prog = SpaceProgram.from_llm_interpretation(
            interp, total_area_sf=500.0, building_type=BuildingType.APARTMENT_LOW_RISE,
        )
        assert prog.spaces[0].room_type == RoomType.OTHER


# -------------------------------------------------------------------
# total_area_sf
# -------------------------------------------------------------------


class TestTotalAreaSf:
    """total_area_sf sums correctly."""

    def test_sums_areas(self) -> None:
        prog = SpaceProgram(
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
                    room_type=RoomType.BEDROOM,
                    name="Bedroom",
                    area_sf=300.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        assert prog.total_area_sf == 500.0

    def test_respects_count(self) -> None:
        prog = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.BEDROOM,
                    name="Bedroom",
                    area_sf=200.0,
                    count=3,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        assert prog.total_area_sf == 600.0

    def test_empty(self) -> None:
        prog = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[],
        )
        assert prog.total_area_sf == 0.0


# -------------------------------------------------------------------
# update_space
# -------------------------------------------------------------------


class TestUpdateSpace:
    """update_space changes source to USER_OVERRIDE."""

    def test_changes_source(self) -> None:
        prog = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=200.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        prog.update_space(0, area_sf=250.0)

        assert prog.spaces[0].source == SpaceSource.USER_OVERRIDE
        assert prog.spaces[0].area_sf == 250.0

    def test_changes_room_type(self) -> None:
        prog = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.OTHER,
                    name="Unknown",
                    area_sf=100.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        prog.update_space(0, room_type=RoomType.BEDROOM, name="Bedroom")

        assert prog.spaces[0].room_type == RoomType.BEDROOM
        assert prog.spaces[0].name == "Bedroom"
        assert prog.spaces[0].source == SpaceSource.USER_OVERRIDE

    def test_preserves_unchanged_fields(self) -> None:
        prog = SpaceProgram(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=200.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
        )
        prog.update_space(0, area_sf=250.0)

        assert prog.spaces[0].room_type == RoomType.KITCHEN
        assert prog.spaces[0].name == "Kitchen"
