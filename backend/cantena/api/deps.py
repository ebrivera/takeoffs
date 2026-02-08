"""Dependency injection for FastAPI endpoints."""

from __future__ import annotations

import logging
import os

from cantena.factory import create_default_engine
from cantena.services.pdf_processor import PdfProcessor
from cantena.services.pipeline import AnalysisPipeline
from cantena.services.space_assembler import SpaceAssembler
from cantena.services.vlm_analyzer import VlmAnalyzer

logger = logging.getLogger(__name__)


def create_pipeline() -> AnalysisPipeline:
    """Create an AnalysisPipeline with default configuration.

    Reads ANTHROPIC_API_KEY from environment. Raises ValueError
    if the key is not set.

    When geometry components are available, wires up HybridAnalyzer
    and SpaceAssembler for room-type-aware cost estimation.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        msg = (
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it to use the /api/analyze endpoint."
        )
        raise ValueError(msg)

    pdf_processor = PdfProcessor()
    vlm_analyzer = VlmAnalyzer(api_key=api_key)
    cost_engine = create_default_engine()

    # Wire up enhanced geometry pipeline
    from cantena.geometry.extractor import VectorExtractor
    from cantena.geometry.measurement import MeasurementService
    from cantena.geometry.scale import ScaleDetector
    from cantena.geometry.walls import WallDetector
    from cantena.services.hybrid_analyzer import HybridAnalyzer

    measurement_service = MeasurementService(
        extractor=VectorExtractor(),
        scale_detector=ScaleDetector(),
        wall_detector=WallDetector(),
    )
    hybrid_analyzer = HybridAnalyzer(
        measurement_service=measurement_service,
        vlm_analyzer=vlm_analyzer,
    )
    space_assembler = SpaceAssembler()

    return AnalysisPipeline(
        pdf_processor=pdf_processor,
        vlm_analyzer=vlm_analyzer,
        cost_engine=cost_engine,
        hybrid_analyzer=hybrid_analyzer,
        space_assembler=space_assembler,
    )
