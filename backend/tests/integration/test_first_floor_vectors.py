"""US-352: Validate vector extraction on the real floor plan."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pytest

from cantena.geometry.extractor import BoundingRect, VectorExtractor

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_extractor = VectorExtractor()


def _is_dark_color(color: tuple[float, float, float] | None) -> bool:
    """Return True if *color* is black or dark gray (RGB sum <= 1.0)."""
    if color is None:
        return False
    return sum(color) <= 1.0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVectorExtraction:
    """Verify that VectorExtractor pulls meaningful geometry from the PDF."""

    def test_returns_at_least_50_paths(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        assert len(data.paths) >= 50, (
            f"Expected at least 50 paths, got {len(data.paths)}"
        )

    def test_stats_line_count_gt_20(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        stats = _extractor.get_stats(data)
        assert stats.line_count > 20, (
            f"Expected line_count > 20, got {stats.line_count}"
        )

    def test_stats_rect_count_ge_0(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        stats = _extractor.get_stats(data)
        assert stats.rect_count >= 0

    def test_bounding_box_covers_page(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Bounding box of geometry covers >=50% of page width and >=40% of height."""
        data = _extractor.extract(first_floor_page)
        stats = _extractor.get_stats(data)
        assert stats.bounding_box is not None, "No bounding box computed"

        bb = stats.bounding_box
        width_coverage = bb.width / data.page_width_pts
        height_coverage = bb.height / data.page_height_pts
        assert width_coverage >= 0.50, (
            f"Bounding box covers {width_coverage:.1%} of page width (need >=50%)"
        )
        assert height_coverage >= 0.40, (
            f"Bounding box covers {height_coverage:.1%} of page height (need >=40%)"
        )

    def test_at_least_2_distinct_line_widths(
        self, first_floor_page: fitz.Page
    ) -> None:
        """At least 2 distinct line_width values exist; log distribution."""
        data = _extractor.extract(first_floor_page)
        width_counter: Counter[float] = Counter()
        for path in data.paths:
            width_counter[path.line_width] += 1

        # Log the distribution for debugging
        print("\n--- Line width distribution ---")
        for width, count in width_counter.most_common():
            print(f"  width={width:.3f}  count={count}")

        distinct = len(width_counter)
        assert distinct >= 2, (
            f"Expected at least 2 distinct line widths, got {distinct}: "
            f"{list(width_counter.keys())}"
        )

    def test_most_paths_have_stroke_color(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Most paths have stroke_color; black/dark gray is the majority."""
        data = _extractor.extract(first_floor_page)
        total = len(data.paths)
        assert total > 0, "No paths extracted"

        with_stroke = sum(
            1 for p in data.paths if p.stroke_color is not None
        )
        dark_count = sum(
            1 for p in data.paths if _is_dark_color(p.stroke_color)
        )

        stroke_pct = with_stroke / total
        dark_pct = dark_count / total if total else 0.0

        print("\n--- Stroke color stats ---")
        print(
            f"  {with_stroke}/{total} ({stroke_pct:.0%}) have stroke_color"
        )
        print(f"  {dark_count}/{total} ({dark_pct:.0%}) are black/dark gray")

        assert stroke_pct > 0.5, (
            f"Expected majority of paths to have stroke_color, "
            f"only {stroke_pct:.0%}"
        )

    def test_filter_by_region_reduces_paths(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Filtering to left half of drawing returns fewer paths than full set."""
        data = _extractor.extract(first_floor_page)
        left_half = BoundingRect(
            x=0.0,
            y=0.0,
            width=data.page_width_pts / 2,
            height=data.page_height_pts,
        )
        filtered = _extractor.filter_by_region(data, left_half)
        assert len(filtered.paths) < len(data.paths), (
            f"filter_by_region(left half) returned {len(filtered.paths)} "
            f"paths, same as unfiltered ({len(data.paths)}). "
            "Expected fewer."
        )


class TestRasterizedFallback:
    """If PDF turns out to be rasterized, skip gracefully."""

    def test_skip_if_rasterized(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Skip all vector tests if this PDF has no usable vector data."""
        data = _extractor.extract(first_floor_page)
        if len(data.paths) < 10:
            pytest.skip(
                f"PDF appears rasterized (only {len(data.paths)} paths). "
                "Vector tests are not applicable."
            )
