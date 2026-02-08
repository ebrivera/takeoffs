"""Scaled measurement service: PDF geometry to real-world dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

    from cantena.geometry.extractor import (
        DrawingData,
        Point2D,
        VectorExtractor,
    )
    from cantena.geometry.walls import WallDetector

from cantena.geometry.scale import (
    Confidence,
    ScaleDetector,
    ScaleResult,
)


class MeasurementConfidence(StrEnum):
    """Confidence level for computed measurements."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


def pts_to_real_sf(
    pts_squared: float, scale: ScaleResult
) -> float:
    """Convert area in square PDF points to real-world square feet.

    Formula: area_sf = area_pts * (1/72)^2 * scale_factor^2 / 144
    """
    paper_sq_in = pts_squared / (72.0 * 72.0)
    real_sq_in = paper_sq_in * scale.scale_factor * scale.scale_factor
    return real_sq_in / 144.0


def pts_to_real_lf(pts: float, scale: ScaleResult) -> float:
    """Convert length in PDF points to real-world linear feet.

    Formula: length_lf = length_pts * (1/72) * scale_factor / 12
    """
    paper_in = pts / 72.0
    real_in = paper_in * scale.scale_factor
    return real_in / 12.0


@dataclass(frozen=True)
class PageMeasurements:
    """Measurements computed from a single PDF page."""

    scale: ScaleResult | None
    gross_area_sf: float | None
    building_perimeter_lf: float | None
    total_wall_length_lf: float | None
    wall_count: int
    confidence: MeasurementConfidence
    raw_data: DrawingData


class MeasurementService:
    """Combines vector extraction + scale detection + wall analysis.

    Produces real-world measurements (square feet, linear feet)
    from a single PDF page.
    """

    def __init__(
        self,
        extractor: VectorExtractor,
        scale_detector: ScaleDetector,
        wall_detector: WallDetector,
    ) -> None:
        self._extractor = extractor
        self._scale_detector = scale_detector
        self._wall_detector = wall_detector

    def measure(self, page: fitz.Page) -> PageMeasurements:
        """Run full measurement pipeline on a single page."""
        # Step 1: Extract vector data
        data = self._extractor.extract(page)

        if not data.paths:
            return PageMeasurements(
                scale=None,
                gross_area_sf=None,
                building_perimeter_lf=None,
                total_wall_length_lf=None,
                wall_count=0,
                confidence=MeasurementConfidence.NONE,
                raw_data=data,
            )

        # Step 2: Detect scale
        text_blocks = self._scale_detector.extract_text_blocks(page)
        page_text = "\n".join(tb.text for tb in text_blocks)
        scale = self._scale_detector.detect_from_text(page_text)

        if scale is None:
            scale = self._scale_detector.detect_from_dimensions(
                data.paths, text_blocks
            )

        # Step 3: Detect walls
        wall_analysis = self._wall_detector.detect(data)

        # Step 4: Compute measurements
        if scale is None:
            # Fallback: estimate scale from page size
            scale = self._estimate_scale_from_page(data)
            confidence = MeasurementConfidence.LOW
        elif wall_analysis.outer_boundary is not None:
            confidence = MeasurementConfidence.HIGH
        else:
            confidence = MeasurementConfidence.MEDIUM

        # Compute area
        gross_area_sf: float | None = None
        if wall_analysis.segments:
            area_pts = self._wall_detector.compute_enclosed_area_pts(
                wall_analysis.segments
            )
            if area_pts is not None and scale is not None:
                gross_area_sf = pts_to_real_sf(area_pts, scale)

        # Compute perimeter
        perimeter_lf: float | None = None
        if wall_analysis.outer_boundary and scale is not None:
            perimeter_pts = self._compute_perimeter_pts(
                wall_analysis.outer_boundary
            )
            if perimeter_pts > 0:
                perimeter_lf = pts_to_real_lf(perimeter_pts, scale)

        # Compute total wall length
        total_wall_lf: float | None = None
        if wall_analysis.total_wall_length_pts > 0 and scale is not None:
            total_wall_lf = pts_to_real_lf(
                wall_analysis.total_wall_length_pts, scale
            )

        return PageMeasurements(
            scale=scale,
            gross_area_sf=gross_area_sf,
            building_perimeter_lf=perimeter_lf,
            total_wall_length_lf=total_wall_lf,
            wall_count=len(wall_analysis.segments),
            confidence=confidence,
            raw_data=data,
        )

    @staticmethod
    def _estimate_scale_from_page(data: DrawingData) -> ScaleResult:
        """Rough scale estimate assuming standard architectural sheet.

        Assumes the drawing fits an ARCH D sheet (36x24 inches)
        representing roughly 100'x66' at 1/4"=1'-0" scale.
        Uses 1/8"=1'-0" (factor 96) as a conservative default.
        """
        return ScaleResult(
            drawing_units=0.125,
            real_units=12.0,
            scale_factor=96.0,
            notation="estimated (1/8\"=1'-0\")",
            confidence=Confidence.MEDIUM,
        )

    @staticmethod
    def _compute_perimeter_pts(
        boundary: list[Point2D],
    ) -> float:
        """Compute perimeter of a boundary polygon in PDF points."""
        import math

        if len(boundary) < 2:
            return 0.0

        perimeter = 0.0
        for i in range(len(boundary)):
            p1 = boundary[i]
            p2 = boundary[(i + 1) % len(boundary)]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            perimeter += math.sqrt(dx * dx + dy * dy)
        return perimeter
