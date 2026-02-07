"""Tests for the CostEngine — the core estimation pipeline."""

from __future__ import annotations

import pytest

from cantena.data.repository import CostDataRepository
from cantena.data.seed import SEED_COST_ENTRIES
from cantena.engine import CostEngine
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    StructuralSystem,
)


@pytest.fixture()
def repo() -> CostDataRepository:
    """Repository loaded with seed data."""
    return CostDataRepository(SEED_COST_ENTRIES)


@pytest.fixture()
def engine(repo: CostDataRepository) -> CostEngine:
    """CostEngine wired to the seed data repository."""
    return CostEngine(repo)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _wood_frame_apartment(
    gross_sf: float = 36_000.0,
    stories: int = 3,
    city: str = "Baltimore",
    state: str = "MD",
    complexity: ComplexityScores | None = None,
    confidence: dict[str, Confidence] | None = None,
) -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        building_use="Multifamily residential",
        gross_sf=gross_sf,
        stories=stories,
        story_height_ft=10.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.BRICK_VENEER,
        location=Location(city=city, state=state),
        complexity_scores=complexity or ComplexityScores(),
        confidence=confidence or {},
    )


def _steel_office(
    gross_sf: float = 45_000.0,
    stories: int = 3,
    city: str = "Houston",
    state: str = "TX",
    complexity: ComplexityScores | None = None,
) -> BuildingModel:
    return BuildingModel(
        building_type=BuildingType.OFFICE_LOW_RISE,
        building_use="Commercial office",
        gross_sf=gross_sf,
        stories=stories,
        story_height_ft=12.0,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall_system=ExteriorWall.BRICK_VENEER,
        location=Location(city=city, state=state),
        complexity_scores=complexity or ComplexityScores(),
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Basic estimation with known seed data."""

    def test_wood_frame_apartment_cost_range(self, engine: CostEngine) -> None:
        """Wood-frame apartment should produce a $180-$250/SF-ish range."""
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test Apartment")

        # Baltimore has index 0.95, default complexity (all 3s) → multiplier 1.0
        # Seed base expected = 195 $/SF → adjusted = 195 * 0.95 = 185.25
        # Range: low = 185.25 * 0.80 = 148.20, high = 185.25 * 1.25 = 231.56
        assert estimate.cost_per_sf.low == pytest.approx(148.20, rel=0.01)
        assert estimate.cost_per_sf.expected == pytest.approx(185.25, rel=0.01)
        assert estimate.cost_per_sf.high == pytest.approx(231.5625, rel=0.01)

        # Total = 185.25 * 36,000 = 6,669,000
        assert estimate.total_cost.expected == pytest.approx(6_669_000.0, rel=0.01)

    def test_estimate_has_project_name(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "My Apartment")
        assert estimate.project_name == "My Apartment"

    def test_estimate_has_building_summary(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")
        assert estimate.building_summary.building_type == "apartment_low_rise"
        assert estimate.building_summary.gross_sf == 36_000.0
        assert estimate.building_summary.stories == 3
        assert estimate.building_summary.location == "Baltimore, MD"

    def test_estimate_has_metadata(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")
        assert estimate.metadata.engine_version == "0.1.0"
        assert estimate.metadata.cost_data_version == "2025.1"
        assert estimate.metadata.estimation_method == "square_foot_conceptual"


# ---------------------------------------------------------------------------
# Location factor tests
# ---------------------------------------------------------------------------


class TestLocationFactor:
    """NYC vs Houston should show ~40% difference."""

    def test_nyc_vs_houston_difference(self, engine: CostEngine) -> None:
        """NYC (1.30) vs Houston (0.88) should differ by ~47%."""
        nyc_building = _steel_office(city="New York", state="NY")
        houston_building = _steel_office(city="Houston", state="TX")

        nyc_est = engine.estimate(nyc_building, "NYC Office")
        houston_est = engine.estimate(houston_building, "Houston Office")

        ratio = nyc_est.total_cost.expected / houston_est.total_cost.expected
        # 1.30 / 0.88 ≈ 1.477
        assert ratio == pytest.approx(1.30 / 0.88, rel=0.01)

    def test_location_factor_stored(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment(city="New York", state="NY")
        estimate = engine.estimate(building, "Test")
        assert estimate.location_factor == pytest.approx(1.30)

    def test_unknown_city_uses_state_fallback(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment(city="Smalltown", state="TX")
        estimate = engine.estimate(building, "Test")
        assert estimate.location_factor == pytest.approx(0.88)

    def test_unknown_city_and_state_uses_default(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment(city="Unknown", state="ZZ")
        estimate = engine.estimate(building, "Test")
        assert estimate.location_factor == pytest.approx(1.00)


# ---------------------------------------------------------------------------
# Complexity multiplier tests
# ---------------------------------------------------------------------------


class TestComplexityMultiplier:
    """Complexity all-5s should be ~25% higher than all-3s."""

    def test_all_5s_higher_than_all_3s(self, engine: CostEngine) -> None:
        base_building = _wood_frame_apartment(
            complexity=ComplexityScores(structural=3, mep=3, finishes=3, site=3),
        )
        complex_building = _wood_frame_apartment(
            complexity=ComplexityScores(structural=5, mep=5, finishes=5, site=5),
        )

        base_est = engine.estimate(base_building, "Base")
        complex_est = engine.estimate(complex_building, "Complex")

        # All 3s → multiplier 1.0, All 5s → multiplier 1.25
        ratio = complex_est.total_cost.expected / base_est.total_cost.expected
        assert ratio == pytest.approx(1.25, rel=0.01)

    def test_all_1s_lower_than_all_3s(self, engine: CostEngine) -> None:
        base_building = _wood_frame_apartment(
            complexity=ComplexityScores(structural=3, mep=3, finishes=3, site=3),
        )
        simple_building = _wood_frame_apartment(
            complexity=ComplexityScores(structural=1, mep=1, finishes=1, site=1),
        )

        base_est = engine.estimate(base_building, "Base")
        simple_est = engine.estimate(simple_building, "Simple")

        # All 1s → multiplier 0.85
        ratio = simple_est.total_cost.expected / base_est.total_cost.expected
        assert ratio == pytest.approx(0.85, rel=0.01)

    def test_mixed_complexity(self, engine: CostEngine) -> None:
        """Weighted average: 0.30*1.10 + 0.30*1.00 + 0.25*0.95 + 0.15*1.25 = 1.0555."""
        building = _wood_frame_apartment(
            complexity=ComplexityScores(structural=4, mep=3, finishes=2, site=5),
        )
        base_building = _wood_frame_apartment()

        est = engine.estimate(building, "Mixed")
        base_est = engine.estimate(base_building, "Base")

        expected_multiplier = 0.30 * 1.10 + 0.30 * 1.00 + 0.25 * 0.95 + 0.15 * 1.25
        ratio = est.total_cost.expected / base_est.total_cost.expected
        assert ratio == pytest.approx(expected_multiplier, rel=0.001)


# ---------------------------------------------------------------------------
# Division breakdown tests
# ---------------------------------------------------------------------------


class TestDivisionBreakdown:
    """CSI division breakdown should sum to total and have sufficient divisions."""

    def test_division_costs_sum_to_total(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")

        division_expected_sum = sum(d.cost.expected for d in estimate.breakdown)
        assert division_expected_sum == pytest.approx(
            estimate.total_cost.expected, rel=0.02
        )

    def test_division_low_costs_sum_to_total_low(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")

        division_low_sum = sum(d.cost.low for d in estimate.breakdown)
        assert division_low_sum == pytest.approx(estimate.total_cost.low, rel=0.02)

    def test_at_least_5_divisions(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")
        assert len(estimate.breakdown) >= 5

    def test_division_has_name_and_number(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")
        for div in estimate.breakdown:
            assert div.csi_division  # not empty
            assert div.division_name  # not empty
            assert div.percent_of_total > 0


# ---------------------------------------------------------------------------
# Fuzzy match / assumptions tests
# ---------------------------------------------------------------------------


class TestFuzzyMatchAssumptions:
    """Fuzzy matching should produce documented assumptions."""

    def test_fuzzy_match_produces_assumptions(self, engine: CostEngine) -> None:
        """Use a wall system not in seed data for this building type."""
        building = BuildingModel(
            building_type=BuildingType.APARTMENT_LOW_RISE,
            building_use="Multifamily",
            gross_sf=20_000.0,
            stories=2,
            structural_system=StructuralSystem.WOOD_FRAME,
            exterior_wall_system=ExteriorWall.STUCCO,  # Not in seed for this combo
            location=Location(city="Denver", state="CO"),
        )
        estimate = engine.estimate(building, "Fuzzy Test")

        # Should still produce an estimate (fuzzy match)
        assert estimate.total_cost.expected > 0

        # Should have at least one assumption documenting the fuzzy match
        match_assumptions = [
            a for a in estimate.assumptions if a.parameter == "cost_data_match"
        ]
        assert len(match_assumptions) >= 1

    def test_exact_match_no_fallback_assumptions(self, engine: CostEngine) -> None:
        """Exact match should not produce cost_data_match assumptions."""
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Exact Test")

        match_assumptions = [
            a for a in estimate.assumptions if a.parameter == "cost_data_match"
        ]
        assert len(match_assumptions) == 0


# ---------------------------------------------------------------------------
# ValueError for unknown type
# ---------------------------------------------------------------------------


class TestErrors:
    """Engine should raise descriptive errors when data is missing."""

    def test_no_seed_data_raises_value_error(self) -> None:
        """An empty repository should raise ValueError."""
        empty_repo = CostDataRepository([])
        engine = CostEngine(empty_repo)

        building = _wood_frame_apartment()
        with pytest.raises(ValueError, match="No cost data found"):
            engine.estimate(building, "Should Fail")


# ---------------------------------------------------------------------------
# Low confidence field assumptions
# ---------------------------------------------------------------------------


class TestLowConfidenceAssumptions:
    """Low-confidence fields should appear as assumptions."""

    def test_low_confidence_field_generates_assumption(
        self, engine: CostEngine
    ) -> None:
        building = _wood_frame_apartment(
            confidence={"structural_system": Confidence.LOW},
        )
        estimate = engine.estimate(building, "Low Confidence Test")

        low_conf_assumptions = [
            a
            for a in estimate.assumptions
            if a.parameter == "structural_system" and a.confidence == Confidence.LOW
        ]
        assert len(low_conf_assumptions) == 1

    def test_high_confidence_field_no_assumption(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment(
            confidence={"structural_system": Confidence.HIGH},
        )
        estimate = engine.estimate(building, "High Confidence Test")

        low_conf_assumptions = [
            a for a in estimate.assumptions if a.parameter == "structural_system"
        ]
        assert len(low_conf_assumptions) == 0


# ---------------------------------------------------------------------------
# Realistic value sanity checks
# ---------------------------------------------------------------------------


class TestRealisticValues:
    """Estimates should produce sensible real-world numbers."""

    def test_45k_sf_office_in_range(self, engine: CostEngine) -> None:
        """A 45K SF office should estimate $9M-$16M range."""
        building = _steel_office(gross_sf=45_000.0, stories=3)
        estimate = engine.estimate(building, "Office")

        # Houston index = 0.88, base expected = 225, complexity default 1.0
        # adjusted = 225 * 0.88 = 198.0, total = 198 * 45000 = 8,910,000
        # low = 8,910,000 * 0.80 = 7,128,000
        # high = 8,910,000 * 1.25 = 11,137,500
        assert estimate.total_cost.low >= 5_000_000
        assert estimate.total_cost.high <= 20_000_000

    def test_cost_range_low_le_expected_le_high(self, engine: CostEngine) -> None:
        building = _wood_frame_apartment()
        estimate = engine.estimate(building, "Test")

        assert estimate.total_cost.low <= estimate.total_cost.expected
        assert estimate.total_cost.expected <= estimate.total_cost.high
        assert estimate.cost_per_sf.low <= estimate.cost_per_sf.expected
        assert estimate.cost_per_sf.expected <= estimate.cost_per_sf.high
