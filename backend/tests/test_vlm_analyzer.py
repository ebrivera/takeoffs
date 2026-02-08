"""Tests for the VLM analysis service — all API calls are mocked."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cantena.models.enums import BuildingType, Confidence, StructuralSystem
from cantena.services.vlm_analyzer import (
    AnalysisContext,
    VlmAnalyzer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vlm_response(
    building_type: str = "office_mid_rise",
    gross_sf: float = 45000.0,
    stories: int = 3,
    structural_system: str = "steel_frame",
    exterior_wall_system: str = "curtain_wall",
    extra_fields: dict[str, Any] | None = None,
) -> str:
    """Build a well-formed VLM response string with reasoning + JSON."""
    data: dict[str, Any] = {
        "building_type": building_type,
        "building_use": "General office space",
        "gross_sf": gross_sf,
        "stories": stories,
        "story_height_ft": 13.0,
        "structural_system": structural_system,
        "exterior_wall_system": exterior_wall_system,
        "mechanical_system": "vav",
        "electrical_service": "standard",
        "fire_protection": "sprinkler_wet",
        "complexity_scores": {
            "structural": 3,
            "mep": 3,
            "finishes": 3,
            "site": 2,
        },
        "special_conditions": [],
        "confidence": {
            "building_type": "high",
            "gross_sf": "medium",
            "stories": "high",
            "structural_system": "medium",
            "exterior_wall_system": "high",
        },
    }
    if extra_fields:
        data.update(extra_fields)

    import json

    json_str = json.dumps(data, indent=2)
    return (
        "**Pass 1 — Description:**\n"
        "This appears to be a 3-story office building with steel frame construction.\n\n"
        "**Pass 2 — Confidence:**\n"
        "Building type: HIGH — clearly labeled.\n"
        "Gross SF: MEDIUM — estimated from floor plate dimensions.\n\n"
        f"```json\n{json_str}\n```"
    )


def _mock_api_response(text: str) -> MagicMock:
    """Create a mock Anthropic API response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response = MagicMock()
    response.content = [text_block]
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """Create a minimal PNG image for testing."""
    # Minimal valid 1x1 PNG
    import struct
    import zlib

    def _create_png() -> bytes:
        signature = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT chunk
        raw_data = zlib.compress(b"\x00\xff\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw_data) & 0xFFFFFFFF
        idat = (
            struct.pack(">I", len(raw_data))
            + b"IDAT"
            + raw_data
            + struct.pack(">I", idat_crc)
        )

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        return signature + ihdr + idat + iend

    img_path = tmp_path / "drawing.png"
    img_path.write_bytes(_create_png())
    return img_path


@pytest.fixture()
def analyzer() -> VlmAnalyzer:
    """Create a VlmAnalyzer with a fake API key."""
    return VlmAnalyzer(api_key="test-key-not-real")


# ---------------------------------------------------------------------------
# Tests: well-formed response parsing
# ---------------------------------------------------------------------------

class TestWellFormedResponse:
    def test_parse_valid_response(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """VLM returns well-formed JSON — should produce a valid BuildingModel."""
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        assert result.building_model.building_type == BuildingType.OFFICE_MID_RISE
        assert result.building_model.gross_sf == 45000.0
        assert result.building_model.stories == 3
        assert result.building_model.structural_system == StructuralSystem.STEEL_FRAME
        assert result.raw_response != ""
        assert "Description" in result.reasoning
        assert result.warnings == []

    def test_confidence_parsed(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Confidence values from VLM response are parsed correctly."""
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        confidence = result.building_model.confidence
        assert confidence["building_type"] == Confidence.HIGH
        assert confidence["gross_sf"] == Confidence.MEDIUM

    def test_complexity_scores_parsed(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Complexity scores from VLM response are parsed correctly."""
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        scores = result.building_model.complexity_scores
        assert scores.structural == 3
        assert scores.site == 2

    def test_optional_fields_null(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Optional fields (mechanical, electrical, fire protection) can be null."""
        response_text = _make_vlm_response(
            extra_fields={
                "mechanical_system": None,
                "electrical_service": None,
                "fire_protection": None,
            }
        )
        mock_response = _mock_api_response(response_text)

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        assert result.building_model.mechanical_system is None
        assert result.building_model.electrical_service is None
        assert result.building_model.fire_protection is None


# ---------------------------------------------------------------------------
# Tests: malformed response and retry
# ---------------------------------------------------------------------------

class TestMalformedResponse:
    def test_retry_on_malformed_then_success(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """First response malformed, second attempt succeeds."""
        bad_response = _mock_api_response("I cannot analyze this image, sorry.")
        good_response = _mock_api_response(_make_vlm_response())

        with patch.object(
            analyzer._client.messages,
            "create",
            side_effect=[bad_response, good_response],
        ):
            result = analyzer.analyze(sample_image)

        assert result.building_model.building_type == BuildingType.OFFICE_MID_RISE

    def test_raises_after_all_retries_fail(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Both attempts return malformed response — raises ValueError."""
        bad_response = _mock_api_response("No JSON here at all.")

        with (
            patch.object(
                analyzer._client.messages, "create", return_value=bad_response
            ),
            pytest.raises(ValueError, match="unparseable response"),
        ):
            analyzer.analyze(sample_image)

    def test_retry_on_invalid_json(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """JSON code fence present but content is invalid JSON."""
        bad_json_response = _mock_api_response(
            "Here is the analysis:\n```json\n{invalid json}\n```"
        )
        good_response = _mock_api_response(_make_vlm_response())

        with patch.object(
            analyzer._client.messages,
            "create",
            side_effect=[bad_json_response, good_response],
        ):
            result = analyzer.analyze(sample_image)

        assert result.building_model.gross_sf == 45000.0


# ---------------------------------------------------------------------------
# Tests: missing field defaults
# ---------------------------------------------------------------------------

class TestMissingFieldDefaults:
    def test_missing_building_type_gets_default(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Missing building_type field gets LOW confidence default."""
        import json

        data = json.loads(
            '{"building_use": "Office", "gross_sf": 30000, "stories": 2,'
            '"story_height_ft": 12, "structural_system": "steel_frame",'
            '"exterior_wall_system": "curtain_wall", "confidence": {}}'
        )
        response_text = f"Analysis:\n```json\n{json.dumps(data)}\n```"
        mock_response = _mock_api_response(response_text)

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        assert result.building_model.building_type == BuildingType.OFFICE_MID_RISE
        assert result.building_model.confidence["building_type"] == Confidence.LOW
        assert any("building_type" in w for w in result.warnings)

    def test_missing_gross_sf_gets_default(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Missing gross_sf gets LOW confidence default of 25000."""
        import json

        data = {
            "building_type": "warehouse",
            "building_use": "Storage",
            "stories": 1,
            "story_height_ft": 24,
            "structural_system": "steel_frame",
            "exterior_wall_system": "metal_panel",
            "confidence": {},
        }
        response_text = f"Analysis:\n```json\n{json.dumps(data)}\n```"
        mock_response = _mock_api_response(response_text)

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        assert result.building_model.gross_sf == 25000.0
        assert result.building_model.confidence["gross_sf"] == Confidence.LOW
        assert any("gross_sf" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Tests: AnalysisContext passthrough
# ---------------------------------------------------------------------------

class TestAnalysisContext:
    def test_context_included_in_api_call(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Context fields are passed through to the API call."""
        context = AnalysisContext(
            project_name="Test Office Tower",
            location="Baltimore, MD",
            additional_notes="Steel frame, 3 stories",
        )
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(
            analyzer._client.messages, "create", return_value=mock_response
        ) as mock_create:
            analyzer.analyze(sample_image, context=context)

        # Verify the context was passed in the user message
        call_args = mock_create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[0]["content"]
        # Find text part
        text_parts = [p for p in user_content if p["type"] == "text"]
        assert len(text_parts) == 1
        assert "Test Office Tower" in text_parts[0]["text"]
        assert "Baltimore, MD" in text_parts[0]["text"]
        assert "Steel frame, 3 stories" in text_parts[0]["text"]

    def test_location_from_context(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """Location from AnalysisContext is used for BuildingModel."""
        context = AnalysisContext(location="Baltimore, MD")
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image, context=context)

        assert result.building_model.location.city == "Baltimore"
        assert result.building_model.location.state == "MD"

    def test_no_context(
        self, analyzer: VlmAnalyzer, sample_image: Path
    ) -> None:
        """No context provided — location defaults to empty strings."""
        mock_response = _mock_api_response(_make_vlm_response())

        with patch.object(analyzer._client.messages, "create", return_value=mock_response):
            result = analyzer.analyze(sample_image)

        assert result.building_model.location.city == ""
        assert result.building_model.location.state == ""


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_nonexistent_image(self, analyzer: VlmAnalyzer) -> None:
        """Raises ValueError for nonexistent image file."""
        with pytest.raises(ValueError, match="not found"):
            analyzer.analyze(Path("/nonexistent/image.png"))
