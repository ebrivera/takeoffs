"""LLM-assisted geometry interpretation service.

Sends extracted geometry data (rooms, measurements, text) and optionally a
PDF page image to Claude for richer semantic analysis.  The LLM validates
and enriches computed geometry rather than guessing measurements from pixels.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import anthropic
from anthropic.types import ImageBlockParam, TextBlockParam

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomSummary:
    """Summary of a detected room for LLM input."""

    room_index: int
    label: str | None
    area_sf: float | None
    perimeter_lf: float | None


@dataclass(frozen=True)
class GeometrySummary:
    """Aggregated geometry data sent to the LLM for interpretation."""

    scale_notation: str | None
    scale_factor: float | None
    total_area_sf: float | None
    rooms: list[RoomSummary] = field(default_factory=list)
    all_text_blocks: list[str] = field(default_factory=list)
    wall_count: int = 0
    measurement_confidence: str = "UNKNOWN"


@dataclass(frozen=True)
class LlmRoomInterpretation:
    """LLM interpretation of a single room."""

    room_index: int
    confirmed_label: str
    room_type_enum: str
    notes: str


@dataclass(frozen=True)
class LlmInterpretation:
    """LLM semantic interpretation of extracted geometry."""

    building_type: str
    structural_system: str
    rooms: list[LlmRoomInterpretation] = field(default_factory=list)
    special_conditions: list[str] = field(default_factory=list)
    measurement_flags: list[str] = field(default_factory=list)
    confidence_notes: str = ""


# ---------------------------------------------------------------------------
# Default fallback
# ---------------------------------------------------------------------------

_DEFAULT_INTERPRETATION = LlmInterpretation(
    building_type="UNKNOWN",
    structural_system="UNKNOWN",
    rooms=[],
    special_conditions=[],
    measurement_flags=[],
    confidence_notes="LLM interpretation unavailable",
)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert construction analyst interpreting extracted geometry "
    "data from an architectural floor plan PDF.\n\n"
    "You will receive structured geometry data including detected rooms, "
    "measurements, scale information, and text blocks extracted from the "
    "drawing.  Optionally you may also receive an image of the page.\n\n"
    "Your task is to:\n"
    "1. Identify the building type (e.g. RESIDENTIAL, COMMERCIAL, "
    "INDUSTRIAL, MIXED_USE, INSTITUTIONAL).\n"
    "2. Infer the structural system (e.g. wood frame, steel frame, "
    "concrete frame, masonry bearing).\n"
    "3. Confirm or correct any detected room labels.\n"
    "4. **CRITICALLY**: Identify ALL rooms visible in the text blocks "
    "and/or drawing image, including rooms that the geometry engine "
    "did NOT detect.  Look for room name labels in the text blocks "
    "(e.g. LIVING ROOM, KITCHEN, DINING, BEDROOM, WC, UTILITY, "
    "LAUNDRY, PORCH, CLOSET, etc.).  Each visible room should be "
    "in the rooms array.  Use room_index starting from 0 for the "
    "first detected room, then continue incrementing for additional "
    "rooms you identify from the text.\n"
    "5. For each room, estimate its approximate area in square feet "
    "based on the dimension annotations visible in the text blocks "
    "and the total building area.  Put area estimates in the notes "
    "field as 'estimated_area_sf: <number>'.\n"
    "6. Assign a room_type_enum to each room from: LIVING_ROOM, "
    "KITCHEN, DINING, BEDROOM, BATHROOM, WC, UTILITY, LAUNDRY, "
    "CLOSET, PORCH, CORRIDOR, HALLWAY, GARAGE, ENTRY, FOYER, "
    "STORAGE, OFFICE, CONFERENCE, LOBBY, MECHANICAL_ROOM, "
    "COMMON_AREA, OTHER.\n"
    "7. Note any special conditions visible in the text or drawing "
    "(e.g. woodstove, chimney, hardwood floors, brick veneer).\n"
    "8. Flag any measurement concerns (e.g. unusually large/small rooms, "
    "missing scale, inconsistent dimensions).\n\n"
    "Output ONLY a JSON object matching this schema exactly:\n\n"
    "```json\n"
    "{\n"
    '  "building_type": "<RESIDENTIAL|COMMERCIAL|INDUSTRIAL|'
    'MIXED_USE|INSTITUTIONAL>",\n'
    '  "structural_system": "<string description>",\n'
    '  "rooms": [\n'
    "    {\n"
    '      "room_index": <int>,\n'
    '      "confirmed_label": "<string>",\n'
    '      "room_type_enum": "<see enum list above>",\n'
    '      "notes": "<string, include estimated_area_sf: <number> '
    'if area was estimated>"\n'
    "    }\n"
    "  ],\n"
    '  "special_conditions": ["<string>"],\n'
    '  "measurement_flags": ["<string>"],\n'
    '  "confidence_notes": "<string>"\n'
    "}\n"
    "```\n\n"
    "IMPORTANT:\n"
    "- Output ONLY the JSON block wrapped in ```json ... ``` fences.\n"
    "- Do not include reasoning text before or after the JSON.\n"
    "- Every field is required.\n"
    "- Include ALL rooms you can identify, not just the ones passed "
    "in the detected rooms list.\n"
)


# ---------------------------------------------------------------------------
# LLM Geometry Interpreter
# ---------------------------------------------------------------------------


class LlmGeometryInterpreter:
    """Sends extracted geometry to Claude for semantic interpretation."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        timeout: float = 30.0,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )
        self._model = model

    def interpret(
        self,
        geometry_summary: GeometrySummary,
        page_image_path: Path | None = None,
    ) -> LlmInterpretation:
        """Interpret geometry data using Claude.

        Parameters
        ----------
        geometry_summary
            Structured geometry data extracted from the drawing.
        page_image_path
            Optional path to a PNG image of the PDF page for vision input.

        Returns
        -------
        ``LlmInterpretation`` with semantic analysis, or a default fallback
        if the API call fails.
        """
        try:
            user_content = self._build_user_content(
                geometry_summary, page_image_path
            )
            raw_response = self._call_api(user_content)
            result = self._parse_response(raw_response)
            if result is not None:
                return result
            logger.warning("Could not parse LLM geometry response")
            return _DEFAULT_INTERPRETATION
        except Exception:
            logger.exception("LLM geometry interpretation failed")
            return _DEFAULT_INTERPRETATION

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_content(
        summary: GeometrySummary,
        image_path: Path | None,
    ) -> list[ImageBlockParam | TextBlockParam]:
        """Build the user message content with geometry data and optional image."""
        parts: list[ImageBlockParam | TextBlockParam] = []

        # Optionally include page image.
        if image_path is not None and image_path.exists():
            image_data = base64.b64encode(
                image_path.read_bytes()
            ).decode("utf-8")
            suffix = image_path.suffix.lower()
            media_type: Literal[
                "image/jpeg", "image/png", "image/gif", "image/webp"
            ] = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
            parts.append(
                ImageBlockParam(
                    type="image",
                    source={
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                )
            )

        # Build structured text summary.
        text = _serialize_geometry_summary(summary)
        parts.append(TextBlockParam(type="text", text=text))
        return parts

    def _call_api(
        self,
        user_content: list[ImageBlockParam | TextBlockParam],
    ) -> str:
        """Call the Anthropic Messages API."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text_blocks = [
            block.text for block in response.content if block.type == "text"
        ]
        return "\n".join(text_blocks)

    @staticmethod
    def _parse_response(raw_response: str) -> LlmInterpretation | None:
        """Parse a raw LLM response into an ``LlmInterpretation``."""
        json_str = _extract_json(raw_response)
        if json_str is None:
            logger.warning("No JSON block found in LLM geometry response")
            return None

        try:
            data: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in LLM geometry response")
            return None

        return _build_interpretation(data)


# ---------------------------------------------------------------------------
# Serialization / parsing helpers (module-level for testability)
# ---------------------------------------------------------------------------


def _serialize_geometry_summary(summary: GeometrySummary) -> str:
    """Serialize a ``GeometrySummary`` to a human-readable text block."""
    lines = ["## Extracted Geometry Data\n"]

    lines.append(f"Scale notation: {summary.scale_notation or 'not detected'}")
    lines.append(f"Scale factor: {summary.scale_factor or 'unknown'}")
    lines.append(f"Total area (SF): {summary.total_area_sf or 'unknown'}")
    lines.append(f"Wall count: {summary.wall_count}")
    lines.append(f"Measurement confidence: {summary.measurement_confidence}")

    if summary.rooms:
        lines.append(f"\n### Detected Rooms ({len(summary.rooms)})\n")
        for room in summary.rooms:
            label = room.label or "(unlabeled)"
            area = f"{room.area_sf:.1f} SF" if room.area_sf else "unknown"
            perim = (
                f"{room.perimeter_lf:.1f} LF" if room.perimeter_lf else "unknown"
            )
            lines.append(
                f"- Room {room.room_index}: {label} — {area}, {perim}"
            )

    if summary.all_text_blocks:
        lines.append(f"\n### Text Blocks ({len(summary.all_text_blocks)})\n")
        # Show up to 50 text blocks to keep context manageable.
        for tb in summary.all_text_blocks[:50]:
            lines.append(f"- {tb}")
        if len(summary.all_text_blocks) > 50:
            lines.append(
                f"... and {len(summary.all_text_blocks) - 50} more"
            )

    return "\n".join(lines)


def _extract_json(text: str) -> str | None:
    """Extract JSON from ```json ... ``` code fences."""
    start = text.find("```json")
    if start == -1:
        start = text.find("```")
        if start == -1:
            return None
        start += 3
    else:
        start += 7

    end = text.find("```", start)
    if end == -1:
        return None

    return text[start:end].strip()


def _build_interpretation(data: dict[str, Any]) -> LlmInterpretation | None:
    """Build an ``LlmInterpretation`` from parsed JSON data."""
    try:
        rooms: list[LlmRoomInterpretation] = []
        for room_data in data.get("rooms", []):
            rooms.append(
                LlmRoomInterpretation(
                    room_index=int(room_data["room_index"]),
                    confirmed_label=str(room_data["confirmed_label"]),
                    room_type_enum=str(room_data["room_type_enum"]),
                    notes=str(room_data.get("notes", "")),
                )
            )

        return LlmInterpretation(
            building_type=str(data.get("building_type", "UNKNOWN")),
            structural_system=str(data.get("structural_system", "UNKNOWN")),
            rooms=rooms,
            special_conditions=[
                str(s) for s in data.get("special_conditions", [])
            ],
            measurement_flags=[
                str(s) for s in data.get("measurement_flags", [])
            ],
            confidence_notes=str(data.get("confidence_notes", "")),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("Failed to build LlmInterpretation from response data")
        return None
