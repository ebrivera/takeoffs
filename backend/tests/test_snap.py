"""Tests for cantena.geometry.snap — endpoint snapping and grid alignment."""

from __future__ import annotations

import math

import pytest

from cantena.geometry.extractor import Point2D
from cantena.geometry.snap import snap_endpoints, snap_to_grid
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


class TestSnapEndpoints:
    """Verify endpoint snapping clusters nearby points correctly."""

    def test_endpoints_within_tolerance_snap_together(self) -> None:
        """Two endpoints 2pts apart should snap to shared centroid."""
        seg_a = _seg((0, 0), (100, 0))
        seg_b = _seg((100, 2), (200, 2))  # start is 2pts from seg_a end

        result = snap_endpoints([seg_a, seg_b], tolerance_pts=3.0)

        assert len(result) == 2
        # After snapping, seg_a's end and seg_b's start should be the same point.
        assert result[0].end.x == result[1].start.x
        assert result[0].end.y == result[1].start.y
        # Centroid of (100,0) and (100,2) => (100, 1).
        assert result[0].end.x == pytest.approx(100.0)
        assert result[0].end.y == pytest.approx(1.0)

    def test_endpoints_outside_tolerance_stay_separate(self) -> None:
        """Two endpoints 5pts apart should NOT snap with tolerance=3."""
        seg_a = _seg((0, 0), (100, 0))
        seg_b = _seg((100, 5), (200, 5))

        result = snap_endpoints([seg_a, seg_b], tolerance_pts=3.0)

        assert len(result) == 2
        # seg_a end stays at (100, 0), seg_b start stays at (100, 5).
        assert result[0].end.y == pytest.approx(0.0)
        assert result[1].start.y == pytest.approx(5.0)

    def test_duplicate_segments_removed(self) -> None:
        """Segments that become identical after snapping are deduplicated."""
        seg_a = _seg((0, 0), (100, 0))
        seg_b = _seg((0, 1), (100, 1))  # within tolerance of seg_a

        result = snap_endpoints([seg_a, seg_b], tolerance_pts=3.0)

        assert len(result) == 1

    def test_empty_input_returns_empty(self) -> None:
        """An empty segment list should return an empty list."""
        result = snap_endpoints([], tolerance_pts=3.0)

        assert result == []

    def test_exactly_matching_endpoints_unchanged(self) -> None:
        """Segments that already share exact endpoints stay the same."""
        seg_a = _seg((0, 0), (100, 0))
        seg_b = _seg((100, 0), (200, 0))

        result = snap_endpoints([seg_a, seg_b], tolerance_pts=3.0)

        assert len(result) == 2
        assert result[0].end.x == pytest.approx(100.0)
        assert result[0].end.y == pytest.approx(0.0)
        assert result[1].start.x == pytest.approx(100.0)
        assert result[1].start.y == pytest.approx(0.0)

    def test_preserves_thickness(self) -> None:
        """Snapping preserves the original wall thickness."""
        seg = _seg((0, 0), (100, 0), thickness=6.0)

        result = snap_endpoints([seg], tolerance_pts=3.0)

        assert len(result) == 1
        assert result[0].thickness_pts == 6.0

    def test_length_recomputed_after_snapping(self) -> None:
        """Segment length is recomputed from snapped endpoints."""
        seg = _seg((0, 0), (100, 1))  # slightly off-horizontal

        result = snap_endpoints([seg], tolerance_pts=3.0)

        expected = math.hypot(
            result[0].end.x - result[0].start.x,
            result[0].end.y - result[0].start.y,
        )
        assert result[0].length_pts == pytest.approx(expected)

    def test_three_way_cluster(self) -> None:
        """Three endpoints within tolerance form a single cluster."""
        # Three segments meeting near (100, 100) with slight offsets.
        seg_a = _seg((0, 100), (100, 100))
        seg_b = _seg((101, 101), (200, 101))
        seg_c = _seg((99, 99), (99, 0))

        result = snap_endpoints([seg_a, seg_b, seg_c], tolerance_pts=3.0)

        # All three near-endpoints should have snapped to a shared centroid.
        centroid_x = (100 + 101 + 99) / 3
        centroid_y = (100 + 101 + 99) / 3

        # seg_a's end, seg_b's start, seg_c's start should all be the centroid.
        assert result[0].end.x == pytest.approx(centroid_x)
        assert result[0].end.y == pytest.approx(centroid_y)
        assert result[1].start.x == pytest.approx(centroid_x)
        assert result[1].start.y == pytest.approx(centroid_y)
        assert result[2].start.x == pytest.approx(centroid_x)
        assert result[2].start.y == pytest.approx(centroid_y)


class TestSnapToGrid:
    """Verify grid snapping rounds coordinates correctly."""

    def test_rounds_to_nearest_grid_point(self) -> None:
        """Coordinates round to the nearest grid multiple."""
        result = snap_to_grid(Point2D(1.3, 2.7), grid_size_pts=1.0)

        assert result.x == pytest.approx(1.0)
        assert result.y == pytest.approx(3.0)

    def test_already_on_grid_unchanged(self) -> None:
        """Point already on the grid stays the same."""
        result = snap_to_grid(Point2D(5.0, 10.0), grid_size_pts=1.0)

        assert result.x == pytest.approx(5.0)
        assert result.y == pytest.approx(10.0)

    def test_half_grid_rounds_to_even(self) -> None:
        """Python round() uses banker's rounding at exactly 0.5."""
        result = snap_to_grid(Point2D(0.5, 1.5), grid_size_pts=1.0)

        assert result.x == pytest.approx(0.0)
        assert result.y == pytest.approx(2.0)

    def test_custom_grid_size(self) -> None:
        """A 0.5-pt grid rounds to half-point increments."""
        result = snap_to_grid(Point2D(1.3, 2.8), grid_size_pts=0.5)

        assert result.x == pytest.approx(1.5)
        assert result.y == pytest.approx(3.0)

    def test_large_grid_size(self) -> None:
        """A 10-pt grid rounds to multiples of 10."""
        result = snap_to_grid(Point2D(23.0, 47.0), grid_size_pts=10.0)

        assert result.x == pytest.approx(20.0)
        assert result.y == pytest.approx(50.0)
