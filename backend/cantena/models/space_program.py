"""Space program model bridging detected rooms to cost estimation.

A SpaceProgram can be populated from three sources:
  1. PRD 3.75 DetectedRoom polygons (highest accuracy, source=GEOMETRY)
  2. LLM interpretation room breakdown (source=LLM)
  3. Default distribution from BuildingModel (source=ASSUMED)

This ensures the cost engine always has a room-by-room program to price.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from cantena.models.enums import BuildingType, Confidence, RoomType

if TYPE_CHECKING:
    from cantena.geometry.rooms import DetectedRoom
    from cantena.models.building import BuildingModel
    from cantena.services.llm_geometry_interpreter import LlmInterpretation


class SpaceSource(StrEnum):
    """Source of a space's data."""

    GEOMETRY = "geometry"
    LLM = "llm"
    ASSUMED = "assumed"
    USER_OVERRIDE = "user_override"


# Map DetectedRoom.label (uppercase, as found on drawings) to RoomType.
LABEL_TO_ROOM_TYPE: dict[str, RoomType] = {
    "LIVING ROOM": RoomType.LIVING_ROOM,
    "KITCHEN": RoomType.KITCHEN,
    "WC": RoomType.WC,
    "UTILITY": RoomType.UTILITY,
    "DINING": RoomType.DINING,
    "DINING ROOM": RoomType.DINING,
    "LAUNDRY": RoomType.LAUNDRY,
    "COATS": RoomType.CLOSET,
    "FRONT PORCH": RoomType.PORCH,
    "BACK PORCH": RoomType.PORCH,
    "BEDROOM": RoomType.BEDROOM,
    "BATHROOM": RoomType.BATHROOM,
    "RESTROOM": RoomType.RESTROOM,
    "CLOSET": RoomType.CLOSET,
    "HALLWAY": RoomType.HALLWAY,
    "CORRIDOR": RoomType.CORRIDOR,
    "GARAGE": RoomType.GARAGE,
    "PORCH": RoomType.PORCH,
    "ENTRY": RoomType.ENTRY,
    "FOYER": RoomType.FOYER,
    "LOBBY": RoomType.LOBBY,
    "OFFICE": RoomType.OPEN_OFFICE,
    "CONFERENCE": RoomType.CONFERENCE,
    "STORAGE": RoomType.STORAGE,
    "MECHANICAL": RoomType.MECHANICAL_ROOM,
    "MASTER BEDROOM": RoomType.BEDROOM,
    "MASTER BATH": RoomType.BATHROOM,
    "FAMILY ROOM": RoomType.LIVING_ROOM,
    "DEN": RoomType.LIVING_ROOM,
    "STUDY": RoomType.PRIVATE_OFFICE,
    "PANTRY": RoomType.STORAGE,
    "MUDROOM": RoomType.ENTRY,
    "SUNROOM": RoomType.LIVING_ROOM,
    "BREAKFAST": RoomType.DINING,
    "NOOK": RoomType.DINING,
    "LINEN": RoomType.CLOSET,
}


class Space(BaseModel):
    """A single space in a space program."""

    room_type: RoomType  # noqa: TCH001
    name: str
    area_sf: float
    count: int = 1
    source: SpaceSource  # noqa: TCH001
    confidence: Confidence  # noqa: TCH001


class SpaceProgram(BaseModel):
    """Room-by-room program for cost estimation."""

    spaces: list[Space] = Field(default_factory=list)
    building_type: BuildingType  # noqa: TCH001

    @property
    def total_area_sf(self) -> float:
        """Sum of all space areas."""
        return sum(s.area_sf * s.count for s in self.spaces)

    @classmethod
    def from_detected_rooms(
        cls,
        rooms: list[DetectedRoom],
        building_type: BuildingType,
    ) -> SpaceProgram:
        """Build a SpaceProgram from geometry-detected room polygons."""
        spaces: list[Space] = []
        for room in rooms:
            label_upper = room.label.strip().upper() if room.label else ""
            # Strip numeric suffix for mapping (e.g., "BEDROOM 1" -> "BEDROOM")
            base_label = label_upper.rsplit(" ", 1)[0] if label_upper else ""

            room_type = (
                LABEL_TO_ROOM_TYPE.get(label_upper)
                or LABEL_TO_ROOM_TYPE.get(base_label)
                or RoomType.OTHER
            )
            name = room.label if room.label else f"Room {room.room_index}"
            area_sf = room.area_sf if room.area_sf is not None else 0.0

            spaces.append(Space(
                room_type=room_type,
                name=name,
                area_sf=area_sf,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ))
        return cls(spaces=spaces, building_type=building_type)

    @classmethod
    def from_llm_interpretation(
        cls,
        interp: LlmInterpretation,
        total_area_sf: float,
        building_type: BuildingType,
    ) -> SpaceProgram:
        """Build a SpaceProgram from LLM-interpreted room data.

        Tries to extract per-room area estimates from the LLM notes
        (``estimated_area_sf: <number>``).  Falls back to equal
        distribution if no estimates are found.
        """
        import re

        spaces: list[Space] = []
        estimated_areas: dict[int, float] = {}

        # First pass: extract any area estimates from notes
        for i, llm_room in enumerate(interp.rooms):
            match = re.search(
                r"estimated_area_sf\s*:\s*([\d.]+)", llm_room.notes
            )
            if match:
                estimated_areas[i] = float(match.group(1))

        # Distribute area: use estimates when available, equal split otherwise
        has_estimates = bool(estimated_areas)
        estimated_total = sum(estimated_areas.values()) if has_estimates else 0.0

        for i, llm_room in enumerate(interp.rooms):
            # Try to map LLM room_type_enum string to RoomType
            try:
                room_type = RoomType(llm_room.room_type_enum.lower())
            except ValueError:
                room_type = RoomType.OTHER

            if has_estimates and i in estimated_areas:
                # Use the LLM's area estimate, scaled to match total
                if estimated_total > 0:
                    area_sf = (
                        estimated_areas[i] / estimated_total * total_area_sf
                    )
                else:
                    area_sf = estimated_areas[i]
            elif has_estimates:
                # This room has no estimate; give it a share of the remainder
                remaining = total_area_sf - sum(
                    estimated_areas[j] / estimated_total * total_area_sf
                    for j in estimated_areas
                ) if estimated_total > 0 else total_area_sf
                unestimated_count = len(interp.rooms) - len(estimated_areas)
                area_sf = (
                    remaining / unestimated_count
                    if unestimated_count > 0
                    else 0.0
                )
            else:
                # No estimates at all — equal split
                area_sf = (
                    total_area_sf / len(interp.rooms)
                    if interp.rooms
                    else 0.0
                )

            spaces.append(Space(
                room_type=room_type,
                name=llm_room.confirmed_label,
                area_sf=area_sf,
                source=SpaceSource.LLM,
                confidence=Confidence.MEDIUM,
            ))
        return cls(spaces=spaces, building_type=building_type)

    @classmethod
    def from_building_model(
        cls,
        model: BuildingModel,
    ) -> SpaceProgram:
        """Build a SpaceProgram using typical room distributions."""
        from cantena.data.room_costs import get_room_costs_for_building_type

        room_costs = get_room_costs_for_building_type(model.building_type)
        spaces: list[Space] = []
        for rc in room_costs:
            area_sf = model.gross_sf * rc.typical_percent_of_building / 100.0
            spaces.append(Space(
                room_type=rc.room_type,
                name=rc.room_type.value.replace("_", " ").title(),
                area_sf=area_sf,
                source=SpaceSource.ASSUMED,
                confidence=Confidence.LOW,
            ))
        return cls(spaces=spaces, building_type=model.building_type)

    def update_space(
        self,
        index: int,
        area_sf: float | None = None,
        room_type: RoomType | None = None,
        name: str | None = None,
    ) -> None:
        """Update a space and mark it as user-overridden."""
        space = self.spaces[index]
        if area_sf is not None:
            space.area_sf = area_sf
        if room_type is not None:
            space.room_type = room_type
        if name is not None:
            space.name = name
        space.source = SpaceSource.USER_OVERRIDE
