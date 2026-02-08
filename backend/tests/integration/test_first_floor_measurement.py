"""US-355: Validate full MeasurementService pipeline on the real floor plan."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import (
    MeasurementConfidence,
    MeasurementService,
)
from cantena.geometry.scale import ScaleDetector
from cantena.geometry.walls import WallDetector

from .conftest import EXPECTED_GROSS_AREA_SF, EXPECTED_SCALE_FACTOR

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Shared service instances
# ---------------------------------------------------------------------------

_service = MeasurementService(
    extractor=VectorExtractor(),
    scale_detector=ScaleDetector(),
    wall_detector=WallDetector(),
)


class TestMeasurementPipeline:
    """Run MeasurementService.measure() on first-floor.pdf."""

    def test_measure_completes_without_error(
        self, first_floor_page: fitz.Page
    ) -> None:
        """measure() returns a PageMeasurements object."""
        result = _service.measure(first_floor_page)
        assert result is not None

    def test_scale_detected(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Scale should be detected (~48.0 ± 5)."""
        result = _service.measure(first_floor_page)
        assert result.scale is not None, "Scale was not detected"
        print(
            f"\n--- Detected scale factor: "
            f"{result.scale.scale_factor:.1f} "
            f"(expected ~{EXPECTED_SCALE_FACTOR}) ---"
        )
        assert abs(result.scale.scale_factor - EXPECTED_SCALE_FACTOR) <= 5, (
            f"Scale factor {result.scale.scale_factor:.1f} not within "
            f"±5 of expected {EXPECTED_SCALE_FACTOR}"
        )

    def test_gross_area_in_range(
        self, first_floor_page: fitz.Page
    ) -> None:
        """gross_area_sf should be between 350 and 800 SF (~512 SF)."""
        result = _service.measure(first_floor_page)
        assert result.gross_area_sf is not None, "gross_area_sf is None"
        print(
            f"\n--- Gross area: {result.gross_area_sf:.1f} SF "
            f"(expected ~{EXPECTED_GROSS_AREA_SF:.0f} SF) ---"
        )
        assert 350 <= result.gross_area_sf <= 800, (
            f"gross_area_sf {result.gross_area_sf:.1f} outside "
            f"expected range 350-800 SF"
        )

    def test_building_perimeter_in_range(
        self, first_floor_page: fitz.Page
    ) -> None:
        """building_perimeter_lf should be between 70 and 200 LF."""
        result = _service.measure(first_floor_page)
        assert result.building_perimeter_lf is not None, (
            "building_perimeter_lf is None"
        )
        print(
            f"\n--- Building perimeter: "
            f"{result.building_perimeter_lf:.1f} LF ---"
        )
        assert 70 <= result.building_perimeter_lf <= 200, (
            f"building_perimeter_lf {result.building_perimeter_lf:.1f} "
            f"outside expected range 70-200 LF"
        )

    def test_total_wall_length_in_range(
        self, first_floor_page: fitz.Page
    ) -> None:
        """total_wall_length_lf should be between 80 and 300 LF."""
        result = _service.measure(first_floor_page)
        assert result.total_wall_length_lf is not None, (
            "total_wall_length_lf is None"
        )
        print(
            f"\n--- Total wall length: "
            f"{result.total_wall_length_lf:.1f} LF ---"
        )
        assert 80 <= result.total_wall_length_lf <= 300, (
            f"total_wall_length_lf {result.total_wall_length_lf:.1f} "
            f"outside expected range 80-300 LF"
        )

    def test_confidence_at_least_medium(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Confidence should be at least MEDIUM on this clean drawing."""
        result = _service.measure(first_floor_page)
        acceptable = {MeasurementConfidence.HIGH, MeasurementConfidence.MEDIUM}
        print(f"\n--- Confidence: {result.confidence.value} ---")
        assert result.confidence in acceptable, (
            f"Expected at least MEDIUM confidence, "
            f"got {result.confidence.value}"
        )

    def test_diagnostic_report(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Print formatted report with % error vs 512 SF (always passes)."""
        result = _service.measure(first_floor_page)

        print("\n=== MEASUREMENT PIPELINE DIAGNOSTIC REPORT ===")
        if result.scale is not None:
            print(
                f"  Scale: {result.scale.notation} "
                f"(factor={result.scale.scale_factor:.1f})"
            )
        else:
            print("  Scale: not detected")

        if result.gross_area_sf is not None:
            error_pct = (
                (result.gross_area_sf - EXPECTED_GROSS_AREA_SF)
                / EXPECTED_GROSS_AREA_SF
                * 100
            )
            print(
                f"  Gross area: {result.gross_area_sf:.1f} SF "
                f"(expected {EXPECTED_GROSS_AREA_SF:.0f} SF, "
                f"error {error_pct:+.1f}%)"
            )
        else:
            print("  Gross area: not computed")

        if result.building_perimeter_lf is not None:
            print(
                f"  Perimeter: {result.building_perimeter_lf:.1f} LF"
            )
        else:
            print("  Perimeter: not computed")

        if result.total_wall_length_lf is not None:
            print(
                f"  Total wall length: "
                f"{result.total_wall_length_lf:.1f} LF"
            )
        else:
            print("  Total wall length: not computed")

        print(f"  Wall count: {result.wall_count}")
        print(f"  Confidence: {result.confidence.value}")
        print(f"  Vector paths: {len(result.raw_data.paths)}")
        print("================================================")


class TestMangledScaleResilience:
    """Pipeline should not crash when scale text is mangled."""

    def test_mangled_text_still_returns_result(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Inject garbled text via mocked text extraction.

        Pipeline should still return a result (possibly with degraded
        confidence) rather than crashing.
        """
        mangled_blocks: list[object] = []

        with patch.object(
            ScaleDetector,
            "extract_text_blocks",
            return_value=mangled_blocks,
        ):
            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            result = service.measure(first_floor_page)

        assert result is not None, "Pipeline crashed on mangled text"
        print(
            f"\n--- Mangled text result: "
            f"confidence={result.confidence.value}, "
            f"scale={'detected' if result.scale else 'None'}, "
            f"area={result.gross_area_sf} ---"
        )

    def test_mangled_text_degrades_confidence(
        self, first_floor_page: fitz.Page
    ) -> None:
        """With no valid text, confidence should degrade (not stay HIGH)."""
        mangled_blocks: list[object] = []

        with patch.object(
            ScaleDetector,
            "extract_text_blocks",
            return_value=mangled_blocks,
        ):
            service = MeasurementService(
                extractor=VectorExtractor(),
                scale_detector=ScaleDetector(),
                wall_detector=WallDetector(),
            )
            result = service.measure(first_floor_page)

        # With no text blocks, detect_from_text returns None and
        # detect_from_dimensions also returns None (no text blocks to
        # match against), so pipeline falls back to estimated scale
        # with LOW confidence.
        print(
            f"\n--- Mangled text confidence: "
            f"{result.confidence.value} ---"
        )
        assert result.confidence != MeasurementConfidence.HIGH, (
            "Confidence should degrade when scale text is mangled"
        )
