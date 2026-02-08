"""Analysis pipeline — orchestrates PDF processing, VLM analysis, and cost estimation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cantena.exceptions import (
    CostEstimationError,
    PdfProcessingError,
    VlmAnalysisError,
)
from cantena.geometry.measurement import MeasurementConfidence
from cantena.services.vlm_analyzer import AnalysisContext

if TYPE_CHECKING:
    from pathlib import Path

    from cantena.engine import CostEngine
    from cantena.geometry.measurement import PageMeasurements
    from cantena.models.estimate import CostEstimate, SpaceCost
    from cantena.models.space_program import SpaceProgram
    from cantena.services.hybrid_analyzer import (
        HybridAnalysisResult,
        HybridAnalyzer,
        MergeDecision,
    )
    from cantena.services.pdf_processor import (
        PageResult,
        PdfProcessingResult,
        PdfProcessor,
    )
    from cantena.services.space_assembler import SpaceAssembler
    from cantena.services.vlm_analyzer import VlmAnalysisResult, VlmAnalyzer

logger = logging.getLogger(__name__)

_VECTOR_PATH_THRESHOLD = 50


@dataclass(frozen=True)
class PipelineResult:
    """Result of the full analysis pipeline."""

    estimate: CostEstimate
    analysis: VlmAnalysisResult
    processing_time_seconds: float
    pages_analyzed: int
    geometry_available: bool = False
    measurement_confidence: MeasurementConfidence = (
        MeasurementConfidence.NONE
    )
    merge_decisions: list[MergeDecision] | None = field(
        default=None
    )
    space_program: SpaceProgram | None = None
    space_breakdown: list[SpaceCost] | None = None
    room_detection_method: str | None = None


class AnalysisPipeline:
    """Orchestrates PDF → VLM → CostEngine in a single call."""

    def __init__(
        self,
        pdf_processor: PdfProcessor,
        vlm_analyzer: VlmAnalyzer,
        cost_engine: CostEngine,
        hybrid_analyzer: HybridAnalyzer | None = None,
        space_assembler: SpaceAssembler | None = None,
    ) -> None:
        self._pdf_processor = pdf_processor
        self._vlm_analyzer = vlm_analyzer
        self._cost_engine = cost_engine
        self._hybrid_analyzer = hybrid_analyzer
        self._space_assembler = space_assembler

    def analyze(
        self,
        pdf_path: Path,
        project_name: str,
        location: str,
    ) -> PipelineResult:
        """Run the full analysis pipeline on a PDF.

        Steps:
            1. Process PDF into page images
            2. Select the best page for analysis
            3. Extract vector data; if rich geometry and HybridAnalyzer
               configured, use hybrid analysis, else VLM-only
            4. Run cost engine on the resulting BuildingModel
            5. Clean up temporary image files

        Raises
        ------
        PdfProcessingError
            If PDF processing fails.
        VlmAnalysisError
            If VLM analysis fails.
        CostEstimationError
            If cost estimation fails.
        """
        start = time.monotonic()
        pdf_result: PdfProcessingResult | None = None

        try:
            # 1. Process PDF
            try:
                pdf_result = self._pdf_processor.process(pdf_path)
            except Exception as exc:
                msg = f"Failed to process PDF: {exc}"
                raise PdfProcessingError(msg) from exc

            if pdf_result.page_count == 0:
                msg = "PDF has no pages to analyze"
                raise PdfProcessingError(msg)

            # 2. Select best page
            best_page = self._select_best_page(pdf_result)

            # 3. Decide: hybrid or VLM-only
            context = AnalysisContext(
                project_name=project_name,
                location=location,
            )

            geometry_available = False
            measurement_confidence = MeasurementConfidence.NONE
            merge_decisions: list[MergeDecision] | None = None
            hybrid_result: HybridAnalysisResult | None = None

            use_hybrid = False
            if self._hybrid_analyzer is not None:
                path_count = self._count_vector_paths(
                    pdf_path, best_page.page_number
                )
                if path_count > _VECTOR_PATH_THRESHOLD:
                    use_hybrid = True

            if use_hybrid:
                assert self._hybrid_analyzer is not None
                try:
                    hybrid_result = (
                        self._run_hybrid_analysis(
                            pdf_path,
                            best_page,
                            context,
                        )
                    )
                except Exception as exc:
                    if isinstance(exc, VlmAnalysisError):
                        raise
                    msg = f"VLM analysis failed: {exc}"
                    raise VlmAnalysisError(msg) from exc

                analysis = hybrid_result.vlm_result
                building_model = hybrid_result.building_model
                geometry_available = True
                measurement_confidence = (
                    hybrid_result.geometry_measurements.confidence
                )
                merge_decisions = list(
                    hybrid_result.merge_decisions
                )
            else:
                try:
                    analysis = self._vlm_analyzer.analyze(
                        image_path=best_page.image_path,
                        context=context,
                    )
                except Exception as exc:
                    if isinstance(exc, VlmAnalysisError):
                        raise
                    msg = f"VLM analysis failed: {exc}"
                    raise VlmAnalysisError(msg) from exc
                building_model = analysis.building_model

            # 4. Assemble SpaceProgram (enhanced flow)
            space_program: SpaceProgram | None = None
            room_detection_method: str | None = None
            geometry_measurements = (
                hybrid_result.geometry_measurements
                if hybrid_result is not None
                else None
            )

            if (
                self._space_assembler is not None
                and geometry_measurements is not None
            ):
                try:
                    space_program = self._space_assembler.assemble(
                        geometry_measurements, building_model
                    )
                    # Reconcile area gap
                    space_program = (
                        self._space_assembler.reconcile_areas(
                            space_program, building_model.gross_sf
                        )
                    )
                    # Determine detection method
                    room_detection_method = (
                        self._determine_room_detection_method(
                            geometry_measurements, space_program
                        )
                    )
                except Exception:
                    logger.warning(
                        "SpaceAssembler failed; "
                        "falling back to whole-building estimate",
                        exc_info=True,
                    )
                    space_program = None
                    room_detection_method = None

            # 5. Cost estimation
            try:
                estimate = self._cost_engine.estimate(
                    building=building_model,
                    project_name=project_name,
                    space_program=space_program,
                )
            except Exception as exc:
                if isinstance(exc, CostEstimationError):
                    raise
                msg = f"Cost estimation failed: {exc}"
                raise CostEstimationError(msg) from exc

            # If no assembler but VLM-only, set room_detection_method
            if (
                space_program is None
                and room_detection_method is None
                and not geometry_available
            ):
                room_detection_method = "assumed"

            elapsed = time.monotonic() - start

            return PipelineResult(
                estimate=estimate,
                analysis=analysis,
                processing_time_seconds=round(elapsed, 2),
                pages_analyzed=1,
                geometry_available=geometry_available,
                measurement_confidence=measurement_confidence,
                merge_decisions=merge_decisions,
                space_program=space_program,
                space_breakdown=estimate.space_breakdown,
                room_detection_method=room_detection_method,
            )

        finally:
            # 5. Always clean up temp files
            if pdf_result is not None:
                self._pdf_processor.cleanup(pdf_result)

    def _run_hybrid_analysis(
        self,
        pdf_path: Path,
        best_page: PageResult,
        context: AnalysisContext,
    ) -> HybridAnalysisResult:
        """Run HybridAnalyzer on a PDF page."""
        import fitz as fitz_lib  # type: ignore[import-untyped]

        assert self._hybrid_analyzer is not None
        doc = fitz_lib.open(pdf_path)
        try:
            page = doc[best_page.page_number - 1]
            result: HybridAnalysisResult = (
                self._hybrid_analyzer.analyze(
                    page=page,
                    image_path=best_page.image_path,
                    context=context,
                )
            )
        finally:
            doc.close()
        return result

    @staticmethod
    def _count_vector_paths(
        pdf_path: Path, page_number: int
    ) -> int:
        """Count vector paths on a specific PDF page."""
        import fitz as fitz_lib  # noqa: F811

        from cantena.geometry.extractor import VectorExtractor

        doc = fitz_lib.open(pdf_path)
        try:
            page = doc[page_number - 1]
            extractor = VectorExtractor()
            data = extractor.extract(page)
            return len(data.paths)
        finally:
            doc.close()

    @staticmethod
    def _determine_room_detection_method(
        measurements: PageMeasurements,
        program: SpaceProgram,
    ) -> str:
        """Determine how rooms were detected for this estimate."""
        from cantena.models.space_program import SpaceSource

        has_geometry = any(
            s.source == SpaceSource.GEOMETRY for s in program.spaces
        )
        has_llm = any(
            s.source == SpaceSource.LLM for s in program.spaces
        )

        if has_geometry:
            return "polygonize"
        if has_llm:
            return "llm_only"
        return "assumed"

    @staticmethod
    def _select_best_page(
        pdf_result: PdfProcessingResult,
    ) -> PageResult:
        """Select the best page for VLM analysis.

        Heuristic (MVP):
        - Prefer page with 'floor plan' in title block text
        - Otherwise, pick the largest page (by pixel area)
        - Fallback to page 1
        """
        pages = pdf_result.pages

        # Check title blocks for "floor plan"
        for page in pages:
            if (
                page.title_block_text
                and "floor plan" in page.title_block_text.lower()
            ):
                logger.info(
                    "Selected page %d (title block match: 'floor plan')",
                    page.page_number,
                )
                return page

        # Pick largest page by pixel area
        best = max(pages, key=lambda p: p.width_px * p.height_px)
        logger.info(
            "Selected page %d (largest: %dx%d)",
            best.page_number,
            best.width_px,
            best.height_px,
        )
        return best
