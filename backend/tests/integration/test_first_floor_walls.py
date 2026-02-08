"""US-354: Validate wall detection and area computation on the real floor plan."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import pts_to_real_lf, pts_to_real_sf
from cantena.geometry.scale import ScaleResult
from cantena.geometry.walls import Orientation, WallDetector

from .conftest import EXPECTED_GROSS_AREA_SF, EXPECTED_SCALE_FACTOR

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_extractor = VectorExtractor()
_wall_detector = WallDetector()

# Build a ScaleResult for the known 1/4"=1'-0" scale.
_SCALE = ScaleResult(
    drawing_units=0.25,
    real_units=12.0,
    scale_factor=EXPECTED_SCALE_FACTOR,
    notation='1/4"=1\'-0"',
    confidence=None,  # type: ignore[arg-type]
)


class TestWallDetection:
    """Verify WallDetector against the real first-floor.pdf."""

    def test_at_least_8_wall_segments(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        print(f"\n--- Wall detection: {len(analysis.segments)} segments ---")
        assert len(analysis.segments) >= 8, (
            f"Expected at least 8 wall segments, got {len(analysis.segments)}"
        )

    def test_at_least_3_horizontal_segments(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        h_count = sum(
            1
            for seg in analysis.segments
            if seg.orientation == Orientation.HORIZONTAL
        )
        print(f"\n--- Horizontal wall segments: {h_count} ---")
        assert h_count >= 3, (
            f"Expected at least 3 HORIZONTAL segments, got {h_count}"
        )

    def test_at_least_3_vertical_segments(
        self, first_floor_page: fitz.Page
    ) -> None:
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        v_count = sum(
            1
            for seg in analysis.segments
            if seg.orientation == Orientation.VERTICAL
        )
        print(f"\n--- Vertical wall segments: {v_count} ---")
        assert v_count >= 3, (
            f"Expected at least 3 VERTICAL segments, got {v_count}"
        )

    def test_total_wall_length_in_range(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Total wall length (scaled) should be between 80 and 250 LF."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)
        total_lf = pts_to_real_lf(
            analysis.total_wall_length_pts, _SCALE
        )
        print(f"\n--- Total wall length: {total_lf:.1f} LF ---")

        if total_lf < 80 or total_lf > 250:
            # Diagnostic: print all segments
            print("  Wall segments (outside 80-250 LF range):")
            for i, seg in enumerate(analysis.segments):
                seg_lf = pts_to_real_lf(seg.length_pts, _SCALE)
                print(
                    f"    [{i}] {seg.orientation.value} "
                    f"{seg_lf:.1f} LF "
                    f"({seg.start.x:.0f},{seg.start.y:.0f}) -> "
                    f"({seg.end.x:.0f},{seg.end.y:.0f})"
                )

        assert 80 <= total_lf <= 250, (
            f"Total wall length {total_lf:.1f} LF outside expected "
            f"range 80-250 LF"
        )

    def test_outer_boundary_area_approximately_512sf(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Outer boundary polygon area should be ~512 SF (±25%)."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)

        area_pts = _wall_detector.compute_enclosed_area_pts(
            analysis.segments
        )
        assert area_pts is not None, "No enclosed area could be computed"

        area_sf = pts_to_real_sf(area_pts, _SCALE)
        error_pct = (
            (area_sf - EXPECTED_GROSS_AREA_SF)
            / EXPECTED_GROSS_AREA_SF
            * 100
        )
        print(
            f"\n--- Computed area: {area_sf:.1f} SF "
            f"(expected ~{EXPECTED_GROSS_AREA_SF:.0f} SF, "
            f"error {error_pct:+.1f}%) ---"
        )

        assert 380 <= area_sf <= 700, (
            f"Computed area {area_sf:.1f} SF outside expected "
            f"range 380-700 SF (±25% of 512 SF)"
        )

    def test_wall_thickness_if_detected(
        self, first_floor_page: fitz.Page
    ) -> None:
        """If wall thickness is detected, it should be 3-12 inches."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)

        if analysis.detected_wall_thickness_pts is None:
            print("\n--- Wall thickness: not detected ---")
            return

        # Convert pts to real inches: pts * (1/72) * scale_factor
        thickness_in = (
            analysis.detected_wall_thickness_pts
            / 72.0
            * EXPECTED_SCALE_FACTOR
        )
        print(
            f"\n--- Wall thickness: {thickness_in:.1f} inches "
            f"({analysis.detected_wall_thickness_pts:.2f} pts) ---"
        )
        assert 3 <= thickness_in <= 12, (
            f"Wall thickness {thickness_in:.1f} inches outside "
            f"expected range 3-12 inches"
        )

    def test_diagnostic_summary(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Print a comprehensive wall detection summary (always passes)."""
        data = _extractor.extract(first_floor_page)
        analysis = _wall_detector.detect(data)

        h_segs = [
            seg
            for seg in analysis.segments
            if seg.orientation == Orientation.HORIZONTAL
        ]
        v_segs = [
            seg
            for seg in analysis.segments
            if seg.orientation == Orientation.VERTICAL
        ]

        h_avg_lf = (
            sum(pts_to_real_lf(seg.length_pts, _SCALE) for seg in h_segs)
            / len(h_segs)
            if h_segs
            else 0.0
        )
        v_avg_lf = (
            sum(pts_to_real_lf(seg.length_pts, _SCALE) for seg in v_segs)
            / len(v_segs)
            if v_segs
            else 0.0
        )

        thickness_str = "not detected"
        if analysis.detected_wall_thickness_pts is not None:
            thickness_in = (
                analysis.detected_wall_thickness_pts
                / 72.0
                * EXPECTED_SCALE_FACTOR
            )
            thickness_str = f"~{thickness_in:.1f} inches"

        print("\n=== WALL DETECTION DIAGNOSTIC SUMMARY ===")
        print(f"  Total walls: {len(analysis.segments)}")
        print(
            f"  Horizontal: {len(h_segs)} (avg {h_avg_lf:.1f} ft)"
        )
        print(f"  Vertical: {len(v_segs)} (avg {v_avg_lf:.1f} ft)")
        print(f"  Thickness: {thickness_str}")

        total_lf = pts_to_real_lf(
            analysis.total_wall_length_pts, _SCALE
        )
        print(f"  Total wall length: {total_lf:.1f} LF")

        area_pts = _wall_detector.compute_enclosed_area_pts(
            analysis.segments
        )
        if area_pts is not None:
            area_sf = pts_to_real_sf(area_pts, _SCALE)
            print(f"  Enclosed area: {area_sf:.1f} SF")
        else:
            print("  Enclosed area: could not compute")

        if analysis.outer_boundary is not None:
            print(
                f"  Outer boundary: "
                f"{len(analysis.outer_boundary)} vertices"
            )
        else:
            print("  Outer boundary: not detected")
        print("==========================================")
