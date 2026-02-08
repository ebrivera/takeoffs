"""Integration test: LLM-assisted scale verification on first-floor.pdf.

Requires ANTHROPIC_API_KEY to be set.  Skipped otherwise.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from cantena.geometry.scale import ScaleDetector
from cantena.geometry.scale_verify import ScaleVerifier

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

pytestmark = pytest.mark.llm


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


class TestScaleVerificationLlm:
    """Real API integration test for scale verification on first-floor.pdf."""

    def test_llm_verifier_returns_expected_scale(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """LLM-verifier returns ~48.0 (±2) for first-floor.pdf."""
        api_key = _get_api_key()
        verifier = ScaleVerifier(api_key=api_key)
        detector = ScaleDetector()

        text_blocks = detector.extract_text_blocks(first_floor_page)
        page_text = "\n".join(tb.text for tb in text_blocks)
        detected = detector.detect_from_text(page_text)

        try:
            result = verifier.verify_or_recover_scale(
                first_floor_page, detected, text_blocks
            )
        except Exception as exc:
            if "429" in str(exc):
                pytest.skip("Rate limited")
            raise

        assert result.verification_source != "UNVERIFIED", (
            f"Expected verified result, got UNVERIFIED: {result.warnings}"
        )
        assert result.scale is not None
        assert abs(result.scale.scale_factor - 48.0) <= 2.0, (
            f"Expected ~48.0, got {result.scale.scale_factor}"
        )
