"""Tests for cantena.geometry.extractor — vector path extraction from PDFs."""

from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

from cantena.geometry.extractor import (
    BoundingRect,
    DrawingData,
    PathType,
    Point2D,
    VectorExtractor,
)


def _create_test_pdf_with_geometry(path: Path) -> None:
    """Create a PDF with known geometry: a rectangle and two diagonal lines."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter
    shape = page.new_shape()

    # Draw a rectangle at (100, 100) → (300, 250)
    shape.draw_rect(fitz.Rect(100, 100, 300, 250))
    shape.finish(color=(0, 0, 0), width=1.0)

    # Draw a line from (50, 50) to (200, 200)
    shape.draw_line(fitz.Point(50, 50), fitz.Point(200, 200))
    shape.finish(color=(1, 0, 0), width=0.5)

    # Draw another line from (400, 100) to (500, 300)
    shape.draw_line(fitz.Point(400, 100), fitz.Point(500, 300))
    shape.finish(color=(0, 0, 1), width=0.5)

    shape.commit()
    doc.save(str(path))
    doc.close()


def _create_empty_pdf(path: Path) -> None:
    """Create a valid PDF with one page but no drawings."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()


def _create_text_only_pdf(path: Path) -> None:
    """Create a PDF with text but no vector drawings."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    writer = fitz.TextWriter(page.rect)
    font = fitz.Font("helv")
    writer.append((100, 100), "Hello World", font=font, fontsize=14)
    writer.write_text(page)
    doc.save(str(path))
    doc.close()


class TestVectorExtraction:
    """Tests for VectorExtractor.extract() with known geometry."""

    def test_extract_known_geometry(self) -> None:
        """Extract a rect and two lines from a test PDF, verify types and counts."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            assert data.page_width_pts == pytest.approx(612.0)
            assert data.page_height_pts == pytest.approx(792.0)
            assert data.page_size_inches == pytest.approx((8.5, 11.0))

            # Should have at least a rect and two lines
            types = [p.path_type for p in data.paths]
            assert PathType.RECT in types
            assert types.count(PathType.LINE) >= 2
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_extract_rect_coordinates(self) -> None:
        """Verify extracted rectangle has correct bounding rect."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            rects = [p for p in data.paths if p.path_type == PathType.RECT]
            assert len(rects) >= 1
            r = rects[0]
            assert r.bounding_rect.x == pytest.approx(100.0)
            assert r.bounding_rect.y == pytest.approx(100.0)
            assert r.bounding_rect.width == pytest.approx(200.0)
            assert r.bounding_rect.height == pytest.approx(150.0)
            assert len(r.points) == 4
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_extract_line_coordinates(self) -> None:
        """Verify extracted lines have correct endpoint coordinates."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            lines = [p for p in data.paths if p.path_type == PathType.LINE]
            assert len(lines) >= 2

            # Find the line from (50,50) to (200,200)
            line1 = next(
                (
                    seg
                    for seg in lines
                    if abs(seg.points[0].x - 50) < 1
                    and abs(seg.points[0].y - 50) < 1
                ),
                None,
            )
            assert line1 is not None
            assert line1.points[1].x == pytest.approx(200.0, abs=1)
            assert line1.points[1].y == pytest.approx(200.0, abs=1)
            assert line1.stroke_color == (1.0, 0.0, 0.0)
        finally:
            pdf_path.unlink(missing_ok=True)


class TestFilterByRegion:
    """Tests for VectorExtractor.filter_by_region()."""

    def test_filter_excludes_outside_paths(self) -> None:
        """Paths fully outside the region should be excluded."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            # Region that only covers the top-left area (should include
            # the line from 50,50→200,200 but exclude 400,100→500,300)
            region = BoundingRect(x=0, y=0, width=250, height=250)
            filtered = extractor.filter_by_region(data, region)

            # The 400→500 line should be excluded
            for p in filtered.paths:
                assert not (
                    p.path_type == PathType.LINE
                    and p.points[0].x > 350
                ), "Line at x>350 should be excluded"

            assert len(filtered.paths) < len(data.paths)
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_filter_preserves_page_metadata(self) -> None:
        """Filtered DrawingData retains page dimensions."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            region = BoundingRect(x=0, y=0, width=100, height=100)
            filtered = extractor.filter_by_region(data, region)
            assert filtered.page_width_pts == data.page_width_pts
            assert filtered.page_height_pts == data.page_height_pts
        finally:
            pdf_path.unlink(missing_ok=True)


class TestDrawingStats:
    """Tests for VectorExtractor.get_stats()."""

    def test_stats_computed_correctly(self) -> None:
        """Stats should reflect correct counts and total line length."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_test_pdf_with_geometry(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            stats = extractor.get_stats(data)
            assert stats.path_count == len(data.paths)
            assert stats.rect_count >= 1
            assert stats.line_count >= 2
            assert stats.total_line_length_pts > 0
            assert stats.bounding_box is not None
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_stats_empty_data(self) -> None:
        """Stats on empty DrawingData should be all zeros."""
        extractor = VectorExtractor()
        empty = DrawingData()
        stats = extractor.get_stats(empty)
        assert stats.path_count == 0
        assert stats.line_count == 0
        assert stats.rect_count == 0
        assert stats.total_line_length_pts == 0.0
        assert stats.bounding_box is None


class TestEmptyAndTextOnlyPdfs:
    """Tests for edge cases: empty pages and text-only pages."""

    def test_empty_page_returns_empty_data(self) -> None:
        """A page with no drawings should return empty paths list."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_empty_pdf(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            assert data.paths == []
            assert data.page_width_pts == pytest.approx(612.0)
            assert data.page_height_pts == pytest.approx(792.0)
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_text_only_page_returns_empty_paths(self) -> None:
        """A page with only text should return empty paths list."""
        extractor = VectorExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            _create_text_only_pdf(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            data = extractor.extract(page)
            doc.close()

            assert data.paths == []
        finally:
            pdf_path.unlink(missing_ok=True)


class TestBoundingRect:
    """Tests for BoundingRect helper methods."""

    def test_contains_point(self) -> None:
        rect = BoundingRect(x=10, y=10, width=100, height=50)
        assert rect.contains(Point2D(50, 30))
        assert not rect.contains(Point2D(200, 200))

    def test_intersects(self) -> None:
        r1 = BoundingRect(x=0, y=0, width=100, height=100)
        r2 = BoundingRect(x=50, y=50, width=100, height=100)
        r3 = BoundingRect(x=200, y=200, width=50, height=50)
        assert r1.intersects(r2)
        assert not r1.intersects(r3)
