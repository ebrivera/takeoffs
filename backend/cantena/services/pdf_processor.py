"""PDF processing service — converts PDF pages to high-resolution PNG images."""

from __future__ import annotations

import contextlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # type: ignore[import-untyped]


@dataclass(frozen=True)
class PageResult:
    """Result of processing a single PDF page."""

    page_number: int
    image_path: Path
    width_px: int
    height_px: int
    text_content: str
    title_block_text: str | None


@dataclass(frozen=True)
class PdfProcessingResult:
    """Result of processing an entire PDF."""

    pages: list[PageResult] = field(default_factory=list)
    page_count: int = 0
    file_size_bytes: int = 0


_DPI = 200
_ZOOM = _DPI / 72  # fitz uses 72 DPI as baseline


class PdfProcessor:
    """Converts PDF pages to high-resolution PNG images for VLM analysis."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir

    def process(self, pdf_path: Path) -> PdfProcessingResult:
        """Convert each page of *pdf_path* to a 200-DPI PNG image.

        Returns a :class:`PdfProcessingResult` with metadata and image paths.

        Raises
        ------
        ValueError
            If *pdf_path* does not exist or is not a valid PDF.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            msg = f"PDF file not found: {pdf_path}"
            raise ValueError(msg)

        file_size = pdf_path.stat().st_size

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            msg = f"Failed to open PDF: {pdf_path}"
            raise ValueError(msg) from exc

        if doc.page_count == 0:
            doc.close()
            return PdfProcessingResult(pages=[], page_count=0, file_size_bytes=file_size)

        out_dir = Path(self._output_dir) if self._output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        pages: list[PageResult] = []
        matrix = fitz.Matrix(_ZOOM, _ZOOM)

        for page_num in range(doc.page_count):
            page = doc[page_num]

            # Render page to pixmap at 200 DPI
            pix = page.get_pixmap(matrix=matrix)
            image_path = out_dir / f"page_{page_num + 1}.png"
            pix.save(str(image_path))

            # Extract full-page text
            text_content = page.get_text()

            # Extract title-block text (bottom-right quadrant heuristic)
            title_block_text = self._extract_title_block(page)

            pages.append(
                PageResult(
                    page_number=page_num + 1,
                    image_path=image_path,
                    width_px=pix.width,
                    height_px=pix.height,
                    text_content=text_content,
                    title_block_text=title_block_text,
                )
            )

        page_count = doc.page_count
        doc.close()

        return PdfProcessingResult(
            pages=pages,
            page_count=page_count,
            file_size_bytes=file_size,
        )

    @staticmethod
    def cleanup(result: PdfProcessingResult) -> None:
        """Delete temporary image files referenced by *result*."""
        dirs_to_remove: set[Path] = set()
        for page in result.pages:
            if page.image_path.exists():
                dirs_to_remove.add(page.image_path.parent)
                page.image_path.unlink()
        # Remove the output directory if it is now empty
        for d in dirs_to_remove:
            with contextlib.suppress(OSError):
                d.rmdir()

    @staticmethod
    def _extract_title_block(page: fitz.Page) -> str | None:
        """Extract text from the bottom-right quadrant (title block area)."""
        rect = page.rect
        mid_x = (rect.x0 + rect.x1) / 2
        mid_y = (rect.y0 + rect.y1) / 2
        clip = fitz.Rect(mid_x, mid_y, rect.x1, rect.y1)
        text = page.get_text(clip=clip).strip()
        return text if text else None
