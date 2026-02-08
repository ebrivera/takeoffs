"""Vector path extraction from PDF pages using PyMuPDF."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


class PathType(StrEnum):
    """Type of vector path extracted from a PDF."""

    LINE = "line"
    RECT = "rect"
    CURVE = "curve"
    POLYLINE = "polyline"


@dataclass(frozen=True)
class Point2D:
    """A 2D point in PDF coordinate space (units: points)."""

    x: float
    y: float


@dataclass(frozen=True)
class BoundingRect:
    """Axis-aligned bounding rectangle in PDF points."""

    x: float
    y: float
    width: float
    height: float

    def contains(self, point: Point2D) -> bool:
        """Return True if *point* lies within this rectangle."""
        return (
            self.x <= point.x <= self.x + self.width
            and self.y <= point.y <= self.y + self.height
        )

    def intersects(self, other: BoundingRect) -> bool:
        """Return True if this rectangle overlaps with *other*."""
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )


@dataclass(frozen=True)
class VectorPath:
    """A single vector path extracted from a PDF page."""

    path_type: PathType
    points: list[Point2D]
    stroke_color: tuple[float, float, float] | None
    fill_color: tuple[float, float, float] | None
    line_width: float
    bounding_rect: BoundingRect


@dataclass(frozen=True)
class DrawingData:
    """All vector drawing data extracted from a single PDF page."""

    paths: list[VectorPath] = field(default_factory=list)
    page_width_pts: float = 0.0
    page_height_pts: float = 0.0
    page_size_inches: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class DrawingStats:
    """Summary statistics for extracted drawing data."""

    path_count: int
    line_count: int
    rect_count: int
    curve_count: int
    polyline_count: int
    total_line_length_pts: float
    bounding_box: BoundingRect | None


class VectorExtractor:
    """Extracts vector drawing paths from PDF pages using PyMuPDF."""

    def extract(self, page: fitz.Page) -> DrawingData:
        """Extract all vector paths from a PDF page.

        Returns a :class:`DrawingData` containing structured path data
        in PDF coordinate space (points, 72 pts = 1 inch).
        """
        rect = page.rect
        page_w: float = rect.width
        page_h: float = rect.height

        raw_drawings: list[dict[str, object]] = page.get_drawings()
        paths: list[VectorPath] = []

        for drawing in raw_drawings:
            extracted = self._convert_drawing(drawing)
            if extracted:
                paths.extend(extracted)

        return DrawingData(
            paths=paths,
            page_width_pts=page_w,
            page_height_pts=page_h,
            page_size_inches=(page_w / 72.0, page_h / 72.0),
        )

    def filter_by_region(
        self, data: DrawingData, region: BoundingRect
    ) -> DrawingData:
        """Return only paths within or intersecting *region*."""
        filtered = [
            p for p in data.paths if p.bounding_rect.intersects(region)
        ]
        return DrawingData(
            paths=filtered,
            page_width_pts=data.page_width_pts,
            page_height_pts=data.page_height_pts,
            page_size_inches=data.page_size_inches,
        )

    def get_stats(self, data: DrawingData) -> DrawingStats:
        """Compute summary statistics for *data*."""
        line_count = sum(
            1 for p in data.paths if p.path_type == PathType.LINE
        )
        rect_count = sum(
            1 for p in data.paths if p.path_type == PathType.RECT
        )
        curve_count = sum(
            1 for p in data.paths if p.path_type == PathType.CURVE
        )
        polyline_count = sum(
            1 for p in data.paths if p.path_type == PathType.POLYLINE
        )

        total_length = 0.0
        for p in data.paths:
            if p.path_type == PathType.LINE and len(p.points) == 2:
                dx = p.points[1].x - p.points[0].x
                dy = p.points[1].y - p.points[0].y
                total_length += math.sqrt(dx * dx + dy * dy)

        bbox = self._compute_bounding_box(data.paths)

        return DrawingStats(
            path_count=len(data.paths),
            line_count=line_count,
            rect_count=rect_count,
            curve_count=curve_count,
            polyline_count=polyline_count,
            total_line_length_pts=total_length,
            bounding_box=bbox,
        )

    def _convert_drawing(
        self, drawing: dict[str, object]
    ) -> list[VectorPath]:
        """Convert a PyMuPDF drawing dict into VectorPath objects."""
        items = drawing.get("items", [])
        if not isinstance(items, list) or not items:
            return []

        stroke_color = self._extract_color(drawing.get("color"))
        fill_color = self._extract_color(drawing.get("fill"))
        raw_width = drawing.get("width")
        line_width = float(raw_width) if isinstance(raw_width, (int, float)) else 0.0

        paths: list[VectorPath] = []

        for item in items:
            if not isinstance(item, tuple) or len(item) < 2:
                continue

            kind = item[0]
            if kind == "l" and len(item) == 3:
                # Line segment: ("l", Point, Point)
                p1, p2 = item[1], item[2]
                pts = [
                    Point2D(float(p1.x), float(p1.y)),
                    Point2D(float(p2.x), float(p2.y)),
                ]
                paths.append(
                    VectorPath(
                        path_type=PathType.LINE,
                        points=pts,
                        stroke_color=stroke_color,
                        fill_color=fill_color,
                        line_width=line_width,
                        bounding_rect=self._bbox_from_points(pts),
                    )
                )
            elif kind == "re" and len(item) >= 2:
                # Rectangle: ("re", Rect, orientation_flag)
                r = item[1]
                corners = [
                    Point2D(float(r.x0), float(r.y0)),
                    Point2D(float(r.x1), float(r.y0)),
                    Point2D(float(r.x1), float(r.y1)),
                    Point2D(float(r.x0), float(r.y1)),
                ]
                paths.append(
                    VectorPath(
                        path_type=PathType.RECT,
                        points=corners,
                        stroke_color=stroke_color,
                        fill_color=fill_color,
                        line_width=line_width,
                        bounding_rect=BoundingRect(
                            x=float(r.x0),
                            y=float(r.y0),
                            width=float(r.width),
                            height=float(r.height),
                        ),
                    )
                )
            elif kind == "c" and len(item) == 5:
                # Cubic Bézier curve: ("c", P0, P1, P2, P3)
                pts = [
                    Point2D(float(item[i].x), float(item[i].y))
                    for i in range(1, 5)
                ]
                paths.append(
                    VectorPath(
                        path_type=PathType.CURVE,
                        points=pts,
                        stroke_color=stroke_color,
                        fill_color=fill_color,
                        line_width=line_width,
                        bounding_rect=self._bbox_from_points(pts),
                    )
                )
            elif kind == "qu" and len(item) == 2:
                # Quad (4-point polygon): ("qu", Quad)
                q = item[1]
                pts = [
                    Point2D(float(q.ul.x), float(q.ul.y)),
                    Point2D(float(q.ur.x), float(q.ur.y)),
                    Point2D(float(q.lr.x), float(q.lr.y)),
                    Point2D(float(q.ll.x), float(q.ll.y)),
                ]
                paths.append(
                    VectorPath(
                        path_type=PathType.POLYLINE,
                        points=pts,
                        stroke_color=stroke_color,
                        fill_color=fill_color,
                        line_width=line_width,
                        bounding_rect=self._bbox_from_points(pts),
                    )
                )

        return paths

    @staticmethod
    def _extract_color(
        raw: object,
    ) -> tuple[float, float, float] | None:
        """Normalise a PyMuPDF colour value to an RGB tuple or None."""
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)):
            if len(raw) == 3:
                return (float(raw[0]), float(raw[1]), float(raw[2]))
            if len(raw) == 1:
                # Grayscale → RGB
                g = float(raw[0])
                return (g, g, g)
        return None

    @staticmethod
    def _bbox_from_points(points: list[Point2D]) -> BoundingRect:
        """Compute axis-aligned bounding rect from a list of points."""
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return BoundingRect(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
        )

    @staticmethod
    def _compute_bounding_box(
        paths: list[VectorPath],
    ) -> BoundingRect | None:
        """Compute overall bounding box of all paths."""
        if not paths:
            return None

        min_x = min(p.bounding_rect.x for p in paths)
        min_y = min(p.bounding_rect.y for p in paths)
        max_x = max(
            p.bounding_rect.x + p.bounding_rect.width for p in paths
        )
        max_y = max(
            p.bounding_rect.y + p.bounding_rect.height for p in paths
        )
        return BoundingRect(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
        )
