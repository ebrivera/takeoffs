"""Tests for the public API surface of the cantena package.

Verifies that consumers can import everything they need from the top-level
``cantena`` package, use ``create_default_engine`` for quick setup, and
round-trip estimates through JSON serialization.
"""

from __future__ import annotations

import json

from cantena import (
    BuildingModel,
    BuildingType,
    ComplexityScores,
    Confidence,
    CostEngine,
    CostEstimate,
    CostRange,
    ElectricalService,
    ExteriorWall,
    FireProtection,
    Location,
    MechanicalSystem,
    StructuralSystem,
    create_default_engine,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_building() -> BuildingModel:
    """Create a simple building model for testing."""
    return BuildingModel(
        building_type=BuildingType.APARTMENT_LOW_RISE,
        building_use="Multifamily residential",
        gross_sf=36_000.0,
        stories=3,
        story_height_ft=10.0,
        structural_system=StructuralSystem.WOOD_FRAME,
        exterior_wall_system=ExteriorWall.BRICK_VENEER,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(structural=3, mep=3, finishes=3, site=3),
    )


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestPublicImports:
    """All expected symbols are importable from the top-level package."""

    def test_import_cost_engine(self) -> None:
        assert CostEngine is not None

    def test_import_building_model(self) -> None:
        assert BuildingModel is not None

    def test_import_cost_estimate(self) -> None:
        assert CostEstimate is not None

    def test_import_cost_range(self) -> None:
        assert CostRange is not None

    def test_import_create_default_engine(self) -> None:
        assert callable(create_default_engine)

    def test_import_enums(self) -> None:
        assert BuildingType is not None
        assert StructuralSystem is not None
        assert ExteriorWall is not None
        assert MechanicalSystem is not None
        assert ElectricalService is not None
        assert FireProtection is not None
        assert Confidence is not None

    def test_import_supporting_models(self) -> None:
        assert Location is not None
        assert ComplexityScores is not None


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestCreateDefaultEngine:
    """create_default_engine() returns a working CostEngine."""

    def test_returns_cost_engine(self) -> None:
        engine = create_default_engine()
        assert isinstance(engine, CostEngine)

    def test_engine_can_produce_estimate(self) -> None:
        engine = create_default_engine()
        building = _sample_building()
        estimate = engine.estimate(building, "Test Project")
        assert isinstance(estimate, CostEstimate)
        assert estimate.project_name == "Test Project"

    def test_estimate_has_populated_fields(self) -> None:
        engine = create_default_engine()
        building = _sample_building()
        estimate = engine.estimate(building, "API Test")
        assert estimate.total_cost.expected > 0
        assert estimate.cost_per_sf.expected > 0
        assert len(estimate.breakdown) > 0
        assert estimate.location_factor > 0
        assert estimate.metadata.engine_version != ""


# ---------------------------------------------------------------------------
# JSON round-trip tests
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    """Estimates serialize to JSON and deserialize back correctly."""

    def test_estimate_to_json(self) -> None:
        engine = create_default_engine()
        estimate = engine.estimate(_sample_building(), "JSON Test")
        json_str = estimate.model_dump_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["project_name"] == "JSON Test"

    def test_json_round_trip(self) -> None:
        engine = create_default_engine()
        original = engine.estimate(_sample_building(), "Round Trip")
        json_str = original.model_dump_json()
        restored = CostEstimate.model_validate_json(json_str)
        assert restored.project_name == original.project_name
        assert restored.total_cost.expected == original.total_cost.expected
        assert restored.total_cost.low == original.total_cost.low
        assert restored.total_cost.high == original.total_cost.high
        assert restored.cost_per_sf.expected == original.cost_per_sf.expected
        assert len(restored.breakdown) == len(original.breakdown)
        assert restored.location_factor == original.location_factor

    def test_json_dict_round_trip(self) -> None:
        engine = create_default_engine()
        original = engine.estimate(_sample_building(), "Dict Round Trip")
        data = original.model_dump()
        restored = CostEstimate.model_validate(data)
        assert restored.project_name == original.project_name
        assert restored.total_cost.expected == original.total_cost.expected

    def test_json_output_is_consumable(self) -> None:
        """JSON output has a structure suitable for frontend consumption."""
        engine = create_default_engine()
        estimate = engine.estimate(_sample_building(), "Frontend Test")
        data = json.loads(estimate.model_dump_json())

        # Top-level keys expected by a frontend consumer
        assert "project_name" in data
        assert "building_summary" in data
        assert "total_cost" in data
        assert "cost_per_sf" in data
        assert "breakdown" in data
        assert "assumptions" in data
        assert "location_factor" in data
        assert "metadata" in data
        assert "generated_at" in data

        # Nested structure checks
        assert "low" in data["total_cost"]
        assert "expected" in data["total_cost"]
        assert "high" in data["total_cost"]
        assert isinstance(data["breakdown"], list)
        assert len(data["breakdown"]) > 0
        assert "csi_division" in data["breakdown"][0]
        assert "division_name" in data["breakdown"][0]
        assert "cost" in data["breakdown"][0]


# ---------------------------------------------------------------------------
# Full round-trip integration test
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """End-to-end: BuildingModel -> estimate -> JSON -> deserialize."""

    def test_building_to_json_to_estimate(self) -> None:
        engine = create_default_engine()
        building = _sample_building()

        # Step 1: Produce estimate
        estimate = engine.estimate(building, "Integration Test")
        assert isinstance(estimate, CostEstimate)

        # Step 2: Serialize to JSON
        json_str = estimate.model_dump_json()
        assert isinstance(json_str, str)

        # Step 3: Parse JSON to dict
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

        # Step 4: Deserialize back to CostEstimate
        restored = CostEstimate.model_validate(parsed)
        assert isinstance(restored, CostEstimate)

        # Step 5: Verify key fields survived the round trip
        assert restored.project_name == "Integration Test"
        assert restored.total_cost.low <= restored.total_cost.expected
        assert restored.total_cost.expected <= restored.total_cost.high
        assert restored.cost_per_sf.expected > 0
        assert len(restored.breakdown) >= 5
        assert restored.metadata.estimation_method == "square_foot_conceptual"
