"""Integration tests: center-line room polygonization on first-floor.pdf.

These tests validate that the center-line extraction pipeline
(parallel wall pairs → center-lines → gap closing → polygonize)
produces actual room polygons from the real first-floor.pdf drawing,
instead of falling back to convex hull or LLM-based identification.

Ground truth: American Farmhouse 1st floor, 32'×16' = 512 SF,
rooms include Living Room, Kitchen, Dining, Utility, WC, Coats, Laundry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cantena.geometry.centerline import (
    close_gaps,
    extend_to_intersections,
    extract_centerlines,
)
from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import MeasurementService, pts_to_real_sf
from cantena.geometry.rooms import RoomDetector
from cantena.geometry.scale import ScaleDetector, ScaleResult
from cantena.geometry.snap import snap_endpoints
from cantena.geometry.walls import WallDetector

from .conftest import EXPECTED_GROSS_AREA_SF, EXPECTED_SCALE_FACTOR

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


_extractor = VectorExtractor()
_wall_detector = WallDetector()
_scale = ScaleResult(
    drawing_units=0.25,
    real_units=12.0,
    scale_factor=EXPECTED_SCALE_FACTOR,
    notation='1/4"=1\'-0"',
    confidence=None,  # type: ignore[arg-type]
)


# ---------------------------------------------------------------------------
# Center-line extraction on real drawing
# ---------------------------------------------------------------------------


class TestCenterlineExtraction:
    """Validate center-line extraction from parallel wall pairs."""

    def test_centerlines_extracted(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Should extract at least 8 center-lines from parallel wall pairs."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        snapped = snap_endpoints(analysis.segments)
        result = extract_centerlines(snapped)

        print(f"\n--- Center-lines: {len(result.centerlines)} ---")
        print(f"--- Unpaired: {len(result.unpaired)} ---")
        print(f"--- Wall thickness: {result.wall_thickness_pts} pts ---")

        assert len(result.centerlines) >= 8, (
            f"Expected at least 8 center-lines, got {len(result.centerlines)}"
        )

    def test_wall_thickness_detected(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Should detect wall thickness in a reasonable range (~5-15 pts)."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        snapped = snap_endpoints(analysis.segments)
        result = extract_centerlines(snapped)

        assert result.wall_thickness_pts is not None
        # At 1/4" scale: 5 pts ≈ 3.3 in, 15 pts ≈ 10 in
        assert 5 <= result.wall_thickness_pts <= 15, (
            f"Wall thickness {result.wall_thickness_pts:.1f} pts outside "
            f"expected range 5-15 pts"
        )

    def test_few_unpaired_segments(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Most segments should be paired; unpaired should be minority."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        snapped = snap_endpoints(analysis.segments)
        result = extract_centerlines(snapped)

        total = len(result.centerlines) + len(result.unpaired)
        unpaired_pct = len(result.unpaired) / max(total, 1) * 100
        print(f"\n--- Unpaired: {len(result.unpaired)}/{total} ({unpaired_pct:.0f}%) ---")
        assert unpaired_pct < 30, (
            f"Too many unpaired segments: {unpaired_pct:.0f}%"
        )


# ---------------------------------------------------------------------------
# Room polygonization via center-lines
# ---------------------------------------------------------------------------


class TestCenterlineRoomDetection:
    """Validate that center-line polygonize produces rooms from the real drawing."""

    def test_polygonize_succeeds(
        self, first_floor_page: fitz.Page
    ) -> None:
        """RoomDetector should report polygonize_success=True."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        assert result.polygonize_success is True, (
            "polygonize should succeed with center-line extraction"
        )

    def test_at_least_4_rooms_detected(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Should detect at least 4 rooms (out of 9 expected)."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        print(f"\n--- Rooms detected: {result.room_count} ---")
        for r in result.rooms:
            sf = f"{r.area_sf:.1f} SF" if r.area_sf else "(no SF)"
            print(f"  Room {r.room_index}: area={sf}")

        assert result.room_count >= 4, (
            f"Expected at least 4 rooms, got {result.room_count}"
        )

    def test_total_area_close_to_512sf(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Total room area should be within ±20% of 512 SF."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        assert result.total_area_sf is not None
        error_pct = abs(result.total_area_sf - EXPECTED_GROSS_AREA_SF) / EXPECTED_GROSS_AREA_SF * 100
        print(
            f"\n--- Total area: {result.total_area_sf:.1f} SF "
            f"(expected ~{EXPECTED_GROSS_AREA_SF:.0f} SF, error {error_pct:.1f}%) ---"
        )
        assert 400 <= result.total_area_sf <= 620, (
            f"Total area {result.total_area_sf:.1f} SF outside "
            f"expected range 400-620 SF (±20% of 512)"
        )

    def test_no_room_exceeds_building_area(
        self, first_floor_page: fitz.Page
    ) -> None:
        """No single room should be larger than the total building footprint."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        for r in result.rooms:
            if r.area_sf is not None:
                assert r.area_sf < EXPECTED_GROSS_AREA_SF, (
                    f"Room {r.room_index} area {r.area_sf:.1f} SF "
                    f"exceeds building footprint {EXPECTED_GROSS_AREA_SF} SF"
                )

    def test_rooms_have_reasonable_sizes(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Each room should be between 5 and 300 SF (residential scale)."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        for r in result.rooms:
            if r.area_sf is not None:
                assert 5 <= r.area_sf <= 300, (
                    f"Room {r.room_index} area {r.area_sf:.1f} SF "
                    f"outside residential range 5-300 SF"
                )


# ---------------------------------------------------------------------------
# Room labeling from text blocks
# ---------------------------------------------------------------------------


class TestCenterlineRoomLabeling:
    """Validate room labeling on center-line-detected room polygons."""

    def test_at_least_3_rooms_labeled(
        self, first_floor_page: fitz.Page
    ) -> None:
        """At least 3 rooms should get labels from text blocks."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        scale_detector = ScaleDetector()
        text_blocks = scale_detector.extract_text_blocks(first_floor_page)
        labeled = detector.label_rooms(result, text_blocks)

        labeled_rooms = [r for r in labeled.rooms if r.label is not None]
        print(f"\n--- Labeled rooms: {len(labeled_rooms)}/{labeled.room_count} ---")
        for r in labeled.rooms:
            sf = f"{r.area_sf:.1f} SF" if r.area_sf else "(no SF)"
            print(f"  Room {r.room_index}: label={r.label!r} area={sf}")

        assert len(labeled_rooms) >= 3, (
            f"Expected at least 3 labeled rooms, got {len(labeled_rooms)}"
        )

    def test_known_room_labels_found(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Should find at least some of the known room labels."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        page_area_pts = data.page_width_pts * data.page_height_pts

        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        scale_detector = ScaleDetector()
        text_blocks = scale_detector.extract_text_blocks(first_floor_page)
        labeled = detector.label_rooms(result, text_blocks)

        found_labels = {r.label for r in labeled.rooms if r.label is not None}
        expected = {"LIVING ROOM", "KITCHEN", "DINING", "WC", "UTILITY", "COATS"}
        matched = found_labels & expected
        print(f"\n--- Found labels: {found_labels} ---")
        print(f"--- Expected match: {matched} ---")

        # Should match at least 3 of the expected labels
        assert len(matched) >= 3, (
            f"Expected at least 3 of {expected} in labels, "
            f"found {matched}"
        )


# ---------------------------------------------------------------------------
# MeasurementService with center-line rooms
# ---------------------------------------------------------------------------


class TestMeasurementServiceWithCenterlines:
    """Validate MeasurementService now uses center-line rooms."""

    def test_measurement_reports_polygonize_success(
        self, first_floor_page: fitz.Page
    ) -> None:
        """MeasurementService should report polygonize_success=True."""
        service = MeasurementService(
            extractor=VectorExtractor(),
            scale_detector=ScaleDetector(),
            wall_detector=WallDetector(),
        )
        result = service.measure(first_floor_page)

        print(f"\n--- polygonize_success: {result.polygonize_success} ---")
        print(f"--- room_count: {result.room_count} ---")
        print(f"--- gross_area_sf: {result.gross_area_sf} ---")

        assert result.polygonize_success is True, (
            "MeasurementService should use center-line polygonize"
        )

    def test_measurement_has_multiple_rooms(
        self, first_floor_page: fitz.Page
    ) -> None:
        """MeasurementService should return multiple rooms, not just 1 hull."""
        service = MeasurementService(
            extractor=VectorExtractor(),
            scale_detector=ScaleDetector(),
            wall_detector=WallDetector(),
        )
        result = service.measure(first_floor_page)

        assert result.rooms is not None
        assert result.room_count >= 4, (
            f"Expected at least 4 rooms, got {result.room_count}"
        )

    def test_measurement_area_in_range(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Gross area from room sum should be close to 512 SF."""
        service = MeasurementService(
            extractor=VectorExtractor(),
            scale_detector=ScaleDetector(),
            wall_detector=WallDetector(),
        )
        result = service.measure(first_floor_page)

        assert result.gross_area_sf is not None
        print(f"\n--- gross_area_sf: {result.gross_area_sf:.1f} ---")
        assert 400 <= result.gross_area_sf <= 620

    def test_rooms_have_labels(
        self, first_floor_page: fitz.Page
    ) -> None:
        """At least some rooms in MeasurementService output should be labeled."""
        service = MeasurementService(
            extractor=VectorExtractor(),
            scale_detector=ScaleDetector(),
            wall_detector=WallDetector(),
        )
        result = service.measure(first_floor_page)

        assert result.rooms is not None
        labeled = [r for r in result.rooms if r.label is not None]
        print(f"\n--- Labeled: {len(labeled)}/{len(result.rooms)} ---")
        for r in labeled:
            print(f"  {r.label}: {r.area_sf:.1f} SF" if r.area_sf else f"  {r.label}")
        assert len(labeled) >= 3


# ---------------------------------------------------------------------------
# Diagnostic report (always passes)
# ---------------------------------------------------------------------------


class TestCenterlineDiagnostic:
    """Print diagnostic info about center-line room detection."""

    def test_diagnostic_report(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Print detailed center-line room detection report."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        snapped = snap_endpoints(analysis.segments)
        cl_result = extract_centerlines(snapped)
        closed = close_gaps(cl_result.centerlines)
        extended = extend_to_intersections(closed)

        page_area_pts = data.page_width_pts * data.page_height_pts
        detector = RoomDetector()
        result = detector.detect_rooms(
            analysis.segments,
            scale_factor=EXPECTED_SCALE_FACTOR,
            page_area_pts=page_area_pts,
        )

        scale_detector = ScaleDetector()
        text_blocks = scale_detector.extract_text_blocks(first_floor_page)
        labeled = detector.label_rooms(result, text_blocks)

        print("\n=== CENTER-LINE ROOM DETECTION REPORT ===")
        print(f"  Wall segments: {len(analysis.segments)}")
        print(f"  Center-lines: {len(cl_result.centerlines)}")
        print(f"  Unpaired: {len(cl_result.unpaired)}")
        print(
            f"  Wall thickness: {cl_result.wall_thickness_pts:.1f} pts"
            if cl_result.wall_thickness_pts else "  Wall thickness: None"
        )
        print(f"  After gap close: {len(closed)}")
        print(f"  After extension: {len(extended)}")
        print(f"  Polygonize success: {result.polygonize_success}")
        print(f"  Room count: {result.room_count}")
        if result.total_area_sf is not None:
            error = (result.total_area_sf - EXPECTED_GROSS_AREA_SF) / EXPECTED_GROSS_AREA_SF * 100
            print(f"  Total area: {result.total_area_sf:.1f} SF (error: {error:+.1f}%)")
        print("  Rooms:")
        for r in labeled.rooms:
            sf = f"{r.area_sf:.1f} SF" if r.area_sf else "(no SF)"
            print(f"    [{r.room_index}] {r.label or '(unlabeled)':20s} {sf}")
        print("==========================================")
