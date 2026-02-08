"""Tests for the geometry debug visualization endpoint."""

from __future__ import annotations

import io

import fitz  # type: ignore[import-untyped]
from fastapi.testclient import TestClient

from cantena.api.app import create_app


def _create_test_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _make_pdf_with_geometry() -> bytes:
    """Create a PDF with known vector geometry for testing."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    shape = page.new_shape()

    # Draw thick walls (will be detected as walls)
    shape.draw_line(fitz.Point(100, 100), fitz.Point(500, 100))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.draw_line(fitz.Point(500, 100), fitz.Point(500, 400))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.draw_line(fitz.Point(500, 400), fitz.Point(100, 400))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.draw_line(fitz.Point(100, 400), fitz.Point(100, 100))
    shape.finish(color=(0, 0, 0), width=2.0)

    # Add scale text
    page.insert_text(
        fitz.Point(50, 750),
        'SCALE: 1/8"=1\'-0"',
        fontsize=10,
    )

    shape.commit()

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_minimal_pdf() -> bytes:
    """Create a minimal valid PDF without geometry."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestDebugGeometryPng:
    def test_returns_200_with_png_for_valid_pdf(self) -> None:
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_geometry()

        response = client.post(
            "/api/debug/geometry",
            files={
                "file": ("plan.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert response.content[:4] == b"\x89PNG"

    def test_returns_200_for_empty_geometry(self) -> None:
        client = _create_test_client()
        pdf_bytes = _make_minimal_pdf()

        response = client.post(
            "/api/debug/geometry",
            files={
                "file": ("plan.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


class TestDebugGeometryJson:
    def test_json_includes_measurements(self) -> None:
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_geometry()

        response = client.post(
            "/api/debug/geometry?output=json",
            files={
                "file": ("plan.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "image_base64" in data
        assert "measurements" in data

        measurements = data["measurements"]
        assert "scale" in measurements
        assert "gross_area_sf" in measurements
        assert "wall_count" in measurements
        assert "confidence" in measurements
        assert "wall_segments" in measurements
        assert "stats" in measurements

    def test_json_wall_segments_have_structure(self) -> None:
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_geometry()

        response = client.post(
            "/api/debug/geometry?output=json",
            files={
                "file": ("plan.pdf", io.BytesIO(pdf_bytes), "application/pdf"),
            },
        )

        data = response.json()
        segments = data["measurements"]["wall_segments"]
        assert len(segments) > 0

        seg = segments[0]
        assert "start" in seg
        assert "end" in seg
        assert "x" in seg["start"]
        assert "y" in seg["start"]
        assert "orientation" in seg
        assert "length_pts" in seg


class TestDebugGeometryValidation:
    def test_non_pdf_returns_400(self) -> None:
        client = _create_test_client()

        response = client.post(
            "/api/debug/geometry",
            files={
                "file": (
                    "image.png",
                    io.BytesIO(b"fake png data"),
                    "image/png",
                ),
            },
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]
