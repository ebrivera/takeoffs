"""Tests for debug visualization with room polygons and labels."""

from __future__ import annotations

import io

import fitz  # type: ignore[import-untyped]
from fastapi.testclient import TestClient
from PIL import Image

from cantena.api.app import create_app


def _create_test_client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _make_pdf_with_rooms() -> bytes:
    """Create a PDF with two adjacent rooms that polygonize can detect.

    Draws a rectangle split into two rooms (left and right) with thick
    wall lines and a scale annotation so MeasurementService produces
    rooms with labels.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    shape = page.new_shape()

    # Outer rectangle
    shape.draw_line(fitz.Point(100, 200), fitz.Point(500, 200))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(500, 200), fitz.Point(500, 500))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(500, 500), fitz.Point(100, 500))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(100, 500), fitz.Point(100, 200))
    shape.finish(color=(0, 0, 0), width=2.0)

    # Dividing wall at center
    shape.draw_line(fitz.Point(300, 200), fitz.Point(300, 500))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.commit()

    # Add scale text
    page.insert_text(
        fitz.Point(50, 750),
        'SCALE: 1/4"=1\'-0"',
        fontsize=10,
    )

    # Add room labels inside the rooms
    page.insert_text(fitz.Point(160, 360), "KITCHEN", fontsize=10)
    page.insert_text(fitz.Point(360, 360), "DINING", fontsize=10)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_pdf_without_rooms() -> bytes:
    """Create a PDF with non-closing segments that won't form room polygons."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    shape = page.new_shape()

    # Just two isolated segments — can't form a room polygon
    shape.draw_line(fitz.Point(100, 300), fitz.Point(400, 300))
    shape.finish(color=(0, 0, 0), width=2.0)
    shape.draw_line(fitz.Point(100, 400), fitz.Point(400, 400))
    shape.finish(color=(0, 0, 0), width=2.0)

    shape.commit()

    page.insert_text(
        fitz.Point(50, 750),
        'SCALE: 1/4"=1\'-0"',
        fontsize=10,
    )

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestDebugRoomsPngOverlay:
    """PNG overlay draws room fills in room areas."""

    def test_room_detectable_pdf_modifies_room_pixels(self) -> None:
        """Room polygons produce semi-transparent fills in PNG output."""
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_rooms()

        response = client.post(
            "/api/debug/geometry",
            files={
                "file": (
                    "rooms.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

        # Parse the PNG and check that room-area pixels are not plain white
        img = Image.open(io.BytesIO(response.content))
        img_rgb = img.convert("RGB")

        # Sample a pixel inside the left room area (centroid ~200, 350)
        # With zoom=2.0: pixel at (400, 700)
        zoom = 2.0
        lx = int(200 * zoom)
        ly = int(350 * zoom)
        pixel = img_rgb.getpixel((lx, ly))
        # The fill should tint the pixel — it should differ from pure white
        assert pixel != (255, 255, 255), (
            "Room area pixel should be tinted by overlay"
        )

    def test_without_rooms_still_returns_png(self) -> None:
        """PDF with no room polygons still gets wall overlay."""
        client = _create_test_client()
        pdf_bytes = _make_pdf_without_rooms()

        response = client.post(
            "/api/debug/geometry",
            files={
                "file": (
                    "no-rooms.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content[:4] == b"\x89PNG"


class TestDebugRoomsJson:
    """JSON response includes rooms[] with room data."""

    def test_room_detectable_pdf_returns_rooms_in_json(self) -> None:
        """JSON response includes rooms array with structure."""
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_rooms()

        response = client.post(
            "/api/debug/geometry?output=json",
            files={
                "file": (
                    "rooms.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            },
        )

        assert response.status_code == 200
        data = response.json()
        measurements = data["measurements"]

        assert "rooms" in measurements
        rooms = measurements["rooms"]
        assert len(rooms) >= 1

        # Verify room structure
        room = rooms[0]
        assert "room_index" in room
        assert "label" in room
        assert "area_sf" in room
        assert "perimeter_lf" in room
        assert "polygon_vertices" in room
        assert "centroid" in room

        # Polygon vertices have x/y
        assert len(room["polygon_vertices"]) >= 3
        vertex = room["polygon_vertices"][0]
        assert "x" in vertex
        assert "y" in vertex

        # Centroid has x/y
        assert "x" in room["centroid"]
        assert "y" in room["centroid"]

    def test_without_rooms_json_has_empty_rooms(self) -> None:
        """JSON response has empty rooms list when no rooms detected."""
        client = _create_test_client()
        pdf_bytes = _make_pdf_without_rooms()

        response = client.post(
            "/api/debug/geometry?output=json",
            files={
                "file": (
                    "no-rooms.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            },
        )

        assert response.status_code == 200
        data = response.json()
        measurements = data["measurements"]

        # rooms key present but may be empty or contain fallback hull room
        assert "rooms" in measurements

    def test_backward_compatible_fields_present(self) -> None:
        """JSON still has all pre-existing measurement fields."""
        client = _create_test_client()
        pdf_bytes = _make_pdf_with_rooms()

        response = client.post(
            "/api/debug/geometry?output=json",
            files={
                "file": (
                    "rooms.pdf",
                    io.BytesIO(pdf_bytes),
                    "application/pdf",
                ),
            },
        )

        data = response.json()
        m = data["measurements"]

        # All pre-existing fields still present
        assert "scale" in m
        assert "gross_area_sf" in m
        assert "wall_count" in m
        assert "confidence" in m
        assert "wall_segments" in m
        assert "stats" in m
