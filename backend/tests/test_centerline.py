"""Tests for cantena.geometry.centerline — center-line extraction from parallel wall pairs."""

from __future__ import annotations

import math

import pytest

from cantena.geometry.centerline import (
    CenterlineResult,
    close_gaps,
    extend_to_intersections,
    extract_centerlines,
)
from cantena.geometry.extractor import Point2D
from cantena.geometry.walls import Orientation, WallSegment


def _seg(
    start: tuple[float, float],
    end: tuple[float, float],
    orientation: Orientation | None = None,
) -> WallSegment:
    """Create a WallSegment from coordinate tuples."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    if orientation is None:
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
        thickness_pts=None,
        orientation=orientation,
        length_pts=length,
    )


def _parallel_wall_pair(
    x1: float, y1: float, x2: float, y2: float, gap: float
) -> list[WallSegment]:
    """Create a parallel wall pair (two lines separated by *gap*).

    For horizontal walls, shifts y by gap.
    For vertical walls, shifts x by gap.
    """
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx >= dy:
        # Horizontal wall pair
        return [
            _seg((x1, y1), (x2, y1)),
            _seg((x1, y1 + gap), (x2, y1 + gap)),
        ]
    else:
        # Vertical wall pair
        return [
            _seg((x1, y1), (x1, y2)),
            _seg((x1 + gap, y1), (x1 + gap, y2)),
        ]


def _rectangle_wall_pairs(
    x: float, y: float, w: float, h: float, thickness: float = 10.0
) -> list[WallSegment]:
    """Build parallel wall pairs forming a rectangle."""
    segs: list[WallSegment] = []
    # Bottom wall pair
    segs += _parallel_wall_pair(x, y, x + w, y, thickness)
    # Top wall pair
    segs += _parallel_wall_pair(x, y + h, x + w, y + h, -thickness)
    # Left wall pair
    segs += _parallel_wall_pair(x, y, x, y + h, thickness)
    # Right wall pair
    segs += _parallel_wall_pair(x + w, y, x + w, y + h, -thickness)
    return segs


# ---------------------------------------------------------------------------
# extract_centerlines
# ---------------------------------------------------------------------------


class TestExtractCenterlines:
    """Test center-line extraction from parallel wall pairs."""

    def test_horizontal_pair_produces_centerline(self) -> None:
        segs = _parallel_wall_pair(100, 200, 400, 200, gap=10)
        result = extract_centerlines(segs)
        assert len(result.centerlines) == 1
        cl = result.centerlines[0]
        assert cl.orientation == Orientation.HORIZONTAL
        # Center should be at y=205 (midpoint of 200 and 210)
        assert cl.start.y == pytest.approx(205.0, abs=1)
        assert cl.length_pts == pytest.approx(300.0, abs=5)

    def test_vertical_pair_produces_centerline(self) -> None:
        segs = _parallel_wall_pair(100, 200, 100, 500, gap=10)
        result = extract_centerlines(segs)
        assert len(result.centerlines) == 1
        cl = result.centerlines[0]
        assert cl.orientation == Orientation.VERTICAL
        # Center should be at x=105
        assert cl.start.x == pytest.approx(105.0, abs=1)
        assert cl.length_pts == pytest.approx(300.0, abs=5)

    def test_rectangle_produces_4_centerlines(self) -> None:
        segs = _rectangle_wall_pairs(100, 100, 300, 200, thickness=10)
        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=15)
        # Should produce 4 center-lines (top, bottom, left, right)
        assert len(result.centerlines) == 4
        h_count = sum(
            1 for c in result.centerlines
            if c.orientation == Orientation.HORIZONTAL
        )
        v_count = sum(
            1 for c in result.centerlines
            if c.orientation == Orientation.VERTICAL
        )
        assert h_count == 2
        assert v_count == 2

    def test_gap_outside_range_not_paired(self) -> None:
        # Gap of 25 pts is outside default max_gap_pts=18
        segs = _parallel_wall_pair(100, 200, 400, 200, gap=25)
        result = extract_centerlines(segs, max_gap_pts=18)
        assert len(result.centerlines) == 0
        assert len(result.unpaired) == 2

    def test_single_line_not_paired(self) -> None:
        segs = [_seg((100, 200), (400, 200))]
        result = extract_centerlines(segs)
        assert len(result.centerlines) == 0
        assert len(result.unpaired) == 1

    def test_wall_thickness_detected(self) -> None:
        segs = _parallel_wall_pair(100, 200, 400, 200, gap=9.4)
        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=18)
        assert result.wall_thickness_pts is not None
        assert result.wall_thickness_pts == pytest.approx(9.4, abs=1)

    def test_empty_input(self) -> None:
        result = extract_centerlines([])
        assert result.centerlines == []
        assert result.unpaired == []
        assert result.wall_thickness_pts is None

    def test_overlapping_segments_merged(self) -> None:
        """Two parallel pairs at the same y produce merged center-lines."""
        segs = [
            # Two segments on one face, one on the other
            _seg((100, 200), (250, 200)),
            _seg((200, 200), (400, 200)),  # overlaps with first
            _seg((100, 210), (400, 210)),  # partner face
        ]
        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=18)
        assert len(result.centerlines) >= 1
        # The merged range should span 100 to 400
        total_span = max(c.end.x for c in result.centerlines) - min(c.start.x for c in result.centerlines)
        assert total_span == pytest.approx(300.0, abs=5)


# ---------------------------------------------------------------------------
# close_gaps
# ---------------------------------------------------------------------------


class TestCloseGaps:
    """Test doorway gap closing in collinear center-lines."""

    def test_small_gap_bridged(self) -> None:
        """Two collinear segments with a 40pt gap are merged."""
        segs = [
            _seg((100, 200), (250, 200)),
            _seg((290, 200), (400, 200)),
        ]
        result = close_gaps(segs, max_gap_pts=60)
        assert len(result) == 1
        assert result[0].start.x == pytest.approx(100, abs=1)
        assert result[0].end.x == pytest.approx(400, abs=1)

    def test_large_gap_not_bridged(self) -> None:
        """Two collinear segments with a 100pt gap are NOT merged."""
        segs = [
            _seg((100, 200), (200, 200)),
            _seg((300, 200), (400, 200)),
        ]
        result = close_gaps(segs, max_gap_pts=60)
        assert len(result) == 2

    def test_vertical_gap_bridged(self) -> None:
        segs = [
            _seg((200, 100), (200, 250)),
            _seg((200, 290), (200, 400)),
        ]
        result = close_gaps(segs, max_gap_pts=60)
        assert len(result) == 1
        y_min = min(result[0].start.y, result[0].end.y)
        y_max = max(result[0].start.y, result[0].end.y)
        assert y_min == pytest.approx(100, abs=1)
        assert y_max == pytest.approx(400, abs=1)

    def test_multiple_gaps_bridged(self) -> None:
        """Three collinear segments with small gaps → one segment."""
        segs = [
            _seg((100, 200), (200, 200)),
            _seg((240, 200), (350, 200)),
            _seg((390, 200), (500, 200)),
        ]
        result = close_gaps(segs, max_gap_pts=60)
        assert len(result) == 1
        assert result[0].length_pts == pytest.approx(400, abs=5)

    def test_no_segments(self) -> None:
        assert close_gaps([]) == []


# ---------------------------------------------------------------------------
# extend_to_intersections
# ---------------------------------------------------------------------------


class TestExtendToIntersections:
    """Test endpoint extension to meet perpendicular lines."""

    def test_horizontal_extended_to_vertical(self) -> None:
        """Horizontal line endpoint near a vertical line gets extended."""
        segs = [
            _seg((100, 200), (280, 200)),  # ends 20pts short of x=300
            _seg((300, 100), (300, 400)),   # vertical at x=300
        ]
        result = extend_to_intersections(segs, max_extension_pts=30)
        h_seg = [s for s in result if s.orientation == Orientation.HORIZONTAL][0]
        assert max(h_seg.start.x, h_seg.end.x) == pytest.approx(300, abs=1)

    def test_vertical_extended_to_horizontal(self) -> None:
        """Vertical line endpoint near a horizontal line gets extended."""
        segs = [
            _seg((200, 100), (200, 280)),   # ends 20pts short of y=300
            _seg((100, 300), (400, 300)),    # horizontal at y=300
        ]
        result = extend_to_intersections(segs, max_extension_pts=30)
        v_seg = [s for s in result if s.orientation == Orientation.VERTICAL][0]
        assert max(v_seg.start.y, v_seg.end.y) == pytest.approx(300, abs=1)

    def test_no_extension_beyond_max(self) -> None:
        """Lines too far apart are NOT extended."""
        segs = [
            _seg((100, 200), (200, 200)),  # ends 150pts short of x=350
            _seg((350, 100), (350, 400)),
        ]
        result = extend_to_intersections(segs, max_extension_pts=30)
        h_seg = [s for s in result if s.orientation == Orientation.HORIZONTAL][0]
        assert max(h_seg.start.x, h_seg.end.x) == pytest.approx(200, abs=1)

    def test_both_ends_can_extend(self) -> None:
        """A horizontal line between two verticals gets extended at both ends."""
        segs = [
            _seg((120, 200), (280, 200)),  # between x=100 and x=300
            _seg((100, 100), (100, 400)),
            _seg((300, 100), (300, 400)),
        ]
        result = extend_to_intersections(segs, max_extension_pts=30)
        h_seg = [s for s in result if s.orientation == Orientation.HORIZONTAL][0]
        assert min(h_seg.start.x, h_seg.end.x) == pytest.approx(100, abs=1)
        assert max(h_seg.start.x, h_seg.end.x) == pytest.approx(300, abs=1)


# ---------------------------------------------------------------------------
# Integration: parallel pairs → polygonize-ready
# ---------------------------------------------------------------------------


class TestCenterlineToPolygonize:
    """End-to-end: parallel wall pairs → center-lines → polygonize rooms."""

    def test_rectangle_pair_walls_produce_one_room(self) -> None:
        """A rectangle drawn as parallel wall pairs should yield 1 room."""
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        segs = _rectangle_wall_pairs(100, 100, 300, 200, thickness=10)
        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=15)
        closed = close_gaps(result.centerlines)
        extended = extend_to_intersections(closed)

        lines = [
            LineString([(s.start.x, s.start.y), (s.end.x, s.end.y)])
            for s in extended
        ]
        merged = unary_union(lines)
        polygons = [p for p in polygonize(merged) if p.area > 100]
        assert len(polygons) >= 1

    def test_two_room_pair_walls(self) -> None:
        """Two adjacent rooms drawn as parallel pairs → 2 polygons."""
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        # Room 1: 200x200 at (100, 100)
        # Room 2: 200x200 at (300, 100) sharing wall at x=300
        segs: list[WallSegment] = []
        # Bottom wall (full width)
        segs += _parallel_wall_pair(100, 100, 500, 100, gap=10)
        # Top wall (full width)
        segs += _parallel_wall_pair(100, 300, 500, 300, gap=-10)
        # Left wall
        segs += _parallel_wall_pair(100, 100, 100, 300, gap=10)
        # Shared interior wall
        segs += _parallel_wall_pair(300, 100, 300, 300, gap=10)
        # Right wall
        segs += _parallel_wall_pair(500, 100, 500, 300, gap=-10)

        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=15)
        closed = close_gaps(result.centerlines)
        extended = extend_to_intersections(closed)

        lines = [
            LineString([(s.start.x, s.start.y), (s.end.x, s.end.y)])
            for s in extended
        ]
        merged = unary_union(lines)
        polygons = [p for p in polygonize(merged) if p.area > 100]
        assert len(polygons) >= 2

    def test_doorway_gap_still_forms_rooms(self) -> None:
        """Parallel wall pairs with doorway gaps still form rooms."""
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union

        segs: list[WallSegment] = []
        # Exterior walls (full, no gaps)
        segs += _parallel_wall_pair(100, 100, 500, 100, gap=10)  # bottom
        segs += _parallel_wall_pair(100, 400, 500, 400, gap=-10)  # top
        segs += _parallel_wall_pair(100, 100, 100, 400, gap=10)  # left
        segs += _parallel_wall_pair(500, 100, 500, 400, gap=-10)  # right

        # Interior wall with doorway gap (x=300, from y=100 to y=200, gap, y=260 to y=400)
        segs += _parallel_wall_pair(300, 100, 300, 200, gap=10)
        segs += _parallel_wall_pair(300, 260, 300, 400, gap=10)

        result = extract_centerlines(segs, min_gap_pts=4, max_gap_pts=15)
        closed = close_gaps(result.centerlines, max_gap_pts=80)
        extended = extend_to_intersections(closed)

        lines = [
            LineString([(s.start.x, s.start.y), (s.end.x, s.end.y)])
            for s in extended
        ]
        merged = unary_union(lines)
        polygons = [p for p in polygonize(merged) if p.area > 100]
        # Interior wall should be gap-closed, forming 2 rooms
        assert len(polygons) >= 2
