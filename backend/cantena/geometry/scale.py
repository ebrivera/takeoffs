"""Scale detection from title block text and dimension annotations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

    from cantena.geometry.extractor import VectorPath

from cantena.geometry.extractor import BoundingRect, Point2D


class Confidence(StrEnum):
    """Confidence level for scale detection."""

    HIGH = "high"
    MEDIUM = "medium"


@dataclass(frozen=True)
class ScaleResult:
    """Result of scale detection from a PDF page."""

    drawing_units: float  # inches on paper
    real_units: float  # inches in real world
    scale_factor: float  # real_units / drawing_units
    notation: str  # original parsed text
    confidence: Confidence


@dataclass(frozen=True)
class TextBlock:
    """A block of text extracted from a PDF page with position."""

    text: str
    position: Point2D  # center of text block
    bounding_rect: BoundingRect


# Common architectural scale fractions: numerator / denominator in inches
_FRACTION_MAP: dict[str, float] = {
    "1/8": 0.125,
    "1/4": 0.25,
    "3/16": 0.1875,
    "3/8": 0.375,
    "1/2": 0.5,
    "3/4": 0.75,
    "1": 1.0,
    "1 1/2": 1.5,
    "3": 3.0,
}

# Pattern: fractional inch = feet-inches, e.g. 1/8"=1'-0"
# Captures: (fraction)(optional ")(=)(feet)('-)(inches)(")?
_ARCH_SCALE_RE = re.compile(
    r"""
    (\d+(?:\s+\d+)?/\d+|\d+)       # fraction or whole number (group 1)
    \s*(?:["\u201d\u2033]|'')?      # optional inch mark
    \s*=\s*                         # equals sign
    (\d+)                           # feet (group 2)
    \s*['\u2019\u2032]              # foot mark
    \s*-?\s*                        # optional dash
    (\d+)                           # inches (group 3)
    \s*(?:["\u201d\u2033]|'')?      # optional inch mark
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern: metric-style scales like 1:100, 1:50
_METRIC_SCALE_RE = re.compile(
    r"""
    1\s*:\s*(\d+)                   # 1:N (group 1 = N)
    """,
    re.VERBOSE,
)

# Pattern: whole inch = feet, e.g. 1"=10'-0"
_WHOLE_INCH_SCALE_RE = re.compile(
    r"""
    (\d+)                           # whole inches (group 1)
    \s*(?:["\u201d\u2033]|'')       # inch mark (required to disambiguate)
    \s*=\s*                         # equals sign
    (\d+)                           # feet (group 2)
    \s*['\u2019\u2032]              # foot mark
    \s*-?\s*                        # optional dash
    (\d+)                           # inches (group 3)
    \s*(?:["\u201d\u2033]|'')?      # optional inch mark
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern for dimension strings: 24'-6", 24'6", 24.5', 10'-0"
_DIMENSION_RE = re.compile(
    r"""
    (\d+(?:\.\d+)?)                 # feet (group 1), may have decimal
    \s*['\u2019\u2032]              # foot mark
    \s*-?\s*                        # optional dash
    (\d+)?                          # optional inches (group 2)
    \s*(?:["\u201d\u2033]|'')?      # optional inch mark
    """,
    re.VERBOSE,
)


def parse_dimension_string(text: str) -> float | None:
    """Parse an architectural dimension string into inches.

    Supports: 24'-6" -> 294, 24'6" -> 294, 24.5' -> 294,
    10'-0" -> 120, 150'-0" -> 1800.
    """
    text = text.strip()
    match = _DIMENSION_RE.fullmatch(text)
    if not match:
        return None

    feet_str = match.group(1)
    inches_str = match.group(2)

    feet = float(feet_str)
    inches = float(inches_str) if inches_str else 0.0

    return feet * 12.0 + inches


def _normalize_scale_text(text: str) -> str:
    """Normalize scale text for tolerant parsing.

    Step 1 of the two-step approach: canonicalize Unicode quotes,
    collapse whitespace, and standardize separators so that the
    regex patterns in step 2 can match reliably.
    """
    # Replace Unicode right-double-quote / double-prime with ASCII "
    text = text.replace("\u201c", '"')  # left double quote
    text = text.replace("\u201d", '"')  # right double quote
    text = text.replace("\u2033", '"')  # double prime
    text = text.replace("\u201e", '"')  # double low-9 quote
    text = text.replace("\u00ab", '"')  # left guillemet
    text = text.replace("\u00bb", '"')  # right guillemet
    # Replace Unicode right-single-quote / prime with ASCII '
    text = text.replace("\u2018", "'")  # left single quote
    text = text.replace("\u2019", "'")  # right single quote
    text = text.replace("\u2032", "'")  # prime
    # Collapse multiple spaces / tabs into one space
    text = re.sub(r"[ \t]+", " ", text)
    return text


class ScaleDetector:
    """Detects drawing scale from title block text and dimension annotations."""

    def detect_from_text(self, page_text: str) -> ScaleResult | None:
        """Parse common architectural scale notations from page text.

        Uses a two-step approach:
        1. Normalize text (Unicode quotes, whitespace, separators)
        2. Apply tolerant regex patterns to the normalized text

        This avoids dependence on a single brittle regex by first
        canonicalizing the many formatting variants found in real PDFs.
        """
        # Step 1: Normalize text
        normalized = _normalize_scale_text(page_text)

        # Step 2: Tolerant parsing on normalized text
        # Try architectural fractional scales first
        result = self._try_arch_scale(normalized)
        if result is not None:
            return result

        # Try whole-inch scales: 1"=10'-0"
        result = self._try_whole_inch_scale(normalized)
        if result is not None:
            return result

        # Try metric-style 1:N scales
        return self._try_metric_scale(normalized)

    def detect_from_dimensions(
        self,
        paths: list[VectorPath],
        texts: list[TextBlock],
    ) -> ScaleResult | None:
        """Infer scale by cross-referencing dimension lines with text values.

        Looks for numeric dimension text near line endpoints and computes
        scale from the ratio of PDF length to annotated real-world length.
        """
        if not paths or not texts:
            return None

        # Find text blocks that contain dimension strings
        dim_texts: list[tuple[TextBlock, float]] = []
        for tb in texts:
            parsed = parse_dimension_string(tb.text.strip())
            if parsed is not None and parsed > 0:
                dim_texts.append((tb, parsed))

        if not dim_texts:
            return None

        # For each dimension text, find the nearest line and compute scale
        from cantena.geometry.extractor import PathType

        lines = [p for p in paths if p.path_type == PathType.LINE]
        if not lines:
            return None

        best_scale: ScaleResult | None = None
        best_dist = float("inf")

        for tb, real_inches in dim_texts:
            for line in lines:
                if len(line.points) < 2:
                    continue

                midpoint = Point2D(
                    (line.points[0].x + line.points[1].x) / 2,
                    (line.points[0].y + line.points[1].y) / 2,
                )

                dx = midpoint.x - tb.position.x
                dy = midpoint.y - tb.position.y
                dist = (dx * dx + dy * dy) ** 0.5

                # Only consider text within 50 pts of line midpoint
                if dist > 50:
                    continue

                # Compute line length in pts
                ldx = line.points[1].x - line.points[0].x
                ldy = line.points[1].y - line.points[0].y
                line_len_pts = (ldx * ldx + ldy * ldy) ** 0.5

                if line_len_pts < 1:
                    continue

                # paper_inches = line_len_pts / 72
                paper_inches = line_len_pts / 72.0
                scale_factor = real_inches / paper_inches

                if dist < best_dist:
                    best_dist = dist
                    best_scale = ScaleResult(
                        drawing_units=paper_inches,
                        real_units=real_inches,
                        scale_factor=scale_factor,
                        notation=tb.text.strip(),
                        confidence=Confidence.MEDIUM,
                    )

        return best_scale

    def extract_text_blocks(self, page: fitz.Page) -> list[TextBlock]:
        """Extract all text blocks from a PDF page with positions."""
        blocks: list[TextBlock] = []
        raw_blocks: list[tuple[object, ...]] = page.get_text("blocks")

        for raw in raw_blocks:
            # Each block: (x0, y0, x1, y1, text, block_no, block_type)
            if len(raw) < 7:
                continue

            block_type = raw[6]
            if block_type != 0:  # 0 = text block
                continue

            x0 = float(raw[0])  # type: ignore[arg-type]
            y0 = float(raw[1])  # type: ignore[arg-type]
            x1 = float(raw[2])  # type: ignore[arg-type]
            y1 = float(raw[3])  # type: ignore[arg-type]
            text = str(raw[4])

            center = Point2D((x0 + x1) / 2, (y0 + y1) / 2)
            rect = BoundingRect(
                x=x0, y=y0, width=x1 - x0, height=y1 - y0
            )
            blocks.append(TextBlock(text=text, position=center, bounding_rect=rect))

        return blocks

    def _try_arch_scale(self, text: str) -> ScaleResult | None:
        """Try to match architectural fractional scale patterns."""
        for match in _ARCH_SCALE_RE.finditer(text):
            frac_str = match.group(1).strip()
            feet = int(match.group(2))
            inches = int(match.group(3))

            drawing_inches = _FRACTION_MAP.get(frac_str)
            if drawing_inches is None:
                continue

            real_inches = feet * 12.0 + inches
            if real_inches <= 0:
                continue

            scale_factor = real_inches / drawing_inches
            notation = match.group(0).strip()

            return ScaleResult(
                drawing_units=drawing_inches,
                real_units=real_inches,
                scale_factor=scale_factor,
                notation=notation,
                confidence=Confidence.HIGH,
            )

        return None

    def _try_whole_inch_scale(self, text: str) -> ScaleResult | None:
        """Try to match whole-inch scale patterns like 1\"=10'-0\"."""
        for match in _WHOLE_INCH_SCALE_RE.finditer(text):
            drawing_inches = float(match.group(1))
            feet = int(match.group(2))
            inches = int(match.group(3))

            real_inches = feet * 12.0 + inches
            if real_inches <= 0 or drawing_inches <= 0:
                continue

            scale_factor = real_inches / drawing_inches
            notation = match.group(0).strip()

            return ScaleResult(
                drawing_units=drawing_inches,
                real_units=real_inches,
                scale_factor=scale_factor,
                notation=notation,
                confidence=Confidence.HIGH,
            )

        return None

    def _try_metric_scale(self, text: str) -> ScaleResult | None:
        """Try to match metric-style 1:N scale patterns."""
        for match in _METRIC_SCALE_RE.finditer(text):
            n = int(match.group(1))
            if n <= 0:
                continue

            notation = match.group(0).strip()

            return ScaleResult(
                drawing_units=1.0,
                real_units=float(n),
                scale_factor=float(n),
                notation=notation,
                confidence=Confidence.HIGH,
            )

        return None
