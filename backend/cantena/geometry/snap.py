"""Endpoint snapping to close near-miss gaps in wall segments.

Shapely polygonize() requires exact endpoint equality to form closed
polygons.  CAD exports often have tiny floating-point gaps (1–3 pts).
This module clusters nearby endpoints and replaces each cluster with
its centroid, producing segments that polygonize cleanly.

If performance becomes an issue with large point sets, the O(n²)
pairwise distance check can be replaced with a scipy.spatial.KDTree
approach — see ``_cluster_endpoints`` for the upgrade path.
"""

from __future__ import annotations

import math

from cantena.geometry.extractor import Point2D
from cantena.geometry.walls import Orientation, WallSegment


def _distance(a: Point2D, b: Point2D) -> float:
    """Euclidean distance between two points."""
    return math.hypot(a.x - b.x, a.y - b.y)


def snap_to_grid(point: Point2D, grid_size_pts: float = 1.0) -> Point2D:
    """Round *point* coordinates to the nearest grid point.

    Parameters
    ----------
    point:
        The point to snap.
    grid_size_pts:
        Grid spacing in PDF points (default 1.0).

    Returns
    -------
    A new ``Point2D`` with coordinates rounded to the nearest multiple
    of *grid_size_pts*.
    """
    return Point2D(
        x=round(point.x / grid_size_pts) * grid_size_pts,
        y=round(point.y / grid_size_pts) * grid_size_pts,
    )


def _cluster_endpoints(
    points: list[Point2D],
    tolerance_pts: float,
) -> dict[tuple[float, float], Point2D]:
    """Cluster nearby points and map each original point to its cluster centroid.

    Uses a simple O(n²) pairwise distance check.  For large point sets
    (>10 000) a ``scipy.spatial.KDTree`` would be more efficient — build
    the tree, query ``ball_point(tolerance_pts)`` for each point, and
    union-find the clusters.

    Returns
    -------
    A mapping from ``(x, y)`` tuples of original points to their
    replacement ``Point2D`` centroids.
    """
    n = len(points)
    parent: list[int] = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # O(n²) pairwise — fine for typical wall segment counts (<1000 endpoints).
    for i in range(n):
        for j in range(i + 1, n):
            if _distance(points[i], points[j]) <= tolerance_pts:
                union(i, j)

    # Group by cluster root.
    clusters: dict[int, list[Point2D]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(points[i])

    # Compute centroid per cluster.
    mapping: dict[tuple[float, float], Point2D] = {}
    for members in clusters.values():
        cx = sum(p.x for p in members) / len(members)
        cy = sum(p.y for p in members) / len(members)
        centroid = Point2D(cx, cy)
        for p in members:
            mapping[(p.x, p.y)] = centroid

    return mapping


def _reclassify_orientation(start: Point2D, end: Point2D) -> Orientation:
    """Determine orientation from snapped endpoints."""
    dx = abs(end.x - start.x)
    dy = abs(end.y - start.y)
    angle_deg = math.degrees(math.atan2(dy, dx)) if (dx or dy) else 0.0
    if angle_deg <= 2.0:
        return Orientation.HORIZONTAL
    if angle_deg >= 88.0:
        return Orientation.VERTICAL
    return Orientation.ANGLED


def snap_endpoints(
    segments: list[WallSegment],
    tolerance_pts: float = 3.0,
) -> list[WallSegment]:
    """Snap nearby wall-segment endpoints together.

    Parameters
    ----------
    segments:
        Wall segments whose endpoints may have small gaps.
    tolerance_pts:
        Maximum distance (in PDF points) between two endpoints
        for them to be snapped to a shared centroid.  Default 3.0.

    Returns
    -------
    A new list of ``WallSegment`` objects with snapped endpoints.
    Duplicate segments (same start and end after snapping) are removed.
    """
    if not segments:
        return []

    # Collect all unique endpoints.
    seen: set[tuple[float, float]] = set()
    unique_points: list[Point2D] = []
    for seg in segments:
        for pt in (seg.start, seg.end):
            key = (pt.x, pt.y)
            if key not in seen:
                seen.add(key)
                unique_points.append(pt)

    # Build cluster mapping.
    mapping = _cluster_endpoints(unique_points, tolerance_pts)

    # Rebuild segments with snapped endpoints, removing duplicates.
    result: list[WallSegment] = []
    seen_pairs: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for seg in segments:
        new_start = mapping[(seg.start.x, seg.start.y)]
        new_end = mapping[(seg.end.x, seg.end.y)]

        # Skip degenerate (zero-length) segments.
        if new_start.x == new_end.x and new_start.y == new_end.y:
            continue

        # Canonical key for duplicate detection (order-independent).
        key_a = (new_start.x, new_start.y)
        key_b = (new_end.x, new_end.y)
        pair_key = (min(key_a, key_b), max(key_a, key_b))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        new_length = _distance(new_start, new_end)
        new_orientation = _reclassify_orientation(new_start, new_end)

        result.append(
            WallSegment(
                start=new_start,
                end=new_end,
                thickness_pts=seg.thickness_pts,
                orientation=new_orientation,
                length_pts=new_length,
            )
        )

    return result
