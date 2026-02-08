"""Wall detection and room boundary identification from vector geometry."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cantena.geometry.extractor import DrawingData

from cantena.geometry.extractor import PathType, Point2D, VectorPath


class Orientation(StrEnum):
    """Orientation of a wall segment."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    ANGLED = "angled"


# Minimum stroke width in PDF points to consider a line a wall.
# 0.5mm ≈ 1.42 pts (72 pts/inch, 25.4 mm/inch).
_MIN_WALL_WIDTH_PTS = 1.0

# Minimum segment length in PDF points.
# 36 pts ≈ 0.5" on paper ≈ 2 ft at 1/4" scale.
# Excludes short annotation ticks, dimension leader lines, and symbols.
_MIN_WALL_LENGTH_PTS = 36.0

# Angular tolerance in degrees for H/V classification.
_ANGLE_TOLERANCE_DEG = 2.0

# Maximum RGB component sum for "dark" colours (black/dark-gray).
_MAX_DARK_COLOR_SUM = 1.0

# IQR multiplier for outlier removal (e.g. title block borders).
_OUTLIER_IQR_FACTOR = 3.0


@dataclass(frozen=True)
class WallSegment:
    """A detected wall segment."""

    start: Point2D
    end: Point2D
    thickness_pts: float | None
    orientation: Orientation
    length_pts: float


@dataclass(frozen=True)
class WallAnalysis:
    """Result of wall detection on a drawing."""

    segments: list[WallSegment] = field(default_factory=list)
    total_wall_length_pts: float = 0.0
    detected_wall_thickness_pts: float | None = None
    outer_boundary: list[Point2D] | None = None


def _line_angle_deg(p1: Point2D, p2: Point2D) -> float:
    """Return the angle (0-180) of the line from *p1* to *p2*."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return abs(math.degrees(math.atan2(dy, dx))) % 180


def _classify_orientation(p1: Point2D, p2: Point2D) -> Orientation:
    angle = _line_angle_deg(p1, p2)
    if angle <= _ANGLE_TOLERANCE_DEG or angle >= 180 - _ANGLE_TOLERANCE_DEG:
        return Orientation.HORIZONTAL
    if abs(angle - 90) <= _ANGLE_TOLERANCE_DEG:
        return Orientation.VERTICAL
    return Orientation.ANGLED


def _is_dark_color(color: tuple[float, float, float] | None) -> bool:
    """Return True if *color* is black or dark grey."""
    if color is None:
        return True  # No stroke colour often means default black
    return sum(color) <= _MAX_DARK_COLOR_SUM


def _line_length(p1: Point2D, p2: Point2D) -> float:
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return math.sqrt(dx * dx + dy * dy)


def _lines_are_parallel_pair(
    seg_a: VectorPath,
    seg_b: VectorPath,
    min_gap: float,
    max_gap: float,
) -> float | None:
    """If two lines are parallel and within *min_gap*–*max_gap* apart, return gap."""
    if len(seg_a.points) < 2 or len(seg_b.points) < 2:
        return None

    a1, a2 = seg_a.points[0], seg_a.points[1]
    b1, b2 = seg_b.points[0], seg_b.points[1]

    angle_a = _line_angle_deg(a1, a2)
    angle_b = _line_angle_deg(b1, b2)

    # Must be roughly parallel (within 5°)
    angle_diff = abs(angle_a - angle_b)
    if angle_diff > 5 and angle_diff < 175:
        return None

    # Compute perpendicular distance between the two lines using midpoints
    mid_b = Point2D((b1.x + b2.x) / 2, (b1.y + b2.y) / 2)

    # Direction vector of line A
    dx = a2.x - a1.x
    dy = a2.y - a1.y
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.001:
        return None

    # Signed distance from mid_b to line through a1→a2
    dist = abs((mid_b.x - a1.x) * dy - (mid_b.y - a1.y) * dx) / length

    if min_gap <= dist <= max_gap:
        return dist
    return None


class WallDetector:
    """Identifies wall segments from extracted vector drawing data."""

    def detect(self, data: DrawingData) -> WallAnalysis:
        """Identify probable wall segments from vector paths.

        Heuristics:
        - Lines with heavier stroke width (≥ 1.0 pts ≈ 0.5mm)
        - Minimum length (≥ 36 pts) to exclude annotation ticks
        - Strictly horizontal or vertical (± 2°)
        - Dark colour (black / dark gray)
        - IQR-based outlier removal (e.g. title block borders)
        """
        candidates = self._filter_wall_candidates(data.paths)

        if not candidates:
            return WallAnalysis()

        # Remove length outliers (e.g. title block border lines)
        candidates = self._remove_length_outliers(candidates)

        if not candidates:
            return WallAnalysis()

        segments: list[WallSegment] = []
        thicknesses: list[float] = []

        # Check for parallel pairs to detect wall thickness
        paired: set[int] = set()
        for i, path_a in enumerate(candidates):
            for j in range(i + 1, len(candidates)):
                path_b = candidates[j]
                gap = _lines_are_parallel_pair(path_a, path_b, 2.0, 20.0)
                if gap is not None:
                    paired.add(i)
                    paired.add(j)
                    thicknesses.append(gap)

        # Build wall segments from all candidates
        for path in candidates:
            if len(path.points) < 2:
                continue
            p1, p2 = path.points[0], path.points[1]
            orientation = _classify_orientation(p1, p2)
            length = _line_length(p1, p2)
            segments.append(
                WallSegment(
                    start=p1,
                    end=p2,
                    thickness_pts=None,
                    orientation=orientation,
                    length_pts=length,
                )
            )

        total_length = sum(seg.length_pts for seg in segments)
        median_thickness = (
            statistics.median(thicknesses) if thicknesses else None
        )

        # Try to find outer boundary from wall endpoints
        boundary = self._find_outer_boundary(segments)

        return WallAnalysis(
            segments=segments,
            total_wall_length_pts=total_length,
            detected_wall_thickness_pts=median_thickness,
            outer_boundary=boundary,
        )

    def compute_enclosed_area_pts(
        self, segments: list[WallSegment]
    ) -> float | None:
        """Compute gross floor area from wall segments using Shapely.

        Uses the convex hull of all wall endpoints as the outer boundary.
        Returns area in square PDF points, or None if insufficient data.
        """
        from shapely.geometry import MultiPoint

        points = []
        for seg in segments:
            points.append((seg.start.x, seg.start.y))
            points.append((seg.end.x, seg.end.y))

        if len(points) < 3:
            return None

        mp = MultiPoint(points)
        hull = mp.convex_hull

        area: float = hull.area
        if area <= 0:
            return None
        return area

    def _filter_wall_candidates(
        self, paths: list[VectorPath]
    ) -> list[VectorPath]:
        """Filter paths to those likely representing walls."""
        candidates: list[VectorPath] = []
        for path in paths:
            if path.path_type != PathType.LINE:
                continue
            if len(path.points) < 2:
                continue
            # Stroke width check
            if path.line_width < _MIN_WALL_WIDTH_PTS:
                continue
            # Minimum length check (excludes annotation ticks)
            length = _line_length(path.points[0], path.points[1])
            if length < _MIN_WALL_LENGTH_PTS:
                continue
            # Color check
            if not _is_dark_color(path.stroke_color):
                continue
            # Orientation check (H or V within tolerance)
            orientation = _classify_orientation(
                path.points[0], path.points[1]
            )
            if orientation == Orientation.ANGLED:
                continue

            candidates.append(path)
        return candidates

    @staticmethod
    def _remove_length_outliers(
        candidates: list[VectorPath],
    ) -> list[VectorPath]:
        """Remove extreme length outliers using IQR method.

        Title block borders and other non-wall lines are often
        much longer than any structural wall. This removes lines
        above Q3 + 3*IQR.
        """
        if len(candidates) < 4:
            return candidates

        lengths = sorted(
            _line_length(p.points[0], p.points[1])
            for p in candidates
        )
        q1 = lengths[len(lengths) // 4]
        q3 = lengths[3 * len(lengths) // 4]
        iqr = q3 - q1
        upper = q3 + _OUTLIER_IQR_FACTOR * iqr

        return [
            p
            for p in candidates
            if _line_length(p.points[0], p.points[1]) <= upper
        ]

    def _find_outer_boundary(
        self, segments: list[WallSegment]
    ) -> list[Point2D] | None:
        """Attempt to find the outer boundary as a convex hull."""
        from shapely.geometry import MultiPoint, Polygon

        points = []
        for seg in segments:
            points.append((seg.start.x, seg.start.y))
            points.append((seg.end.x, seg.end.y))

        if len(points) < 3:
            return None

        mp = MultiPoint(points)
        hull = mp.convex_hull

        if not isinstance(hull, Polygon) or hull.is_empty:
            return None

        coords = list(hull.exterior.coords)
        return [Point2D(x, y) for x, y in coords]
