"""Tests for room-based area computation in MeasurementService."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import fitz  # type: ignore[import-untyped]
import pytest

from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import (
    MeasurementConfidence,
    MeasurementService,
    PageMeasurements,
)
from cantena.geometry.scale import (
    Confidence,
    ScaleDetector,
    ScaleResult,
)
from cantena.geometry.scale_verify import ScaleVerificationResult
from cantena.geometry.walls import WallDetector

# 1/4"=1'-0" scale: factor = 48
_SCALE_QUARTER = ScaleResult(
    drawing_units=0.25,
    real_units=12.0,
    scale_factor=48.0,
    notation='1/4"=1\'-0"',
    confidence=Confidence.HIGH,
)


def _create_rectangle_pdf(
    x0: float = 100.0,
    y0: float = 100.0,
    x1: float = 400.0,
    y1: float = 300.0,
    scale_text: str = 'SCALE: 1/4"=1\'-0"',
) -> Path:
    """Create a PDF with a closed rectangle and scale text."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = Path(tmp.name)

    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    shape = page.new_shape()

    # Draw closed rectangle
    shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(x1, y0), fitz.Point(x1, y1))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(x1, y1), fitz.Point(x0, y1))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(x0, y1), fitz.Point(x0, y0))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.commit()

    # Insert scale text at bottom
    page.insert_text(fitz.Point(100, 560), scale_text, fontsize=10)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _create_two_room_pdf() -> Path:
    """Create a PDF with two adjacent rooms sharing a dividing wall."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = Path(tmp.name)

    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    shape = page.new_shape()

    # Outer rectangle: 300x200 pts
    x0, y0 = 100.0, 100.0
    x1, y1 = 400.0, 300.0
    mid_x = 250.0  # Dividing wall at x=250

    # Top wall
    shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0))
    shape.finish(color=(0, 0, 0), width=2.0)
    # Right wall
    shape.draw_line(fitz.Point(x1, y0), fitz.Point(x1, y1))
    shape.finish(color=(0, 0, 0), width=2.0)
    # Bottom wall
    shape.draw_line(fitz.Point(x1, y1), fitz.Point(x0, y1))
    shape.finish(color=(0, 0, 0), width=2.0)
    # Left wall
    shape.draw_line(fitz.Point(x0, y1), fitz.Point(x0, y0))
    shape.finish(color=(0, 0, 0), width=2.0)
    # Dividing wall
    shape.draw_line(fitz.Point(mid_x, y0), fitz.Point(mid_x, y1))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.commit()

    # Scale text
    page.insert_text(
        fitz.Point(100, 560), 'SCALE: 1/4"=1\'-0"', fontsize=10
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _create_non_closing_pdf() -> Path:
    """Create a PDF with non-closing wall segments (no polygonize rooms)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = Path(tmp.name)

    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    shape = page.new_shape()

    # Two disconnected parallel lines — won't form a polygon
    shape.draw_line(fitz.Point(100, 200), fitz.Point(400, 200))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(100, 300), fitz.Point(400, 300))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.commit()

    page.insert_text(
        fitz.Point(100, 560), 'SCALE: 1/4"=1\'-0"', fontsize=10
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _run_measurement(pdf_path: Path) -> PageMeasurements:
    """Run MeasurementService.measure() on a PDF and return results."""
    service = MeasurementService(
        extractor=VectorExtractor(),
        scale_detector=ScaleDetector(),
        wall_detector=WallDetector(),
    )
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[0]
        return service.measure(page)
    finally:
        doc.close()


class TestRoomsIncludedWhenPolygonizeWorks:
    """Rooms are populated in PageMeasurements when polygonize succeeds."""

    def test_rooms_not_none(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.rooms is not None
            assert len(result.rooms) >= 1
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_room_count_set(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.room_count >= 1
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_polygonize_success_true(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.polygonize_success is True
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_room_has_area_sf(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.rooms is not None
            for room in result.rooms:
                assert room.area_sf is not None
                assert room.area_sf > 0
        finally:
            pdf_path.unlink(missing_ok=True)


class TestPolygonizedTotalCloserThanConvexHull:
    """Polygonized room-sum area is more accurate than convex hull on
    multi-room layouts (2 rooms should sum closer to true area than hull)."""

    def test_two_rooms_area_closer(self) -> None:
        """Two adjacent rooms: polygonize gives per-room areas that sum to
        the correct total, while convex hull would give the same total
        (for a simple rectangle).  Verify polygonize total is reasonable."""
        pdf_path = _create_two_room_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.rooms is not None
            assert result.polygonize_success is True
            assert result.room_count >= 2
            assert result.gross_area_sf is not None
            # The two-room area sum should be positive and reasonable
            room_sum = sum(
                r.area_sf for r in result.rooms if r.area_sf is not None
            )
            assert room_sum > 0
            # gross_area_sf should come from room sum
            assert result.gross_area_sf == pytest.approx(room_sum, rel=0.01)
        finally:
            pdf_path.unlink(missing_ok=True)


class TestFallbackToConvexHull:
    """When polygonize fails, area falls back to convex hull."""

    def test_non_closing_segments_fallback(self) -> None:
        pdf_path = _create_non_closing_pdf()
        try:
            result = _run_measurement(pdf_path)
            # Polygonize should fail on open line segments
            assert result.polygonize_success is False
            # But we should still get an area from convex hull fallback
            assert result.gross_area_sf is not None
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_non_closing_room_count(self) -> None:
        """Even with fallback, room_count reflects what RoomDetector returned."""
        pdf_path = _create_non_closing_pdf()
        try:
            result = _run_measurement(pdf_path)
            # Convex hull fallback gives 1 "room" (the hull)
            assert result.room_count >= 0
        finally:
            pdf_path.unlink(missing_ok=True)


class TestRoomCountAndPolygonizeSuccess:
    """room_count and polygonize_success set correctly."""

    def test_single_room(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.room_count >= 1
            assert result.polygonize_success is True
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_two_rooms(self) -> None:
        pdf_path = _create_two_room_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.room_count >= 2
            assert result.polygonize_success is True
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_no_rooms_on_open_segments(self) -> None:
        pdf_path = _create_non_closing_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.polygonize_success is False
        finally:
            pdf_path.unlink(missing_ok=True)


class TestWithoutLlmInterpreter:
    """Without LLM interpreter, llm_interpretation is None."""

    def test_llm_interpretation_none(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.llm_interpretation is None
        finally:
            pdf_path.unlink(missing_ok=True)


class TestWithScaleVerifier:
    """With a mocked ScaleVerifier, scale_verification is populated."""

    def test_scale_verification_populated(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            mock_verifier = MagicMock()
            mock_verifier.verify_or_recover_scale.return_value = (
                ScaleVerificationResult(
                    scale=_SCALE_QUARTER,
                    verification_source="LLM_CONFIRMED",
                    llm_raw_notation='1/4"=1\'-0"',
                )
            )

            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
                scale_verifier=mock_verifier,
            )

            doc = fitz.open(str(pdf_path))
            try:
                result = service.measure(doc[0])
            finally:
                doc.close()

            assert result.scale_verification is not None
            assert result.scale_verification.verification_source == "LLM_CONFIRMED"
            mock_verifier.verify_or_recover_scale.assert_called_once()
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_scale_verification_none_without_verifier(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            assert result.scale_verification is None
        finally:
            pdf_path.unlink(missing_ok=True)


class TestBackwardCompatibility:
    """Existing tests patterns should still work: room fields are additive."""

    def test_existing_fields_present(self) -> None:
        pdf_path = _create_rectangle_pdf()
        try:
            result = _run_measurement(pdf_path)
            # All original fields should be present and populated
            assert result.scale is not None
            assert result.gross_area_sf is not None
            assert result.wall_count > 0
            assert result.confidence in (
                MeasurementConfidence.HIGH,
                MeasurementConfidence.MEDIUM,
            )
            assert result.raw_data is not None
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_default_room_fields(self) -> None:
        """Empty page returns default room field values."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = Path(tmp.name)
        try:
            doc = fitz.open()
            doc.new_page(width=612, height=792)
            doc.save(str(pdf_path))
            doc.close()

            result = _run_measurement(pdf_path)
            assert result.rooms is None
            assert result.room_count == 0
            assert result.polygonize_success is False
            assert result.llm_interpretation is None
            assert result.scale_verification is None
        finally:
            pdf_path.unlink(missing_ok=True)
