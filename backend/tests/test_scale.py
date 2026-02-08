"""Tests for cantena.geometry.scale — scale detection and dimension parsing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

from cantena.geometry.extractor import (
    BoundingRect,
    PathType,
    Point2D,
    VectorPath,
)
from cantena.geometry.scale import (
    Confidence,
    ScaleDetector,
    TextBlock,
    parse_dimension_string,
)


class TestParseDimensionString:
    """Tests for the parse_dimension_string helper."""

    def test_feet_dash_inches(self) -> None:
        """24'-6" should parse to 294 inches."""
        assert parse_dimension_string('24\'-6"') == pytest.approx(294.0)

    def test_feet_inches_no_dash(self) -> None:
        """24'6" should parse to 294 inches."""
        assert parse_dimension_string('24\'6"') == pytest.approx(294.0)

    def test_feet_zero_inches(self) -> None:
        """10'-0" should parse to 120 inches."""
        assert parse_dimension_string('10\'-0"') == pytest.approx(120.0)

    def test_large_dimension(self) -> None:
        """150'-0" should parse to 1800 inches."""
        assert parse_dimension_string('150\'-0"') == pytest.approx(1800.0)

    def test_decimal_feet(self) -> None:
        """24.5' should parse to 294 inches."""
        assert parse_dimension_string("24.5'") == pytest.approx(294.0)

    def test_unparseable_returns_none(self) -> None:
        """Random text should return None."""
        assert parse_dimension_string("hello world") is None
        assert parse_dimension_string("") is None
        assert parse_dimension_string("42") is None


class TestScaleNotationParsing:
    """Tests for ScaleDetector.detect_from_text with common notations."""

    def setup_method(self) -> None:
        self.detector = ScaleDetector()

    def test_eighth_inch_scale(self) -> None:
        """1/8"=1'-0" -> scale factor 96."""
        result = self.detector.detect_from_text('1/8"=1\'-0"')
        assert result is not None
        assert result.scale_factor == pytest.approx(96.0)
        assert result.drawing_units == pytest.approx(0.125)
        assert result.real_units == pytest.approx(12.0)
        assert result.confidence == Confidence.HIGH

    def test_quarter_inch_scale(self) -> None:
        """1/4"=1'-0" -> scale factor 48."""
        result = self.detector.detect_from_text('1/4"=1\'-0"')
        assert result is not None
        assert result.scale_factor == pytest.approx(48.0)

    def test_three_sixteenths_scale(self) -> None:
        """3/16"=1'-0" -> scale factor 64."""
        result = self.detector.detect_from_text('3/16"=1\'-0"')
        assert result is not None
        assert result.scale_factor == pytest.approx(64.0)

    def test_one_inch_equals_ten_feet(self) -> None:
        """1"=10'-0" -> scale factor 120."""
        result = self.detector.detect_from_text('1"=10\'-0"')
        assert result is not None
        assert result.scale_factor == pytest.approx(120.0)

    def test_metric_scale_1_100(self) -> None:
        """1:100 -> scale factor 100."""
        result = self.detector.detect_from_text("1:100")
        assert result is not None
        assert result.scale_factor == pytest.approx(100.0)

    def test_metric_scale_1_50(self) -> None:
        """1:50 -> scale factor 50."""
        result = self.detector.detect_from_text("1:50")
        assert result is not None
        assert result.scale_factor == pytest.approx(50.0)


class TestMessyText:
    """Test that scale detection handles inconsistent spacing/punctuation."""

    def setup_method(self) -> None:
        self.detector = ScaleDetector()

    def test_extra_spaces(self) -> None:
        """Scale with extra spaces around = and - should still parse."""
        result = self.detector.detect_from_text("1/8\" = 1' - 0\"")
        assert result is not None
        assert result.scale_factor == pytest.approx(96.0)

    def test_no_inch_mark(self) -> None:
        """Scale without inch mark on the fraction should still parse."""
        result = self.detector.detect_from_text("1/8=1'-0\"")
        assert result is not None
        assert result.scale_factor == pytest.approx(96.0)

    def test_scale_in_title_block_text(self) -> None:
        """Find scale notation embedded in a block of title block text."""
        title_block = (
            "PROJECT: Example Office Building\n"
            "SHEET: A-101 FLOOR PLAN\n"
            "DATE: 2024-01-15\n"
            'SCALE: 1/8"=1\'-0"\n'
            "DRAWN BY: JDS\n"
        )
        result = self.detector.detect_from_text(title_block)
        assert result is not None
        assert result.scale_factor == pytest.approx(96.0)
        assert result.confidence == Confidence.HIGH

    def test_metric_with_spaces(self) -> None:
        """1 : 50 with spaces should parse."""
        result = self.detector.detect_from_text("1 : 50")
        assert result is not None
        assert result.scale_factor == pytest.approx(50.0)


class TestUnparseableText:
    """Test that unparseable input returns None."""

    def setup_method(self) -> None:
        self.detector = ScaleDetector()

    def test_random_text(self) -> None:
        assert self.detector.detect_from_text("Hello World") is None

    def test_empty_text(self) -> None:
        assert self.detector.detect_from_text("") is None

    def test_no_scale_pattern(self) -> None:
        text = "PROJECT: Office Building\nSHEET: A-101"
        assert self.detector.detect_from_text(text) is None


class TestDetectFromDimensions:
    """Tests for ScaleDetector.detect_from_dimensions."""

    def setup_method(self) -> None:
        self.detector = ScaleDetector()

    def test_infers_scale_from_dimension_near_line(self) -> None:
        """A dimension text near a line midpoint should produce a scale."""
        # A line 72 pts long (1 inch on paper)
        line = VectorPath(
            path_type=PathType.LINE,
            points=[Point2D(100, 100), Point2D(172, 100)],
            stroke_color=(0, 0, 0),
            fill_color=None,
            line_width=0.5,
            bounding_rect=BoundingRect(x=100, y=100, width=72, height=0),
        )
        # Text "10'-0"" centered near the line midpoint
        text = TextBlock(
            text="10'-0\"",
            position=Point2D(136, 110),  # near midpoint (136, 100)
            bounding_rect=BoundingRect(x=120, y=105, width=32, height=10),
        )
        result = self.detector.detect_from_dimensions([line], [text])
        assert result is not None
        # 1 inch on paper = 120 inches real = scale factor 120
        assert result.scale_factor == pytest.approx(120.0)
        assert result.confidence == Confidence.MEDIUM

    def test_no_paths_returns_none(self) -> None:
        assert self.detector.detect_from_dimensions([], []) is None

    def test_no_matching_text_returns_none(self) -> None:
        line = VectorPath(
            path_type=PathType.LINE,
            points=[Point2D(0, 0), Point2D(100, 0)],
            stroke_color=None,
            fill_color=None,
            line_width=0.5,
            bounding_rect=BoundingRect(x=0, y=0, width=100, height=0),
        )
        text = TextBlock(
            text="NOT A DIMENSION",
            position=Point2D(50, 0),
            bounding_rect=BoundingRect(x=30, y=0, width=40, height=10),
        )
        assert self.detector.detect_from_dimensions([line], [text]) is None

    def test_text_too_far_from_line_returns_none(self) -> None:
        """Text more than 50 pts from line midpoint should not match."""
        line = VectorPath(
            path_type=PathType.LINE,
            points=[Point2D(0, 0), Point2D(100, 0)],
            stroke_color=None,
            fill_color=None,
            line_width=0.5,
            bounding_rect=BoundingRect(x=0, y=0, width=100, height=0),
        )
        text = TextBlock(
            text="10'-0\"",
            position=Point2D(50, 200),  # way too far
            bounding_rect=BoundingRect(x=30, y=195, width=40, height=10),
        )
        assert self.detector.detect_from_dimensions([line], [text]) is None


class TestExtractTextBlocks:
    """Tests for ScaleDetector.extract_text_blocks using a real PDF."""

    def test_extracts_text_with_positions(self) -> None:
        """Text inserted into a PDF should be extracted with position."""
        detector = ScaleDetector()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            writer = fitz.TextWriter(page.rect)
            font = fitz.Font("helv")
            writer.append((100, 200), "SCALE: 1/4\"=1'-0\"", font=font, fontsize=12)
            writer.write_text(page)
            doc.save(str(pdf_path))
            doc.close()

            doc = fitz.open(str(pdf_path))
            page = doc[0]
            blocks = detector.extract_text_blocks(page)
            doc.close()

            assert len(blocks) >= 1
            scale_block = next(
                (b for b in blocks if "SCALE" in b.text), None
            )
            assert scale_block is not None
            assert scale_block.bounding_rect.width > 0
            assert scale_block.bounding_rect.height > 0
        finally:
            pdf_path.unlink(missing_ok=True)
