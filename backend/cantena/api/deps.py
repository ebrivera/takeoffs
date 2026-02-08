"""Dependency injection for FastAPI endpoints."""

from __future__ import annotations

import os

from cantena.factory import create_default_engine
from cantena.services.pdf_processor import PdfProcessor
from cantena.services.pipeline import AnalysisPipeline
from cantena.services.vlm_analyzer import VlmAnalyzer


def create_pipeline() -> AnalysisPipeline:
    """Create an AnalysisPipeline with default configuration.

    Reads ANTHROPIC_API_KEY from environment. Raises ValueError
    if the key is not set.
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

    return AnalysisPipeline(
        pdf_processor=pdf_processor,
        vlm_analyzer=vlm_analyzer,
        cost_engine=cost_engine,
    )
