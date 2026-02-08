"""Tests for cantena.geometry.rooms — room polygon reconstruction."""

from __future__ import annotations

import math

import pytest

from cantena.geometry.extractor import Point2D
from cantena.geometry.rooms import RoomDetector
from cantena.geometry.walls import Orientation, WallSegment


def _seg(
    start: tuple[float, float],
    end: tuple[float, float],
    thickness: float | None = None,
) -> WallSegment:
    """Create a WallSegment helper for tests."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    dx = abs(ex - sx)
    dy = abs(ey - sy)
    angle = math.degrees(math.atan2(dy, dx)) if (dx or dy) else 0.0
    if angle <= 2.0:
        orientation = Orientation.HORIZONTAL
    elif angle >= 88.0:
        orientation = Orientation.VERTICAL
    else:
        orientation = Orientation.ANGLED
    return WallSegment(
        start=Point2D(sx, sy),
        end=Point2D(ex, ey),
        thickness_pts=thickness,
        orientation=orientation,
        length_pts=length,
    )


def _rectangle_segments(
    x: float, y: float, w: float, h: float
) -> list[WallSegment]:
    """Build four wall segments forming a rectangle at (x, y) with size w×h."""
    return [
        _seg((x, y), (x + w, y)),        # bottom
        _seg((x + w, y), (x + w, y + h)),  # right
        _seg((x + w, y + h), (x, y + h)),  # top
        _seg((x, y + h), (x, y)),          # left
    ]


class TestDetectRoomsSingleRectangle:
    """A closed rectangle should produce exactly 1 room."""

    def test_single_room_detected(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        assert result.polygonize_success is True
        assert result.room_count == 1
        assert len(result.rooms) == 1

    def test_room_area_correct(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        expected_area = 200.0 * 150.0  # 30 000 sq pts
        room = result.rooms[0]
        # Allow small tolerance from segment extension
        assert room.area_pts == pytest.approx(expected_area, rel=0.05)
        assert result.total_area_pts == pytest.approx(expected_area, rel=0.05)

    def test_area_converts_to_sf_with_scale(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs, scale_factor=48.0)

        room = result.rooms[0]
        assert room.area_sf is not None
        assert result.total_area_sf is not None
        # 30000 sq pts * (1/72)^2 * 48^2 / 144 ≈ 88.9 SF
        expected_sf = 30000.0 / (72.0 * 72.0) * 48.0 * 48.0 / 144.0
        assert room.area_sf == pytest.approx(expected_sf, rel=0.05)

    def test_area_sf_none_without_scale(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs, scale_factor=None)

        assert result.rooms[0].area_sf is None
        assert result.total_area_sf is None


class TestDetectRoomsTwoAdjacent:
    """Two adjacent rectangles sharing a wall should produce 2 rooms."""

    def test_two_rooms_detected(self) -> None:
        # Room 1: 200×150 starting at (100, 100)
        # Room 2: 200×150 to the right, sharing the wall at x=300
        segs = [
            # Room 1 outer walls
            _seg((100, 100), (300, 100)),   # bottom
            _seg((100, 100), (100, 250)),   # left
            _seg((100, 250), (300, 250)),   # top
            # Shared wall
            _seg((300, 100), (300, 250)),   # middle
            # Room 2 outer walls
            _seg((300, 100), (500, 100)),   # bottom
            _seg((500, 100), (500, 250)),   # right
            _seg((500, 250), (300, 250)),   # top
        ]
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        assert result.polygonize_success is True
        assert result.room_count == 2
        assert len(result.rooms) == 2

    def test_each_room_has_correct_area(self) -> None:
        segs = [
            _seg((100, 100), (300, 100)),
            _seg((100, 100), (100, 250)),
            _seg((100, 250), (300, 250)),
            _seg((300, 100), (300, 250)),
            _seg((300, 100), (500, 100)),
            _seg((500, 100), (500, 250)),
            _seg((500, 250), (300, 250)),
        ]
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        expected_each = 200.0 * 150.0  # 30 000 sq pts
        for room in result.rooms:
            assert room.area_pts == pytest.approx(expected_each, rel=0.05)


class TestSmallGapsSnapped:
    """Segments with small gaps (within snap tolerance) should still form rooms."""

    def test_gaps_within_tolerance_produce_rooms(self) -> None:
        # Rectangle with 2pt gaps at each corner
        segs = [
            _seg((100, 100), (300, 100)),          # bottom
            _seg((302, 100), (302, 250)),           # right (2pt gap at bottom)
            _seg((300, 252), (100, 252)),           # top (2pt gap at right)
            _seg((98, 250), (98, 100)),             # left (2pt gap at top)
        ]
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        assert result.polygonize_success is True
        assert result.room_count >= 1


class TestNonClosingFallback:
    """Segments that don't form a closed polygon should use convex hull fallback."""

    def test_fallback_to_hull(self) -> None:
        # Three walls of a rectangle — not closed
        segs = [
            _seg((100, 100), (300, 100)),   # bottom
            _seg((300, 100), (300, 250)),   # right
            _seg((300, 250), (100, 250)),   # top
            # Missing left wall
        ]
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        # polygonize may still form a room from extended segments meeting,
        # but if not, falls back to hull
        assert result.room_count >= 1
        # If fallback used, polygonize_success is False
        if not result.polygonize_success:
            assert result.room_count == 1
            assert result.rooms[0].area_pts > 0


class TestTinyArtifactsFiltered:
    """Polygons smaller than 100 sq pts should be filtered out."""

    def test_tiny_polygon_removed(self) -> None:
        # A proper room + a tiny triangle
        segs = _rectangle_segments(100, 100, 200, 150)
        # Add a tiny triangle (area < 100 sq pts: ~50 sq pts)
        segs.extend([
            _seg((400, 400), (410, 400)),
            _seg((410, 400), (405, 410)),
            _seg((405, 410), (400, 400)),
        ])
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        # The tiny triangle should be filtered
        assert result.polygonize_success is True
        assert result.room_count == 1


class TestEmptyInput:
    """Empty or insufficient input should return empty RoomAnalysis."""

    def test_empty_segments(self) -> None:
        detector = RoomDetector()
        result = detector.detect_rooms([])

        assert result.room_count == 0
        assert result.rooms == []
        assert result.polygonize_success is False

    def test_single_segment(self) -> None:
        detector = RoomDetector()
        result = detector.detect_rooms([_seg((0, 0), (100, 0))])

        # Can't form a polygon from one line
        assert result.room_count <= 1
        # Should at least not crash


class TestPageBoundaryFilter:
    """Polygons covering >80% of page area should be filtered."""

    def test_page_boundary_filtered(self) -> None:
        # Create a rectangle covering most of the page
        page_w, page_h = 612.0, 792.0  # US Letter
        page_area = page_w * page_h
        # Rectangle covering ~90% of page
        segs = _rectangle_segments(10, 10, 590, 770)
        # Also add a small inner room
        segs.extend(_rectangle_segments(100, 100, 200, 150))

        detector = RoomDetector()
        result = detector.detect_rooms(
            segs, page_area_pts=page_area
        )

        # The big page-boundary polygon should be filtered;
        # only the small inner room remains
        assert result.polygonize_success is True
        for room in result.rooms:
            assert room.area_pts < page_area * 0.80


class TestRoomAnalysisModel:
    """Test RoomAnalysis and DetectedRoom model properties."""

    def test_room_has_centroid(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        room = result.rooms[0]
        # Centroid should be near center of rectangle
        assert room.centroid.x == pytest.approx(200.0, abs=5)
        assert room.centroid.y == pytest.approx(175.0, abs=5)

    def test_room_has_perimeter(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        room = result.rooms[0]
        expected_perimeter = 2 * (200.0 + 150.0)
        assert room.perimeter_pts == pytest.approx(expected_perimeter, rel=0.05)

    def test_perimeter_converts_to_lf(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs, scale_factor=48.0)

        room = result.rooms[0]
        assert room.perimeter_lf is not None
        # 700 pts * (1/72) * 48 / 12 ≈ 38.9 LF
        expected_lf = 700.0 / 72.0 * 48.0 / 12.0
        assert room.perimeter_lf == pytest.approx(expected_lf, rel=0.05)

    def test_label_initially_none(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        assert result.rooms[0].label is None

    def test_outer_boundary_populated(self) -> None:
        segs = _rectangle_segments(100, 100, 200, 150)
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        assert result.outer_boundary_polygon is not None
        assert len(result.outer_boundary_polygon) >= 4

    def test_room_index_sequential(self) -> None:
        segs = [
            _seg((100, 100), (300, 100)),
            _seg((100, 100), (100, 250)),
            _seg((100, 250), (300, 250)),
            _seg((300, 100), (300, 250)),
            _seg((300, 100), (500, 100)),
            _seg((500, 100), (500, 250)),
            _seg((500, 250), (300, 250)),
        ]
        detector = RoomDetector()
        result = detector.detect_rooms(segs)

        indices = [r.room_index for r in result.rooms]
        assert indices == list(range(len(result.rooms)))
