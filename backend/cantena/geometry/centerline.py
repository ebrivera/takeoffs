"""Center-line extraction from parallel wall pairs.

Architectural CAD drawings represent walls as parallel line pairs
(inner face + outer face) separated by wall thickness (~5-10 pts
at typical scales).  ``polygonize()`` cannot form closed room
polygons from these because doorway gaps break continuity.

This module:
  1. Identifies parallel wall pairs by perpendicular coordinate gap.
  2. Computes the center-line for each pair.
  3. Merges overlapping center-line projections.
  4. Closes doorway-sized gaps between collinear center-lines.

The result is a clean set of single-line wall segments suitable
for ``polygonize()``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cantena.geometry.extractor import Point2D
from cantena.geometry.walls import Orientation, WallSegment

# Tolerance for grouping segments at the "same" perpendicular coordinate.
_COORD_GROUP_TOLERANCE_PTS = 2.0


@dataclass(frozen=True)
class CenterlineResult:
    """Output of center-line extraction."""

    centerlines: list[WallSegment]
    unpaired: list[WallSegment]
    wall_thickness_pts: float | None


def _seg_perp_coord(seg: WallSegment) -> float:
    """Return the perpendicular coordinate: y for horizontal, x for vertical."""
    if seg.orientation == Orientation.HORIZONTAL:
        return (seg.start.y + seg.end.y) / 2.0
    return (seg.start.x + seg.end.x) / 2.0


def _seg_parallel_range(seg: WallSegment) -> tuple[float, float]:
    """Return (min, max) of the parallel coordinate."""
    if seg.orientation == Orientation.HORIZONTAL:
        return (min(seg.start.x, seg.end.x), max(seg.start.x, seg.end.x))
    return (min(seg.start.y, seg.end.y), max(seg.start.y, seg.end.y))


def _group_by_perp_coord(
    segments: list[WallSegment],
    tolerance: float = _COORD_GROUP_TOLERANCE_PTS,
) -> dict[float, list[WallSegment]]:
    """Group segments by their perpendicular coordinate.

    Segments within *tolerance* of each other are merged into the
    same group, keyed by the mean perpendicular coordinate.
    """
    if not segments:
        return {}

    coords = [(i, _seg_perp_coord(s)) for i, s in enumerate(segments)]
    coords.sort(key=lambda t: t[1])

    groups: dict[float, list[WallSegment]] = {}
    current_indices: list[int] = [coords[0][0]]
    current_sum = coords[0][1]

    for k in range(1, len(coords)):
        idx, val = coords[k]
        prev_val = coords[k - 1][1]
        if val - prev_val <= tolerance:
            current_indices.append(idx)
            current_sum += val
        else:
            # Finalize current group
            mean = current_sum / len(current_indices)
            groups[mean] = [segments[i] for i in current_indices]
            current_indices = [idx]
            current_sum = val

    # Finalize last group
    if current_indices:
        mean = current_sum / len(current_indices)
        groups[mean] = [segments[i] for i in current_indices]

    return groups


def _merge_ranges(
    ranges: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Merge overlapping 1D ranges.

    Input: list of (min, max) tuples, possibly overlapping.
    Output: list of merged (min, max) tuples, sorted.
    """
    if not ranges:
        return []
    sorted_ranges = sorted(ranges)
    merged: list[tuple[float, float]] = [sorted_ranges[0]]
    for lo, hi in sorted_ranges[1:]:
        prev_lo, prev_hi = merged[-1]
        if lo <= prev_hi:
            merged[-1] = (prev_lo, max(prev_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _make_segment(
    orientation: Orientation,
    perp_coord: float,
    par_lo: float,
    par_hi: float,
) -> WallSegment:
    """Create a WallSegment from orientation, perpendicular coord, and parallel range."""
    if orientation == Orientation.HORIZONTAL:
        start = Point2D(par_lo, perp_coord)
        end = Point2D(par_hi, perp_coord)
    else:
        start = Point2D(perp_coord, par_lo)
        end = Point2D(perp_coord, par_hi)
    length = abs(par_hi - par_lo)
    return WallSegment(
        start=start,
        end=end,
        thickness_pts=None,
        orientation=orientation,
        length_pts=length,
    )


def extract_centerlines(
    segments: list[WallSegment],
    min_gap_pts: float = 4.0,
    max_gap_pts: float = 18.0,
) -> CenterlineResult:
    """Extract center-lines from parallel wall pairs.

    Parameters
    ----------
    segments:
        Wall segments (H/V only; angled are ignored).
    min_gap_pts:
        Minimum perpendicular gap to consider a parallel pair (pts).
    max_gap_pts:
        Maximum perpendicular gap to consider a parallel pair (pts).

    Returns
    -------
    ``CenterlineResult`` with center-lines and any unpaired segments.
    """
    h_segs = [s for s in segments if s.orientation == Orientation.HORIZONTAL]
    v_segs = [s for s in segments if s.orientation == Orientation.VERTICAL]

    centerlines: list[WallSegment] = []
    unpaired: list[WallSegment] = []
    thicknesses: list[float] = []

    for orientation, segs in [
        (Orientation.HORIZONTAL, h_segs),
        (Orientation.VERTICAL, v_segs),
    ]:
        groups = _group_by_perp_coord(segs)
        if not groups:
            continue

        sorted_keys = sorted(groups.keys())
        used: set[float] = set()

        # Greedy pair: each group pairs with its nearest unused neighbor
        # at wall-thickness distance.
        for i, k1 in enumerate(sorted_keys):
            if k1 in used:
                continue
            for j in range(i + 1, len(sorted_keys)):
                k2 = sorted_keys[j]
                if k2 in used:
                    continue
                gap = abs(k2 - k1)
                if gap < min_gap_pts:
                    continue
                if gap > max_gap_pts:
                    break  # sorted, so no point looking further
                # Found a pair
                center = (k1 + k2) / 2.0
                thicknesses.append(gap)
                # Project all segments from both groups onto center
                all_ranges: list[tuple[float, float]] = []
                for seg in groups[k1] + groups[k2]:
                    all_ranges.append(_seg_parallel_range(seg))
                merged = _merge_ranges(all_ranges)
                for par_lo, par_hi in merged:
                    if par_hi - par_lo < 1.0:
                        continue
                    centerlines.append(
                        _make_segment(orientation, center, par_lo, par_hi)
                    )
                used.add(k1)
                used.add(k2)
                break

        # Collect unpaired segments
        for key in sorted_keys:
            if key not in used:
                unpaired.extend(groups[key])

    wall_thickness: float | None = None
    if thicknesses:
        thicknesses.sort()
        wall_thickness = thicknesses[len(thicknesses) // 2]

    return CenterlineResult(
        centerlines=centerlines,
        unpaired=unpaired,
        wall_thickness_pts=wall_thickness,
    )


def close_gaps(
    centerlines: list[WallSegment],
    max_gap_pts: float = 60.0,
) -> list[WallSegment]:
    """Close doorway-sized gaps between collinear center-line segments.

    Merges center-lines that share the same perpendicular coordinate
    and have a parallel gap smaller than *max_gap_pts*.

    Parameters
    ----------
    centerlines:
        Center-line segments (from ``extract_centerlines``).
    max_gap_pts:
        Maximum gap to bridge (pts).  At 1/4"=1'-0" scale,
        60 pts ≈ 3.3 real feet — a standard doorway.

    Returns
    -------
    New list of center-line segments with doorway gaps bridged.
    """
    h_segs = [s for s in centerlines if s.orientation == Orientation.HORIZONTAL]
    v_segs = [s for s in centerlines if s.orientation == Orientation.VERTICAL]
    result: list[WallSegment] = []

    for orientation, segs in [
        (Orientation.HORIZONTAL, h_segs),
        (Orientation.VERTICAL, v_segs),
    ]:
        groups = _group_by_perp_coord(segs, tolerance=1.0)

        for perp_coord, group in groups.items():
            ranges = [_seg_parallel_range(s) for s in group]
            ranges.sort()

            # Bridge gaps smaller than max_gap_pts
            bridged: list[tuple[float, float]] = [ranges[0]] if ranges else []
            for lo, hi in ranges[1:]:
                prev_lo, prev_hi = bridged[-1]
                gap = lo - prev_hi
                if gap <= max_gap_pts:
                    bridged[-1] = (prev_lo, max(prev_hi, hi))
                else:
                    bridged.append((lo, hi))

            for par_lo, par_hi in bridged:
                if par_hi - par_lo < 1.0:
                    continue
                result.append(
                    _make_segment(orientation, perp_coord, par_lo, par_hi)
                )

    return result


def extend_to_intersections(
    centerlines: list[WallSegment],
    max_extension_pts: float = 80.0,
) -> list[WallSegment]:
    """Extend center-line endpoints to meet nearby perpendicular lines.

    For each center-line endpoint, if a perpendicular center-line
    passes within *max_extension_pts*, extend to meet it.  This
    closes T-junction and L-junction gaps left after center-line
    extraction (doorways are typically 50–75 pts at 1/4" scale).

    Parameters
    ----------
    centerlines:
        Center-line segments.
    max_extension_pts:
        Maximum distance to extend an endpoint (pts).
        Default 80 covers standard doorways at common arch scales.

    Returns
    -------
    New list of segments with endpoints extended.
    """
    h_segs = [s for s in centerlines if s.orientation == Orientation.HORIZONTAL]
    v_segs = [s for s in centerlines if s.orientation == Orientation.VERTICAL]

    extended_h = list(h_segs)
    extended_v = list(v_segs)

    # Extend horizontal endpoints to nearby vertical lines
    for i, h in enumerate(extended_h):
        h_y = (h.start.y + h.end.y) / 2.0
        h_x_min = min(h.start.x, h.end.x)
        h_x_max = max(h.start.x, h.end.x)

        for v in v_segs:
            v_x = (v.start.x + v.end.x) / 2.0
            v_y_min = min(v.start.y, v.end.y)
            v_y_max = max(v.start.y, v.end.y)

            # Check if the vertical line spans this horizontal line's y
            if not (v_y_min - max_extension_pts <= h_y <= v_y_max + max_extension_pts):
                continue

            # Check if extending the left end reaches this vertical
            if 0 < h_x_min - v_x <= max_extension_pts:
                h_x_min = v_x
            # Check if extending the right end reaches this vertical
            if 0 < v_x - h_x_max <= max_extension_pts:
                h_x_max = v_x

        if h_x_min != min(h.start.x, h.end.x) or h_x_max != max(h.start.x, h.end.x):
            extended_h[i] = _make_segment(
                Orientation.HORIZONTAL, h_y, h_x_min, h_x_max
            )

    # Extend vertical endpoints to nearby horizontal lines
    for i, v in enumerate(extended_v):
        v_x = (v.start.x + v.end.x) / 2.0
        v_y_min = min(v.start.y, v.end.y)
        v_y_max = max(v.start.y, v.end.y)

        for h in h_segs:
            h_y = (h.start.y + h.end.y) / 2.0
            h_x_min = min(h.start.x, h.end.x)
            h_x_max = max(h.start.x, h.end.x)

            # Check if the horizontal line spans this vertical line's x
            if not (h_x_min - max_extension_pts <= v_x <= h_x_max + max_extension_pts):
                continue

            # Check if extending the top end reaches this horizontal
            if 0 < v_y_min - h_y <= max_extension_pts:
                v_y_min = h_y
            # Check if extending the bottom end reaches this horizontal
            if 0 < h_y - v_y_max <= max_extension_pts:
                v_y_max = h_y

        if v_y_min != min(v.start.y, v.end.y) or v_y_max != max(v.start.y, v.end.y):
            extended_v[i] = _make_segment(
                Orientation.VERTICAL, v_x, v_y_min, v_y_max
            )

    return extended_h + extended_v
