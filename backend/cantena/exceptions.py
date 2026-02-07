"""Custom exception hierarchy for the Cantena pipeline."""

from __future__ import annotations


class CantenaError(Exception):
    """Base exception for all Cantena errors."""


class PdfProcessingError(CantenaError):
    """Raised when PDF processing fails."""


class VlmAnalysisError(CantenaError):
    """Raised when VLM analysis fails."""


class CostEstimationError(CantenaError):
    """Raised when cost estimation fails."""
