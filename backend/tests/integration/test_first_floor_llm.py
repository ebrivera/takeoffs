"""US-376: Real API integration tests — enhanced pipeline on first-floor.pdf.

Runs the full geometry + room detection + LLM interpretation pipeline using
real Anthropic API calls.  Skipped when ANTHROPIC_API_KEY is not set.

Rate-limit (429) responses are handled with ``pytest.skip`` rather than fail.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import (
    MeasurementService,
    pts_to_real_sf,
)
from cantena.geometry.scale import ScaleDetector
from cantena.geometry.scale_verify import ScaleVerifier
from cantena.geometry.walls import WallDetector
from cantena.services.llm_geometry_interpreter import LlmGeometryInterpreter

from .conftest import EXPECTED_GROSS_AREA_SF, EXPECTED_SCALE_FACTOR

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]

    from cantena.geometry.measurement import PageMeasurements

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


def _build_service(api_key: str) -> MeasurementService:
    """Build a MeasurementService with LLM interpreter and scale verifier."""
    return MeasurementService(
        extractor=VectorExtractor(),
        scale_detector=ScaleDetector(),
        wall_detector=WallDetector(),
        llm_interpreter=LlmGeometryInterpreter(api_key=api_key),
        scale_verifier=ScaleVerifier(api_key=api_key),
    )


def _measure_with_rate_limit_guard(
    service: MeasurementService,
    page: fitz.Page,
) -> PageMeasurements:
    """Run measure() and skip on 429 rate-limit errors."""
    try:
        return service.measure(page)
    except Exception as exc:
        if "429" in str(exc):
            pytest.skip("Rate limited (429)")
        raise


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPORT_DIR = Path(__file__).resolve().parents[3] / "test_results"
_ENHANCED_REPORT_PATH = _REPORT_DIR / "first-floor-enhanced-report.md"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLlmRoomInterpretation:
    """LLM interprets room data from a real floor-plan PDF."""

    def test_llm_room_interpretation(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """LLM identifies building type, structural system, rooms, and special conditions."""
        api_key = _get_api_key()
        service = _build_service(api_key)
        result = _measure_with_rate_limit_guard(service, first_floor_page)

        # Scale verification should be active
        assert result.scale_verification is not None
        assert result.scale_verification.verification_source != "UNVERIFIED", (
            f"Expected verified scale, got UNVERIFIED: "
            f"{result.scale_verification.warnings}"
        )

        # LLM interpretation must be non-default
        interp = result.llm_interpretation
        assert interp is not None, "LLM interpretation is None"
        assert interp.building_type != "UNKNOWN", (
            f"Expected non-UNKNOWN building_type, got {interp.building_type}"
        )

        # Building type should be residential
        assert "RESIDENTIAL" in interp.building_type.upper(), (
            f"Expected RESIDENTIAL, got {interp.building_type}"
        )

        # Structural system should mention wood frame or similar
        structural_lower = interp.structural_system.lower()
        assert any(
            kw in structural_lower
            for kw in ("wood", "frame", "timber", "stick")
        ), (
            f"Expected wood frame structural system, got: "
            f"{interp.structural_system}"
        )

        # At least 3 rooms should have confirmed labels
        assert len(interp.rooms) >= 3, (
            f"Expected >=3 confirmed rooms, got {len(interp.rooms)}"
        )

        # Special conditions should mention at least one notable feature
        conditions_lower = " ".join(interp.special_conditions).lower()
        notable_features = (
            "woodstove", "chimney", "hardwood", "brick",
            "fireplace", "stove", "wood stove",
        )
        assert any(feat in conditions_lower for feat in notable_features), (
            f"Expected at least one of {notable_features} in special_conditions, "
            f"got: {interp.special_conditions}"
        )

        print("\n=== LLM ROOM INTERPRETATION ===")
        print(f"  Building type: {interp.building_type}")
        print(f"  Structural system: {interp.structural_system}")
        print(f"  Rooms confirmed: {len(interp.rooms)}")
        for room in interp.rooms:
            print(
                f"    [{room.room_index}] {room.confirmed_label} "
                f"({room.room_type_enum}) — {room.notes}"
            )
        print(f"  Special conditions: {interp.special_conditions}")
        print(f"  Measurement flags: {interp.measurement_flags}")
        print(f"  Confidence notes: {interp.confidence_notes}")
        print("================================")


class TestLlmWithImage:
    """LLM interpretation with a rendered page image (vision input)."""

    def test_llm_with_image(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Send rendered page image alongside geometry data; assert response returned."""
        api_key = _get_api_key()
        interpreter = LlmGeometryInterpreter(api_key=api_key)

        # Render page to a temp PNG
        import fitz as fitz_mod  # type: ignore[import-untyped]

        mat = fitz_mod.Matrix(2.0, 2.0)  # 144 DPI
        pix = first_floor_page.get_pixmap(matrix=mat)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pix.save(tmp.name)
            image_path = Path(tmp.name)

        try:
            # Build geometry summary from real measurement data
            service = _build_service(api_key)
            result = _measure_with_rate_limit_guard(service, first_floor_page)

            # Build a GeometrySummary from the measurement result
            from cantena.services.llm_geometry_interpreter import (
                GeometrySummary,
                RoomSummary,
            )

            room_summaries = [
                RoomSummary(
                    room_index=r.room_index,
                    label=r.label,
                    area_sf=r.area_sf,
                    perimeter_lf=r.perimeter_lf,
                )
                for r in (result.rooms or [])
            ]
            summary = GeometrySummary(
                scale_notation=(
                    result.scale.notation if result.scale else None
                ),
                scale_factor=(
                    result.scale.scale_factor if result.scale else None
                ),
                total_area_sf=result.gross_area_sf,
                rooms=room_summaries,
                all_text_blocks=[],
                wall_count=result.wall_count,
                measurement_confidence=result.confidence.value,
            )

            try:
                interp_with_image = interpreter.interpret(
                    summary, page_image_path=image_path
                )
            except Exception as exc:
                if "429" in str(exc):
                    pytest.skip("Rate limited (429)")
                raise

            assert interp_with_image is not None
            assert interp_with_image.building_type != "UNKNOWN", (
                "Vision-assisted interpretation returned UNKNOWN building_type"
            )

            print("\n=== LLM WITH IMAGE ===")
            print(f"  Building type: {interp_with_image.building_type}")
            print(f"  Structural system: {interp_with_image.structural_system}")
            print(f"  Rooms: {len(interp_with_image.rooms)}")
            print(f"  Special conditions: {interp_with_image.special_conditions}")
            print("======================")

        finally:
            image_path.unlink(missing_ok=True)


class TestFullPipelineAccuracy:
    """End-to-end pipeline accuracy with LLM enrichment."""

    def test_full_pipeline_accuracy(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Total area in [400, 600] SF, >=4 named rooms, scale ~48, LLM residential."""
        api_key = _get_api_key()
        service = _build_service(api_key)
        result = _measure_with_rate_limit_guard(service, first_floor_page)

        # Scale factor ~48 ± 5
        assert result.scale is not None, "Scale not detected"
        assert abs(result.scale.scale_factor - EXPECTED_SCALE_FACTOR) <= 5, (
            f"Scale factor {result.scale.scale_factor:.1f} not within "
            f"±5 of expected {EXPECTED_SCALE_FACTOR}"
        )

        # Total area from polygonized rooms in [400, 600] SF
        assert result.gross_area_sf is not None, "gross_area_sf is None"
        assert 400 <= result.gross_area_sf <= 600, (
            f"gross_area_sf {result.gross_area_sf:.1f} outside [400, 600] SF range"
        )

        # At least 4 named rooms
        named_rooms = [
            r for r in (result.rooms or []) if r.label is not None
        ]
        assert len(named_rooms) >= 4, (
            f"Expected >=4 named rooms, got {len(named_rooms)}: "
            f"{[r.label for r in named_rooms]}"
        )

        # LLM identifies residential
        interp = result.llm_interpretation
        assert interp is not None, "LLM interpretation is None"
        assert "RESIDENTIAL" in interp.building_type.upper(), (
            f"Expected RESIDENTIAL, got {interp.building_type}"
        )

        error_pct = (
            (result.gross_area_sf - EXPECTED_GROSS_AREA_SF)
            / EXPECTED_GROSS_AREA_SF
            * 100
        )
        print("\n=== FULL PIPELINE ACCURACY ===")
        print(
            f"  Scale: {result.scale.notation} "
            f"(factor={result.scale.scale_factor:.1f})"
        )
        print(
            f"  Total area: {result.gross_area_sf:.1f} SF "
            f"(expected ~{EXPECTED_GROSS_AREA_SF:.0f} SF, "
            f"error {error_pct:+.1f}%)"
        )
        print(f"  Polygonize success: {result.polygonize_success}")
        print(f"  Room count: {result.room_count}")
        print(f"  Named rooms: {[r.label for r in named_rooms]}")
        print(f"  Building type: {interp.building_type}")
        print(f"  Confidence: {result.confidence.value}")
        print("==============================")


class TestRoomAreaImprovementOverConvexHull:
    """Polygonize total should be closer to 512 SF than convex hull total."""

    def test_room_area_improvement_over_convex_hull(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Assert polygonize total is closer to expected than convex hull."""
        api_key = _get_api_key()
        service = _build_service(api_key)
        result = _measure_with_rate_limit_guard(service, first_floor_page)

        assert result.polygonize_success, "Polygonize did not succeed"
        assert result.rooms is not None and len(result.rooms) > 0, (
            "No rooms detected"
        )
        assert result.gross_area_sf is not None, "gross_area_sf is None"
        assert result.scale is not None, "Scale not detected"

        polygonize_area = result.gross_area_sf

        # Compute convex hull area for comparison
        wall_detector = WallDetector()
        extractor = VectorExtractor()
        data = extractor.extract(first_floor_page)
        wall_analysis = wall_detector.detect(data)
        hull_area_pts = wall_detector.compute_enclosed_area_pts(
            wall_analysis.segments
        )
        assert hull_area_pts is not None, "Convex hull area is None"
        hull_area_sf = pts_to_real_sf(hull_area_pts, result.scale)

        poly_error = abs(polygonize_area - EXPECTED_GROSS_AREA_SF)
        hull_error = abs(hull_area_sf - EXPECTED_GROSS_AREA_SF)

        print("\n=== AREA COMPARISON ===")
        print(f"  Expected: {EXPECTED_GROSS_AREA_SF:.0f} SF")
        print(
            f"  Polygonize: {polygonize_area:.1f} SF "
            f"(error: {poly_error:.1f} SF)"
        )
        print(
            f"  Convex hull: {hull_area_sf:.1f} SF "
            f"(error: {hull_error:.1f} SF)"
        )
        improvement = hull_error - poly_error
        print(f"  Improvement: {improvement:.1f} SF closer")
        print("=======================")

        assert poly_error <= hull_error, (
            f"Polygonize area ({polygonize_area:.1f} SF, "
            f"error={poly_error:.1f}) is NOT closer to "
            f"{EXPECTED_GROSS_AREA_SF:.0f} SF than convex hull "
            f"({hull_area_sf:.1f} SF, error={hull_error:.1f})"
        )


class TestMeasurementReportWithRooms:
    """Generate enhanced report with per-room breakdown + LLM summary."""

    def test_measurement_report_with_rooms(
        self,
        first_floor_page: fitz.Page,
    ) -> None:
        """Write test_results/first-floor-enhanced-report.md."""
        api_key = _get_api_key()
        service = _build_service(api_key)
        result = _measure_with_rate_limit_guard(service, first_floor_page)

        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = []

        lines.append(
            "# Enhanced Geometry Report: first-floor.pdf"
        )
        lines.append("")
        lines.append(f"Generated: {now}")
        lines.append("")

        # --- Summary ---
        lines.append("## Pipeline Summary")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        scale_str = (
            f"{result.scale.notation} "
            f"(factor={result.scale.scale_factor:.1f})"
            if result.scale
            else "Not detected"
        )
        lines.append(f"| Scale | {scale_str} |")
        lines.append(
            f"| Total area | "
            f"{result.gross_area_sf:.1f} SF |"
            if result.gross_area_sf is not None
            else "| Total area | N/A |"
        )
        lines.append(f"| Polygonize success | {result.polygonize_success} |")
        lines.append(f"| Room count | {result.room_count} |")
        lines.append(f"| Wall count | {result.wall_count} |")
        lines.append(f"| Confidence | {result.confidence.value} |")

        # Scale verification
        if result.scale_verification is not None:
            lines.append(
                f"| Scale verification | "
                f"{result.scale_verification.verification_source} |"
            )
            if result.scale_verification.warnings:
                lines.append(
                    f"| Scale warnings | "
                    f"{'; '.join(result.scale_verification.warnings)} |"
                )
        lines.append("")

        # --- Per-Room Breakdown ---
        lines.append("## Room Breakdown")
        lines.append("")
        if result.rooms:
            lines.append(
                "| # | Label | Area (SF) | Perimeter (LF) |"
            )
            lines.append(
                "|---|-------|-----------|----------------|"
            )
            for room in result.rooms:
                label = room.label or "*(unlabeled)*"
                area = (
                    f"{room.area_sf:.1f}" if room.area_sf is not None else "N/A"
                )
                perim = (
                    f"{room.perimeter_lf:.1f}"
                    if room.perimeter_lf is not None
                    else "N/A"
                )
                lines.append(
                    f"| {room.room_index} | {label} | {area} | {perim} |"
                )
            lines.append("")
        else:
            lines.append("*No rooms detected.*")
            lines.append("")

        # --- LLM Interpretation ---
        lines.append("## LLM Interpretation")
        lines.append("")
        interp = result.llm_interpretation
        if interp is not None and interp.building_type != "UNKNOWN":
            lines.append(f"**Building type:** {interp.building_type}")
            lines.append(
                f"**Structural system:** {interp.structural_system}"
            )
            lines.append("")

            if interp.rooms:
                lines.append("### Room Analysis")
                lines.append("")
                lines.append(
                    "| # | Confirmed Label | Type | Notes |"
                )
                lines.append(
                    "|---|-----------------|------|-------|"
                )
                for room in interp.rooms:
                    lines.append(
                        f"| {room.room_index} | {room.confirmed_label} "
                        f"| {room.room_type_enum} | {room.notes} |"
                    )
                lines.append("")

            if interp.special_conditions:
                lines.append("### Special Conditions")
                lines.append("")
                for cond in interp.special_conditions:
                    lines.append(f"- {cond}")
                lines.append("")

            if interp.measurement_flags:
                lines.append("### Measurement Flags")
                lines.append("")
                for flag in interp.measurement_flags:
                    lines.append(f"- {flag}")
                lines.append("")

            if interp.confidence_notes:
                lines.append(
                    f"**Confidence notes:** {interp.confidence_notes}"
                )
                lines.append("")
        else:
            lines.append("*LLM interpretation unavailable.*")
            lines.append("")

        # --- Accuracy vs Expected ---
        lines.append("## Accuracy vs Expected")
        lines.append("")
        lines.append("| Metric | Expected | Actual | Error |")
        lines.append("|--------|----------|--------|-------|")

        if result.scale is not None:
            scale_err = (
                (result.scale.scale_factor - EXPECTED_SCALE_FACTOR)
                / EXPECTED_SCALE_FACTOR
                * 100
            )
            lines.append(
                f"| Scale factor | {EXPECTED_SCALE_FACTOR:.0f} "
                f"| {result.scale.scale_factor:.1f} "
                f"| {scale_err:+.1f}% |"
            )

        if result.gross_area_sf is not None:
            area_err = (
                (result.gross_area_sf - EXPECTED_GROSS_AREA_SF)
                / EXPECTED_GROSS_AREA_SF
                * 100
            )
            lines.append(
                f"| Total area | {EXPECTED_GROSS_AREA_SF:.0f} SF "
                f"| {result.gross_area_sf:.1f} SF "
                f"| {area_err:+.1f}% |"
            )

        named_rooms = [
            r for r in (result.rooms or []) if r.label is not None
        ]
        lines.append(
            f"| Named rooms | >=4 | {len(named_rooms)} | - |"
        )
        lines.append("")

        # Write report
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _ENHANCED_REPORT_PATH.write_text("\n".join(lines) + "\n")

        print(f"\n--- Enhanced report written to {_ENHANCED_REPORT_PATH} ---")

        assert _ENHANCED_REPORT_PATH.exists(), (
            "Enhanced report file was not created"
        )
