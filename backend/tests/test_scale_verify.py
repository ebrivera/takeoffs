"""Unit tests for scale verification safety rail (US-378)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from cantena.geometry.extractor import BoundingRect, Point2D
from cantena.geometry.scale import Confidence, ScaleResult, TextBlock
from cantena.geometry.scale_verify import (
    ScaleVerificationResult,
    ScaleVerifier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scale(
    factor: float = 48.0,
    notation: str = '1/4"=1\'-0"',
    confidence: Confidence = Confidence.HIGH,
) -> ScaleResult:
    """Build a ScaleResult for testing."""
    return ScaleResult(
        drawing_units=0.25,
        real_units=12.0,
        scale_factor=factor,
        notation=notation,
        confidence=confidence,
    )


def _make_text_block(
    text: str,
    x: float = 100.0,
    y: float = 700.0,
) -> TextBlock:
    """Build a TextBlock for testing."""
    return TextBlock(
        text=text,
        position=Point2D(x, y),
        bounding_rect=BoundingRect(x=x - 20, y=y - 5, width=40, height=10),
    )


def _mock_page() -> MagicMock:
    """Create a mock fitz.Page."""
    page = MagicMock()
    page.rect.height = 800.0
    page.rect.width = 1200.0
    return page


def _make_llm_response(
    notation: str = '1/4"=1\'-0"',
    paper_inches: float = 0.25,
    real_inches: float = 12.0,
    scale_factor: float = 48.0,
    confidence: str = "HIGH",
) -> str:
    """Build a mock LLM response string."""
    import json

    data = {
        "notation": notation,
        "paper_inches": paper_inches,
        "real_inches": real_inches,
        "scale_factor": scale_factor,
        "confidence": confidence,
    }
    return f"```json\n{json.dumps(data)}\n```"


def _mock_api_response(text: str) -> MagicMock:
    """Build a mock Anthropic API response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Tests: deterministic HIGH + LLM agrees -> confirmed
# ---------------------------------------------------------------------------


class TestDeterministicHighLlmAgrees:
    """Deterministic HIGH + LLM agrees within 5% -> LLM_CONFIRMED."""

    def test_exact_match(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE: 1/4"=1\'-0"', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=48.0)
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "LLM_CONFIRMED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0
        assert result.warnings == []

    def test_within_five_percent(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE: 1/4"=1\'-0"', y=750.0)]

        # 49.0 is ~2% off from 48.0 -> within 5%
        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=49.0)
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "LLM_CONFIRMED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0  # keeps detected

    def test_between_five_and_ten_percent_still_confirmed(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        # 52.0 is ~8.3% off from 48.0 -> within 10%, confirmed with warning
        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=52.0)
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "LLM_CONFIRMED"
        assert len(result.warnings) == 1
        assert "differs" in result.warnings[0]


# ---------------------------------------------------------------------------
# Tests: deterministic None + LLM recovers -> recovered
# ---------------------------------------------------------------------------


class TestDeterministicNoneLlmRecovers:
    """Deterministic None + LLM HIGH/MEDIUM -> LLM_RECOVERED."""

    def test_llm_recovers_missing_scale(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        text_blocks = [_make_text_block('SCALE: 1/4"=1\'-0"', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(
                    notation='1/4"=1\'-0"',
                    paper_inches=0.25,
                    real_inches=12.0,
                    scale_factor=48.0,
                    confidence="HIGH",
                )
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, None, text_blocks
            )

        assert result.verification_source == "LLM_RECOVERED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0
        assert result.llm_raw_notation == '1/4"=1\'-0"'

    def test_llm_recovers_with_medium_confidence(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        text_blocks = [_make_text_block('1/4" = 1\'', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(
                    scale_factor=48.0,
                    confidence="MEDIUM",
                )
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, None, text_blocks
            )

        assert result.verification_source == "LLM_RECOVERED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0


# ---------------------------------------------------------------------------
# Tests: disagreement emits warning
# ---------------------------------------------------------------------------


class TestDisagreement:
    """LLM disagrees >10% -> keep detected with warning."""

    def test_disagreement_keeps_detected(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        # 96.0 is 100% off from 48.0 -> major disagreement
        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=96.0)
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "DETERMINISTIC"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0  # keeps detected
        assert len(result.warnings) == 1
        assert "disagrees" in result.warnings[0]

    def test_slight_disagreement_over_ten_percent(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        # 54.0 is 12.5% off -> over 10%
        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=54.0)
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "DETERMINISTIC"
        assert len(result.warnings) >= 1


# ---------------------------------------------------------------------------
# Tests: timeout/429 returns UNVERIFIED
# ---------------------------------------------------------------------------


class TestTimeoutAndErrors:
    """Timeout / 429 / connection error -> UNVERIFIED."""

    def test_timeout_returns_unverified(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            side_effect=anthropic.APITimeoutError(request=MagicMock()),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0
        assert len(result.warnings) >= 1

    def test_rate_limit_returns_unverified(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0

    def test_connection_error_returns_unverified(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            side_effect=anthropic.APIConnectionError(request=MagicMock()),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None

    def test_no_api_key_returns_unverified(self) -> None:
        """If API key is missing, verifier should still return UNVERIFIED."""
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks: list[TextBlock] = []

        with patch.object(
            verifier._client.messages,
            "create",
            side_effect=anthropic.AuthenticationError(
                message="invalid key",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0


# ---------------------------------------------------------------------------
# Tests: LLM low confidence
# ---------------------------------------------------------------------------


class TestLlmLowConfidence:
    """LLM returns LOW confidence -> UNVERIFIED."""

    def test_low_confidence_with_detected(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=48.0, confidence="LOW")
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0

    def test_low_confidence_without_detected(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response(
                _make_llm_response(scale_factor=0.0, confidence="LOW")
            ),
        ):
            result = verifier.verify_or_recover_scale(
                page, None, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is None


# ---------------------------------------------------------------------------
# Tests: malformed LLM response
# ---------------------------------------------------------------------------


class TestMalformedResponse:
    """Malformed or empty LLM response -> UNVERIFIED."""

    def test_no_json_in_response(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response("I cannot determine the scale."),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None
        assert result.scale.scale_factor == 48.0

    def test_invalid_json(self) -> None:
        verifier = ScaleVerifier(api_key="test-key")
        page = _mock_page()
        detected = _make_scale(factor=48.0)
        text_blocks = [_make_text_block('SCALE', y=750.0)]

        with patch.object(
            verifier._client.messages,
            "create",
            return_value=_mock_api_response("```json\n{broken json}\n```"),
        ):
            result = verifier.verify_or_recover_scale(
                page, detected, text_blocks
            )

        assert result.verification_source == "UNVERIFIED"
        assert result.scale is not None


# ---------------------------------------------------------------------------
# Tests: ScaleVerificationResult model
# ---------------------------------------------------------------------------


class TestScaleVerificationResultModel:
    """Verify the ScaleVerificationResult model behaves correctly."""

    def test_default_fields(self) -> None:
        result = ScaleVerificationResult(
            scale=None,
            verification_source="UNVERIFIED",
        )
        assert result.warnings == []
        assert result.llm_raw_notation is None

    def test_with_all_fields(self) -> None:
        scale = _make_scale()
        result = ScaleVerificationResult(
            scale=scale,
            verification_source="LLM_CONFIRMED",
            warnings=["test warning"],
            llm_raw_notation='1/4"=1\'-0"',
        )
        assert result.scale is not None
        assert result.verification_source == "LLM_CONFIRMED"
        assert len(result.warnings) == 1
        assert result.llm_raw_notation is not None

    def test_frozen(self) -> None:
        result = ScaleVerificationResult(
            scale=None,
            verification_source="UNVERIFIED",
        )
        with pytest.raises(AttributeError):
            result.verification_source = "LLM_CONFIRMED"  # type: ignore[misc]
