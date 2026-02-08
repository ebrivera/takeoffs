"""Tests for cantena.geometry.walls — wall detection and boundary identification."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

from cantena.geometry.extractor import (
    BoundingRect,
    DrawingData,
    PathType,
    Point2D,
    VectorExtractor,
    VectorPath,
)
from cantena.geometry.walls import Orientation, WallDetector


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


class TestThickVsThinLines:
    """Verify that thick lines are detected as walls and thin lines are not."""

    def test_thick_lines_detected(self) -> None:
        """Lines with width >= 1.0 pts should be detected as walls."""
        detector = WallDetector()
        paths = [
            _make_line((0, 0), (200, 0), width=2.0),  # thick horizontal
            _make_line((0, 0), (0, 150), width=2.0),  # thick vertical
            _make_line((0, 50), (200, 50), width=0.1),  # thin annotation
        ]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 2

    def test_filter_out_thin_lines(self) -> None:
        """Lines with width < 1.0 pts should be excluded."""
        detector = WallDetector()
        paths = [
            _make_line((0, 0), (200, 0), width=0.5),
            _make_line((0, 0), (0, 150), width=0.3),
        ]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 0

    def test_pdf_with_thick_and_thin_lines(self) -> None:
        """Create a test PDF with thick walls and thin annotations, verify detection."""
        detector = WallDetector()
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            shape = page.new_shape()

            # Thick lines (walls) — width=2.0
            shape.draw_line(fitz.Point(100, 100), fitz.Point(400, 100))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(100, 100), fitz.Point(100, 300))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(400, 100), fitz.Point(400, 300))
            shape.finish(color=(0, 0, 0), width=2.0)
            shape.draw_line(fitz.Point(100, 300), fitz.Point(400, 300))
            shape.finish(color=(0, 0, 0), width=2.0)

            # Thin lines (annotations) — width=0.2
            shape.draw_line(fitz.Point(150, 80), fitz.Point(350, 80))
            shape.finish(color=(0, 0, 0), width=0.2)
            shape.draw_line(fitz.Point(50, 150), fitz.Point(80, 150))
            shape.finish(color=(0, 0, 0), width=0.2)

            shape.commit()
            doc.save(str(pdf_path))
            doc.close()

            doc = fitz.open(str(pdf_path))
            page = doc[0]
            drawing_data = extractor.extract(page)
            doc.close()

            result = detector.detect(drawing_data)
            # Should detect 4 thick wall lines, not the 2 thin ones
            assert len(result.segments) >= 4
            assert result.total_wall_length_pts > 0
        finally:
            pdf_path.unlink(missing_ok=True)


class TestParallelWallPairs:
    """Test detection of parallel line pairs as wall thickness."""

    def test_parallel_lines_6pts_apart(self) -> None:
        """Two parallel horizontal lines 6pts apart should be detected as a wall pair."""
        detector = WallDetector()
        paths = [
            _make_line((100, 100), (400, 100), width=2.0),
            _make_line((100, 106), (400, 106), width=2.0),
        ]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 2
        assert result.detected_wall_thickness_pts is not None
        assert result.detected_wall_thickness_pts == pytest.approx(6.0, abs=1.0)


class TestEnclosedArea:
    """Test area computation from wall segments."""

    def test_rectangular_plan_area(self) -> None:
        """A rectangular plan should compute correct enclosed area."""
        detector = WallDetector()
        # 300 x 200 pts rectangle
        paths = [
            _make_line((100, 100), (400, 100), width=2.0),  # top
            _make_line((400, 100), (400, 300), width=2.0),  # right
            _make_line((100, 300), (400, 300), width=2.0),  # bottom
            _make_line((100, 100), (100, 300), width=2.0),  # left
        ]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)

        area = detector.compute_enclosed_area_pts(result.segments)
        assert area is not None
        # 300 * 200 = 60000 sq pts
        assert area == pytest.approx(60000.0, rel=0.01)

    def test_no_segments_returns_none(self) -> None:
        """Empty segments list should return None, not error."""
        detector = WallDetector()
        area = detector.compute_enclosed_area_pts([])
        assert area is None


class TestEmptyAnalysis:
    """Test that missing walls produce an empty analysis, not an error."""

    def test_no_walls_returns_empty(self) -> None:
        """DrawingData with no qualifying paths should return empty analysis."""
        detector = WallDetector()
        data = DrawingData(paths=[], page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert result.segments == []
        assert result.total_wall_length_pts == 0.0
        assert result.detected_wall_thickness_pts is None
        assert result.outer_boundary is None

    def test_only_curves_returns_empty(self) -> None:
        """DrawingData with only curves (no lines) should return empty analysis."""
        detector = WallDetector()
        curve = VectorPath(
            path_type=PathType.CURVE,
            points=[Point2D(0, 0), Point2D(50, 50), Point2D(100, 0), Point2D(100, 50)],
            stroke_color=(0, 0, 0),
            fill_color=None,
            line_width=2.0,
            bounding_rect=BoundingRect(x=0, y=0, width=100, height=50),
        )
        data = DrawingData(
            paths=[curve], page_width_pts=612, page_height_pts=792
        )
        result = detector.detect(data)
        assert result.segments == []


class TestOrientation:
    """Test wall segment orientation classification."""

    def test_horizontal_wall(self) -> None:
        detector = WallDetector()
        paths = [_make_line((0, 100), (300, 100), width=2.0)]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 1
        assert result.segments[0].orientation == Orientation.HORIZONTAL

    def test_vertical_wall(self) -> None:
        detector = WallDetector()
        paths = [_make_line((100, 0), (100, 300), width=2.0)]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 1
        assert result.segments[0].orientation == Orientation.VERTICAL

    def test_angled_lines_excluded(self) -> None:
        """Lines at 45° should be excluded from wall candidates."""
        detector = WallDetector()
        paths = [_make_line((0, 0), (100, 100), width=2.0)]
        data = DrawingData(paths=paths, page_width_pts=612, page_height_pts=792)
        result = detector.detect(data)
        assert len(result.segments) == 0
