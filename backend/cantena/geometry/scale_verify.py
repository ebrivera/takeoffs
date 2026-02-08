"""Scale verification safety rail via LLM.

Verifies (and optionally recovers) the detected scale factor using an LLM
that reads title-block text and candidate scale strings.  This prevents a
brittle title-block parse or unreliable dimension inference from silently
producing massively wrong areas (scale^2 error).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import anthropic
from anthropic.types import TextBlockParam

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

from cantena.geometry.scale import ScaleResult, TextBlock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

VerificationSource = Literal[
    "DETERMINISTIC",
    "LLM_CONFIRMED",
    "LLM_RECOVERED",
    "UNVERIFIED",
]


@dataclass(frozen=True)
class ScaleVerificationResult:
    """Result of scale verification."""

    scale: ScaleResult | None
    verification_source: VerificationSource
    warnings: list[str] = field(default_factory=list)
    llm_raw_notation: str | None = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert at reading architectural drawing title blocks. "
    "You will receive text extracted from the title-block region of an "
    "architectural floor plan, along with any candidate scale strings "
    "that were detected by a deterministic parser.\n\n"
    "Your task is to identify the drawing scale notation and compute "
    "the scale factor.\n\n"
    "Output ONLY a JSON object matching this schema exactly:\n\n"
    "```json\n"
    "{\n"
    '  "notation": "<scale notation as written, e.g. 1/4\\"=1\'-0\\">",\n'
    '  "paper_inches": <float, drawing inches>,\n'
    '  "real_inches": <float, real-world inches>,\n'
    '  "scale_factor": <float, real_inches / paper_inches>,\n'
    '  "confidence": "<HIGH|MEDIUM|LOW>"\n'
    "}\n"
    "```\n\n"
    "IMPORTANT:\n"
    "- Output ONLY the JSON block wrapped in ```json ... ``` fences.\n"
    "- Do not include reasoning text before or after the JSON.\n"
    "- If you cannot determine the scale, use confidence LOW "
    "and scale_factor 0.\n"
)


# ---------------------------------------------------------------------------
# ScaleVerifier
# ---------------------------------------------------------------------------


class ScaleVerifier:
    """Verifies or recovers drawing scale via LLM safety rail."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        timeout: float = 30.0,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )
        self._model = model

    def verify_or_recover_scale(
        self,
        page: fitz.Page,
        detected: ScaleResult | None,
        text_blocks: list[TextBlock],
    ) -> ScaleVerificationResult:
        """Verify detected scale or recover it via LLM.

        Decision logic
        --------------
        1. HIGH detected + LLM agrees ±5%  -> LLM_CONFIRMED
        2. LOW/MEDIUM/None detected + LLM HIGH/MEDIUM -> LLM_RECOVERED
        3. LLM disagrees >10% -> keep detected with warning
        4. LLM fails/timeouts/429 -> UNVERIFIED with best deterministic
        """
        try:
            llm_result = self._ask_llm(page, detected, text_blocks)
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.APIStatusError,
        ):
            logger.warning("LLM scale verification API error")
            return ScaleVerificationResult(
                scale=detected,
                verification_source="UNVERIFIED",
                warnings=["LLM API call failed; using best deterministic scale"],
            )
        except Exception:
            logger.exception("Unexpected error during LLM scale verification")
            return ScaleVerificationResult(
                scale=detected,
                verification_source="UNVERIFIED",
                warnings=["LLM verification failed unexpectedly"],
            )

        if llm_result is None:
            return ScaleVerificationResult(
                scale=detected,
                verification_source="UNVERIFIED",
                warnings=["LLM returned unparseable response"],
            )

        llm_factor = llm_result.get("scale_factor", 0.0)
        llm_confidence = str(llm_result.get("confidence", "LOW")).upper()
        llm_notation = str(llm_result.get("notation", ""))

        # LLM returned LOW confidence or zero factor — can't help
        if llm_confidence == "LOW" or llm_factor <= 0:
            return ScaleVerificationResult(
                scale=detected,
                verification_source="UNVERIFIED",
                warnings=["LLM confidence too low to verify or recover"],
                llm_raw_notation=llm_notation or None,
            )

        # No deterministic scale — LLM recovery
        if detected is None:
            return self._recover_from_llm(llm_result, llm_notation)

        # Compare LLM vs deterministic
        return self._compare_scales(detected, llm_result, llm_notation)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ask_llm(
        self,
        page: fitz.Page,
        detected: ScaleResult | None,
        text_blocks: list[TextBlock],
    ) -> dict[str, Any] | None:
        """Send title-block text to LLM and parse JSON response."""
        user_text = _build_user_text(page, detected, text_blocks)
        content: list[TextBlockParam] = [
            TextBlockParam(type="text", text=user_text),
        ]

        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        raw = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        return _parse_llm_json(raw)

    @staticmethod
    def _recover_from_llm(
        llm_result: dict[str, Any],
        llm_notation: str,
    ) -> ScaleVerificationResult:
        """Build a recovered ScaleResult from LLM output."""
        from cantena.geometry.scale import Confidence

        paper = float(llm_result.get("paper_inches", 0.0))
        real = float(llm_result.get("real_inches", 0.0))
        factor = float(llm_result.get("scale_factor", 0.0))

        if factor <= 0:
            return ScaleVerificationResult(
                scale=None,
                verification_source="UNVERIFIED",
                warnings=["LLM recovery produced invalid scale factor"],
                llm_raw_notation=llm_notation or None,
            )

        recovered = ScaleResult(
            drawing_units=paper if paper > 0 else 1.0,
            real_units=real if real > 0 else factor,
            scale_factor=factor,
            notation=llm_notation or "LLM-recovered",
            confidence=Confidence.MEDIUM,
        )
        return ScaleVerificationResult(
            scale=recovered,
            verification_source="LLM_RECOVERED",
            llm_raw_notation=llm_notation or None,
        )

    @staticmethod
    def _compare_scales(
        detected: ScaleResult,
        llm_result: dict[str, Any],
        llm_notation: str,
    ) -> ScaleVerificationResult:
        """Compare deterministic and LLM scale factors."""
        llm_factor = float(llm_result.get("scale_factor", 0.0))
        det_factor = detected.scale_factor

        if det_factor <= 0:
            # Defensive: shouldn't happen but handle gracefully
            return ScaleVerificationResult(
                scale=detected,
                verification_source="UNVERIFIED",
                warnings=["Detected scale factor is zero"],
                llm_raw_notation=llm_notation or None,
            )

        ratio = abs(llm_factor - det_factor) / det_factor

        if ratio <= 0.05:
            # Agreement within 5% -> confirmed
            return ScaleVerificationResult(
                scale=detected,
                verification_source="LLM_CONFIRMED",
                llm_raw_notation=llm_notation or None,
            )

        if ratio <= 0.10:
            # Close but not exact — still confirmed with note
            return ScaleVerificationResult(
                scale=detected,
                verification_source="LLM_CONFIRMED",
                warnings=[
                    f"LLM scale ({llm_factor:.1f}) differs "
                    f"from detected ({det_factor:.1f}) by {ratio:.0%}"
                ],
                llm_raw_notation=llm_notation or None,
            )

        # Disagree >10% -> keep detected with warning
        return ScaleVerificationResult(
            scale=detected,
            verification_source="DETERMINISTIC",
            warnings=[
                f"LLM scale ({llm_factor:.1f}) disagrees with "
                f"detected ({det_factor:.1f}) by {ratio:.0%}; "
                "keeping detected scale"
            ],
            llm_raw_notation=llm_notation or None,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_user_text(
    page: fitz.Page,
    detected: ScaleResult | None,
    text_blocks: list[TextBlock],
) -> str:
    """Build user message text with title-block info."""
    lines: list[str] = []

    # Title-block region text (bottom 20% of page)
    page_height = float(page.rect.height)
    title_block_y = page_height * 0.80
    tb_texts = [
        tb.text.strip()
        for tb in text_blocks
        if tb.position.y >= title_block_y and tb.text.strip()
    ]

    lines.append("## Title Block Region Text\n")
    if tb_texts:
        for t in tb_texts:
            lines.append(f"- {t}")
    else:
        lines.append("(no text found in title block region)")

    # Candidate scale strings (any text containing "scale" or common patterns)
    scale_candidates = _find_scale_candidates(text_blocks)
    if scale_candidates:
        lines.append("\n## Candidate Scale Strings\n")
        for c in scale_candidates:
            lines.append(f"- {c}")

    # Current detected scale
    lines.append("\n## Detected Scale (deterministic parser)\n")
    if detected is not None:
        lines.append(f"- Notation: {detected.notation}")
        lines.append(f"- Scale factor: {detected.scale_factor}")
        lines.append(f"- Paper inches: {detected.drawing_units}")
        lines.append(f"- Real inches: {detected.real_units}")
        lines.append(f"- Confidence: {detected.confidence.value}")
    else:
        lines.append("- No scale detected by deterministic parser")

    return "\n".join(lines)


def _find_scale_candidates(text_blocks: list[TextBlock]) -> list[str]:
    """Find text blocks that might contain scale information."""
    import re

    candidates: list[str] = []
    scale_pattern = re.compile(
        r"(?:scale|1/\d+|1:\d+|\d+/\d+\s*[\"'=])", re.IGNORECASE
    )
    for tb in text_blocks:
        text = tb.text.strip()
        if text and scale_pattern.search(text):
            candidates.append(text)
    return candidates


def _extract_json(text: str) -> str | None:
    """Extract JSON from ```json ... ``` code fences."""
    start = text.find("```json")
    if start == -1:
        start = text.find("```")
        if start == -1:
            return None
        start += 3
    else:
        start += 7

    end = text.find("```", start)
    if end == -1:
        return None

    return text[start:end].strip()


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Parse LLM response JSON."""
    json_str = _extract_json(raw)
    if json_str is None:
        logger.warning("No JSON block found in LLM scale verification response")
        return None

    try:
        data: dict[str, Any] = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in LLM scale verification response")
        return None

    return data
