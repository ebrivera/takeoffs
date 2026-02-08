"""Shared fixtures for integration tests against real architectural drawings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # type: ignore[import-untyped]
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_TEST_PDF_DIR = Path(__file__).resolve().parents[3] / "test_pdfs"
FIRST_FLOOR_PDF = _TEST_PDF_DIR / "first-floor.pdf"

# ---------------------------------------------------------------------------
# Ground truth values for first-floor.pdf (American Farmhouse 1st Floor)
# Scale: 1/4" = 1'-0"  →  scale_factor = 48.0
# Main building footprint: 32' × 16' = 512 SF
# ---------------------------------------------------------------------------

EXPECTED_SCALE_FACTOR = 48.0
EXPECTED_OVERALL_WIDTH_FT = 32.0
EXPECTED_OVERALL_DEPTH_FT = 16.0
EXPECTED_GROSS_AREA_SF = 512.0
# Porches extend beyond main footprint; approximate total with porches
EXPECTED_TOTAL_WITH_PORCHES_SF = 700.0
EXPECTED_ROOM_COUNT = 7  # minimum: at least 7 named rooms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def first_floor_pdf() -> Generator[fitz.Document, None, None]:
    """Open test_pdfs/first-floor.pdf and yield the fitz.Document."""
    assert FIRST_FLOOR_PDF.exists(), (
        f"Test PDF not found: {FIRST_FLOOR_PDF}"
    )
    doc: fitz.Document = fitz.open(str(FIRST_FLOOR_PDF))
    yield doc
    doc.close()


@pytest.fixture()
def first_floor_page(
    first_floor_pdf: fitz.Document,
) -> fitz.Page:
    """Yield the first (and only) page of first-floor.pdf."""
    assert len(first_floor_pdf) >= 1, "PDF has no pages"
    return first_floor_pdf[0]
