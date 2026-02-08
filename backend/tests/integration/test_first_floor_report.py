"""US-357: Geometry accuracy report and known-limitations documentation."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cantena.geometry.extractor import VectorExtractor
from cantena.geometry.measurement import MeasurementService
from cantena.geometry.scale import ScaleDetector, TextBlock
from cantena.geometry.walls import WallDetector

from .conftest import (
    EXPECTED_GROSS_AREA_SF,
    EXPECTED_ROOM_COUNT,
    EXPECTED_SCALE_FACTOR,
)

if TYPE_CHECKING:
    import fitz  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPORT_DIR = Path(__file__).resolve().parents[3] / "test_results"
_REPORT_PATH = _REPORT_DIR / "first-floor-geometry-report.md"

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_extractor = VectorExtractor()
_scale_detector = ScaleDetector()
_wall_detector = WallDetector()
_service = MeasurementService(
    extractor=_extractor,
    scale_detector=_scale_detector,
    wall_detector=_wall_detector,
)

# Room labels we expect to find (same list as US-356)
_EXPECTED_ROOM_LABELS: list[str] = [
    "LIVING ROOM",
    "KITCHEN",
    "DINING",
    "FRONT PORCH",
    "BACK PORCH",
    "UTILITY",
    "WC",
    "COATS",
    "LAUNDRY",
]

# Dimension pattern (same as US-356)
_DIMENSION_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*['\u2019\u2032]"
    r"(?:\s*-?\s*\d+\s*(?:[\"'\u201d\u2033]|''))?"
)

# Title block fields
_TITLE_BLOCK_FIELDS: list[str] = [
    "SCALE",
    "1/4",
    "A1.2",
    "1ST FLOOR",
    "AMERICAN FARMHOUSE",
]


def _normalize_block_text(text: str) -> str:
    """Collapse newlines and extra spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _collapse_spaced_text(text: str) -> str:
    """Collapse spaced-out title block text."""
    collapsed = re.sub(r"\b(\w) (?=\w\b)", r"\1", text)
    return re.sub(r"\s+", " ", collapsed)


def _find_room_labels(
    blocks: list[TextBlock],
) -> tuple[list[str], list[str]]:
    """Return (found, missed) room labels."""
    found: list[str] = []
    missed: list[str] = []
    for label in _EXPECTED_ROOM_LABELS:
        label_lower = label.lower()
        matched = any(
            label_lower in _normalize_block_text(blk.text).lower()
            for blk in blocks
        )
        if matched:
            found.append(label)
        else:
            missed.append(label)
    return found, missed


def _count_dimension_blocks(blocks: list[TextBlock]) -> int:
    """Count text blocks matching dimension patterns."""
    return sum(
        1
        for blk in blocks
        if _DIMENSION_PATTERN.search(blk.text.strip())
    )


def _find_title_block_fields(
    blocks: list[TextBlock],
    page_w: float,
    page_h: float,
) -> tuple[list[str], list[str]]:
    """Find title block fields in border area (right 15% or bottom 15%)."""
    border_blocks = [
        blk
        for blk in blocks
        if blk.position.x > page_w * 0.85
        or blk.position.y > page_h * 0.85
    ]
    raw_text = " ".join(blk.text for blk in border_blocks)
    border_text = _collapse_spaced_text(raw_text).lower()

    found: list[str] = []
    missed: list[str] = []
    for field_text in _TITLE_BLOCK_FIELDS:
        if field_text.lower() in border_text:
            found.append(field_text)
        else:
            missed.append(field_text)
    return found, missed


def _scale_detection_path(
    page: fitz.Page,
) -> str:
    """Determine which scale detection path was used."""
    text_blocks = _scale_detector.extract_text_blocks(page)
    page_text = "\n".join(tb.text for tb in text_blocks)

    # Try text-based first
    result = _scale_detector.detect_from_text(page_text)
    if result is not None:
        return (
            f"Deterministic text normalization/parsing "
            f"(notation: {result.notation!r}, "
            f"confidence: {result.confidence.value})"
        )

    # Try dimension calibration
    data = _extractor.extract(page)
    result = _scale_detector.detect_from_dimensions(
        data.paths, text_blocks
    )
    if result is not None:
        return (
            f"Dimension calibration fallback "
            f"(notation: {result.notation!r}, "
            f"confidence: {result.confidence.value})"
        )

    return "No scale detected — used estimated default (1/8\"=1'-0\")"


# ---------------------------------------------------------------------------
# Report generation test (always passes — diagnostic tool)
# ---------------------------------------------------------------------------


class TestReportGeneration:
    """Generate the comprehensive accuracy report."""

    def test_generate_report(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Run full pipeline and write test_results/first-floor-geometry-report.md."""
        # Run pipeline
        result = _service.measure(first_floor_page)
        data = result.raw_data
        stats = _extractor.get_stats(data)
        text_blocks = _scale_detector.extract_text_blocks(
            first_floor_page
        )

        # Wall analysis (for additional details)
        wall_analysis = _wall_detector.detect(data)

        # Room labels
        found_labels, missed_labels = _find_room_labels(text_blocks)

        # Dimension blocks
        dim_count = _count_dimension_blocks(text_blocks)

        # Title block fields
        page_rect = first_floor_page.rect
        page_w: float = page_rect.width
        page_h: float = page_rect.height
        found_tb, missed_tb = _find_title_block_fields(
            text_blocks, page_w, page_h
        )

        # Scale detection path
        scale_path = _scale_detection_path(first_floor_page)

        # Compute area error
        area_error_pct: float | None = None
        if result.gross_area_sf is not None:
            area_error_pct = (
                (result.gross_area_sf - EXPECTED_GROSS_AREA_SF)
                / EXPECTED_GROSS_AREA_SF
                * 100
            )

        # Count H/V walls
        h_count = sum(
            1
            for seg in wall_analysis.segments
            if seg.orientation.value == "horizontal"
        )
        v_count = sum(
            1
            for seg in wall_analysis.segments
            if seg.orientation.value == "vertical"
        )

        # Perimeter expected (32+16)*2 = 96 LF
        expected_perimeter_lf = (32.0 + 16.0) * 2
        perimeter_error_pct: float | None = None
        if result.building_perimeter_lf is not None:
            perimeter_error_pct = (
                (
                    result.building_perimeter_lf
                    - expected_perimeter_lf
                )
                / expected_perimeter_lf
                * 100
            )

        # Confidence per-component
        scale_conf = (
            result.scale.confidence.value
            if result.scale
            else "none"
        )

        # Build report
        now = datetime.now(tz=UTC).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines: list[str] = []
        lines.append(
            "# Geometry Engine Accuracy Report: first-floor.pdf"
        )
        lines.append("")
        lines.append(f"Generated: {now}")
        lines.append("")

        # --- Drawing Info ---
        lines.append("## Drawing Info")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append("| Filename | first-floor.pdf |")
        lines.append(
            f"| Page size | {page_w:.0f} x {page_h:.0f} pts "
            f"({page_w / 72:.1f} x {page_h / 72:.1f} in) |"
        )
        scale_str = (
            f"{result.scale.notation} "
            f"(factor={result.scale.scale_factor:.1f})"
            if result.scale
            else "Not detected"
        )
        lines.append(f"| Scale detected | {scale_str} |")
        lines.append(
            f"| Vector path count | {stats.path_count} |"
        )
        lines.append(
            f"| Line/Rect/Curve/Poly | "
            f"{stats.line_count} / {stats.rect_count} / "
            f"{stats.curve_count} / {stats.polyline_count} |"
        )
        lines.append(
            f"| Text blocks | {len(text_blocks)} |"
        )
        lines.append("")

        # --- Measurement Results ---
        lines.append("## Measurement Results")
        lines.append("")
        lines.append("| Metric | Expected | Actual | Error |")
        lines.append("|--------|----------|--------|-------|")

        area_actual = (
            f"{result.gross_area_sf:.1f} SF"
            if result.gross_area_sf is not None
            else "N/A"
        )
        area_err = (
            f"{area_error_pct:+.1f}%"
            if area_error_pct is not None
            else "N/A"
        )
        lines.append(
            f"| Gross area | {EXPECTED_GROSS_AREA_SF:.0f} SF "
            f"| {area_actual} | {area_err} |"
        )

        perim_actual = (
            f"{result.building_perimeter_lf:.1f} LF"
            if result.building_perimeter_lf is not None
            else "N/A"
        )
        perim_err = (
            f"{perimeter_error_pct:+.1f}%"
            if perimeter_error_pct is not None
            else "N/A"
        )
        lines.append(
            f"| Perimeter | ~{expected_perimeter_lf:.0f} LF "
            f"| {perim_actual} | {perim_err} |"
        )

        lines.append(
            f"| Wall count | - | {len(wall_analysis.segments)} "
            f"({h_count}H, {v_count}V) | - |"
        )

        wall_len_str = (
            f"{result.total_wall_length_lf:.1f} LF"
            if result.total_wall_length_lf is not None
            else "N/A"
        )
        lines.append(
            f"| Total wall length | - | {wall_len_str} | - |"
        )

        thickness_str: str
        if (
            wall_analysis.detected_wall_thickness_pts is not None
            and result.scale is not None
        ):
            real_in = (
                wall_analysis.detected_wall_thickness_pts
                / 72
                * result.scale.scale_factor
            )
            thickness_str = (
                f"{wall_analysis.detected_wall_thickness_pts:.1f}"
                f" pts (~{real_in:.1f}\" real)"
            )
        else:
            thickness_str = "Not detected"
        lines.append(
            f"| Wall thickness | - | {thickness_str} | - |"
        )
        lines.append("")

        # --- Text Extraction ---
        lines.append("## Text Extraction")
        lines.append("")
        lines.append(
            f"**Room labels found** ({len(found_labels)}/{len(_EXPECTED_ROOM_LABELS)}): "
            f"{', '.join(found_labels)}"
        )
        if missed_labels:
            lines.append(
                f"**Room labels missed**: {', '.join(missed_labels)}"
            )
        lines.append(f"**Dimension strings found**: {dim_count}")
        lines.append(
            f"**Title block fields found** ({len(found_tb)}/{len(_TITLE_BLOCK_FIELDS)}): "
            f"{', '.join(found_tb)}"
        )
        if missed_tb:
            lines.append(
                f"**Title block fields missed**: {', '.join(missed_tb)}"
            )
        lines.append("")

        # --- Confidence Assessment ---
        lines.append("## Confidence Assessment")
        lines.append("")
        lines.append("| Component | Confidence |")
        lines.append("|-----------|------------|")
        lines.append(
            f"| Overall | **{result.confidence.value.upper()}** |"
        )
        lines.append(f"| Scale detection | {scale_conf} |")
        wall_conf = (
            "high"
            if len(wall_analysis.segments) >= 8
            and wall_analysis.outer_boundary is not None
            else "medium"
            if len(wall_analysis.segments) >= 4
            else "low"
        )
        lines.append(f"| Wall detection | {wall_conf} |")
        text_conf = (
            "high"
            if len(found_labels) >= 7
            else "medium"
            if len(found_labels) >= 4
            else "low"
        )
        lines.append(f"| Text extraction | {text_conf} |")
        lines.append("")

        # --- Scale Detection Path ---
        lines.append("## Scale Detection Path")
        lines.append("")
        lines.append(f"Method used: {scale_path}")
        lines.append("")

        # --- Known Limitations ---
        lines.append("## Known Limitations")
        lines.append("")
        lines.append(
            "| # | Limitation | Severity | Suggested Fix |"
        )
        lines.append(
            "|----|-----------|----------|---------------|"
        )
        lines.append(
            "| 1 | Convex hull overestimates area for L-shaped "
            "or irregular footprints | **moderate** | Use concave "
            "hull or alpha-shape from wall endpoints |"
        )
        lines.append(
            "| 2 | Porch area included in gross area "
            "(no interior/exterior wall distinction) | **moderate** "
            "| Classify wall segments by line weight or "
            "room-label proximity |"
        )
        lines.append(
            "| 3 | Dimension calibration fallback can pick "
            "annotation leader lines instead of dimension "
            "lines, yielding wrong scale | **minor** | Require "
            "minimum line length for calibration candidates |"
        )
        lines.append(
            "| 4 | No room-level area breakdown — only gross "
            "footprint computed | **moderate** | Implement "
            "room segmentation using flood-fill on wall graph |"
        )
        lines.append(
            "| 5 | Wall thickness detection depends on parallel "
            "pair analysis — fails on single-line wall "
            "representations | **minor** | Fall back to "
            "stroke-width heuristic for single-line walls |"
        )
        lines.append(
            "| 6 | Only works on vector PDFs — scanned/rasterized "
            "drawings produce no geometry | **critical** | "
            "Integrate OCR + image-based line detection "
            "(Hough transform) for raster fallback |"
        )
        lines.append(
            "| 7 | Multi-story PDFs not yet supported — only "
            "processes first page | **moderate** | "
            "Extend pipeline to iterate pages and match "
            "floor labels |"
        )
        lines.append("")

        # --- Recommendations ---
        lines.append("## Recommendations")
        lines.append("")
        lines.append(
            "### What to tune"
        )
        lines.append(
            "- **Area tolerance**: Current ±25% is generous. "
            "Phase 1 target: ±15%. Production target: ±10%."
        )
        lines.append(
            "- **Min wall length** (`_MIN_WALL_LENGTH_PTS=36`): "
            "Works well for 1/4\" scale. May need adjustment "
            "for 1/8\" scale drawings."
        )
        lines.append(
            "- **IQR outlier factor** (`_OUTLIER_IQR_FACTOR=3.0`): "
            "Effective at removing title block borders. "
            "Tighten to 2.5 if false positives appear."
        )
        lines.append("")
        lines.append(
            "### VLM vs Geometry: division of labor"
        )
        lines.append(
            "- **Geometry handles**: Scale detection, gross area, "
            "perimeter, wall count/length, wall thickness."
        )
        lines.append(
            "- **VLM handles**: Building type, structural system, "
            "story count, story height, exterior wall type, "
            "room identification."
        )
        lines.append(
            "- **Hybrid merge** (HybridAnalyzer): Uses geometry "
            "for area when confidence is HIGH/MEDIUM, "
            "VLM for semantic fields always."
        )
        lines.append("")
        lines.append(
            "### PDF classes that work well"
        )
        lines.append(
            "- Clean CAD exports with vector geometry "
            "(AutoCAD, Revit, SketchUp)"
        )
        lines.append(
            "- Drawings at 1/4\" or 1/8\" architectural scales"
        )
        lines.append(
            "- Single-page floor plans with title block "
            "and dimension annotations"
        )
        lines.append("")
        lines.append(
            "### PDF classes that work poorly"
        )
        lines.append(
            "- Scanned/rasterized drawings (no vector data)"
        )
        lines.append(
            "- Multi-page document sets (only first page processed)"
        )
        lines.append(
            "- Imperial engineering scales (1\"=20', 1\"=40') — "
            "untested"
        )
        lines.append(
            "- Drawings without scale notation in title block"
        )
        lines.append("")

        # Write report
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text("\n".join(lines) + "\n")

        print(f"\n--- Report written to {_REPORT_PATH} ---")
        print(
            f"--- Area: {area_actual} "
            f"(error: {area_err}) ---"
        )
        print(
            f"--- Scale: {scale_str} ---"
        )
        print(
            f"--- Confidence: {result.confidence.value} ---"
        )

        # Always passes — this is a diagnostic tool
        assert _REPORT_PATH.exists(), (
            "Report file was not created"
        )


# ---------------------------------------------------------------------------
# Assertion test: minimum accuracy thresholds
# ---------------------------------------------------------------------------


class TestMinimumThresholds:
    """Verify minimum accuracy thresholds are met."""

    def test_scale_factor_within_10_percent(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Scale factor should be within ±10% of 48.0."""
        result = _service.measure(first_floor_page)
        assert result.scale is not None, "Scale not detected"
        actual = result.scale.scale_factor
        tolerance = EXPECTED_SCALE_FACTOR * 0.10
        print(
            f"\n--- Scale: {actual:.1f} "
            f"(expected {EXPECTED_SCALE_FACTOR} "
            f"±{tolerance:.1f}) ---"
        )
        assert abs(actual - EXPECTED_SCALE_FACTOR) <= tolerance, (
            f"Scale factor {actual:.1f} not within ±10% "
            f"of {EXPECTED_SCALE_FACTOR}"
        )

    def test_gross_area_within_30_percent(
        self, first_floor_page: fitz.Page
    ) -> None:
        """Gross area should be within ±30% of 512 SF."""
        result = _service.measure(first_floor_page)
        assert result.gross_area_sf is not None, (
            "Gross area not computed"
        )
        actual = result.gross_area_sf
        lower = EXPECTED_GROSS_AREA_SF * 0.70
        upper = EXPECTED_GROSS_AREA_SF * 1.30
        error_pct = (
            (actual - EXPECTED_GROSS_AREA_SF)
            / EXPECTED_GROSS_AREA_SF
            * 100
        )
        print(
            f"\n--- Area: {actual:.1f} SF "
            f"(expected {EXPECTED_GROSS_AREA_SF:.0f} SF, "
            f"error {error_pct:+.1f}%, "
            f"range {lower:.0f}-{upper:.0f}) ---"
        )
        assert lower <= actual <= upper, (
            f"Gross area {actual:.1f} SF not within ±30% "
            f"of {EXPECTED_GROSS_AREA_SF:.0f} SF"
        )

    def test_at_least_6_room_labels(
        self, first_floor_page: fitz.Page
    ) -> None:
        """At least 6 room labels should be extracted."""
        text_blocks = _scale_detector.extract_text_blocks(
            first_floor_page
        )
        found, missed = _find_room_labels(text_blocks)
        print(
            f"\n--- Room labels: {len(found)} found "
            f"(need >= {EXPECTED_ROOM_COUNT - 1}) ---"
        )
        assert len(found) >= 6, (
            f"Only {len(found)} room labels found, "
            f"expected at least 6. "
            f"Found: {found}, Missed: {missed}"
        )
