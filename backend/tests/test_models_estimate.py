"""Tests for CostEstimate and related output models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cantena.models import (
    Assumption,
    BuildingSummary,
    Confidence,
    CostEstimate,
    CostRange,
    DivisionCost,
    EstimateMetadata,
)

# ---------- CostRange ----------


class TestCostRange:
    def test_valid_cost_range(self) -> None:
        cr = CostRange(low=100.0, expected=150.0, high=200.0)
        assert cr.low == 100.0
        assert cr.expected == 150.0
        assert cr.high == 200.0

    def test_equal_values(self) -> None:
        cr = CostRange(low=100.0, expected=100.0, high=100.0)
        assert cr.low == cr.expected == cr.high

    def test_low_equals_expected(self) -> None:
        cr = CostRange(low=100.0, expected=100.0, high=200.0)
        assert cr.low == cr.expected

    def test_expected_equals_high(self) -> None:
        cr = CostRange(low=100.0, expected=200.0, high=200.0)
        assert cr.expected == cr.high

    def test_low_greater_than_expected_raises(self) -> None:
        with pytest.raises(ValidationError, match="low <= expected <= high"):
            CostRange(low=200.0, expected=100.0, high=300.0)

    def test_expected_greater_than_high_raises(self) -> None:
        with pytest.raises(ValidationError, match="low <= expected <= high"):
            CostRange(low=100.0, expected=300.0, high=200.0)

    def test_low_greater_than_high_raises(self) -> None:
        with pytest.raises(ValidationError, match="low <= expected <= high"):
            CostRange(low=300.0, expected=200.0, high=100.0)

    def test_json_round_trip(self) -> None:
        cr = CostRange(low=100.0, expected=150.0, high=200.0)
        json_str = cr.model_dump_json()
        restored = CostRange.model_validate_json(json_str)
        assert restored == cr


# ---------- DivisionCost ----------


class TestDivisionCost:
    def test_valid_division_cost(self) -> None:
        dc = DivisionCost(
            csi_division="03",
            division_name="Concrete",
            cost=CostRange(low=500_000.0, expected=650_000.0, high=800_000.0),
            percent_of_total=15.0,
            source="RSMeans 2025",
        )
        assert dc.csi_division == "03"
        assert dc.division_name == "Concrete"
        assert dc.percent_of_total == 15.0


# ---------- Assumption ----------


class TestAssumption:
    def test_valid_assumption(self) -> None:
        a = Assumption(
            parameter="structural_system",
            assumed_value="steel_frame",
            reasoning="Extracted from drawings with high confidence",
            confidence=Confidence.HIGH,
        )
        assert a.parameter == "structural_system"
        assert a.confidence == Confidence.HIGH


# ---------- BuildingSummary ----------


class TestBuildingSummary:
    def test_valid_summary(self) -> None:
        bs = BuildingSummary(
            building_type="office_mid_rise",
            gross_sf=120_000.0,
            stories=8,
            structural_system="steel_frame",
            exterior_wall="curtain_wall",
            location="New York, NY",
        )
        assert bs.gross_sf == 120_000.0
        assert bs.stories == 8


# ---------- EstimateMetadata ----------


class TestEstimateMetadata:
    def test_valid_metadata(self) -> None:
        m = EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025-Q1",
        )
        assert m.estimation_method == "square_foot_conceptual"

    def test_custom_estimation_method(self) -> None:
        m = EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025-Q1",
            estimation_method="detailed_unit_cost",
        )
        assert m.estimation_method == "detailed_unit_cost"


# ---------- CostEstimate ----------


def _build_realistic_estimate() -> CostEstimate:
    """Build a realistic example CostEstimate for testing."""
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


class TestCostEstimate:
    def test_valid_construction(self) -> None:
        estimate = _build_realistic_estimate()
        assert estimate.project_name == "Downtown Office Tower"
        assert estimate.location_factor == 1.30
        assert len(estimate.breakdown) == 5
        assert len(estimate.assumptions) == 2

    def test_generated_at_default(self) -> None:
        """generated_at defaults to now if not provided."""
        estimate = CostEstimate(
            project_name="Test",
            building_summary=BuildingSummary(
                building_type="warehouse",
                gross_sf=50_000.0,
                stories=1,
                structural_system="steel_frame",
                exterior_wall="metal_panel",
                location="Houston, TX",
            ),
            total_cost=CostRange(low=4_000_000.0, expected=5_000_000.0, high=6_250_000.0),
            cost_per_sf=CostRange(low=80.0, expected=100.0, high=125.0),
            breakdown=[],
            assumptions=[],
            location_factor=0.88,
            metadata=EstimateMetadata(
                engine_version="0.1.0",
                cost_data_version="2025-Q1",
            ),
        )
        assert isinstance(estimate.generated_at, datetime)

    def test_json_round_trip(self) -> None:
        estimate = _build_realistic_estimate()
        json_str = estimate.model_dump_json()
        restored = CostEstimate.model_validate_json(json_str)
        assert restored.project_name == estimate.project_name
        assert restored.total_cost == estimate.total_cost
        assert restored.cost_per_sf == estimate.cost_per_sf
        assert len(restored.breakdown) == len(estimate.breakdown)
        assert len(restored.assumptions) == len(estimate.assumptions)
        assert restored.location_factor == estimate.location_factor
        assert restored.metadata == estimate.metadata

    def test_json_serialization_structure(self) -> None:
        estimate = _build_realistic_estimate()
        data = estimate.model_dump()
        assert "project_name" in data
        assert "building_summary" in data
        assert "total_cost" in data
        assert "cost_per_sf" in data
        assert "breakdown" in data
        assert "assumptions" in data
        assert "location_factor" in data
        assert "metadata" in data
        # Check nested structure
        assert "low" in data["total_cost"]
        assert "expected" in data["total_cost"]
        assert "high" in data["total_cost"]

    def test_cost_range_validation_in_estimate(self) -> None:
        """CostRange validation fires within CostEstimate."""
        with pytest.raises(ValidationError):
            CostEstimate(
                project_name="Bad",
                building_summary=BuildingSummary(
                    building_type="warehouse",
                    gross_sf=50_000.0,
                    stories=1,
                    structural_system="steel_frame",
                    exterior_wall="metal_panel",
                    location="Houston, TX",
                ),
                total_cost=CostRange(low=999.0, expected=1.0, high=999.0),
                cost_per_sf=CostRange(low=80.0, expected=100.0, high=125.0),
                breakdown=[],
                assumptions=[],
                location_factor=1.0,
                metadata=EstimateMetadata(
                    engine_version="0.1.0",
                    cost_data_version="2025-Q1",
                ),
            )

    def test_realistic_example_helper(self) -> None:
        """The helper function produces a valid, realistic estimate."""
        estimate = _build_realistic_estimate()
        assert estimate.total_cost.expected == 38_000_000.0
        assert estimate.cost_per_sf.expected == pytest.approx(316.67, abs=0.01)
        assert estimate.building_summary.gross_sf == 120_000.0
        assert estimate.metadata.estimation_method == "square_foot_conceptual"
