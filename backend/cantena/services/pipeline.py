"""Analysis pipeline — orchestrates PDF processing, VLM analysis, and cost estimation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cantena.exceptions import (
    CostEstimationError,
    PdfProcessingError,
    VlmAnalysisError,
)
from cantena.services.vlm_analyzer import AnalysisContext

if TYPE_CHECKING:
    from pathlib import Path

    from cantena.engine import CostEngine
    from cantena.models.estimate import CostEstimate
    from cantena.services.pdf_processor import (
        PageResult,
        PdfProcessingResult,
        PdfProcessor,
    )
    from cantena.services.vlm_analyzer import VlmAnalysisResult, VlmAnalyzer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Result of the full analysis pipeline."""

    estimate: CostEstimate
    analysis: VlmAnalysisResult
    processing_time_seconds: float
    pages_analyzed: int


class AnalysisPipeline:
    """Orchestrates PDF → VLM → CostEngine in a single call."""

    def __init__(
        self,
        pdf_processor: PdfProcessor,
        vlm_analyzer: VlmAnalyzer,
        cost_engine: CostEngine,
    ) -> None:
        self._pdf_processor = pdf_processor
        self._vlm_analyzer = vlm_analyzer
        self._cost_engine = cost_engine

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
            3. Run VLM analysis on selected page
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

            # 3. VLM analysis
            context = AnalysisContext(
                project_name=project_name,
                location=location,
            )
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

            # 4. Cost estimation
            try:
                estimate = self._cost_engine.estimate(
                    building=analysis.building_model,
                    project_name=project_name,
                )
            except Exception as exc:
                if isinstance(exc, CostEstimationError):
                    raise
                msg = f"Cost estimation failed: {exc}"
                raise CostEstimationError(msg) from exc

            elapsed = time.monotonic() - start

            return PipelineResult(
                estimate=estimate,
                analysis=analysis,
                processing_time_seconds=round(elapsed, 2),
                pages_analyzed=1,
            )

        finally:
            # 5. Always clean up temp files
            if pdf_result is not None:
                self._pdf_processor.cleanup(pdf_result)

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
