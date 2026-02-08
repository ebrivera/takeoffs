"""Tests for POST /api/estimate with optional SpaceProgram support."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from cantena.api.app import create_app
from cantena.models.building import BuildingModel, ComplexityScores, Location
from cantena.models.enums import (
    BuildingType,
    Confidence,
    ExteriorWall,
    RoomType,
    StructuralSystem,
)
from cantena.models.estimate import (
    BuildingSummary,
    CostEstimate,
    CostRange,
    EstimateMetadata,
    SpaceCost,
)
from cantena.models.space_program import Space, SpaceProgram, SpaceSource

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_building_model(
    building_type: BuildingType = BuildingType.OFFICE_MID_RISE,
    gross_sf: float = 45000.0,
) -> BuildingModel:
    return BuildingModel(
        building_type=building_type,
        building_use="General office",
        gross_sf=gross_sf,
        stories=3,
        story_height_ft=13.0,
        structural_system=StructuralSystem.STEEL_FRAME,
        exterior_wall_system=ExteriorWall.CURTAIN_WALL,
        location=Location(city="Baltimore", state="MD"),
        complexity_scores=ComplexityScores(),
        confidence={"building_type": Confidence.HIGH},
    )


def _make_cost_estimate(
    space_breakdown: list[SpaceCost] | None = None,
) -> CostEstimate:
    return CostEstimate(
        project_name="Baltimore, MD",
        building_summary=BuildingSummary(
            building_type="office_mid_rise",
            gross_sf=45000.0,
            stories=3,
            structural_system="steel_frame",
            exterior_wall="curtain_wall",
            location="Baltimore, MD",
        ),
        total_cost=CostRange(low=8_000_000, expected=10_000_000, high=12_500_000),
        cost_per_sf=CostRange(low=178.0, expected=222.0, high=278.0),
        breakdown=[],
        assumptions=[],
        location_factor=1.02,
        metadata=EstimateMetadata(
            engine_version="0.1.0",
            cost_data_version="2025.1",
        ),
        space_breakdown=space_breakdown,
    )


def _make_space_program() -> SpaceProgram:
    return SpaceProgram(
        spaces=[
            Space(
                room_type=RoomType.LOBBY,
                name="Lobby",
                area_sf=5000.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.OPEN_OFFICE,
                name="Open Office",
                area_sf=30000.0,
                source=SpaceSource.GEOMETRY,
                confidence=Confidence.HIGH,
            ),
            Space(
                room_type=RoomType.CORRIDOR,
                name="Corridor",
                area_sf=10000.0,
                source=SpaceSource.LLM,
                confidence=Confidence.MEDIUM,
            ),
        ],
        building_type=BuildingType.OFFICE_MID_RISE,
    )


def _make_space_breakdown() -> list[SpaceCost]:
    return [
        SpaceCost(
            room_type="lobby",
            name="Lobby",
            area_sf=5000.0,
            cost_per_sf=CostRange(low=300.0, expected=350.0, high=400.0),
            total_cost=CostRange(low=1_500_000, expected=1_750_000, high=2_000_000),
            percent_of_total=17.5,
            source="geometry",
        ),
        SpaceCost(
            room_type="open_office",
            name="Open Office",
            area_sf=30000.0,
            cost_per_sf=CostRange(low=200.0, expected=240.0, high=280.0),
            total_cost=CostRange(low=6_000_000, expected=7_200_000, high=8_400_000),
            percent_of_total=72.0,
            source="geometry",
        ),
        SpaceCost(
            room_type="corridor",
            name="Corridor",
            area_sf=10000.0,
            cost_per_sf=CostRange(low=150.0, expected=175.0, high=200.0),
            total_cost=CostRange(low=1_500_000, expected=1_750_000, high=2_000_000),
            percent_of_total=17.5,
            source="llm",
        ),
    ]


def _create_test_client(
    cost_engine: object | None = None,
) -> TestClient:
    app = create_app(cost_engine=cost_engine)  # type: ignore[arg-type]
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: POST /api/estimate with SpaceProgram
# ---------------------------------------------------------------------------


class TestEstimateWithSpaceProgram:
    """POST /api/estimate with SpaceProgram body returns room-type-aware estimate."""

    def test_estimate_with_space_program_returns_space_breakdown(self) -> None:
        space_breakdown = _make_space_breakdown()
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate(space_breakdown)
        client = _create_test_client(cost_engine=mock_engine)

        building = _make_building_model()
        program = _make_space_program()
        body = {
            "building": building.model_dump(mode="json"),
            "space_program": program.model_dump(mode="json"),
        }
        response = client.post("/api/estimate", json=body)

        assert response.status_code == 200
        data = response.json()
        assert "space_breakdown" in data
        assert len(data["space_breakdown"]) == 3
        assert data["space_breakdown"][0]["room_type"] == "lobby"
        assert data["space_breakdown"][0]["source"] == "geometry"

    def test_engine_receives_space_program(self) -> None:
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate()
        client = _create_test_client(cost_engine=mock_engine)

        building = _make_building_model()
        program = _make_space_program()
        body = {
            "building": building.model_dump(mode="json"),
            "space_program": program.model_dump(mode="json"),
        }
        client.post("/api/estimate", json=body)

        call_args = mock_engine.estimate.call_args
        assert call_args.kwargs["space_program"] is not None
        sp = call_args.kwargs["space_program"]
        assert isinstance(sp, SpaceProgram)
        assert len(sp.spaces) == 3

    def test_space_breakdown_has_correct_structure(self) -> None:
        space_breakdown = _make_space_breakdown()
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate(space_breakdown)
        client = _create_test_client(cost_engine=mock_engine)

        building = _make_building_model()
        program = _make_space_program()
        body = {
            "building": building.model_dump(mode="json"),
            "space_program": program.model_dump(mode="json"),
        }
        response = client.post("/api/estimate", json=body)

        data = response.json()
        sc = data["space_breakdown"][0]
        assert "room_type" in sc
        assert "name" in sc
        assert "area_sf" in sc
        assert "cost_per_sf" in sc
        assert "total_cost" in sc
        assert "percent_of_total" in sc
        assert "source" in sc
        # cost_per_sf and total_cost are ranges
        assert "low" in sc["cost_per_sf"]
        assert "expected" in sc["cost_per_sf"]
        assert "high" in sc["cost_per_sf"]


# ---------------------------------------------------------------------------
# Tests: POST /api/estimate without SpaceProgram (backward compatibility)
# ---------------------------------------------------------------------------


class TestEstimateWithoutSpaceProgram:
    """POST /api/estimate without SpaceProgram returns standard estimate."""

    def test_estimate_without_space_program_returns_standard(self) -> None:
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate()
        client = _create_test_client(cost_engine=mock_engine)

        building = _make_building_model()
        body = {"building": building.model_dump(mode="json")}
        response = client.post("/api/estimate", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["project_name"] == "Baltimore, MD"
        assert "total_cost" in data
        assert "breakdown" in data
        # space_breakdown in the model_dump will be None
        assert data.get("space_breakdown") is None

    def test_engine_receives_none_space_program(self) -> None:
        mock_engine = MagicMock()
        mock_engine.estimate.return_value = _make_cost_estimate()
        client = _create_test_client(cost_engine=mock_engine)

        building = _make_building_model()
        body = {"building": building.model_dump(mode="json")}
        client.post("/api/estimate", json=body)

        call_kwargs = mock_engine.estimate.call_args.kwargs
        assert call_kwargs["space_program"] is None

    def test_invalid_data_returns_422(self) -> None:
        mock_engine = MagicMock()
        client = _create_test_client(cost_engine=mock_engine)

        response = client.post("/api/estimate", json={"bad": "data"})
        assert response.status_code == 422
