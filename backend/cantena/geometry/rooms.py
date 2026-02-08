"""Room polygon reconstruction via Shapely polygonize.

Converts snapped wall segments into enclosed room polygons using
``shapely.ops.polygonize``.  This produces accurate per-room areas
instead of the convex-hull approximation from ``WallDetector``.

Workflow:
  1. Snap endpoints (via US-371 ``snap_endpoints``).
  2. Extend wall segments slightly at both ends (1 pt) to ensure overlap.
  3. Convert to Shapely ``LineString`` objects.
  4. Union linework with ``unary_union``.
  5. Call ``polygonize()`` to form closed polygons.
  6. Filter tiny artifacts (<100 sq pts) and page-boundary polygons
     (>80% of bounding page area).
  7. Fall back to convex hull if ``polygonize`` produces 0 rooms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shapely.geometry import Polygon as ShapelyPolygon

    from cantena.geometry.walls import WallSegment

from cantena.geometry.extractor import Point2D
from cantena.geometry.snap import snap_endpoints

# Minimum polygon area in square PDF points to keep (filters tiny artifacts).
_MIN_ROOM_AREA_PTS = 100.0

# Maximum fraction of page area for a single polygon (filters page boundary).
_MAX_PAGE_AREA_FRACTION = 0.80

# Extension length in PDF points added to each segment endpoint.
_SEGMENT_EXTENSION_PTS = 1.0


@dataclass(frozen=True)
class DetectedRoom:
    """A single detected room polygon."""

    polygon_pts: list[tuple[float, float]]
    area_pts: float
    area_sf: float | None
    perimeter_pts: float
    perimeter_lf: float | None
    centroid: Point2D
    label: str | None
    room_index: int


@dataclass(frozen=True)
class RoomAnalysis:
    """Result of room detection on a drawing."""

    rooms: list[DetectedRoom] = field(default_factory=list)
    total_area_pts: float = 0.0
    total_area_sf: float | None = None
    room_count: int = 0
    outer_boundary_polygon: list[tuple[float, float]] | None = None
    polygonize_success: bool = False


def _extend_segment(
    start: Point2D,
    end: Point2D,
    extension: float,
) -> tuple[Point2D, Point2D]:
    """Extend a segment by *extension* pts at both ends along its direction."""
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return start, end
    ux = dx / length
    uy = dy / length
    new_start = Point2D(start.x - ux * extension, start.y - uy * extension)
    new_end = Point2D(end.x + ux * extension, end.y + uy * extension)
    return new_start, new_end


def _polygon_to_detected_room(
    polygon: ShapelyPolygon,
    room_index: int,
    scale_factor: float | None,
) -> DetectedRoom:
    """Convert a Shapely polygon to a ``DetectedRoom``."""
    area_pts: float = polygon.area
    perimeter_pts: float = polygon.length
    centroid = polygon.centroid
    coords = [(float(x), float(y)) for x, y in polygon.exterior.coords]

    area_sf: float | None = None
    perimeter_lf: float | None = None
    if scale_factor is not None:
        # area_sf = area_pts * (1/72)^2 * scale_factor^2 / 144
        paper_sq_in = area_pts / (72.0 * 72.0)
        real_sq_in = paper_sq_in * scale_factor * scale_factor
        area_sf = real_sq_in / 144.0
        # perimeter_lf = perimeter_pts * (1/72) * scale_factor / 12
        paper_in = perimeter_pts / 72.0
        real_in = paper_in * scale_factor
        perimeter_lf = real_in / 12.0

    return DetectedRoom(
        polygon_pts=coords,
        area_pts=area_pts,
        area_sf=area_sf,
        perimeter_pts=perimeter_pts,
        perimeter_lf=perimeter_lf,
        centroid=Point2D(centroid.x, centroid.y),
        label=None,
        room_index=room_index,
    )


def _convex_hull_fallback(
    segments: list[WallSegment],
    scale_factor: float | None,
) -> RoomAnalysis:
    """Fall back to convex hull when polygonize produces 0 rooms."""
    from shapely.geometry import MultiPoint, Polygon

    points = []
    for seg in segments:
        points.append((seg.start.x, seg.start.y))
        points.append((seg.end.x, seg.end.y))

    if len(points) < 3:
        return RoomAnalysis()

    mp = MultiPoint(points)
    hull = mp.convex_hull

    if not isinstance(hull, Polygon) or hull.is_empty:
        return RoomAnalysis()

    room = _polygon_to_detected_room(hull, 0, scale_factor)
    coords = [(float(x), float(y)) for x, y in hull.exterior.coords]
    return RoomAnalysis(
        rooms=[room],
        total_area_pts=room.area_pts,
        total_area_sf=room.area_sf,
        room_count=1,
        outer_boundary_polygon=coords,
        polygonize_success=False,
    )


class RoomDetector:
    """Reconstructs enclosed room polygons from wall segments."""

    def detect_rooms(
        self,
        segments: list[WallSegment],
        scale_factor: float | None = None,
        page_area_pts: float | None = None,
    ) -> RoomAnalysis:
        """Detect enclosed room polygons from wall segments.

        Parameters
        ----------
        segments:
            Wall segments (will be snapped internally).
        scale_factor:
            Architectural scale factor (e.g. 48.0 for 1/4"=1'-0").
            Used to convert areas to square feet.  ``None`` skips conversion.
        page_area_pts:
            Total page area in square PDF points.  Used to filter
            page-boundary polygons.  ``None`` disables that filter.

        Returns
        -------
        ``RoomAnalysis`` with detected rooms, or a convex-hull fallback
        if ``polygonize`` fails.
        """
        from shapely.geometry import LineString, MultiPoint, Polygon
        from shapely.ops import polygonize, unary_union

        if not segments:
            return RoomAnalysis()

        # Step 1: Snap endpoints.
        snapped = snap_endpoints(segments)

        if not snapped:
            return RoomAnalysis()

        # Step 2: Extend segments slightly and convert to LineStrings.
        lines: list[LineString] = []
        for seg in snapped:
            ext_start, ext_end = _extend_segment(
                seg.start, seg.end, _SEGMENT_EXTENSION_PTS
            )
            lines.append(
                LineString(
                    [(ext_start.x, ext_start.y), (ext_end.x, ext_end.y)]
                )
            )

        # Step 3: Union all linework, then polygonize.
        merged = unary_union(lines)
        polygons: list[Polygon] = list(polygonize(merged))

        # Step 4: Filter tiny and page-boundary polygons.
        filtered: list[Polygon] = []
        for poly in polygons:
            if poly.area < _MIN_ROOM_AREA_PTS:
                continue
            if (
                page_area_pts is not None
                and poly.area > page_area_pts * _MAX_PAGE_AREA_FRACTION
            ):
                continue
            filtered.append(poly)

        # Step 5: Fallback if nothing survived.
        if not filtered:
            return _convex_hull_fallback(snapped, scale_factor)

        # Build DetectedRoom objects.
        rooms: list[DetectedRoom] = []
        for i, poly in enumerate(filtered):
            rooms.append(
                _polygon_to_detected_room(poly, i, scale_factor)
            )

        total_area_pts = sum(r.area_pts for r in rooms)
        total_area_sf: float | None = None
        if scale_factor is not None:
            total_area_sf = sum(
                r.area_sf for r in rooms if r.area_sf is not None
            )

        # Outer boundary = convex hull of all room polygon vertices.
        all_pts: list[tuple[float, float]] = []
        for r in rooms:
            all_pts.extend(r.polygon_pts)
        outer_boundary: list[tuple[float, float]] | None = None
        if len(all_pts) >= 3:
            mp = MultiPoint(all_pts)
            hull = mp.convex_hull
            if isinstance(hull, Polygon) and not hull.is_empty:
                outer_boundary = [
                    (float(x), float(y))
                    for x, y in hull.exterior.coords
                ]

        return RoomAnalysis(
            rooms=rooms,
            total_area_pts=total_area_pts,
            total_area_sf=total_area_sf,
            room_count=len(rooms),
            outer_boundary_polygon=outer_boundary,
            polygonize_success=True,
        )
