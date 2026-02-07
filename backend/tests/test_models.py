"""Tests for BuildingModel and related domain types."""

import json

import pytest
from pydantic import ValidationError

from cantena.models import (
    BuildingModel,
    BuildingType,
    ComplexityScores,
    Confidence,
    ElectricalService,
    ExteriorWall,
    FireProtection,
    Location,
    MechanicalSystem,
    StructuralSystem,
)


def _make_building(**overrides: object) -> BuildingModel:
    """Helper to build a valid BuildingModel with sensible defaults."""
    defaults: dict[str, object] = {
        "building_type": BuildingType.APARTMENT_LOW_RISE,
        "building_use": "Residential apartments",
        "gross_sf": 36000.0,
        "stories": 3,
        "story_height_ft": 10.0,
        "structural_system": StructuralSystem.WOOD_FRAME,
        "exterior_wall_system": ExteriorWall.BRICK_VENEER,
        "mechanical_system": MechanicalSystem.SPLIT_SYSTEM,
        "electrical_service": ElectricalService.STANDARD,
        "fire_protection": FireProtection.SPRINKLER_WET,
        "location": Location(city="Baltimore", state="MD"),
        "complexity_scores": ComplexityScores(structural=3, mep=3, finishes=3, site=3),
        "special_conditions": [],
        "confidence": {"building_type": Confidence.HIGH, "gross_sf": Confidence.MEDIUM},
    }
    defaults.update(overrides)
    return BuildingModel(**defaults)  # type: ignore[arg-type]


class TestValidConstruction:
    def test_minimal_valid_building(self) -> None:
        """Build with only required fields — defaults fill the rest."""
        b = BuildingModel(
            building_type=BuildingType.OFFICE_LOW_RISE,
            building_use="General office",
            gross_sf=10000.0,
            stories=2,
            structural_system=StructuralSystem.STEEL_FRAME,
            exterior_wall_system=ExteriorWall.CURTAIN_WALL,
            location=Location(city="New York", state="NY"),
        )
        assert b.mechanical_system is None
        assert b.electrical_service is None
        assert b.fire_protection is None
        assert b.complexity_scores.structural == 3  # default
        assert b.special_conditions == []
        assert b.confidence == {}

    def test_full_valid_building(self) -> None:
        b = _make_building()
        assert b.building_type == BuildingType.APARTMENT_LOW_RISE
        assert b.gross_sf == 36000.0
        assert b.stories == 3
        assert b.location.city == "Baltimore"
        assert b.location.state == "MD"
        assert b.location.zip_code is None

    def test_location_with_zip(self) -> None:
        loc = Location(city="Denver", state="CO", zip_code="80202")
        b = _make_building(location=loc)
        assert b.location.zip_code == "80202"


class TestValidationErrors:
    def test_negative_gross_sf(self) -> None:
        with pytest.raises(ValidationError):
            _make_building(gross_sf=-100.0)

    def test_zero_gross_sf(self) -> None:
        with pytest.raises(ValidationError):
            _make_building(gross_sf=0.0)

    def test_stories_less_than_one(self) -> None:
        with pytest.raises(ValidationError):
            _make_building(stories=0)

    def test_complexity_score_below_range(self) -> None:
        with pytest.raises(ValidationError):
            ComplexityScores(structural=0, mep=3, finishes=3, site=3)

    def test_complexity_score_above_range(self) -> None:
        with pytest.raises(ValidationError):
            ComplexityScores(structural=3, mep=6, finishes=3, site=3)

    def test_invalid_building_type(self) -> None:
        with pytest.raises(ValidationError):
            _make_building(building_type="not_a_type")

    def test_invalid_structural_system(self) -> None:
        with pytest.raises(ValidationError):
            _make_building(structural_system="bamboo")


class TestJsonRoundTrip:
    def test_serialize_and_deserialize(self) -> None:
        original = _make_building()
        json_str = original.model_dump_json()
        restored = BuildingModel.model_validate_json(json_str)
        assert restored == original

    def test_json_is_valid_json(self) -> None:
        b = _make_building()
        parsed = json.loads(b.model_dump_json())
        assert isinstance(parsed, dict)
        assert parsed["building_type"] == "apartment_low_rise"
        assert parsed["location"]["city"] == "Baltimore"

    def test_dict_round_trip(self) -> None:
        original = _make_building()
        data = original.model_dump()
        restored = BuildingModel.model_validate(data)
        assert restored == original


class TestDefaults:
    def test_default_complexity_scores(self) -> None:
        scores = ComplexityScores()
        assert scores.structural == 3
        assert scores.mep == 3
        assert scores.finishes == 3
        assert scores.site == 3

    def test_default_story_height(self) -> None:
        b = _make_building()
        assert b.story_height_ft == 10.0

    def test_default_special_conditions_empty(self) -> None:
        b = _make_building()
        assert b.special_conditions == []

    def test_default_confidence_can_be_empty(self) -> None:
        b = BuildingModel(
            building_type=BuildingType.WAREHOUSE,
            building_use="Storage",
            gross_sf=50000.0,
            stories=1,
            structural_system=StructuralSystem.STEEL_FRAME,
            exterior_wall_system=ExteriorWall.METAL_PANEL,
            location=Location(city="Houston", state="TX"),
        )
        assert b.confidence == {}


class TestEnumValues:
    def test_building_type_has_at_least_12_values(self) -> None:
        assert len(BuildingType) >= 12

    def test_structural_system_has_5_values(self) -> None:
        assert len(StructuralSystem) == 5

    def test_exterior_wall_has_7_values(self) -> None:
        assert len(ExteriorWall) == 7

    def test_mechanical_system_has_5_values(self) -> None:
        assert len(MechanicalSystem) == 5

    def test_electrical_service_has_3_values(self) -> None:
        assert len(ElectricalService) == 3

    def test_fire_protection_has_3_values(self) -> None:
        assert len(FireProtection) == 3

    def test_confidence_has_3_values(self) -> None:
        assert len(Confidence) == 3
