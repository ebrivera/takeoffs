"""Tests for the LLM geometry interpretation service — all API calls are mocked."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from cantena.services.llm_geometry_interpreter import (
    GeometrySummary,
    LlmGeometryInterpreter,
    RoomSummary,
    _serialize_geometry_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_interpretation_json(
    building_type: str = "RESIDENTIAL",
    structural_system: str = "wood frame",
    rooms: list[dict[str, Any]] | None = None,
    special_conditions: list[str] | None = None,
    measurement_flags: list[str] | None = None,
    confidence_notes: str = "All measurements appear consistent.",
) -> str:
    """Build a well-formed LLM response string with JSON."""
    if rooms is None:
        rooms = [
            {
                "room_index": 0,
                "confirmed_label": "LIVING ROOM",
                "room_type_enum": "LIVING",
                "notes": "Open plan, connected to kitchen",
            },
            {
                "room_index": 1,
                "confirmed_label": "KITCHEN",
                "room_type_enum": "KITCHEN",
                "notes": "Galley style layout",
            },
            {
                "room_index": 2,
                "confirmed_label": "BEDROOM",
                "room_type_enum": "BEDROOM",
                "notes": "",
            },
        ]

    data: dict[str, Any] = {
        "building_type": building_type,
        "structural_system": structural_system,
        "rooms": rooms,
        "special_conditions": special_conditions or ["woodstove", "hardwood floors"],
        "measurement_flags": measurement_flags or [],
        "confidence_notes": confidence_notes,
    }

    json_str = json.dumps(data, indent=2)
    return f"```json\n{json_str}\n```"


def _mock_api_response(text: str) -> MagicMock:
    """Create a mock Anthropic API response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response = MagicMock()
    response.content = [text_block]
    return response


def _make_summary() -> GeometrySummary:
    """Create a sample GeometrySummary for testing."""
    return GeometrySummary(
        scale_notation='1/4" = 1\'-0"',
        scale_factor=48.0,
        total_area_sf=512.0,
        rooms=[
            RoomSummary(room_index=0, label="LIVING ROOM", area_sf=180.0, perimeter_lf=54.0),
            RoomSummary(room_index=1, label="KITCHEN", area_sf=120.0, perimeter_lf=44.0),
            RoomSummary(room_index=2, label=None, area_sf=80.0, perimeter_lf=36.0),
        ],
        all_text_blocks=["LIVING ROOM", "KITCHEN", "SCALE: 1/4\" = 1'-0\"", "24'-0\""],
        wall_count=42,
        measurement_confidence="HIGH",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def interpreter() -> LlmGeometryInterpreter:
    """Create an LlmGeometryInterpreter with a fake API key."""
    return LlmGeometryInterpreter(api_key="test-key-not-real")


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """Create a minimal PNG image for testing."""
    import struct
    import zlib

    def _create_png() -> bytes:
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
        raw_data = zlib.compress(b"\x00\xff\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw_data) & 0xFFFFFFFF
        idat = struct.pack(">I", len(raw_data)) + b"IDAT" + raw_data + struct.pack(">I", idat_crc)
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        return signature + ihdr + idat + iend

    img_path = tmp_path / "page.png"
    img_path.write_bytes(_create_png())
    return img_path


# ---------------------------------------------------------------------------
# Tests: well-formed response parsing
# ---------------------------------------------------------------------------


class TestWellFormedResponse:
    def test_parse_valid_response(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """LLM returns well-formed JSON — should produce a valid LlmInterpretation."""
        mock_response = _mock_api_response(_make_interpretation_json())
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "RESIDENTIAL"
        assert result.structural_system == "wood frame"
        assert len(result.rooms) == 3
        assert result.rooms[0].confirmed_label == "LIVING ROOM"
        assert result.rooms[0].room_type_enum == "LIVING"
        assert result.rooms[1].confirmed_label == "KITCHEN"
        assert result.rooms[2].confirmed_label == "BEDROOM"
        assert "woodstove" in result.special_conditions
        assert "hardwood floors" in result.special_conditions
        assert result.confidence_notes == "All measurements appear consistent."

    def test_rooms_parsed_with_notes(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """Room notes are preserved in the interpretation."""
        mock_response = _mock_api_response(_make_interpretation_json())
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.rooms[0].notes == "Open plan, connected to kitchen"
        assert result.rooms[1].notes == "Galley style layout"

    def test_measurement_flags_parsed(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """Measurement flags are correctly parsed."""
        response_text = _make_interpretation_json(
            measurement_flags=["Room 2 area seems small", "Scale not verified"]
        )
        mock_response = _mock_api_response(response_text)
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert len(result.measurement_flags) == 2
        assert "Room 2 area seems small" in result.measurement_flags

    def test_empty_rooms_list(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """LLM response with empty rooms list is valid."""
        response_text = _make_interpretation_json(rooms=[])
        mock_response = _mock_api_response(response_text)
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.rooms == []
        assert result.building_type == "RESIDENTIAL"


# ---------------------------------------------------------------------------
# Tests: malformed response fallback
# ---------------------------------------------------------------------------


class TestMalformedResponse:
    def test_no_json_returns_default(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """Response without JSON block -> default fallback."""
        mock_response = _mock_api_response("I cannot analyze this geometry data.")
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "UNKNOWN"
        assert result.structural_system == "UNKNOWN"
        assert result.rooms == []
        assert result.confidence_notes == "LLM interpretation unavailable"

    def test_invalid_json_returns_default(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """Invalid JSON in code fence -> default fallback."""
        mock_response = _mock_api_response("```json\n{invalid json}\n```")
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "UNKNOWN"
        assert result.confidence_notes == "LLM interpretation unavailable"

    def test_missing_rooms_key_uses_empty(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """JSON missing 'rooms' key returns interpretation with empty rooms."""
        data = {
            "building_type": "COMMERCIAL",
            "structural_system": "steel frame",
            "special_conditions": [],
            "measurement_flags": [],
            "confidence_notes": "Partial data.",
        }
        response_text = f"```json\n{json.dumps(data)}\n```"
        mock_response = _mock_api_response(response_text)
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "COMMERCIAL"
        assert result.rooms == []


# ---------------------------------------------------------------------------
# Tests: timeout and API error fallback
# ---------------------------------------------------------------------------


class TestTimeoutFallback:
    def test_timeout_returns_default(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """API timeout returns default fallback."""
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages,
            "create",
            side_effect=anthropic.APITimeoutError(request=MagicMock()),
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "UNKNOWN"
        assert result.confidence_notes == "LLM interpretation unavailable"

    def test_api_error_returns_default(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """Generic API error returns default fallback."""
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages,
            "create",
            side_effect=anthropic.APIConnectionError(request=MagicMock()),
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "UNKNOWN"

    def test_rate_limit_returns_default(
        self, interpreter: LlmGeometryInterpreter
    ) -> None:
        """429 rate limit returns default fallback."""
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages,
            "create",
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
        ):
            result = interpreter.interpret(summary)

        assert result.building_type == "UNKNOWN"


# ---------------------------------------------------------------------------
# Tests: GeometrySummary serialization
# ---------------------------------------------------------------------------


class TestGeometrySummarySerialization:
    def test_serialize_full_summary(self) -> None:
        """Full GeometrySummary serializes to readable text."""
        summary = _make_summary()
        text = _serialize_geometry_summary(summary)

        assert "Scale notation: 1/4" in text
        assert "Scale factor: 48.0" in text
        assert "Total area (SF): 512.0" in text
        assert "Wall count: 42" in text
        assert "Measurement confidence: HIGH" in text
        assert "LIVING ROOM" in text
        assert "180.0 SF" in text
        assert "(unlabeled)" in text
        assert "SCALE:" in text

    def test_serialize_empty_summary(self) -> None:
        """Empty GeometrySummary serializes without errors."""
        summary = GeometrySummary(
            scale_notation=None,
            scale_factor=None,
            total_area_sf=None,
        )
        text = _serialize_geometry_summary(summary)

        assert "not detected" in text
        assert "unknown" in text

    def test_serialize_many_text_blocks(self) -> None:
        """More than 50 text blocks are truncated."""
        blocks = [f"TEXT_{i}" for i in range(60)]
        summary = GeometrySummary(
            scale_notation=None,
            scale_factor=None,
            total_area_sf=None,
            all_text_blocks=blocks,
        )
        text = _serialize_geometry_summary(summary)

        assert "TEXT_49" in text
        assert "TEXT_50" not in text
        assert "10 more" in text


# ---------------------------------------------------------------------------
# Tests: vision input
# ---------------------------------------------------------------------------


class TestVisionInput:
    def test_image_included_when_provided(
        self,
        interpreter: LlmGeometryInterpreter,
        sample_image: Path,
    ) -> None:
        """When page_image_path provided, image is sent to API."""
        mock_response = _mock_api_response(_make_interpretation_json())
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ) as mock_create:
            interpreter.interpret(summary, page_image_path=sample_image)

        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[0]["content"]
        image_parts = [p for p in user_content if p["type"] == "image"]
        assert len(image_parts) == 1
        assert image_parts[0]["source"]["media_type"] == "image/png"

    def test_no_image_when_path_none(
        self,
        interpreter: LlmGeometryInterpreter,
    ) -> None:
        """When page_image_path is None, no image is sent."""
        mock_response = _mock_api_response(_make_interpretation_json())
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ) as mock_create:
            interpreter.interpret(summary, page_image_path=None)

        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[0]["content"]
        image_parts = [p for p in user_content if p["type"] == "image"]
        assert len(image_parts) == 0

    def test_nonexistent_image_skipped(
        self,
        interpreter: LlmGeometryInterpreter,
    ) -> None:
        """When page_image_path doesn't exist, it's skipped gracefully."""
        mock_response = _mock_api_response(_make_interpretation_json())
        summary = _make_summary()

        with patch.object(
            interpreter._client.messages, "create", return_value=mock_response
        ) as mock_create:
            interpreter.interpret(
                summary, page_image_path=Path("/nonexistent/page.png")
            )

        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[0]["content"]
        image_parts = [p for p in user_content if p["type"] == "image"]
        assert len(image_parts) == 0


# ---------------------------------------------------------------------------
# Tests: default interpretation model
# ---------------------------------------------------------------------------


class TestDefaultInterpretation:
    def test_default_interpretation_fields(self) -> None:
        """Default LlmInterpretation has UNKNOWN fields."""
        from cantena.services.llm_geometry_interpreter import (
            _DEFAULT_INTERPRETATION,
        )

        assert _DEFAULT_INTERPRETATION.building_type == "UNKNOWN"
        assert _DEFAULT_INTERPRETATION.structural_system == "UNKNOWN"
        assert _DEFAULT_INTERPRETATION.rooms == []
        assert _DEFAULT_INTERPRETATION.special_conditions == []
        assert _DEFAULT_INTERPRETATION.measurement_flags == []
        assert _DEFAULT_INTERPRETATION.confidence_notes == "LLM interpretation unavailable"
