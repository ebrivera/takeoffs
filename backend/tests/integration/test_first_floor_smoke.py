"""Smoke tests: verify first-floor.pdf loads and is usable for geometry testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


class TestFirstFloorSmoke:
    """Basic sanity checks on the test PDF."""

    def test_pdf_loads_without_error(
        self,
        first_floor_pdf: fitz.Document,
    ) -> None:
        """PDF opens without raising any exception."""
        assert first_floor_pdf is not None

    def test_pdf_has_exactly_one_page(
        self,
        first_floor_pdf: fitz.Document,
    ) -> None:
        """First-floor plan is a single-page document."""
        assert len(first_floor_pdf) == 1

    def test_page_has_nonzero_dimensions(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Page has non-zero width and height."""
        rect = first_floor_page.rect
        assert rect.width > 0, f"Page width is {rect.width}"
        assert rect.height > 0, f"Page height is {rect.height}"

    def test_page_contains_text(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Page has extractable text (not a scanned raster image)."""
        text = first_floor_page.get_text()
        assert len(text.strip()) > 0, (
            "No text found — PDF may be a scanned image"
        )
