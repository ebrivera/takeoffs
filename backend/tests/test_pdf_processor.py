"""Tests for the PDF processing service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import fitz
import pytest

from cantena.services.pdf_processor import PdfProcessingResult, PdfProcessor

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Return a temporary directory for image output."""
    return tmp_path / "output"


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal 1-page PDF with text for testing."""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter
    # Insert text in main area
    page.insert_text((72, 100), "Floor Plan - Level 1", fontsize=14)
    page.insert_text((72, 140), "Scale: 1/8\" = 1'-0\"", fontsize=10)
    # Insert text in bottom-right quadrant (title block area)
    page.insert_text((400, 700), "Sheet A-101", fontsize=10)
    page.insert_text((400, 720), "Project: Test Office", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def multi_page_pdf(tmp_path: Path) -> Path:
    """Create a 3-page PDF for multi-page testing."""
    pdf_path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 100), f"Page {i + 1} content", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def empty_pdf(tmp_path: Path) -> Path:
    """Create a PDF with zero pages (raw bytes — PyMuPDF can't save empty docs)."""
    pdf_path = tmp_path / "empty.pdf"
    # Minimal valid PDF structure with no pages
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"xref\n0 3\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"trailer<</Size 3/Root 1 0 R>>\nstartxref\n97\n%%EOF"
    )
    return pdf_path


# ---------------------------------------------------------------------------
# Tests: process a PDF
# ---------------------------------------------------------------------------

class TestPdfProcessorProcess:
    def test_process_single_page(self, sample_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(sample_pdf)

        assert result.page_count == 1
        assert len(result.pages) == 1
        assert result.file_size_bytes > 0

        page = result.pages[0]
        assert page.page_number == 1
        assert page.image_path.exists()
        assert page.image_path.suffix == ".png"
        assert page.width_px > 0
        assert page.height_px > 0

    def test_process_multi_page(self, multi_page_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(multi_page_pdf)

        assert result.page_count == 3
        assert len(result.pages) == 3
        for i, page in enumerate(result.pages, 1):
            assert page.page_number == i
            assert page.image_path.exists()

    def test_200_dpi_resolution(self, sample_pdf: Path, tmp_output: Path) -> None:
        """Images should be rendered at 200 DPI (≈2.78x the 72 DPI base)."""
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(sample_pdf)
        page = result.pages[0]

        # US Letter at 200 DPI: 8.5" * 200 ≈ 1700, 11" * 200 ≈ 2200
        assert page.width_px == pytest.approx(1700, abs=5)
        assert page.height_px == pytest.approx(2200, abs=5)

    def test_default_output_dir(self, sample_pdf: Path) -> None:
        """When no output_dir given, uses system temp."""
        processor = PdfProcessor()
        result = processor.process(sample_pdf)

        assert result.page_count == 1
        assert result.pages[0].image_path.exists()
        # Cleanup
        PdfProcessor.cleanup(result)


# ---------------------------------------------------------------------------
# Tests: text extraction
# ---------------------------------------------------------------------------

class TestTextExtraction:
    def test_text_content_extracted(self, sample_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(sample_pdf)

        page = result.pages[0]
        assert "Floor Plan" in page.text_content
        assert "Scale" in page.text_content

    def test_title_block_extraction(self, sample_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(sample_pdf)

        page = result.pages[0]
        assert page.title_block_text is not None
        assert "Sheet A-101" in page.title_block_text


# ---------------------------------------------------------------------------
# Tests: cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_deletes_files(self, sample_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(sample_pdf)

        image_path = result.pages[0].image_path
        assert image_path.exists()

        PdfProcessor.cleanup(result)
        assert not image_path.exists()

    def test_cleanup_empty_result(self) -> None:
        """Cleanup on an empty result should not raise."""
        PdfProcessor.cleanup(PdfProcessingResult())


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_empty_pdf(self, empty_pdf: Path, tmp_output: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_output)
        result = processor.process(empty_pdf)

        assert result.page_count == 0
        assert result.pages == []
        assert result.file_size_bytes > 0

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        processor = PdfProcessor(output_dir=tmp_path)
        with pytest.raises(ValueError, match="not found"):
            processor.process(tmp_path / "nonexistent.pdf")

    def test_non_pdf_file(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "not_a_pdf.pdf"
        bad_file.write_text("this is not a PDF")
        processor = PdfProcessor(output_dir=tmp_path)
        with pytest.raises(ValueError, match="Failed to open PDF"):
            processor.process(bad_file)
