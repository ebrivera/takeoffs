"""End-to-end LLM + SpaceAssembler tests on first-floor.pdf.

Exercises the full pipeline (PDF -> geometry -> LLM enrichment -> SpaceAssembler)
with real Anthropic API calls.  All tests share a single session-scoped API call
via the ``llm_page_measurements`` fixture in conftest.py.

Skipped gracefully when ANTHROPIC_API_KEY is not set or on 429 rate-limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cantena.models.enums import RoomType
from cantena.models.space_program import SpaceSource
from cantena.services.space_assembler import SpaceAssembler

if TYPE_CHECKING:
    from cantena.geometry.measurement import PageMeasurements

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLlmIdentifiesUnlabeledKitchen:
    """Room 0 (unlabeled by geometry) should be identified as Kitchen by LLM."""

    def test_llm_identifies_unlabeled_kitchen(
        self,
        llm_page_measurements: PageMeasurements,
    ) -> None:
        result = llm_page_measurements
        interp = result.llm_interpretation
        assert interp is not None, "LLM interpretation is None"

        # Find room_index 0 in LLM interpretation
        room_0 = next(
            (r for r in interp.rooms if r.room_index == 0), None
        )
        assert room_0 is not None, (
            "LLM did not interpret room_index 0; "
            f"indices present: {[r.room_index for r in interp.rooms]}"
        )

        label_upper = room_0.confirmed_label.strip().upper()
        type_upper = room_0.room_type_enum.strip().upper()
        assert "KITCHEN" in label_upper or "KITCHEN" in type_upper, (
            f"Expected LLM to identify room 0 as Kitchen, "
            f"got label={room_0.confirmed_label!r}, "
            f"type={room_0.room_type_enum!r}"
        )

        print(
            f"\n  Room 0 identified: {room_0.confirmed_label} "
            f"({room_0.room_type_enum})"
        )


class TestLlmFindsRoomsGeometryMissed:
    """LLM should find rooms beyond geometry's detections."""

    def test_llm_finds_rooms_geometry_missed(
        self,
        llm_page_measurements: PageMeasurements,
    ) -> None:
        result = llm_page_measurements
        interp = result.llm_interpretation
        assert interp is not None, "LLM interpretation is None"

        geometry_rooms = result.rooms or []
        geometry_count = len(geometry_rooms)
        llm_count = len(interp.rooms)

        assert llm_count > geometry_count, (
            f"Expected LLM to find more rooms than geometry. "
            f"Geometry: {geometry_count}, LLM: {llm_count}"
        )

        # Check that LLM found common rooms like Laundry or Porch
        llm_labels = {r.confirmed_label.upper() for r in interp.rooms}
        llm_types = {r.room_type_enum.upper() for r in interp.rooms}
        extra_keywords = {"LAUNDRY", "PORCH", "FRONT PORCH", "BACK PORCH"}
        found = (llm_labels | llm_types) & extra_keywords

        print(f"\n  Geometry rooms: {geometry_count}")
        print(f"  LLM rooms: {llm_count}")
        print(f"  LLM labels: {sorted(llm_labels)}")
        print(f"  Extra rooms found: {sorted(found)}")


class TestSpaceAssemblerUsesGeometryPlusLlm:
    """Full SpaceAssembler.assemble() with real PageMeasurements."""

    def test_space_assembler_uses_geometry_plus_llm(
        self,
        llm_page_measurements: PageMeasurements,
    ) -> None:
        from cantena.models.building import BuildingModel, ComplexityScores, Location
        from cantena.models.enums import (
            BuildingType,
            Confidence,
            ExteriorWall,
            MechanicalSystem,
            StructuralSystem,
        )

        result = llm_page_measurements

        # Build a minimal BuildingModel matching the farmhouse
        building = BuildingModel(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            building_use="Single-family residential",
            gross_sf=result.gross_area_sf or 512.0,
            stories=1,
            story_height_ft=9.0,
            structural_system=StructuralSystem.WOOD_FRAME,
            exterior_wall_system=ExteriorWall.WOOD_SIDING,
            mechanical_system=MechanicalSystem.SPLIT_SYSTEM,
            location=Location(city="Rural", state="VA"),
            complexity_scores=ComplexityScores(
                structural=2, mep=2, finishes=2, site=1,
            ),
            confidence={
                "building_type": Confidence.MEDIUM,
                "gross_sf": Confidence.HIGH,
            },
        )

        assembler = SpaceAssembler()
        program = assembler.assemble(result, building)

        # Geometry path should be used (polygonize succeeded)
        assert result.polygonize_success, (
            "Expected polygonize_success=True for geometry-primary path"
        )

        sources = {s.source for s in program.spaces}
        geometry_rooms = result.rooms or []

        # At least one space from geometry
        assert SpaceSource.GEOMETRY in sources, (
            f"No GEOMETRY-sourced spaces; sources: {sources}"
        )

        # At least one space enriched/added by LLM
        assert SpaceSource.LLM in sources, (
            f"No LLM-sourced spaces; sources: {sources}"
        )

        # Total spaces > geometry room count (LLM added rooms)
        assert len(program.spaces) > len(geometry_rooms), (
            f"Expected more spaces than geometry rooms. "
            f"Spaces: {len(program.spaces)}, Geometry rooms: {len(geometry_rooms)}"
        )

        print(f"\n  Polygonize success: {result.polygonize_success}")
        print(f"  Total spaces: {len(program.spaces)}")
        print(f"  Sources: {sources}")
        for s in program.spaces:
            print(
                f"    {s.name} ({s.room_type.value}) — "
                f"{s.area_sf:.1f} SF [{s.source.value}]"
            )


class TestLlmEnrichmentReclassifiesUnlabeledRooms:
    """No RoomType.OTHER should remain after LLM enrichment."""

    def test_llm_enrichment_reclassifies_unlabeled_rooms(
        self,
        llm_page_measurements: PageMeasurements,
    ) -> None:
        from cantena.models.building import BuildingModel, ComplexityScores, Location
        from cantena.models.enums import (
            BuildingType,
            Confidence,
            ExteriorWall,
            MechanicalSystem,
            StructuralSystem,
        )

        result = llm_page_measurements

        building = BuildingModel(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            building_use="Single-family residential",
            gross_sf=result.gross_area_sf or 512.0,
            stories=1,
            story_height_ft=9.0,
            structural_system=StructuralSystem.WOOD_FRAME,
            exterior_wall_system=ExteriorWall.WOOD_SIDING,
            mechanical_system=MechanicalSystem.SPLIT_SYSTEM,
            location=Location(city="Rural", state="VA"),
            complexity_scores=ComplexityScores(
                structural=2, mep=2, finishes=2, site=1,
            ),
            confidence={
                "building_type": Confidence.MEDIUM,
                "gross_sf": Confidence.HIGH,
            },
        )

        assembler = SpaceAssembler()
        program = assembler.assemble(result, building)

        other_spaces = [
            s for s in program.spaces if s.room_type == RoomType.OTHER
        ]

        print(f"\n  Total spaces: {len(program.spaces)}")
        print(f"  OTHER spaces: {len(other_spaces)}")
        if other_spaces:
            for s in other_spaces:
                print(f"    {s.name} — {s.area_sf:.1f} SF [{s.source.value}]")

        assert len(other_spaces) == 0, (
            f"Expected no OTHER rooms after LLM enrichment, "
            f"got {len(other_spaces)}: "
            f"{[(s.name, s.area_sf) for s in other_spaces]}"
        )


class TestGeometryVsLlmRoomCountComparison:
    """Diagnostic: LLM should find >= geometry room count."""

    def test_geometry_vs_llm_room_count_comparison(
        self,
        llm_page_measurements: PageMeasurements,
    ) -> None:
        result = llm_page_measurements
        interp = result.llm_interpretation
        assert interp is not None, "LLM interpretation is None"

        geometry_rooms = result.rooms or []
        geometry_count = len(geometry_rooms)
        llm_count = len(interp.rooms)

        print("\n=== GEOMETRY vs LLM ROOM COMPARISON ===")
        print(f"  Geometry detected: {geometry_count} rooms")
        for r in geometry_rooms:
            label = r.label or "(unlabeled)"
            area = f"{r.area_sf:.1f} SF" if r.area_sf else "N/A"
            print(f"    [{r.room_index}] {label} — {area}")

        print(f"\n  LLM identified: {llm_count} rooms")
        for r in interp.rooms:
            print(
                f"    [{r.room_index}] {r.confirmed_label} "
                f"({r.room_type_enum}) — {r.notes}"
            )
        print("========================================")

        assert llm_count >= geometry_count, (
            f"LLM found fewer rooms ({llm_count}) "
            f"than geometry ({geometry_count})"
        )
