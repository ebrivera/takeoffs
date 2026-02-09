"""SpaceProgram assembly: merge geometry rooms with LLM enrichment.

Assembles the best possible SpaceProgram by merging geometry-detected rooms
with LLM interpretation, filling gaps and resolving conflicts.

Priority:
  1. Geometry-detected rooms from PageMeasurements (highest accuracy)
  2. LLM interpretation room breakdown
  3. Default distribution from BuildingModel (fallback)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cantena.geometry.measurement import PageMeasurements
    from cantena.models.building import BuildingModel
    from cantena.services.llm_geometry_interpreter import LlmInterpretation

from cantena.models.enums import Confidence, RoomType
from cantena.models.space_program import (
    LABEL_TO_ROOM_TYPE,
    Space,
    SpaceProgram,
    SpaceSource,
)

logger = logging.getLogger(__name__)

# WC / bathroom typical max area in SF — flag if larger.
_WC_MAX_AREA_SF = 150.0


class SpaceAssembler:
    """Assembles a SpaceProgram from the best available data source."""

    def assemble(
        self,
        page_measurements: PageMeasurements,
        building_model: BuildingModel,
    ) -> SpaceProgram:
        """Build the best possible SpaceProgram from available data.

        Priority:
          1. If geometry rooms exist with labels → ``from_detected_rooms``
          2. Else if LLM interpretation has rooms → ``from_llm_interpretation``
          3. Else fallback → ``from_building_model``

        When using geometry rooms, LLM interpretation is also consulted to
        re-classify unlabeled rooms, add missing rooms, and flag anomalies.
        """
        rooms = page_measurements.rooms
        llm_interp = page_measurements.llm_interpretation

        # Geometry rooms are only trusted when polygonize actually
        # produced real room polygons (polygonize_success=True).
        # A single convex-hull fallback room (polygonize_success=False)
        # should NOT be preferred over LLM-interpreted room breakdown.
        has_real_geometry_rooms = bool(
            rooms
            and len(rooms) > 0
            and page_measurements.polygonize_success
        )
        has_geometry_rooms = bool(rooms and len(rooms) > 0)
        has_llm_rooms = bool(
            llm_interp is not None and len(llm_interp.rooms) > 0
        )

        if has_real_geometry_rooms:
            assert rooms is not None  # for mypy
            program = SpaceProgram.from_detected_rooms(
                rooms, building_model.building_type
            )
            # Enrich with LLM data if available
            if has_llm_rooms:
                assert llm_interp is not None  # for mypy
                program = self._enrich_with_llm(program, llm_interp)
            # Flag anomalies on all spaces
            for space in program.spaces:
                _flag_anomalies(space)
            return program

        if has_llm_rooms:
            assert llm_interp is not None  # for mypy
            total_area = (
                page_measurements.gross_area_sf
                if page_measurements.gross_area_sf is not None
                else building_model.gross_sf
            )
            return SpaceProgram.from_llm_interpretation(
                llm_interp, total_area, building_model.building_type
            )

        return SpaceProgram.from_building_model(building_model)

    def reconcile_areas(
        self,
        program: SpaceProgram,
        expected_total_sf: float,
    ) -> SpaceProgram:
        """Add an Unaccounted space if detected rooms don't cover expected area.

        Rooms are never scaled — the gap is made explicit as an OTHER space.
        """
        detected_total = program.total_area_sf
        gap = expected_total_sf - detected_total

        if gap <= 0:
            return program

        unaccounted = Space(
            room_type=RoomType.OTHER,
            name="Unaccounted",
            area_sf=gap,
            source=SpaceSource.ASSUMED,
            confidence=Confidence.LOW,
        )
        return SpaceProgram(
            spaces=[*program.spaces, unaccounted],
            building_type=program.building_type,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_with_llm(
        program: SpaceProgram,
        llm_interp: LlmInterpretation,
    ) -> SpaceProgram:
        """Enrich geometry-based SpaceProgram with LLM interpretation.

        1. Re-classify unlabeled (OTHER) rooms using LLM suggestions.
        2. Add rooms the LLM found but geometry missed.
        3. Flag anomalies (e.g., WC with unreasonably large area).
        """
        # Build LLM room lookup by index
        llm_by_index = {r.room_index: r for r in llm_interp.rooms}

        updated_spaces: list[Space] = []
        for space in program.spaces:
            # Try to re-classify unlabeled rooms via LLM
            if space.room_type == RoomType.OTHER:
                # Find matching LLM room by index
                llm_room = llm_by_index.get(
                    program.spaces.index(space)
                )
                if llm_room is not None:
                    # Try label-based mapping first
                    label_upper = llm_room.confirmed_label.strip().upper()
                    mapped = LABEL_TO_ROOM_TYPE.get(label_upper)
                    if mapped is None:
                        # Try room_type_enum directly
                        try:
                            mapped = RoomType(
                                llm_room.room_type_enum.lower()
                            )
                        except ValueError:
                            mapped = None

                    if mapped is not None:
                        space = Space(
                            room_type=mapped,
                            name=llm_room.confirmed_label,
                            area_sf=space.area_sf,
                            count=space.count,
                            source=SpaceSource.LLM,
                            confidence=Confidence.MEDIUM,
                        )
            updated_spaces.append(space)

        # Add LLM-only rooms (indices not present in geometry)
        geometry_indices = set(range(len(program.spaces)))
        for llm_room in llm_interp.rooms:
            if llm_room.room_index not in geometry_indices:
                try:
                    room_type = RoomType(llm_room.room_type_enum.lower())
                except ValueError:
                    room_type = RoomType.OTHER
                updated_spaces.append(Space(
                    room_type=room_type,
                    name=llm_room.confirmed_label,
                    area_sf=0.0,
                    source=SpaceSource.LLM,
                    confidence=Confidence.LOW,
                ))

        return SpaceProgram(
            spaces=updated_spaces,
            building_type=program.building_type,
        )


def _flag_anomalies(space: Space) -> None:
    """Log warnings for anomalous room data."""
    if (
        space.room_type in (RoomType.WC, RoomType.BATHROOM, RoomType.RESTROOM)
        and space.area_sf > _WC_MAX_AREA_SF
    ):
        logger.warning(
            "Anomaly: %s (%s) has area %.1f SF (expected < %.0f SF)",
            space.name,
            space.room_type.value,
            space.area_sf,
            _WC_MAX_AREA_SF,
        )
