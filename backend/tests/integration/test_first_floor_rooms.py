"""US-356: Validate text and room label extraction for future room-type detection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cantena.geometry.scale import ScaleDetector, TextBlock

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_detector = ScaleDetector()

# Expected room labels (case-insensitive match against extracted text)
_EXPECTED_ROOM_LABELS: list[str] = [
    "LIVING ROOM",
    "KITCHEN",
    "DINING",
    "FRONT PORCH",
    "BACK PORCH",
    "UTILITY",
    "WC",
    "COATS",
    "LAUNDRY",
]

# Dimension pattern: e.g. 32', 6'-6", 5'-6", 3'-4"
_DIMENSION_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*['\u2019\u2032]"
    r"(?:\s*-?\s*\d+\s*(?:[\"'\u201d\u2033]|''))?",
)

# Expected title block fields (case-insensitive)
_TITLE_BLOCK_FIELDS: list[str] = [
    "SCALE",
    "1/4",
    "A1.2",
    "1ST FLOOR",
    "AMERICAN FARMHOUSE",
]


def _normalize_block_text(text: str) -> str:
    """Normalize text block content: collapse newlines and extra spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _find_label_block(
    blocks: list[TextBlock], label: str
) -> TextBlock | None:
    """Find the first text block whose text contains *label* (case-insensitive).

    Normalizes newlines to spaces before matching so that multi-line
    blocks like ``"BACK \\nPORCH"`` match ``"BACK PORCH"``.
    """
    label_lower = label.lower()
    for blk in blocks:
        normalized = _normalize_block_text(blk.text).lower()
        if label_lower in normalized:
            return blk
    return None


# ---------------------------------------------------------------------------
# Tests: room label extraction
# ---------------------------------------------------------------------------


class TestRoomLabelExtraction:
    """Verify we can find expected room labels in the extracted text."""

    def test_find_expected_room_labels(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Extract text blocks and find all expected room labels."""
        blocks = _detector.extract_text_blocks(first_floor_page)
        found: list[str] = []
        missed: list[str] = []

        for label in _EXPECTED_ROOM_LABELS:
            blk = _find_label_block(blocks, label)
            if blk is not None:
                found.append(label)
            else:
                missed.append(label)

        print("\n--- Room label search ---")
        print(f"  Found ({len(found)}): {found}")
        print(f"  Missed ({len(missed)}): {missed}")

        # All expected labels should be found
        assert len(missed) == 0, (
            f"Missing room labels: {missed}. "
            f"Found: {found}"
        )


# ---------------------------------------------------------------------------
# Tests: room label positions within drawing content area
# ---------------------------------------------------------------------------


class TestRoomLabelPositions:
    """Verify room label positions fall within the drawing content area."""

    def test_labels_within_content_area(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Room labels should be in the drawing area, not title block/margins."""
        blocks = _detector.extract_text_blocks(first_floor_page)
        page_rect = first_floor_page.rect
        page_w: float = page_rect.width
        page_h: float = page_rect.height

        # Content area: exclude ~5% margins on each side
        margin_x = page_w * 0.05
        margin_y = page_h * 0.05
        content_x_min = margin_x
        content_x_max = page_w - margin_x
        content_y_min = margin_y
        content_y_max = page_h - margin_y

        outside: list[str] = []
        for label in _EXPECTED_ROOM_LABELS:
            blk = _find_label_block(blocks, label)
            if blk is None:
                continue
            cx, cy = blk.position.x, blk.position.y
            if not (
                content_x_min <= cx <= content_x_max
                and content_y_min <= cy <= content_y_max
            ):
                outside.append(
                    f"{label} at ({cx:.0f}, {cy:.0f})"
                )

        assert len(outside) == 0, (
            f"Room labels outside content area: {outside}"
        )


# ---------------------------------------------------------------------------
# Tests: room labels spatially separated
# ---------------------------------------------------------------------------


class TestRoomLabelSpatialSeparation:
    """Distinct room label text blocks should be spatially separated."""

    def test_labels_spatially_separated(
        self, first_floor_page: fitz.Page
    ) -> None:
        """No two room labels from *distinct* text blocks within 20 pts.

        Some labels (e.g. LIVING ROOM and KITCHEN) may share the same
        PDF text block, which is acceptable — they annotate the same
        open-plan area. We only flag labels from truly separate blocks
        that are too close together.
        """
        blocks = _detector.extract_text_blocks(first_floor_page)

        # Collect (label, block_center) de-duplicating by block identity.
        # Two labels sharing the same block get the same position and are
        # expected to be at distance 0 — that is fine.
        seen_positions: dict[tuple[float, float], list[str]] = {}
        for label in _EXPECTED_ROOM_LABELS:
            blk = _find_label_block(blocks, label)
            if blk is not None:
                key = (blk.position.x, blk.position.y)
                seen_positions.setdefault(key, []).append(label)

        unique_entries = [
            (labels, x, y)
            for (x, y), labels in seen_positions.items()
        ]

        too_close: list[str] = []
        for i in range(len(unique_entries)):
            for j in range(i + 1, len(unique_entries)):
                labels_i, xi, yi = unique_entries[i]
                labels_j, xj, yj = unique_entries[j]
                dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
                if dist < 20.0:
                    too_close.append(
                        f"{labels_i} <-> {labels_j}: {dist:.1f} pts"
                    )

        assert len(too_close) == 0, (
            f"Distinct room label blocks too close: {too_close}"
        )


# ---------------------------------------------------------------------------
# Tests: coarse zone mapping (left half vs right half)
# ---------------------------------------------------------------------------


class TestCoarseZoneMapping:
    """Labels should fall in expected spatial zones."""

    def test_zone_mapping(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Assign labels to left/right zones and verify expectations."""
        blocks = _detector.extract_text_blocks(first_floor_page)
        page_rect = first_floor_page.rect
        midpoint_x: float = page_rect.width / 2.0

        # Build zone mapping
        left_labels: list[str] = []
        right_labels: list[str] = []

        for label in _EXPECTED_ROOM_LABELS:
            blk = _find_label_block(blocks, label)
            if blk is None:
                continue
            if blk.position.x < midpoint_x:
                left_labels.append(label)
            else:
                right_labels.append(label)

        print("\n--- Zone mapping ---")
        print(f"  Page midpoint X: {midpoint_x:.0f}")
        print(f"  Left half ({len(left_labels)}): {left_labels}")
        print(f"  Right half ({len(right_labels)}): {right_labels}")

        # Both halves should have at least one label
        assert len(left_labels) >= 1, (
            "Expected at least 1 room label in left half"
        )
        assert len(right_labels) >= 1, (
            "Expected at least 1 room label in right half"
        )


# ---------------------------------------------------------------------------
# Tests: dimension pattern text blocks
# ---------------------------------------------------------------------------


class TestDimensionBlocks:
    """Verify we find sufficient dimension annotation text blocks."""

    def test_at_least_10_dimension_blocks(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Find text blocks matching dimension patterns (e.g. 32', 6'-6\")."""
        blocks = _detector.extract_text_blocks(first_floor_page)

        dim_blocks: list[tuple[str, float, float]] = []
        for blk in blocks:
            text = blk.text.strip()
            if _DIMENSION_PATTERN.search(text):
                dim_blocks.append(
                    (text.replace("\n", " "), blk.position.x, blk.position.y)
                )

        print(f"\n--- Dimension blocks ({len(dim_blocks)}) ---")
        for text, x, y in dim_blocks[:20]:
            print(f"  ({x:.0f}, {y:.0f}) {text!r}")

        assert len(dim_blocks) >= 10, (
            f"Expected >= 10 dimension blocks, got {len(dim_blocks)}"
        )


# ---------------------------------------------------------------------------
# Tests: title block fields in border area
# ---------------------------------------------------------------------------


def _collapse_spaced_text(text: str) -> str:
    """Collapse spaced-out title block text like 'A M E R I C A N'.

    Construction drawings often space out text in title blocks for
    visual emphasis. This collapses single-char-space-single-char
    sequences back into words, then normalizes remaining whitespace.
    """
    collapsed = re.sub(r"\b(\w) (?=\w\b)", r"\1", text)
    return re.sub(r"\s+", " ", collapsed)


class TestTitleBlockFields:
    """Verify title block text in the border area of the page."""

    def test_find_title_block_fields(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Find SCALE, 1/4, A1.2, 1ST FLOOR, AMERICAN FARMHOUSE.

        Title block elements on this drawing are spread across the right
        edge (sheet info), lower-left (scale notation), and lower-right
        (sheet number / title). We search border areas: right 15% or
        bottom 15% of the page.
        """
        blocks = _detector.extract_text_blocks(first_floor_page)
        page_rect = first_floor_page.rect
        page_w: float = page_rect.width
        page_h: float = page_rect.height

        # Border area: right 15% OR bottom 15% of the page
        border_blocks = [
            blk
            for blk in blocks
            if blk.position.x > page_w * 0.85
            or blk.position.y > page_h * 0.85
        ]

        # Combine all text, normalizing newlines and collapsing spaced text
        raw_text = " ".join(blk.text for blk in border_blocks)
        border_text = _collapse_spaced_text(raw_text).lower()

        found: list[str] = []
        missed: list[str] = []

        for field_text in _TITLE_BLOCK_FIELDS:
            if field_text.lower() in border_text:
                found.append(field_text)
            else:
                missed.append(field_text)

        print("\n--- Title block fields (border area) ---")
        print(f"  Border blocks: {len(border_blocks)}")
        print(f"  Found ({len(found)}): {found}")
        print(f"  Missed ({len(missed)}): {missed}")

        assert len(missed) == 0, (
            f"Missing title block fields in border: {missed}. "
            f"Found: {found}"
        )
