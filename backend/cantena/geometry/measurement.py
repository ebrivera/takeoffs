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
    from cantena.geometry.rooms import DetectedRoom, RoomAnalysis
    from cantena.geometry.scale import TextBlock
    from cantena.geometry.scale_verify import (
        ScaleVerificationResult,
        ScaleVerifier,
    )
    from cantena.geometry.walls import WallDetector, WallSegment
    from cantena.services.llm_geometry_interpreter import (
        LlmGeometryInterpreter,
        LlmInterpretation,
    )

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
    rooms: list[DetectedRoom] | None = None
    room_count: int = 0
    polygonize_success: bool = False
    llm_interpretation: LlmInterpretation | None = None
    scale_verification: ScaleVerificationResult | None = None
    wall_segments: list[WallSegment] | None = None
    outer_boundary_polygon: list[tuple[float, float]] | None = None


class MeasurementService:
    """Combines vector extraction + scale detection + wall analysis.

    Produces real-world measurements (square feet, linear feet)
    from a single PDF page.  Optionally uses RoomDetector for
    polygonize-based area computation and LLM enrichment.
    """

    def __init__(
        self,
        extractor: VectorExtractor,
        scale_detector: ScaleDetector,
        wall_detector: WallDetector,
        llm_interpreter: LlmGeometryInterpreter | None = None,
        scale_verifier: ScaleVerifier | None = None,
    ) -> None:
        self._extractor = extractor
        self._scale_detector = scale_detector
        self._wall_detector = wall_detector
        self._llm_interpreter = llm_interpreter
        self._scale_verifier = scale_verifier

    def measure(self, page: fitz.Page) -> PageMeasurements:
        """Run full measurement pipeline on a single page."""
        from cantena.geometry.rooms import RoomDetector

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

        # Step 2b: Optionally verify/recover scale via LLM
        scale_verification: ScaleVerificationResult | None = None
        if self._scale_verifier is not None:
            scale_verification = self._scale_verifier.verify_or_recover_scale(
                page, scale, text_blocks
            )
            if scale_verification.scale is not None:
                scale = scale_verification.scale

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

        # Step 5: Detect rooms via polygonize
        room_analysis: RoomAnalysis | None = None
        room_detector = RoomDetector()
        if wall_analysis.segments:
            page_area_pts = data.page_width_pts * data.page_height_pts
            room_analysis = room_detector.detect_rooms(
                wall_analysis.segments,
                scale_factor=scale.scale_factor if scale else None,
                page_area_pts=page_area_pts if page_area_pts > 0 else None,
            )
            # Label rooms from text blocks
            if room_analysis.rooms and text_blocks:
                room_analysis = room_detector.label_rooms(
                    room_analysis, text_blocks
                )

        # Step 6: Compute area (priority: rooms > convex hull > page estimate)
        gross_area_sf: float | None = None
        polygonize_success = False
        if (
            room_analysis is not None
            and room_analysis.polygonize_success
            and room_analysis.total_area_sf is not None
        ):
            # Priority 1: sum of polygonized room areas (HIGH)
            gross_area_sf = room_analysis.total_area_sf
            polygonize_success = True
            if confidence == MeasurementConfidence.MEDIUM:
                confidence = MeasurementConfidence.HIGH
        elif wall_analysis.segments:
            # Priority 2: convex hull area (MEDIUM)
            area_pts = self._wall_detector.compute_enclosed_area_pts(
                wall_analysis.segments
            )
            if area_pts is not None and scale is not None:
                gross_area_sf = pts_to_real_sf(area_pts, scale)

        # Boost confidence if scale was verified/confirmed
        if (
            scale_verification is not None
            and scale_verification.verification_source
            in ("LLM_CONFIRMED", "LLM_RECOVERED")
            and confidence == MeasurementConfidence.MEDIUM
        ):
            confidence = MeasurementConfidence.HIGH

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

        # Step 7: Optionally run LLM enrichment
        llm_interpretation: LlmInterpretation | None = None
        if self._llm_interpreter is not None and room_analysis is not None:
            llm_interpretation = self._run_llm_enrichment(
                scale, room_analysis, text_blocks
            )

        return PageMeasurements(
            scale=scale,
            gross_area_sf=gross_area_sf,
            building_perimeter_lf=perimeter_lf,
            total_wall_length_lf=total_wall_lf,
            wall_count=len(wall_analysis.segments),
            confidence=confidence,
            raw_data=data,
            rooms=room_analysis.rooms if room_analysis else None,
            room_count=room_analysis.room_count if room_analysis else 0,
            polygonize_success=polygonize_success,
            llm_interpretation=llm_interpretation,
            scale_verification=scale_verification,
            wall_segments=wall_analysis.segments or None,
            outer_boundary_polygon=(
                room_analysis.outer_boundary_polygon
                if room_analysis else None
            ),
        )

    def _run_llm_enrichment(
        self,
        scale: ScaleResult | None,
        room_analysis: RoomAnalysis,
        text_blocks: list[TextBlock],
    ) -> LlmInterpretation | None:
        """Run LLM geometry interpretation if interpreter is available."""
        from cantena.services.llm_geometry_interpreter import (
            GeometrySummary,
            RoomSummary,
        )

        if self._llm_interpreter is None:
            return None

        room_summaries = [
            RoomSummary(
                room_index=r.room_index,
                label=r.label,
                area_sf=r.area_sf,
                perimeter_lf=r.perimeter_lf,
            )
            for r in room_analysis.rooms
        ]

        summary = GeometrySummary(
            scale_notation=scale.notation if scale else None,
            scale_factor=scale.scale_factor if scale else None,
            total_area_sf=room_analysis.total_area_sf,
            rooms=room_summaries,
            all_text_blocks=[tb.text for tb in text_blocks],
            wall_count=0,
            measurement_confidence="HIGH",
        )

        return self._llm_interpreter.interpret(summary)

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
