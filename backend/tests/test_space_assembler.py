"""Tests for SpaceAssembler: geometry → LLM → assumed fallback assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from cantena.models.enums import BuildingType, Confidence, RoomType
from cantena.models.space_program import Space, SpaceProgram, SpaceSource
from cantena.services.space_assembler import SpaceAssembler

# ---------------------------------------------------------------------------
# Lightweight stubs (avoid importing heavy geometry/LLM modules)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubDetectedRoom:
    label: str | None
    area_sf: float | None
    room_index: int
    polygon_pts: list[tuple[float, float]] = field(default_factory=list)
    area_pts: float = 0.0
    perimeter_pts: float = 0.0
    perimeter_lf: float | None = None
    centroid: Any = None


@dataclass(frozen=True)
class _StubLlmRoom:
    room_index: int
    confirmed_label: str
    room_type_enum: str
    notes: str = ""


@dataclass(frozen=True)
class _StubLlmInterpretation:
    building_type: str = "RESIDENTIAL"
    structural_system: str = "wood frame"
    rooms: list[_StubLlmRoom] = field(default_factory=list)
    special_conditions: list[str] = field(default_factory=list)
    measurement_flags: list[str] = field(default_factory=list)
    confidence_notes: str = ""


@dataclass(frozen=True)
class _StubPageMeasurements:
    rooms: list[_StubDetectedRoom] | None = None
    llm_interpretation: _StubLlmInterpretation | None = None
    gross_area_sf: float | None = None


@dataclass(frozen=True)
class _StubBuildingModel:
    building_type: BuildingType = BuildingType.APARTMENT_LOW_RISE
    gross_sf: float = 1000.0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeometryRoomsAvailable:
    """When geometry rooms are available, assembler uses from_detected_rooms."""

    def test_uses_geometry_rooms(self) -> None:
        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
            _StubDetectedRoom(label="LIVING ROOM", area_sf=250.0, room_index=1),
            _StubDetectedRoom(label="BEDROOM", area_sf=150.0, room_index=2),
        ]
        pm = _StubPageMeasurements(rooms=rooms)  # type: ignore[arg-type]
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert len(program.spaces) == 3
        assert all(s.source == SpaceSource.GEOMETRY for s in program.spaces)

    def test_room_types_mapped_correctly(self) -> None:
        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
            _StubDetectedRoom(label="WC", area_sf=30.0, room_index=1),
        ]
        pm = _StubPageMeasurements(rooms=rooms)  # type: ignore[arg-type]
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert program.spaces[0].room_type == RoomType.KITCHEN
        assert program.spaces[1].room_type == RoomType.WC


class TestNoGeometryLlmAvailable:
    """When no geometry but LLM is available, assembler uses from_llm_interpretation."""

    def test_uses_llm_interpretation(self) -> None:
        llm_rooms = [
            _StubLlmRoom(room_index=0, confirmed_label="Kitchen", room_type_enum="KITCHEN"),
            _StubLlmRoom(room_index=1, confirmed_label="Bedroom", room_type_enum="BEDROOM"),
        ]
        llm_interp = _StubLlmInterpretation(rooms=llm_rooms)
        pm = _StubPageMeasurements(
            rooms=None,
            llm_interpretation=llm_interp,  # type: ignore[arg-type]
            gross_area_sf=500.0,
        )
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert len(program.spaces) == 2
        assert all(s.source == SpaceSource.LLM for s in program.spaces)

    def test_uses_building_model_area_when_no_gross(self) -> None:
        llm_rooms = [
            _StubLlmRoom(room_index=0, confirmed_label="Kitchen", room_type_enum="KITCHEN"),
        ]
        llm_interp = _StubLlmInterpretation(rooms=llm_rooms)
        pm = _StubPageMeasurements(
            rooms=None,
            llm_interpretation=llm_interp,  # type: ignore[arg-type]
            gross_area_sf=None,
        )
        bm = _StubBuildingModel(gross_sf=800.0)

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert program.spaces[0].area_sf == 800.0


class TestNeitherAvailable:
    """When neither geometry nor LLM is available, uses from_building_model."""

    def test_uses_building_model_fallback(self) -> None:
        pm = _StubPageMeasurements(rooms=None, llm_interpretation=None)
        bm = _StubBuildingModel(gross_sf=1000.0)

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert len(program.spaces) > 0
        assert all(s.source == SpaceSource.ASSUMED for s in program.spaces)
        assert program.building_type == BuildingType.APARTMENT_LOW_RISE


class TestUnlabeledGeometryRoomsGetLlmLabels:
    """Unlabeled geometry rooms get re-classified from LLM data."""

    def test_unlabeled_rooms_reclassified(self) -> None:
        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
            _StubDetectedRoom(label=None, area_sf=80.0, room_index=1),
        ]
        llm_rooms = [
            _StubLlmRoom(room_index=0, confirmed_label="Kitchen", room_type_enum="KITCHEN"),
            _StubLlmRoom(room_index=1, confirmed_label="Utility Room", room_type_enum="UTILITY"),
        ]
        llm_interp = _StubLlmInterpretation(rooms=llm_rooms)
        pm = _StubPageMeasurements(
            rooms=rooms,  # type: ignore[arg-type]
            llm_interpretation=llm_interp,  # type: ignore[arg-type]
        )
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        # The originally-unlabeled room (index 1) should be reclassified
        reclassified = program.spaces[1]
        assert reclassified.room_type == RoomType.UTILITY
        assert reclassified.source == SpaceSource.LLM
        assert reclassified.name == "Utility Room"
        # The labeled room should remain GEOMETRY
        assert program.spaces[0].source == SpaceSource.GEOMETRY


class TestAreaGapCreatesUnaccounted:
    """reconcile_areas adds an Unaccounted space for the area gap."""

    def test_gap_creates_unaccounted_space(self) -> None:
        program = SpaceProgram(
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=120.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
                Space(
                    room_type=RoomType.LIVING_ROOM,
                    name="Living Room",
                    area_sf=200.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
            building_type=BuildingType.APARTMENT_LOW_RISE,
        )

        assembler = SpaceAssembler()
        reconciled = assembler.reconcile_areas(program, expected_total_sf=500.0)

        assert len(reconciled.spaces) == 3
        unaccounted = reconciled.spaces[2]
        assert unaccounted.name == "Unaccounted"
        assert unaccounted.room_type == RoomType.OTHER
        assert unaccounted.area_sf == pytest.approx(180.0, abs=0.1)
        assert unaccounted.source == SpaceSource.ASSUMED

    def test_no_gap_no_unaccounted(self) -> None:
        program = SpaceProgram(
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=500.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
            building_type=BuildingType.APARTMENT_LOW_RISE,
        )

        assembler = SpaceAssembler()
        reconciled = assembler.reconcile_areas(program, expected_total_sf=500.0)

        assert len(reconciled.spaces) == 1

    def test_negative_gap_no_unaccounted(self) -> None:
        """Rooms larger than expected — no unaccounted space added."""
        program = SpaceProgram(
            spaces=[
                Space(
                    room_type=RoomType.KITCHEN,
                    name="Kitchen",
                    area_sf=600.0,
                    source=SpaceSource.GEOMETRY,
                    confidence=Confidence.HIGH,
                ),
            ],
            building_type=BuildingType.APARTMENT_LOW_RISE,
        )

        assembler = SpaceAssembler()
        reconciled = assembler.reconcile_areas(program, expected_total_sf=500.0)

        assert len(reconciled.spaces) == 1


class TestAnomalyFlagging:
    """Anomaly flagging for oversized WC/bathroom."""

    def test_oversized_wc_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        rooms = [
            _StubDetectedRoom(label="WC", area_sf=300.0, room_index=0),
        ]
        pm = _StubPageMeasurements(rooms=rooms)  # type: ignore[arg-type]
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        with caplog.at_level("WARNING"):
            assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert any("Anomaly" in record.message for record in caplog.records)

    def test_normal_wc_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        rooms = [
            _StubDetectedRoom(label="WC", area_sf=50.0, room_index=0),
        ]
        pm = _StubPageMeasurements(rooms=rooms)  # type: ignore[arg-type]
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        with caplog.at_level("WARNING"):
            assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert not any("Anomaly" in record.message for record in caplog.records)


class TestLlmOnlyRoomsAdded:
    """LLM rooms not present in geometry are added to the program."""

    def test_missing_rooms_added_from_llm(self) -> None:
        rooms = [
            _StubDetectedRoom(label="KITCHEN", area_sf=120.0, room_index=0),
        ]
        llm_rooms = [
            _StubLlmRoom(room_index=0, confirmed_label="Kitchen", room_type_enum="KITCHEN"),
            # LLM found a pantry that geometry missed
            _StubLlmRoom(room_index=5, confirmed_label="Pantry", room_type_enum="STORAGE"),
        ]
        llm_interp = _StubLlmInterpretation(rooms=llm_rooms)
        pm = _StubPageMeasurements(
            rooms=rooms,  # type: ignore[arg-type]
            llm_interpretation=llm_interp,  # type: ignore[arg-type]
        )
        bm = _StubBuildingModel()

        assembler = SpaceAssembler()
        program = assembler.assemble(pm, bm)  # type: ignore[arg-type]

        assert len(program.spaces) == 2
        pantry = program.spaces[1]
        assert pantry.name == "Pantry"
        assert pantry.room_type == RoomType.STORAGE
        assert pantry.source == SpaceSource.LLM
        assert pantry.area_sf == 0.0
