"""Tests for formatting helpers and CostEstimate summary/export methods."""

from __future__ import annotations

from datetime import UTC, datetime

from cantena.formatting import format_cost_range, format_currency, format_sf_cost
from cantena.models.enums import Confidence
from cantena.models.estimate import (
    Assumption,
    BuildingSummary,
    CostEstimate,
    CostRange,
    DivisionCost,
    EstimateMetadata,
)

# ---------- Helpers ----------


def _build_estimate() -> CostEstimate:
    """Build a realistic CostEstimate for testing summary/export methods."""
    return CostEstimate(
        project_name="Downtown Office Tower",
        building_summary=BuildingSummary(
            building_type="office_mid_rise",
            gross_sf=120_000.0,
            stories=8,
            structural_system="steel_frame",
            exterior_wall="curtain_wall",
            location="New York, NY",
        ),
        total_cost=CostRange(
            low=30_000_000.0, expected=38_000_000.0, high=47_500_000.0
        ),
        cost_per_sf=CostRange(low=250.0, expected=316.67, high=395.83),
        breakdown=[
            DivisionCost(
                csi_division="03",
                division_name="Concrete",
                cost=CostRange(
                    low=4_500_000.0, expected=5_700_000.0, high=7_125_000.0
                ),
                percent_of_total=15.0,
                source="RSMeans 2025",
            ),
            DivisionCost(
                csi_division="05",
                division_name="Metals",
                cost=CostRange(
                    low=3_600_000.0, expected=4_560_000.0, high=5_700_000.0
                ),
                percent_of_total=12.0,
                source="RSMeans 2025",
            ),
            DivisionCost(
                csi_division="07",
                division_name="Thermal & Moisture Protection",
                cost=CostRange(
                    low=2_100_000.0, expected=2_660_000.0, high=3_325_000.0
                ),
                percent_of_total=7.0,
                source="RSMeans 2025",
            ),
            DivisionCost(
                csi_division="08",
                division_name="Openings",
                cost=CostRange(
                    low=2_400_000.0, expected=3_040_000.0, high=3_800_000.0
                ),
                percent_of_total=8.0,
                source="RSMeans 2025",
            ),
            DivisionCost(
                csi_division="23",
                division_name="HVAC",
                cost=CostRange(
                    low=4_200_000.0, expected=5_320_000.0, high=6_650_000.0
                ),
                percent_of_total=14.0,
                source="RSMeans 2025",
            ),
        ],
        assumptions=[
            Assumption(
                parameter="mechanical_system",
                assumed_value="vav",
                reasoning="Standard for mid-rise office buildings",
                confidence=Confidence.MEDIUM,
            ),
            Assumption(
                parameter="fire_protection",
                assumed_value="sprinkler_wet",
                reasoning="Required by code for this building type",
                confidence=Confidence.HIGH,
            ),
        ],
        generated_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC),
        location_factor=1.30,
        metadata=EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025-Q1",
        ),
    )


# ---------- format_currency ----------


class TestFormatCurrency:
    def test_large_amount_no_cents(self) -> None:
        assert format_currency(12_437_892.34) == "$12,437,892"

    def test_exact_threshold(self) -> None:
        assert format_currency(10_000.0) == "$10,000"

    def test_below_threshold_with_cents(self) -> None:
        assert format_currency(9_876.54) == "$9,876.54"

    def test_small_amount(self) -> None:
        assert format_currency(42.50) == "$42.50"

    def test_zero(self) -> None:
        assert format_currency(0.0) == "$0.00"

    def test_millions(self) -> None:
        assert format_currency(38_000_000.0) == "$38,000,000"

    def test_just_below_threshold(self) -> None:
        assert format_currency(9_999.99) == "$9,999.99"


# ---------- format_cost_range ----------


class TestFormatCostRange:
    def test_millions_range(self) -> None:
        cr = CostRange(low=30_000_000.0, expected=38_000_000.0, high=47_500_000.0)
        assert format_cost_range(cr) == "$30.0M - $47.5M"

    def test_below_million(self) -> None:
        cr = CostRange(low=500_000.0, expected=650_000.0, high=800_000.0)
        assert format_cost_range(cr) == "$500,000 - $800,000"

    def test_mixed_boundary(self) -> None:
        """When high >= 1M, use millions format."""
        cr = CostRange(low=800_000.0, expected=900_000.0, high=1_125_000.0)
        assert format_cost_range(cr) == "$0.8M - $1.1M"

    def test_exact_million(self) -> None:
        cr = CostRange(low=800_000.0, expected=1_000_000.0, high=1_250_000.0)
        assert format_cost_range(cr) == "$0.8M - $1.2M"

    def test_small_range(self) -> None:
        cr = CostRange(low=100_000.0, expected=125_000.0, high=150_000.0)
        assert format_cost_range(cr) == "$100,000 - $150,000"


# ---------- format_sf_cost ----------


class TestFormatSfCost:
    def test_typical_range(self) -> None:
        cr = CostRange(low=250.0, expected=316.67, high=395.83)
        assert format_sf_cost(cr) == "$250 - $396 / SF"

    def test_low_cost(self) -> None:
        cr = CostRange(low=75.0, expected=100.0, high=125.0)
        assert format_sf_cost(cr) == "$75 - $125 / SF"

    def test_high_cost(self) -> None:
        cr = CostRange(low=400.0, expected=500.0, high=625.0)
        assert format_sf_cost(cr) == "$400 - $625 / SF"


# ---------- CostEstimate.to_summary_dict ----------


class TestToSummaryDict:
    def test_all_keys_present(self) -> None:
        estimate = _build_estimate()
        summary = estimate.to_summary_dict()
        expected_keys = {
            "project_name",
            "building_type",
            "gross_sf_formatted",
            "total_cost_formatted",
            "total_cost_range_formatted",
            "cost_per_sf_formatted",
            "cost_per_sf_range_formatted",
            "location",
            "location_factor",
            "num_divisions",
            "top_cost_drivers",
            "num_assumptions",
            "generated_at_formatted",
        }
        assert set(summary.keys()) == expected_keys

    def test_project_name(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["project_name"] == "Downtown Office Tower"

    def test_building_type(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["building_type"] == "office_mid_rise"

    def test_gross_sf_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["gross_sf_formatted"] == "120,000 SF"

    def test_total_cost_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["total_cost_formatted"] == "$38,000,000"

    def test_total_cost_range_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["total_cost_range_formatted"] == "$30.0M - $47.5M"

    def test_cost_per_sf_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["cost_per_sf_formatted"] == "$316.67"

    def test_cost_per_sf_range_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["cost_per_sf_range_formatted"] == "$250 - $396 / SF"

    def test_location(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["location"] == "New York, NY"

    def test_location_factor(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["location_factor"] == 1.30

    def test_num_divisions(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["num_divisions"] == 5

    def test_top_cost_drivers(self) -> None:
        summary = _build_estimate().to_summary_dict()
        drivers = summary["top_cost_drivers"]
        assert len(drivers) == 3
        # Top 3 by expected cost: Concrete (5.7M), HVAC (5.32M), Metals (4.56M)
        assert drivers[0]["division_name"] == "Concrete"
        assert drivers[1]["division_name"] == "HVAC"
        assert drivers[2]["division_name"] == "Metals"
        assert "cost_formatted" in drivers[0]
        assert "percent_of_total" in drivers[0]

    def test_num_assumptions(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["num_assumptions"] == 2

    def test_generated_at_formatted(self) -> None:
        summary = _build_estimate().to_summary_dict()
        assert summary["generated_at_formatted"] == "2025-01-15 10:30"


# ---------- CostEstimate.to_export_dict ----------


class TestToExportDict:
    def test_all_keys_present(self) -> None:
        export = _build_estimate().to_export_dict()
        expected_keys = {
            "project_name",
            "building_summary",
            "total_cost",
            "cost_per_sf",
            "breakdown",
            "assumptions",
            "generated_at",
            "location_factor",
            "metadata",
        }
        assert set(export.keys()) == expected_keys

    def test_building_summary_is_dict(self) -> None:
        export = _build_estimate().to_export_dict()
        bs = export["building_summary"]
        assert isinstance(bs, dict)
        assert bs["building_type"] == "office_mid_rise"
        assert bs["gross_sf"] == 120_000.0

    def test_total_cost_structure(self) -> None:
        export = _build_estimate().to_export_dict()
        tc = export["total_cost"]
        assert tc["low"] == 30_000_000.0
        assert tc["expected"] == 38_000_000.0
        assert tc["high"] == 47_500_000.0

    def test_breakdown_structure(self) -> None:
        export = _build_estimate().to_export_dict()
        assert len(export["breakdown"]) == 5
        first = export["breakdown"][0]
        assert "csi_division" in first
        assert "division_name" in first
        assert "cost" in first
        assert "percent_of_total" in first
        assert "source" in first
        assert "low" in first["cost"]

    def test_assumptions_structure(self) -> None:
        export = _build_estimate().to_export_dict()
        assert len(export["assumptions"]) == 2
        first = export["assumptions"][0]
        assert "parameter" in first
        assert "assumed_value" in first
        assert "reasoning" in first
        assert "confidence" in first
        assert first["confidence"] == "medium"

    def test_generated_at_is_iso(self) -> None:
        export = _build_estimate().to_export_dict()
        assert "2025-01-15" in export["generated_at"]

    def test_metadata_structure(self) -> None:
        export = _build_estimate().to_export_dict()
        meta = export["metadata"]
        assert meta["engine_version"] == "0.1.0"
        assert meta["estimation_method"] == "square_foot_conceptual"


# ---------- Formatting consistency ----------


class TestFormattingConsistency:
    def test_summary_and_export_same_estimate(self) -> None:
        """Both methods return valid data from the same estimate."""
        estimate = _build_estimate()
        summary = estimate.to_summary_dict()
        export = estimate.to_export_dict()
        assert summary["project_name"] == export["project_name"]
        assert summary["location_factor"] == export["location_factor"]
        assert summary["num_divisions"] == len(export["breakdown"])
        assert summary["num_assumptions"] == len(export["assumptions"])
