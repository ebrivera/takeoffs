"""Tests for cantena.geometry.measurement — scaled measurement service."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

from cantena.geometry.extractor import (
    BoundingRect,
    PathType,
    Point2D,
    VectorExtractor,
    VectorPath,
)
from cantena.geometry.measurement import (
    MeasurementConfidence,
    MeasurementService,
    pts_to_real_lf,
    pts_to_real_sf,
)
from cantena.geometry.scale import (
    Confidence,
    ScaleDetector,
    ScaleResult,
)
from cantena.geometry.walls import WallDetector


def _make_line(
    p1: tuple[float, float],
    p2: tuple[float, float],
    width: float = 2.0,
    color: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> VectorPath:
    """Create a VectorPath representing a line segment."""
    pts = [Point2D(*p1), Point2D(*p2)]
    xs = [p1[0], p2[0]]
    ys = [p1[1], p2[1]]
    return VectorPath(
        path_type=PathType.LINE,
        points=pts,
        stroke_color=color,
        fill_color=None,
        line_width=width,
        bounding_rect=BoundingRect(
            x=min(xs),
            y=min(ys),
            width=max(xs) - min(xs),
            height=max(ys) - min(ys),
        ),
    )


# 1/8"=1'-0" scale: factor = 96
_SCALE_1_8 = ScaleResult(
    drawing_units=0.125,
    real_units=12.0,
    scale_factor=96.0,
    notation='1/8"=1\'-0"',
    confidence=Confidence.HIGH,
)


class TestConversionFunctions:
    """Test pts_to_real_sf and pts_to_real_lf with known values."""

    def test_pts_to_real_sf(self) -> None:
        """900x450 pts at 1/8\"=1'-0\" should be 5000 SF."""
        area_pts = 900.0 * 450.0  # 405000 sq pts
        result = pts_to_real_sf(area_pts, _SCALE_1_8)
        assert result == pytest.approx(5000.0, rel=0.01)

    def test_pts_to_real_lf(self) -> None:
        """2700 pts perimeter at 1/8\"=1'-0\" should be 300 LF."""
        result = pts_to_real_lf(2700.0, _SCALE_1_8)
        assert result == pytest.approx(300.0, rel=0.01)

    def test_pts_to_real_sf_quarter_scale(self) -> None:
        """Verify with 1/4\"=1'-0\" scale (factor 48)."""
        scale = ScaleResult(
            drawing_units=0.25,
            real_units=12.0,
            scale_factor=48.0,
            notation='1/4"=1\'-0"',
            confidence=Confidence.HIGH,
        )
        # 450x225 pts at 1/4" scale
        # paper area = 450*225 / 72^2 = 19.53 sq in
        # real area = 19.53 * 48^2 / 144 = 19.53 * 16 = 312.5 SF
        # Actually: 450*225=101250, / 5184 = 19.53, * 2304 = 45000, / 144 = 312.5
        # Wait, let me recalculate:
        # 100' at 1/4" scale = 1200/48 = 25" paper = 25*72 = 1800 pts
        # But we have 450 pts = 450/72 = 6.25" paper * 48 = 300" = 25'
        # So 450x225 pts at 1/4" = 25' x 12.5' = 312.5 SF
        area_pts = 450.0 * 225.0
        result = pts_to_real_sf(area_pts, scale)
        assert result == pytest.approx(312.5, rel=0.01)

    def test_pts_to_real_lf_single_wall(self) -> None:
        """72 pts at scale 96 = 1 foot * 96/12 = 8 LF."""
        result = pts_to_real_lf(72.0, _SCALE_1_8)
        assert result == pytest.approx(8.0, rel=0.01)


class TestMeasurementServiceKnownPDF:
    """Test full pipeline with a PDF containing a known-size rectangle."""

    def _create_test_pdf(self) -> Path:
        """Create PDF with 900x450 pts rectangle using thick walls.

        At 1/8\"=1'-0\" (factor 96), this represents 100'x50' = 5000 SF.
        Perimeter = 2*(100+50) = 300 LF.
        Also inserts scale notation text.
        """
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = Path(tmp.name)

        doc = fitz.open()
        page = doc.new_page(width=1200, height=800)
        shape = page.new_shape()

        # Draw 900x450 rectangle with thick walls
        x0, y0 = 100.0, 100.0
        x1, y1 = 1000.0, 550.0

        shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0))
        shape.finish(color=(0, 0, 0), width=2.0)
        shape.draw_line(fitz.Point(x1, y0), fitz.Point(x1, y1))
        shape.finish(color=(0, 0, 0), width=2.0)
        shape.draw_line(fitz.Point(x1, y1), fitz.Point(x0, y1))
        shape.finish(color=(0, 0, 0), width=2.0)
        shape.draw_line(fitz.Point(x0, y1), fitz.Point(x0, y0))
        shape.finish(color=(0, 0, 0), width=2.0)

        shape.commit()

        # Insert scale notation text
        page.insert_text(
            fitz.Point(100, 750),
            'SCALE: 1/8"=1\'-0"',
            fontsize=10,
        )

        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    def test_area_5000_sf(self) -> None:
        """100'x50' rectangle at 1/8\" scale -> ~5000 SF."""
        pdf_path = self._create_test_pdf()
        try:
            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            result = service.measure(page)
            doc.close()

            assert result.gross_area_sf is not None
            assert result.gross_area_sf == pytest.approx(5000.0, rel=0.05)
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_perimeter_300_lf(self) -> None:
        """Perimeter of 100'x50' rectangle -> ~300 LF."""
        pdf_path = self._create_test_pdf()
        try:
            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            result = service.measure(page)
            doc.close()

            assert result.building_perimeter_lf is not None
            assert result.building_perimeter_lf == pytest.approx(
                300.0, rel=0.05
            )
        finally:
            pdf_path.unlink(missing_ok=True)


class TestNoVectorData:
    """Test behavior when page has no vector data."""

    def test_empty_page_returns_none_confidence(self) -> None:
        """Page with no paths returns NONE confidence."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = Path(tmp.name)
        try:
            doc = fitz.open()
            doc.new_page(width=612, height=792)
            doc.save(str(pdf_path))
            doc.close()

            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            result = service.measure(page)
            doc.close()

            assert result.confidence == MeasurementConfidence.NONE
            assert result.gross_area_sf is None
            assert result.building_perimeter_lf is None
            assert result.total_wall_length_lf is None
            assert result.wall_count == 0
            assert result.scale is None
        finally:
            pdf_path.unlink(missing_ok=True)


class TestMissingScale:
    """Test fallback when scale cannot be detected."""

    def test_no_scale_returns_low_confidence(self) -> None:
        """Paths with no scale text -> LOW confidence (estimated scale)."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = Path(tmp.name)
        try:
            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            shape = page.new_shape()

            # Draw thick walls but no scale text
            shape.draw_line(fitz.Point(100, 100), fitz.Point(400, 100))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(400, 100), fitz.Point(400, 300))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(100, 300), fitz.Point(400, 300))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(100, 100), fitz.Point(100, 300))
            shape.finish(color=(0, 0, 0), width=2.0)

            shape.commit()
            doc.save(str(pdf_path))
            doc.close()

            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            result = service.measure(page)
            doc.close()

            assert result.confidence == MeasurementConfidence.LOW
            assert result.scale is not None
            assert "estimated" in result.scale.notation
        finally:
            pdf_path.unlink(missing_ok=True)
